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
