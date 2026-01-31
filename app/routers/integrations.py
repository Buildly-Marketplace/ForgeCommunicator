"""
External integrations router for Slack/Discord notifications.

Handles OAuth flows, webhook callbacks, and notification settings.
"""

import secrets
import logging
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DBSession
from app.models.external_integration import (
    ExternalIntegration,
    IntegrationType,
    NotificationLog,
    NotificationSource,
)
from app.services.slack import slack_service
from app.services.discord import discord_service
from app.settings import settings
from app.templates_config import templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


# ==================== Slack OAuth ====================

@router.get("/slack/connect")
async def slack_connect(
    request: Request,
    user: CurrentUser,
):
    """Start Slack OAuth flow."""
    if not settings.slack_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slack integration is not configured",
        )
    
    # Build redirect URI
    proto = request.headers.get("X-Forwarded-Proto", "https" if not settings.debug else "http")
    host = request.headers.get("X-Forwarded-Host", request.url.netloc)
    redirect_uri = f"{proto}://{host}/integrations/slack/callback"
    
    # Generate state token
    state = secrets.token_urlsafe(32)
    
    # Get authorization URL
    auth_url = slack_service.get_authorization_url(state, redirect_uri)
    
    response = RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="slack_oauth_state",
        value=state,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        max_age=600,  # 10 minutes
    )
    response.set_cookie(
        key="slack_redirect_uri",
        value=redirect_uri,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        max_age=600,
    )
    return response


@router.get("/slack/callback")
async def slack_callback(
    request: Request,
    db: DBSession,
    user: CurrentUser,
    code: str = Query(...),
    state: str = Query(...),
):
    """Handle Slack OAuth callback."""
    # Verify state
    stored_state = request.cookies.get("slack_oauth_state")
    redirect_uri = request.cookies.get("slack_redirect_uri")
    
    if not stored_state or state != stored_state:
        return RedirectResponse(
            url="/profile/integrations?error=Invalid+state",
            status_code=status.HTTP_302_FOUND,
        )
    
    # Exchange code for tokens
    token_data = await slack_service.exchange_code_for_token(code, redirect_uri)
    
    if not token_data:
        return RedirectResponse(
            url="/profile/integrations?error=Failed+to+connect+Slack",
            status_code=status.HTTP_302_FOUND,
        )
    
    # Extract user token data (authed_user contains user-level tokens)
    authed_user = token_data.get("authed_user", {})
    access_token = authed_user.get("access_token")
    
    if not access_token:
        logger.error(f"No user access token in Slack response: {token_data}")
        return RedirectResponse(
            url="/profile/integrations?error=No+access+token+received",
            status_code=status.HTTP_302_FOUND,
        )
    
    # Get or create integration record
    result = await db.execute(
        select(ExternalIntegration).where(
            ExternalIntegration.user_id == user.id,
            ExternalIntegration.integration_type == IntegrationType.SLACK,
        )
    )
    integration = result.scalar_one_or_none()
    
    if not integration:
        integration = ExternalIntegration(
            user_id=user.id,
            integration_type=IntegrationType.SLACK,
            notification_preferences={
                "dm": True,
                "mentions": True,
                "channels": [],
            },
        )
        db.add(integration)
    
    # Update tokens and info
    integration.access_token = access_token
    integration.external_user_id = authed_user.get("id")
    integration.external_team_id = token_data.get("team", {}).get("id")
    integration.external_team_name = token_data.get("team", {}).get("name")
    integration.is_active = True
    
    await db.commit()
    
    # Clear OAuth cookies
    response = RedirectResponse(
        url="/profile/integrations?success=slack",
        status_code=status.HTTP_302_FOUND,
    )
    response.delete_cookie("slack_oauth_state")
    response.delete_cookie("slack_redirect_uri")
    return response


