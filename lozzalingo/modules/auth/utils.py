"""
Auth Utilities
==============

Utility functions for authentication including OAuth support.
"""

from flask import flash, redirect, url_for, session, current_app, request
import os

# Optional import for authlib (OAuth support)
try:
    from authlib.integrations.flask_client import OAuth
    HAS_AUTHLIB = True
except ImportError:
    HAS_AUTHLIB = False
    OAuth = None

# Optional import for app-specific config
try:
    from lozzalingo.core import Config
except ImportError:
    Config = None

# OAuth configuration - only if authlib is installed
oauth = OAuth() if HAS_AUTHLIB else None

def validate_password_strength(password):
    """Validate password meets security requirements"""
    if len(password) < 8:
        return False
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    
    return has_upper and has_lower and has_digit

def configure_oauth(app):
    """Configure OAuth providers"""
    if not HAS_AUTHLIB or oauth is None:
        print("[AUTH] OAuth not available - authlib not installed")
        return None, None

    oauth.init_app(app)

    google = None
    github = None

    # Google OAuth - using explicit endpoints instead of discovery
    google_client_id = app.config.get('GOOGLE_CLIENT_ID') or os.getenv('GOOGLE_CLIENT_ID')
    google_client_secret = app.config.get('GOOGLE_CLIENT_SECRET') or os.getenv('GOOGLE_CLIENT_SECRET')

    if google_client_id and google_client_secret:
        google = oauth.register(
            name='google',
            client_id=google_client_id,
            client_secret=google_client_secret,
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={
                'scope': 'openid email profile'
            }
        )

    # GitHub OAuth
    github_client_id = app.config.get('GITHUB_CLIENT_ID') or os.getenv('GITHUB_CLIENT_ID')
    github_client_secret = app.config.get('GITHUB_CLIENT_SECRET') or os.getenv('GITHUB_CLIENT_SECRET')

    if github_client_id and github_client_secret:
        github = oauth.register(
            name='github',
            client_id=github_client_id,
            client_secret=github_client_secret,
            token_url='https://github.com/login/oauth/access_token',
            authorize_url='https://github.com/login/oauth/authorize',
            api_base_url='https://api.github.com/',
            client_kwargs={'scope': 'user:email'},
        )

    return google, github

# Helper function to check if user is authenticated
def login_required(f):
    """Decorator to require authentication.

    Checks in order:
    1. SSO JWT (auth_token cookie) - centralised auth service
    2. Flask session user_id (public user auth)
    3. Flask session admin_id (dashboard admin auth)

    If none pass, redirects to login.
    """
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. Check SSO JWT cookie first (admin auth)
        try:
            from lozzalingo.auth_client import get_auth_user_from_cookie
            payload = get_auth_user_from_cookie()
            if payload:
                # Valid SSO token - populate session for downstream compat
                if 'admin_id' not in session:
                    is_super = payload.get('is_super_admin', False)
                    has_admin_role = any(
                        a.get('role') in ('admin', 'owner')
                        for a in payload.get('site_access', [])
                    )
                    if is_super or has_admin_role:
                        session['admin_id'] = payload.get('sub') or payload.get('user_id') or 'sso'
                        session['admin_email'] = payload.get('email', '')
                if 'user_id' not in session:
                    session['user_id'] = payload.get('sub') or payload.get('user_id') or 'sso'
                    session['email'] = payload.get('email', '')
                return f(*args, **kwargs)
        except ImportError:
            pass
        except Exception:
            pass

        # 1b. Check per-site user JWT cookie (public user auth)
        try:
            from lozzalingo.auth_client import decode_jwt
            site_id = current_app.config.get('SITE_ID', '')
            if site_id:
                user_token = request.cookies.get(f'lza_user_{site_id}')
                if user_token:
                    payload = decode_jwt(user_token)
                    if payload:
                        if 'user_id' not in session:
                            session['user_id'] = payload.get('sub') or payload.get('user_id')
                            session['email'] = payload.get('email', '')
                            session['first_name'] = payload.get('first_name', '')
                            session['last_name'] = payload.get('last_name', '')
                        return f(*args, **kwargs)
        except ImportError:
            pass
        except Exception:
            pass

        # 2. Fall back to Flask session
        if 'user_id' in session or 'admin_id' in session:
            return f(*args, **kwargs)

        flash('Please sign in to access this page.', 'error')
        # Prefer the dashboard login when it exists, fall back to auth signin
        try:
            return redirect(url_for('admin.login'))
        except Exception:
            return redirect(url_for('auth.signin'))
    return decorated_function