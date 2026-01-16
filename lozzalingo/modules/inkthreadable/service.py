# lozzalingo/modules/inkthreadable/service.py
import os
import json
import hashlib
import requests
from datetime import datetime
from typing import Optional, Dict, Any, List
from urllib.parse import quote


class InkThreadableService:
    """Service for managing InkThreadable API integration"""

    def __init__(self, app_id: str = None, secret_key: str = None, brand_name: str = ""):
        self.app_id = app_id or os.getenv("INKTHREADABLE_APPID")
        self.secret_key = secret_key or os.getenv("INKTHREADABLE_SECRET_KEY")
        self.brand_name = brand_name

        # Design mappings - can be set per-brand
        self.design_mappings = {}
        self.back_design = None
        self.back_mockup = None

        # Default SKU prefix (Gildan 5000 Heavy Cotton black)
        self.default_sku_prefix = "GD05-BLK"

    def set_design_mappings(self, mappings: Dict[str, Dict[str, str]],
                           back_design: str = None, back_mockup: str = None):
        """
        Set design mappings for products

        Args:
            mappings: Dict mapping product name to {front_design, front_mockup}
            back_design: URL for back design (optional)
            back_mockup: URL for back mockup (optional)
        """
        self.design_mappings = mappings
        self.back_design = back_design
        self.back_mockup = back_mockup

    def get_shipping_address_from_order(self, order) -> Dict[str, str]:
        """Extract shipping address from Order object using structured fields"""
        # Split full name into first/last
        shipping_name = getattr(order, 'shipping_name', None) or getattr(order, 'customer_name', '') or ''
        name_parts = shipping_name.split(' ', 1)
        first_name = name_parts[0] if len(name_parts) > 0 else ''
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        return {
            'first_name': first_name,
            'last_name': last_name,
            'line1': getattr(order, 'shipping_line1', '') or '',
            'line2': getattr(order, 'shipping_line2', '') or '',
            'city': getattr(order, 'shipping_city', '') or '',
            'state': getattr(order, 'shipping_state', '') or '',
            'postal_code': getattr(order, 'shipping_postal_code', '') or '',
            'country': getattr(order, 'shipping_country', 'GB') or 'GB'
        }

    def get_product_sku(self, product_name: str = None, size: str = 'L',
                       sku_prefix: str = None, existing_sku: str = None) -> str:
        """
        Map product name and size to InkThreadable SKU

        Args:
            product_name: Name of the product (optional)
            size: Size (S, M, L, XL, etc.)
            sku_prefix: Custom SKU prefix (default: GD05-BLK)
            existing_sku: If provided, use this SKU directly
        """
        # If existing SKU is provided (e.g., from Etsy), use it directly
        if existing_sku:
            return existing_sku

        prefix = sku_prefix or self.default_sku_prefix
        size_normalized = (size or 'L').upper()

        # Map common size variations
        size_map = {
            'SMALL': 'S',
            'MEDIUM': 'M',
            'LARGE': 'L',
            'X-LARGE': 'XL',
            'XLARGE': 'XL',
            '2X-LARGE': '2XL',
            '2XLARGE': '2XL',
            '3X-LARGE': '3XL',
            '3XLARGE': '3XL'
        }

        final_size = size_map.get(size_normalized, size_normalized)
        return f"{prefix}-{final_size}"

    def create_order(self, order_id: int, get_order_func, get_order_items_func,
                    get_product_func=None, get_db_func=None,
                    external_id_prefix: str = "ORD") -> Optional[Dict[str, Any]]:
        """
        Create an InkThreadable order from a database order

        Args:
            order_id: The ID of the order in the database
            get_order_func: Function to get order by ID (returns Order object)
            get_order_items_func: Function to get order items by order ID
            get_product_func: Function to get product by ID (optional)
            get_db_func: Function to get database connection for updates
            external_id_prefix: Prefix for external order ID (default: ORD)

        Returns:
            Response data from InkThreadable API or None if failed
        """
        if not self.app_id or not self.secret_key:
            print("ERROR: InkThreadable credentials not configured")
            return None

        # Get order from database
        order = get_order_func(order_id)
        if not order:
            print(f"ERROR: Order {order_id} not found")
            return None

        # Get order items
        order_items = get_order_items_func(order_id)
        if not order_items:
            print(f"ERROR: No items found for order {order_id}")
            return None

        # Get structured shipping address from order
        address_parts = self.get_shipping_address_from_order(order)

        # Build items array for InkThreadable
        inkthreadable_items = []
        for item in order_items:
            item_data = self._build_item_payload(item, get_product_func)
            if item_data:
                inkthreadable_items.append(item_data)

        if not inkthreadable_items:
            print(f"ERROR: No valid items to send to InkThreadable for order {order_id}")
            return None

        # Build unique external_id
        existing_ink_id = getattr(order, 'inkthreadable_id', None)
        if existing_ink_id:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            external_id = f"{external_id_prefix}-{order_id}-retry-{timestamp}"
            print(f"Order {order_id} already has InkThreadable ID {existing_ink_id}")
            print(f"Creating new order with external_id: {external_id}")
        else:
            external_id = f"{external_id_prefix}-{order_id}"

        # Build payload
        payload = {
            "external_id": external_id,
            "brand": self.brand_name,
            "channel": "API",
            "buyer_email": getattr(order, 'customer_email', '') or getattr(order, 'email', ''),
            "shipping_address": {
                "firstName": address_parts.get('first_name', ''),
                "lastName": address_parts.get('last_name', ''),
                "company": "",
                "address1": address_parts.get('line1', ''),
                "address2": address_parts.get('line2', ''),
                "city": address_parts.get('city', ''),
                "county": address_parts.get('state', ''),
                "postcode": address_parts.get('postal_code', ''),
                "country": address_parts.get('country', 'GB'),
                "phone1": "",
                "phone2": "",
            },
            "items": inkthreadable_items,
            "shipping": {
                "shippingMethod": "UK Royal Mail 24 Tracked",
            },
            "comments": f"{self.brand_name} - Order #{order_id}"
        }

        # Convert to JSON
        payload_json = json.dumps(payload, separators=(',', ':'))

        # Generate signature
        signature_string = payload_json + self.secret_key
        signature = hashlib.sha1(signature_string.encode('utf-8')).hexdigest()

        # Make API request
        url = f"https://www.inkthreadable.co.uk/api/orders.php?AppId={self.app_id}&Signature={signature}"
        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(url, headers=headers, data=payload_json, timeout=30)

            print(f"InkThreadable API Status: {response.status_code}")

            if response.status_code in [200, 201]:
                response_data = response.json()
                print(f"InkThreadable Response: {response_data}")

                # Extract order info
                order_data = response_data.get("order", {})
                inkthreadable_id = order_data.get("id")
                status = order_data.get("status")

                # Update database if function provided
                if inkthreadable_id and get_db_func:
                    conn = get_db_func()
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE orders
                        SET inkthreadable_id = ?, inkthreadable_status = ?, updated_at = ?
                        WHERE id = ?
                    """, (inkthreadable_id, status, datetime.now().isoformat(), order_id))
                    conn.commit()
                    conn.close()

                    print(f"Order {order_id} sent to InkThreadable with ID: {inkthreadable_id}")

                return response_data
            else:
                print(f"ERROR: InkThreadable API returned {response.status_code}: {response.text}")
                return None

        except Exception as e:
            print(f"ERROR: Failed to send order to InkThreadable: {e}")
            return None

    def _build_item_payload(self, item, get_product_func=None) -> Optional[Dict[str, Any]]:
        """Build InkThreadable item payload from order item"""
        # Get product name - try different attributes
        product_name = None
        if get_product_func and hasattr(item, 'product_id'):
            product = get_product_func(item.product_id)
            if product:
                product_name = getattr(product, 'name', None)

        # Fallback to item title
        if not product_name:
            product_name = getattr(item, 'title', None) or getattr(item, 'product_name', 'Unknown')

        # Get SKU - use existing if available, otherwise generate
        existing_sku = getattr(item, 'sku', None)
        size = getattr(item, 'size', 'L')
        sku = self.get_product_sku(product_name, size, existing_sku=existing_sku)

        # Get quantity
        quantity = getattr(item, 'quantity', 1)
        if isinstance(quantity, str):
            quantity = int(quantity)

        # Get price
        price = getattr(item, 'price_at_time', None) or getattr(item, 'grand_total_amount', 0)
        if isinstance(price, str):
            price = int(price)
        retail_price = round(price / 100, 2) if price > 100 else price

        # Get design info
        design_info = self.design_mappings.get(product_name, {})
        front_design = design_info.get('front_design')
        front_mockup = design_info.get('front_mockup')

        # Build item
        item_payload = {
            "pn": sku,
            "quantity": quantity,
            "retailPrice": retail_price,
            "description": f"Please print using mockup image as reference",
            "label": {
                "type": "printed",
                "name": "ink-label"
            }
        }

        # Add designs if available
        if front_design or self.back_design:
            item_payload["designs"] = {}
            if front_design:
                item_payload["designs"]["front"] = front_design
            if self.back_design:
                item_payload["designs"]["back"] = self.back_design

        # Add mockups if available
        if front_mockup or self.back_mockup:
            item_payload["mockups"] = {}
            if front_mockup:
                item_payload["mockups"]["front"] = front_mockup
            if self.back_mockup:
                item_payload["mockups"]["back"] = self.back_mockup

        return item_payload

    def get_order_status(self, inkthreadable_id: str) -> Optional[Dict[str, Any]]:
        """Get order status from InkThreadable API"""
        if not self.app_id or not self.secret_key:
            print("ERROR: InkThreadable credentials not configured")
            return None

        # URL encode the ID (it contains # which is a URL fragment)
        encoded_id = quote(inkthreadable_id, safe='')

        # Build query string (must match parameter order in URL)
        query_string = f"AppId={self.app_id}&id={encoded_id}"

        # Generate signature
        signature_string = query_string + self.secret_key
        signature = hashlib.sha1(signature_string.encode('utf-8')).hexdigest()

        # Make API request
        url = f"https://www.inkthreadable.co.uk/api/order.php?AppId={self.app_id}&id={encoded_id}&Signature={signature}"

        try:
            response = requests.get(url, timeout=30)

            if response.status_code == 200:
                return response.json()
            else:
                print(f"ERROR: InkThreadable API returned {response.status_code}: {response.text}")
                return None

        except Exception as e:
            print(f"ERROR: Failed to get order status: {e}")
            return None

    def update_shipping_info(self, order_id: int, get_db_func,
                            carrier: str = None,
                            inkthreadable_status: str = None,
                            tracking_number: str = None,
                            shipped_at: str = None) -> bool:
        """Update shipping information in database"""
        try:
            conn = get_db_func()
            cursor = conn.cursor()

            updates = []
            params = []

            if carrier is not None:
                updates.append("carrier = ?")
                params.append(carrier)
            if inkthreadable_status is not None:
                updates.append("inkthreadable_status = ?")
                params.append(inkthreadable_status)
            if tracking_number is not None:
                updates.append("tracking_number = ?")
                params.append(tracking_number)
            if shipped_at is not None:
                updates.append("shipped_at = ?")
                params.append(shipped_at)

            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())

            if updates:
                params.append(order_id)
                query = f"UPDATE orders SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                conn.commit()
                conn.close()
                return True

            conn.close()
            return False

        except Exception as e:
            print(f"ERROR: Failed to update shipping info: {e}")
            return False

    def check_all_pending_orders(self, get_db_func,
                                 send_notification_func=None) -> int:
        """
        Check shipping status for all pending orders

        Args:
            get_db_func: Function to get database connection
            send_notification_func: Optional callback for shipping notifications

        Returns:
            Count of orders updated
        """
        if not self.app_id or not self.secret_key:
            print("ERROR: InkThreadable credentials not configured")
            return 0

        # Get orders with InkThreadable ID but no shipped_at date
        conn = get_db_func()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, inkthreadable_id, inkthreadable_status, carrier, tracking_number, shipped_at
            FROM orders
            WHERE inkthreadable_id IS NOT NULL
            AND (shipped_at IS NULL OR shipped_at = '')
        """)

        pending_orders = cursor.fetchall()
        conn.close()

        print(f"Found {len(pending_orders)} orders to check")

        updated_count = 0

        for order in pending_orders:
            order_id, inkthreadable_id, current_status, current_carrier, current_tracking, current_shipped = order

            print(f"Checking order {order_id} (InkThreadable ID: {inkthreadable_id})...")

            # Get status from API
            order_data = self.get_order_status(inkthreadable_id)

            if not order_data:
                continue

            # Extract order information
            order_info = order_data.get("order", {})
            if not order_info:
                print(f"WARNING: No order info found for {inkthreadable_id}")
                continue

            # Extract shipping information
            status = order_info.get("status")
            shipping_info = order_info.get("shipping", {})

            carrier = shipping_info.get("shippingMethod")
            tracking_number = shipping_info.get("trackingNumber")
            shipped_at = shipping_info.get("shipped_at")

            # Clean empty values
            if carrier == "":
                carrier = None
            if tracking_number == "":
                tracking_number = None
            if shipped_at == "":
                shipped_at = None

            print(f"Status: {status}, Carrier: {carrier}, Tracking: {tracking_number}, Shipped: {shipped_at}")

            # Update database
            if self.update_shipping_info(order_id, get_db_func, carrier, status, tracking_number, shipped_at):
                updated_count += 1

                # If newly shipped, send notification
                if shipped_at and not current_shipped and send_notification_func:
                    send_notification_func(order_id, tracking_number)

        return updated_count


# Global instance (can be configured per-app)
inkthreadable_service = InkThreadableService()
