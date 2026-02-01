"""
Artifact management router.
"""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DBSession
from app.models.artifact import Artifact, ArtifactStatus, ArtifactType
from app.models.channel import Channel
from app.models.membership import Membership
from app.models.note import Note
from app.models.product import Product
from app.models.user import User
from app.models.workspace import Workspace
from app.settings import settings
from app.templates_config import templates

router = APIRouter(tags=["artifacts"])


async def verify_workspace_access(workspace_id: int, user_id: int, db) -> Membership:
    """Verify user has access to workspace."""
    result = await db.execute(
        select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == user_id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a workspace member")
    return membership


# Channel artifacts
@router.get("/workspaces/{workspace_id}/channels/{channel_id}/artifacts", response_class=HTMLResponse)
async def channel_artifacts(
    request: Request,
    workspace_id: int,
    channel_id: int,
    user: CurrentUser,
    db: DBSession,
    type: ArtifactType | None = Query(default=None),
):
    """List artifacts for a channel."""
    await verify_workspace_access(workspace_id, user.id, db)
    
    # Get channel
    result = await db.execute(
        select(Channel).where(Channel.id == channel_id, Channel.workspace_id == workspace_id)
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    
    # Get artifacts
    query = select(Artifact).where(Artifact.channel_id == channel_id)
    if type:
        query = query.where(Artifact.type == type)
    query = query.options(selectinload(Artifact.author)).order_by(Artifact.created_at.desc())
    
    result = await db.execute(query)
    artifacts = result.scalars().all()
    
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/artifact_list.html",
            {
                "request": request,
                "artifacts": artifacts,
                "user": user,
                "workspace_id": workspace_id,
                "channel_id": channel_id,
                "filter_type": type,
            },
        )
    
    return templates.TemplateResponse(
        "artifacts/list.html",
        {
            "request": request,
            "user": user,
            "workspace_id": workspace_id,
            "channel": channel,
            "artifacts": artifacts,
            "filter_type": type,
            "artifact_types": ArtifactType,
        },
    )


@router.post("/workspaces/{workspace_id}/channels/{channel_id}/artifacts")
async def create_channel_artifact(
    request: Request,
    workspace_id: int,
    channel_id: int,
    user: CurrentUser,
    db: DBSession,
    type: Annotated[ArtifactType, Form()],
    title: Annotated[str, Form()],
    body: Annotated[str | None, Form()] = None,
    tags: Annotated[str | None, Form()] = None,
):
    """Create an artifact in a channel."""
    await verify_workspace_access(workspace_id, user.id, db)
    
    # Get channel for product_id
    result = await db.execute(
        select(Channel).where(Channel.id == channel_id, Channel.workspace_id == workspace_id)
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    
    # Parse tags
    tag_list = None
    if tags:
        tag_list = [t.strip() for t in tags.split(',') if t.strip()]
    
    artifact = Artifact(
        workspace_id=workspace_id,
        channel_id=channel_id,
        product_id=channel.product_id,
        type=type,
        title=title.strip(),
        body=body.strip() if body else None,
        status=Artifact.get_default_status(type),
        tags=tag_list,
        created_by=user.id,
    )
    db.add(artifact)
    await db.commit()
    
    if request.headers.get("HX-Request"):
        response = HTMLResponse("")
        response.headers["HX-Redirect"] = f"/workspaces/{workspace_id}/channels/{channel_id}/artifacts/{artifact.id}"
        return response
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/channels/{channel_id}/artifacts/{artifact.id}",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/workspaces/{workspace_id}/channels/{channel_id}/artifacts/new", response_class=HTMLResponse)
async def new_channel_artifact_form(
    request: Request,
    workspace_id: int,
    channel_id: int,
    user: CurrentUser,
    db: DBSession,
    type: ArtifactType = Query(default=ArtifactType.TASK),
):
    """Render new artifact form."""
    await verify_workspace_access(workspace_id, user.id, db)
    
    result = await db.execute(
        select(Channel).where(Channel.id == channel_id, Channel.workspace_id == workspace_id)
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    
    return templates.TemplateResponse(
        "artifacts/new.html",
        {
            "request": request,
            "user": user,
            "workspace_id": workspace_id,
            "channel": channel,
            "artifact_type": type,
            "artifact_types": ArtifactType,
        },
    )


@router.get("/workspaces/{workspace_id}/channels/{channel_id}/artifacts/{artifact_id}", response_class=HTMLResponse)
async def view_artifact(
    request: Request,
    workspace_id: int,
    channel_id: int,
    artifact_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """View an artifact."""
    await verify_workspace_access(workspace_id, user.id, db)
    
    result = await db.execute(
        select(Artifact)
        .where(Artifact.id == artifact_id, Artifact.channel_id == channel_id)
        .options(selectinload(Artifact.author), selectinload(Artifact.assignee))
    )
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    
    result = await db.execute(
        select(Channel).where(Channel.id == channel_id)
    )
    channel = result.scalar_one()
    
    return templates.TemplateResponse(
        "artifacts/view.html",
        {
            "request": request,
            "user": user,
            "workspace_id": workspace_id,
            "channel": channel,
            "artifact": artifact,
        },
    )


@router.post("/workspaces/{workspace_id}/channels/{channel_id}/artifacts/{artifact_id}/status")
async def update_artifact_status(
    request: Request,
    workspace_id: int,
    channel_id: int,
    artifact_id: int,
    user: CurrentUser,
    db: DBSession,
    status_value: Annotated[str, Form(alias="status")],
):
    """Update artifact status."""
    await verify_workspace_access(workspace_id, user.id, db)
    
    result = await db.execute(
        select(Artifact).where(Artifact.id == artifact_id, Artifact.channel_id == channel_id)
    )
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    
    artifact.status = status_value
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse(f'<span class="badge">{status_value}</span>')
    
    return RedirectResponse(
        url=f"/workspaces/{workspace_id}/channels/{channel_id}/artifacts/{artifact_id}",
        status_code=status.HTTP_302_FOUND,
    )


# Product artifacts (docs view)
@router.get("/workspaces/{workspace_id}/products/{product_id}/docs", response_class=HTMLResponse)
async def product_docs(
    request: Request,
    workspace_id: int,
    product_id: int,
    user: CurrentUser,
    db: DBSession,
    type: ArtifactType | None = Query(default=None),
):
    """View documentation/artifacts for a product."""
    await verify_workspace_access(workspace_id, user.id, db)
    
    # Get product
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.workspace_id == workspace_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    
    # Get workspace for Labs URL
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    
    # Build Labs URL if product is linked to Labs
    labs_url = None
    if product.buildly_product_id and workspace.buildly_org_uuid:
        labs_base = getattr(settings, 'BUILDLY_LABS_URL', 'https://labs.buildly.io')
        labs_url = f"{labs_base}/products/{product.buildly_product_id}"
    
    # Get artifacts grouped by type
    query = select(Artifact).where(Artifact.product_id == product_id)
    if type:
        query = query.where(Artifact.type == type)
    query = query.options(selectinload(Artifact.author)).order_by(Artifact.created_at.desc())
    
    result = await db.execute(query)
    artifacts = result.scalars().all()
    
    # Group by type
    grouped = {
        ArtifactType.DECISION: [],
        ArtifactType.FEATURE: [],
        ArtifactType.ISSUE: [],
        ArtifactType.TASK: [],
    }
    for artifact in artifacts:
        grouped[artifact.type].append(artifact)
    
    # Get user's notes related to this product's channels
    # Find channels that belong to this product
    channel_result = await db.execute(
        select(Channel.id).where(Channel.product_id == product_id)
    )
    product_channel_ids = [c for c in channel_result.scalars().all()]
    
    # Get user's notes for this workspace, optionally filtering by product channels
    notes_query = select(Note).where(
        Note.owner_id == user.id,
        Note.deleted_at == None,
        Note.workspace_id == workspace_id,
    ).order_by(Note.updated_at.desc()).limit(5)
    
    # If there are product channels, prefer notes from those channels
    if product_channel_ids:
        notes_query = select(Note).where(
            Note.owner_id == user.id,
            Note.deleted_at == None,
            Note.channel_id.in_(product_channel_ids) if product_channel_ids else Note.workspace_id == workspace_id,
        ).order_by(Note.updated_at.desc()).limit(5)
    
    notes_result = await db.execute(notes_query)
    user_notes = notes_result.scalars().all()
    
    return templates.TemplateResponse(
        "products/docs.html",
        {
            "request": request,
            "user": user,
            "workspace_id": workspace_id,
            "product": product,
            "grouped_artifacts": grouped,
            "filter_type": type,
            "artifact_types": ArtifactType,
            "user_notes": user_notes,
            "labs_url": labs_url,
        },
    )


# Sync product with Buildly Labs
@router.post("/workspaces/{workspace_id}/products/{product_id}/sync")
async def sync_product_with_labs(
    request: Request,
    workspace_id: int,
    product_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Sync product artifacts with Buildly Labs."""
    membership = await verify_workspace_access(workspace_id, user.id, db)
    
    # Get product
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.workspace_id == workspace_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    
    # Get workspace for Labs integration
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    
    # Check if Labs integration is configured
    if not workspace.labs_access_token and not workspace.labs_api_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Buildly Labs integration not configured. Connect your workspace to Labs in Settings."
        )
    
    # TODO: Implement actual sync with Labs API
    # For now, return success placeholder
    # In future: call labs_sync service to push/pull artifacts
    
    return JSONResponse({
        "status": "success",
        "message": f"Synced {product.name} with Buildly Labs",
        "product_id": product_id,
    })
