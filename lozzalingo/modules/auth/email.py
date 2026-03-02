"""
Auth Email Functions
====================

Email sending functions for authentication flows.
Uses the lozzalingo email module with styled HTML templates.
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


def _get_style():
    """Get email style dict from the email service, falling back to defaults."""
    if HAS_EMAIL_SERVICE and hasattr(email_service, 'style'):
        return email_service.style
    return {
        'bg': '#f8f6f0', 'card_bg': '#ffffff', 'header_bg': '#2a2a2a',
        'header_text': '#f8f6f0', 'text': '#2a2a2a', 'text_secondary': '#666666',
        'accent': '#2a2a2a', 'highlight_bg': '#f8f6f0', 'highlight_border': '#2a2a2a',
        'border': '#d4c5a0', 'link': '#2a2a2a', 'btn_bg': '#2a2a2a',
        'btn_text': '#f8f6f0', 'footer_bg': '#f8f6f0',
        'font': "'Georgia', serif", 'font_heading': "'Georgia', serif",
    }


def _get_website_url():
    """Get website URL from email service or config."""
    if HAS_EMAIL_SERVICE and hasattr(email_service, 'website_url'):
        return email_service.website_url
    try:
        return current_app.config.get('EMAIL_WEBSITE_URL', '')
    except RuntimeError:
        return ''


def _get_tagline():
    """Get brand tagline from email service or config."""
    if HAS_EMAIL_SERVICE and hasattr(email_service, 'brand_tagline'):
        return email_service.brand_tagline
    try:
        return current_app.config.get('EMAIL_BRAND_TAGLINE', '')
    except RuntimeError:
        return ''


def _wrap_html(brand, s, content):
    """Wrap email content in the standard Lozzalingo email layout."""
    tagline = _get_tagline()
    website_url = _get_website_url()
    from datetime import datetime
    tagline_html = f'<p style="font-size: 14px; margin: 0; opacity: 0.8;">{tagline}</p>' if tagline else ''
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{brand}</title>
</head>
<body style="font-family: {s['font']}; line-height: 1.6; color: {s['text']}; background: {s['bg']}; max-width: 600px; margin: 0 auto; padding: 24px;">
    <div style="background: {s['card_bg']}; border: 1px solid {s['border']}; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
        <div style="background: {s['header_bg']}; color: {s['header_text']}; padding: 32px; text-align: center;">
            <h1 style="font-family: {s['font_heading']}; font-size: 24px; margin: 0 0 8px 0; font-weight: normal; letter-spacing: 2px;">{brand.upper()}</h1>
            {tagline_html}
        </div>
        <div style="padding: 40px 32px;">
            {content}
        </div>
        <div style="background: {s['footer_bg']}; padding: 24px; text-align: center; font-size: 13px; color: {s['text_secondary']}; border-top: 1px solid {s['border']};">
            <p style="margin: 4px 0;">{brand} &middot; {datetime.now().year}</p>
            <p style="margin: 4px 0;"><a href="{website_url}" style="color: {s['link']};">Website</a></p>
        </div>
    </div>
</body>
</html>"""


def send_password_reset_email(email, first_name, reset_link):
    """Send password reset email"""
    brand = _get_brand_name()
    s = _get_style()
    subject = f"Reset Your {brand} Password"

    text_body = f"""Hi {first_name},

You requested a password reset for your {brand} account.

Click the link below to reset your password:
{reset_link}

This link will expire in 1 hour for security reasons.

If you didn't request this reset, you can safely ignore this email.

Best regards,
The {brand} Team"""

    content = f"""
            <h2 style="font-family: {s['font_heading']}; font-size: 20px; margin: 0 0 24px 0; font-weight: normal; color: {s['text']};">Reset Your Password</h2>
            <p style="font-size: 16px; margin: 16px 0; line-height: 1.7;">Hi {first_name},</p>
            <p style="font-size: 16px; margin: 16px 0; line-height: 1.7;">You requested a password reset for your {brand} account. Click the button below to set a new password:</p>
            <p style="text-align: center; margin: 32px 0;">
                <a href="{reset_link}" style="display: inline-block; background: {s['btn_bg']}; color: {s['btn_text']}; padding: 14px 32px; text-decoration: none; font-weight: bold; font-family: {s['font_heading']}; font-size: 16px;">Reset Password</a>
            </p>
            <div style="background: {s['highlight_bg']}; padding: 16px 20px; margin: 24px 0; border-left: 4px solid {s['highlight_border']};">
                <p style="margin: 0; font-size: 14px; color: {s['text_secondary']};">This link will expire in 1 hour for security reasons. If you didn't request this reset, you can safely ignore this email.</p>
            </div>
            <div style="border-top: 1px solid {s['border']}; margin: 32px 0;"></div>
            <p style="font-size: 14px; color: {s['text_secondary']}; margin: 0;">Best regards,<br>The {brand} Team</p>"""

    html_body = _wrap_html(brand, s, content)

    if HAS_EMAIL_SERVICE:
        return email_service.send_email([email], subject, html_body, text_body=text_body)
    else:
        print(f"[EMAIL] Would send password reset to {email}")
        return True


