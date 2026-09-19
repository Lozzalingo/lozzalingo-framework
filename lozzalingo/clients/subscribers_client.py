"""
Thin client for the centralised Subscribers service.
Sites call this instead of importing lozzalingo.modules.subscribers directly.

Usage:
    from lozzalingo.clients.subscribers_client import SubscribersClient

    client = SubscribersClient()  # reads SUBSCRIBERS_SERVICE_URL + SUBSCRIBERS_API_KEY from env

    # Subscribe a new email (triggers double opt-in)
    result = client.subscribe(
        email='user@example.com',
        list_id=1,
        first_name='Jane',
        consent_source='footer_form',
    )
    # result = {"message": "Subscription received...", "subscriber_id": 42}

    # List subscribers
    subs = client.list_subscribers(list_id=1, status='confirmed', page=1)
    # subs = {"subscribers": [...], "total": 150, "page": 1, "pages": 3}

    # Get subscriber detail
    sub = client.get_subscriber(42)
    # sub = {"id": 42, "email": "user@example.com", "status": "confirmed", "lists": [...]}

    # Update subscriber
    client.update_subscriber(42, {"first_name": "Janet"})

    # Unsubscribe (GDPR erasure)
    client.unsubscribe(42)
"""

import os

from lozzalingo.core import db_log


class SubscribersClient:
    """Synchronous client for the centralised Subscribers service."""

    def __init__(self, service_url=None, api_key=None, timeout=10):
        self.url = (service_url or os.getenv('SUBSCRIBERS_SERVICE_URL', '')).rstrip('/')
        self.key = api_key or os.getenv('SUBSCRIBERS_API_KEY', '')
        self.timeout = timeout

        if not self.url:
            db_log('warning', 'subscribers_client', 'SUBSCRIBERS_SERVICE_URL not set')
        if not self.key:
            db_log('warning', 'subscribers_client', 'SUBSCRIBERS_API_KEY not set')

    def _headers(self):
        """Build request headers with authentication."""
        return {
            'Content-Type': 'application/json',
            'X-Subscribers-Key': self.key,
        }

    def _request(self, method, path, json_data=None, params=None):
        """Make an HTTP request to the subscribers service.

        Returns the parsed JSON response on success, or None on failure.
        Never raises - logs errors and returns None.
        """
        if not self.url:
            db_log('error', 'subscribers_client', 'Cannot make request, SUBSCRIBERS_SERVICE_URL not set')
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
                db_log('error', 'subscribers_client', f'Request timed out: {method} {path}')
            elif 'ConnectionError' in cls:
                db_log('error', 'subscribers_client', f'Connection failed: {method} {path}')
            elif 'HTTPError' in cls:
                resp = getattr(e, 'response', None)
                db_log('error', 'subscribers_client', f'HTTP error: {method} {path}', {
                    'status': resp.status_code if resp is not None else None,
                    'body': resp.text[:500] if resp is not None else None,
                })
            else:
                db_log('error', 'subscribers_client', f'Unexpected error: {method} {path}', {
                    'error': str(e),
                })
            return None

    # ------------------------------------------------------------------
    # Subscribers
    # ------------------------------------------------------------------

    def subscribe(self, email, list_id, first_name='', last_name='',
                  consent_source='', ip_address=''):
        """Subscribe an email address. Triggers double opt-in.

        Args:
            email: Subscriber email address.
            list_id: The mailing list ID to subscribe to.
            first_name: Optional first name.
            last_name: Optional last name.
            consent_source: Where the signup came from (e.g. 'footer_form').
            ip_address: Optional IP for consent logging.

        Returns:
            Dict with message and subscriber_id on success, or None.
        """
        payload = {
            'email': email,
            'list_id': list_id,
        }
        if first_name:
            payload['first_name'] = first_name
        if last_name:
            payload['last_name'] = last_name
        if consent_source:
            payload['consent_source'] = consent_source
        if ip_address:
            payload['ip_address'] = ip_address

        return self._request('POST', '/subscribers', json_data=payload)

    def get_subscriber(self, subscriber_id):
        """Get subscriber detail with list memberships.

        Args:
            subscriber_id: The subscriber record ID.

        Returns:
            Dict with subscriber fields and lists array, or None.
        """
        return self._request('GET', f'/subscribers/{subscriber_id}')

    def list_subscribers(self, page=1, per_page=50, status=None, list_id=None):
        """List subscribers with pagination and filters.

        Args:
            page: Page number (default 1).
            per_page: Results per page (default 50).
            status: Filter by status (pending, confirmed, unsubscribed).
            list_id: Filter by mailing list ID.

        Returns:
            Dict with subscribers list and pagination info, or None.
        """
        params = {'page': page, 'per_page': per_page}
        if status:
            params['status'] = status
        if list_id:
            params['list_id'] = list_id
        return self._request('GET', '/subscribers', params=params)

    def update_subscriber(self, subscriber_id, data):
        """Update subscriber details.

        Args:
            subscriber_id: The subscriber record ID.
            data: Dict with fields to update (first_name, last_name, status).

        Returns:
            Dict with message on success, or None.
        """
        return self._request('PUT', f'/subscribers/{subscriber_id}', json_data=data)

    def unsubscribe(self, subscriber_id):
        """Unsubscribe and erase subscriber data (GDPR).

        Args:
            subscriber_id: The subscriber record ID.

        Returns:
            Dict with message on success, or None.
        """
        return self._request('DELETE', f'/subscribers/{subscriber_id}')

    # ------------------------------------------------------------------
    # Lists
    # ------------------------------------------------------------------

    def create_list(self, name, description=''):
        """Create a new mailing list.

        Args:
            name: List name.
            description: Optional description.

        Returns:
            Dict with list_id on success, or None.
        """
        payload = {'name': name}
        if description:
            payload['description'] = description
        return self._request('POST', '/lists', json_data=payload)

    def get_lists(self):
        """Get all mailing lists.

        Returns:
            List of dicts with list info, or None.
        """
        return self._request('GET', '/lists')

    def get_list(self, list_id):
        """Get a single mailing list.

        Args:
            list_id: The list ID.

        Returns:
            Dict with list info, or None.
        """
        return self._request('GET', f'/lists/{list_id}')
