"""
Orders Module
=============

Admin interface for order management + public recent-sales API.
Plugs into the admin dashboard module.

Provides:
- Order listing and search
- Order detail view and editing
- Order status management
- Integration with fulfillment services
- Public /api/recent-sales endpoint (API key protected, for live ticker feeds)
"""

from flask import Blueprint

orders_bp = Blueprint(
    'orders_admin',
    __name__,
    url_prefix='/admin/orders-manager',
    template_folder='templates'
)

orders_public_bp = Blueprint(
    'orders_public',
    __name__,
    url_prefix='/api'
)

from . import routes

__all__ = ['orders_bp', 'orders_public_bp']
