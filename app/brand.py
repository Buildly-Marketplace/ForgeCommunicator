"""
White-label branding configuration.

This module provides branding context for templates, allowing each 
customer deployment to have custom logos, colors, and company name.

Supports both static (environment variable) and dynamic (database) configuration.
Dynamic settings override static ones when present.

Example customer deployments:
- comms.buildly.io (default Buildly branding)
- comms.transparentpath.com (Transparent Path branding)
- comms.acme.com (ACME Corp branding)
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.settings import settings


@dataclass
class BrandContext:
    """Branding context passed to all templates."""
    
    # Names
    name: str  # "Communicator" or custom
    company: str  # "Buildly" or customer company name
    full_name: str  # "Buildly Communicator" or "ACME Communicator"
    
    # Assets
    logo_url: str  # Logo image URL
    favicon_url: str  # Favicon URL
    
    # Colors (CSS custom properties)
    primary_color: str  # Main accent (buttons, links)
    secondary_color: str  # Secondary (headers, nav)
    accent_color: str  # Highlights
    
    # Theme
    dark_mode_default: bool  # Whether dark mode is on by default
    
    # Support
    support_email: str
    
    # Computed CSS for inline styles
    @property
    def css_vars(self) -> str:
        """CSS custom properties for dynamic theming."""
        return f"""
            --brand-primary: {self.primary_color};
            --brand-secondary: {self.secondary_color};
            --brand-accent: {self.accent_color};
        """
    
    @property
    def tailwind_config(self) -> dict:
        """Tailwind color config for runtime theme."""
        return {
            "primary": self.primary_color,
            "secondary": self.secondary_color,
            "accent": self.accent_color,
        }


# Dynamic config cache (cleared when config changes)
_dynamic_config_cache: dict[str, Any] = {}


def clear_brand_cache():
    """Clear brand cache to pick up new config values."""
    global _dynamic_config_cache
    _dynamic_config_cache.clear()
    get_brand.cache_clear()


async def get_dynamic_config(db) -> dict[str, Any]:
    """Get dynamic configuration from database.
    
    Returns dict of config key -> value.
    """
    from sqlalchemy import select
    from app.models.site_config import SiteConfig
    
    result = await db.execute(select(SiteConfig))
    configs = result.scalars().all()
    
    return {c.key: c.value for c in configs}


def get_brand_with_overrides(overrides: dict[str, Any] | None = None) -> "BrandContext":
    """Get brand context with optional overrides from database.
    
    Args:
        overrides: Dict of config key -> value from database
    """
    overrides = overrides or {}
    
    # Determine logo URL
    if overrides.get("brand_logo_url"):
        logo_url = overrides["brand_logo_url"]
    elif settings.brand_logo_url:
        logo_url = settings.brand_logo_url
    else:
        logo_url = "/static/forge-logo.png"
    
    # Determine favicon URL
    if overrides.get("brand_favicon_url"):
        favicon_url = overrides["brand_favicon_url"]
    elif settings.brand_favicon_url:
        favicon_url = settings.brand_favicon_url
    else:
        favicon_url = "/static/favicon.svg"
    
    # Get name and company
    name = overrides.get("brand_name") or settings.brand_name
    company = overrides.get("brand_company") or settings.brand_company
    
    # Build full name
    full_name = f"{company} {name}"
    
    # Get colors - default to futuristic dark theme
    primary_color = overrides.get("theme_primary_color") or settings.brand_primary_color
    secondary_color = overrides.get("theme_secondary_color") or settings.brand_secondary_color
    accent_color = overrides.get("theme_accent_color") or settings.brand_accent_color
    
    # Dark mode default
    dark_default = overrides.get("theme_dark_mode_default")
    if dark_default is None:
        dark_mode_default = True  # Default to dark mode to match splash
    else:
        dark_mode_default = dark_default in (True, "true", "True", "1", 1)
    
    return BrandContext(
        name=name,
        company=company,
        full_name=full_name,
        logo_url=logo_url,
        favicon_url=favicon_url,
        primary_color=primary_color,
        secondary_color=secondary_color,
        accent_color=accent_color,
        dark_mode_default=dark_mode_default,
        support_email=overrides.get("brand_support_email") or settings.brand_support_email,
    )


@lru_cache
def get_brand() -> BrandContext:
    """Get the brand context from settings.
    
    Cached for performance - use clear_brand_cache() to pick up changes.
    For dynamic config, use get_brand_with_overrides() with db values.
    """
    return get_brand_with_overrides()


# Convenience instance (static config only)
brand = get_brand()

