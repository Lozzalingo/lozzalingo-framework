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
                        <p class="card-desc">Regular order confirmation template</p>
                    </div>
                    <div class="card-footer">Template Preview</div>
                </a>

                <a href="/admin/email-preview/purchase-preorder" class="preview-card">
                    <div class="card-header">
                        <span class="card-icon">&#9200;</span>
                        <h3 class="card-title">Pre-Order Confirmation</h3>
                        <p class="card-desc">Pre-order confirmation with shipping info</p>
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
    """Preview purchase confirmation email template (regular order)"""
    email_service = get_email_service()

    sample_order = {
        'product_name': f'{email_service.brand_name} Official T-Shirt',
        'amount': 2999,
        'currency': 'GBP',
        'order_id': f'ORD-{datetime.now().year}-001',
        'size': 'Large',
        'is_preorder': False
    }

    html_content = email_service._get_purchase_template(sample_order)
    return render_template_string(html_content)


@email_preview_bp.route('/purchase-preorder')
@require_admin
def preview_purchase_preorder():
    """Preview purchase confirmation email template (pre-order)"""
    email_service = get_email_service()

    sample_order = {
        'product_name': f'{email_service.brand_name} Limited Edition T-Shirt',
        'amount': 3499,
        'currency': 'GBP',
        'order_id': f'ORD-{datetime.now().year}-002',
        'size': 'XL',
        'is_preorder': True
    }

    html_content = email_service._get_purchase_template(sample_order)
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
