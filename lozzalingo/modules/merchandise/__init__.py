"""
Merchandise Admin Module
========================

Admin interface for product/merchandise management.
Plugs into the admin dashboard module.

Provides:
- Product creation and editing
- Pricing management
- Inventory tracking
- Product image management
"""

from flask import Blueprint

merchandise_bp = Blueprint(
    'merchandise_admin',
    __name__,
    url_prefix='/admin/merchandise-editor',
    template_folder='templates'
)

from . import routes

__all__ = ['merchandise_bp']
