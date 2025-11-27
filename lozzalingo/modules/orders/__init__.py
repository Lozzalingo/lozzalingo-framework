"""
Orders Admin Module
===================

Admin interface for order management.
Plugs into the admin dashboard module.

Provides:
- Order listing and search
- Order detail view and editing
- Order status management
- Integration with fulfillment services
"""

from flask import Blueprint

orders_bp = Blueprint(
    'orders_admin',
    __name__,
    url_prefix='/admin/orders-manager',
    template_folder='templates'
)

from . import routes

__all__ = ['orders_bp']
