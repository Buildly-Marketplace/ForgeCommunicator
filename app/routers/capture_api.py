"""
Capture API for the Forge Capture mobile app (iOS + Android, see /mobile).

Quick-capture flow:
  1. POST /mobile/v1/ideas                 jot down an idea/bug (+ photos/screenshots)
  2. POST /mobile/v1/ideas/{id}/refine     AI turns it into features/issues + estimates
  3. PATCH /mobile/v1/ideas/{id}           user tweaks: deselect items, change builder
  4. POST /mobile/v1/ideas/{id}/submit     creates Forge artifacts + Labs backlog items,
                                           optionally assigning AI work to an agent

Plus read-only browsing of the user's Labs products and their backlog.

Auth: same Bearer session token as the rest of /mobile/v1.
"""

import json
import logging
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.deps import DBSession
from app.models.agent_integration import AgentIntegration
from app.models.artifact import Artifact, ArtifactType
from app.models.idea import Idea, IdeaKind, IdeaStatus
from app.models.membership import Membership
from app.models.product import Product
from app.models.workspace import Workspace
from app.routers.mobile_api import MobileUser
from app.routers.sync import get_workspace_labs_token
from app.services import idea_refiner
from app.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mobile/v1", tags=["capture"])

MAX_ATTACHMENTS = 6
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/heic", "image/heif"}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CaptureWorkspace(BaseModel):
    id: int
    name: str
    labs_connected: bool
    default_product_uuid: str | None = None


class CaptureBootstrap(BaseModel):
    workspaces: list[CaptureWorkspace]
    user_labs_connected: bool
    ai_configured: bool
    uploads_enabled: bool
    labs_web_url: str


class ProductOut(BaseModel):
    id: int
    workspace_id: int
    name: str
    description: str | None = None
    labs_uuid: str | None = None
    color: str | None = None
    icon_url: str | None = None
    open_features: int = 0
    open_issues: int = 0


class BacklogItemOut(BaseModel):
    id: int
    type: str
    title: str
    status: str
    priority: str | None = None
    severity: str | None = None
    labs_uuid: str | None = None
    assignee_agent: str | None = None
    created_at: datetime


class AgentOut(BaseModel):
    id: int
    name: str
    provider: str
    avatar_emoji: str | None = None


class IdeaOut(BaseModel):
    id: int
    workspace_id: int
    product_id: int | None = None
    product_name: str | None = None
    client_id: str | None = None
    kind: str
    title: str | None = None
    body: str
    status: str
    attachments: list[dict] = []
    context: dict | None = None
    breakdown: dict | None = None
    error: str | None = None
    submitted_items: list[dict] = []
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_idea(cls, idea: Idea) -> "IdeaOut":
        return cls(
            id=idea.id,
            workspace_id=idea.workspace_id,
            product_id=idea.product_id,
            product_name=idea.product.name if idea.product else None,
            client_id=idea.client_id,
            kind=idea.kind,
            title=idea.title,
            body=idea.body or "",
            status=idea.status,
            attachments=idea.attachments or [],
            context=idea.context,
            breakdown=idea.breakdown,
            error=idea.error,
            submitted_items=idea.submitted_items or [],
            created_at=idea.created_at,
            updated_at=idea.updated_at,
        )


class ItemPatch(BaseModel):
    id: str
    selected: bool | None = None
    builder: Literal["dev", "ai", "pair"] | None = None
    title: str | None = Field(default=None, max_length=200)
    priority: Literal["low", "medium", "high", "critical"] | None = None


