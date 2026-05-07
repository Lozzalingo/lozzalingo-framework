"""
Public products API for cross-site embedding.

GET /api/products/embed?limit=3&shop=Crowd+Sauced

Returns a lightweight JSON array of active products with CORS headers,
suitable for embedding product ads in external sites (e.g. AI Blog Builder).
"""

import os
import json
import sqlite3
import logging
from flask import jsonify, request, current_app
from flask_cors import cross_origin
from . import merchandise_public_bp

logger = logging.getLogger(__name__)

# Allowed origins for CORS — add any domains that need to fetch products
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


def _get_merchandise_db():
    """Resolve merchandise.db path using framework config hierarchy."""
    # 1. Flask app config (set by Lozzalingo init or host app)
    try:
        val = current_app.config.get('MERCHANDISE_DB')
        if val and os.path.exists(val):
            return val
    except RuntimeError:
        pass

    # 2. Host app's Config class
    try:
        from config import Config
        if hasattr(Config, 'MERCHANDISE_DB') and os.path.exists(Config.MERCHANDISE_DB):
            return Config.MERCHANDISE_DB
    except ImportError:
        pass

    # 3. db_schema.DB (used by Crowd Sauced)
    try:
        from db_schema import DB
        if hasattr(DB, 'MERCHANDISE') and os.path.exists(DB.MERCHANDISE):
            return DB.MERCHANDISE
    except ImportError:
        pass

    # 4. Environment variable
    env_path = os.getenv('MERCHANDISE_DB')
    if env_path and os.path.exists(env_path):
        return env_path

    # 5. Default
    default = os.path.join(os.getcwd(), 'databases', 'merchandise.db')
    if os.path.exists(default):
        return default

    return None


def _get_design_engine_db():
    """Resolve design_engine.db path."""
    try:
        from db_schema import DB
        if hasattr(DB, 'DESIGN_ENGINE') and os.path.exists(DB.DESIGN_ENGINE):
            return DB.DESIGN_ENGINE
    except ImportError:
        pass

    env_path = os.getenv('DESIGN_ENGINE_DB')
    if env_path and os.path.exists(env_path):
        return env_path

    default = os.path.join(os.getcwd(), 'databases', 'design_engine.db')
    if os.path.exists(default):
        return default

    return None


def _get_base_url():
    """Get the site's public base URL for building product links."""
    # Check app config first
    try:
        url = current_app.config.get('EMAIL_WEBSITE_URL')
        if url:
            return url.rstrip('/')
    except RuntimeError:
        pass

    # Check env
    url = os.getenv('SITE_URL') or os.getenv('PRODUCTION_BASE_URL')
    if url:
        return url.rstrip('/')

    # Fallback to request host
    try:
        return request.host_url.rstrip('/')
    except RuntimeError:
        return ''


def ensure_shop_name_column():
    """Ensure every product has a correct shop_name.

    - Adds the shop_name column if missing
    - Adds a product_type column if missing (for sites that stored type data in shop_name)
    - Migrates misused shop_name values to product_type
    - Sets shop_name to EMAIL_BRAND_NAME on all rows that are empty/NULL
    """
    merch_db = _get_merchandise_db()
    if not merch_db:
        return

    brand = (
        current_app.config.get('EMAIL_BRAND_NAME')
        or current_app.config.get('brand_name')
        or ''
    )
    if not brand:
        return

    try:
        conn = sqlite3.connect(merch_db)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(products)")
        columns = {row[1] for row in cursor.fetchall()}

        # Add shop_name column if missing
        if 'shop_name' not in columns:
            print(f"[MerchandisePublic] Adding shop_name column to products table")
            cursor.execute('ALTER TABLE products ADD COLUMN shop_name TEXT')
            columns.add('shop_name')

        # Add product_type column if missing (used by sites that need type filtering)
        if 'product_type' not in columns:
            cursor.execute('ALTER TABLE products ADD COLUMN product_type TEXT')
            columns.add('product_type')

        # Migrate: if shop_name contains product type data (not the brand name),
        # move it to product_type and clear shop_name so it gets set correctly below.
        # Product type values are lowercase identifiers like 'blend', 'single_origin', 'decaf'.
        # Real shop names contain spaces or capitals (e.g. 'Crowd Sauced', 'Mario Pinto MMA').
        cursor.execute('''
            UPDATE products
            SET product_type = shop_name, shop_name = NULL
            WHERE shop_name IS NOT NULL
            AND shop_name != ''
            AND shop_name != ?
            AND shop_name = LOWER(shop_name)
            AND shop_name NOT LIKE '% %'
            AND product_type IS NULL
        ''', (brand,))
        if cursor.rowcount > 0:
            print(f"[MerchandisePublic] Migrated {cursor.rowcount} product type value(s) from shop_name to product_type")

        # Fill any empty/NULL shop_name rows with the brand name
        cursor.execute(
            "UPDATE products SET shop_name = ? WHERE shop_name IS NULL OR shop_name = ''",
            (brand,)
        )
        if cursor.rowcount > 0:
            print(f"[MerchandisePublic] Set shop_name='{brand}' on {cursor.rowcount} product(s)")

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[MerchandisePublic] Error ensuring shop_name: {e}")


