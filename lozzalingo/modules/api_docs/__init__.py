"""
API Docs Module
===============

Auto-generates interactive API documentation from an OpenAPI (Swagger) YAML
spec file. Reads ``openapi.yaml`` from the host app root and renders a
themed docs page at ``/api/docs``.

Activate via config:
    features:
      api_docs: true
"""

import os
from flask import Blueprint

_template_dir = os.path.join(os.path.dirname(__file__), 'templates')
_static_dir = os.path.join(os.path.dirname(__file__), 'static')

api_docs_bp = Blueprint(
    'api_docs',
    __name__,
    url_prefix='/api/docs',
    template_folder=_template_dir,
    static_folder=_static_dir,
    static_url_path='/static',
)

from . import routes  # noqa: E402, F401
