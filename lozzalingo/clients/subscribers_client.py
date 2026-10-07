"""
Thin client for subscriber management via CRM + Email services.

The standalone Subscribers service has been merged into CRM (contacts, lists,
GDPR) and Email (double opt-in, confirmation, preferences).

Usage:
    from lozzalingo.clients.subscribers_client import SubscribersClient

    client = SubscribersClient()  # reads EMAIL_SERVICE_URL, CRM_SERVICE_URL from env

    # Subscribe (triggers double opt-in via Email service)
    result = client.subscribe(
        email='user@example.com',
        list_id=1,
        site_id='my-site',
        first_name='Jane',
    )

    # List contacts on a list (via CRM)
    contacts = client.list_subscribers(list_id=1, page=1)

    # Get contact by email (via CRM)
    contact = client.get_contact_by_email('user@example.com')
"""

import os

from lozzalingo.core import db_log


class SubscribersClient:
    """Client for subscriber management via CRM + Email services."""

    def __init__(self, email_service_url=None, crm_service_url=None,
                 email_api_key=None, crm_api_key=None, timeout=10):
        self.email_url = (
            email_service_url
            or os.getenv('EMAIL_SERVICE_URL', '')
        ).rstrip('/')
        self.crm_url = (
            crm_service_url
            or os.getenv('CRM_SERVICE_URL', '')
        ).rstrip('/')
        self.email_key = email_api_key or os.getenv('EMAIL_SERVICE_API_KEY', '')
        self.crm_key = crm_api_key or os.getenv('CRM_API_KEY', '')
        self.timeout = timeout

        # Backwards compat: old env vars
        if not self.email_url:
            self.email_url = os.getenv('SUBSCRIBERS_SERVICE_URL', '').rstrip('/')
        if not self.crm_url:
            self.crm_url = self.email_url  # fallback

    def _email_request(self, method, path, json_data=None, params=None):
        """Make a request to the Email service."""
        if not self.email_url:
            db_log('error', 'subscribers_client', 'EMAIL_SERVICE_URL not set')
            return None

        try:
            import requests
            response = requests.request(
                method,
                f'{self.email_url}{path}',
                json=json_data,
                params=params,
                headers={
                    'Content-Type': 'application/json',
                    'X-Email-Service-Key': self.email_key,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            db_log('error', 'subscribers_client', f'Email request failed: {method} {path}', {
                'error': str(e),
            })
            return None

    def _crm_request(self, method, path, json_data=None, params=None):
        """Make a request to the CRM service."""
        if not self.crm_url:
            db_log('error', 'subscribers_client', 'CRM_SERVICE_URL not set')
            return None

        try:
            import requests
            response = requests.request(
                method,
                f'{self.crm_url}{path}',
                json=json_data,
                params=params,
                headers={
                    'Content-Type': 'application/json',
                    'X-API-Key': self.crm_key,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            db_log('error', 'subscribers_client', f'CRM request failed: {method} {path}', {
                'error': str(e),
            })
            return None

    # ------------------------------------------------------------------
    # Subscribe (via Email service)
    # ------------------------------------------------------------------

    def subscribe(self, email, list_id, site_id='', first_name='',
                  last_name='', consent_source='', ip_address=''):
        """Subscribe an email address. Triggers double opt-in via Email service."""
        payload = {
            'email': email,
            'list_id': list_id,
            'site_id': site_id,
        }
        if first_name:
            payload['first_name'] = first_name
        if last_name:
            payload['last_name'] = last_name

        return self._email_request('POST', '/api/email/subscribe', json_data=payload)

    # ------------------------------------------------------------------
    # Contacts (via CRM)
    # ------------------------------------------------------------------

    def get_subscriber(self, subscriber_id):
        """Get contact detail by ID."""
        return self._crm_request('GET', f'/api/crm/contacts/{subscriber_id}')

    def get_contact_by_email(self, email):
        """Get contact detail by email."""
        return self._crm_request('GET', f'/api/crm/contacts/by-email/{email}')

    def list_subscribers(self, page=1, per_page=50, status=None, list_id=None):
        """List contacts with pagination."""
        if list_id:
            return self._crm_request('GET', f'/api/crm/lists/{list_id}/contacts',
                                     params={'page': page, 'per_page': per_page})
        return self._crm_request('GET', '/api/crm/contacts',
                                 params={'page': page, 'per_page': per_page})

    def update_subscriber(self, subscriber_id, data):
        """Update contact details."""
        return self._crm_request('PUT', f'/api/crm/contacts/{subscriber_id}', json_data=data)

    def unsubscribe(self, subscriber_id):
        """Unsubscribe contact from all lists."""
        return self._crm_request('POST', f'/api/crm/contacts/{subscriber_id}/unsubscribe',
                                 json_data={'global': True})

    # ------------------------------------------------------------------
    # Lists (via CRM)
    # ------------------------------------------------------------------

    def create_list(self, name, description=''):
        """Create a new mailing list."""
        payload = {'name': name}
        if description:
            payload['description'] = description
        return self._crm_request('POST', '/api/crm/lists', json_data=payload)

    def get_lists(self):
        """Get all mailing lists."""
        return self._crm_request('GET', '/api/crm/lists')

    def get_list(self, list_id):
        """Get a single mailing list."""
        return self._crm_request('GET', f'/api/crm/lists/{list_id}')
