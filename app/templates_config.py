"""
Shared Jinja2 templates configuration.

All routers should import templates from here to ensure brand context is available.
"""

from fastapi.templating import Jinja2Templates

from app.brand import get_brand

# Create shared templates instance
templates = Jinja2Templates(directory="app/templates")

# Add brand to all template contexts globally
templates.env.globals["brand"] = get_brand()