@router.post("/slack/disconnect")
async def slack_disconnect(
    request: Request,
    db: DBSession,
    user: CurrentUser,
):
    """Disconnect Slack integration."""
    result = await db.execute(
        select(ExternalIntegration).where(
            ExternalIntegration.user_id == user.id,
            ExternalIntegration.integration_type == IntegrationType.SLACK,
        )
    )
    integration = result.scalar_one_or_none()
    
    if integration:
        integration.is_active = False
        integration.access_token = None
        integration.refresh_token = None
        await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse('<div class="text-green-500">Slack disconnected</div>')
    
    return RedirectResponse(
        url="/profile/integrations",
        status_code=status.HTTP_302_FOUND,
    )


# ==================== Discord OAuth ====================

@router.get("/discord/connect")
async def discord_connect(
    request: Request,
    user: CurrentUser,
):
    """Start Discord OAuth flow."""
    if not settings.discord_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discord integration is not configured",
        )
    
    # Build redirect URI
    proto = request.headers.get("X-Forwarded-Proto", "https" if not settings.debug else "http")
    host = request.headers.get("X-Forwarded-Host", request.url.netloc)
    redirect_uri = f"{proto}://{host}/integrations/discord/callback"
    
    # Generate state token
    state = secrets.token_urlsafe(32)
    
    # Get authorization URL
    auth_url = discord_service.get_authorization_url(state, redirect_uri)
    
    response = RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="discord_oauth_state",
        value=state,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        max_age=600,
    )
    response.set_cookie(
        key="discord_redirect_uri",
        value=redirect_uri,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        max_age=600,
    )
    return response


@router.get("/discord/callback")
async def discord_callback(
    request: Request,
    db: DBSession,
    user: CurrentUser,
    code: str = Query(...),
    state: str = Query(...),
):
    """Handle Discord OAuth callback."""
    # Verify state
    stored_state = request.cookies.get("discord_oauth_state")
    redirect_uri = request.cookies.get("discord_redirect_uri")
    
    if not stored_state or state != stored_state:
        return RedirectResponse(
            url="/profile/integrations?error=Invalid+state",
            status_code=status.HTTP_302_FOUND,
        )
    
    # Exchange code for tokens
    token_data = await discord_service.exchange_code_for_token(code, redirect_uri)
    
    if not token_data:
        return RedirectResponse(
            url="/profile/integrations?error=Failed+to+connect+Discord",
            status_code=status.HTTP_302_FOUND,
        )
    
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in")
    
    # Get Discord user info
    discord_user = await discord_service.get_current_user(access_token)
    
    if not discord_user:
        return RedirectResponse(
            url="/profile/integrations?error=Failed+to+get+Discord+user",
            status_code=status.HTTP_302_FOUND,
        )
    
    # Get or create integration record
    result = await db.execute(
        select(ExternalIntegration).where(
            ExternalIntegration.user_id == user.id,
            ExternalIntegration.integration_type == IntegrationType.DISCORD,
        )
    )
    integration = result.scalar_one_or_none()
    
    if not integration:
        integration = ExternalIntegration(
            user_id=user.id,
            integration_type=IntegrationType.DISCORD,
            notification_preferences={
                "dm": True,
                "mentions": True,
                "guilds": [],
            },
        )
        db.add(integration)
    
    # Update tokens and info
    integration.update_tokens(access_token, refresh_token, expires_in)
    integration.external_user_id = discord_user.get("id")
    integration.external_username = f"{discord_user.get('username')}#{discord_user.get('discriminator', '0')}"
    integration.is_active = True
    
    await db.commit()
    
    # Clear OAuth cookies
    response = RedirectResponse(
        url="/profile/integrations?success=discord",
        status_code=status.HTTP_302_FOUND,
    )
    response.delete_cookie("discord_oauth_state")
    response.delete_cookie("discord_redirect_uri")
    return response


