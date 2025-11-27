from authlib.integrations.flask_client import OAuth
from flask import flash, redirect, url_for, session
import os

# Optional import for app-specific config
try:
    from config import Config
except ImportError:
    Config = None

# OAuth configuration
oauth = OAuth()

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
    oauth.init_app(app)
    
    # Google OAuth - using explicit endpoints instead of discovery
    google = oauth.register(
        name='google',
        client_id=Config.GOOGLE_CLIENT_ID,
        client_secret=Config.GOOGLE_CLIENT_SECRET,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )
    # GitHub OAuth
    github = oauth.register(
        name='github',
        client_id=os.getenv('GITHUB_CLIENT_ID'),
        client_secret=os.getenv('GITHUB_CLIENT_SECRET'),
        token_url='https://github.com/login/oauth/access_token',
        authorize_url='https://github.com/login/oauth/authorize',
        api_base_url='https://api.github.com/',
        client_kwargs={'scope': 'user:email'},
    )
    
    return google, github

# Helper function to check if user is authenticated
def login_required(f):
    """Decorator to require authentication"""
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please sign in to access this page.', 'error')
            return redirect(url_for('auth.signin'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function