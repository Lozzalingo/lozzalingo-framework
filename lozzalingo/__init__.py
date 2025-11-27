"""
Lozzalingo - A Flask Admin Framework
====================================

A modular, reusable Flask admin dashboard framework with:
- Analytics tracking and visualization
- User authentication and session management
- Dashboard components
- And more modules to come

Usage:
    from lozzalingo.modules.analytics import analytics_bp
    from lozzalingo.modules.auth import auth_bp

    app.register_blueprint(analytics_bp, url_prefix='/admin/analytics')
    app.register_blueprint(auth_bp, url_prefix='/admin')
"""

__version__ = '0.1.0'
__author__ = 'Laurence Stephan'

# Make common imports available at package level
from .modules import analytics, auth, dashboard

__all__ = ['analytics', 'auth', 'dashboard']
