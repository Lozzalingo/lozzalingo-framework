"""
Dashboard Module
================

Admin dashboard interface for Lozzalingo.

Provides core admin functionality:
- Admin authentication (login/logout)
- Admin dashboard with statistics
- Password management
- Admin user creation

This is the foundation module that other admin features plug into.
"""

from flask import Blueprint

# Create admin dashboard blueprint
# Note: Blueprint name is 'admin' to avoid conflicts with site-specific user dashboards
dashboard_bp = Blueprint(
    'admin',
    __name__,
    url_prefix='/admin',
    template_folder='templates',
    static_folder='static',
    static_url_path='/static'  # Will be /admin/static due to url_prefix
)

# Import routes after blueprint is created
from . import routes

__all__ = ['dashboard_bp']
