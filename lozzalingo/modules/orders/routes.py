"""
Orders Admin Routes
===================

Extracted from Mario Pinto project.
Made framework-ready with optional imports.
"""

from flask import render_template, request, redirect, url_for, session, jsonify
from . import orders_bp

@orders_bp.route('/')
def orders_manager():
    """Order management page"""
    if 'admin_id' not in session:
        return redirect(url_for('admin.login', next=request.path))

    return render_template('orders/orders_manager.html')

@orders_bp.route('/api/orders')
def api_orders():
    """List recent orders for admin"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        # Get database connection (framework-ready)
        try:
            from config import Config
            merchandise_db = Config.MERCHANDISE_DB if hasattr(Config, 'MERCHANDISE_DB') else None
            items_db = Config.ITEMS_DB if hasattr(Config, 'ITEMS_DB') else None
        except ImportError:
            import os
            merchandise_db = os.getenv('MERCHANDISE_DB', 'merchandise.db')
            items_db = os.getenv('ITEMS_DB', 'clothing_items.db')

        if not merchandise_db:
            # No merchandise database configured - return empty list
            return jsonify({'success': True, 'orders': [], 'message': 'Merchandise database not configured'})

        # Try to import Order models
        try:
            from app.models.merchandise import get_merchandise_db, Order, OrderItem, Product
        except ImportError:
            # No merchandise models available - return empty list
            return jsonify({'success': True, 'orders': [], 'message': 'Order models not configured'})

        # Get recent orders (last 50)
        conn = get_merchandise_db()
        cursor = conn.cursor()

        # Detect available columns to handle schema differences across projects
        cursor.execute("PRAGMA table_info(orders)")
        available_columns = {col[1] for col in cursor.fetchall()}

        has_receipt_id = 'receipt_id' in available_columns
        has_product_id = 'product_id' in available_columns

        select_cols = ['id']
        if has_receipt_id:
            select_cols.append('receipt_id')
        select_cols += [
            'stripe_session_id', 'customer_email', 'customer_name',
            'total_amount', 'status', 'created_at',
            'shipping_name', 'shipping_line1', 'shipping_line2', 'shipping_city',
            'shipping_state', 'shipping_postal_code', 'shipping_country'
        ]

        cursor.execute(f'''
            SELECT {', '.join(select_cols)}
            FROM orders
            ORDER BY id DESC
            LIMIT 50
        ''')

        orders = []
        for row in cursor.fetchall():
            idx = 0
            order_id = row[idx]; idx += 1
            receipt_id = row[idx] if has_receipt_id else None
            if has_receipt_id:
                idx += 1
            session_id = row[idx]; idx += 1
            email = row[idx]; idx += 1
            name = row[idx]; idx += 1
            amount = row[idx]; idx += 1
            status = row[idx]; idx += 1
            created_at = row[idx]; idx += 1
            ship_name = row[idx]; idx += 1
            ship_line1 = row[idx]; idx += 1
            ship_line2 = row[idx]; idx += 1
            ship_city = row[idx]; idx += 1
            ship_state = row[idx]; idx += 1
            ship_postal = row[idx]; idx += 1
            ship_country = row[idx]; idx += 1

            # Format shipping address for display
            shipping_parts = [
                ship_line1,
                ship_line2,
                ship_city,
                ship_state,
                ship_postal,
                ship_country
            ]
            shipping = '\n'.join(part for part in shipping_parts if part)

            # Get order items for this order
            order_items = OrderItem.get_by_order_id(order_id)
            product_names = []
            shop_name = None

            for item in order_items:
                product = Product.get_by_id(item.product_id)
                if product:
                    item_name = f"{product.name}"
                    if item.size:
                        item_name += f" ({item.size})"
                    if item.quantity > 1:
                        item_name += f" x{item.quantity}"
                    product_names.append(item_name)
                    # Get shop_name from product if this is an Etsy order
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
                        shop_name = getattr(product, 'shop_name', None)

            orders.append({
                'id': order_id,
                'order_number': f"ORD-{str(order_id).zfill(6)}",
                'receipt_id': receipt_id,
                'session_id': session_id,
                'customer_email': email,
                'customer_name': name,
                'total_amount': amount,
                'amount_display': f"£{amount / 100:.2f}" if amount else "£0.00",
                'status': status,
                'created_at': created_at,
                'products': ", ".join(product_names) if product_names else "Unknown",
                'shop': shop_name
            })

        conn.close()

        return jsonify({
            'success': True,
            'orders': orders
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
        # Try to import Order models
        try:
            from app.models.merchandise import Order, OrderItem, Product
        except ImportError:
            return jsonify({'success': False, 'error': 'Order models not available'}), 500

        order = Order.get_by_id(order_id)
        if not order:
            return jsonify({'success': False, 'error': 'Order not found'}), 404

        # Get order items
        order_items = OrderItem.get_by_order_id(order_id)
        items = []

        for item in order_items:
            product = Product.get_by_id(item.product_id)
            if product:
                items.append({
                    'id': item.id,
                    'product_id': item.product_id,
                    'product_name': product.name,
                    'quantity': item.quantity,
                    'size': item.size,
                    'color': item.color,
                    'price_at_time': item.price_at_time,
                    'subtotal': item.price_at_time * item.quantity
                })

        order_data = {
            'id': order.id,
            'order_number': f"ORD-{str(order.id).zfill(6)}",
            'stripe_session_id': order.stripe_session_id,
            'customer_email': order.customer_email,
            'customer_name': order.customer_name,
            'total_amount': order.total_amount,
            'amount_display': f"£{order.total_amount / 100:.2f}",
            'status': order.status,
            'created_at': order.created_at,
            'items': items,
            # Shipping address fields
            'shipping_name': order.shipping_name or '',
            'shipping_line1': order.shipping_line1 or '',
            'shipping_line2': order.shipping_line2 or '',
            'shipping_city': order.shipping_city or '',
            'shipping_state': order.shipping_state or '',
            'shipping_postal_code': order.shipping_postal_code or '',
            'shipping_country': order.shipping_country or '',
            # Fulfillment tracking info (InkThreadable)
            'inkthreadable_id': getattr(order, 'inkthreadable_id', '') or '',
            'inkthreadable_status': getattr(order, 'inkthreadable_status', '') or '',
            'carrier': getattr(order, 'carrier', '') or '',
            'tracking_number': getattr(order, 'tracking_number', '') or '',
            'shipped_at': getattr(order, 'shipped_at', '') or ''
        }

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
        from app.models.merchandise import get_merchandise_db, Order

        data = request.get_json()
        order_id = data.get('order_id')

        if not order_id:
            return jsonify({'success': False, 'error': 'Order ID required'}), 400

        # Get the order to verify it exists
        order = Order.get_by_id(order_id)
        if not order:
            return jsonify({'success': False, 'error': 'Order not found'}), 404

        # Update fields
        conn = get_merchandise_db()
        cursor = conn.cursor()

        update_fields = []
        values = []

        # Customer fields
        if 'customer_name' in data:
            update_fields.append('customer_name = ?')
            values.append(data['customer_name'])
        if 'customer_email' in data:
            update_fields.append('customer_email = ?')
            values.append(data['customer_email'])

        # Shipping fields
        for field in ['shipping_name', 'shipping_line1', 'shipping_line2',
                      'shipping_city', 'shipping_state', 'shipping_postal_code', 'shipping_country']:
            if field in data:
                update_fields.append(f'{field} = ?')
                values.append(data[field])

        # Order fields
        if 'status' in data:
            update_fields.append('status = ?')
            values.append(data['status'])
        if 'total_amount' in data:
            update_fields.append('total_amount = ?')
            values.append(int(data['total_amount']))

        # InkThreadable / Fulfillment fields
        for field in ['inkthreadable_id', 'inkthreadable_status', 'carrier', 'tracking_number', 'shipped_at']:
            if field in data:
                update_fields.append(f'{field} = ?')
                values.append(data[field] if data[field] else None)

        if not update_fields:
            return jsonify({'success': False, 'error': 'No fields to update'}), 400

        # Add updated timestamp
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
        from app.models.merchandise import get_merchandise_db, Order

        data = request.get_json()
        order_id = data.get('order_id')

        if not order_id:
            return jsonify({'success': False, 'error': 'Order ID required'}), 400

        # Get the order to verify it exists
        order = Order.get_by_id(order_id)
        if not order:
            return jsonify({'success': False, 'error': 'Order not found'}), 404

        # Delete order and related data
        conn = get_merchandise_db()
        cursor = conn.cursor()

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
        from app.models.merchandise import Product

        products = Product.get_all_active()
        product_list = [{
            'id': p.id,
            'name': p.name,
            'price': p.price,
            'price_display': f"£{p.price / 100:.2f}"
        } for p in products]

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
        from app.models.merchandise import get_merchandise_db

        data = request.get_json()

        customer_name = data.get('customer_name')
        customer_email = data.get('customer_email')
        total_amount = data.get('total_amount', 0)
        status = data.get('status', 'paid')
        shipping_address = data.get('shipping_address', '')

        if not customer_email:
            return jsonify({'success': False, 'error': 'Customer email required'}), 400

        conn = get_merchandise_db()
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
        from app.models.merchandise import get_merchandise_db, Product

        data = request.get_json()

        order_id = data.get('order_id')
        product_id = data.get('product_id')
        quantity = data.get('quantity', 1)
        size = data.get('size')
        color = data.get('color')

        if not order_id or not product_id:
            return jsonify({'success': False, 'error': 'Order ID and Product ID required'}), 400

        # Get product price
        product = Product.get_by_id(product_id)
        if not product:
            return jsonify({'success': False, 'error': 'Product not found'}), 404

        price_at_time = product.price

        conn = get_merchandise_db()
        cursor = conn.cursor()

        # Insert order item
        cursor.execute('''
            INSERT INTO order_items (order_id, product_id, quantity, price_at_time, size, color)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (order_id, product_id, quantity, price_at_time, size, color))

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
        from app.models.merchandise import get_merchandise_db

        data = request.get_json()

        item_id = data.get('item_id')
        order_id = data.get('order_id')
        quantity = data.get('quantity')
        size = data.get('size')
        color = data.get('color')
        price_at_time = data.get('price_at_time')

        if not item_id:
            return jsonify({'success': False, 'error': 'Item ID required'}), 400

        conn = get_merchandise_db()
        cursor = conn.cursor()

        # Update the item
        cursor.execute('''
            UPDATE order_items
            SET quantity = ?, size = ?, color = ?, price_at_time = ?
            WHERE id = ?
        ''', (quantity, size, color, price_at_time, item_id))

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
        from app.models.merchandise import get_merchandise_db

        data = request.get_json()

        item_id = data.get('item_id')
        order_id = data.get('order_id')

        if not item_id:
            return jsonify({'success': False, 'error': 'Item ID required'}), 400

        conn = get_merchandise_db()
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
        from app.models.merchandise import Order, OrderItem, Product

        data = request.get_json()
        order_id = data.get('order_id')

        if not order_id:
            return jsonify({'success': False, 'error': 'Order ID required'}), 400

        order = Order.get_by_id(order_id)
        if not order:
            return jsonify({'success': False, 'error': 'Order not found'}), 404

        if not order.customer_email:
            return jsonify({'success': False, 'error': 'Order has no customer email'}), 400

        # Try to send confirmation email using crowd_sauced email service
        try:
            from email_service import EmailService

            # Get order items
            order_items = OrderItem.get_by_order_id(order_id)

            # Build email items list
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

            # Send confirmation email
            email_sent = EmailService.send_clothing_order_confirmation(
                to_email=order.customer_email,
                order_id=order.id,
                items=email_items,
                total_amount=order.total_amount or 0,
                shipping_info={'country': order.shipping_country or 'GB', 'cost': 0}
            )

            if email_sent:
                return jsonify({
                    'success': True,
                    'message': f'Confirmation email sent to {order.customer_email}'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Email service returned failure - check server logs for details'
                }), 500

        except ImportError as ie:
            print(f"Import error: {ie}")
            return jsonify({
                'success': False,
                'error': 'Email service not configured'
            }), 500
        except Exception as e:
            print(f"Email error: {e}")
            return jsonify({
                'success': False,
                'error': f'Failed to send email: {str(e)}'
            }), 500

    except Exception as e:
        print(f"Error resending confirmation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


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

        # Get product data (sku, shop_name) from merchandise.db
        sku = None
        shop = None
        if product_id:
            product = Product.get_by_id(product_id)
            if product:
                sku = getattr(product, 'sku', None)
                shop = getattr(product, 'shop_name', None)

        # Get listing_id - first from order, then fall back to partners table
        listing_id = getattr(order, 'listing_id', None)
        if not listing_id:
            try:
                partners_conn = sqlite3.connect(DB.DESIGN_ENGINE if hasattr(DB, 'DESIGN_ENGINE') else 'databases/design_engine.db')
                partners_cursor = partners_conn.cursor()
                partners_cursor.execute("SELECT listing_id FROM partners WHERE product_id = ?", (product_id,))
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
