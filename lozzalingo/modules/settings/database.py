"""
Settings Database with Encryption
=================================

Stores site settings with encryption for sensitive values.
Uses Fernet symmetric encryption (AES-128-CBC).
"""

import sqlite3
import os
import base64
import hashlib
from datetime import datetime

# Try to import cryptography for encryption
try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    print("Warning: cryptography package not installed. Settings will not be encrypted.")


def get_settings_db_path():
    """Get settings database path"""
    try:
        from lozzalingo.core import Config
        db_dir = os.path.dirname(Config.ADMIN_DB) if hasattr(Config, 'ADMIN_DB') else 'databases'
    except ImportError:
        db_dir = 'databases'

    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    return os.path.join(db_dir, 'settings.db') if db_dir else 'settings.db'


def get_encryption_key():
    """
    Derive encryption key from Flask SECRET_KEY.
    Returns a Fernet-compatible key (32 bytes, base64 encoded).
    """
    if not HAS_CRYPTO:
        return None

    try:
        from flask import current_app
        secret = current_app.config.get('SECRET_KEY', 'default-insecure-key')
    except RuntimeError:
        # Outside of request context
        secret = os.environ.get('SECRET_KEY', os.environ.get('FLASK_SECRET_KEY', 'default-insecure-key'))

    # Derive a 32-byte key using SHA256
    key_bytes = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)


def encrypt_value(value):
    """Encrypt a value using Fernet"""
    if not HAS_CRYPTO or not value:
        return value

    try:
        key = get_encryption_key()
        f = Fernet(key)
        return f.encrypt(value.encode()).decode()
    except Exception as e:
        print(f"Encryption error: {e}")
        return value


def decrypt_value(encrypted_value):
    """Decrypt a value using Fernet"""
    if not HAS_CRYPTO or not encrypted_value:
        return encrypted_value

    try:
        key = get_encryption_key()
        f = Fernet(key)
        return f.decrypt(encrypted_value.encode()).decode()
    except Exception as e:
        # May not be encrypted (old value or encryption disabled)
        return encrypted_value


def init_settings_db():
    """Initialize settings database"""
    db_path = get_settings_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            key TEXT NOT NULL UNIQUE,
            value TEXT,
            is_secret BOOLEAN DEFAULT 0,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_settings_category ON settings(category)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_settings_key ON settings(key)')

    conn.commit()
    conn.close()

    return db_path


def get_setting(key, default=None, decrypt=True):
    """
    Get a setting value by key.
    Falls back to environment variable if not in database.
    """
    try:
        db_path = get_settings_db_path()
        if not os.path.exists(db_path):
            # Fall back to environment variable
            return os.environ.get(key, default)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT value, is_secret FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        conn.close()

        if row:
            value, is_secret = row
            if is_secret and decrypt and value:
                value = decrypt_value(value)
            return value if value else default

        # Fall back to environment variable
        return os.environ.get(key, default)

    except Exception as e:
        print(f"Error getting setting {key}: {e}")
        return os.environ.get(key, default)


