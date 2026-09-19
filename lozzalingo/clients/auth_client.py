"""
Thin client for the centralised Auth service.
Sites call this instead of managing users/sessions locally.

The auth-service handles registration, login, JWT issuance, password reset,
email verification, and session validation via a shared cookie on
.laurence.computer domain.

Usage:
    from lozzalingo.clients.auth_client import AuthClient, sso_login_required

    client = AuthClient()  # reads AUTH_SERVICE_URL + AUTH_API_KEY from env

    # Validate a JWT token (e.g. from cookie)
    user = client.validate_token(token)
    # user = {"valid": True, "user_id": 1, "email": "...", "display_name": "..."}

    # Get user profile
    profile = client.get_user(user_id=1)

    # Use the SSO login_required decorator on Flask routes
    @app.route('/admin/dashboard')
    @sso_login_required
    def admin_dashboard():
        return render_template('dashboard.html')
"""

import os
from functools import wraps

from lozzalingo.core import db_log


class AuthClient:
    """Synchronous client for the centralised Auth service."""

    def __init__(self, service_url=None, api_key=None, timeout=10):
        self.url = (service_url or os.getenv('AUTH_SERVICE_URL', '')).rstrip('/')
        self.key = api_key or os.getenv('AUTH_API_KEY', '')
        self.timeout = timeout

        if not self.url:
            db_log('warning', 'auth_client', 'AUTH_SERVICE_URL not set')

    def _headers(self):
        """Build request headers with authentication."""
        return {
            'Content-Type': 'application/json',
            'X-API-Key': self.key,
        }

    def _request(self, method, path, json_data=None, params=None):
        """Make an HTTP request to the auth service.

        Returns the parsed JSON response on success, or None on failure.
        Never raises - logs errors and returns None.
        """
        if not self.url:
            db_log('error', 'auth_client', 'Cannot make request, AUTH_SERVICE_URL not set')
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
                db_log('error', 'auth_client', f'Request timed out: {method} {path}')
            elif 'ConnectionError' in cls:
                db_log('error', 'auth_client', f'Connection failed: {method} {path}')
            elif 'HTTPError' in cls:
                resp = getattr(e, 'response', None)
                db_log('error', 'auth_client', f'HTTP error: {method} {path}', {
                    'status': resp.status_code if resp is not None else None,
                    'body': resp.text[:500] if resp is not None else None,
                })
            else:
                db_log('error', 'auth_client', f'Unexpected error: {method} {path}', {
                    'error': str(e),
                })
            return None

    # ------------------------------------------------------------------
    # Token validation
    # ------------------------------------------------------------------

    def validate_token(self, token):
        """Validate a JWT access token and return user info.

        Args:
            token: JWT access token string.

        Returns:
            Dict with valid, user_id, email, display_name on success.
            Dict with valid=False and reason on failure.
            None if the service is unreachable.
        """
        return self._request('POST', '/api/auth/validate', json_data={'token': token})

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    def get_user(self, user_id):
        """Get user profile by ID.

        Args:
            user_id: The user record ID.

        Returns:
            Dict with id, email, display_name, email_verified, is_active, created_at.
            Or None on failure.
        """
        return self._request('GET', f'/api/auth/users/{user_id}')

    def update_user(self, user_id, data):
        """Update user profile.

        Args:
            user_id: The user record ID.
            data: Dict with fields to update (display_name, email).

        Returns:
            Dict with message on success, or None.
        """
        return self._request('PUT', f'/api/auth/users/{user_id}', json_data=data)

    # ------------------------------------------------------------------
    # Registration (server-side)
    # ------------------------------------------------------------------

    def register(self, email, password, display_name=None):
        """Register a new user account.

        Args:
            email: User email address.
            password: User password (validated server-side).
            display_name: Optional display name.

        Returns:
            Dict with user_id and message on success, or None.
        """
        payload = {'email': email, 'password': password}
        if display_name:
            payload['display_name'] = display_name
        return self._request('POST', '/api/auth/register', json_data=payload)

    # ------------------------------------------------------------------
    # Login (server-side)
    # ------------------------------------------------------------------

    def login(self, email, password):
        """Authenticate a user and get tokens.

        Args:
            email: User email address.
            password: User password.

        Returns:
            Dict with access_token, refresh_token, expires_in on success. Or None.
        """
        return self._request('POST', '/api/auth/login', json_data={
            'email': email,
            'password': password,
        })

    def refresh(self, refresh_token):
        """Exchange a refresh token for a new access token.

        Args:
            refresh_token: The refresh token from login.

        Returns:
            Dict with access_token and expires_in on success. Or None.
        """
        return self._request('POST', '/api/auth/refresh', json_data={
            'refresh_token': refresh_token,
        })

    def logout(self, refresh_token):
        """Revoke a refresh token.

        Args:
            refresh_token: The refresh token to revoke.

        Returns:
            Dict with message on success, or None.
        """
        return self._request('POST', '/api/auth/logout', json_data={
            'refresh_token': refresh_token,
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
        return self._request('POST', '/api/auth/forgot-password', json_data={
            'email': email,
        })

    def reset_password(self, token, new_password):
        """Complete password reset with token.

        Args:
            token: Password reset token from email.
            new_password: New password (validated server-side).

        Returns:
            Dict with message on success, or None.
        """
        return self._request('POST', '/api/auth/reset-password', json_data={
            'token': token,
            'new_password': new_password,
        })

    # ------------------------------------------------------------------
    # Site access
    # ------------------------------------------------------------------

    def get_user_access(self, user_id):
        """Get all site access records for a user.

        Args:
            user_id: The user record ID.

        Returns:
            Dict with user_id, email, site_access array. Or None.
        """
        return self._request('GET', f'/api/auth/admin/user-access/{user_id}')

    def grant_access(self, user_id, site_id, role='viewer'):
        """Grant user access to a site.

        Args:
            user_id: The user record ID.
            site_id: The site identifier.
            role: Access role (viewer, editor, admin, owner).

        Returns:
            Dict with message on success, or None.
        """
        return self._request('POST', '/api/auth/admin/grant-access', json_data={
            'user_id': user_id,
            'site_id': site_id,
            'role': role,
        })


def sso_login_required(f):
    """Decorator that validates the auth_token cookie via the auth-service.

    If the cookie is missing or invalid, redirects to the auth-service login page
    with a redirect back to the current URL.

    Sets g.current_user with user info on success.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import request, redirect, g, current_app

        token = request.cookies.get('auth_token', '')

        if not token:
            auth_url = os.getenv('AUTH_SERVICE_URL', '')
            if auth_url:
                return redirect(f'{auth_url}/login?redirect={request.url}')
            # Fallback: try framework auth
            from flask import session
            if not session.get('logged_in'):
                return redirect('/sign-in')
            return f(*args, **kwargs)

        client = AuthClient()
        result = client.validate_token(token)

        if result and result.get('valid'):
            g.current_user = {
                'user_id': result.get('user_id'),
                'email': result.get('email'),
                'display_name': result.get('display_name'),
            }
            return f(*args, **kwargs)
        else:
            # Token invalid or expired, redirect to login
            auth_url = os.getenv('AUTH_SERVICE_URL', '')
            if auth_url:
                return redirect(f'{auth_url}/login?redirect={request.url}')
            return redirect('/sign-in')

    return decorated
