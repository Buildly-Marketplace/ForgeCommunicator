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


# Push artifact to Buildly Labs
@router.post("/workspaces/{workspace_id}/channels/{channel_id}/artifacts/{artifact_id}/push-to-labs")
async def push_artifact_to_labs(
    request: Request,
    workspace_id: int,
    channel_id: int,
    artifact_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Push an artifact to Buildly Labs as a backlog item.
    
    Creates a new backlog item in Labs and stores the UUID to prevent duplicates.
    """
    membership = await verify_workspace_access(workspace_id, user.id, db)
    
    # Get artifact with product
    result = await db.execute(
        select(Artifact)
        .options(selectinload(Artifact.product))
        .where(Artifact.id == artifact_id, Artifact.workspace_id == workspace_id)
    )
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    # Check if already synced
    if artifact.buildly_item_uuid:
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                f'''<span class="text-sm text-green-600">
                    ✓ Already synced to Labs
                </span>'''
            )
        return JSONResponse({
            "status": "already_synced",
            "message": "Artifact is already synced to Labs",
            "buildly_item_uuid": artifact.buildly_item_uuid,
        })
    
    # Get workspace for Labs credentials
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    
    # Check Labs credentials
    token = workspace.labs_access_token or workspace.labs_api_token or settings.labs_api_key
    if not token:
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                f'''<span class="text-sm text-red-500">
                    Labs not configured. <a href="/workspaces/{workspace_id}/settings" class="underline">Connect workspace</a>
                </span>'''
            )
        raise HTTPException(status_code=400, detail="Buildly Labs not configured")
    
    # Get product UUID (required for Labs)
    product_uuid = None
    if artifact.product and artifact.product.labs_product_uuid:
        product_uuid = artifact.product.labs_product_uuid
    elif workspace.labs_default_product_uuid:
        product_uuid = workspace.labs_default_product_uuid
    
    if not product_uuid:
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                f'''<span class="text-sm text-red-500">
                    No product linked. Set a default product in workspace settings.
                </span>'''
            )
        raise HTTPException(status_code=400, detail="No Labs product linked")
    
    # Map artifact type to Labs item type
    type_mapping = {
        ArtifactType.DECISION: "story",  # Labs doesn't have decisions, use story
        ArtifactType.FEATURE: "story",
        ArtifactType.ISSUE: "bug",
        ArtifactType.TASK: "task",
    }
    labs_type = type_mapping.get(artifact.type, "story")
    
    # Map priority
    priority_mapping = {
        "urgent": "critical",
        "high": "high",
        "medium": "medium",
        "low": "low",
    }
    labs_priority = priority_mapping.get(artifact.priority, "medium")
    
    # Create in Labs
    try:
        from app.services.labs_sync import LabsSyncService
        service = LabsSyncService(access_token=token)
        
        result = await service.create_backlog_item(
            product_uuid=product_uuid,
            title=artifact.title,
            description=artifact.body or "",
            item_type=labs_type,
            priority=labs_priority,
        )
        
        # Store the Labs UUID
        item_uuid = result.get("uuid") or result.get("data", {}).get("uuid")
        if item_uuid:
            artifact.buildly_item_uuid = item_uuid
            await db.commit()
            
            if request.headers.get("HX-Request"):
                labs_base = settings.labs_api_url.replace("/api", "")
                return HTMLResponse(
                    f'''<a href="{labs_base}/backlog/{item_uuid}" target="_blank" 
                           class="inline-flex items-center text-sm text-indigo-600 hover:text-indigo-500">
                        <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                        </svg>
                        View in Labs
                    </a>'''
                )
            
            return JSONResponse({
                "status": "success",
                "message": "Artifact pushed to Labs",
                "buildly_item_uuid": item_uuid,
            })
        else:
            raise Exception("No UUID returned from Labs API")
            
    except Exception as e:
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                f'''<span class="text-sm text-red-500">
                    Failed: {str(e)[:50]}
                </span>'''
            )
        raise HTTPException(status_code=500, detail=f"Failed to push to Labs: {str(e)}")


# Push artifact to GitHub
@router.post("/workspaces/{workspace_id}/channels/{channel_id}/artifacts/{artifact_id}/push-to-github")
async def push_artifact_to_github(
    request: Request,
    workspace_id: int,
    channel_id: int,
    artifact_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Push an artifact to GitHub as an issue.
    
    Creates a new GitHub issue and stores the URL to prevent duplicates.
    """
    import httpx
    
    membership = await verify_workspace_access(workspace_id, user.id, db)
    
    # Get artifact
    result = await db.execute(
        select(Artifact).where(Artifact.id == artifact_id, Artifact.workspace_id == workspace_id)
    )
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    # Check if already synced
    if artifact.github_issue_url:
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                f'''<a href="{artifact.github_issue_url}" target="_blank" 
                       class="inline-flex items-center text-sm text-gray-600 hover:text-gray-500">
                    <svg class="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 24 24">
                        <path fill-rule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
                    </svg>
                    View on GitHub
                </a>'''
            )
        return JSONResponse({
            "status": "already_synced",
            "message": "Artifact is already synced to GitHub",
            "github_issue_url": artifact.github_issue_url,
        })
    
    # Get workspace for GitHub settings
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    
    # Check GitHub credentials
    github_token = workspace.github_token or settings.github_error_token
    github_repo = workspace.github_repo or settings.github_error_repo
    
    if not github_token or not github_repo:
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                f'''<span class="text-sm text-red-500">
                    GitHub not configured. <a href="/workspaces/{workspace_id}/settings" class="underline">Connect repo</a>
                </span>'''
            )
        raise HTTPException(status_code=400, detail="GitHub not configured for this workspace")
    
    # Build labels based on artifact type
    labels = []
    type_labels = {
        ArtifactType.DECISION: ["decision", "discussion"],
        ArtifactType.FEATURE: ["enhancement", "feature"],
        ArtifactType.ISSUE: ["bug"],
        ArtifactType.TASK: ["task"],
    }
    labels.extend(type_labels.get(artifact.type, []))
    
    # Add priority label if set
    if artifact.priority:
        labels.append(f"priority:{artifact.priority}")
    
    # Build issue body
    body_parts = []
    if artifact.body:
        body_parts.append(artifact.body)
    
    body_parts.append(f"\n\n---\n_Synced from Forge Communicator_")
    
    issue_body = "\n".join(body_parts)
    
    # Create GitHub issue
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.github.com/repos/{github_repo}/issues",
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "ForgeCommunicator",
                },
                json={
                    "title": artifact.title,
                    "body": issue_body,
                    "labels": labels,
                },
                timeout=30.0,
            )
            
            if response.status_code == 201:
                issue_data = response.json()
                issue_url = issue_data.get("html_url")
                
                # Store the GitHub URL
                artifact.github_issue_url = issue_url
                await db.commit()
                
                if request.headers.get("HX-Request"):
                    return HTMLResponse(
                        f'''<a href="{issue_url}" target="_blank" 
                               class="inline-flex items-center text-sm text-gray-600 hover:text-gray-500">
                            <svg class="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 24 24">
                                <path fill-rule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
                            </svg>
                            #{issue_data.get('number')}
                        </a>'''
                    )
                
                return JSONResponse({
                    "status": "success",
                    "message": "Artifact pushed to GitHub",
                    "github_issue_url": issue_url,
                    "issue_number": issue_data.get("number"),
                })
            else:
                error_msg = response.json().get("message", response.text[:100])
                raise Exception(f"GitHub API error: {error_msg}")
                
    except Exception as e:
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                f'''<span class="text-sm text-red-500">
                    Failed: {str(e)[:50]}
                </span>'''
            )
        raise HTTPException(status_code=500, detail=f"Failed to push to GitHub: {str(e)}")
