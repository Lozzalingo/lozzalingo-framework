"""
Thin client for the centralised Analytics service.
Used for server-side event and conversion tracking.
Client-side tracking (page views, clicks) is handled by lza.js.

Usage:
    from lozzalingo.clients.analytics_client import AnalyticsClient

    client = AnalyticsClient()  # reads ANALYTICS_SERVICE_URL + ANALYTICS_API_KEY from env

    # Track a purchase conversion (server-side, e.g. from Stripe webhook)
    client.log_conversion(
        site_id='coffee-goblin',
        conversion_type='purchase',
        order_id='ord_123',
        order_value=2500,  # pence
        customer_email='buyer@example.com',
        fingerprint_hash='abc123',  # from Stripe metadata
    )

    # Track a custom event (server-side)
    client.log_event(
        site_id='coffee-goblin',
        event_type='subscription',
        event_name='premium_activated',
        event_data={'plan': 'annual', 'amount': 9900},
    )
"""

import os

from lozzalingo.core import db_log


class AnalyticsClient:
    """Synchronous client for server-side analytics tracking."""

    def __init__(self, service_url=None, api_key=None, timeout=10):
        self.url = (service_url or os.getenv('ANALYTICS_SERVICE_URL', '')).rstrip('/')
        self.key = api_key or os.getenv('ANALYTICS_API_KEY', '')
        self.timeout = timeout

        if not self.url:
            db_log('warning', 'analytics_client', 'ANALYTICS_SERVICE_URL not set')

    def _headers(self):
        """Build request headers with authentication."""
        headers = {'Content-Type': 'application/json'}
        if self.key:
            headers['X-API-Key'] = self.key
        return headers

    def _request(self, method, path, json_data=None, params=None):
        """Make an HTTP request to the analytics service.

        Returns the parsed JSON response on success, or None on failure.
        Never raises - logs errors and returns None. Analytics failures
        must never break the calling site.
        """
        if not self.url:
            db_log('error', 'analytics_client', 'Cannot make request, ANALYTICS_SERVICE_URL not set')
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
                db_log('error', 'analytics_client', f'Request timed out: {method} {path}')
            elif 'ConnectionError' in cls:
                db_log('error', 'analytics_client', f'Connection failed: {method} {path}')
            elif 'HTTPError' in cls:
                resp = getattr(e, 'response', None)
                db_log('error', 'analytics_client', f'HTTP error: {method} {path}', {
                    'status': resp.status_code if resp is not None else None,
                    'body': resp.text[:500] if resp is not None else None,
                })
            else:
                db_log('error', 'analytics_client', f'Unexpected error: {method} {path}', {
                    'error': str(e),
                })
            return None

    # ------------------------------------------------------------------
    # Conversion tracking (server-side)
    # ------------------------------------------------------------------

    def log_conversion(self, site_id, conversion_type, order_id=None,
                       order_value=None, currency='GBP', fingerprint_hash=None,
                       product_id=None, product_name=None, customer_email=None,
                       user_id=None, session_id=None, metadata=None):
        """Track a conversion event (purchase, add_to_cart, checkout_start, etc.).

        Args:
            site_id: Identifier for the calling site (e.g. 'coffee-goblin').
            conversion_type: Type of conversion (purchase, add_to_cart, checkout_start, product_view).
            order_id: Optional order/transaction ID.
            order_value: Optional value in pence.
            currency: Currency code (default GBP).
            fingerprint_hash: Optional visitor fingerprint for attribution.
            product_id: Optional product identifier.
            product_name: Optional product name.
            customer_email: Optional customer email.
            user_id: Optional user ID.
            session_id: Optional session ID.
            metadata: Optional dict of extra data.

        Returns:
            Dict with status on success, or None.
        """
        payload = {
            'site_id': site_id,
            'conversion_type': conversion_type,
        }
        if order_id:
            payload['order_id'] = order_id
        if order_value is not None:
            payload['order_value'] = order_value
        if currency != 'GBP':
            payload['currency'] = currency
        if fingerprint_hash:
            payload['fingerprint_hash'] = fingerprint_hash
        if product_id:
            payload['product_id'] = product_id
        if product_name:
            payload['product_name'] = product_name
        if customer_email:
            payload['customer_email'] = customer_email
        if user_id:
            payload['user_id'] = user_id
        if session_id:
            payload['session_id'] = session_id
        if metadata:
            payload['metadata'] = metadata

        return self._request('POST', '/api/ingest/conversion', json_data=payload)

    # ------------------------------------------------------------------
    # Event tracking (server-side)
    # ------------------------------------------------------------------

    def log_event(self, site_id, event_type, event_name, event_data=None,
                  fingerprint=None, session_id=None, url=None, path=None):
        """Track a custom event (server-side).

        Args:
            site_id: Identifier for the calling site.
            event_type: Category of event (e.g. 'subscription', 'form_submit').
            event_name: Specific event name (e.g. 'premium_activated').
            event_data: Optional dict of event-specific data.
            fingerprint: Optional visitor fingerprint hash.
            session_id: Optional session ID.
            url: Optional page URL where event occurred.
            path: Optional page path.

        Returns:
            Dict with status on success, or None.
        """
        payload = {
            'site_id': site_id,
            'event_type': event_type,
            'event_name': event_name,
        }
        if event_data:
            payload['event_data'] = event_data
        if fingerprint:
            payload['fingerprint'] = fingerprint
        if session_id:
            payload['session_id'] = session_id
        if url:
            payload['url'] = url
        if path:
            payload['path'] = path

        return self._request('POST', '/api/ingest/event', json_data=payload)

    # ------------------------------------------------------------------
    # Read queries
    # ------------------------------------------------------------------

    def get_page_views(self, site_id):
        """Get page view counts grouped by path.

        Args:
            site_id: Identifier for the site (e.g. 'laurencedotcomputer').

        Returns:
            List of dicts with path, unique_views, total_views. Or None on failure.
        """
        result = self._request('GET', '/api/analytics/page-views', params={
            'site_id': site_id,
            'key': self.key,
        })
        if result and result.get('status') == 'ok':
            return result.get('views', [])
        return None
