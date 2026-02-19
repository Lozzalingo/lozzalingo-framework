"""
Quick Links Module
==================

Admin interface and public page for quick links (linktree-style).
Two blueprints: admin editor and public page.
"""

from flask import Blueprint

# Admin interface for managing links
quick_links_admin_bp = Blueprint(
    'quick_links_admin',
    __name__,
    url_prefix='/admin/quick-links-editor',
    template_folder='templates'
)

# Public quick links page
quick_links_bp = Blueprint(
    'quick_links',
    __name__,
    url_prefix='/quick-links',
    template_folder='templates'
)

from . import routes

__all__ = ['quick_links_admin_bp', 'quick_links_bp']
