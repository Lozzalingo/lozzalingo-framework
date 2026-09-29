"""
Product Embed routes.

GET /api/product-embed/<site_id>
    Proxies to the centralised E-commerce Service embed endpoint and
    returns the product list as JSON.  Apps can call this locally
    instead of reaching out to the E-commerce Service directly,
    keeping the service URL private.
"""

from __future__ import annotations

import logging

import requests
from flask import Blueprint, current_app, jsonify, request

logger = logging.getLogger(__name__)

product_embed_bp = Blueprint(
    'product_embed',
    __name__,
    template_folder='templates',
)


@product_embed_bp.route('/api/product-embed/<site_id>')
def get_embedded_products(site_id: str):
    """Proxy product data from the E-commerce Service.

    Query parameters are forwarded as-is (e.g. ``?limit=6``).
    """
    ecommerce_url = current_app.config.get('ECOMMERCE_SERVICE_URL')
    if not ecommerce_url:
        return jsonify({'error': 'E-commerce Service URL not configured'}), 503

    try:
        resp = requests.get(
            f'{ecommerce_url}/api/embed/{site_id}',
            params=request.args,
            timeout=10,
        )
        resp.raise_for_status()
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as exc:
        logger.error('Failed to fetch products from E-commerce Service: %s', exc)
        try:
            from lozzalingo.core import db_log
            db_log('error', 'product_embed', f'E-commerce Service request failed: {exc}')
        except Exception:
            pass
        return jsonify({'error': 'Unable to fetch products at this time'}), 502
