"""
Public products API for cross-site embedding.

GET /api/products/embed?limit=3&shop=Crowd+Sauced

Calls the centralised E-commerce Service (port 7224) for product data.
Returns a lightweight JSON array of active products with CORS headers,
suitable for embedding product ads in external sites (e.g. AI Blog Builder).
"""

import os
import json
import logging
from flask import jsonify, request, current_app
from flask_cors import cross_origin
from . import merchandise_public_bp

from lozzalingo.core import db_log

logger = logging.getLogger(__name__)

# Allowed origins for CORS
ALLOWED_ORIGINS = [
    'https://laurence.computer',
    'https://aiblogbuilder.laurence.computer',
    'https://promptnews.laurence.computer',
    'https://crowdsauced.laurence.computer',
    'https://coffeegoblin.co.uk',
    'https://www.mariopintomma.com',
    'https://fatbigquiz.com',
    'http://localhost:3000',
    'http://localhost:5001',
]


def _get_ecommerce_client():
    """Get an EcommerceClient instance."""
    from lozzalingo.clients.ecommerce_client import EcommerceClient
    return EcommerceClient()


def _get_site_id():
    """Get the current site's identifier for e-commerce service calls."""
    try:
        site_id = current_app.config.get('ECOMMERCE_SITE_ID')
        if site_id:
            return site_id
    except RuntimeError:
        pass
    return os.getenv('ECOMMERCE_SITE_ID', os.getenv('EMAIL_SITE_ID', ''))


def _get_base_url():
    """Get the site's public base URL for building product links."""
    try:
        url = current_app.config.get('EMAIL_WEBSITE_URL')
        if url:
            return url.rstrip('/')
    except RuntimeError:
        pass

    url = os.getenv('SITE_URL') or os.getenv('PRODUCTION_BASE_URL')
    if url:
        return url.rstrip('/')

    try:
        return request.host_url.rstrip('/')
    except RuntimeError:
        return ''


@merchandise_public_bp.route('/embed', methods=['GET', 'OPTIONS'])
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=False)
def products_embed():
    """
    Public products endpoint for cross-site embedding.

    Query params:
        limit: Max products to return (default 6, max 20)
        shop: Filter by shop name (e.g. "Crowd Sauced")

    Returns JSON:
        { "success": true, "products": [...], "count": N }
    """
    print(f'[MerchandisePublic] GET /embed')
    limit = min(request.args.get('limit', 6, type=int), 20)
    shop_filter = request.args.get('shop')

    try:
        client = _get_ecommerce_client()
        site_id = _get_site_id()
        result = client.list_products(site_id=site_id)

        if result is None:
            return jsonify({'success': False, 'error': 'Service unavailable', 'products': []}), 200

        products_list = result if isinstance(result, list) else result.get('products', result)
        if not isinstance(products_list, list):
            products_list = []

        # Filter active products
        active_products = [p for p in products_list if p.get('is_active', True)]

        # Apply shop filter if provided
        if shop_filter:
            active_products = [p for p in active_products if p.get('shop_name') == shop_filter]

        # Randomise and limit
        import random
        if len(active_products) > limit:
            active_products = random.sample(active_products, limit)

        base_url = _get_base_url()
        shop_path = current_app.config.get('SHOP_URL_PATH', '/merchandise')
        shop_base = shop_path.split('#')[0] if '#' in shop_path else shop_path

        products = []
        for p in active_products:
            # Parse image URLs
            image_urls = p.get('image_urls', [])
            if isinstance(image_urls, str):
                try:
                    image_urls = json.loads(image_urls)
                except (json.JSONDecodeError, TypeError):
                    image_urls = []

            # Get first valid image URL
            image_url = ''
            for img in (image_urls or []):
                if img and str(img).strip():
                    image_url = str(img).strip()
                    if not image_url.startswith(('http://', 'https://')):
                        if image_url.startswith('/static/'):
                            image_url = f"{base_url}{image_url}"
                        else:
                            image_url = f"{base_url}/static/{image_url}"
                    break

            # Truncate description
            desc = p.get('description', '') or ''
            if len(desc) > 100:
                desc = desc[:97] + '...'

            # Format price
            price = p.get('base_price_pence', 0) or p.get('price', 0) or 0
            price_display = f"\u00a3{price / 100:.2f}"

            # Build product URL
            product_url = f"{base_url}{shop_base}?product={p.get('id')}"

            products.append({
                'id': p.get('id'),
                'name': p.get('name', ''),
                'description': desc,
                'price_display': price_display,
                'price_pence': price,
                'image_url': image_url,
                'product_url': product_url,
                'limited_edition': bool(p.get('limited_edition', False)),
                'is_preorder': bool(p.get('is_preorder', False)),
                'category': p.get('category', ''),
                'shop_name': p.get('shop_name', ''),
                'color_count': 0,
            })

        return jsonify({
            'success': True,
            'products': products,
            'count': len(products)
        })

    except Exception as e:
        db_log('error', 'merchandise_public', f'Error fetching products for embed: {e}')
        return jsonify({'success': False, 'error': 'Internal error', 'products': []}), 500