def send_password_changed_email(email, first_name):
    """Send confirmation email after password change"""
    brand = _get_brand_name()
    s = _get_style()
    subject = f"Password Changed - {brand}"

    text_body = f"""Hi {first_name},

Your {brand} account password has been successfully changed.

If you didn't make this change, please contact us immediately.

Best regards,
The {brand} Team"""

    content = f"""
            <h2 style="font-family: {s['font_heading']}; font-size: 20px; margin: 0 0 24px 0; font-weight: normal; color: {s['text']};">Password Changed</h2>
            <p style="font-size: 16px; margin: 16px 0; line-height: 1.7;">Hi {first_name},</p>
            <p style="font-size: 16px; margin: 16px 0; line-height: 1.7;">Your {brand} account password has been successfully changed.</p>
            <div style="background: {s['highlight_bg']}; padding: 16px 20px; margin: 24px 0; border-left: 4px solid {s['highlight_border']};">
                <p style="margin: 0; font-size: 14px; color: {s['text_secondary']};">If you didn't make this change, please contact us immediately.</p>
            </div>
            <div style="border-top: 1px solid {s['border']}; margin: 32px 0;"></div>
            <p style="font-size: 14px; color: {s['text_secondary']}; margin: 0;">Best regards,<br>The {brand} Team</p>"""

    html_body = _wrap_html(brand, s, content)

    if HAS_EMAIL_SERVICE:
        return email_service.send_email([email], subject, html_body, text_body=text_body)
    else:
        print(f"[EMAIL] Would send password changed notification to {email}")
        return True


def send_verification_email(email, first_name, verification_link):
    """Send email verification for new users"""
    brand = _get_brand_name()
    s = _get_style()
    subject = f"Verify Your Email - {brand}"

    text_body = f"""Hi {first_name},

Welcome to {brand}!

Please verify your email address by clicking the link below:
{verification_link}

This link will expire in 24 hours.

Once verified, you'll be able to access all features of your account.

Best regards,
The {brand} Team"""

    content = f"""
            <h2 style="font-family: {s['font_heading']}; font-size: 20px; margin: 0 0 24px 0; font-weight: normal; color: {s['text']};">Verify Your Email</h2>
            <p style="font-size: 16px; margin: 16px 0; line-height: 1.7;">Hi {first_name},</p>
            <p style="font-size: 16px; margin: 16px 0; line-height: 1.7;">Welcome to {brand}! Please verify your email address to get started:</p>
            <p style="text-align: center; margin: 32px 0;">
                <a href="{verification_link}" style="display: inline-block; background: {s['btn_bg']}; color: {s['btn_text']}; padding: 14px 32px; text-decoration: none; font-weight: bold; font-family: {s['font_heading']}; font-size: 16px;">Verify Email</a>
            </p>
            <div style="background: {s['highlight_bg']}; padding: 16px 20px; margin: 24px 0; border-left: 4px solid {s['highlight_border']};">
                <p style="margin: 0; font-size: 14px; color: {s['text_secondary']};">This link will expire in 24 hours. Once verified, you'll have full access to your account.</p>
            </div>
            <div style="border-top: 1px solid {s['border']}; margin: 32px 0;"></div>
            <p style="font-size: 14px; color: {s['text_secondary']}; margin: 0;">Best regards,<br>The {brand} Team</p>"""

    html_body = _wrap_html(brand, s, content)

    if HAS_EMAIL_SERVICE:
        return email_service.send_email([email], subject, html_body, text_body=text_body)
    else:
        print(f"[EMAIL] Would send verification to {email}")
        return True
