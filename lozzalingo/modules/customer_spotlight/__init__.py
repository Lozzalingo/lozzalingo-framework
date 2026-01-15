"""
Customer Spotlight Module
=========================

Displays customer photos/submissions in a gallery-style spotlight section.
Includes admin management for adding/editing spotlight entries.
"""

from flask import Blueprint

customer_spotlight_bp = Blueprint(
    'customer_spotlight',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/customer-spotlight/static'
)

from . import routes
