"""
Thin client for the per-site User Auth service.
Sites use this to manage end-user accounts (registration, login, profile)
via the centralised auth service's per-site API.

Unlike AuthClient (admin SSO), this client authenticates with X-Site-API-Key
and operates on site-scoped user records.

Usage:
    from lozzalingo.clients.user_auth_client import UserAuthClient

    client = UserAuthClient(site_id='coffee-goblin')

    # Register a new user
    result = client.register(
        email='user@example.com',
        password='SecurePass1',
        display_name='Jane',
        first_name='Jane',
        last_name='Doe',
    )

    # Login
    result = client.login('user@example.com', 'SecurePass1')
    # result = {"access_token": "...", "refresh_token": "...", "expires_in": 3600}

    # Get profile
    profile = client.get_profile(token='eyJ...')

    # OAuth callback
    result = client.oauth_callback(
        provider='google',
        provider_id='12345',
        email='user@example.com',
        display_name='Jane Doe',
        avatar_url='https://...',
    )
"""

import os

from lozzalingo.core import db_log


class UserAuthClient:
    """Synchronous client for per-site user authentication via the auth service."""

    def __init__(self, site_id, service_url=None, api_key=None, timeout=10):
        self.site_id = site_id
        self.url = (service_url or os.getenv('AUTH_SERVICE_URL', '')).rstrip('/')
        self.key = api_key or os.getenv('AUTH_SITE_API_KEY', '')
        self.timeout = timeout

        if not self.url:
            db_log('warning', 'user_auth_client', 'AUTH_SERVICE_URL not set')
        if not self.key:
            db_log('warning', 'user_auth_client', 'AUTH_SITE_API_KEY not set')

    def _headers(self):
        """Build request headers with site API key authentication."""
        return {
            'Content-Type': 'application/json',
            'X-Site-API-Key': self.key,
        }

    def _request(self, method, path, json_data=None, params=None, extra_headers=None):
        """Make an HTTP request to the auth service.

        Returns the parsed JSON response on success, or None on failure.
        Never raises - logs errors and returns None.
        """
        if not self.url:
            db_log('error', 'user_auth_client', 'Cannot make request, AUTH_SERVICE_URL not set')
            return None

        full_url = f'{self.url}{path}'
        headers = self._headers()
        if extra_headers:
            headers.update(extra_headers)

        try:
            import requests
            response = requests.request(
                method,
                full_url,
                json=json_data,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            cls = type(e).__name__
            if 'Timeout' in cls:
                db_log('error', 'user_auth_client', f'Request timed out: {method} {path}')
            elif 'ConnectionError' in cls:
                db_log('error', 'user_auth_client', f'Connection failed: {method} {path}')
            elif 'HTTPError' in cls:
                resp = getattr(e, 'response', None)
                db_log('error', 'user_auth_client', f'HTTP error: {method} {path}', {
                    'status': resp.status_code if resp is not None else None,
                    'body': resp.text[:500] if resp is not None else None,
                })
            else:
                db_log('error', 'user_auth_client', f'Unexpected error: {method} {path}', {
                    'error': str(e),
                })
            return None

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, email, password, display_name=None, first_name=None, last_name=None):
        """Register a new site user account.

        Args:
            email: User email address.
            password: User password (validated server-side).
            display_name: Optional display name.
            first_name: Optional first name.
            last_name: Optional last name.

        Returns:
            Dict with user_id and message on success, or None.
        """
        payload = {
            'email': email,
            'password': password,
            'site_id': self.site_id,
        }
        if display_name:
            payload['display_name'] = display_name
        if first_name:
            payload['first_name'] = first_name
        if last_name:
            payload['last_name'] = last_name
        return self._request('POST', '/api/users/register', json_data=payload)

    # ------------------------------------------------------------------
    # Login / Logout
    # ------------------------------------------------------------------

    def login(self, email, password):
        """Authenticate a site user and get tokens.

        Args:
            email: User email address.
            password: User password.

        Returns:
            Dict with access_token, refresh_token, expires_in on success. Or None.
        """
        return self._request('POST', '/api/users/login', json_data={
            'email': email,
            'password': password,
            'site_id': self.site_id,
        })

    def logout(self, token):
        """Log out a user by revoking their token.

        Args:
            token: The access or refresh token to revoke.

        Returns:
            Dict with message on success, or None.
        """
        return self._request('POST', '/api/users/logout', json_data={
            'token': token,
            'site_id': self.site_id,
        })

    # ------------------------------------------------------------------
    # Email verification
    # ------------------------------------------------------------------

    def verify_email(self, token):
        """Verify a user's email address with a verification token.

        Args:
            token: Email verification token from the verification email.

        Returns:
            Dict with message on success, or None.
        """
        return self._request('POST', '/api/users/verify-email', json_data={
            'token': token,
            'site_id': self.site_id,
        })

    # ------------------------------------------------------------------
    # Password reset
    # ------------------------------------------------------------------

    def forgot_password(self, email):
        """Initiate password reset. Always returns success (email security).

        Args:
            email: User email address.

        Returns:
            Dict with message on success, or None.
        """
        return self._request('POST', '/api/users/forgot-password', json_data={
            'email': email,
            'site_id': self.site_id,
        })

    def reset_password(self, token, new_password):
        """Complete password reset with token.

        Args:
            token: Password reset token from email.
            new_password: New password (validated server-side).

        Returns:
            Dict with message on success, or None.
        """
        return self._request('POST', '/api/users/reset-password', json_data={
            'token': token,
            'new_password': new_password,
            'site_id': self.site_id,
        })

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    def get_profile(self, token):
        """Get the authenticated user's profile.

        Args:
            token: JWT access token.

        Returns:
            Dict with user profile data, or None.
        """
        return self._request('GET', '/api/users/profile', extra_headers={
            'Authorization': f'Bearer {token}',
        })

    def update_profile(self, token, data):
        """Update the authenticated user's profile.

        Args:
            token: JWT access token.
            data: Dict with fields to update (display_name, first_name, last_name, avatar_url, etc.).

        Returns:
            Dict with message on success, or None.
        """
        return self._request('PUT', '/api/users/profile', json_data=data, extra_headers={
            'Authorization': f'Bearer {token}',
        })

    # ------------------------------------------------------------------
    # OAuth
    # ------------------------------------------------------------------

    def oauth_callback(self, provider, provider_id, email, display_name=None, avatar_url=None):
        """Handle OAuth provider callback - create or link user account.

        Args:
            provider: OAuth provider name (google, github, etc.).
            provider_id: The user's ID from the provider.
            email: Email address from the provider.
            display_name: Optional display name from the provider.
            avatar_url: Optional avatar URL from the provider.

        Returns:
            Dict with access_token, refresh_token, user_id on success. Or None.
        """
        payload = {
            'provider': provider,
            'provider_id': provider_id,
            'email': email,
            'site_id': self.site_id,
        }
        if display_name:
            payload['display_name'] = display_name
        if avatar_url:
            payload['avatar_url'] = avatar_url
        return self._request('POST', '/api/users/oauth-callback', json_data=payload)
