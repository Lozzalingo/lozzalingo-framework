"""
Settings Helpers
================

Convenient functions for accessing settings throughout the application.
These automatically fall back to environment variables if settings aren't in the database.
"""

from .database import get_setting


# ============================================
# Stripe Settings
# ============================================

def get_stripe_mode():
    """Get current Stripe mode (test or live)"""
    return get_setting('STRIPE_MODE', 'test')


def get_stripe_publishable_key():
    """Get the appropriate Stripe publishable key based on mode"""
    mode = get_stripe_mode()
    if mode == 'live':
        return get_setting('STRIPE_LIVE_PK') or get_setting('STRIPE_PUBLISHABLE_KEY')
    return get_setting('STRIPE_TEST_PK') or get_setting('STRIPE_TEST_PUBLISHABLE_KEY')


def get_stripe_secret_key():
    """Get the appropriate Stripe secret key based on mode"""
    mode = get_stripe_mode()
    if mode == 'live':
        return get_setting('STRIPE_LIVE_SK') or get_setting('STRIPE_SECRET_KEY')
    return get_setting('STRIPE_TEST_SK') or get_setting('STRIPE_TEST_SECRET_KEY')


def get_stripe_webhook_secret():
    """Get Stripe webhook secret"""
    return get_setting('STRIPE_WEBHOOK_SECRET')


def is_stripe_live():
    """Check if Stripe is in live mode"""
    return get_stripe_mode() == 'live'


# ============================================
# Email Settings (Resend)
# ============================================

def get_resend_api_key():
    """Get Resend API key"""
    return get_setting('RESEND_API_KEY')


def get_email_from():
    """Get from email address"""
    return get_setting('EMAIL_FROM') or get_setting('RESEND_FROM_EMAIL')


def get_email_reply_to():
    """Get reply-to email address"""
    return get_setting('EMAIL_REPLY_TO') or get_setting('RESEND_REPLY_TO')


# ============================================
# OAuth Settings
# ============================================

def get_google_oauth_credentials():
    """Get Google OAuth credentials"""
    return {
        'client_id': get_setting('GOOGLE_CLIENT_ID'),
        'client_secret': get_setting('GOOGLE_CLIENT_SECRET')
    }


def get_github_oauth_credentials():
    """Get GitHub OAuth credentials"""
    return {
        'client_id': get_setting('GITHUB_CLIENT_ID'),
        'client_secret': get_setting('GITHUB_CLIENT_SECRET')
    }


# ============================================
# Storage Settings (DigitalOcean Spaces)
# ============================================

def get_storage_type():
    """Get storage type (local or cloud)"""
    return get_setting('STORAGE_TYPE', 'local')


def is_cloud_storage():
    """Check if using cloud storage"""
    return get_storage_type() == 'cloud'


def get_do_spaces_config():
    """Get DigitalOcean Spaces configuration"""
    return {
        'region': get_setting('DO_SPACES_REGION'),
        'space_name': get_setting('DO_SPACES_NAME'),
        'access_key': get_setting('DO_SPACES_KEY'),
        'secret_key': get_setting('DO_SPACES_SECRET')
    }


# ============================================
# Site Settings
# ============================================

def get_brand_name():
    """Get brand/site name"""
    return get_setting('BRAND_NAME', 'Lozzalingo')


def get_base_url():
    """Get site base URL"""
    return get_setting('BASE_URL', 'http://localhost:5000')


def get_environment():
    """Get current environment"""
    return get_setting('ENVIRONMENT', 'development')


def is_production():
    """Check if running in production"""
    return get_environment() == 'production'


def is_development():
    """Check if running in development"""
    return get_environment() == 'development'
