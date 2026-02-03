"""
Email Service Module
====================

Configurable email service using Resend API.
All branding is configurable through Flask app config.
"""

import os
import re
import logging
import sqlite3
import time
from typing import List, Optional, Dict, Any
from datetime import datetime

# Rejects consecutive dots, leading/trailing dots in local part
_VALID_EMAIL = re.compile(r'^[a-zA-Z0-9_%+-]+(\.[a-zA-Z0-9_%+-]+)*@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$')

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import resend - it's optional
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    logger.warning("resend package not installed. Email sending will be disabled.")


class EmailService:
    """
    Configurable email service with Resend API integration.

    Configuration (set in Flask app.config):
        RESEND_API_KEY: Your Resend API key
        EMAIL_ADDRESS: Sender email address (default: onboarding@resend.dev)
        EMAIL_BRAND_NAME: Brand name for emails (default: 'Your Brand')
        EMAIL_BRAND_TAGLINE: Brand tagline (default: '')
        EMAIL_WEBSITE_URL: Website URL (default: 'https://example.com')
        EMAIL_SUPPORT_EMAIL: Support email (default: 'support@example.com')
        EMAIL_ADMIN_EMAIL: Admin notification email (default: None)
        USER_DB: Path to SQLite database for email logs
    """

    def __init__(self, app=None):
        self.api_key = None
        self.sender_email = None
        self.brand_name = 'Your Brand'
        self.brand_tagline = ''
        self.website_url = 'https://example.com'
        self.support_email = 'support@example.com'
        self.admin_email = None
        self.user_db = None

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Initialize email service with Flask app configuration"""
        logger.info("=== INITIALIZING EMAIL SERVICE (Resend) ===")

        # Core settings
        self.sender_email = app.config.get('EMAIL_ADDRESS', 'onboarding@resend.dev')
        self.api_key = app.config.get('RESEND_API_KEY')

        # Branding settings
        self.brand_name = app.config.get('EMAIL_BRAND_NAME', 'Your Brand')
        self.brand_tagline = app.config.get('EMAIL_BRAND_TAGLINE', '')
        self.website_url = app.config.get('EMAIL_WEBSITE_URL', 'https://example.com')
        self.support_email = app.config.get('EMAIL_SUPPORT_EMAIL', 'support@example.com')
        self.admin_email = app.config.get('EMAIL_ADMIN_EMAIL')
        self.user_db = app.config.get('USER_DB')

        logger.info(f"Sender email: {self.sender_email}")
        logger.info(f"Brand name: {self.brand_name}")

        if not self.api_key:
            logger.warning("RESEND_API_KEY not configured - email sending disabled")
            return

        if not RESEND_AVAILABLE:
            logger.error("resend package not installed")
            return

        # Set the global API key for resend
        resend.api_key = self.api_key
        logger.info("Resend API client initialized successfully")

    def _get_db_path(self):
        """Get database path from config or environment"""
        if self.user_db:
            return self.user_db
        # Fallback to environment variable
        return os.getenv('USER_DB', 'users.db')

    def _log_email(self, recipient: str, subject: str, email_type: str,
                   status: str, error_message: str = None):
        """Log email attempt to database"""
        try:
            db_path = self._get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Create table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS email_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    email_type TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                INSERT INTO email_logs (recipient, subject, email_type, status, error_message)
                VALUES (?, ?, ?, ?, ?)
            """, (recipient, subject, email_type, status, error_message))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to log email to database: {e}")

    def send_email(self, to: List[str], subject: str, html_body: str,
                   text_body: Optional[str] = None) -> bool:
        """
        Send an email to multiple recipients using Resend API

        Args:
            to: List of recipient email addresses
            subject: Email subject
            html_body: HTML content of the email
            text_body: Plain text content (optional)

        Returns:
            bool: True if successful, False otherwise
        """
        if not RESEND_AVAILABLE:
            logger.error("resend package not installed")
            return False

        try:
            if not self.api_key:
                logger.error("Resend API key not configured")
                return False

            if not to:
                logger.error("No recipients provided")
                return False

            if not self.sender_email:
                logger.error("Sender email not configured")
                return False

            # Filter out invalid email addresses before sending
            valid_recipients = []
            for addr in to:
                if _VALID_EMAIL.match(addr):
                    valid_recipients.append(addr)
                else:
                    logger.warning(f"Skipping invalid email address: {addr}")

            if not valid_recipients:
                logger.error("No valid recipients after filtering")
                return False

            # Send email to each recipient, skipping failures
            sent_count = 0
            failed_count = 0
            for i, recipient in enumerate(valid_recipients):
                logger.info(f"Sending email from: {self.sender_email} to: {recipient}")
                logger.info(f"Subject: {subject}")

                try:
                    # Prepare email data for Resend
                    email_params = {
                        "from": self.sender_email,
                        "to": recipient,
                        "subject": subject,
                        "html": html_body
                    }

                    # Add plain text content if provided
                    if text_body:
                        email_params["text"] = text_body

                    # Send via Resend API
                    r = resend.Emails.send(email_params)
                    logger.info(f"Resend response: {r}")

                    if r and r.get('id'):
                        logger.debug(f"Email sent successfully to: {recipient}, ID: {r['id']}")
                        email_type = self._get_email_type_from_subject(subject)
                        self._log_email(recipient, subject, email_type, 'sent', None)
                        sent_count += 1
                    else:
                        logger.error(f"Resend error for {recipient}: {r}")
                        self._log_email(recipient, subject, 'unknown', 'failed', str(r))
                        failed_count += 1

                    # Rate limit: Wait 0.6s between sends (max ~1.66 emails/sec)
                    if i < len(valid_recipients) - 1:
                        logger.debug(f"Rate limiting: Waiting 0.6s before next send...")
                        time.sleep(0.6)

                except Exception as send_error:
                    logger.error(f"Error sending to {recipient}: {send_error}")
                    self._log_email(recipient, subject, 'unknown', 'failed', str(send_error))
                    failed_count += 1

            if failed_count > 0:
                logger.warning(f"Email send completed with errors: {sent_count} sent, {failed_count} failed")
            else:
                logger.info(f"Email sent successfully to {sent_count} recipients: {subject}")

            # Return True as long as at least one email was sent
            return sent_count > 0

        except Exception as e:
            logger.error(f"Failed to send email via Resend: {str(e)}")
            for recipient in to:
                self._log_email(recipient, subject, 'unknown', 'failed', str(e))
            return False

    def _get_email_type_from_subject(self, subject: str) -> str:
        """Determine email type from subject line"""
        subject_lower = subject.lower()
        if 'order confirmation' in subject_lower or 'purchase' in subject_lower:
            return 'order_confirmation'
        elif 'shipped' in subject_lower or 'tracking' in subject_lower:
            return 'shipping_confirmation'
        elif 'welcome' in subject_lower:
            return 'welcome'
        elif 'alert' in subject_lower or 'notification' in subject_lower:
            return 'admin_notification'
        else:
            return 'other'

    # ==================== Welcome Email ====================

    def send_welcome_email(self, email: str, name: Optional[str] = None) -> bool:
        """Send welcome email to new subscriber"""
        subject = f"Welcome to {self.brand_name}!"

        html_body = self._get_welcome_template(name or "Friend")
        text_body = f"""
Welcome to {self.brand_name}!

Thank you for subscribing. You'll now receive:
- Latest news and updates
- Behind-the-scenes content
- Special offers and releases
- Exclusive subscriber content

Stay tuned for exciting updates!

Best regards,
The {self.brand_name} Team

To unsubscribe, visit: {self.website_url}/unsubscribe
        """

        return self.send_email([email], subject, html_body, text_body)

    def _get_welcome_template(self, name: str) -> str:
        """Get welcome email HTML template"""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to {self.brand_name}</title>
    <style>
        body {{ font-family: 'Georgia', serif; line-height: 1.6; color: #2a2a2a; background: #f8f6f0; max-width: 600px; margin: 0 auto; padding: 24px; }}
        .container {{ background: #fff; border: 1px solid #d4c5a0; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
        .header {{ background: #2a2a2a; color: #f8f6f0; padding: 32px; text-align: center; }}
        .content {{ background: #fff; padding: 40px 32px; color: #2a2a2a; }}
        .footer {{ background: #f8f6f0; padding: 24px; text-align: center; font-size: 13px; color: #666; border-top: 1px solid #d4c5a0; }}
        h1 {{ font-size: 24px; margin: 0 0 8px 0; font-weight: normal; letter-spacing: 2px; }}
        h2 {{ font-size: 20px; margin: 0 0 24px 0; font-weight: normal; color: #4a4a4a; }}
        p {{ font-size: 16px; margin: 16px 0; line-height: 1.7; }}
        .welcome-box {{ background: #f8f6f0; padding: 24px; margin: 24px 0; border-left: 4px solid #2a2a2a; }}
        .welcome-box p {{ margin: 8px 0; font-size: 15px; }}
        a {{ color: #2a2a2a; text-decoration: underline; }}
        a:hover {{ color: #000; }}
        .divider {{ border-top: 1px solid #e0d5b7; margin: 32px 0; }}
        ul {{ padding-left: 0; list-style: none; }}
        li {{ margin: 8px 0; padding-left: 16px; position: relative; }}
        li:before {{ content: '.'; position: absolute; left: 0; color: #2a2a2a; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{self.brand_name.upper()}</h1>
            {f'<p>{self.brand_tagline}</p>' if self.brand_tagline else ''}
        </div>

        <div class="content">
            <h2>Welcome, {name}</h2>

            <p>Thank you for joining the {self.brand_name} community. You're now part of an exclusive group that receives inside access to our latest updates.</p>

            <div class="welcome-box">
                <p><strong>What you'll receive:</strong></p>
                <ul>
                    <li>Latest news and announcements</li>
                    <li>Behind-the-scenes content</li>
                    <li>Early access to new releases</li>
                    <li>Exclusive subscriber-only updates</li>
                </ul>
            </div>

            <div class="divider"></div>

            <p>Stay connected and never miss an important update.</p>

            <p style="text-align: center; margin-top: 32px;">
                <a href="{self.website_url}" style="display: inline-block; background: #2a2a2a; color: #f8f6f0; padding: 12px 24px; text-decoration: none; font-weight: bold;">Visit Website</a>
            </p>
        </div>

        <div class="footer">
            <p>{self.brand_name} Updates . {datetime.now().year}</p>
            <p><a href="{self.website_url}/unsubscribe">Unsubscribe</a> | <a href="{self.website_url}">Website</a></p>
        </div>
    </div>
</body>
</html>
        """

    # ==================== Purchase Confirmation ====================

    def send_purchase_confirmation(self, email: str, order_details: Dict[str, Any]) -> bool:
        """Send purchase confirmation email"""
        subject = f"Order Confirmation - {self.brand_name}"

        html_body = self._get_purchase_template(order_details)
        is_preorder = order_details.get('is_preorder', False)
        size = order_details.get('size', '')

        preorder_text = ""
        if is_preorder:
            preorder_text = """
PRE-ORDER INFORMATION:
This is a pre-order purchase. We will update you via email about shipping.
"""

        text_body = f"""
Thank you for your purchase from {self.brand_name}!

Order Details:
- Product: {order_details.get('product_name', 'N/A')}
{f'- Size: {size}' if size else ''}
- Amount: {order_details.get('currency', 'GBP')} {order_details.get('amount', 0) / 100:.2f}
- Order ID: {order_details.get('order_id', 'N/A')}
{preorder_text}
{'Your order will be processed and we will update you with shipping information.' if is_preorder else 'Your order will be processed and shipped within 4-7 business days.'}

Best regards,
The {self.brand_name} Team
        """

        return self.send_email([email], subject, html_body, text_body)

    def _get_purchase_template(self, order_details: Dict[str, Any]) -> str:
        """Get purchase confirmation email HTML template"""
        product_name = order_details.get('product_name', 'N/A')
        amount = order_details.get('amount', 0) / 100
        currency = order_details.get('currency', 'GBP')
        currency_symbol = {'GBP': '£', 'USD': '$', 'EUR': '€'}.get(currency, currency)
        order_id = order_details.get('order_id', 'N/A')
        size = order_details.get('size', '')
        is_preorder = order_details.get('is_preorder', False)

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Order Confirmation - {self.brand_name}</title>
    <style>
        body {{ font-family: 'Georgia', serif; line-height: 1.6; color: #2a2a2a; background: #f8f6f0; max-width: 600px; margin: 0 auto; padding: 24px; }}
        .container {{ background: #fff; border: 1px solid #d4c5a0; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
        .header {{ background: #2a2a2a; color: #f8f6f0; padding: 32px; text-align: center; }}
        .content {{ background: #fff; padding: 40px 32px; color: #2a2a2a; }}
        .footer {{ background: #f8f6f0; padding: 24px; text-align: center; font-size: 13px; color: #666; border-top: 1px solid #d4c5a0; }}
        h1 {{ font-size: 24px; margin: 0 0 8px 0; font-weight: normal; letter-spacing: 2px; }}
        h2 {{ font-size: 20px; margin: 0 0 24px 0; font-weight: normal; color: #4a4a4a; }}
        p {{ font-size: 16px; margin: 16px 0; line-height: 1.7; }}
        .order-summary {{ background: #f8f6f0; padding: 24px; margin: 24px 0; border-left: 4px solid #2a2a2a; }}
        .order-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e0d5b7; font-size: 15px; }}
        .order-row:last-child {{ border-bottom: none; font-weight: bold; padding-top: 16px; font-size: 18px; color: #2a2a2a; }}
        .order-row span:first-child {{ color: #666; }}
        a {{ color: #2a2a2a; text-decoration: underline; }}
        .divider {{ border-top: 1px solid #e0d5b7; margin: 32px 0; }}
        .shipping-info {{ background: #f8f6f0; padding: 20px; margin: 24px 0; }}
        .shipping-info h3 {{ margin: 0 0 12px 0; font-size: 16px; color: #2a2a2a; }}
        .shipping-info p {{ margin: 8px 0; font-size: 14px; }}
        .preorder-notice {{ background: #fff3cd; border: 1px solid #ffecb5; padding: 16px; margin: 16px 0; border-radius: 4px; }}
        .preorder-notice h4 {{ margin: 0 0 12px 0; color: #856404; }}
        .preorder-notice p {{ margin: 8px 0; font-size: 14px; color: #856404; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>ORDER CONFIRMATION</h1>
            <p>{self.brand_name}</p>
        </div>

        <div class="content">
            <h2>Thank you for your purchase!</h2>

            <p>Your order has been successfully received and will be processed with care.</p>

            <div class="order-summary">
                <div class="order-row">
                    <span>Order ID:</span>
                    <span><strong>{order_id}</strong></span>
                </div>
                <div class="order-row">
                    <span>Product:</span>
                    <span>{product_name}</span>
                </div>
                {f'<div class="order-row"><span>Size:</span><span>{size}</span></div>' if size else ''}
                <div class="order-row">
                    <span>Total:</span>
                    <span>{currency_symbol}{amount:.2f}</span>
                </div>
            </div>

            <div class="shipping-info">
                <h3>Shipping Information</h3>
                {f'''
                <div class="preorder-notice">
                    <h4>Pre-Order Information</h4>
                    <p><strong>This is a pre-order purchase.</strong> We will update you via email about when your item will be shipped.</p>
                </div>
                ''' if is_preorder else ''}
                <p>Processing time: {('We will update you with shipping information' if is_preorder else '4-7 business days')}</p>
                <p>You will receive {'updates via email about shipping status' if is_preorder else 'a tracking number via email once your order ships'}.</p>
            </div>

            <div class="divider"></div>

            <p>If you have any questions, please contact our support team.</p>

            <p style="text-align: center; margin-top: 32px;">
                <a href="mailto:{self.support_email}" style="display: inline-block; background: #2a2a2a; color: #f8f6f0; padding: 12px 24px; text-decoration: none; font-weight: bold;">Contact Support</a>
            </p>
        </div>

        <div class="footer">
            <p>{self.brand_name} . {datetime.now().year}</p>
            <p><a href="{self.website_url}">Website</a> | <a href="mailto:{self.support_email}">Support</a></p>
        </div>
    </div>
</body>
</html>
        """

    # ==================== Shipping Notification ====================

    def send_shipping_notification(self, email: str, customer_name: str,
                                   order_id: int, tracking_number: Optional[str],
                                   items_text: str) -> bool:
        """Send shipping notification email to customer"""
        subject = f"Your {self.brand_name} Order Has Shipped!"

        html_body = self._get_shipping_template(customer_name, order_id, tracking_number, items_text)

        newline = '\n'
        tracking_info = f'Tracking Information:{newline}{tracking_number}{newline}{newline}You can track your order using the tracking number above.' if tracking_number else 'Your order is on its way! You will receive tracking information shortly.'

        text_body = f"""
Hi {customer_name},

Great news! Your order from {self.brand_name} has shipped!

Order Details:
- Order ID: ORD-{str(order_id).zfill(6)}
- Items:
{items_text}

{tracking_info}

Your package should arrive within 2-3 business days depending on your location.

If you have any questions, please contact our support team at {self.support_email}.

Best regards,
The {self.brand_name} Team
        """

        return self.send_email([email], subject, html_body, text_body)

    def _get_shipping_template(self, customer_name: str, order_id: int,
                              tracking_number: Optional[str], items_text: str) -> str:
        """Get shipping notification email HTML template"""
        items_html = items_text.replace('\n', '<br>')

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 0; background-color: #f4f4f4; }}
        .container {{ background-color: white; margin: 20px; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #2a2a2a 0%, #4a4a4a 100%); color: #f8f6f0; padding: 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 28px; }}
        .content {{ padding: 30px; }}
        .success-badge {{ background: #d4edda; border: 1px solid #c3e6cb; color: #155724; padding: 16px; margin: 16px 0; border-radius: 4px; text-align: center; font-weight: bold; }}
        .order-details {{ background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 6px; border-left: 4px solid #28a745; }}
        .order-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e9ecef; }}
        .order-row:last-child {{ border-bottom: none; }}
        .tracking-box {{ background: #fff3cd; border: 1px solid #ffeaa7; padding: 16px; margin: 20px 0; border-radius: 4px; text-align: center; }}
        .tracking-number {{ font-family: 'Courier New', monospace; font-size: 18px; font-weight: bold; color: #856404; background: white; padding: 12px; border-radius: 4px; margin: 12px 0; letter-spacing: 1px; }}
        .divider {{ border-top: 1px solid #e9ecef; margin: 24px 0; }}
        .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #6c757d; font-size: 14px; }}
        .footer a {{ color: #007bff; text-decoration: none; }}
        .btn {{ display: inline-block; background: #28a745; color: white; padding: 12px 24px; text-decoration: none; font-weight: bold; border-radius: 4px; margin: 16px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Your Order Has Shipped!</h1>
        </div>

        <div class="content">
            <p>Hi {customer_name},</p>

            <div class="success-badge">
                Your {self.brand_name} order is on its way!
            </div>

            <div class="order-details">
                <h3 style="margin-top: 0;">Order Information</h3>
                <div class="order-row">
                    <span>Order ID:</span>
                    <span><strong>ORD-{str(order_id).zfill(6)}</strong></span>
                </div>
                <div class="order-row">
                    <span>Items:</span>
                    <span>{items_html}</span>
                </div>
            </div>

            {f'''
            <div class="tracking-box">
                <h3 style="margin-top: 0; color: #856404;">Tracking Information</h3>
                <p>Track your order with the number below:</p>
                <div class="tracking-number">{tracking_number}</div>
                <p style="font-size: 14px; color: #856404;">Your package should arrive within 3-5 business days</p>
            </div>
            ''' if tracking_number else '''
            <div class="tracking-box">
                <h3 style="margin-top: 0; color: #856404;">On Its Way!</h3>
                <p>Your order is being prepared for delivery. You will receive tracking information shortly.</p>
            </div>
            '''}

            <div class="divider"></div>

            <p><strong>Estimated Delivery:</strong> 2-3 business days from shipment</p>
            <p>If you have any questions about your order, please don't hesitate to contact our support team.</p>

            <p style="text-align: center; margin-top: 32px;">
                <a href="mailto:{self.support_email}" class="btn">Contact Support</a>
            </p>
        </div>

        <div class="footer">
            <p>{self.brand_name} . {datetime.now().year}</p>
            <p><a href="{self.website_url}">Website</a> | <a href="mailto:{self.support_email}">Support</a></p>
        </div>
    </div>
</body>
</html>
        """

    # ==================== News Notification ====================

    def send_news_notification(self, subscribers: List[str], article: Dict[str, Any]) -> bool:
        """Send news notification to all subscribers"""
        subject = f"New Update: {article.get('title', f'{self.brand_name} News')}"

        html_body = self._get_news_template(article)
        text_body = f"""
New update from {self.brand_name}!

{article.get('title', 'Latest News')}

{article.get('excerpt', article.get('content', '')[:200] + '...')}

Read the full article: {self.website_url}/news/{article.get('slug', '')}

Best regards,
The {self.brand_name} Team

To unsubscribe, visit: {self.website_url}/unsubscribe
        """

        return self.send_email(subscribers, subject, html_body, text_body)

    def _get_news_template(self, article: Dict[str, Any]) -> str:
        """Get news notification email HTML template"""
        title = article.get('title', 'Latest News')
        excerpt = article.get('excerpt', article.get('content', '')[:320] + '...')
        article_url = f"{self.website_url}/news/{article.get('slug', '')}"
        date = article.get('date', datetime.now().strftime('%B %d, %Y'))

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - {self.brand_name}</title>
    <style>
        body {{ font-family: 'Georgia', serif; line-height: 1.6; color: #2a2a2a; background: #f8f6f0; max-width: 600px; margin: 0 auto; padding: 24px; }}
        .container {{ background: #fff; border: 1px solid #d4c5a0; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
        .header {{ background: #2a2a2a; color: #f8f6f0; padding: 32px; text-align: center; }}
        .content {{ background: #fff; padding: 40px 32px; color: #2a2a2a; }}
        .footer {{ background: #f8f6f0; padding: 24px; text-align: center; font-size: 13px; color: #666; border-top: 1px solid #d4c5a0; }}
        h1 {{ font-size: 24px; margin: 0 0 8px 0; font-weight: normal; letter-spacing: 2px; }}
        h2 {{ font-size: 22px; margin: 0 0 16px 0; font-weight: normal; color: #2a2a2a; line-height: 1.3; }}
        p {{ font-size: 16px; margin: 16px 0; line-height: 1.7; }}
        .date {{ font-size: 14px; color: #666; margin-bottom: 24px; font-style: italic; }}
        .article-preview {{ background: #f8f6f0; padding: 24px; margin: 24px 0; border-left: 4px solid #2a2a2a; }}
        .article-preview p {{ font-size: 15px; line-height: 1.6; margin: 0; }}
        a {{ color: #2a2a2a; text-decoration: underline; }}
        .divider {{ border-top: 1px solid #e0d5b7; margin: 32px 0; }}
        .cta-section {{ text-align: center; margin: 32px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{self.brand_name.upper()}</h1>
            <p>Latest News Update</p>
        </div>

        <div class="content">
            <h2>{title}</h2>
            <div class="date">{date}</div>

            <div class="article-preview">
                <p>{excerpt}</p>
            </div>

            <div class="cta-section">
                <a href="{article_url}" style="display: inline-block; background: #2a2a2a; color: #f8f6f0; padding: 14px 28px; text-decoration: none; font-weight: bold; font-size: 16px;">Read Full Article</a>
            </div>

            <div class="divider"></div>

            <p>Stay connected and never miss an important update.</p>
        </div>

        <div class="footer">
            <p>{self.brand_name} News . {datetime.now().year}</p>
            <p><a href="{self.website_url}/unsubscribe">Unsubscribe</a> | <a href="{self.website_url}">Website</a></p>
        </div>
    </div>
</body>
</html>
        """

    # ==================== Admin Notifications ====================

    def send_admin_order_notification(self, order_details: Dict[str, Any]) -> bool:
        """Send order notification to admin"""
        if not self.admin_email:
            logger.warning("Admin email not configured - skipping admin notification")
            return False

        subject = f"New Order Alert - {self.brand_name}"

        customer_email = order_details.get('customer_email', 'N/A')
        customer_name = order_details.get('customer_name', 'N/A')
        product_name = order_details.get('product_name', 'N/A')
        amount = order_details.get('amount', 0)
        currency = order_details.get('currency', 'GBP')
        currency_symbol = {'GBP': '£', 'USD': '$', 'EUR': '€'}.get(currency, currency)
        order_id = order_details.get('order_id', 'N/A')
        size = order_details.get('size', 'N/A')
        shipping_address = order_details.get('shipping_address', 'N/A')

        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #dc3545;">New Order Received!</h2>

            <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                <h3>Order Details:</h3>
                <p><strong>Order ID:</strong> {order_id}</p>
                <p><strong>Product:</strong> {product_name}</p>
                <p><strong>Size:</strong> {size}</p>
                <p><strong>Amount:</strong> {currency_symbol}{amount / 100:.2f}</p>
            </div>

            <div style="background: #e9ecef; padding: 20px; border-radius: 5px; margin: 20px 0;">
                <h3>Customer Details:</h3>
                <p><strong>Name:</strong> {customer_name}</p>
                <p><strong>Email:</strong> {customer_email}</p>
                <p><strong>Shipping:</strong> {shipping_address}</p>
            </div>

            <p style="color: #6c757d; font-size: 12px;">
                This is an automated notification from {self.brand_name}.
            </p>
        </div>
        """

        text_body = f"""
NEW ORDER ALERT

Order Details:
- Order ID: {order_id}
- Product: {product_name}
- Size: {size}
- Amount: {currency_symbol}{amount / 100:.2f}

Customer Details:
- Name: {customer_name}
- Email: {customer_email}
- Shipping: {shipping_address}

---
{self.brand_name}
        """

        return self.send_email([self.admin_email], subject, html_body, text_body)

    def send_admin_subscriber_notification(self, subscriber_details: Dict[str, Any]) -> bool:
        """Send new subscriber notification to admin"""
        if not self.admin_email:
            logger.warning("Admin email not configured - skipping admin notification")
            return False

        subject = f"New Newsletter Subscriber - {self.brand_name}"

        email = subscriber_details.get('email', 'N/A')
        subscribed_at = subscriber_details.get('subscribed_at', 'N/A')
        ip_address = subscriber_details.get('ip_address', 'N/A')
        user_agent = subscriber_details.get('user_agent', 'N/A')
        source = subscriber_details.get('source', 'website')

        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #007bff;">New Newsletter Subscriber!</h2>

            <div style="background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                <h3>Subscriber Details:</h3>
                <p><strong>Email:</strong> {email}</p>
                <p><strong>Subscribed:</strong> {subscribed_at}</p>
                <p><strong>Source:</strong> {source}</p>
            </div>

            <div style="background: #e9ecef; padding: 20px; border-radius: 5px; margin: 20px 0;">
                <h3>Technical Details:</h3>
                <p><strong>IP Address:</strong> {ip_address}</p>
                <p><strong>User Agent:</strong> {user_agent[:100]}{'...' if len(user_agent) > 100 else ''}</p>
            </div>

            <p style="color: #6c757d; font-size: 12px;">
                This is an automated notification from {self.brand_name} Newsletter.
            </p>
        </div>
        """

        text_body = f"""
NEW NEWSLETTER SUBSCRIBER

Subscriber Details:
- Email: {email}
- Subscribed: {subscribed_at}
- Source: {source}

Technical Details:
- IP Address: {ip_address}
- User Agent: {user_agent[:100]}{'...' if len(user_agent) > 100 else ''}

---
{self.brand_name} Newsletter
        """

        return self.send_email([self.admin_email], subject, html_body, text_body)

    def send_admin_shipping_notification(self, order_id: int,
                                        customer_email: str, tracking_number: Optional[str],
                                        items_text: str) -> bool:
        """Send shipping notification to admin"""
        if not self.admin_email:
            logger.warning("Admin email not configured - skipping admin notification")
            return False

        subject = f"Order Shipped - ORD-{str(order_id).zfill(6)}"

        items_html = items_text.replace('\n', '<br>')
        tracking_html = f'<p><strong>Tracking:</strong> {tracking_number}</p>' if tracking_number else '<p><em>Tracking number not yet available</em></p>'

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: #2a2a2a; color: #f8f6f0; padding: 20px; text-align: center;">
        <h1 style="margin: 0; font-size: 24px;">Order Shipped</h1>
    </div>

    <div style="padding: 20px; background: #f9f9f9;">
        <h2>Order ORD-{str(order_id).zfill(6)} Has Shipped</h2>

        <div style="background: white; padding: 16px; margin: 16px 0; border-radius: 4px; border-left: 4px solid #28a745;">
            <p><strong>Customer:</strong> {customer_email}</p>
            <p><strong>Order ID:</strong> ORD-{str(order_id).zfill(6)}</p>
            <p><strong>Items:</strong><br>{items_html}</p>
            {tracking_html}
        </div>

        <p style="color: #666; font-size: 14px;">This is an automated notification from {self.brand_name}.</p>
    </div>
</body>
</html>
        """

        text_body = f"""
Order Shipped - ORD-{str(order_id).zfill(6)}

Customer: {customer_email}
Order ID: ORD-{str(order_id).zfill(6)}
Items:
{items_text}

{'Tracking: ' + tracking_number if tracking_number else 'Tracking number not yet available'}

This is an automated notification from {self.brand_name}.
        """

        return self.send_email([self.admin_email], subject, html_body, text_body)


# Global email service instance
email_service = EmailService()
