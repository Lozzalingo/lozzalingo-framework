"""
Orders Routes
=============

Framework-ready order management module.
Supports multiple project structures via fallback imports.

Provides:
- Admin routes on orders_bp (/admin/orders-manager)
- Public /api/recent-sales endpoint on orders_public_bp (API key protected)
"""

import os
import sqlite3
from flask import render_template, request, redirect, url_for, session, jsonify, current_app
from . import orders_bp, orders_public_bp


def _get_merchandise_conn():
    """Get a SQLite connection to the merchandise database.

    Tries app.models.merchandise first (Mario Pinto pattern),
    falls back to direct SQLite connection using Config (Coffee Goblin pattern).
    """
    try:
        from app.models.merchandise import get_merchandise_db
        return get_merchandise_db()
    except ImportError:
        pass

    # Fallback: resolve DB path from config
    db_path = current_app.config.get('MERCHANDISE')
    if not db_path:
        try:
            from config import Config
            db_path = (
                Config.MERCHANDISE_DB if hasattr(Config, 'MERCHANDISE_DB')
                else Config.MERCHANDISE if hasattr(Config, 'MERCHANDISE')
                else None
            )
        except ImportError:
            import os
            db_path = os.getenv('MERCHANDISE_DB', 'merchandise.db')

    if not db_path:
        return None

    return sqlite3.connect(db_path)

@orders_bp.route('/')
def orders_manager():
    """Order management page"""
    if 'admin_id' not in session:
        return redirect(url_for('admin.login', next=request.path))

    from flask import current_app
    etsy_shops = current_app.config.get('ETSY_SHOPS', [])

    # Per-app fulfilment config. Apps set ORDERS_FULFILMENT_CONFIG in app.config.
    # Default: no provider-specific UI (generic order management only).
    # Example config:
    # {
    #     'provider_name': 'Limini Coffee',
    #     'fields': [
    #         {'id': 'fulfilment-status', 'label': 'Fulfilment Status', 'key': 'fulfilment_status', 'placeholder': 'pending / ready / fulfilled'},
    #         {'id': 'carrier', 'label': 'Carrier', 'key': 'carrier', 'placeholder': 'e.g., DPD, Royal Mail'},
    #         {'id': 'tracking-number', 'label': 'Tracking Number', 'key': 'tracking_number', 'placeholder': 'Enter tracking number'},
    #     ],
    #     'row_actions': [
    #         {'label': '📦 Fulfil', 'onclick': 'fulfilOrder({order_id})', 'style': 'background: #28a745; color: white;', 'condition': "order.status === 'completed'"},
    #     ],
    #     'modal_actions': [
    #         {'label': '📦 Mark as Ready', 'onclick': 'markReady({order_id}, this)', 'style': 'background: #28a745;'},
    #     ],
    # }
    fulfilment_config = current_app.config.get('ORDERS_FULFILMENT_CONFIG', None)

    return render_template('orders/orders_manager.html',
                           etsy_shops=etsy_shops,
                           fulfilment_config=fulfilment_config)

