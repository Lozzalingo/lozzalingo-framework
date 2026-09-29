"""
Merchandise Admin Routes
========================

Admin interface for product/merchandise management.
Calls the centralised E-commerce Service (port 7224) for all product data.
"""

import os
import json
import time
from flask import render_template, request, redirect, url_for, session, jsonify, current_app
from . import merchandise_bp

from lozzalingo.core import db_log


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
    return os.getenv('ECOMMERCE_SITE_ID', os.getenv('EMAIL_SITE_ID', 'unknown'))


def _format_product(p):
    """Format a product dict from the service for the frontend."""
    price = p.get('base_price_pence', 0) or p.get('price', 0) or 0
    image_urls = p.get('image_urls', []) or p.get('image_urls_json', []) or []
    if isinstance(image_urls, str):
        try:
            image_urls = json.loads(image_urls)
        except (json.JSONDecodeError, TypeError):
            image_urls = []

    return {
        'id': p.get('id'),
        'name': p.get('name', ''),
        'description': p.get('description', ''),
        'price': price,
        'price_display': f"£{price / 100:.2f}",
        'stock_quantity': p.get('stock_quantity', 0),
        'is_preorder': p.get('is_preorder', False),
        'is_active': p.get('is_active', True),
        'limited_edition': p.get('limited_edition', False),
        'print_on_demand': p.get('print_on_demand', False),
        'sold_out': p.get('sold_out', False),
        'image_urls': image_urls,
        'front_design_url': p.get('front_design_url'),
        'back_design_url': p.get('back_design_url'),
        'front_mockup_url': p.get('front_mockup_url'),
        'back_mockup_url': p.get('back_mockup_url'),
        'sku': p.get('sku'),
        'fulfilment_meta': p.get('fulfilment_meta'),
    }


@merchandise_bp.route('/')
def merchandise_editor():
    """Merchandise editor - main interface"""
    print(f'[Merchandise] Loading editor page')
    if 'admin_id' not in session:
        return redirect(url_for('admin.login', next=request.path))

    return render_template('merchandise/merchandise_editor.html')

@merchandise_bp.route('/products')
def get_products():
    """Get all products from the E-commerce Service"""
    print(f'[Merchandise] GET /products')
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        client = _get_ecommerce_client()
        site_id = _get_site_id()
        result = client.list_products(site_id=site_id)

        if result is None:
            return jsonify({'products': []})

        products_list = result if isinstance(result, list) else result.get('products', result)
        if not isinstance(products_list, list):
            products_list = []

        products_data = {
            'products': [_format_product(p) for p in products_list]
        }
        return jsonify(products_data)

    except Exception as e:
        db_log('error', 'merchandise', f'Error getting products: {e}')
        return jsonify({'error': str(e)}), 500