class IdeaPatch(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    body: str | None = None
    kind: Literal["idea", "bug", "feedback"] | None = None
    product_id: int | None = None
    items: list[ItemPatch] | None = None


class SubmitRequest(BaseModel):
    push_to_labs: bool = True
    # Agent to assign "ai" and "pair" items to (see /workspaces/{id}/agents)
    agent_integration_id: int | None = None


class SubmitResult(BaseModel):
    idea: IdeaOut
    created: list[dict]
    labs_pushed: int
    warnings: list[str] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _require_member(db, workspace_id: int, user_id: int) -> Membership:
    result = await db.execute(
        select(Membership).where(Membership.workspace_id == workspace_id, Membership.user_id == user_id)
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a workspace member")
    return membership


async def _get_idea(db, idea_id: int, user_id: int) -> Idea:
    result = await db.execute(
        select(Idea).options(selectinload(Idea.product)).where(Idea.id == idea_id)
    )
    idea = result.scalar_one_or_none()
    # Captures are personal until submitted — only the author can see/edit them.
    if not idea or idea.created_by != user_id:
        raise HTTPException(status_code=404, detail="Idea not found")
    return idea


async def _check_product(db, product_id: int | None, workspace_id: int) -> Product | None:
    if product_id is None:
        return None
    product = await db.get(Product, product_id)
    if not product or product.workspace_id != workspace_id:
        raise HTTPException(status_code=400, detail="Product not in this workspace")
    return product


def _parse_context(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="context must be a JSON object")
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="context must be a JSON object")
    # Keep it small and flat
    return {str(k)[:50]: str(v)[:300] for k, v in list(data.items())[:20] if v is not None}


def _upload_attachments(files: list[UploadFile], user_id: int) -> list[dict]:
    if not files:
        return []
    if len(files) > MAX_ATTACHMENTS:
        raise HTTPException(status_code=422, detail=f"At most {MAX_ATTACHMENTS} attachments")
    if not settings.file_storage_enabled:
        raise HTTPException(
            status_code=503,
            detail="File uploads are not configured on this server (STORAGE_* settings)",
        )
    from app.services.storage import StorageError, get_storage_service

    storage = get_storage_service()
    out = []
    for f in files:
        if f.content_type and f.content_type not in IMAGE_TYPES:
            raise HTTPException(status_code=422, detail=f"Only images are supported ({f.filename})")
        try:
            key, ctype, size = storage.upload_file(
                f.file, f.filename or "capture.jpg", f.content_type, channel_id=0,
                prefix=f"ideas/{user_id}",
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except StorageError as e:
            raise HTTPException(status_code=502, detail=str(e))
        out.append({
            "url": storage.get_public_url(key),
            "storage_key": key,
            "filename": f.filename,
            "content_type": ctype,
            "size": size,
        })
    return out


def _apply_item_patches(breakdown: dict, patches: list[ItemPatch]) -> dict:
    by_id = {item["id"]: item for item in breakdown.get("items", [])}
    for patch in patches:
        item = by_id.get(patch.id)
        if not item:
            raise HTTPException(status_code=422, detail=f"Unknown item {patch.id}")
        for field in ("selected", "builder", "title", "priority"):
            value = getattr(patch, field)
            if value is not None:
                item[field] = value
    breakdown["totals"] = idea_refiner.compute_totals(breakdown.get("items", []))
    return breakdown


# ---------------------------------------------------------------------------
# Bootstrap, products, backlog, agents
# ---------------------------------------------------------------------------


@router.get("/capture/bootstrap", response_model=CaptureBootstrap)
async def capture_bootstrap(user: MobileUser, db: DBSession):
    """Everything the app needs on launch: workspaces + which integrations are live."""
    result = await db.execute(
        select(Workspace)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == user.id)
        .order_by(Workspace.name)
    )
    workspaces = result.scalars().all()
    return CaptureBootstrap(
        workspaces=[
            CaptureWorkspace(
                id=w.id,
                name=w.name,
                labs_connected=bool(w.labs_api_token or w.labs_access_token or user.labs_access_token
                                    or settings.labs_api_key),
                default_product_uuid=w.labs_default_product_uuid,
            )
            for w in workspaces
        ],
        user_labs_connected=bool(user.labs_access_token),
        ai_configured=bool(settings.idea_ai_provider and settings.idea_ai_api_key),
        uploads_enabled=settings.file_storage_enabled,
        labs_web_url=settings.buildly_oauth_url,
    )


@router.get("/workspaces/{workspace_id}/products", response_model=list[ProductOut])
async def list_products(workspace_id: int, user: MobileUser, db: DBSession):
    await _require_member(db, workspace_id, user.id)
    result = await db.execute(
        select(Product)
        .where(Product.workspace_id == workspace_id, Product.is_active.is_(True))
        .order_by(Product.name)
    )
    products = result.scalars().all()

    counts: dict[tuple[int, str], int] = {}
    if products:
        rows = await db.execute(
            select(Artifact.product_id, Artifact.type, func.count())
            .where(
                Artifact.product_id.in_([p.id for p in products]),
                Artifact.status.notin_(["closed", "done", "shipped", "wont_fix", "rejected"]),
            )
            .group_by(Artifact.product_id, Artifact.type)
        )
        counts = {(pid, str(t)): n for pid, t, n in rows.all()}

    return [
        ProductOut(
            id=p.id,
            workspace_id=p.workspace_id,
            name=p.name,
            description=p.description,
            labs_uuid=p.buildly_product_uuid,
            color=p.color,
            icon_url=p.icon_url,
            open_features=counts.get((p.id, "feature"), 0),
            open_issues=counts.get((p.id, "issue"), 0),
        )
        for p in products
    ]


@router.post("/workspaces/{workspace_id}/products/sync")
async def sync_products_from_labs(workspace_id: int, user: MobileUser, db: DBSession):
    """Pull the latest product list (and backlogs) from Buildly Labs."""
    await _require_member(db, workspace_id, user.id)
    token, method = await get_workspace_labs_token(db, workspace_id, user)
    if not token:
        raise HTTPException(status_code=400, detail="Buildly Labs is not connected for this workspace")
    from app.services.labs_sync import sync_all_from_labs

    try:
        results = await sync_all_from_labs(db, workspace_id, user.id, access_token=token)
    except Exception as e:  # Labs returns a variety of errors; surface them to the app
        logger.warning("Labs sync failed for workspace %s: %s", workspace_id, e)
        raise HTTPException(status_code=502, detail=f"Labs sync failed: {e}")
    return {"results": results, "auth_method": method}


@router.get("/products/{product_id}/items", response_model=list[BacklogItemOut])
async def product_items(
    product_id: int,
    user: MobileUser,
    db: DBSession,
    type: Literal["feature", "issue", "task", "decision"] | None = Query(default=None),
    limit: int = Query(default=100, le=500),
):
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    await _require_member(db, product.workspace_id, user.id)

    query = (
        select(Artifact)
        .options(selectinload(Artifact.assignee_agent))
        .where(Artifact.product_id == product_id)
        .order_by(Artifact.created_at.desc())
        .limit(limit)
    )
    if type:
        query = query.where(Artifact.type == type)
    result = await db.execute(query)
    return [
        BacklogItemOut(
            id=a.id,
            type=str(a.type.value if hasattr(a.type, "value") else a.type),
            title=a.title,
            status=a.status,
            priority=a.priority,
            severity=a.severity,
            labs_uuid=a.buildly_item_uuid,
            assignee_agent=a.assignee_agent.name if a.assignee_agent else None,
            created_at=a.created_at,
        )
        for a in result.scalars().all()
    ]


@router.get("/workspaces/{workspace_id}/agents", response_model=list[AgentOut])
async def list_agents(workspace_id: int, user: MobileUser, db: DBSession):
    """AI coding agents (Claude Code, Codex, ...) that AI-buildable items can be assigned to."""
    await _require_member(db, workspace_id, user.id)
    result = await db.execute(
        select(AgentIntegration)
        .where(
            AgentIntegration.workspace_id == workspace_id,
            AgentIntegration.is_active.is_(True),
            AgentIntegration.revoked_at.is_(None),
        )
        .order_by(AgentIntegration.name)
    )
    return [
        AgentOut(id=a.id, name=a.name, provider=a.provider, avatar_emoji=a.avatar_emoji)
        for a in result.scalars().all()
    ]


# ---------------------------------------------------------------------------
# Ideas
# ---------------------------------------------------------------------------


@router.post("/ideas", response_model=IdeaOut, status_code=201)
async def create_idea(
    user: MobileUser,
    db: DBSession,
    workspace_id: int = Form(...),
    body: str = Form(default=""),
    kind: Literal["idea", "bug", "feedback"] = Form(default="idea"),
    title: str | None = Form(default=None, max_length=200),
    product_id: int | None = Form(default=None),
    client_id: str | None = Form(default=None, max_length=64),
    context: str | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
):
    """Save a quick capture. Multipart so photos/screenshots can ride along."""
    await _require_member(db, workspace_id, user.id)
    if not body.strip() and not files:
        raise HTTPException(status_code=422, detail="Write something or attach a photo")

    if client_id:
        # Offline queue retries: return the existing capture instead of duplicating it
        existing = await db.execute(
            select(Idea)
            .options(selectinload(Idea.product))
            .where(Idea.created_by == user.id, Idea.client_id == client_id)
        )
        found = existing.scalar_one_or_none()
        if found:
            return IdeaOut.from_idea(found)

    await _check_product(db, product_id, workspace_id)
    attachments = _upload_attachments(files, user.id)

    idea = Idea(
        workspace_id=workspace_id,
        product_id=product_id,
        created_by=user.id,
        client_id=client_id,
        kind=IdeaKind(kind).value,
        title=(title or "").strip() or None,
        body=body.strip(),
        status=IdeaStatus.DRAFT.value,
        attachments=attachments,
        context=_parse_context(context),
    )
    db.add(idea)
    await db.commit()
    return IdeaOut.from_idea(await _get_idea(db, idea.id, user.id))


@router.get("/ideas", response_model=list[IdeaOut])
async def list_ideas(
    user: MobileUser,
    db: DBSession,
    workspace_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    query = (
        select(Idea)
        .options(selectinload(Idea.product))
        .where(Idea.created_by == user.id)
        .order_by(Idea.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if workspace_id is not None:
        query = query.where(Idea.workspace_id == workspace_id)
    if status:
        query = query.where(Idea.status == status)
    result = await db.execute(query)
    return [IdeaOut.from_idea(i) for i in result.scalars().all()]


@router.get("/ideas/{idea_id}", response_model=IdeaOut)
async def get_idea(idea_id: int, user: MobileUser, db: DBSession):
    return IdeaOut.from_idea(await _get_idea(db, idea_id, user.id))


@router.patch("/ideas/{idea_id}", response_model=IdeaOut)
async def update_idea(idea_id: int, patch: IdeaPatch, user: MobileUser, db: DBSession):
    idea = await _get_idea(db, idea_id, user.id)
    if idea.status == IdeaStatus.SUBMITTED.value:
        raise HTTPException(status_code=409, detail="Already submitted to Labs")

    fields = patch.model_fields_set
    if "title" in fields:
        idea.title = (patch.title or "").strip() or None
    if "body" in fields and patch.body is not None:
        idea.body = patch.body.strip()
    if "kind" in fields and patch.kind:
        idea.kind = patch.kind
    if "product_id" in fields:
        await _check_product(db, patch.product_id, idea.workspace_id)
        idea.product_id = patch.product_id
    if patch.items:
        if not idea.breakdown:
            raise HTTPException(status_code=409, detail="Refine the idea before editing items")
        # Reassign so SQLAlchemy notices the JSON change
        idea.breakdown = _apply_item_patches(json.loads(json.dumps(idea.breakdown)), patch.items)

    await db.commit()
    db.expire(idea)
    return IdeaOut.from_idea(await _get_idea(db, idea_id, user.id))


@router.delete("/ideas/{idea_id}", status_code=204)
async def delete_idea(idea_id: int, user: MobileUser, db: DBSession):
    idea = await _get_idea(db, idea_id, user.id)
    await db.delete(idea)
    await db.commit()


@router.post("/ideas/{idea_id}/refine", response_model=IdeaOut)
async def refine_idea(idea_id: int, user: MobileUser, db: DBSession):
    """Run the AI breakdown (features/issues + dev/AI estimates). Safe to re-run."""
    idea = await _get_idea(db, idea_id, user.id)
    if idea.status == IdeaStatus.SUBMITTED.value:
        raise HTTPException(status_code=409, detail="Already submitted to Labs")

    idea.status = IdeaStatus.REFINING.value
    idea.error = None
    await db.commit()

    try:
        breakdown = await idea_refiner.refine_idea(db, idea)
    except Exception as e:  # provider/network errors — keep the capture, let the user retry
        logger.warning("Refine failed for idea %s: %s", idea_id, e)
        idea.status = IdeaStatus.FAILED.value
        idea.error = f"AI refinement failed: {e}"[:1000]
    else:
        idea.breakdown = breakdown
        idea.status = IdeaStatus.REFINED.value
        if not idea.title:
            idea.title = breakdown.get("title")
    await db.commit()
    db.expire(idea)
    return IdeaOut.from_idea(await _get_idea(db, idea_id, user.id))


LABS_TYPE = {"feature": "story", "issue": "bug", "task": "task"}
ARTIFACT_TYPE = {"feature": ArtifactType.FEATURE, "issue": ArtifactType.ISSUE, "task": ArtifactType.TASK}


@router.post("/ideas/{idea_id}/submit", response_model=SubmitResult)
async def submit_idea(idea_id: int, req: SubmitRequest, user: MobileUser, db: DBSession):
    """Create Forge artifacts (and Labs backlog items) from the selected breakdown items."""
    idea = await _get_idea(db, idea_id, user.id)
    await _require_member(db, idea.workspace_id, user.id)
    if idea.status == IdeaStatus.SUBMITTED.value:
        raise HTTPException(status_code=409, detail="Already submitted to Labs")
    if not idea.breakdown:
        # Allow one-tap send: refine with whatever engine is available first
        idea.breakdown = await idea_refiner.refine_idea(db, idea)

    items = [i for i in idea.breakdown.get("items", []) if i.get("selected", True)]
    if not items:
        raise HTTPException(status_code=422, detail="Select at least one item to send")

    agent = None
    if req.agent_integration_id is not None:
        agent = await db.get(AgentIntegration, req.agent_integration_id)
        if not agent or agent.workspace_id != idea.workspace_id or not agent.is_valid:
            raise HTTPException(status_code=400, detail="Agent not available in this workspace")

    warnings: list[str] = []
    labs_service = None
    product_uuid = None
    if req.push_to_labs:
        workspace = await db.get(Workspace, idea.workspace_id)
        product_uuid = (idea.product.buildly_product_uuid if idea.product else None) \
            or (workspace.labs_default_product_uuid if workspace else None)
        token, _ = await get_workspace_labs_token(db, idea.workspace_id, user)
        if not token:
            warnings.append("Buildly Labs is not connected — items were saved in Forge only.")
        elif not product_uuid:
            warnings.append("Pick a Labs product (or set a workspace default) to push items to Labs.")
        else:
            from app.services.labs_sync import LabsSyncService
            labs_service = LabsSyncService(access_token=token)

    created: list[dict[str, Any]] = []
    labs_pushed = 0
    for item in items:
        body = idea_refiner.render_item_markdown(item, idea, idea.breakdown)
        artifact_type = ARTIFACT_TYPE.get(item["type"], ArtifactType.FEATURE)
        artifact = Artifact(
            workspace_id=idea.workspace_id,
            product_id=idea.product_id,
            type=artifact_type.value,
            title=item["title"],
            body=body,
            status=Artifact.get_default_status(artifact_type),
            tags=["capture", f"builder:{item['builder']}", f"points:{item['estimate']['points']}"],
            created_by=user.id,
            priority=item["priority"] if item["priority"] != "critical" else "urgent",
            severity=item["priority"] if artifact_type == ArtifactType.ISSUE else None,
            assignee_agent_id=agent.id if agent and item["builder"] in ("ai", "pair") else None,
        )
        db.add(artifact)
        await db.flush()

        labs_uuid = None
        if labs_service:
            try:
                result = await labs_service.create_backlog_item(
                    product_uuid=product_uuid,
                    title=item["title"],
                    description=body,
                    item_type=LABS_TYPE.get(item["type"], "story"),
                    priority=item["priority"],
                )
                labs_uuid = result.get("uuid") or (result.get("data") or {}).get("uuid")
                if labs_uuid:
                    artifact.buildly_item_uuid = labs_uuid
                    labs_pushed += 1
            except Exception as e:
                warnings.append(f"Labs push failed for “{item['title']}”: {e}"[:300])

        created.append({
            "artifact_id": artifact.id,
            "item_id": item["id"],
            "type": item["type"],
            "title": item["title"],
            "builder": item["builder"],
            "labs_uuid": labs_uuid,
            "assigned_agent": agent.name if artifact.assignee_agent_id else None,
        })

    idea.submitted_items = created
    idea.status = IdeaStatus.SUBMITTED.value
    idea.error = None
    await db.commit()
    db.expire(idea)
    return SubmitResult(
        idea=IdeaOut.from_idea(await _get_idea(db, idea_id, user.id)),
        created=created,
        labs_pushed=labs_pushed,
        warnings=warnings,
    )
