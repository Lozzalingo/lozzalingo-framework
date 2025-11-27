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
        except ImportError:
            import os
            merchandise_db = os.getenv('MERCHANDISE_DB', 'merchandise.db')

        if not merchandise_db:
            return jsonify({'success': False, 'error': 'Merchandise database not configured'}), 500

        # Try to import Order models
        try:
            from app.models.merchandise import get_merchandise_db, Order, OrderItem, Product
        except ImportError:
            return jsonify({'success': False, 'error': 'Order models not available'}), 500

        # Get recent orders (last 50)
        conn = get_merchandise_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, stripe_session_id, customer_email, customer_name,
                   total_amount, status, created_at,
                   shipping_name, shipping_line1, shipping_line2, shipping_city,
                   shipping_state, shipping_postal_code, shipping_country
            FROM orders
            ORDER BY created_at DESC
            LIMIT 50
        ''')

        orders = []
        for row in cursor.fetchall():
            order_id, session_id, email, name, amount, status, created_at, \
            ship_name, ship_line1, ship_line2, ship_city, ship_state, ship_postal, ship_country = row

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

            for item in order_items:
                product = Product.get_by_id(item.product_id)
                if product:
                    item_name = f"{product.name}"
                    if item.size:
                        item_name += f" ({item.size})"
                    if item.quantity > 1:
                        item_name += f" x{item.quantity}"
                    product_names.append(item_name)

            orders.append({
                'id': order_id,
                'order_number': f"ORD-{str(order_id).zfill(6)}",
                'session_id': session_id,
                'customer_email': email,
                'customer_name': name,
                'total_amount': amount,
                'amount_display': f"£{amount / 100:.2f}",
                'status': status,
                'created_at': created_at,
                'products': ", ".join(product_names) if product_names else "Unknown"
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
            # Fulfillment tracking info
            'fulfillment_id': getattr(order, 'fulfillment_id', '') or '',
            'fulfillment_status': getattr(order, 'fulfillment_status', '') or '',
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
