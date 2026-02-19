"""
Projects Admin Module
=====================

Admin interface for project portfolio management.
Plugs into the admin dashboard module.

Provides:
- Project creation and editing
- Active/inactive status toggle
- Image upload for projects
- Technologies tagging
"""

from flask import Blueprint

projects_bp = Blueprint(
    'projects_admin',
    __name__,
    url_prefix='/admin/projects-editor',
    template_folder='templates',
    static_folder='static',
    static_url_path='/projects/static'
)

from . import routes

__all__ = ['projects_bp']
