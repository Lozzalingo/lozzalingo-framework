"""
External API Module
===================

Provides API key authenticated endpoints for external services
to interact with your application (e.g., publishing blog posts from external CMS).

Features:
- API key generation and management
- Token-based authentication for external requests
- Blog post creation via external API
- Admin interface for managing API keys

Usage:
    from lozzalingo.modules.external_api import external_api_bp, external_api_admin_bp

    # Public API endpoint (API key auth)
    app.register_blueprint(external_api_bp)  # Registers at /api/external

    # Admin interface for managing API keys
    app.register_blueprint(external_api_admin_bp)  # Registers at /admin/api-keys
"""

from flask import Blueprint

# Public external API (API key authenticated)
external_api_bp = Blueprint(
    'external_api',
    __name__,
    url_prefix='/api/external',
    template_folder='templates'
)

# Admin interface for API key management
external_api_admin_bp = Blueprint(
    'external_api_admin',
    __name__,
    url_prefix='/admin/api-keys',
    template_folder='templates'
)

from . import routes
