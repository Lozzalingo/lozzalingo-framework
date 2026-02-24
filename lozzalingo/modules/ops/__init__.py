"""
Ops Module
==========

Server health monitoring, alerting, and admin dashboard for infrastructure visibility.

Features:
- Public /health endpoint for uptime monitors (no auth)
- Admin dashboard with disk, memory, swap, uptime, load, and error feed
- Email alerts with rate-limiting when thresholds are crossed
- Docker cleanup from admin UI

Usage:
    from lozzalingo.modules.ops import ops_health_bp, ops_admin_bp

    # Public health check (no auth)
    app.register_blueprint(ops_health_bp)  # Registers at /health

    # Admin ops dashboard (session auth)
    app.register_blueprint(ops_admin_bp)   # Registers at /admin/ops
"""

from flask import Blueprint

# Public health endpoint (no auth, for uptime monitors)
ops_health_bp = Blueprint(
    'ops_health',
    __name__,
    url_prefix='/health'
)

# Admin ops dashboard (session auth)
ops_admin_bp = Blueprint(
    'ops_admin',
    __name__,
    url_prefix='/admin/ops',
    template_folder='templates'
)

from . import routes
