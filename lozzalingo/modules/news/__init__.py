"""
News Admin Module
=================

Admin interface for news/blog article management.
Plugs into the admin dashboard module.

Provides:
- Article creation and editing
- Draft/publish workflow
- Image upload for articles
- Email notifications to subscribers
"""

from flask import Blueprint

news_bp = Blueprint(
    'news_admin',
    __name__,
    url_prefix='/admin/news-editor',
    template_folder='templates',
    static_folder='static',
    static_url_path='/news/static'
)

from . import routes

__all__ = ['news_bp']