def set_setting(key, value, category='general', is_secret=False, description=None):
    """Set a setting value"""
    try:
        db_path = get_settings_db_path()
        init_settings_db()

        # Encrypt if secret
        stored_value = encrypt_value(value) if is_secret and value else value

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO settings (category, key, value, is_secret, description, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                category = excluded.category,
                is_secret = excluded.is_secret,
                description = COALESCE(excluded.description, settings.description),
                updated_at = excluded.updated_at
        ''', (category, key, stored_value, is_secret, description, datetime.now().isoformat()))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"Error setting {key}: {e}")
        return False


def delete_setting(key):
    """Delete a setting"""
    try:
        db_path = get_settings_db_path()
        if not os.path.exists(db_path):
            return False

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM settings WHERE key = ?', (key,))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted

    except Exception as e:
        print(f"Error deleting setting {key}: {e}")
        return False


def get_all_settings(category=None, mask_secrets=True):
    """
    Get all settings, optionally filtered by category.
    Secrets are masked by default (show only last 4 chars).
    """
    try:
        db_path = get_settings_db_path()
        if not os.path.exists(db_path):
            return []

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        if category:
            cursor.execute('''
                SELECT id, category, key, value, is_secret, description, updated_at
                FROM settings WHERE category = ? ORDER BY key
            ''', (category,))
        else:
            cursor.execute('''
                SELECT id, category, key, value, is_secret, description, updated_at
                FROM settings ORDER BY category, key
            ''')

        settings = []
        for row in cursor.fetchall():
            setting_id, cat, key, value, is_secret, description, updated_at = row

            # Decrypt and mask secrets
            if is_secret and value:
                decrypted = decrypt_value(value)
                if mask_secrets and decrypted:
                    # Show only last 4 characters
                    masked = '*' * max(0, len(decrypted) - 4) + decrypted[-4:] if len(decrypted) > 4 else '****'
                    display_value = masked
                else:
                    display_value = decrypted
            else:
                display_value = value

            settings.append({
                'id': setting_id,
                'category': cat,
                'key': key,
                'value': display_value,
                'is_secret': bool(is_secret),
                'description': description,
                'updated_at': updated_at
            })

        conn.close()
        return settings

    except Exception as e:
        print(f"Error getting all settings: {e}")
        return []


def get_categories():
    """Get list of all setting categories"""
    try:
        db_path = get_settings_db_path()
        if not os.path.exists(db_path):
            return []

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT category FROM settings ORDER BY category')
        categories = [row[0] for row in cursor.fetchall()]
        conn.close()
        return categories

    except Exception as e:
        print(f"Error getting categories: {e}")
        return []


# Define the standard settings schema
SETTINGS_SCHEMA = {
    'stripe': {
        'label': 'Payment (Stripe)',
        'icon': '💳',
        'settings': [
            {'key': 'STRIPE_MODE', 'label': 'Mode', 'type': 'select', 'options': ['test', 'live'], 'default': 'test', 'is_secret': False, 'description': 'Use test or live Stripe keys'},
            {'key': 'STRIPE_TEST_PK', 'label': 'Test Publishable Key', 'type': 'text', 'is_secret': False, 'description': 'pk_test_...'},
            {'key': 'STRIPE_TEST_SK', 'label': 'Test Secret Key', 'type': 'password', 'is_secret': True, 'description': 'sk_test_...'},
            {'key': 'STRIPE_LIVE_PK', 'label': 'Live Publishable Key', 'type': 'text', 'is_secret': False, 'description': 'pk_live_...'},
            {'key': 'STRIPE_LIVE_SK', 'label': 'Live Secret Key', 'type': 'password', 'is_secret': True, 'description': 'sk_live_...'},
            {'key': 'STRIPE_WEBHOOK_SECRET', 'label': 'Webhook Secret', 'type': 'password', 'is_secret': True, 'description': 'whsec_...'},
        ]
    },
    'email': {
        'label': 'Email (Resend)',
        'icon': '📧',
        'settings': [
            {'key': 'RESEND_API_KEY', 'label': 'Resend API Key', 'type': 'password', 'is_secret': True, 'description': 're_...'},
            {'key': 'EMAIL_FROM', 'label': 'From Email', 'type': 'email', 'is_secret': False, 'description': 'noreply@yourdomain.com'},
            {'key': 'EMAIL_REPLY_TO', 'label': 'Reply-To Email', 'type': 'email', 'is_secret': False, 'description': 'support@yourdomain.com'},
        ]
    },
    'oauth': {
        'label': 'OAuth Authentication',
        'icon': '🔐',
        'settings': [
            {'key': 'GOOGLE_CLIENT_ID', 'label': 'Google Client ID', 'type': 'text', 'is_secret': False, 'description': 'From Google Cloud Console'},
            {'key': 'GOOGLE_CLIENT_SECRET', 'label': 'Google Client Secret', 'type': 'password', 'is_secret': True, 'description': 'GOCSPX-...'},
            {'key': 'GITHUB_CLIENT_ID', 'label': 'GitHub Client ID', 'type': 'text', 'is_secret': False, 'description': 'From GitHub Developer Settings'},
            {'key': 'GITHUB_CLIENT_SECRET', 'label': 'GitHub Client Secret', 'type': 'password', 'is_secret': True, 'description': 'GitHub OAuth secret'},
        ]
    },
    'storage': {
        'label': 'Storage (DigitalOcean Spaces)',
        'icon': '💾',
        'settings': [
            {'key': 'STORAGE_TYPE', 'label': 'Storage Type', 'type': 'select', 'options': ['local', 'cloud'], 'default': 'local', 'is_secret': False, 'description': 'Where to store uploaded files'},
            {'key': 'DO_SPACES_REGION', 'label': 'Region', 'type': 'text', 'is_secret': False, 'description': 'e.g., sfo3, nyc3'},
            {'key': 'DO_SPACES_NAME', 'label': 'Space Name', 'type': 'text', 'is_secret': False, 'description': 'Your space/bucket name'},
            {'key': 'DO_SPACES_KEY', 'label': 'Access Key ID', 'type': 'text', 'is_secret': False, 'description': 'Spaces access key'},
            {'key': 'DO_SPACES_SECRET', 'label': 'Secret Access Key', 'type': 'password', 'is_secret': True, 'description': 'Spaces secret key'},
        ]
    },
    'site': {
        'label': 'Site Settings',
        'icon': '⚙️',
        'settings': [
            {'key': 'BRAND_NAME', 'label': 'Brand Name', 'type': 'text', 'is_secret': False, 'description': 'Your site/brand name'},
            {'key': 'BASE_URL', 'label': 'Base URL', 'type': 'url', 'is_secret': False, 'description': 'https://yourdomain.com'},
            {'key': 'ENVIRONMENT', 'label': 'Environment', 'type': 'select', 'options': ['development', 'staging', 'production'], 'default': 'development', 'is_secret': False, 'description': 'Current environment'},
        ]
    }
}
