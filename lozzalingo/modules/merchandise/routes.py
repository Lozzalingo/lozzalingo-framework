"""
Merchandise Admin Routes
========================

Complete product/merchandise management for admin.
Framework-ready with optional imports.
"""

from flask import render_template, request, redirect, url_for, session, jsonify
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
                'image_urls': p.image_urls or []
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
                'image_urls': product.image_urls or []
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

        if not all([name, description, price_str]):
            return jsonify({'success': False, 'error': 'Name, description, and price are required'}), 400

        # Convert price to pence
        price = int(float(price_str) * 100)

        # Create product
        product = Product(
            name=name,
            description=description,
            price=price,
            stock_quantity=stock_quantity,
            is_preorder=is_preorder,
            limited_edition=limited_edition,
            print_on_demand=print_on_demand,
            is_active=True,
            image_urls=[]
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
