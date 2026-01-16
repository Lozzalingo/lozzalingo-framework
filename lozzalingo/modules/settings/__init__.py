"""
Settings Module
===============

Provides admin UI for managing site settings and API keys.
Settings are encrypted at rest for security.
"""

from flask import Blueprint
import os

_template_dir = os.path.join(os.path.dirname(__file__), 'templates')

settings_bp = Blueprint('settings', __name__,
                        url_prefix='/admin/settings',
                        template_folder=_template_dir)

from . import routes