@merchandise_public_bp.record_once
def on_register(state):
    """Run shop_name migration when the blueprint is registered."""
    with state.app.app_context():
        ensure_shop_name_column()


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
    limit = min(request.args.get('limit', 6, type=int), 20)
    shop_filter = request.args.get('shop')

    merch_db = _get_merchandise_db()
    if not merch_db:
        return jsonify({'success': False, 'error': 'Database not configured', 'products': []}), 200

    try:
        conn = sqlite3.connect(merch_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Detect available columns to handle different DB schemas
        cursor.execute("PRAGMA table_info(products)")
        available_cols = {row[1] for row in cursor.fetchall()}

        # Core columns (must exist)
        select_cols = ['id', 'name', 'description', 'price', 'image_urls',
                       'stock_quantity', 'is_preorder', 'is_active']
        # Optional columns (may not exist in all deployments)
        optional_cols = ['category', 'shop_name', 'sex', 'limited_edition',
                         'print_on_demand', 'sort_order']
        for col in optional_cols:
            if col in available_cols:
                select_cols.append(col)

        query = f'''
            SELECT {', '.join(select_cols)}
            FROM products
            WHERE is_active = 1
            AND name IS NOT NULL AND name != ''
        '''
        params = []

        if shop_filter and 'shop_name' in available_cols:
            query += ' AND shop_name = ?'
            params.append(shop_filter)

        # Only include in-stock or preorder or print-on-demand
        if 'print_on_demand' in available_cols:
            query += ' AND (stock_quantity > 0 OR is_preorder = 1 OR print_on_demand = 1)'
        else:
            query += ' AND (stock_quantity > 0 OR is_preorder = 1)'

        if 'sort_order' in available_cols:
            query += ' ORDER BY COALESCE(sort_order, 999), id'
        else:
            query += ' ORDER BY id'
        query += ' LIMIT ?'
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        # Get design_engine data for colour_group (used for color options display)
        design_db = _get_design_engine_db()
        design_data = {}
        if design_db:
            try:
                de_conn = sqlite3.connect(design_db)
                de_conn.row_factory = sqlite3.Row
                de_cursor = de_conn.cursor()
                product_ids = [row['id'] for row in rows]
                if product_ids:
                    placeholders = ','.join('?' * len(product_ids))
                    de_cursor.execute(f'''
                        SELECT id, colour_group
                        FROM design_engine
                        WHERE id IN ({placeholders})
                    ''', product_ids)
                    for de_row in de_cursor.fetchall():
                        design_data[de_row['id']] = de_row['colour_group']
                de_conn.close()
            except Exception:
                pass

        base_url = _get_base_url()

        products = []

        for row in rows:
            # Parse primary image
            image_url = ''
            if row['image_urls']:
                try:
                    images = json.loads(row['image_urls'])
                    if isinstance(images, list):
                        for img in images:
                            if img and str(img).strip():
                                image_url = str(img).strip()
                                # Make paths absolute for cross-site embedding
                                if image_url.startswith(('http://', 'https://')):
                                    pass  # Already absolute
                                elif image_url.startswith('/static/'):
                                    image_url = f"{base_url}{image_url}"
                                else:
                                    # Legacy fallback for bare filenames
                                    image_url = f"{base_url}/static/{image_url}"
                                break
                except (json.JSONDecodeError, TypeError):
                    pass

            # Truncate description
            desc = row['description'] or ''
            if len(desc) > 100:
                desc = desc[:97] + '...'

            # Format price (stored in pence)
            price = row['price'] or 0
            price_display = f"\u00a3{price / 100:.2f}"

            # Build product URL — uses configurable shop path
            # Set SHOP_URL_PATH in app config (e.g. '/aightclothing' or '/merchandise')
            shop_path = current_app.config.get('SHOP_URL_PATH', '/merchandise')
            product_url = f"{base_url}{shop_path}#product-{row['id']}"

            # Parse color options count
            color_count = 0
            colour_group = design_data.get(row['id'])
            if colour_group:
                try:
                    colors = json.loads(colour_group)
                    if isinstance(colors, list):
                        color_count = len(colors)
                except (json.JSONDecodeError, TypeError):
                    pass

            # Safe access for optional columns
            def _get(r, col, default=None):
                try:
                    return r[col]
                except (IndexError, KeyError):
                    return default

            products.append({
                'id': row['id'],
                'name': row['name'],
                'description': desc,
                'price_display': price_display,
                'price_pence': price,
                'image_url': image_url,
                'product_url': product_url,
                'limited_edition': bool(_get(row, 'limited_edition', False)),
                'is_preorder': bool(row['is_preorder']),
                'category': _get(row, 'category', ''),
                'shop_name': _get(row, 'shop_name', ''),
                'color_count': color_count,
            })

        return jsonify({
            'success': True,
            'products': products,
            'count': len(products)
        })

    except Exception as e:
        logger.error(f"Error fetching products for embed: {e}")
        return jsonify({'success': False, 'error': 'Internal error', 'products': []}), 500
