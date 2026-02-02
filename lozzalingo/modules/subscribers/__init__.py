"""
Subscribers Module
==================

Provides:
- Public API for newsletter subscriptions (with optional feed/category support)
- Unsubscribe page and API
- Subscriber stats and export
- Helper functions for other modules (get_all_subscriber_emails, get_subscriber_count)
"""

from flask import Blueprint

subscribers_bp = Blueprint(
    'subscribers',
    __name__,
    url_prefix='/api/subscribers',
    template_folder='templates',
    static_folder='static',
    static_url_path='/subscribers/static'
)

from . import routes