@orders_bp.route('/api/orders')
def api_orders():
    """List recent orders for admin"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        conn = _get_merchandise_conn()
        if not conn:
            return jsonify({'success': True, 'orders': [], 'message': 'Merchandise database not configured'})

        # Check if ORM models are available (Mario Pinto) or use raw SQL (Coffee Goblin)
        _use_raw_sql = True
        try:
            from app.models.merchandise import OrderItem, Product
            _use_raw_sql = False
        except ImportError:
            pass
        cursor = conn.cursor()

        # Use SELECT * so we get all columns regardless of schema
        cursor.execute('SELECT * FROM orders ORDER BY id DESC LIMIT 50')
        col_names = [desc[0] for desc in cursor.description]

        orders = []
        for row in cursor.fetchall():
            r = dict(zip(col_names, row))

            order_id = r.get('id')
            order_number_val = r.get('order_number')
            receipt_id = r.get('receipt_id')
            session_id = r.get('stripe_session_id')
            email = r.get('customer_email')
            name = r.get('customer_name')
            amount = r.get('total_amount')
            status = r.get('status')
            created_at = r.get('created_at')
            ship_name = r.get('shipping_name')
            fulfilment_status_val = r.get('fulfilment_status')
            order_shop = r.get('shop')

            # Get order items for this order
            product_names = []
            shop_name = order_shop  # Prefer shop from the order row (set by insert_order for Etsy)

            # Check if order_items has grind_type column
            _has_grind_type = False
            try:
                _gi_cursor = conn.cursor()
                _gi_cursor.execute("PRAGMA table_info(order_items)")
                _oi_cols = {c[1] for c in _gi_cursor.fetchall()}
                _has_grind_type = 'grind_type' in _oi_cols
            except Exception:
                pass

            grind_types = []  # Collect grind types for this order

            if _use_raw_sql:
                # Raw SQL fallback for projects without ORM models
                items_cursor = conn.cursor()
                grind_col = ', oi.grind_type' if _has_grind_type else ''
                items_cursor.execute(f'''
                    SELECT oi.quantity, p.name{grind_col}
                    FROM order_items oi
                    LEFT JOIN products p ON oi.product_id = p.id
                    WHERE oi.order_id = ?
                ''', (order_id,))
                for item_row in items_cursor.fetchall():
                    item_qty = item_row[0] or 1
                    item_name = item_row[1] or 'Unknown'
                    if item_qty > 1:
                        item_name += f" x{item_qty}"
                    product_names.append(item_name)
                    if _has_grind_type and len(item_row) > 2 and item_row[2]:
                        grind_types.append(item_row[2])
            else:
                order_items = OrderItem.get_by_order_id(order_id)

                for item in order_items:
                    product = Product.get_by_id(item.product_id)
                    if product:
                        item_name = f"{product.name}"
                        if item.size:
                            item_name += f" ({item.size})"
                        if item.quantity > 1:
                            item_name += f" x{item.quantity}"
                        product_names.append(item_name)
                        # Fall back to shop_name from product if order has no shop
                        if not shop_name and hasattr(product, 'shop_name'):
                            shop_name = product.shop_name

                # If no order_items, check if order has product_id directly (Etsy orders)
                if not product_names and has_product_id:
                    # Get product_id from order
                    order_cursor = conn.cursor()
                    order_cursor.execute('SELECT product_id FROM orders WHERE id = ?', (order_id,))
                    prod_row = order_cursor.fetchone()
                    if prod_row and prod_row[0]:
                        product = Product.get_by_id(prod_row[0])
                        if product:
                            product_names.append(product.name)
                            if not shop_name:
                                shop_name = getattr(product, 'shop_name', None)

            # Format order number display
            # Only completed orders get a real order number. Abandoned/expired
            # carts have no order_number and should not fake one.
            is_abandoned = (
                status in ('expired',) or
                (email and email == 'pending') or
                (status == 'pending' and not email)
            )
            if order_number_val:
                display_order_number = f"#{order_number_val}"
            elif is_abandoned:
                display_order_number = ""
            else:
                display_order_number = f"ORD-{str(order_id).zfill(6)}"

            order_entry = {
                'id': order_id,
                'order_number': display_order_number,
                'receipt_id': receipt_id,
                'session_id': session_id,
                'customer_email': email,
                'customer_name': name or ship_name,
                'total_amount': amount,
                'amount_display': f"£{amount / 100:.2f}" if amount else "£0.00",
                'status': status,
                'fulfilment_status': fulfilment_status_val or 'pending',
                'created_at': created_at,
                'products': ", ".join(product_names) if product_names else "Unknown",
                'shop': shop_name,
                'visitor_ip': r.get('visitor_ip', ''),
                'visitor_city': r.get('visitor_city', ''),
            }

            # Pass through extra columns when they exist (app-specific fields)
            _extra_list_keys = [
                'subscription_id', 'scheduled_delivery_date',
                'shipping_name', 'shipping_line1', 'shipping_city', 'shipping_postal_code',
                'shipping_cost', 'vegan_discovery_pack', 'order_type',
            ]
            # Integer columns where 0 is a meaningful value (not to be replaced with '')
            _int_extra_keys = {'shipping_cost', 'vegan_discovery_pack'}
            for _ek in _extra_list_keys:
                if _ek in r:
                    val = r[_ek]
                    if _ek in _int_extra_keys:
                        order_entry[_ek] = val if val is not None else 0
                    else:
                        order_entry[_ek] = val or ''

            if grind_types:
                order_entry['grind_types'] = grind_types

            orders.append(order_entry)

        conn.close()

        # Calculate summary stats server-side for the response
        # Filter out abandoned orders for revenue calculations
        def _is_real_order(o):
            s = o.get('status')
            e = o.get('customer_email')
            if s == 'expired':
                return False
            if e and e == 'pending':
                return False
            if s == 'pending' and not e:
                return False
            return True

        real_orders = [o for o in orders if _is_real_order(o)]
        total_gross = sum(o.get('total_amount') or 0 for o in real_orders)
        total_shipping = sum(o.get('shipping_cost') or 0 for o in real_orders)
        total_net = total_gross - total_shipping

        summary = {
            'total_orders': len(real_orders),
            'total_gross': total_gross,
            'total_gross_display': f"£{total_gross / 100:.2f}",
            'total_shipping': total_shipping,
            'total_shipping_display': f"£{total_shipping / 100:.2f}",
            'total_net': total_net,
            'total_net_display': f"£{total_net / 100:.2f}",
        }

        return jsonify({
            'success': True,
            'orders': orders,
            'summary': summary,
        })

    except Exception as e:
        print(f"Error listing orders: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@orders_bp.route('/api/order/<int:order_id>')
def api_order_details(order_id):
    """Get detailed order information"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        conn = _get_merchandise_conn()
        if not conn:
            return jsonify({'success': False, 'error': 'Database not configured'}), 500

        cursor = conn.cursor()

        # Get all columns for this order
        cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Order not found'}), 404

        # Get column names
        col_names = [desc[0] for desc in cursor.description]
        order_dict = dict(zip(col_names, row))

        # Check if order_items has extra columns (grind_type etc.)
        cursor.execute("PRAGMA table_info(order_items)")
        _oi_detail_cols = {c[1] for c in cursor.fetchall()}
        _detail_has_grind = 'grind_type' in _oi_detail_cols

        # Get order items with product details
        grind_col = ', oi.grind_type' if _detail_has_grind else ''
        cursor.execute(f'''
            SELECT oi.id, oi.product_id, oi.quantity, oi.price_at_time,
                   p.name as product_name{grind_col}
            FROM order_items oi
            LEFT JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = ?
        ''', (order_id,))
        items = []
        for item_row in cursor.fetchall():
            item_cols = [desc[0] for desc in cursor.description]
            item = dict(zip(item_cols, item_row))
            price = item.get('price_at_time') or 0
            qty = item.get('quantity') or 1
            item_data = {
                'id': item.get('id'),
                'product_id': item.get('product_id'),
                'product_name': item.get('product_name') or 'Unknown',
                'quantity': qty,
                'size': item.get('size', ''),
                'color': item.get('color', ''),
                'price_at_time': price,
                'subtotal': price * qty
            }
            if _detail_has_grind:
                item_data['grind_type'] = item.get('grind_type', '') or ''
            items.append(item_data)

        conn.close()

        # Format order number
        order_number_val = order_dict.get('order_number')
        display_order_number = f"#{order_number_val}" if order_number_val else f"ORD-{str(order_id).zfill(6)}"

        total = order_dict.get('total_amount') or 0

        # Start with ALL columns from the DB row, so apps with custom columns
        # (subscription_id, scheduled_delivery_date, shipping_cost, etc.)
        # get their data without needing framework changes each time.
        order_data = {}
        # Integer columns where 0 is meaningful (not to be replaced with '')
        _int_keys = {'shipping_cost', 'vegan_discovery_pack', 'total_amount'}
        for key, val in order_dict.items():
            if key in _int_keys:
                order_data[key] = val if val is not None else 0
            else:
                order_data[key] = val if val is not None else ''

        # Add computed/display fields on top of raw DB columns
        order_data['order_number'] = display_order_number
        order_data['amount_display'] = f"£{total / 100:.2f}"
        order_data['items'] = items
        # Ensure customer_name falls back to shipping_name
        if not order_data.get('customer_name'):
            order_data['customer_name'] = order_data.get('shipping_name', '')
        # Ensure fulfilment_status has a default
        if not order_data.get('fulfilment_status'):
            order_data['fulfilment_status'] = 'pending'

        return jsonify({
            'success': True,
            'order': order_data
        })

    except Exception as e:
        print(f"Error getting order details: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@orders_bp.route('/api/update-order', methods=['POST'])
def api_update_order():
    """Update order details"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        data = request.get_json()
        order_id = data.get('order_id')

        if not order_id:
            return jsonify({'success': False, 'error': 'Order ID required'}), 400

        conn = _get_merchandise_conn()
        if not conn:
            return jsonify({'success': False, 'error': 'Database not configured'}), 500

        cursor = conn.cursor()

        # Verify order exists
        cursor.execute('SELECT id FROM orders WHERE id = ?', (order_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Order not found'}), 404

        # Get available columns so we only update columns that exist
        cursor.execute("PRAGMA table_info(orders)")
        available_columns = {col[1] for col in cursor.fetchall()}

        update_fields = []
        values = []

        # Fields that should never be updated via this endpoint
        _protected = {'id', 'order_id', 'created_at'}
        # Integer columns that need type coercion
        _int_columns = {'total_amount', 'shipping_cost', 'vegan_discovery_pack'}

        # Accept any field the client sends, as long as it exists in the DB
        # and is not protected. This allows apps with custom columns
        # (order_type, subscription_id, etc.) to update without framework changes.
        for field, val in data.items():
            if field in _protected or field not in available_columns:
                continue
            update_fields.append(f'{field} = ?')
            if field in _int_columns and val is not None:
                val = int(val)
            values.append(val if val else None)

        if not update_fields:
            conn.close()
            return jsonify({'success': False, 'error': 'No fields to update'}), 400

        update_fields.append('updated_at = CURRENT_TIMESTAMP')
        values.append(order_id)

        query = f"UPDATE orders SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(query, values)

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'Order {order_id} updated successfully'
        })

    except Exception as e:
        print(f"Error updating order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@orders_bp.route('/api/delete-order', methods=['POST'])
def api_delete_order():
    """Delete an order and its items"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        data = request.get_json()
        order_id = data.get('order_id')

        if not order_id:
            return jsonify({'success': False, 'error': 'Order ID required'}), 400

        conn = _get_merchandise_conn()
        if not conn:
            return jsonify({'success': False, 'error': 'Database not configured'}), 500

        cursor = conn.cursor()

        # Verify order exists
        cursor.execute('SELECT id FROM orders WHERE id = ?', (order_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Order not found'}), 404

        # Delete order items first (foreign key constraint)
        cursor.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
        deleted_items = cursor.rowcount

        # Delete the order
        cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        deleted_order = cursor.rowcount

        conn.commit()
        conn.close()

        if deleted_order > 0:
            return jsonify({
                'success': True,
                'message': f'Order {order_id} deleted successfully (removed {deleted_items} items)'
            })
        else:
            return jsonify({'success': False, 'error': 'Order could not be deleted'}), 500

    except Exception as e:
        print(f"Error deleting order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@orders_bp.route('/api/products')
def api_products():
    """List available products for adding to orders"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        conn = _get_merchandise_conn()
        if not conn:
            return jsonify({'success': True, 'products': []})

        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, price FROM products
            WHERE is_active = 1 AND name IS NOT NULL AND name != ''
            ORDER BY name
        ''')
        product_list = []
        for row in cursor.fetchall():
            pid, pname, pprice = row[0], row[1], row[2] or 0
            product_list.append({
                'id': pid,
                'name': pname,
                'price': pprice,
                'price_display': f"£{pprice / 100:.2f}"
            })
        conn.close()

        return jsonify({
            'success': True,
            'products': product_list
        })

    except Exception as e:
        print(f"Error listing products: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@orders_bp.route('/api/create-order', methods=['POST'])
def api_create_order():
    """Create a new order manually"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        data = request.get_json()

        customer_name = data.get('customer_name')
        customer_email = data.get('customer_email')
        total_amount = data.get('total_amount', 0)
        status = data.get('status', 'paid')
        shipping_address = data.get('shipping_address', '')

        if not customer_email:
            return jsonify({'success': False, 'error': 'Customer email required'}), 400

        conn = _get_merchandise_conn()
        if not conn:
            return jsonify({'success': False, 'error': 'Database not configured'}), 500
        cursor = conn.cursor()

        # Parse shipping address into fields (simple split by newline)
        address_lines = shipping_address.split('\n') if shipping_address else []
        shipping_line1 = address_lines[0] if len(address_lines) > 0 else ''
        shipping_line2 = address_lines[1] if len(address_lines) > 1 else ''
        shipping_city = address_lines[2] if len(address_lines) > 2 else ''
        shipping_postal = address_lines[3] if len(address_lines) > 3 else ''
        shipping_country = address_lines[4] if len(address_lines) > 4 else ''

        cursor.execute('''
            INSERT INTO orders (customer_email, customer_name, total_amount, status,
                               shipping_name, shipping_line1, shipping_line2, shipping_city,
                               shipping_postal_code, shipping_country)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (customer_email, customer_name, total_amount, status,
              customer_name, shipping_line1, shipping_line2, shipping_city,
              shipping_postal, shipping_country))

        order_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'order_id': order_id,
            'message': f'Order created successfully'
        })

    except Exception as e:
        print(f"Error creating order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@orders_bp.route('/api/add-order-item', methods=['POST'])
def api_add_order_item():
    """Add an item to an existing order"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        data = request.get_json()

        order_id = data.get('order_id')
        product_id = data.get('product_id')
        quantity = data.get('quantity', 1)
        size = data.get('size')
        color = data.get('color')

        if not order_id or not product_id:
            return jsonify({'success': False, 'error': 'Order ID and Product ID required'}), 400

        conn = _get_merchandise_conn()
        if not conn:
            return jsonify({'success': False, 'error': 'Database not configured'}), 500
        cursor = conn.cursor()

        # Get product price
        cursor.execute('SELECT price FROM products WHERE id = ?', (product_id,))
        prod_row = cursor.fetchone()
        if not prod_row:
            conn.close()
            return jsonify({'success': False, 'error': 'Product not found'}), 404

        price_at_time = prod_row[0]

        # Check if order_items has size/color columns
        cursor.execute("PRAGMA table_info(order_items)")
        oi_columns = {col[1] for col in cursor.fetchall()}
        has_size = 'size' in oi_columns
        has_color = 'color' in oi_columns

        # Insert order item
        if has_size and has_color:
            cursor.execute('''
                INSERT INTO order_items (order_id, product_id, quantity, price_at_time, size, color)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (order_id, product_id, quantity, price_at_time, size, color))
        else:
            cursor.execute('''
                INSERT INTO order_items (order_id, product_id, quantity, price_at_time)
                VALUES (?, ?, ?, ?)
            ''', (order_id, product_id, quantity, price_at_time))

        # Update order total
        cursor.execute('''
            UPDATE orders SET total_amount = (
                SELECT COALESCE(SUM(price_at_time * quantity), 0)
                FROM order_items WHERE order_id = ?
            ), updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (order_id, order_id))

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Item added successfully'
        })

    except Exception as e:
        print(f"Error adding order item: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@orders_bp.route('/api/update-order-item', methods=['POST'])
def api_update_order_item():
    """Update an order item"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        data = request.get_json()

        item_id = data.get('item_id')
        order_id = data.get('order_id')
        quantity = data.get('quantity')
        size = data.get('size')
        color = data.get('color')
        price_at_time = data.get('price_at_time')

        if not item_id:
            return jsonify({'success': False, 'error': 'Item ID required'}), 400

        conn = _get_merchandise_conn()
        if not conn:
            return jsonify({'success': False, 'error': 'Database not configured'}), 500
        cursor = conn.cursor()

        # Check available columns
        cursor.execute("PRAGMA table_info(order_items)")
        oi_columns = {col[1] for col in cursor.fetchall()}
        has_size = 'size' in oi_columns
        has_color = 'color' in oi_columns

        # Update the item
        if has_size and has_color:
            cursor.execute('''
                UPDATE order_items
                SET quantity = ?, size = ?, color = ?, price_at_time = ?
                WHERE id = ?
            ''', (quantity, size, color, price_at_time, item_id))
        else:
            cursor.execute('''
                UPDATE order_items
                SET quantity = ?, price_at_time = ?
                WHERE id = ?
            ''', (quantity, price_at_time, item_id))

        # Update order total
        if order_id:
            cursor.execute('''
                UPDATE orders SET total_amount = (
                    SELECT COALESCE(SUM(price_at_time * quantity), 0)
                    FROM order_items WHERE order_id = ?
                ), updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (order_id, order_id))

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Item updated successfully'
        })

    except Exception as e:
        print(f"Error updating order item: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@orders_bp.route('/api/delete-order-item', methods=['POST'])
def api_delete_order_item():
    """Delete an order item"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        data = request.get_json()

        item_id = data.get('item_id')
        order_id = data.get('order_id')

        if not item_id:
            return jsonify({'success': False, 'error': 'Item ID required'}), 400

        conn = _get_merchandise_conn()
        if not conn:
            return jsonify({'success': False, 'error': 'Database not configured'}), 500
        cursor = conn.cursor()

        # Delete the item
        cursor.execute('DELETE FROM order_items WHERE id = ?', (item_id,))

        # Update order total
        if order_id:
            cursor.execute('''
                UPDATE orders SET total_amount = (
                    SELECT COALESCE(SUM(price_at_time * quantity), 0)
                    FROM order_items WHERE order_id = ?
                ), updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (order_id, order_id))

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Item deleted successfully'
        })

    except Exception as e:
        print(f"Error deleting order item: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@orders_bp.route('/api/resend-confirmation', methods=['POST'])
def api_resend_confirmation():
    """Resend order confirmation email"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        data = request.get_json()
        order_id = data.get('order_id')

        if not order_id:
            return jsonify({'success': False, 'error': 'Order ID required'}), 400

        conn = _get_merchandise_conn()
        if not conn:
            return jsonify({'success': False, 'error': 'Database not configured'}), 500
        cursor = conn.cursor()
        cursor.execute('SELECT customer_email FROM orders WHERE id = ?', (order_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return jsonify({'success': False, 'error': 'Order not found'}), 404

        customer_email = row[0]
        if not customer_email or customer_email == 'pending':
            return jsonify({'success': False, 'error': 'Order has no customer email'}), 400

        # Try Mario Pinto email pattern first, then fall back to lozzalingo email service
        try:
            from email_service import EmailService
            from app.models.merchandise import Order, OrderItem, Product

            order = Order.get_by_id(order_id)
            order_items = OrderItem.get_by_order_id(order_id)

            email_items = []
            for item in order_items:
                product = Product.get_by_id(item.product_id)
                email_items.append({
                    'name': product.name if product else 'Unknown Product',
                    'size': item.size or 'N/A',
                    'color': item.color or 'N/A',
                    'quantity': item.quantity or 1,
                    'price': item.price_at_time or 0
                })

            email_sent = EmailService.send_clothing_order_confirmation(
                to_email=order.customer_email,
                order_id=order.id,
                items=email_items,
                total_amount=order.total_amount or 0,
                shipping_info={'country': order.shipping_country or 'GB', 'cost': 0}
            )

            if email_sent:
                return jsonify({'success': True, 'message': f'Confirmation email sent to {customer_email}'})
            else:
                return jsonify({'success': False, 'error': 'Email service returned failure'}), 500

        except ImportError:
            # Fallback: use lozzalingo email service directly
            try:
                from lozzalingo.modules.email.email_service import email_service
                email_service.send_email(
                    [customer_email],
                    'Order Confirmation (resent)',
                    f'<p>This is a resend of your order confirmation for order #{order_id}.</p>'
                )
                return jsonify({'success': True, 'message': f'Confirmation email sent to {customer_email}'})
            except Exception as e:
                print(f"Email error: {e}")
                return jsonify({'success': False, 'error': f'Email service not configured: {str(e)}'}), 500

        except Exception as e:
            print(f"Email error: {e}")
            return jsonify({'success': False, 'error': f'Failed to send email: {str(e)}'}), 500

    except Exception as e:
        print(f"Error resending confirmation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# INTEGRATION: InkThreadable fulfillment is optional. If lozzalingo.modules.inkthreadable
# is not installed, these endpoints return a 500 with a clear error -- they do NOT crash.
@orders_bp.route('/api/resend-to-inkthreadable', methods=['POST'])
def api_resend_to_inkthreadable():
    """Resend order to InkThreadable for fulfillment"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        from app.models.merchandise import Order, get_merchandise_db

        data = request.get_json()
        order_id = data.get('order_id')

        if not order_id:
            return jsonify({'success': False, 'error': 'Order ID required'}), 400

        order = Order.get_by_id(order_id)
        if not order:
            return jsonify({'success': False, 'error': 'Order not found'}), 404

        # Try to send to InkThreadable using framework service
        try:
            from lozzalingo.modules.inkthreadable import inkthreadable_service
            from app.models.merchandise import OrderItem

            # Create order via the service
            result = inkthreadable_service.create_order(
                order_id=order_id,
                get_order_func=Order.get_by_id,
                get_order_items_func=OrderItem.get_by_order_id,
                get_db_func=get_merchandise_db
            )

            if result:
                # Extract InkThreadable ID from response
                order_data = result.get('order', {})
                inkthreadable_id = order_data.get('id')
                status = order_data.get('status', 'Submitted')

                return jsonify({
                    'success': True,
                    'message': f'Order sent to InkThreadable (ID: {inkthreadable_id})',
                    'inkthreadable_id': inkthreadable_id,
                    'status': status
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to send order to InkThreadable'
                }), 500

        except ImportError as e:
            return jsonify({
                'success': False,
                'error': f'InkThreadable integration not configured: {str(e)}'
            }), 500
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Failed to send to InkThreadable: {str(e)}'
            }), 500

    except Exception as e:
        print(f"Error resending to InkThreadable: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@orders_bp.route('/api/check-shipping-status', methods=['POST'])
def api_check_shipping_status():
    """Check and update shipping status from InkThreadable"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        from app.models.merchandise import Order, get_merchandise_db

        data = request.get_json()
        order_id = data.get('order_id')

        if not order_id:
            return jsonify({'success': False, 'error': 'Order ID required'}), 400

        order = Order.get_by_id(order_id)
        if not order:
            return jsonify({'success': False, 'error': 'Order not found'}), 404

        inkthreadable_id = getattr(order, 'inkthreadable_id', None)
        if not inkthreadable_id:
            # Not an error - order just hasn't been sent to InkThreadable yet
            return jsonify({
                'success': True,
                'message': 'Order not yet sent to fulfillment',
                'status': 'pending_fulfillment'
            })

        # Try to check status from InkThreadable
        try:
            from lozzalingo.modules.inkthreadable import inkthreadable_service
            api_response = inkthreadable_service.get_order_status(inkthreadable_id)

            if api_response:
                # Extract order info from API response
                order_info = api_response.get('order', {})
                shipping_info = order_info.get('shipping', {})

                # Update order with new status info
                conn = get_merchandise_db()
                cursor = conn.cursor()

                updates = []
                values = []

                status = order_info.get('status')
                if status:
                    updates.append('inkthreadable_status = ?')
                    values.append(status)

                carrier = shipping_info.get('shippingMethod')
                if carrier:
                    updates.append('carrier = ?')
                    values.append(carrier)

                tracking_number = shipping_info.get('trackingNumber')
                if tracking_number:
                    updates.append('tracking_number = ?')
                    values.append(tracking_number)

                shipped_at = shipping_info.get('shipped_at')
                if shipped_at:
                    updates.append('shipped_at = ?')
                    values.append(shipped_at)

                if updates:
                    updates.append('updated_at = CURRENT_TIMESTAMP')
                    values.append(order_id)
                    query = f"UPDATE orders SET {', '.join(updates)} WHERE id = ?"
                    cursor.execute(query, values)
                    conn.commit()

                conn.close()

                return jsonify({
                    'success': True,
                    'status': status,
                    'message': f"Shipping status updated: {status or 'Unknown'}"
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Could not retrieve status from InkThreadable'
                }), 500

        except ImportError:
            return jsonify({
                'success': False,
                'error': 'InkThreadable integration not configured'
            }), 500
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Failed to check shipping status: {str(e)}'
            }), 500

    except Exception as e:
        print(f"Error checking shipping status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@orders_bp.route('/api/fetch-etsy-orders', methods=['POST'])
def api_fetch_etsy_orders():
    """Trigger Make.com to fetch Etsy orders for a shop"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        data = request.get_json() or {}
        shop_name = data.get('shop_name')

        if not shop_name:
            return jsonify({'success': False, 'error': 'shop_name required'}), 400

        # Import from main app
        try:
            from utils.etsy_orders import fetch_etsy_orders, ETSY_SHOPS
        except ImportError:
            return jsonify({
                'success': False,
                'error': 'Etsy orders module not configured'
            }), 500

        if shop_name not in ETSY_SHOPS:
            return jsonify({
                'success': False,
                'error': f'Invalid shop. Valid shops: {ETSY_SHOPS}'
            }), 400

        result = fetch_etsy_orders(shop_name)

        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 500

    except Exception as e:
        print(f"Error fetching Etsy orders: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@orders_bp.route('/api/send-etsy-shipping-update', methods=['POST'])
def api_send_etsy_shipping_update():
    """Send shipping update to Etsy via Make.com webhook"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        import os
        from dotenv import load_dotenv
        load_dotenv(override=True)

        data = request.get_json() or {}
        order_id = data.get('order_id')
        receipt_id = data.get('receipt_id')

        if not order_id and not receipt_id:
            return jsonify({'success': False, 'error': 'order_id or receipt_id required'}), 400

        # Get webhook URL and callback URL
        webhook_url = os.getenv('MAKE_ORDER_WEBHOOK_URL')
        if not webhook_url:
            return jsonify({'success': False, 'error': 'MAKE_ORDER_WEBHOOK_URL not configured'}), 500

        # Determine callback URL
        environment = os.getenv('ENVIRONMENT', 'development')
        if environment == 'production' or os.getenv('USE_NGROK', 'true').lower() == 'false':
            callback_url = os.getenv('PRODUCTION_BASE_URL')
        else:
            callback_url = os.getenv('NGROK_TUNNEL_URL')

        if not callback_url:
            return jsonify({'success': False, 'error': 'Could not determine callback URL'}), 500

        # Get order data from merchandise.db
        from app.models.merchandise import Order, Product, get_merchandise_db
        from db_schema import DB

        import sqlite3

        # Get order from merchandise.db
        if order_id:
            order = Order.get_by_id(order_id)
        else:
            # Find order by receipt_id
            conn = get_merchandise_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM orders WHERE receipt_id = ?", (str(receipt_id),))
            row = cursor.fetchone()
            conn.close()
            if row:
                order = Order.get_by_id(row[0])
            else:
                order = None

        if not order:
            return jsonify({'success': False, 'error': 'Order not found'}), 404

        receipt_id = getattr(order, 'receipt_id', None)
        carrier = getattr(order, 'carrier', None)
        tracking_number = getattr(order, 'tracking_number', None)
        shipped_at = getattr(order, 'shipped_at', None)
        inkthreadable_id = getattr(order, 'inkthreadable_id', None)
        product_id = getattr(order, 'product_id', None)

        if not shipped_at:
            return jsonify({'success': False, 'error': 'Order has not been shipped yet'}), 400

        # Get sku and shop - first from the order itself, then fall back to product
        sku = getattr(order, 'sku', None)
        shop = getattr(order, 'shop', None) or getattr(order, 'shop_name', None)
        if not sku or not shop:
            if product_id:
                product = Product.get_by_id(product_id)
                if product:
                    sku = sku or getattr(product, 'sku', None)
                    shop = shop or getattr(product, 'shop_name', None)

        # Get listing_id - first from order, then fall back to partners table
        listing_id = getattr(order, 'listing_id', None)
        if not listing_id:
            try:
                partners_db = DB.MERCHANDISE if hasattr(DB, 'MERCHANDISE') else (DB.DESIGN_ENGINE if hasattr(DB, 'DESIGN_ENGINE') else 'databases/design_engine.db')
                partners_conn = sqlite3.connect(partners_db)
                partners_cursor = partners_conn.cursor()
                partners_cursor.execute("SELECT listing_id FROM partners WHERE id = ?", (product_id,))
                partner_row = partners_cursor.fetchone()
                partners_conn.close()
                if partner_row:
                    listing_id = partner_row[0]
            except Exception as e:
                print(f"Warning: Could not get listing_id from partners table: {e}")

        # Send shipping update
        from lozzalingo.modules.inkthreadable import inkthreadable_service

        order_data = {
            'receipt_id': receipt_id,
            'sku': sku,
            'listing_id': listing_id,
            'shop': shop,
            'carrier': carrier,
            'tracking_number': tracking_number,
            'shipped_at': shipped_at,
            'inkthreadable_id': inkthreadable_id
        }

        result = inkthreadable_service.send_etsy_shipping_update(order_data, webhook_url, callback_url)

        if result.get('success'):
            # Mark as updated in orders table (merchandise.db)
            conn = get_merchandise_db()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE orders
                SET shipping_updated = CURRENT_TIMESTAMP
                WHERE receipt_id = ?
            """, (str(receipt_id),))
            conn.commit()
            conn.close()

            return jsonify(result), 200
        else:
            return jsonify(result), 500

    except Exception as e:
        print(f"Error sending Etsy shipping update: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Public API: /api/recent-sales
# =============================================================================
# API key protected endpoint for live ticker feeds.
# Returns the 5 most recent paid orders with product titles.
#
# Config:
#   TICKER_API_KEY (env var) - shared secret for X-Ticker-Key header
#   TICKER_BRAND_NAME (app config) - falls back to EMAIL_BRAND_NAME or brand_name
#   SITE_URL (app config) - public URL for the app
#   TICKER_EXCLUDE_EMAILS (app config) - list of emails to filter out (test purchases)
#
# Response:
#   {"sales": [{"title": "Brand - Product", "url": "...", "date": "YYYY-MM-DD", "type": "purchase"}]}
# =============================================================================

# Default test emails to exclude from ticker
_DEFAULT_EXCLUDE_EMAILS = [
    'laurencestephan@hotmail.com',
    'laurencedotcomputer@gmail.com',
]


@orders_public_bp.route('/recent-sales')
def recent_sales():
    """Return the 5 most recent paid orders for live ticker feeds.

    Protected by X-Ticker-Key header matching TICKER_API_KEY env var.
    """
    # Auth: check X-Ticker-Key header against TICKER_API_KEY env var
    expected_key = os.getenv('TICKER_API_KEY')
    if not expected_key:
        return jsonify({'error': 'Ticker API not configured'}), 503

    provided_key = request.headers.get('X-Ticker-Key', '')
    if provided_key != expected_key:
        return jsonify({'error': 'Unauthorised'}), 401

    # Resolve brand name and site URL from app config
    brand_name = (
        current_app.config.get('TICKER_BRAND_NAME')
        or current_app.config.get('EMAIL_BRAND_NAME')
        or current_app.config.get('brand_name', 'Unknown')
    )
    site_url = current_app.config.get('SITE_URL', '')

    # Emails to exclude (test purchases)
    exclude_emails = current_app.config.get('TICKER_EXCLUDE_EMAILS', _DEFAULT_EXCLUDE_EMAILS)

    try:
        conn = _get_merchandise_conn()
        if not conn:
            return jsonify({'sales': []})

        cursor = conn.cursor()

        # Check which columns exist in the orders table
        cursor.execute("PRAGMA table_info(orders)")
        available_cols = {col[1] for col in cursor.fetchall()}

        # Build exclusion filter for test emails
        if exclude_emails:
            placeholders = ', '.join('?' for _ in exclude_emails)
            email_filter = f"AND customer_email NOT IN ({placeholders})"
            params = list(exclude_emails)
        else:
            email_filter = ''
            params = []

        # Query for recent paid/completed orders
        # Accept common status values across different host app schemas
        status_filter = "status IN ('paid', 'succeeded', 'completed')"

        # Check for order_type column (coffee-goblin uses 'subscription', 'coffee' etc.)
        has_order_type = 'order_type' in available_cols

        order_type_col = ', order_type' if has_order_type else ''

        cursor.execute(f'''
            SELECT id, customer_email, total_amount, created_at{order_type_col}
            FROM orders
            WHERE {status_filter}
            {email_filter}
            ORDER BY created_at DESC
            LIMIT 5
        ''', params)

        col_names = [desc[0] for desc in cursor.description]
        rows = [dict(zip(col_names, row)) for row in cursor.fetchall()]

        # Check if order_items table exists
        has_order_items = False
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='order_items'")
            has_order_items = cursor.fetchone() is not None
        except Exception:
            pass

        sales = []
        for row in rows:
            order_id = row.get('id')
            created_at = row.get('created_at', '')

            # Get product names from order_items
            product_names = []
            if has_order_items:
                try:
                    cursor.execute('''
                        SELECT p.name
                        FROM order_items oi
                        LEFT JOIN products p ON oi.product_id = p.id
                        WHERE oi.order_id = ?
                    ''', (order_id,))
                    product_names = [r[0] for r in cursor.fetchall() if r[0]]
                except Exception:
                    pass

            # Build title: "Brand - Product1, Product2" or just "Brand" if no products
            if product_names:
                title = f"{brand_name} - {', '.join(product_names)}"
            else:
                title = brand_name

            # Determine sale type from order_type column if available
            sale_type = 'purchase'
            if has_order_type:
                order_type_val = (row.get('order_type') or '').lower()
                if order_type_val in ('coffee', 'donation', 'tip'):
                    sale_type = 'coffee'
                elif order_type_val in ('subscription', 'recurring'):
                    sale_type = 'subscription'

            # Parse date to YYYY-MM-DD
            date_str = ''
            if created_at:
                try:
                    date_str = str(created_at)[:10]
                except Exception:
                    date_str = ''

            sales.append({
                'title': title,
                'url': site_url,
                'date': date_str,
                'type': sale_type,
            })

        conn.close()
        return jsonify({'sales': sales})

    except Exception as e:
        try:
            from lozzalingo.core import db_log
            db_log('error', 'orders', 'Error in recent-sales API', {'error': str(e)})
        except Exception:
            pass
        return jsonify({'sales': [], 'error': 'Internal error'}), 500