@router.post("/discord/disconnect")
async def discord_disconnect(
    request: Request,
    db: DBSession,
    user: CurrentUser,
):
    """Disconnect Discord integration."""
    result = await db.execute(
        select(ExternalIntegration).where(
            ExternalIntegration.user_id == user.id,
            ExternalIntegration.integration_type == IntegrationType.DISCORD,
        )
    )
    integration = result.scalar_one_or_none()
    
    if integration:
        # Revoke token
        if integration.access_token:
            await discord_service.revoke_token(integration.access_token)
        
        integration.is_active = False
        integration.access_token = None
        integration.refresh_token = None
        await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse('<div class="text-green-500">Discord disconnected</div>')
    
    return RedirectResponse(
        url="/profile/integrations",
        status_code=status.HTTP_302_FOUND,
    )


# ==================== Notification Settings ====================

@router.post("/{integration_type}/settings")
async def update_integration_settings(
    request: Request,
    db: DBSession,
    user: CurrentUser,
    integration_type: str,
    dm: Annotated[str | None, Form()] = None,
    mentions: Annotated[str | None, Form()] = None,
    channels: Annotated[str | None, Form()] = None,
):
    """Update notification preferences for an integration."""
    try:
        int_type = IntegrationType(integration_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid integration type")
    
    result = await db.execute(
        select(ExternalIntegration).where(
            ExternalIntegration.user_id == user.id,
            ExternalIntegration.integration_type == int_type,
        )
    )
    integration = result.scalar_one_or_none()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    # Update preferences
    prefs = integration.notification_preferences or {}
    prefs["dm"] = dm == "true"
    prefs["mentions"] = mentions == "true"
    
    # Parse channel list (comma-separated)
    if channels:
        prefs["channels"] = [c.strip() for c in channels.split(",") if c.strip()]
    else:
        prefs["channels"] = []
    
    integration.notification_preferences = prefs
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse('<div class="text-green-500 text-sm">Settings saved!</div>')
    
    return RedirectResponse(
        url="/profile/integrations",
        status_code=status.HTTP_302_FOUND,
    )


# ==================== Notifications Feed ====================

@router.get("/notifications", response_class=HTMLResponse)
async def notifications_feed(
    request: Request,
    db: DBSession,
    user: CurrentUser,
    page: int = 1,
    per_page: int = 50,
):
    """View aggregated notifications from Slack/Discord."""
    # Get user's integrations
    result = await db.execute(
        select(ExternalIntegration).where(
            ExternalIntegration.user_id == user.id,
            ExternalIntegration.is_active == True,
        )
    )
    integrations = result.scalars().all()
    
    # Get notifications
    offset = (page - 1) * per_page
    result = await db.execute(
        select(NotificationLog)
        .where(NotificationLog.user_id == user.id)
        .order_by(NotificationLog.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    notifications = result.scalars().all()
    
    # Count unread
    result = await db.execute(
        select(NotificationLog)
        .where(
            NotificationLog.user_id == user.id,
            NotificationLog.is_read == False,
        )
    )
    unread_count = len(result.scalars().all())
    
    return templates.TemplateResponse(
        "integrations/notifications.html",
        {
            "request": request,
            "user": user,
            "integrations": integrations,
            "notifications": notifications,
            "unread_count": unread_count,
            "page": page,
            "per_page": per_page,
            "has_more": len(notifications) == per_page,
        },
    )


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    request: Request,
    db: DBSession,
    user: CurrentUser,
    notification_id: int,
):
    """Mark a notification as read."""
    result = await db.execute(
        select(NotificationLog).where(
            NotificationLog.id == notification_id,
            NotificationLog.user_id == user.id,
        )
    )
    notification = result.scalar_one_or_none()
    
    if notification:
        notification.is_read = True
        await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse("")
    
    return JSONResponse({"status": "ok"})


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    request: Request,
    db: DBSession,
    user: CurrentUser,
):
    """Mark all notifications as read."""
    from sqlalchemy import update
    
    await db.execute(
        update(NotificationLog)
        .where(
            NotificationLog.user_id == user.id,
            NotificationLog.is_read == False,
        )
        .values(is_read=True)
    )
    await db.commit()
    
    if request.headers.get("HX-Request"):
        return HTMLResponse('<span class="text-green-500">All marked as read</span>')
    
    return RedirectResponse(
        url="/integrations/notifications",
        status_code=status.HTTP_302_FOUND,
    )


# ==================== Webhook Endpoints ====================

@router.post("/slack/webhook")
async def slack_webhook(
    request: Request,
    db: DBSession,
):
    """
    Handle Slack Events API webhooks.
    
    Note: This requires a Slack App with Event Subscriptions enabled.
    The app needs to subscribe to message events.
    """
    body = await request.body()
    
    # Verify signature
    signature = request.headers.get("X-Slack-Signature", "")
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    
    if not slack_service.verify_webhook_signature(signature, timestamp, body):
        logger.warning("Invalid Slack webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    data = await request.json()
    
    # Handle URL verification challenge
    if data.get("type") == "url_verification":
        return JSONResponse({"challenge": data.get("challenge")})
    
    # Handle events
    if data.get("type") == "event_callback":
        event_data = slack_service.parse_event(data)
        
        if event_data:
            # Find user with this Slack integration
            result = await db.execute(
                select(ExternalIntegration).where(
                    ExternalIntegration.integration_type == IntegrationType.SLACK,
                    ExternalIntegration.external_team_id == data.get("team_id"),
                    ExternalIntegration.is_active == True,
                )
            )
            integrations = result.scalars().all()
            
            for integration in integrations:
                # Check if this user should receive this notification
                prefs = integration.notification_preferences or {}
                source = event_data.get("source")
                
                should_notify = False
                if source == "slack_dm" and prefs.get("dm"):
                    should_notify = True
                elif source == "slack_channel":
                    # Check for mentions or watched channels
                    if prefs.get("mentions"):
                        # Check if user was mentioned
                        text = event_data.get("text", "")
                        if f"<@{integration.external_user_id}>" in text:
                            source = "slack_mention"
                            should_notify = True
                    
                    # Check watched channels
                    watched = prefs.get("channels", [])
                    if event_data.get("channel_id") in watched:
                        should_notify = True
                
                if should_notify:
                    # Get sender info
                    sender_info = await slack_service.get_user_info(
                        integration.access_token,
                        event_data.get("user_id"),
                    )
                    sender_name = sender_info.get("real_name", "Unknown") if sender_info else "Unknown"
                    
                    # Get channel info
                    channel_info = await slack_service.get_channel_info(
                        integration.access_token,
                        event_data.get("channel_id"),
                    )
                    channel_name = channel_info.get("name") if channel_info else None
                    
                    # Build message URL
                    external_url = slack_service.build_message_url(
                        event_data.get("team_id"),
                        event_data.get("channel_id"),
                        event_data.get("ts"),
                    )
                    
                    # Create notification log
                    notification = NotificationLog.create_from_slack(
                        user_id=integration.user_id,
                        integration_id=integration.id,
                        source=NotificationSource(source),
                        sender_name=sender_name,
                        message_body=event_data.get("text", ""),
                        channel_name=channel_name,
                        external_url=external_url,
                        sender_external_id=event_data.get("user_id"),
                        channel_external_id=event_data.get("channel_id"),
                        external_message_id=event_data.get("ts"),
                    )
                    db.add(notification)
            
            await db.commit()
    
    return JSONResponse({"status": "ok"})


@router.post("/discord/webhook")
async def discord_webhook(
    request: Request,
    db: DBSession,
):
    """
    Handle Discord webhook events.
    
    Note: Discord doesn't have user-level webhooks like Slack.
    This endpoint is for bot-based notifications if a bot is configured.
    For OAuth-only integrations, we use polling instead.
    """
    # Discord uses different verification
    # For Interactions endpoint, verify signature
    signature = request.headers.get("X-Signature-Ed25519")
    timestamp = request.headers.get("X-Signature-Timestamp")
    
    if not signature or not timestamp:
        raise HTTPException(status_code=401, detail="Missing signature")
    
    data = await request.json()
    
    # Handle ping
    if data.get("type") == 1:
        return JSONResponse({"type": 1})
    
    # Process other events...
    # This would require more complex bot setup
    
    return JSONResponse({"status": "ok"})
