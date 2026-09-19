"""
Thin client for the centralised Email service.
Sites call this instead of using Resend/SES/SMTP directly.

Usage:
    from lozzalingo.clients.email_client import EmailClient

    client = EmailClient()  # reads EMAIL_SERVICE_URL + EMAIL_SERVICE_API_KEY from env

    # Send a single email
    result = client.send(
        to='user@example.com',
        subject='Welcome!',
        html='<h1>Hello</h1>',
        site_id='coffee-goblin',
    )
    # result = {"success": True, "email_id": 42, "resend_id": "re_xxx"}

    # Send to multiple recipients
    result = client.send_batch(
        recipients=['a@example.com', 'b@example.com'],
        subject='Newsletter',
        html='<p>News</p>',
        site_id='coffee-goblin',
    )
    # result = {"success": True, "sent": 2, "failed": 0, "results": [...]}

    # Check delivery status
    status = client.get_status(email_id=42)
    # status = {"id": 42, "status": "delivered", "recipient": "user@example.com", ...}

    # Get sending statistics
    stats = client.get_stats()
    # stats = {"total_sent": 1500, "delivered": 1480, "bounced": 5, ...}
"""

import os

from lozzalingo.core import db_log


class EmailClient:
    """Synchronous client for the centralised Email service."""

    def __init__(self, service_url=None, api_key=None, timeout=15):
        self.url = (service_url or os.getenv('EMAIL_SERVICE_URL', '')).rstrip('/')
        self.key = api_key or os.getenv('EMAIL_SERVICE_API_KEY', '')
        self.timeout = timeout

        if not self.url:
            db_log('warning', 'email_client', 'EMAIL_SERVICE_URL not set')
        if not self.key:
            db_log('warning', 'email_client', 'EMAIL_SERVICE_API_KEY not set')

    def _headers(self):
        """Build request headers with authentication."""
        return {
            'Content-Type': 'application/json',
            'X-Email-Service-Key': self.key,
        }

    def _request(self, method, path, json_data=None, params=None):
        """Make an HTTP request to the email service.

        Returns the parsed JSON response on success, or None on failure.
        Never raises - logs errors and returns None so the calling site
        keeps working even if the email service is down.
        """
        if not self.url:
            db_log('error', 'email_client', 'Cannot make request, EMAIL_SERVICE_URL not set')
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
            module = type(e).__module__ or ''
            cls = type(e).__name__
            if 'Timeout' in cls:
                db_log('error', 'email_client', f'Request timed out: {method} {path}')
            elif 'ConnectionError' in cls:
                db_log('error', 'email_client', f'Connection failed: {method} {path}')
            elif 'HTTPError' in cls:
                resp = getattr(e, 'response', None)
                db_log('error', 'email_client', f'HTTP error: {method} {path}', {
                    'status': resp.status_code if resp is not None else None,
                    'body': resp.text[:500] if resp is not None else None,
                })
            else:
                db_log('error', 'email_client', f'Unexpected error: {method} {path}', {
                    'error': str(e),
                })
            return None

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------

    def send(self, to, subject, html, site_id, from_email=None, text=None,
             template_name=None, variables=None):
        """Send a single email via the centralised email service.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            html: HTML body of the email.
            site_id: Identifier for the calling site (e.g. 'coffee-goblin').
            from_email: Optional sender address (overrides site default).
            text: Optional plain text body.
            template_name: Optional template slug to use instead of raw html.
            variables: Optional dict of template variables.

        Returns:
            Dict with success, email_id, resend_id on success, or None on failure.
        """
        payload = {
            'to': to,
            'subject': subject,
            'html': html,
            'site_id': site_id,
        }
        if from_email:
            payload['from_email'] = from_email
        if text:
            payload['text'] = text
        if template_name:
            payload['template_name'] = template_name
        if variables:
            payload['variables'] = variables

        return self._request('POST', '/api/email/send', json_data=payload)

    def send_batch(self, recipients, subject, html, site_id, from_email=None,
                   text=None, template_name=None, variables=None):
        """Send an email to multiple recipients.

        Args:
            recipients: List of email addresses.
            subject: Email subject line.
            html: HTML body of the email.
            site_id: Identifier for the calling site.
            from_email: Optional sender address.
            text: Optional plain text body.
            template_name: Optional template slug.
            variables: Optional dict of template variables.

        Returns:
            Dict with success, sent, failed, results on success, or None.
        """
        payload = {
            'recipients': recipients,
            'subject': subject,
            'html': html,
            'site_id': site_id,
        }
        if from_email:
            payload['from_email'] = from_email
        if text:
            payload['text'] = text
        if template_name:
            payload['template_name'] = template_name
        if variables:
            payload['variables'] = variables

        return self._request('POST', '/api/email/send-batch', json_data=payload)

    # ------------------------------------------------------------------
    # Status and stats
    # ------------------------------------------------------------------

    def get_status(self, email_id):
        """Get delivery status for a specific email.

        Args:
            email_id: The email record ID.

        Returns:
            Dict with id, status, recipient, etc. or None on failure.
        """
        return self._request('GET', f'/api/email/status/{email_id}')

    def get_stats(self, site_id=None):
        """Get sending statistics.

        Args:
            site_id: Optional filter by site.

        Returns:
            Dict with total_sent, delivered, bounced, etc. or None.
        """
        params = {}
        if site_id:
            params['site_id'] = site_id
        return self._request('GET', '/api/email/stats', params=params)

    def get_logs(self, site_id=None, page=1, per_page=50):
        """Get email delivery logs.

        Args:
            site_id: Optional filter by site.
            page: Page number (default 1).
            per_page: Results per page (default 50).

        Returns:
            Dict with emails list and pagination info, or None.
        """
        params = {'page': page, 'per_page': per_page}
        if site_id:
            params['site_id'] = site_id
        return self._request('GET', '/api/email/list', params=params)