@merchandise_bp.route('/product/<int:product_id>')
def get_product(product_id):
    """Get single product details from the E-commerce Service"""
    print(f'[Merchandise] GET /product/{product_id}')
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        client = _get_ecommerce_client()
        result = client.get_product(product_id)

        if not result:
            return jsonify({'success': False, 'error': 'Product not found'}), 404

        return jsonify({
            'success': True,
            'product': _format_product(result)
        })

    except Exception as e:
        db_log('error', 'merchandise', f'Error getting product: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@merchandise_bp.route('/create', methods=['POST'])
def create_product():
    """Create new product via the E-commerce Service"""
    print(f'[Merchandise] POST /create')
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        price_str = request.form.get('price', '').strip()
        stock_quantity = int(request.form.get('stock_quantity', 0))
        is_preorder = request.form.get('is_preorder') == 'true'
        limited_edition = request.form.get('limited_edition') == 'true'
        print_on_demand = request.form.get('print_on_demand') == 'true'
        sold_out = request.form.get('sold_out') == 'true'

        if not all([name, description, price_str]):
            return jsonify({'success': False, 'error': 'Name, description, and price are required'}), 400

        price = int(float(price_str) * 100)

        # Upload images via storage service
        image_urls = []
        uploaded_files = request.files.getlist('images')
        if uploaded_files:
            from lozzalingo.core.storage import upload_file
            for file in uploaded_files:
                if file and file.filename:
                    file_bytes = file.read()
                    timestamp = int(time.time())
                    safe_name = f"{timestamp}_{file.filename}"
                    url = upload_file(file_bytes, safe_name, 'merchandise')
                    image_urls.append(url)

        sku = request.form.get('sku', '').strip() or None
        fulfilment_meta_raw = request.form.get('fulfilment_meta', '').strip()
        fulfilment_meta = ''
        if fulfilment_meta_raw:
            try:
                json.loads(fulfilment_meta_raw)
                fulfilment_meta = fulfilment_meta_raw
            except json.JSONDecodeError:
                return jsonify({'success': False, 'error': 'Invalid JSON in fulfilment meta'}), 400

        client = _get_ecommerce_client()
        site_id = _get_site_id()
        result = client.create_product(
            name=name,
            site_id=site_id,
            base_price_pence=price,
            description=description,
            image_urls=image_urls,
            fulfilment_meta=fulfilment_meta,
            is_active=True,
        )

        if result:
            return jsonify({'success': True, 'product_id': result.get('id')})
        return jsonify({'success': False, 'error': 'Failed to create product'}), 500

    except Exception as e:
        db_log('error', 'merchandise', f'Error creating product: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@merchandise_bp.route('/update', methods=['POST'])
def update_product():
    """Update product via the E-commerce Service"""
    print(f'[Merchandise] POST /update')
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        product_id = request.form.get('product_id')
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        price_str = request.form.get('price', '').strip()

        if not all([product_id, name, description, price_str]):
            return jsonify({'success': False, 'error': 'All fields are required'}), 400

        # Handle image updates
        existing_image_order_raw = request.form.get('existing_image_order', '[]')
        images_to_delete_raw = request.form.get('images_to_delete', '[]')

        existing_image_order = json.loads(existing_image_order_raw)
        images_to_delete = json.loads(images_to_delete_raw)

        # Delete removed images from storage
        if images_to_delete:
            try:
                from lozzalingo.core.storage import delete_file
                for url in images_to_delete:
                    try:
                        delete_file(url)
                    except Exception as del_err:
                        db_log('warning', 'merchandise', f'Could not delete image {url}: {del_err}')
            except ImportError:
                pass

        # Build new image list
        new_image_urls = list(existing_image_order)

        uploaded_files = request.files.getlist('images')
        if uploaded_files:
            from lozzalingo.core.storage import upload_file
            for file in uploaded_files:
                if file and file.filename:
                    file_bytes = file.read()
                    timestamp = int(time.time())
                    safe_name = f"{timestamp}_{file.filename}"
                    url = upload_file(file_bytes, safe_name, 'merchandise')
                    new_image_urls.append(url)

        data = {
            'name': name,
            'description': description,
            'base_price_pence': int(float(price_str) * 100),
            'image_urls': new_image_urls,
            'is_preorder': request.form.get('is_preorder') == 'true',
            'is_active': True,
        }

        client = _get_ecommerce_client()
        result = client.update_product(int(product_id), data)

        if result:
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Failed to update product'}), 500

    except Exception as e:
        db_log('error', 'merchandise', f'Error updating product: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@merchandise_bp.route('/delete/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    """Delete product via the E-commerce Service"""
    print(f'[Merchandise] POST /delete/{product_id}')
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        client = _get_ecommerce_client()
        result = client.delete_product(product_id)

        if result:
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Failed to delete product'}), 500

    except Exception as e:
        db_log('error', 'merchandise', f'Error deleting product: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@merchandise_bp.route('/reorder', methods=['POST'])
def reorder_products():
    """Reorder products via the E-commerce Service"""
    print(f'[Merchandise] POST /reorder')
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        data = request.json
        product_orders = data.get('product_orders', [])

        if not product_orders:
            return jsonify({'success': False, 'error': 'No order data provided'}), 400

        client = _get_ecommerce_client()
        for po in product_orders:
            client.update_product(po['id'], {'sort_order': po.get('sort_order', 0)})

        return jsonify({'success': True})

    except Exception as e:
        db_log('error', 'merchandise', f'Error reordering products: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@merchandise_bp.route('/duplicate/<int:product_id>', methods=['POST'])
def duplicate_product(product_id):
    """Duplicate a product via the E-commerce Service"""
    print(f'[Merchandise] POST /duplicate/{product_id}')
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        client = _get_ecommerce_client()
        source = client.get_product(product_id)
        if not source:
            return jsonify({'success': False, 'error': 'Product not found'}), 404

        site_id = _get_site_id()
        result = client.create_product(
            name=f"{source.get('name', '')} (Copy)",
            site_id=site_id,
            base_price_pence=source.get('base_price_pence', 0),
            description=source.get('description', ''),
            image_urls=source.get('image_urls', []),
            is_active=True,
        )

        if result:
            return jsonify({'success': True, 'product_id': result.get('id')})
        return jsonify({'success': False, 'error': 'Failed to duplicate product'}), 500

    except Exception as e:
        db_log('error', 'merchandise', f'Error duplicating product: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@merchandise_bp.route('/upload-design', methods=['POST'])
def upload_design():
    """Upload a fulfilment design or mockup file (uncompressed)"""
    print(f'[Merchandise] POST /upload-design')
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        file = request.files.get('file')
        product_id = request.form.get('product_id')
        field = request.form.get('field')

        valid_fields = ['front_design_url', 'back_design_url', 'front_mockup_url', 'back_mockup_url']
        if not file or not product_id or field not in valid_fields:
            return jsonify({'success': False, 'error': 'Missing file, product_id, or invalid field'}), 400

        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'png'
        filename = f"{int(time.time())}_{field}_{product_id}.{ext}"

        from lozzalingo.core.storage import upload_file_raw
        file_bytes = file.read()
        url = upload_file_raw(file_bytes, filename, 'designs')

        # Update the product via the service
        client = _get_ecommerce_client()
        client.update_product(int(product_id), {field: url})

        return jsonify({'success': True, 'url': url})

    except Exception as e:
        db_log('error', 'merchandise', f'Error uploading design: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@merchandise_bp.route('/remove-design', methods=['POST'])
def remove_design():
    """Remove a fulfilment design or mockup file"""
    print(f'[Merchandise] POST /remove-design')
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        product_id = request.form.get('product_id')
        field = request.form.get('field')

        valid_fields = ['front_design_url', 'back_design_url', 'front_mockup_url', 'back_mockup_url']
        if not product_id or field not in valid_fields:
            return jsonify({'success': False, 'error': 'Missing product_id or invalid field'}), 400

        # Get current URL to delete from storage
        client = _get_ecommerce_client()
        product = client.get_product(int(product_id))
        if not product:
            return jsonify({'success': False, 'error': 'Product not found'}), 404

        current_url = product.get(field)
        if current_url:
            try:
                from lozzalingo.core.storage import delete_file
                delete_file(current_url)
            except Exception as del_err:
                db_log('warning', 'merchandise', f'Could not delete design file {current_url}: {del_err}')

        # Clear the field via the service
        client.update_product(int(product_id), {field: None})

        return jsonify({'success': True})

    except Exception as e:
        db_log('error', 'merchandise', f'Error removing design: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@merchandise_bp.route('/browse-storage')
def browse_storage():
    """List files in a storage subfolder for the storage browser modal"""
    print(f'[Merchandise] GET /browse-storage')
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        from lozzalingo.core.storage import list_files

        subfolder = request.args.get('subfolder', 'merchandise')
        files = list_files(subfolder)

        return jsonify({'success': True, 'files': files})

    except Exception as e:
        db_log('error', 'merchandise', f'Error browsing storage: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@merchandise_bp.route('/set-design-url', methods=['POST'])
def set_design_url():
    """Set a design/mockup field to an existing URL (from storage browser)"""
    print(f'[Merchandise] POST /set-design-url')
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        product_id = request.form.get('product_id')
        field = request.form.get('field')
        url = request.form.get('url')

        valid_fields = ['front_design_url', 'back_design_url', 'front_mockup_url', 'back_mockup_url']
        if not product_id or field not in valid_fields or not url:
            return jsonify({'success': False, 'error': 'Missing product_id, field, or url'}), 400

        client = _get_ecommerce_client()
        result = client.update_product(int(product_id), {field: url})

        if result:
            return jsonify({'success': True, 'url': url})
        return jsonify({'success': False, 'error': 'Product not found'}), 404

    except Exception as e:
        db_log('error', 'merchandise', f'Error setting design URL: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@merchandise_bp.route('/check-file-usage', methods=['POST'])
def check_file_usage():
    """Check if a file URL is used by any products"""
    print(f'[Merchandise] POST /check-file-usage')
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        url = request.form.get('url', '')
        if not url:
            return jsonify({'success': False, 'error': 'No URL provided'}), 400

        client = _get_ecommerce_client()
        site_id = _get_site_id()
        result = client.list_products(site_id=site_id)

        products_list = result if isinstance(result, list) else (result.get('products', []) if result else [])
        usage = []
        filename = url.rsplit('/', 1)[-1] if '/' in url else url

        for p in products_list:
            reasons = []
            image_urls = p.get('image_urls', []) or []
            if isinstance(image_urls, str):
                try:
                    image_urls = json.loads(image_urls)
                except (json.JSONDecodeError, TypeError):
                    image_urls = []

            for img_url in image_urls:
                if url in str(img_url) or str(img_url).endswith(filename):
                    reasons.append('listing image')
                    break

            for field, label in [
                ('front_design_url', 'front design'),
                ('back_design_url', 'back design'),
                ('front_mockup_url', 'front mockup'),
                ('back_mockup_url', 'back mockup'),
            ]:
                val = p.get(field)
                if val and (url in val or val.endswith(filename)):
                    reasons.append(label)

            if reasons:
                usage.append({'product': p.get('name', 'Unknown'), 'reasons': reasons})

        # Also check framework-level references
        try:
            from lozzalingo.core.storage import check_image_in_use
            framework_refs = check_image_in_use(url)
            for ref in framework_refs:
                usage.append({'product': f"{ref['type']}: {ref['title']}", 'reasons': ['referenced']})
        except Exception:
            pass

        return jsonify({'success': True, 'usage': usage, 'in_use': len(usage) > 0})

    except Exception as e:
        db_log('error', 'merchandise', f'Error checking file usage: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@merchandise_bp.route('/delete-storage-file', methods=['POST'])
def delete_storage_file():
    """Delete a file from storage"""
    print(f'[Merchandise] POST /delete-storage-file')
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        from lozzalingo.core.storage import delete_file

        url = request.form.get('url', '')
        if not url:
            return jsonify({'success': False, 'error': 'No URL provided'}), 400

        delete_file(url)
        return jsonify({'success': True})

    except Exception as e:
        db_log('error', 'merchandise', f'Error deleting storage file: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500
