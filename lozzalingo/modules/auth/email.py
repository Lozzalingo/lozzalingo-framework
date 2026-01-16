"""
Auth Email Functions
====================

Email sending functions for authentication flows.
Uses the lozzalingo email module.
"""

from flask import current_app

# Try to import from lozzalingo email module
try:
    from lozzalingo.modules.email import email_service
    HAS_EMAIL_SERVICE = True
except ImportError:
    HAS_EMAIL_SERVICE = False


def _get_brand_name():
    """Get brand name from config or use default"""
    try:
        return current_app.config.get('EMAIL_BRAND_NAME', 'Our Site')
    except RuntimeError:
        return 'Our Site'


def send_password_reset_email(email, first_name, reset_link):
    """Send password reset email"""
    brand = _get_brand_name()
    subject = f"Reset Your {brand} Password"

    body = f"""Hi {first_name},

You requested a password reset for your {brand} account.

Click the link below to reset your password:
{reset_link}

This link will expire in 1 hour for security reasons.

If you didn't request this reset, you can safely ignore this email.

Best regards,
The {brand} Team"""

    if HAS_EMAIL_SERVICE:
        return email_service.send_email(email, subject, body)
    else:
        print(f"[EMAIL] Would send password reset to {email}")
        return True


def send_password_changed_email(email, first_name):
    """Send confirmation email after password change"""
    brand = _get_brand_name()
    subject = f"Password Changed - {brand}"

    body = f"""Hi {first_name},

Your {brand} account password has been successfully changed.

If you didn't make this change, please contact us immediately.

Best regards,
The {brand} Team"""

    if HAS_EMAIL_SERVICE:
        return email_service.send_email(email, subject, body)
    else:
        print(f"[EMAIL] Would send password changed notification to {email}")
        return True


def send_verification_email(email, first_name, verification_link):
    """Send email verification for new users"""
    brand = _get_brand_name()
    subject = f"Welcome to {brand} - Verify Your Email"

    body = f"""Hi {first_name},

Welcome to {brand}!

Please verify your email address by clicking the link below:
{verification_link}

This link will expire in 24 hours.

Once verified, you'll be able to access all features of your account.

Best regards,
The {brand} Team"""

    if HAS_EMAIL_SERVICE:
        return email_service.send_email(email, subject, body)
    else:
        print(f"[EMAIL] Would send verification to {email}")
        return True