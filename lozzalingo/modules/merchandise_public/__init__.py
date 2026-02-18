"""
Merchandise Public API Module
==============================

Public, read-only API for product data.
Designed for cross-site embedding (e.g. product ads in blog posts).

Provides:
- /api/products/embed — CORS-enabled JSON endpoint for product cards
"""

from flask import Blueprint

merchandise_public_bp = Blueprint(
    'merchandise_public',
    __name__,
    url_prefix='/api/products',
    static_folder='static',
    static_url_path='/merchandise-public-static'
)

from . import routes

__all__ = ['merchandise_public_bp']
