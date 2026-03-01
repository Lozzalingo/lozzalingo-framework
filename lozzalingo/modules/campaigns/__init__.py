"""
Campaigns Module
================

Provides:
- Block-based email campaign editor with live preview
- Manual blast sending to all active subscribers
- Auto-triggered campaigns (e.g. new_subscriber)
- Variable substitution per recipient (e.g. {{CODE}}, {{EMAIL}})
"""

from flask import Blueprint

campaigns_bp = Blueprint(
    'campaigns',
    __name__,
    url_prefix='/admin/campaigns',
    template_folder='templates',
    static_folder='static',
    static_url_path='/campaigns/static'
)

from . import routes
