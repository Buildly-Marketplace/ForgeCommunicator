"""
Buildly CollabHub API sync service.

Syncs community profiles, team memberships, and public profile data
between Forge Communicator and CollabHub. Uses Labs as the shared
identity provider.

CollabHub API follows Django REST Framework patterns:
- /users/ - User profiles
- /teams/ - Team management
- /organizations/ - Organization data
- /community/ - Community stats and roles
"""

from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel import Channel
from app.models.membership import Membership, MembershipRole
from app.models.user import AuthProvider, User
from app.models.workspace import Workspace
from app.settings import settings

# Community workspace constants
COMMUNITY_WORKSPACE_SLUG = "community"
COMMUNITY_WORKSPACE_NAME = "Buildly Community"
COMMUNITY_WORKSPACE_DESCRIPTION = "Welcome to the Buildly Community! Connect with developers, share ideas, and collaborate on projects."


class CollabHubSyncError(Exception):
    """Exception raised for CollabHub API errors."""
    pass


class CollabHubSyncService:
    """Service for syncing data with Buildly CollabHub API."""
    
    BASE_URL = settings.collabhub_api_url
    
    def __init__(self, access_token: str | None = None, api_key: str | None = None):
        """
        Initialize with either an OAuth access token (from Labs) or API key.
        
        Labs OAuth tokens work for both Labs and CollabHub since they share
        identity infrastructure.
        """
        self.token = access_token or api_key or settings.collabhub_api_key
        if not self.token:
            raise ValueError("CollabHub API key or Labs access token is required")
        
        # Determine auth header style based on token type
        if api_key or (not access_token and settings.collabhub_api_key):
            # API key uses Token auth (DRF default)
            self.headers = {
                "Authorization": f"Token {self.token}",
                "Content-Type": "application/json",
            }
        else:
            # OAuth access token uses Bearer auth
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json: dict | None = None,
    ) -> dict:
        """Make an authenticated request to the CollabHub API."""
        url = f"{self.BASE_URL}{endpoint}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    params=params,
                    json=json,
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise CollabHubSyncError(
                    f"CollabHub API error {e.response.status_code}: {e.response.text}"
                )
            except httpx.RequestError as e:
                raise CollabHubSyncError(f"CollabHub API request failed: {e}")
    
    # -------------------------------------------------------------------------
    # User Profile APIs (DRF-style)
    # -------------------------------------------------------------------------
    
    async def get_me(self) -> dict:
        """
        Get current user's CollabHub profile.
        
        Returns DRF-style response:
        {
            "uuid": "...",
            "email": "user@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "bio": "...",
            "title": "Developer",
            "avatar_url": "...",
            "github_url": "...",
            "linkedin_url": "...",
            "twitter_url": "...",
            "website_url": "...",
            "organization": {...},
            "roles": {"community": "member", "dev_team": true, "customer": false},
            "stats": {"reputation": 100, "projects": 5, "contributions": 42}
        }
        """
        return await self._request("GET", "/users/me/")
    
    async def get_user(self, user_uuid: str) -> dict:
        """Get a specific user's public profile."""
        return await self._request("GET", f"/users/{user_uuid}/")
    
    async def update_user(self, user_uuid: str, data: dict) -> dict:
        """Update user profile."""
        return await self._request("PATCH", f"/users/{user_uuid}/", json=data)
    
    async def search_users(
        self,
        query: str | None = None,
        organization_uuid: str | None = None,
        is_dev_team: bool | None = None,
        is_customer: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """
        Search for users in CollabHub.
        
        Returns paginated DRF response:
        {"count": N, "next": "...", "previous": "...", "results": [...]}
        """
        params = {"limit": limit, "offset": offset}
        if query:
            params["search"] = query
        if organization_uuid:
            params["organization"] = organization_uuid
        if is_dev_team is not None:
            params["is_dev_team"] = str(is_dev_team).lower()
        if is_customer is not None:
            params["is_customer"] = str(is_customer).lower()
        
        return await self._request("GET", "/users/", params=params)
    
    # -------------------------------------------------------------------------
    # Organization APIs
    # -------------------------------------------------------------------------
    
    async def get_organization(self, org_uuid: str | None = None) -> dict:
        """Get organization details. If no UUID provided, gets user's org."""
        if org_uuid:
            return await self._request("GET", f"/organizations/{org_uuid}/")
        return await self._request("GET", "/organizations/me/")
    
    async def get_organization_members(
        self,
        org_uuid: str,
        role: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """Get members of an organization."""
        params = {"limit": limit, "offset": offset}
        if role:
            params["role"] = role
        return await self._request("GET", f"/organizations/{org_uuid}/members/", params=params)
    
    # -------------------------------------------------------------------------
    # Team APIs
    # -------------------------------------------------------------------------
    
    async def get_teams(
        self,
        organization_uuid: str | None = None,
        team_type: str | None = None,  # "dev_team", "customer", etc.
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """Get teams from CollabHub."""
        params = {"limit": limit, "offset": offset}
        if organization_uuid:
            params["organization"] = organization_uuid
        if team_type:
            params["type"] = team_type
        return await self._request("GET", "/teams/", params=params)
    
    async def get_team(self, team_uuid: str) -> dict:
        """Get a specific team's details."""
        return await self._request("GET", f"/teams/{team_uuid}/")
    
    async def get_team_members(
        self,
        team_uuid: str,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """Get members of a team."""
        params = {"limit": limit, "offset": offset}
        return await self._request("GET", f"/teams/{team_uuid}/members/", params=params)
    
    # -------------------------------------------------------------------------
    # Community APIs
    # -------------------------------------------------------------------------
    
    async def get_community_stats(self, user_uuid: str | None = None) -> dict:
        """
        Get community stats for a user.
        
        Returns:
        {
            "reputation": 100,
            "projects_count": 5,
            "contributions_count": 42,
            "badges": ["contributor", "early_adopter"],
            "rank": "Gold"
        }
        """
        if user_uuid:
            return await self._request("GET", f"/community/stats/{user_uuid}/")
        return await self._request("GET", "/community/stats/me/")
    
    async def get_community_activity(
        self,
        user_uuid: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        """Get community activity feed for a user."""
        params = {"limit": limit, "offset": offset}
        if user_uuid:
            return await self._request("GET", f"/community/activity/{user_uuid}/", params=params)
        return await self._request("GET", "/community/activity/me/", params=params)
    
    # -------------------------------------------------------------------------
    # Entitlements APIs (marketplace)
    # -------------------------------------------------------------------------
    
    async def get_entitlements(self, user_uuid: str | None = None) -> dict:
        """Get user's app entitlements (purchased/licensed apps)."""
        if user_uuid:
            return await self._request("GET", f"/marketplace/api/entitlements/", params={"user": user_uuid})
        return await self._request("GET", "/marketplace/api/entitlements/")
    
    # -------------------------------------------------------------------------
    # Sync Methods
    # -------------------------------------------------------------------------
    
    async def sync_user_profile(
        self,
        db: AsyncSession,
        user: User,
    ) -> dict[str, Any]:
        """
        Sync a user's profile from CollabHub.
        
        Pulls profile data, social links, community stats, and role memberships
        from CollabHub and updates the local user record.
        
        Returns dict with sync results.
        """
        stats = {"synced": False, "fields_updated": [], "error": None}
        
        try:
            # Get user profile from CollabHub
            profile = await self.get_me()
            
            # Extract data
            user_uuid = profile.get("uuid") or profile.get("id")
            org = profile.get("organization", {})
            roles = profile.get("roles", {})
            community_stats = profile.get("stats", {})
            
            # Update user record
            user.update_from_collabhub(
                user_uuid=str(user_uuid) if user_uuid else None,
                org_uuid=org.get("uuid") if org else None,
                github_url=profile.get("github_url"),
                linkedin_url=profile.get("linkedin_url"),
                twitter_url=profile.get("twitter_url"),
                website_url=profile.get("website_url"),
                reputation=community_stats.get("reputation"),
                projects=community_stats.get("projects_count") or community_stats.get("projects"),
                contributions=community_stats.get("contributions_count") or community_stats.get("contributions"),
                roles=roles,
            )
            
            # Also sync display info if provided
            if profile.get("first_name") or profile.get("last_name"):
                full_name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()
                if full_name and not user.display_name:
                    user.display_name = full_name
                    stats["fields_updated"].append("display_name")
            
            if profile.get("bio") and not user.bio:
                user.bio = profile["bio"]
                stats["fields_updated"].append("bio")
            
            if profile.get("title") and not user.title:
                user.title = profile["title"]
                stats["fields_updated"].append("title")
            
            if profile.get("avatar_url") and not user.avatar_url:
                user.avatar_url = profile["avatar_url"]
                stats["fields_updated"].append("avatar_url")
            
            await db.commit()
            stats["synced"] = True
            stats["fields_updated"].extend([
                "collabhub_user_uuid", "collabhub_org_uuid", "collabhub_synced_at",
                "github_url", "linkedin_url", "twitter_url", "website_url",
                "community_reputation", "projects_count", "contributions_count",
                "collabhub_roles"
            ])
            
            print(f"[CollabHub Sync] Synced profile for user {user.email}")
            
            # Auto-join community workspace if user is a community member
            if roles.get("community") or user.collabhub_user_uuid:
                community_result = await ensure_community_membership(db, user)
                if community_result["joined"]:
                    stats["fields_updated"].append("community_workspace_joined")
                    print(f"[CollabHub Sync] Added {user.email} to Community workspace")
            
        except CollabHubSyncError as e:
            stats["error"] = str(e)
            print(f"[CollabHub Sync] Error syncing profile for {user.email}: {e}")
        
        return stats
    
    async def push_user_profile(
        self,
        user: User,
    ) -> dict[str, Any]:
        """
        Push a user's profile to CollabHub.
        
        Sends profile data from ForgeCommunicator to CollabHub for sync.
        Only updates fields that have values locally.
        
        Returns dict with push results.
        """
        stats = {"pushed": False, "fields_pushed": [], "error": None}
        
        if not user.collabhub_user_uuid:
            stats["error"] = "User not linked to CollabHub"
            return stats
        
        try:
            # Build update payload (only non-null fields)
            data = {}
            if user.display_name:
                # Split display name into first/last for DRF
                parts = user.display_name.split(" ", 1)
                data["first_name"] = parts[0]
                if len(parts) > 1:
                    data["last_name"] = parts[1]
            if user.bio:
                data["bio"] = user.bio
            if user.title:
                data["title"] = user.title
            if user.phone:
                data["phone"] = user.phone
            if user.avatar_url:
                data["avatar_url"] = user.avatar_url
            if user.github_url:
                data["github_url"] = user.github_url
            if user.linkedin_url:
                data["linkedin_url"] = user.linkedin_url
            if user.twitter_url:
                data["twitter_url"] = user.twitter_url
            if user.website_url:
                data["website_url"] = user.website_url
            
            if data:
                await self.update_user(user.collabhub_user_uuid, data)
                stats["pushed"] = True
                stats["fields_pushed"] = list(data.keys())
                print(f"[CollabHub Sync] Pushed profile for user {user.email}: {list(data.keys())}")
            else:
                stats["error"] = "No fields to push"
                
        except CollabHubSyncError as e:
            stats["error"] = str(e)
            print(f"[CollabHub Sync] Error pushing profile for {user.email}: {e}")
        
        return stats
    
    async def sync_team_members(
        self,
        db: AsyncSession,
        workspace_id: int,
        team_uuid: str,
    ) -> dict[str, int]:
        """
        Sync team members from a CollabHub team.
        
        Creates user records for team members who don't exist locally
        and updates existing users' CollabHub data.
        
        Returns counts: {"created": N, "updated": N, "skipped": N}
        """
        stats = {"created": 0, "updated": 0, "skipped": 0}
        
        try:
            response = await self.get_team_members(team_uuid)
            members = response.get("results", [])
            
            for member in members:
                email = member.get("email")
                if not email:
                    stats["skipped"] += 1
                    continue
                
                # Check if user exists
                result = await db.execute(
                    select(User).where(User.email == email.lower())
                )
                user = result.scalar_one_or_none()
                
                if user:
                    # Update existing user's CollabHub data
                    user.update_from_collabhub(
                        user_uuid=str(member.get("uuid") or member.get("id")),
                        roles=member.get("roles", {}),
                    )
                    stats["updated"] += 1
                else:
                    # Create new user from CollabHub data
                    full_name = f"{member.get('first_name', '')} {member.get('last_name', '')}".strip()
                    new_user = User(
                        email=email.lower(),
                        display_name=full_name or email.split("@")[0],
                        auth_provider="buildly",  # Will use Labs OAuth
                        collabhub_user_uuid=str(member.get("uuid") or member.get("id")),
                        collabhub_roles=member.get("roles", {}),
                        github_url=member.get("github_url"),
                        linkedin_url=member.get("linkedin_url"),
                        avatar_url=member.get("avatar_url"),
                    )
                    db.add(new_user)
                    stats["created"] += 1
            
            await db.commit()
            print(f"[CollabHub Sync] Synced {len(members)} team members from team {team_uuid}")
            
        except CollabHubSyncError as e:
            print(f"[CollabHub Sync] Error syncing team {team_uuid}: {e}")
            raise
        
        return stats


# -------------------------------------------------------------------------
# Community Workspace Helper Functions
# -------------------------------------------------------------------------

async def get_or_create_community_workspace(db: AsyncSession) -> tuple[Workspace, bool]:
    """
    Get or create the Community workspace.
    
    Returns:
        Tuple of (workspace, created) where created is True if newly created.
    """
    # Try to find existing community workspace
    result = await db.execute(
        select(Workspace).where(Workspace.slug == COMMUNITY_WORKSPACE_SLUG)
    )
    workspace = result.scalar_one_or_none()
    
    if workspace:
        return workspace, False
    
    # Create the community workspace
    workspace = Workspace(
        name=COMMUNITY_WORKSPACE_NAME,
        slug=COMMUNITY_WORKSPACE_SLUG,
        description=COMMUNITY_WORKSPACE_DESCRIPTION,
    )
    db.add(workspace)
    await db.flush()  # Get the workspace ID
    
    # Create default channels for the community
    default_channels = [
        ("welcome", "Welcome to Buildly Community", "Welcome new members and introductions", True),
        ("general", "General discussion", "General chat for community members", True),
        ("help", "Help & Support", "Get help from the community", False),
        ("showcase", "Project Showcase", "Share your projects and get feedback", False),
        ("announcements", "Announcements", "Official announcements from Buildly", False),
    ]
    
    for name, topic, description, is_default in default_channels:
        channel = Channel(
            workspace_id=workspace.id,
            name=name,
            topic=topic,
            description=description,
            is_default=is_default,
        )
        db.add(channel)
    
    await db.commit()
    print(f"[CollabHub Sync] Created Community workspace with default channels")
    
    return workspace, True


async def ensure_community_membership(
    db: AsyncSession,
    user: User,
) -> dict[str, Any]:
    """
    Ensure a user is a member of the Community workspace.
    
    Creates the workspace if it doesn't exist, then adds the user as a member
    if they aren't already.
    
    Returns:
        Dict with {"joined": bool, "workspace_id": int, "created_workspace": bool}
        Returns {"skipped": True} if CollabHub plugin is disabled.
    """
    # Check if CollabHub Community workspace feature is enabled
    if not settings.collabhub_enabled or not settings.collabhub_community_workspace_enabled:
        return {"skipped": True, "reason": "CollabHub Community workspace feature is disabled"}
    
    result = {
        "joined": False,
        "workspace_id": None,
        "workspace_created": False,
        "already_member": False,
    }
    
    # Get or create the community workspace
    workspace, created = await get_or_create_community_workspace(db)
    result["workspace_id"] = workspace.id
    result["workspace_created"] = created
    
    # Check if user is already a member
    membership_result = await db.execute(
        select(Membership).where(
            Membership.workspace_id == workspace.id,
            Membership.user_id == user.id,
        )
    )
    existing_membership = membership_result.scalar_one_or_none()
    
    if existing_membership:
        result["already_member"] = True
        return result
    
    # Add user as a member
    membership = Membership(
        workspace_id=workspace.id,
        user_id=user.id,
        role=MembershipRole.MEMBER,
    )
    db.add(membership)
    await db.commit()
    
    result["joined"] = True
    print(f"[CollabHub Sync] User {user.email} joined Community workspace")
    
    return result


async def sync_collabhub_users_to_community(
    db: AsyncSession,
) -> dict[str, int]:
    """
    Sync all CollabHub users to the Community workspace.
    
    Finds all users with collabhub_user_uuid set and ensures they're members
    of the Community workspace.
    
    Returns:
        Dict with counts: {"added": N, "already_members": N, "total_users": N}
        Returns {"skipped": True} if CollabHub plugin is disabled.
    """
    # Check if CollabHub Community workspace feature is enabled
    if not settings.collabhub_enabled or not settings.collabhub_community_workspace_enabled:
        return {"skipped": True, "reason": "CollabHub Community workspace feature is disabled"}
    
    stats = {"added": 0, "already_members": 0, "total_users": 0}
    
    # Get all CollabHub users
    result = await db.execute(
        select(User).where(
            User.collabhub_user_uuid.isnot(None),
            User.is_active == True,
        )
    )
    users = result.scalars().all()
    stats["total_users"] = len(users)
    
    for user in users:
        membership_result = await ensure_community_membership(db, user)
        if membership_result["joined"]:
            stats["added"] += 1
        elif membership_result["already_member"]:
            stats["already_members"] += 1
    
    print(f"[CollabHub Sync] Community sync complete: {stats}")
    return stats
