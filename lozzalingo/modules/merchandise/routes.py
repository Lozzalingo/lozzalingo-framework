"""
Merchandise Admin Routes
========================

Complete product/merchandise management for admin.
Framework-ready with optional imports.
"""

from flask import render_template, request, redirect, url_for, session, jsonify, current_app
from . import merchandise_bp

@merchandise_bp.route('/')
def merchandise_editor():
    """Merchandise editor - main interface"""
    if 'admin_id' not in session:
        return redirect(url_for('admin.login', next=request.path))

    return render_template('merchandise/merchandise_editor.html')

@merchandise_bp.route('/products')
def get_products():
    """Get all products"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        from app.models.merchandise import Product
        products = Product.get_all_active()

        # Format products for frontend
        products_data = {
            'products': [{
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'price': p.price,
                'price_display': f"£{p.price / 100:.2f}",
                'stock_quantity': p.stock_quantity,
                'is_preorder': p.is_preorder,
                'is_active': p.is_active,
                'limited_edition': p.limited_edition,
                'print_on_demand': getattr(p, 'print_on_demand', False),
                'sold_out': getattr(p, 'sold_out', False),
                'image_urls': p.image_urls or [],
                'front_design_url': getattr(p, 'front_design_url', None),
                'back_design_url': getattr(p, 'back_design_url', None),
                'front_mockup_url': getattr(p, 'front_mockup_url', None),
                'back_mockup_url': getattr(p, 'back_mockup_url', None),
                'sku': getattr(p, 'sku', None),
                'fulfilment_meta': getattr(p, 'fulfilment_meta', None),
            } for p in products]
        }

        return jsonify(products_data)

    except ImportError:
        return jsonify({'products': []})  # Return empty if no merchandise model
    except Exception as e:
        print(f"Error getting products: {e}")
        return jsonify({'error': str(e)}), 500

@merchandise_bp.route('/product/<int:product_id>')
def get_product(product_id):
    """Get single product details"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        from app.models.merchandise import Product
        product = Product.get_by_id(product_id)

        if not product:
            return jsonify({'success': False, 'error': 'Product not found'}), 404

        return jsonify({
            'success': True,
            'product': {
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'price': product.price,
                'price_display': f"£{product.price / 100:.2f}",
                'stock_quantity': product.stock_quantity,
                'is_preorder': product.is_preorder,
                'is_active': product.is_active,
                'limited_edition': product.limited_edition,
                'print_on_demand': getattr(product, 'print_on_demand', False),
                'sold_out': getattr(product, 'sold_out', False),
                'image_urls': product.image_urls or [],
                'front_design_url': getattr(product, 'front_design_url', None),
                'back_design_url': getattr(product, 'back_design_url', None),
                'front_mockup_url': getattr(product, 'front_mockup_url', None),
                'back_mockup_url': getattr(product, 'back_mockup_url', None),
                'sku': getattr(product, 'sku', None),
                'fulfilment_meta': getattr(product, 'fulfilment_meta', None),
            }
        })

    except ImportError:
        return jsonify({'success': False, 'error': 'Merchandise models not available'}), 500
    except Exception as e:
        print(f"Error getting product: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@merchandise_bp.route('/create', methods=['POST'])
def create_product():
    """Create new product"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        from app.models.merchandise import Product
        import json

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

        # Convert price to pence
        price = int(float(price_str) * 100)

        # Upload new images
        image_urls = []
        uploaded_files = request.files.getlist('images')
        if uploaded_files:
            from lozzalingo.core.storage import upload_file
            import time
            for file in uploaded_files:
                if file and file.filename:
                    file_bytes = file.read()
                    timestamp = int(time.time())
                    safe_name = f"{timestamp}_{file.filename}"
                    url = upload_file(file_bytes, safe_name, 'merchandise')
                    image_urls.append(url)

        # Create product
        sku = request.form.get('sku', '').strip() or None
        fulfilment_meta_raw = request.form.get('fulfilment_meta', '').strip()
        fulfilment_meta = None
        if fulfilment_meta_raw:
            try:
                fulfilment_meta = json.loads(fulfilment_meta_raw)
            except json.JSONDecodeError:
                return jsonify({'success': False, 'error': 'Invalid JSON in fulfilment meta'}), 400
        product = Product(
            name=name,
            description=description,
            price=price,
            stock_quantity=stock_quantity,
            is_preorder=is_preorder,
            limited_edition=limited_edition,
            print_on_demand=print_on_demand,
            sold_out=sold_out,
            is_active=True,
            image_urls=image_urls,
            sku=sku,
            fulfilment_meta=fulfilment_meta
        )
        product.save()

        return jsonify({'success': True, 'product_id': product.id})

    except ImportError:
        return jsonify({'success': False, 'error': 'Merchandise models not available'}), 500
    except Exception as e:
        print(f"Error creating product: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@merchandise_bp.route('/update', methods=['POST'])
def update_product():
    """Update product"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        from app.models.merchandise import Product
        import json

        product_id = request.form.get('product_id')
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        price_str = request.form.get('price', '').strip()
        stock_quantity = int(request.form.get('stock_quantity', 0))
        is_preorder = request.form.get('is_preorder') == 'true'
        limited_edition = request.form.get('limited_edition') == 'true'
        print_on_demand = request.form.get('print_on_demand') == 'true'

        if not all([product_id, name, description, price_str]):
            return jsonify({'success': False, 'error': 'All fields are required'}), 400

        # Get existing product
        product = Product.get_by_id(int(product_id))
        if not product:
            return jsonify({'success': False, 'error': 'Product not found'}), 404

        # Update fields
        product.name = name
        product.description = description
        product.price = int(float(price_str) * 100)
        product.stock_quantity = stock_quantity
        product.is_preorder = is_preorder
        product.limited_edition = limited_edition
        product.print_on_demand = print_on_demand
        product.sold_out = request.form.get('sold_out') == 'true'
        product.sku = request.form.get('sku', '').strip() or None
        fulfilment_meta_raw = request.form.get('fulfilment_meta', '').strip()
        if fulfilment_meta_raw:
            try:
                product.fulfilment_meta = json.loads(fulfilment_meta_raw)
            except json.JSONDecodeError:
                return jsonify({'success': False, 'error': 'Invalid JSON in fulfilment meta'}), 400
        else:
            product.fulfilment_meta = None

        # Handle image updates: reordering + deletions + new uploads
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
                    except Exception as e:
                        print(f"Warning: could not delete image {url}: {e}")
            except ImportError:
                pass

        # Build new image list: existing (in new order) + newly uploaded
        new_image_urls = list(existing_image_order)
        print(f"MERCH_UPDATE: Product {product_id} - existing order: {new_image_urls}")
        print(f"MERCH_UPDATE: Product {product_id} - images to delete: {images_to_delete}")

        uploaded_files = request.files.getlist('images')
        if uploaded_files:
            from lozzalingo.core.storage import upload_file
            import time
            for file in uploaded_files:
                if file and file.filename:
                    file_bytes = file.read()
                    timestamp = int(time.time())
                    safe_name = f"{timestamp}_{file.filename}"
                    url = upload_file(file_bytes, safe_name, 'merchandise')
                    new_image_urls.append(url)
                    print(f"MERCH_UPDATE: Uploaded new image: {url}")

        product.image_urls = new_image_urls
        print(f"MERCH_UPDATE: Product {product_id} - final image_urls: {new_image_urls}")
        product.save()
        return jsonify({'success': True})

    except ImportError:
        return jsonify({'success': False, 'error': 'Merchandise models not available'}), 500
    except Exception as e:
        print(f"Error updating product: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@merchandise_bp.route('/delete/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    """Delete product"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        from app.models.merchandise import get_merchandise_db

        conn = get_merchandise_db()
        cursor = conn.cursor()

        # Delete product
        cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
        conn.commit()
        conn.close()

        return jsonify({'success': True})

    except ImportError:
        return jsonify({'success': False, 'error': 'Merchandise models not available'}), 500
    except Exception as e:
        print(f"Error deleting product: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@merchandise_bp.route('/reorder', methods=['POST'])
def reorder_products():
    """Reorder products"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        from app.models.merchandise import Product

        data = request.json
        product_orders = data.get('product_orders', [])

        if not product_orders:
            return jsonify({'success': False, 'error': 'No order data provided'}), 400

        # Update sort orders
        Product.update_sort_orders(product_orders)

        return jsonify({'success': True})

    except ImportError:
        return jsonify({'success': False, 'error': 'Merchandise models not available'}), 500
    except Exception as e:
        print(f"Error reordering products: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@merchandise_bp.route('/duplicate/<int:product_id>', methods=['POST'])
def duplicate_product(product_id):
    """Duplicate a product with all its fields (except images)"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        from app.models.merchandise import Product

        source = Product.get_by_id(product_id)
        if not source:
            return jsonify({'success': False, 'error': 'Product not found'}), 404

        # Create a copy with "(Copy)" suffix
        new_product = Product(
            name=f"{source.name} (Copy)",
            description=source.description,
            price=source.price,
            stripe_price_id=None,
            stripe_product_id=None,
            stock_quantity=source.stock_quantity,
            is_preorder=getattr(source, 'is_preorder', False),
            is_active=True,
            image_urls=list(source.image_urls) if source.image_urls else [],
            limited_edition=getattr(source, 'limited_edition', False),
        )

        # Copy design/mockup URLs if they exist
        for field in ['front_design_url', 'back_design_url', 'front_mockup_url', 'back_mockup_url']:
            setattr(new_product, field, getattr(source, field, None))

        # Copy print_on_demand and sold_out if they exist
        if hasattr(source, 'print_on_demand'):
            new_product.print_on_demand = source.print_on_demand
        if hasattr(source, 'sold_out'):
            new_product.sold_out = source.sold_out

        new_product.save()

        print(f"DUPLICATE_PRODUCT: Duplicated product {product_id} -> {new_product.id}")
        return jsonify({'success': True, 'product_id': new_product.id})

    except ImportError:
        return jsonify({'success': False, 'error': 'Merchandise models not available'}), 500
    except Exception as e:
        print(f"Error duplicating product: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@merchandise_bp.route('/upload-design', methods=['POST'])
def upload_design():
    """Upload a fulfilment design or mockup file (uncompressed)"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        from app.models.merchandise import Product, get_merchandise_db

        file = request.files.get('file')
        product_id = request.form.get('product_id')
        field = request.form.get('field')

        valid_fields = ['front_design_url', 'back_design_url', 'front_mockup_url', 'back_mockup_url']
        if not file or not product_id or field not in valid_fields:
            return jsonify({'success': False, 'error': 'Missing file, product_id, or invalid field'}), 400

        product = Product.get_by_id(int(product_id))
        if not product:
            return jsonify({'success': False, 'error': 'Product not found'}), 404

        # Generate unique filename
        import time
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'png'
        filename = f"{int(time.time())}_{field}_{product_id}.{ext}"

        # Upload without compression (print-ready files)
        from lozzalingo.core.storage import upload_file_raw
        file_bytes = file.read()
        url = upload_file_raw(file_bytes, filename, 'designs')

        # Update the product's column directly
        conn = get_merchandise_db()
        cursor = conn.cursor()
        cursor.execute(f'UPDATE products SET {field} = ? WHERE id = ?', (url, int(product_id)))
        conn.commit()
        conn.close()

        print(f"DESIGN_UPLOAD: Uploaded {field} for product {product_id}: {url}")
        return jsonify({'success': True, 'url': url})

    except ImportError as e:
        print(f"Error uploading design (import): {e}")
        return jsonify({'success': False, 'error': 'Merchandise models not available'}), 500
    except Exception as e:
        print(f"Error uploading design: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@merchandise_bp.route('/remove-design', methods=['POST'])
def remove_design():
    """Remove a fulfilment design or mockup file"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        from app.models.merchandise import Product, get_merchandise_db

        product_id = request.form.get('product_id')
        field = request.form.get('field')

        valid_fields = ['front_design_url', 'back_design_url', 'front_mockup_url', 'back_mockup_url']
        if not product_id or field not in valid_fields:
            return jsonify({'success': False, 'error': 'Missing product_id or invalid field'}), 400

        product = Product.get_by_id(int(product_id))
        if not product:
            return jsonify({'success': False, 'error': 'Product not found'}), 404

        # Optionally delete the file from storage
        current_url = getattr(product, field, None)
        if current_url:
            try:
                from lozzalingo.core.storage import delete_file
                delete_file(current_url)
            except Exception as e:
                print(f"Warning: Could not delete design file {current_url}: {e}")

        # Clear the column
        conn = get_merchandise_db()
        cursor = conn.cursor()
        cursor.execute(f'UPDATE products SET {field} = NULL WHERE id = ?', (int(product_id),))
        conn.commit()
        conn.close()

        print(f"DESIGN_REMOVE: Cleared {field} for product {product_id}")
        return jsonify({'success': True})

    except ImportError:
        return jsonify({'success': False, 'error': 'Merchandise models not available'}), 500
    except Exception as e:
        print(f"Error removing design: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@merchandise_bp.route('/browse-storage')
def browse_storage():
    """List files in a storage subfolder for the storage browser modal"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        from lozzalingo.core.storage import list_files

        subfolder = request.args.get('subfolder', 'merchandise')
        files = list_files(subfolder)

        return jsonify({'success': True, 'files': files})

    except Exception as e:
        print(f"Error browsing storage: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@merchandise_bp.route('/set-design-url', methods=['POST'])
def set_design_url():
    """Set a design/mockup field to an existing URL (from storage browser)"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        from app.models.merchandise import Product, get_merchandise_db

        product_id = request.form.get('product_id')
        field = request.form.get('field')
        url = request.form.get('url')

        valid_fields = ['front_design_url', 'back_design_url', 'front_mockup_url', 'back_mockup_url']
        if not product_id or field not in valid_fields or not url:
            return jsonify({'success': False, 'error': 'Missing product_id, field, or url'}), 400

        product = Product.get_by_id(int(product_id))
        if not product:
            return jsonify({'success': False, 'error': 'Product not found'}), 404

        conn = get_merchandise_db()
        cursor = conn.cursor()
        cursor.execute(f'UPDATE products SET {field} = ? WHERE id = ?', (url, int(product_id)))
        conn.commit()
        conn.close()

        print(f"DESIGN_SET_URL: Set {field} for product {product_id}: {url}")
        return jsonify({'success': True, 'url': url})

    except ImportError:
        return jsonify({'success': False, 'error': 'Merchandise models not available'}), 500
    except Exception as e:
        print(f"Error setting design URL: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@merchandise_bp.route('/check-file-usage', methods=['POST'])
def check_file_usage():
    """Check if a file URL is used by any products (images, designs, mockups)"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        from app.models.merchandise import Product

        url = request.form.get('url', '')
        if not url:
            return jsonify({'success': False, 'error': 'No URL provided'}), 400

        # Check all products for usage
        products = Product.get_all_active()
        usage = []

        # Also extract the filename to check against relative image_urls
        filename = url.rsplit('/', 1)[-1] if '/' in url else url

        for p in products:
            reasons = []
            # Check image_urls (may be relative paths like "merchandise/file.png")
            for img_url in (p.image_urls or []):
                if url in img_url or img_url.endswith(filename):
                    reasons.append('listing image')
                    break

            # Check design/mockup URL columns
            for field, label in [
                ('front_design_url', 'front design'),
                ('back_design_url', 'back design'),
                ('front_mockup_url', 'front mockup'),
                ('back_mockup_url', 'back mockup'),
            ]:
                val = getattr(p, field, None)
                if val and (url in val or val.endswith(filename)):
                    reasons.append(label)

            if reasons:
                usage.append({'product': p.name, 'reasons': reasons})

        # Also check framework-level references (news, projects, quick-links)
        try:
            from lozzalingo.core.storage import check_image_in_use
            framework_refs = check_image_in_use(url)
            for ref in framework_refs:
                usage.append({'product': f"{ref['type']}: {ref['title']}", 'reasons': ['referenced']})
        except Exception:
            pass

        return jsonify({'success': True, 'usage': usage, 'in_use': len(usage) > 0})

    except Exception as e:
        print(f"Error checking file usage: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@merchandise_bp.route('/delete-storage-file', methods=['POST'])
def delete_storage_file():
    """Delete a file from storage"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        from lozzalingo.core.storage import delete_file

        url = request.form.get('url', '')
        if not url:
            return jsonify({'success': False, 'error': 'No URL provided'}), 400

        delete_file(url)
        print(f"STORAGE_DELETE: Deleted file {url}")
        return jsonify({'success': True})

    except Exception as e:
        print(f"Error deleting storage file: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
