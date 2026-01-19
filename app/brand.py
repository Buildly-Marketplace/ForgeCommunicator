"""
White-label branding configuration.

This module provides branding context for templates, allowing each 
customer deployment to have custom logos, colors, and company name.

Example customer deployments:
- comms.buildly.io (default Buildly branding)
- comms.transparentpath.com (Transparent Path branding)
- comms.acme.com (ACME Corp branding)
"""

from dataclasses import dataclass
from functools import lru_cache

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


@lru_cache
def get_brand() -> BrandContext:
    """Get the brand context from settings.
    
    Cached for performance - restart app to pick up changes.
    """
    # Determine logo URL
    if settings.brand_logo_url:
        logo_url = settings.brand_logo_url
    else:
        logo_url = "/static/forge-logo.png"
    
    # Determine favicon URL
    if settings.brand_favicon_url:
        favicon_url = settings.brand_favicon_url
    else:
        favicon_url = "/static/favicon.svg"
    
    # Build full name
    full_name = f"{settings.brand_company} {settings.brand_name}"
    
    return BrandContext(
        name=settings.brand_name,
        company=settings.brand_company,
        full_name=full_name,
        logo_url=logo_url,
        favicon_url=favicon_url,
        primary_color=settings.brand_primary_color,
        secondary_color=settings.brand_secondary_color,
        accent_color=settings.brand_accent_color,
        support_email=settings.brand_support_email,
    )


# Convenience instance
brand = get_brand()
