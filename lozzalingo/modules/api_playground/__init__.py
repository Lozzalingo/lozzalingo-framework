"""
API Playground Module
=====================

Interactive API testing tool. Reads the host app's ``openapi.yaml`` and
provides a form-driven request builder, live response viewer, and code
generation (curl, Python, JavaScript).

Activate via config:
    features:
      api_playground: true
"""

import os
from flask import Blueprint

_template_dir = os.path.join(os.path.dirname(__file__), 'templates')
_static_dir = os.path.join(os.path.dirname(__file__), 'static')

api_playground_bp = Blueprint(
    'api_playground',
    __name__,
    url_prefix='/api/playground',
    template_folder=_template_dir,
    static_folder=_static_dir,
    static_url_path='/static',
)

from . import routes  # noqa: E402, F401
