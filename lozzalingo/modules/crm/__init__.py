"""
CRM Module
==========

Provides customer relationship management for Lozzalingo Python sites.
Mirrors the JavaScript CRM module (@lozzalingo/crm) so that all sites
across both frameworks share an identical CRM data structure.

Features:
- Customer management with scoring, activities, campaigns, and marketing preferences
- Admin API routes behind auth middleware
- Config-driven scoring weights and customer number prefixes
- Dashboard stats endpoint

Schema definition: docs/crm-schema.md (shared with JS framework)
"""

from flask import Blueprint

crm_bp = Blueprint(
    'crm',
    __name__,
    url_prefix='/api/crm',
)

from . import routes
