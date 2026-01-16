"""
Settings Admin Routes
=====================

Admin interface for managing site settings.
"""

from flask import render_template, request, redirect, url_for, session, jsonify, flash
from . import settings_bp
from .database import (
    init_settings_db, get_setting, set_setting, delete_setting,
    get_all_settings, get_categories, SETTINGS_SCHEMA, HAS_CRYPTO
)


def admin_required(f):
    """Decorator to require admin login"""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin.login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function


@settings_bp.route('/')
@admin_required
def settings_page():
    """Main settings page"""
    # Initialize database
    init_settings_db()

    # Get current settings
    all_settings = get_all_settings(mask_secrets=True)

    # Create a lookup dict for current values
    current_values = {s['key']: s['value'] for s in all_settings}

    return render_template('settings/settings.html',
                           schema=SETTINGS_SCHEMA,
                           current_values=current_values,
                           has_crypto=HAS_CRYPTO)


@settings_bp.route('/save', methods=['POST'])
@admin_required
def save_settings():
    """Save settings from form"""
    try:
        data = request.form.to_dict()

        saved_count = 0
        for category_key, category_data in SETTINGS_SCHEMA.items():
            for setting in category_data['settings']:
                key = setting['key']
                if key in data:
                    value = data[key].strip()

                    # Don't overwrite secrets with masked value
                    if setting.get('is_secret') and value and value.startswith('*'):
                        continue

                    # Only save non-empty values, or explicitly save empty to clear
                    if value or key in data:
                        set_setting(
                            key=key,
                            value=value if value else None,
                            category=category_key,
                            is_secret=setting.get('is_secret', False),
                            description=setting.get('description')
                        )
                        saved_count += 1

        flash(f'Settings saved successfully ({saved_count} settings updated)', 'success')

    except Exception as e:
        flash(f'Error saving settings: {str(e)}', 'error')

    return redirect(url_for('settings.settings_page'))


@settings_bp.route('/api/settings')
@admin_required
def api_get_settings():
    """API endpoint to get all settings"""
    category = request.args.get('category')
    settings = get_all_settings(category=category, mask_secrets=True)
    return jsonify({'success': True, 'settings': settings})


@settings_bp.route('/api/settings/<key>', methods=['GET'])
@admin_required
def api_get_setting(key):
    """API endpoint to get a single setting (masked)"""
    all_settings = get_all_settings(mask_secrets=True)
    setting = next((s for s in all_settings if s['key'] == key), None)

    if setting:
        return jsonify({'success': True, 'setting': setting})
    return jsonify({'success': False, 'error': 'Setting not found'}), 404


@settings_bp.route('/api/settings', methods=['POST'])
@admin_required
def api_save_setting():
    """API endpoint to save a single setting"""
    data = request.get_json()

    if not data or 'key' not in data:
        return jsonify({'success': False, 'error': 'Key is required'}), 400

    key = data['key']
    value = data.get('value', '')
    category = data.get('category', 'general')
    is_secret = data.get('is_secret', False)
    description = data.get('description')

    success = set_setting(key, value, category, is_secret, description)

    if success:
        return jsonify({'success': True, 'message': 'Setting saved'})
    return jsonify({'success': False, 'error': 'Failed to save setting'}), 500


@settings_bp.route('/api/settings/<key>', methods=['DELETE'])
@admin_required
def api_delete_setting(key):
    """API endpoint to delete a setting"""
    success = delete_setting(key)

    if success:
        return jsonify({'success': True, 'message': 'Setting deleted'})
    return jsonify({'success': False, 'error': 'Setting not found'}), 404


@settings_bp.route('/api/test-stripe')
@admin_required
def test_stripe_connection():
    """Test Stripe API connection"""
    try:
        import stripe

        mode = get_setting('STRIPE_MODE', 'test')
        if mode == 'live':
            sk = get_setting('STRIPE_LIVE_SK')
        else:
            sk = get_setting('STRIPE_TEST_SK')

        if not sk:
            return jsonify({'success': False, 'error': 'Stripe secret key not configured'})

        stripe.api_key = sk
        # Make a simple API call to verify
        stripe.Account.retrieve()

        return jsonify({'success': True, 'message': f'Stripe connection successful ({mode} mode)'})

    except ImportError:
        return jsonify({'success': False, 'error': 'Stripe package not installed'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@settings_bp.route('/api/test-resend')
@admin_required
def test_resend_connection():
    """Test Resend API connection"""
    try:
        import resend

        api_key = get_setting('RESEND_API_KEY')
        if not api_key:
            return jsonify({'success': False, 'error': 'Resend API key not configured'})

        resend.api_key = api_key
        # List domains to verify connection
        resend.Domains.list()

        return jsonify({'success': True, 'message': 'Resend connection successful'})

    except ImportError:
        return jsonify({'success': False, 'error': 'Resend package not installed'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
