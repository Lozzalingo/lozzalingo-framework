"""
Thin client for the centralised E-Commerce service.
Sites call this instead of importing lozzalingo.modules.merchandise directly.

Usage:
    from lozzalingo.clients.ecommerce_client import EcommerceClient

    client = EcommerceClient()  # reads ECOMMERCE_SERVICE_URL + ECOMMERCE_API_KEY from env

    # Create a product
    result = client.create_product(
        name='London Bus T-Shirt',
        site_id='mario-pinto',
        base_price_pence=2500,
        category='clothing',
        image_urls=['https://cdn.example.com/tshirt.jpg'],
    )
    # result = {"id": 1, "slug": "london-bus-t-shirt"}

    # List products
    products = client.list_products(site_id='mario-pinto')
    # products = [{"id": 1, "name": "...", "variants": [...], ...}, ...]

    # Get single product
    product = client.get_product(1)

    # Update product
    client.update_product(1, {"base_price_pence": 2000})

    # Delete product
    client.delete_product(1)
"""

import os

from lozzalingo.core import db_log


class EcommerceClient:
    """Synchronous client for the centralised E-Commerce service."""

    def __init__(self, service_url=None, api_key=None, timeout=10):
        self.url = (service_url or os.getenv('ECOMMERCE_SERVICE_URL', '')).rstrip('/')
        self.key = api_key or os.getenv('ECOMMERCE_API_KEY', '')
        self.timeout = timeout

        if not self.url:
            db_log('warning', 'ecommerce_client', 'ECOMMERCE_SERVICE_URL not set')
        if not self.key:
            db_log('warning', 'ecommerce_client', 'ECOMMERCE_API_KEY not set')

    def _headers(self):
        """Build request headers with authentication."""
        return {
            'Content-Type': 'application/json',
            'X-API-Key': self.key,
        }

    def _request(self, method, path, json_data=None, params=None):
        """Make an HTTP request to the e-commerce service.

        Returns the parsed JSON response on success, or None on failure.
        Never raises - logs errors and returns None.
        """
        if not self.url:
            db_log('error', 'ecommerce_client', 'Cannot make request, ECOMMERCE_SERVICE_URL not set')
            return None

        full_url = f'{self.url}{path}'

        try:
            import requests
            response = requests.request(
                method,
                full_url,
                json=json_data,
                params=params,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            cls = type(e).__name__
            if 'Timeout' in cls:
                db_log('error', 'ecommerce_client', f'Request timed out: {method} {path}')
            elif 'ConnectionError' in cls:
                db_log('error', 'ecommerce_client', f'Connection failed: {method} {path}')
            elif 'HTTPError' in cls:
                resp = getattr(e, 'response', None)
                db_log('error', 'ecommerce_client', f'HTTP error: {method} {path}', {
                    'status': resp.status_code if resp is not None else None,
                    'body': resp.text[:500] if resp is not None else None,
                })
            else:
                db_log('error', 'ecommerce_client', f'Unexpected error: {method} {path}', {
                    'error': str(e),
                })
            return None

    # ------------------------------------------------------------------
    # Products
    # ------------------------------------------------------------------

    def create_product(self, name, site_id, base_price_pence=0, description='',
                       category='', image_urls=None, slug=None,
                       fulfilment_meta='', is_active=True):
        """Create a new product.

        Args:
            name: Product name.
            site_id: Identifier for the calling site.
            base_price_pence: Price in pence (default 0).
            description: Optional product description.
            category: Optional product category.
            image_urls: Optional list of image URLs.
            slug: Optional URL slug (auto-generated from name if omitted).
            fulfilment_meta: Optional fulfilment metadata (JSON string).
            is_active: Whether the product is active (default True).

        Returns:
            Dict with id and slug on success, or None.
        """
        payload = {
            'name': name,
            'site_id': site_id,
            'base_price_pence': base_price_pence,
            'description': description,
            'category': category,
            'is_active': is_active,
        }
        if image_urls:
            payload['image_urls'] = image_urls
        if slug:
            payload['slug'] = slug
        if fulfilment_meta:
            payload['fulfilment_meta'] = fulfilment_meta

        return self._request('POST', '/api/ecommerce/products', json_data=payload)

    def get_product(self, product_id):
        """Get a single product with its variants.

        Args:
            product_id: The product record ID.

        Returns:
            Dict with product fields and variants array, or None.
        """
        return self._request('GET', f'/api/ecommerce/products/{product_id}')

    def list_products(self, site_id=None, category=None):
        """List products, optionally filtered.

        Args:
            site_id: Optional filter by site.
            category: Optional filter by category.

        Returns:
            List of product dicts, or None.
        """
        params = {}
        if site_id:
            params['site_id'] = site_id
        if category:
            params['category'] = category
        return self._request('GET', '/api/ecommerce/products', params=params)

    def update_product(self, product_id, data):
        """Update a product.

        Args:
            product_id: The product record ID.
            data: Dict with fields to update.

        Returns:
            Dict with id and updated flag, or None.
        """
        return self._request('PUT', f'/api/ecommerce/products/{product_id}', json_data=data)

    def delete_product(self, product_id):
        """Delete a product and its variants.

        Args:
            product_id: The product record ID.

        Returns:
            Dict with id and deleted flag, or None.
        """
        return self._request('DELETE', f'/api/ecommerce/products/{product_id}')

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def list_orders(self, site_id=None, customer_email=None, status=None,
                    limit=50, offset=0):
        """List orders, optionally filtered.

        Returns:
            List of order dicts (each with items array), or None.
        """
        params = {'limit': limit, 'offset': offset}
        if site_id:
            params['site_id'] = site_id
        if customer_email:
            params['customer_email'] = customer_email
        if status:
            params['status'] = status
        return self._request('GET', '/api/ecommerce/orders', params=params)

    def get_order(self, order_id):
        """Get a single order with items and fulfilment events, or None."""
        return self._request('GET', f'/api/ecommerce/orders/{order_id}')

    def create_order(self, customer_email, items, customer_name='',
                     shipping_address=None, payment_session_id='',
                     shipping_pence=0, discount_code='', discount_pence=0):
        """Create an order on the central service.

        Args:
            customer_email: Customer email (required).
            items: List of dicts with product_id, quantity, unit_price_pence,
                   optional variant_id and attributes dict.
            shipping_address: Optional dict.
            payment_session_id: Optional payment session reference.
            shipping_pence: Shipping cost in pence.
            discount_code: Optional applied discount code.
            discount_pence: Discount amount in pence.

        Returns:
            Dict with id and status, or None.
        """
        payload = {
            'customer_email': customer_email,
            'customer_name': customer_name,
            'items': items,
            'shipping_address': shipping_address or {},
            'payment_session_id': payment_session_id,
            'shipping_pence': shipping_pence,
            'discount_code': discount_code,
            'discount_pence': discount_pence,
        }
        return self._request('POST', '/api/ecommerce/orders', json_data=payload)

    def update_order(self, order_id, data):
        """Update an order (status, customer details, shipping address).

        Args:
            order_id: The order record ID.
            data: Dict with any of: status, customer_email, customer_name,
                  shipping_address (dict).

        Returns:
            Dict with id and updated flag, or None.
        """
        return self._request('PUT', f'/api/ecommerce/orders/{order_id}', json_data=data)

    def cancel_order(self, order_id):
        """Cancel an order (restores variant stock). Returns dict or None."""
        return self._request('POST', f'/api/ecommerce/orders/{order_id}/cancel')

    def fulfil_order(self, order_id, provider='inkthreadable'):
        """Submit an order for fulfilment. Returns dict or None."""
        return self._request(
            'POST', f'/api/ecommerce/orders/{order_id}/fulfil',
            params={'provider': provider},
        )

    def get_tracking(self, order_id):
        """Get fulfilment/tracking status for an order. Returns dict or None."""
        return self._request('GET', f'/api/ecommerce/orders/{order_id}/tracking')

    # ------------------------------------------------------------------
    # Discounts
    # ------------------------------------------------------------------

    def validate_discount(self, code, subtotal_pence):
        """Validate a discount code against a basket subtotal.

        Returns dict with valid, discount_pence, new_total_pence, or None.
        """
        return self._request('POST', '/api/ecommerce/discounts/validate', json_data={
            'code': code,
            'subtotal_pence': subtotal_pence,
        })

    def list_discounts(self):
        """List discount codes for this site. Returns list or None."""
        return self._request('GET', '/api/ecommerce/discounts')

    def create_discount(self, code, discount_type, discount_value, **kwargs):
        """Create a discount code. Extra kwargs: min_order_pence, max_uses,
        valid_from, valid_until, is_active. Returns dict or None."""
        payload = {
            'code': code,
            'discount_type': discount_type,
            'discount_value': discount_value,
        }
        payload.update(kwargs)
        return self._request('POST', '/api/ecommerce/discounts', json_data=payload)

    # ------------------------------------------------------------------
    # Shipping
    # ------------------------------------------------------------------

    def get_shipping_rate(self, country):
        """Resolve the shipping rate for a destination country, or None."""
        return self._request('GET', '/api/ecommerce/shipping/rates',
                             params={'country': country})

    def seed_default_shipping(self):
        """Seed the default GB/EU/US/CA/AU/rest-of-world rates. Returns list or None."""
        return self._request('POST', '/api/ecommerce/shipping/seed-defaults')
