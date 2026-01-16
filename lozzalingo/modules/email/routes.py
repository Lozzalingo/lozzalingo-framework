"""
Email Preview Routes
====================

Blueprint for previewing email templates in development.
Access at /admin/email-preview/ when registered.
"""

from flask import Blueprint, render_template_string, session, redirect, url_for, current_app
from datetime import datetime

email_preview_bp = Blueprint(
    'email_preview',
    __name__,
    url_prefix='/admin/email-preview'
)


def get_email_service():
    """Get email service instance with current app config"""
    from .email_service import EmailService
    service = EmailService()
    service.init_app(current_app)
    return service


def require_admin(f):
    """Decorator to require admin login"""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin.login', next=f'/admin/email-preview/'))
        return f(*args, **kwargs)
    return decorated_function


@email_preview_bp.route('/')
@require_admin
def preview_index():
    """Email preview index page"""
    email_service = get_email_service()
    brand_name = email_service.brand_name

    return f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Email Preview - {brand_name}</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --noir-black: #0a0a0a;
                --noir-charcoal: #1a1a1a;
                --noir-dark: #2a2a2a;
                --noir-gray: #3a3a3a;
                --noir-light-gray: #666666;
                --noir-white: #ffffff;
                --accent-green: #2d5016;
                --accent-blue: #1a4d2e;
            }}

            * {{ margin: 0; padding: 0; box-sizing: border-box; }}

            body {{
                background: var(--noir-black);
                color: var(--noir-white);
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                line-height: 1.6;
                min-height: 100vh;
                overflow-x: hidden;
            }}

            .container {{
                max-width: 1200px;
                margin: 0 auto;
                padding: 60px 40px;
            }}

            .header {{
                margin-bottom: 60px;
                border-bottom: 1px solid var(--noir-gray);
                padding-bottom: 40px;
            }}

            .title {{
                font-family: 'Space Grotesk', sans-serif;
                font-size: 2.5rem;
                font-weight: 600;
                letter-spacing: -0.02em;
                margin-bottom: 12px;
                background: linear-gradient(135deg, var(--noir-white), var(--noir-light-gray));
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }}

            .subtitle {{
                font-size: 1rem;
                color: var(--noir-light-gray);
                font-weight: 400;
                letter-spacing: 0.01em;
            }}

            .back-link {{
                display: inline-block;
                margin-bottom: 20px;
                color: var(--noir-light-gray);
                text-decoration: none;
                font-size: 0.9rem;
            }}
            .back-link:hover {{ color: var(--noir-white); }}

            .preview-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 20px;
                margin-top: 40px;
            }}

            .preview-card {{
                background: var(--noir-charcoal);
                border: 1px solid var(--noir-gray);
                border-radius: 8px;
                overflow: hidden;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                text-decoration: none;
                color: inherit;
                position: relative;
            }}

            .preview-card:hover {{
                border-color: var(--accent-green);
                transform: translateY(-2px);
                box-shadow: 0 8px 32px rgba(45, 80, 22, 0.2);
            }}

            .card-header {{
                padding: 20px 24px 16px;
                border-bottom: 1px solid var(--noir-gray);
            }}

            .card-icon {{
                font-size: 1.2rem;
                margin-bottom: 8px;
                display: block;
            }}

            .card-title {{
                font-family: 'Space Grotesk', sans-serif;
                font-size: 0.95rem;
                font-weight: 500;
                letter-spacing: -0.01em;
                margin-bottom: 4px;
            }}

            .card-desc {{
                font-size: 0.85rem;
                color: var(--noir-light-gray);
                font-weight: 400;
            }}

            .card-footer {{
                padding: 16px 24px;
                background: var(--noir-dark);
                font-size: 0.8rem;
                color: var(--noir-light-gray);
                text-transform: uppercase;
                letter-spacing: 0.05em;
                font-weight: 500;
            }}

            .preview-card.primary {{
                border-color: var(--accent-green);
                background: linear-gradient(135deg, var(--noir-charcoal), #1e2d1a);
            }}

            .preview-card.primary .card-header {{
                border-color: var(--accent-green);
            }}

            .preview-card.warning {{
                border-color: #b45309;
                background: linear-gradient(135deg, var(--noir-charcoal), #2d1a0a);
            }}

            .preview-card.warning .card-header {{
                border-color: #b45309;
            }}

            @media (max-width: 768px) {{
                .container {{ padding: 40px 20px; }}
                .title {{ font-size: 2rem; }}
                .preview-grid {{ grid-template-columns: 1fr; gap: 16px; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/admin/dashboard" class="back-link">&larr; Back to Admin Dashboard</a>
            <div class="header">
                <h1 class="title">Email Templates</h1>
                <p class="subtitle">Preview and test email templates for {brand_name}</p>
            </div>

            <div class="preview-grid">
                <a href="/admin/email-preview/test-send" class="preview-card primary">
                    <div class="card-header">
                        <span class="card-icon">&#128640;</span>
                        <h3 class="card-title">Send Test Email</h3>
                        <p class="card-desc">Dispatch test emails to verify delivery</p>
                    </div>
                    <div class="card-footer">Live Test</div>
                </a>

                <a href="/admin/email-preview/welcome" class="preview-card">
                    <div class="card-header">
                        <span class="card-icon">&#128075;</span>
                        <h3 class="card-title">Welcome Email</h3>
                        <p class="card-desc">New subscriber onboarding template</p>
                    </div>
                    <div class="card-footer">Template Preview</div>
                </a>

                <a href="/admin/email-preview/welcome/John%20Doe" class="preview-card">
                    <div class="card-header">
                        <span class="card-icon">&#127919;</span>
                        <h3 class="card-title">Welcome Email (Custom)</h3>
                        <p class="card-desc">Personalized welcome with custom name</p>
                    </div>
                    <div class="card-footer">Template Preview</div>
                </a>

                <a href="/admin/email-preview/purchase" class="preview-card">
                    <div class="card-header">
                        <span class="card-icon">&#128231;</span>
                        <h3 class="card-title">Purchase Confirmation</h3>
                        <p class="card-desc">Aight Clothing order confirmation</p>
                    </div>
                    <div class="card-footer">Template Preview</div>
                </a>

                <a href="/admin/email-preview/purchase-preorder" class="preview-card">
                    <div class="card-header">
                        <span class="card-icon">&#9200;</span>
                        <h3 class="card-title">Pre-Order Confirmation</h3>
                        <p class="card-desc">Aight Clothing pre-order confirmation</p>
                    </div>
                    <div class="card-footer">Template Preview</div>
                </a>

                <a href="/admin/email-preview/news" class="preview-card">
                    <div class="card-header">
                        <span class="card-icon">&#128240;</span>
                        <h3 class="card-title">News Notification</h3>
                        <p class="card-desc">Newsletter and updates template</p>
                    </div>
                    <div class="card-footer">Template Preview</div>
                </a>

                <a href="/admin/email-preview/shipping" class="preview-card">
                    <div class="card-header">
                        <span class="card-icon">&#128230;</span>
                        <h3 class="card-title">Shipping Confirmation</h3>
                        <p class="card-desc">Order shipped with tracking information</p>
                    </div>
                    <div class="card-footer">Template Preview</div>
                </a>

                <a href="/admin/email-preview/admin-order" class="preview-card warning">
                    <div class="card-header">
                        <span class="card-icon">&#128722;</span>
                        <h3 class="card-title">Admin Order Alert</h3>
                        <p class="card-desc">Admin notification for new orders</p>
                    </div>
                    <div class="card-footer">Sends Live Email</div>
                </a>

                <a href="/admin/email-preview/admin-subscriber" class="preview-card warning">
                    <div class="card-header">
                        <span class="card-icon">&#128231;</span>
                        <h3 class="card-title">Admin Subscriber Alert</h3>
                        <p class="card-desc">Admin notification for new subscribers</p>
                    </div>
                    <div class="card-footer">Sends Live Email</div>
                </a>

                <a href="/admin/email-preview/credit-purchase" class="preview-card">
                    <div class="card-header">
                        <span class="card-icon">&#128176;</span>
                        <h3 class="card-title">Credit Purchase</h3>
                        <p class="card-desc">Crowd Sauced credit purchase confirmation</p>
                    </div>
                    <div class="card-footer">Template Preview</div>
                </a>

                <a href="/admin/email-preview/subscription" class="preview-card">
                    <div class="card-header">
                        <span class="card-icon">&#11088;</span>
                        <h3 class="card-title">Subscription Confirmation</h3>
                        <p class="card-desc">Crowd Sauced Premium subscription</p>
                    </div>
                    <div class="card-footer">Template Preview</div>
                </a>

                <a href="/admin/email-preview/subscription-renewal" class="preview-card">
                    <div class="card-header">
                        <span class="card-icon">&#128260;</span>
                        <h3 class="card-title">Subscription Renewal</h3>
                        <p class="card-desc">Monthly subscription renewal email</p>
                    </div>
                    <div class="card-footer">Template Preview</div>
                </a>
            </div>
        </div>
    </body>
    </html>
    '''


@email_preview_bp.route('/welcome')
@email_preview_bp.route('/welcome/<name>')
@require_admin
def preview_welcome(name="Friend"):
    """Preview welcome email template"""
    email_service = get_email_service()
    html_content = email_service._get_welcome_template(name)
    return render_template_string(html_content)


@email_preview_bp.route('/purchase')
@require_admin
def preview_purchase():
    """Preview purchase confirmation email template (Aight Clothing order)"""
    sample_order = {
        'product_name': 'Aight Clothing Official T-Shirt',
        'amount': 2999,
        'currency': 'GBP',
        'order_id': f'ORD-{datetime.now().year}-001',
        'size': 'Large',
        'is_preorder': False
    }

    # Use Aight Clothing branding
    product_name = sample_order.get('product_name', 'N/A')
    amount = sample_order.get('amount', 0) / 100
    currency_symbol = '£'
    order_id = sample_order.get('order_id', 'N/A')
    size = sample_order.get('size', '')

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Order Confirmation - Aight Clothing</title>
    <!--[if mso]>
    <style type="text/css">
        body, table, td {{font-family: Arial, sans-serif !important;}}
    </style>
    <![endif]-->
</head>
<body style="margin: 0; padding: 0; background-color: #f5f5f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f5f5f5;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="background-color: #ffffff; max-width: 600px; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);">

                    <!-- Header -->
                    <tr>
                        <td style="background-color: #1a1a1a; padding: 32px 40px; text-align: center;">
                            <h1 style="margin: 0; font-size: 11px; font-weight: 600; letter-spacing: 3px; text-transform: uppercase; color: #666666;">Order Confirmation</h1>
                            <p style="margin: 16px 0 0 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px; color: #ffffff;">AI-GHT CLOTHING</p>
                        </td>
                    </tr>

                    <!-- Main Content -->
                    <tr>
                        <td style="padding: 48px 40px;">
                            <h2 style="margin: 0 0 8px 0; font-size: 24px; font-weight: 700; color: #1a1a1a; letter-spacing: -0.5px;">Thank you for your order.</h2>
                            <p style="margin: 0 0 32px 0; font-size: 15px; color: #666666; line-height: 1.6;">We've received your order and will begin processing it shortly.</p>

                            <!-- Order Details Box -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #fafafa; border: 1px solid #e5e5e5; border-radius: 8px; margin-bottom: 32px;">
                                <tr>
                                    <td style="padding: 24px;">
                                        <p style="margin: 0 0 16px 0; font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: #999999;">Order Details</p>

                                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                            <tr>
                                                <td style="padding: 12px 0; border-bottom: 1px solid #e5e5e5;">
                                                    <span style="font-size: 13px; color: #666666;">Order ID</span>
                                                </td>
                                                <td style="padding: 12px 0; border-bottom: 1px solid #e5e5e5; text-align: right;">
                                                    <span style="font-size: 13px; font-weight: 600; color: #1a1a1a; font-family: monospace;">{order_id}</span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 12px 0; border-bottom: 1px solid #e5e5e5;">
                                                    <span style="font-size: 13px; color: #666666;">Product</span>
                                                </td>
                                                <td style="padding: 12px 0; border-bottom: 1px solid #e5e5e5; text-align: right;">
                                                    <span style="font-size: 13px; font-weight: 500; color: #1a1a1a;">{product_name}</span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 12px 0; border-bottom: 1px solid #e5e5e5;">
                                                    <span style="font-size: 13px; color: #666666;">Size</span>
                                                </td>
                                                <td style="padding: 12px 0; border-bottom: 1px solid #e5e5e5; text-align: right;">
                                                    <span style="font-size: 13px; font-weight: 500; color: #1a1a1a;">{size}</span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 16px 0 0 0;">
                                                    <span style="font-size: 14px; font-weight: 600; color: #1a1a1a;">Total</span>
                                                </td>
                                                <td style="padding: 16px 0 0 0; text-align: right;">
                                                    <span style="font-size: 20px; font-weight: 700; color: #1a1a1a;">{currency_symbol}{amount:.2f}</span>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <!-- Shipping Info -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #1a1a1a; border-radius: 8px; margin-bottom: 32px;">
                                <tr>
                                    <td style="padding: 24px;">
                                        <p style="margin: 0 0 12px 0; font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: #666666;">What Happens Next</p>
                                        <p style="margin: 0 0 8px 0; font-size: 14px; color: #ffffff; line-height: 1.6;"><strong style="color: #999999;">1.</strong> Your order is being processed</p>
                                        <p style="margin: 0 0 8px 0; font-size: 14px; color: #ffffff; line-height: 1.6;"><strong style="color: #999999;">2.</strong> Production takes 4-7 business days</p>
                                        <p style="margin: 0; font-size: 14px; color: #ffffff; line-height: 1.6;"><strong style="color: #999999;">3.</strong> We'll email you tracking info when shipped</p>
                                    </td>
                                </tr>
                            </table>

                            <!-- CTA Button -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td align="center">
                                        <a href="https://aightclothing.laurence.computer" style="display: inline-block; background-color: #1a1a1a; color: #ffffff; text-decoration: none; font-size: 13px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; padding: 16px 32px; border-radius: 6px;">Continue Shopping</a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #fafafa; padding: 32px 40px; border-top: 1px solid #e5e5e5;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td align="center">
                                        <p style="margin: 0 0 8px 0; font-size: 13px; font-weight: 600; color: #1a1a1a;">AI-GHT CLOTHING</p>
                                        <p style="margin: 0 0 16px 0; font-size: 12px; color: #999999;">Unique AI-designed apparel</p>
                                        <p style="margin: 0; font-size: 12px; color: #999999;">
                                            <a href="https://aightclothing.laurence.computer" style="color: #666666; text-decoration: none;">Website</a>
                                            <span style="margin: 0 8px; color: #cccccc;">|</span>
                                            <a href="mailto:aight@send.laurence.computer" style="color: #666666; text-decoration: none;">Support</a>
                                        </p>
                                        <p style="margin: 16px 0 0 0; font-size: 11px; color: #cccccc;">&copy; {datetime.now().year} Aight Clothing. All rights reserved.</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>
    """
    return render_template_string(html_content)


@email_preview_bp.route('/purchase-preorder')
@require_admin
def preview_purchase_preorder():
    """Preview purchase confirmation email template (Aight Clothing pre-order)"""
    sample_order = {
        'product_name': 'Aight Clothing Limited Edition T-Shirt',
        'amount': 3499,
        'currency': 'GBP',
        'order_id': f'ORD-{datetime.now().year}-002',
        'size': 'XL',
        'is_preorder': True
    }

    # Use Aight Clothing branding
    product_name = sample_order.get('product_name', 'N/A')
    amount = sample_order.get('amount', 0) / 100
    currency_symbol = '£'
    order_id = sample_order.get('order_id', 'N/A')
    size = sample_order.get('size', '')

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pre-Order Confirmation - Aight Clothing</title>
    <!--[if mso]>
    <style type="text/css">
        body, table, td {{font-family: Arial, sans-serif !important;}}
    </style>
    <![endif]-->
</head>
<body style="margin: 0; padding: 0; background-color: #f5f5f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f5f5f5;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="background-color: #ffffff; max-width: 600px; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);">

                    <!-- Header -->
                    <tr>
                        <td style="background-color: #1a1a1a; padding: 32px 40px; text-align: center;">
                            <h1 style="margin: 0; font-size: 11px; font-weight: 600; letter-spacing: 3px; text-transform: uppercase; color: #666666;">Pre-Order Confirmation</h1>
                            <p style="margin: 16px 0 0 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px; color: #ffffff;">AI-GHT CLOTHING</p>
                        </td>
                    </tr>

                    <!-- Status Bar -->
                    <tr>
                        <td style="background-color: #f59e0b; padding: 12px 40px; text-align: center;">
                            <p style="margin: 0; font-size: 13px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; color: #ffffff;">Pre-Order Confirmed</p>
                        </td>
                    </tr>

                    <!-- Main Content -->
                    <tr>
                        <td style="padding: 48px 40px;">
                            <h2 style="margin: 0 0 8px 0; font-size: 24px; font-weight: 700; color: #1a1a1a; letter-spacing: -0.5px;">Thank you for your pre-order.</h2>
                            <p style="margin: 0 0 32px 0; font-size: 15px; color: #666666; line-height: 1.6;">You've secured your item. We'll notify you when it's ready to ship.</p>

                            <!-- Pre-Order Notice -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; margin-bottom: 24px;">
                                <tr>
                                    <td style="padding: 20px 24px;">
                                        <p style="margin: 0 0 8px 0; font-size: 14px; font-weight: 600; color: #92400e;">Pre-Order Item</p>
                                        <p style="margin: 0; font-size: 13px; color: #a16207; line-height: 1.5;">This item is currently in production. We'll email you with shipping updates and tracking info once your order is on its way.</p>
                                    </td>
                                </tr>
                            </table>

                            <!-- Order Details Box -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #fafafa; border: 1px solid #e5e5e5; border-radius: 8px; margin-bottom: 32px;">
                                <tr>
                                    <td style="padding: 24px;">
                                        <p style="margin: 0 0 16px 0; font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: #999999;">Order Details</p>

                                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                            <tr>
                                                <td style="padding: 12px 0; border-bottom: 1px solid #e5e5e5;">
                                                    <span style="font-size: 13px; color: #666666;">Order ID</span>
                                                </td>
                                                <td style="padding: 12px 0; border-bottom: 1px solid #e5e5e5; text-align: right;">
                                                    <span style="font-size: 13px; font-weight: 600; color: #1a1a1a; font-family: monospace;">{order_id}</span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 12px 0; border-bottom: 1px solid #e5e5e5;">
                                                    <span style="font-size: 13px; color: #666666;">Product</span>
                                                </td>
                                                <td style="padding: 12px 0; border-bottom: 1px solid #e5e5e5; text-align: right;">
                                                    <span style="font-size: 13px; font-weight: 500; color: #1a1a1a;">{product_name}</span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 12px 0; border-bottom: 1px solid #e5e5e5;">
                                                    <span style="font-size: 13px; color: #666666;">Size</span>
                                                </td>
                                                <td style="padding: 12px 0; border-bottom: 1px solid #e5e5e5; text-align: right;">
                                                    <span style="font-size: 13px; font-weight: 500; color: #1a1a1a;">{size}</span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 16px 0 0 0;">
                                                    <span style="font-size: 14px; font-weight: 600; color: #1a1a1a;">Total</span>
                                                </td>
                                                <td style="padding: 16px 0 0 0; text-align: right;">
                                                    <span style="font-size: 20px; font-weight: 700; color: #1a1a1a;">{currency_symbol}{amount:.2f}</span>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <!-- Timeline -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #1a1a1a; border-radius: 8px; margin-bottom: 32px;">
                                <tr>
                                    <td style="padding: 24px;">
                                        <p style="margin: 0 0 12px 0; font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: #666666;">What Happens Next</p>
                                        <p style="margin: 0 0 8px 0; font-size: 14px; color: #ffffff; line-height: 1.6;"><strong style="color: #f59e0b;">1.</strong> Your pre-order is secured</p>
                                        <p style="margin: 0 0 8px 0; font-size: 14px; color: #ffffff; line-height: 1.6;"><strong style="color: #f59e0b;">2.</strong> We'll email updates on production status</p>
                                        <p style="margin: 0; font-size: 14px; color: #ffffff; line-height: 1.6;"><strong style="color: #f59e0b;">3.</strong> You'll get tracking info when shipped</p>
                                    </td>
                                </tr>
                            </table>

                            <!-- CTA Button -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td align="center">
                                        <a href="https://aightclothing.laurence.computer" style="display: inline-block; background-color: #1a1a1a; color: #ffffff; text-decoration: none; font-size: 13px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; padding: 16px 32px; border-radius: 6px;">Continue Shopping</a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #fafafa; padding: 32px 40px; border-top: 1px solid #e5e5e5;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td align="center">
                                        <p style="margin: 0 0 8px 0; font-size: 13px; font-weight: 600; color: #1a1a1a;">AI-GHT CLOTHING</p>
                                        <p style="margin: 0 0 16px 0; font-size: 12px; color: #999999;">Unique AI-designed apparel</p>
                                        <p style="margin: 0; font-size: 12px; color: #999999;">
                                            <a href="https://aightclothing.laurence.computer" style="color: #666666; text-decoration: none;">Website</a>
                                            <span style="margin: 0 8px; color: #cccccc;">|</span>
                                            <a href="mailto:aight@send.laurence.computer" style="color: #666666; text-decoration: none;">Support</a>
                                        </p>
                                        <p style="margin: 16px 0 0 0; font-size: 11px; color: #cccccc;">&copy; {datetime.now().year} Aight Clothing. All rights reserved.</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>
    """
    return render_template_string(html_content)


@email_preview_bp.route('/news')
@require_admin
def preview_news():
    """Preview news notification email template"""
    email_service = get_email_service()

    sample_article = {
        'title': f'Big News from {email_service.brand_name}',
        'excerpt': 'We are excited to share some incredible news with you. This update showcases our latest achievements and upcoming plans that we think you will love...',
        'slug': 'sample-news-123',
        'date': datetime.now().strftime('%Y-%m-%d')
    }

    html_content = email_service._get_news_template(sample_article)
    return render_template_string(html_content)


@email_preview_bp.route('/shipping')
@require_admin
def preview_shipping():
    """Preview shipping confirmation email template"""
    email_service = get_email_service()
    html_content = email_service._get_shipping_template(
        "John Doe",
        12345,
        "1234567890TRACK",
        f"* {email_service.brand_name} T-Shirt (Size: XL) x1\n* {email_service.brand_name} Hoodie (Size: L) x1"
    )
    return render_template_string(html_content)


@email_preview_bp.route('/test-send')
@require_admin
def test_send_email():
    """Send a test email to verify email service is working"""
    email_service = get_email_service()
    admin_email = session.get('admin_email', email_service.admin_email)

    if not admin_email:
        return f'''
        <h1 style="color: red;">Admin Email Not Configured</h1>
        <p>Please configure EMAIL_ADMIN_EMAIL in your app config or log in with an admin email.</p>
        <p><a href="/admin/email-preview/">&larr; Back to Email Previews</a></p>
        '''

    result = email_service.send_welcome_email(admin_email, "Test User")

    if result:
        return f'''
        <h1 style="color: green;">Test Email Sent Successfully!</h1>
        <p>Welcome email sent to: {admin_email}</p>
        <p><a href="/admin/email-preview/">&larr; Back to Email Previews</a></p>
        '''
    else:
        return f'''
        <h1 style="color: red;">Test Email Failed</h1>
        <p>Failed to send welcome email to: {admin_email}</p>
        <p>Check the server logs for error details.</p>
        <p><strong>Possible issues:</strong></p>
        <ul>
            <li>RESEND_API_KEY not configured</li>
            <li>EMAIL_ADDRESS not configured</li>
            <li>resend package not installed</li>
        </ul>
        <p><a href="/admin/email-preview/">&larr; Back to Email Previews</a></p>
        '''


@email_preview_bp.route('/admin-order')
@require_admin
def preview_admin_order():
    """Preview admin order notification email (sends actual email)"""
    email_service = get_email_service()

    sample_order_details = {
        'order_id': f'ORD-{datetime.now().year}-001',
        'product_name': f'{email_service.brand_name} Official T-Shirt',
        'amount': 3999,
        'currency': 'GBP',
        'size': 'Large',
        'customer_email': 'customer@example.com',
        'customer_name': 'John Doe',
        'shipping_address': '123 Example Street, London, UK, SW1A 1AA'
    }

    success = email_service.send_admin_order_notification(sample_order_details)

    color = 'green' if success else 'red'
    status = 'Admin Order Notification Sent!' if success else 'Failed to Send'
    message = f'Admin order notification sent to {email_service.admin_email}' if success else 'Check server logs for error details. Is EMAIL_ADMIN_EMAIL configured?'

    return f'''
    <h1 style="color: {color};">{status}</h1>
    <p>{message}</p>
    <p><strong>Sample Data Used:</strong></p>
    <ul>
        <li>Order ID: {sample_order_details['order_id']}</li>
        <li>Product: {sample_order_details['product_name']}</li>
        <li>Amount: GBP {sample_order_details['amount']/100:.2f}</li>
        <li>Customer: {sample_order_details['customer_name']}</li>
    </ul>
    <p><a href="/admin/email-preview/">&larr; Back to Email Previews</a></p>
    '''


@email_preview_bp.route('/admin-subscriber')
@require_admin
def preview_admin_subscriber():
    """Preview admin subscriber notification email (sends actual email)"""
    email_service = get_email_service()

    sample_subscriber_details = {
        'email': 'newfan@example.com',
        'subscribed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'ip_address': '192.168.1.100',
        'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'source': 'website'
    }

    success = email_service.send_admin_subscriber_notification(sample_subscriber_details)

    color = 'green' if success else 'red'
    status = 'Admin Subscriber Notification Sent!' if success else 'Failed to Send'
    message = f'Admin subscriber notification sent to {email_service.admin_email}' if success else 'Check server logs for error details. Is EMAIL_ADMIN_EMAIL configured?'

    return f'''
    <h1 style="color: {color};">{status}</h1>
    <p>{message}</p>
    <p><strong>Sample Data Used:</strong></p>
    <ul>
        <li>Email: {sample_subscriber_details['email']}</li>
        <li>Subscribed: {sample_subscriber_details['subscribed_at']}</li>
        <li>Source: {sample_subscriber_details['source']}</li>
        <li>IP: {sample_subscriber_details['ip_address']}</li>
    </ul>
    <p><a href="/admin/email-preview/">&larr; Back to Email Previews</a></p>
    '''


# ================================
# CROWD SAUCED SPECIFIC EMAILS
# ================================

@email_preview_bp.route('/credit-purchase')
@require_admin
def preview_credit_purchase():
    """Preview credit purchase confirmation email (Crowd Sauced)"""
    from datetime import datetime
    credits_purchased = 50
    amount_paid = 2249
    new_balance = 75
    amount_display = f"£{amount_paid / 100:.2f}"

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Credit Purchase Confirmation - Crowd Sauced</title>
    <!--[if mso]>
    <style type="text/css">
        body, table, td {{font-family: Georgia, serif !important;}}
    </style>
    <![endif]-->
</head>
<body style="margin: 0; padding: 0; background-color: #f7f5f0; font-family: Georgia, 'Times New Roman', serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f7f5f0;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="background-color: #ffffff; max-width: 600px; border: 3px solid #2c2c2c;">

                    <!-- Header -->
                    <tr>
                        <td style="background-color: #2c2c2c; padding: 32px 40px; text-align: center;">
                            <h1 style="margin: 0; font-size: 11px; font-weight: 400; letter-spacing: 3px; text-transform: uppercase; color: #d4a574;">Credit Purchase</h1>
                            <p style="margin: 12px 0 0 0; font-size: 28px; font-weight: 700; letter-spacing: 1px; color: #f7f5f0; font-family: Georgia, serif;">CROWD SAUCED</p>
                        </td>
                    </tr>

                    <!-- Decorative Line -->
                    <tr>
                        <td style="background-color: #d4a574; height: 4px;"></td>
                    </tr>

                    <!-- Main Content -->
                    <tr>
                        <td style="padding: 48px 40px;">
                            <h2 style="margin: 0 0 8px 0; font-size: 24px; font-weight: 700; color: #2c2c2c; font-family: Georgia, serif;">Thank you for your purchase!</h2>
                            <p style="margin: 0 0 32px 0; font-size: 15px; color: #6b6b6b; line-height: 1.7;">Your credits have been added to your account and are ready to use.</p>

                            <!-- Credits Display -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 32px;">
                                <tr>
                                    <td align="center" style="padding: 24px; background-color: #f7f5f0; border: 2px dashed #d4a574;">
                                        <p style="margin: 0 0 8px 0; font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: #6b6b6b;">New Balance</p>
                                        <p style="margin: 0; font-size: 48px; font-weight: 700; color: #2c2c2c; font-family: Georgia, serif;">{new_balance}</p>
                                        <p style="margin: 8px 0 0 0; font-size: 14px; color: #d4a574; text-transform: uppercase; letter-spacing: 1px;">credits</p>
                                    </td>
                                </tr>
                            </table>

                            <!-- Order Details Box -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f7f5f0; border-left: 4px solid #2c2c2c; margin-bottom: 32px;">
                                <tr>
                                    <td style="padding: 24px;">
                                        <p style="margin: 0 0 16px 0; font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: #6b6b6b;">Purchase Details</p>

                                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid #e0d5c0;">
                                                    <span style="font-size: 14px; color: #6b6b6b;">Credits Purchased</span>
                                                </td>
                                                <td style="padding: 10px 0; border-bottom: 1px solid #e0d5c0; text-align: right;">
                                                    <span style="font-size: 14px; font-weight: 600; color: #2c2c2c;">{credits_purchased}</span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 14px 0 0 0;">
                                                    <span style="font-size: 14px; font-weight: 600; color: #2c2c2c;">Amount Paid</span>
                                                </td>
                                                <td style="padding: 14px 0 0 0; text-align: right;">
                                                    <span style="font-size: 20px; font-weight: 700; color: #2c2c2c;">{amount_display}</span>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 0 0 32px 0; font-size: 15px; color: #6b6b6b; line-height: 1.7; text-align: center;">You can now use your credits to create unique AI-generated t-shirt designs!</p>

                            <!-- CTA Button -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td align="center">
                                        <a href="https://crowdsauced.laurence.computer" style="display: inline-block; background-color: #2c2c2c; color: #f7f5f0; text-decoration: none; font-size: 13px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; padding: 16px 32px; border: 2px solid #2c2c2c;">Start Creating</a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f7f5f0; padding: 32px 40px; border-top: 3px solid #2c2c2c;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td align="center">
                                        <p style="margin: 0 0 8px 0; font-size: 14px; font-weight: 700; color: #2c2c2c; font-family: Georgia, serif;">CROWD SAUCED</p>
                                        <p style="margin: 0 0 16px 0; font-size: 12px; color: #6b6b6b; font-style: italic;">AI-powered design studio</p>
                                        <p style="margin: 0; font-size: 12px; color: #6b6b6b;">
                                            <a href="https://crowdsauced.laurence.computer" style="color: #2c2c2c; text-decoration: none;">Website</a>
                                            <span style="margin: 0 8px; color: #d4a574;">&#9670;</span>
                                            <a href="mailto:crowdsauced@send.laurence.computer" style="color: #2c2c2c; text-decoration: none;">Support</a>
                                        </p>
                                        <p style="margin: 16px 0 0 0; font-size: 11px; color: #999999;">&copy; {datetime.now().year} Crowd Sauced. All rights reserved.</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>
    """
    return render_template_string(html_body)


@email_preview_bp.route('/subscription')
@require_admin
def preview_subscription():
    """Preview subscription confirmation email (Crowd Sauced Premium)"""
    from datetime import datetime
    credits_granted = 25

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Subscription Confirmation - Crowd Sauced Premium</title>
    <!--[if mso]>
    <style type="text/css">
        body, table, td {{font-family: Georgia, serif !important;}}
    </style>
    <![endif]-->
</head>
<body style="margin: 0; padding: 0; background-color: #f7f5f0; font-family: Georgia, 'Times New Roman', serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f7f5f0;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="background-color: #ffffff; max-width: 600px; border: 3px solid #2c2c2c;">

                    <!-- Header -->
                    <tr>
                        <td style="background-color: #2c2c2c; padding: 32px 40px; text-align: center;">
                            <h1 style="margin: 0; font-size: 11px; font-weight: 400; letter-spacing: 3px; text-transform: uppercase; color: #d4a574;">Welcome to Premium</h1>
                            <p style="margin: 12px 0 0 0; font-size: 28px; font-weight: 700; letter-spacing: 1px; color: #f7f5f0; font-family: Georgia, serif;">CROWD SAUCED</p>
                        </td>
                    </tr>

                    <!-- Decorative Line -->
                    <tr>
                        <td style="background-color: #d4a574; height: 4px;"></td>
                    </tr>

                    <!-- Main Content -->
                    <tr>
                        <td style="padding: 48px 40px;">
                            <h2 style="margin: 0 0 8px 0; font-size: 24px; font-weight: 700; color: #2c2c2c; font-family: Georgia, serif;">Your subscription is active!</h2>
                            <p style="margin: 0 0 32px 0; font-size: 15px; color: #6b6b6b; line-height: 1.7;">Thank you for joining Crowd Sauced Premium. Your monthly credits have been added.</p>

                            <!-- Credits Display -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 32px;">
                                <tr>
                                    <td align="center" style="padding: 24px; background-color: #f7f5f0; border: 2px dashed #d4a574;">
                                        <p style="margin: 0 0 8px 0; font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: #6b6b6b;">Credits Added</p>
                                        <p style="margin: 0; font-size: 48px; font-weight: 700; color: #2c2c2c; font-family: Georgia, serif;">{credits_granted}</p>
                                        <p style="margin: 8px 0 0 0; font-size: 14px; color: #d4a574; text-transform: uppercase; letter-spacing: 1px;">credits</p>
                                    </td>
                                </tr>
                            </table>

                            <!-- Subscription Details Box -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f7f5f0; border-left: 4px solid #2c2c2c; margin-bottom: 32px;">
                                <tr>
                                    <td style="padding: 24px;">
                                        <p style="margin: 0 0 16px 0; font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: #6b6b6b;">Subscription Details</p>

                                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid #e0d5c0;">
                                                    <span style="font-size: 14px; color: #6b6b6b;">Plan</span>
                                                </td>
                                                <td style="padding: 10px 0; border-bottom: 1px solid #e0d5c0; text-align: right;">
                                                    <span style="font-size: 14px; font-weight: 600; color: #2c2c2c;">Monthly Premium</span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 14px 0 0 0;">
                                                    <span style="font-size: 14px; font-weight: 600; color: #2c2c2c;">Price</span>
                                                </td>
                                                <td style="padding: 14px 0 0 0; text-align: right;">
                                                    <span style="font-size: 20px; font-weight: 700; color: #2c2c2c;">£9.99<span style="font-size: 14px; font-weight: 400; color: #6b6b6b;">/month</span></span>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <!-- Benefits -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #2c2c2c; margin-bottom: 32px;">
                                <tr>
                                    <td style="padding: 24px;">
                                        <p style="margin: 0 0 16px 0; font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: #d4a574;">Your Premium Benefits</p>
                                        <p style="margin: 0 0 8px 0; font-size: 14px; color: #f7f5f0; line-height: 1.6;"><span style="color: #d4a574;">&#9670;</span>&nbsp;&nbsp;25 credits every month</p>
                                        <p style="margin: 0 0 8px 0; font-size: 14px; color: #f7f5f0; line-height: 1.6;"><span style="color: #d4a574;">&#9670;</span>&nbsp;&nbsp;Priority design generation</p>
                                        <p style="margin: 0 0 8px 0; font-size: 14px; color: #f7f5f0; line-height: 1.6;"><span style="color: #d4a574;">&#9670;</span>&nbsp;&nbsp;Exclusive premium designs</p>
                                        <p style="margin: 0; font-size: 14px; color: #f7f5f0; line-height: 1.6;"><span style="color: #d4a574;">&#9670;</span>&nbsp;&nbsp;Cancel anytime</p>
                                    </td>
                                </tr>
                            </table>

                            <!-- CTA Button -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td align="center">
                                        <a href="https://crowdsauced.laurence.computer" style="display: inline-block; background-color: #2c2c2c; color: #f7f5f0; text-decoration: none; font-size: 13px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; padding: 16px 32px; border: 2px solid #2c2c2c;">Start Creating</a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f7f5f0; padding: 32px 40px; border-top: 3px solid #2c2c2c;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td align="center">
                                        <p style="margin: 0 0 8px 0; font-size: 14px; font-weight: 700; color: #2c2c2c; font-family: Georgia, serif;">CROWD SAUCED</p>
                                        <p style="margin: 0 0 16px 0; font-size: 12px; color: #6b6b6b; font-style: italic;">AI-powered design studio</p>
                                        <p style="margin: 0; font-size: 12px; color: #6b6b6b;">
                                            <a href="https://crowdsauced.laurence.computer" style="color: #2c2c2c; text-decoration: none;">Website</a>
                                            <span style="margin: 0 8px; color: #d4a574;">&#9670;</span>
                                            <a href="mailto:crowdsauced@send.laurence.computer" style="color: #2c2c2c; text-decoration: none;">Support</a>
                                        </p>
                                        <p style="margin: 16px 0 0 0; font-size: 11px; color: #999999;">&copy; {datetime.now().year} Crowd Sauced. All rights reserved.</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>
    """
    return render_template_string(html_body)


@email_preview_bp.route('/subscription-renewal')
@require_admin
def preview_subscription_renewal():
    """Preview subscription renewal email (Crowd Sauced Premium)"""
    from datetime import datetime
    credits_granted = 25

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Subscription Renewal - Crowd Sauced Premium</title>
    <!--[if mso]>
    <style type="text/css">
        body, table, td {{font-family: Georgia, serif !important;}}
    </style>
    <![endif]-->
</head>
<body style="margin: 0; padding: 0; background-color: #f7f5f0; font-family: Georgia, 'Times New Roman', serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f7f5f0;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="background-color: #ffffff; max-width: 600px; border: 3px solid #2c2c2c;">

                    <!-- Header -->
                    <tr>
                        <td style="background-color: #2c2c2c; padding: 32px 40px; text-align: center;">
                            <h1 style="margin: 0; font-size: 11px; font-weight: 400; letter-spacing: 3px; text-transform: uppercase; color: #d4a574;">Monthly Renewal</h1>
                            <p style="margin: 12px 0 0 0; font-size: 28px; font-weight: 700; letter-spacing: 1px; color: #f7f5f0; font-family: Georgia, serif;">CROWD SAUCED</p>
                        </td>
                    </tr>

                    <!-- Decorative Line -->
                    <tr>
                        <td style="background-color: #d4a574; height: 4px;"></td>
                    </tr>

                    <!-- Main Content -->
                    <tr>
                        <td style="padding: 48px 40px;">
                            <h2 style="margin: 0 0 8px 0; font-size: 24px; font-weight: 700; color: #2c2c2c; font-family: Georgia, serif;">Your credits have been refreshed!</h2>
                            <p style="margin: 0 0 32px 0; font-size: 15px; color: #6b6b6b; line-height: 1.7;">Your monthly subscription has renewed and your credits are ready to use.</p>

                            <!-- Credits Display -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 32px;">
                                <tr>
                                    <td align="center" style="padding: 24px; background-color: #f7f5f0; border: 2px dashed #d4a574;">
                                        <p style="margin: 0 0 8px 0; font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: #6b6b6b;">Credits Added</p>
                                        <p style="margin: 0; font-size: 48px; font-weight: 700; color: #2c2c2c; font-family: Georgia, serif;">{credits_granted}</p>
                                        <p style="margin: 8px 0 0 0; font-size: 14px; color: #d4a574; text-transform: uppercase; letter-spacing: 1px;">credits</p>
                                    </td>
                                </tr>
                            </table>

                            <!-- Renewal Details Box -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f7f5f0; border-left: 4px solid #2c2c2c; margin-bottom: 32px;">
                                <tr>
                                    <td style="padding: 24px;">
                                        <p style="margin: 0 0 16px 0; font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: #6b6b6b;">Renewal Details</p>

                                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid #e0d5c0;">
                                                    <span style="font-size: 14px; color: #6b6b6b;">Plan</span>
                                                </td>
                                                <td style="padding: 10px 0; border-bottom: 1px solid #e0d5c0; text-align: right;">
                                                    <span style="font-size: 14px; font-weight: 600; color: #2c2c2c;">Monthly Premium</span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 14px 0 0 0;">
                                                    <span style="font-size: 14px; font-weight: 600; color: #2c2c2c;">Amount Charged</span>
                                                </td>
                                                <td style="padding: 14px 0 0 0; text-align: right;">
                                                    <span style="font-size: 20px; font-weight: 700; color: #2c2c2c;">£9.99</span>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 0 0 32px 0; font-size: 15px; color: #6b6b6b; line-height: 1.7; text-align: center;">Your credits are ready. Create more unique AI-generated t-shirt designs!</p>

                            <!-- CTA Button -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td align="center">
                                        <a href="https://crowdsauced.laurence.computer" style="display: inline-block; background-color: #2c2c2c; color: #f7f5f0; text-decoration: none; font-size: 13px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; padding: 16px 32px; border: 2px solid #2c2c2c;">Start Creating</a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f7f5f0; padding: 32px 40px; border-top: 3px solid #2c2c2c;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td align="center">
                                        <p style="margin: 0 0 8px 0; font-size: 14px; font-weight: 700; color: #2c2c2c; font-family: Georgia, serif;">CROWD SAUCED</p>
                                        <p style="margin: 0 0 16px 0; font-size: 12px; color: #6b6b6b; font-style: italic;">AI-powered design studio</p>
                                        <p style="margin: 0; font-size: 12px; color: #6b6b6b;">
                                            <a href="https://crowdsauced.laurence.computer" style="color: #2c2c2c; text-decoration: none;">Website</a>
                                            <span style="margin: 0 8px; color: #d4a574;">&#9670;</span>
                                            <a href="mailto:crowdsauced@send.laurence.computer" style="color: #2c2c2c; text-decoration: none;">Support</a>
                                        </p>
                                        <p style="margin: 16px 0 0 0; font-size: 11px; color: #999999;">&copy; {datetime.now().year} Crowd Sauced. All rights reserved.</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>
    """
    return render_template_string(html_body)
