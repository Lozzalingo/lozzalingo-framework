"""
Auth Utilities
==============

Utility functions for authentication including OAuth support.
"""

from flask import flash, redirect, url_for, session, current_app
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

    Accepts either auth module sessions (user_id) or dashboard admin
    sessions (admin_id) so that admin users authenticated via the
    dashboard login are also recognised.
    """
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session and 'admin_id' not in session:
            flash('Please sign in to access this page.', 'error')
            # Prefer the dashboard login when it exists, fall back to auth signin
            try:
                return redirect(url_for('admin.login'))
            except Exception:
                return redirect(url_for('auth.signin'))
        return f(*args, **kwargs)
    return decorated_function