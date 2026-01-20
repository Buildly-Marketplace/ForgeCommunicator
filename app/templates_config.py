"""
Shared Jinja2 templates configuration.

All routers should import templates from here to ensure brand context is available.
"""

import re
from markupsafe import Markup
from fastapi.templating import Jinja2Templates
import markdown

from app.brand import get_brand


def markdown_filter(text: str) -> Markup:
    """Convert markdown text to HTML, safe for display."""
    if not text:
        return Markup("")
    
    # Convert markdown to HTML
    # Use safe extensions only
    html = markdown.markdown(
        text,
        extensions=['nl2br', 'fenced_code', 'tables'],
        output_format='html'
    )
    
    return Markup(html)


def simple_markdown_filter(text: str) -> Markup:
    """
    Simple markdown conversion for inline formatting only.
    Handles: **bold**, *italic*, `code`, ~~strikethrough~~
    """
    if not text:
        return Markup("")
    
    import html
    # Escape HTML first
    text = html.escape(text)
    
    # Convert markdown patterns
    # Bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
    
    # Italic: *text* or _text_ (but not inside words)
    text = re.sub(r'(?<!\w)\*([^*]+?)\*(?!\w)', r'<em>\1</em>', text)
    text = re.sub(r'(?<!\w)_([^_]+?)_(?!\w)', r'<em>\1</em>', text)
    
    # Inline code: `code`
    text = re.sub(r'`([^`]+?)`', r'<code class="bg-gray-100 dark:bg-gray-700 px-1 py-0.5 rounded text-sm font-mono">\1</code>', text)
    
    # Strikethrough: ~~text~~
    text = re.sub(r'~~(.+?)~~', r'<del>\1</del>', text)
    
    # Links: [text](url)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" class="text-indigo-600 hover:underline" target="_blank" rel="noopener">\1</a>', text)
    
    # Preserve newlines
    text = text.replace('\n', '<br>')
    
    return Markup(text)


# Create shared templates instance
templates = Jinja2Templates(directory="app/templates")

# Add brand to all template contexts globally
templates.env.globals["brand"] = get_brand()

# Add markdown filters
templates.env.filters["markdown"] = markdown_filter
templates.env.filters["md"] = simple_markdown_filter
