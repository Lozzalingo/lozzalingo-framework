# Lozzalingo Framework Integration Guide

This document outlines how to integrate the Lozzalingo framework into your Flask application.

## Quick Start

The framework provides ready-to-use modules that you can plug into your Flask app:
- **Dashboard Module**: Admin authentication and dashboard (core admin foundation)
- **Orders Module**: Order management interface (plugs into admin dashboard)
- **News Module**: News/blog article management (plugs into admin dashboard)
- **Merchandise Module**: Product/merchandise management (plugs into admin dashboard)
- **Auth Module**: User authentication system (email/password, OAuth, password reset)
- **Analytics Module**: Admin analytics dashboard
- **Email Module**: Configurable email service with Resend API (templates + preview)
- **Customer Spotlight Module**: Instagram-style customer gallery with infinite scroll

## Installation

### 1. Install the Framework

```bash
# Development installation (editable)
pip install -e /path/to/lozzalingo-framework

# Or use direct Python path to ensure correct venv
/path/to/your-project/venv/bin/python3 -m pip install -e /path/to/lozzalingo-framework
```

### 2. Basic Integration

```python
from flask import Flask
from lozzalingo.modules.dashboard import dashboard_bp as admin_dashboard_bp
from lozzalingo.modules.auth import auth_bp, configure_oauth, init_oauth, oauth
from lozzalingo.modules.analytics import analytics_bp

app = Flask(__name__)
app.secret_key = 'your-secret-key'

# Register blueprints
app.register_blueprint(admin_dashboard_bp)  # Admin dashboard at /admin
app.register_blueprint(auth_bp)             # User auth
app.register_blueprint(analytics_bp)        # Admin analytics at /admin/analytics

# Configure OAuth (optional, for Google/GitHub login)
configure_oauth(app)
init_oauth(oauth)

if __name__ == '__main__':
    app.run(debug=True)
```

That's it! You now have:
- Admin dashboard: `/admin/dashboard` (with login at `/admin/login`)
- User auth routes: `/login`, `/register`, `/logout`, `/forgot-password`
- Admin analytics: `/admin/analytics/`

## Dashboard Module (Admin)

The Dashboard Module provides the core admin functionality that all other admin features plug into. It handles admin authentication, the main admin dashboard interface, and serves as the foundation for modular admin features.

### Features

- **Admin Authentication**: Secure login system separate from user auth
- **Admin Dashboard**: Unified interface with cards for different admin features
- **Password Management**: Change password functionality
- **Admin User Management**: Create new admin accounts
- **Stats API**: Extensible API endpoint for dashboard statistics
- **Modular Design**: Other admin features (orders, news, etc.) plug into this foundation

### Routes Provided

- `/admin/login` - Admin login page
- `/admin/logout` - Admin logout
- `/admin/dashboard` or `/admin` - Main admin dashboard
- `/admin/change-password` - Change admin password
- `/admin/create-admin` - Create new admin account (protected)
- `/admin/status` - API endpoint to check admin login status
- `/admin/api/stats` - API endpoint for dashboard statistics

### Basic Setup

```python
from flask import Flask
from lozzalingo.modules.dashboard import dashboard_bp as admin_dashboard_bp

app = Flask(__name__)
app.secret_key = 'your-secret-key'

# Register admin dashboard
app.register_blueprint(admin_dashboard_bp)

if __name__ == '__main__':
    app.run(debug=True)
```

### First-Time Setup

1. Start your application
2. Navigate to `/admin/create-admin`
3. Create the first admin account (this route is only accessible when no admins exist)
4. Log in at `/admin/login`
5. Access the dashboard at `/admin/dashboard`

### Configuration

The Dashboard Module uses these configuration values (all optional):

```python
class Config:
    USER_DB = 'path/to/users.db'        # Database for admin accounts
    ANALYTICS_DB = 'path/to/analytics.db'  # Optional: For analytics stats
    NEWS_DB = 'path/to/news.db'         # Optional: For news stats
```

If not provided, it falls back to environment variables or defaults.

### Extending the Dashboard

The dashboard template includes cards that other modules can plug into. The `/admin/api/stats` endpoint returns statistics that populate the dashboard cards:

```python
# Custom stats can be added by extending the stats API
@admin_dashboard_bp.route('/api/custom-stats')
def custom_stats():
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    return jsonify({
        'my_feature': {
            'total_items': 100,
            'active_items': 75
        }
    })
```

### Adding Admin Links to User Dashboard

To add an admin link from your user dashboard:

```html
<!-- In your user dashboard template -->
<nav>
    <a href="#my-stuff">My Stuff</a>
    <a href="#settings">Settings</a>
    <a href="{{ url_for('admin.dashboard') }}" style="color: #ffd700;">Admin</a>
</nav>
```

### Database Schema

The module creates these tables automatically:

**admin table:**
- `id` - Primary key
- `email` - Admin email (unique)
- `password_hash` - Hashed password
- `created_at` - Creation timestamp

**email_logs table:**
- `id` - Primary key
- `recipient` - Email recipient
- `subject` - Email subject
- `email_type` - Type of email
- `status` - Status (sent/failed)
- `error_message` - Error details if failed
- `sent_at` - Timestamp

### Modular Admin Features

The Dashboard Module is designed to be the foundation. Other admin features should:

1. Have their own routes (e.g., `/admin/orders`, `/admin/news`)
2. Include their own dashboard cards
3. Require `'admin_id' in session` for authentication
4. Link back to `/admin/dashboard`

Example of a pluggable admin feature:

```python
# In your orders module
from flask import Blueprint, session, redirect, url_for

orders_admin_bp = Blueprint('orders_admin', __name__, url_prefix='/admin/orders')

@orders_admin_bp.route('/')
def orders_manager():
    if 'admin_id' not in session:
        return redirect(url_for('admin.login'))
    # Your orders management code here
    return render_template('orders_admin.html')
```

## Auth Module

The framework's auth module provides a complete authentication system.

### Features

- Email/password authentication
- Email verification with tokens
- Password reset flow
- OAuth integration (Google, GitHub)
- User session management
- Admin user detection

### Configuration

Set these environment variables in your `.env` or config:

```python
# Required
SECRET_KEY = 'your-secret-key'

# For OAuth (optional)
GOOGLE_CLIENT_ID = 'your-google-client-id'
GOOGLE_CLIENT_SECRET = 'your-google-client-secret'
GITHUB_CLIENT_ID = 'your-github-client-id'
GITHUB_CLIENT_SECRET = 'your-github-client-secret'
```

### Database Setup

The auth module expects a SQLite database with a users table. Create it:

```python
from lozzalingo.modules.auth import SignInDatabase

# Initialize the database (run once)
SignInDatabase.create_tables()
```

### Session Variables

When users log in, these session variables are set:

```python
session['user_id']      # User's ID
session['email']        # User's email
session['first_name']   # User's first name
session['last_name']    # User's last name

# For admin users:
session['admin_id']     # Admin ID
session['admin_email']  # Admin email
```

### Available Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/login` | GET | Login page |
| `/sign-in` | GET | Alias for /login |
| `/register` | GET, POST | Registration page |
| `/logout` | GET | Sign out user |
| `/sign-out` | GET | Alias for /logout |
| `/forgot-password` | GET, POST | Password reset request |
| `/password-reset` | GET, POST | Password reset with token |
| `/verify-email` | GET | Email verification with token |
| `/resend-verification` | POST | Resend verification email |
| `/dashboard` | GET | User dashboard (redirects to index) |
| `/change-password` | GET | Change password page |
| `/auth/google` | GET | Google OAuth login |
| `/auth/github` | GET | GitHub OAuth login |

### Customizing Templates

The framework provides default templates, but you can override them:

```
your-app/
├── templates/
│   └── auth/              # Override framework templates
│       ├── sign-in.html   # Your custom sign-in page
│       └── register.html  # Your custom register page
```

Flask will use your templates first, falling back to framework templates if not found.

### Linking to Existing Data

If your app has existing user-related data, you can link it when users sign in:

```python
# In your app's database module
class Database:
    @staticmethod
    def link_submission_to_user(email, user_id):
        """Link existing submissions from email to user_id"""
        # Your logic to update submissions
        pass
```

The auth module will automatically call this if it exists.

## Analytics Module

Provides an admin dashboard for viewing site analytics with client-side tracking.

### Setup

```python
from lozzalingo.modules.analytics import analytics_bp

app.register_blueprint(analytics_bp, url_prefix='/admin/analytics')

# Tell analytics which blueprint name your auth uses
app.config['LOZZALINGO_AUTH_BLUEPRINT_NAME'] = 'auth'  # Default is 'auth'
```

### Access Control

The analytics dashboard requires admin access. Users are considered admins if:

```python
session['admin_id']     # is set
session['admin_email']  # is set
```

Set these in your auth logic when admin users log in:

```python
if user.get('user_level') == 'admin':
    session['admin_id'] = user['id']
    session['admin_email'] = user['email']
```

### Available Routes

| Route | Description |
|-------|-------------|
| `/admin/analytics/` | Main analytics dashboard |
| `/admin/analytics/api/log-interaction` | Client-side logging endpoint |

### CRITICAL: Client-Side Setup

**You MUST add the analytics scripts to ALL templates where you want tracking:**

```html
<!-- Add these scripts before </body> in your templates -->
<script src="{{ url_for('analytics.static', filename='js/analytics.js') }}"></script>
<script src="{{ url_for('analytics.static', filename='js/device_analytics.js') }}"></script>
```

**Common templates to include these in:**
- Main page/form templates
- Gallery pages
- Profile pages
- About/info pages
- Any page you want tracked

**Important notes:**
- The endpoint is `analytics.static` (NOT `analytics.analytics_static`)
- The path must include `js/` prefix: `filename='js/analytics.js'`
- Optionally add cache-busting: `?v={{ file_version('analytics.js') }}`

### CRITICAL: Allowed Origins Configuration

The analytics API validates the `Origin` header for security. **You MUST add your production domains** to the allowed origins list in `lozzalingo/modules/analytics/routes.py`.

Find the `allowed_origins` lists (there are TWO locations, around lines 647 and 1011):

```python
allowed_origins = [
    'http://localhost:5001',
    'http://127.0.0.1:5001',
    # ADD YOUR PRODUCTION DOMAINS HERE:
    'https://yourdomain.com',
    'https://www.yourdomain.com',
]
```

**If your domain is not in allowed_origins:**
- The API will return 403 Forbidden
- Analytics will silently fail to log
- Check container logs for "Rejected request from origin" messages

### Fingerprint Data Handling

The analytics module accepts device fingerprints as either:
- A string (legacy)
- A dict/object (from `deviceDetails` in device_analytics.js)

The module automatically handles conversion for SQLite storage. If you're extending analytics, ensure dict fingerprints are JSON-serialized before database storage:

```python
# The module handles this automatically, but if extending:
fingerprint_str = json.dumps(fingerprint) if isinstance(fingerprint, dict) else fingerprint
```

### Troubleshooting Analytics

**Analytics not recording data:**

1. **Check scripts are included** - View page source and search for `analytics.js`
2. **Check allowed_origins** - Your domain must be in the list in routes.py (TWO locations!)
3. **Check container logs** - `docker logs <container>` for errors like:
   - "Rejected request from origin: https://yourdomain.com"
   - "'dict' object has no attribute 'encode'" (fingerprint issue - update module)
   - "Error binding parameter" (dict storage issue - update module)
4. **Check database** - Query the analytics_log table:
   ```sql
   SELECT timestamp, event_type, ip FROM analytics_log ORDER BY timestamp DESC LIMIT 5;
   ```

**BuildError: Could not build url for endpoint 'analytics.analytics_static':**
- Wrong endpoint name. Use `analytics.static` not `analytics.analytics_static`

**403 Forbidden on /api/log-interaction:**
- Add your domain to allowed_origins in routes.py (both locations!)

## Using Custom Auth (Advanced)

If you prefer to use your own authentication system instead of the framework's auth module, you can! Just ensure your auth blueprint:

1. Is registered with the name `'auth'`
2. Provides these endpoints: `/login`, `/logout`, `/dashboard`, `/change-password`
3. Sets the required session variables

```python
from your_auth import your_auth_bp

# Register with name 'auth' for framework compatibility
app.register_blueprint(your_auth_bp, name='auth')
```

## Example: Complete Integration

```python
from flask import Flask
from lozzalingo.modules.auth import auth_bp, configure_oauth, init_oauth, oauth, SignInDatabase
from lozzalingo.modules.analytics import analytics_bp
from config import Config

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
app.config['LOZZALINGO_AUTH_BLUEPRINT_NAME'] = 'auth'

# Initialize auth database (run once)
# SignInDatabase.create_tables()

# Register framework modules
app.register_blueprint(auth_bp)
app.register_blueprint(analytics_bp, url_prefix='/admin/analytics')

# Configure OAuth
configure_oauth(app)
init_oauth(oauth)

# Your app routes
@app.route('/')
def index():
    return "Hello World!"

if __name__ == '__main__':
    app.run(debug=True, port=5001)
```

## Troubleshooting

### ImportError: No module named 'lozzalingo'

The framework isn't installed in your venv. Use:
```bash
/path/to/your-project/venv/bin/python3 -m pip install -e /path/to/lozzalingo-framework
```

### BuildError: Could not build url for endpoint 'auth.login'

Your auth blueprint isn't registered with the name 'auth'. Either:
- Use the framework's auth module (it's already named 'auth')
- Or register your custom auth blueprint: `app.register_blueprint(your_bp, name='auth')`

### Templates not found

Make sure templates are in the correct directory structure:
```
your-app/templates/auth/sign-in.html  # To override framework template
```

Or just use the framework's default templates (no action needed).

### OAuth not working

Check that you've:
1. Set environment variables: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
2. Called `configure_oauth(app)` and `init_oauth(oauth)`
3. Configured OAuth redirect URIs in Google/GitHub console

## Directory Structure

After integration, your project should look like:

```
your-project/
├── venv/
│   └── lib/python3.x/site-packages/
│       └── lozzalingo/              # Framework installed here
├── templates/
│   └── auth/                        # Optional: override templates
├── static/
├── app.py                           # Your main app
├── config.py                        # Your config
└── requirements.txt
```

## What's Next?

- Customize templates to match your brand
- Add your own blueprints alongside framework modules  
- Use the auth session variables in your routes
- Check out the framework source for advanced customization

## Getting Help

If you encounter issues:
1. Check this integration guide
2. Review the framework source code at `/lozzalingo-framework/lozzalingo/modules/`
3. Ensure all dependencies are installed in the correct venv


## Orders Module

Admin interface for order management. Plugs into the Dashboard Module.

### Features
- Order listing and search
- Order detail view
- Order status management
- Customer information editing
- Integration-ready for fulfillment services

### Routes
- `/admin/orders` - Order management interface
- `/admin/orders/api/orders` - List orders API
- `/admin/orders/api/order/<id>` - Get order details
- `/admin/orders/api/update-order` - Update order
- `/admin/orders/api/delete-order` - Delete order

### Setup

```python
from lozzalingo.modules.orders import orders_bp
app.register_blueprint(orders_bp)
```

Requires `app.models.merchandise` with Order, OrderItem, Product models.

## News Module

Admin interface for news/blog article management. Plugs into the Dashboard Module.

### Features
- Article creation and editing
- Draft/publish workflow
- Image upload for articles
- Integration-ready for email notifications

### Routes
- `/admin/news` - News editor interface
- `/admin/news/api/articles` - List/create articles
- `/admin/news/api/articles/<id>` - Get/update/delete article
- `/admin/news/upload-image` - Upload article images

### Setup

```python
from lozzalingo.modules.news import news_bp
app.register_blueprint(news_bp)
```

Requires `app.models.news` with article management functions.

## Merchandise Module

Admin interface for product/merchandise management. Plugs into the Dashboard Module.

### Features
- Product creation and editing
- Pricing management
- Inventory tracking
- Category management

### Routes
- `/admin/merchandise` - Merchandise editor interface
- `/admin/merchandise/products` - List products
- `/admin/merchandise/create` - Create product
- `/admin/merchandise/update` - Update product
- `/admin/merchandise/delete/<id>` - Delete product

### Setup

```python
from lozzalingo.modules.merchandise import merchandise_bp
app.register_blueprint(merchandise_bp)
```

Requires `app.models.merchandise` with product management functions.

## Email Module

Provides a configurable email service using Resend API with template preview functionality.

### Features

- **Configurable Branding**: All templates use configurable brand name, tagline, website URL
- **Resend API Integration**: Uses Resend for reliable email delivery
- **Email Templates**: Welcome, purchase confirmation, shipping, news, admin notifications
- **Email Preview**: Admin interface to preview all templates before sending
- **Email Logging**: All emails logged to SQLite database for tracking
- **Pre-order Support**: Special handling for pre-order purchase confirmations

### Setup

```python
from flask import Flask
from lozzalingo.modules.email import email_preview_bp, email_service

app = Flask(__name__)

# Configure email settings
app.config['RESEND_API_KEY'] = 'your-resend-api-key'
app.config['EMAIL_ADDRESS'] = 'noreply@yourdomain.com'
app.config['EMAIL_BRAND_NAME'] = 'Your Brand'
app.config['EMAIL_BRAND_TAGLINE'] = 'Your tagline here'
app.config['EMAIL_WEBSITE_URL'] = 'https://yourdomain.com'
app.config['EMAIL_SUPPORT_EMAIL'] = 'support@yourdomain.com'
app.config['EMAIL_ADMIN_EMAIL'] = 'admin@yourdomain.com'  # For admin notifications
app.config['USER_DB'] = 'path/to/users.db'  # For email logs

# Initialize email service
email_service.init_app(app)

# Register email preview blueprint (admin only)
app.register_blueprint(email_preview_bp)

if __name__ == '__main__':
    app.run(debug=True)
```

### Configuration Options

| Config Key | Description | Default |
|------------|-------------|---------|
| `RESEND_API_KEY` | Your Resend API key | Required |
| `EMAIL_ADDRESS` | Sender email address | `onboarding@resend.dev` |
| `EMAIL_BRAND_NAME` | Brand name in emails | `Your Brand` |
| `EMAIL_BRAND_TAGLINE` | Brand tagline (optional) | Empty |
| `EMAIL_WEBSITE_URL` | Website URL for links | `https://example.com` |
| `EMAIL_SUPPORT_EMAIL` | Support contact email | `support@example.com` |
| `EMAIL_ADMIN_EMAIL` | Admin notification email | None (disables admin notifications) |
| `USER_DB` | SQLite database path for email logs | `users.db` |

### Routes Provided

| Route | Description |
|-------|-------------|
| `/admin/email-preview/` | Email template preview index |
| `/admin/email-preview/welcome` | Preview welcome email |
| `/admin/email-preview/welcome/<name>` | Preview welcome email with custom name |
| `/admin/email-preview/purchase` | Preview purchase confirmation |
| `/admin/email-preview/purchase-preorder` | Preview pre-order confirmation |
| `/admin/email-preview/news` | Preview news notification |
| `/admin/email-preview/shipping` | Preview shipping notification |
| `/admin/email-preview/test-send` | Send test welcome email |
| `/admin/email-preview/admin-order` | Send test admin order notification |
| `/admin/email-preview/admin-subscriber` | Send test admin subscriber notification |

### Using the Email Service

```python
from lozzalingo.modules.email import email_service

# Send welcome email
email_service.send_welcome_email('user@example.com', 'John')

# Send purchase confirmation
email_service.send_purchase_confirmation('user@example.com', {
    'product_name': 'T-Shirt',
    'amount': 2999,  # In pence/cents
    'currency': 'GBP',
    'order_id': 'ORD-001',
    'size': 'Large',
    'is_preorder': False
})

# Send shipping notification
email_service.send_shipping_notification(
    email='user@example.com',
    customer_name='John Doe',
    order_id=123,
    tracking_number='TRACK123456',
    items_text='* T-Shirt (Size: L) x1'
)

# Send news notification to subscribers
email_service.send_news_notification(
    subscribers=['user1@example.com', 'user2@example.com'],
    article={
        'title': 'Big News!',
        'excerpt': 'We have exciting news...',
        'slug': 'big-news',
        'date': '2024-01-15'
    }
)

# Admin notifications (requires EMAIL_ADMIN_EMAIL configured)
email_service.send_admin_order_notification({...})
email_service.send_admin_subscriber_notification({...})
```

### Email Logging

The module automatically creates an `email_logs` table in the configured USER_DB:

```sql
CREATE TABLE email_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    email_type TEXT,
    status TEXT NOT NULL,  -- 'sent' or 'failed'
    error_message TEXT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Dependencies

Add `resend` to your requirements.txt:

```
resend>=0.5.0
```

### Troubleshooting

**Emails not sending:**
1. Check `RESEND_API_KEY` is configured
2. Verify `EMAIL_ADDRESS` is verified in Resend dashboard
3. Check server logs for error messages
4. Ensure `resend` package is installed

**Admin notifications not working:**
- Ensure `EMAIL_ADMIN_EMAIL` is configured in app.config

**Preview pages showing default branding:**
- Make sure `email_service.init_app(app)` is called before using the service


## Customer Spotlight Module

Instagram-style customer gallery showcasing user-submitted photos. Features an infinite-scroll horizontal carousel and admin management interface.

### Features

- **Horizontal Infinite Scroll**: Seamless looping carousel of customer photos
- **Admin Management**: Add, edit, delete spotlight entries
- **Image Upload**: Upload customer photos with Instagram handle
- **Public API**: JSON endpoint for fetching spotlight data
- **Responsive Design**: Works on mobile and desktop
- **Generic Styling**: Base styles that can be overridden per-project

### Setup

```python
from flask import Flask
from lozzalingo.modules.customer_spotlight import customer_spotlight_bp

app = Flask(__name__)

# Register the blueprint
app.register_blueprint(customer_spotlight_bp)

if __name__ == '__main__':
    app.run(debug=True)
```

### Routes Provided

| Route | Description |
|-------|-------------|
| `/api/customer-spotlight` | Public API - returns spotlight entries as JSON |
| `/admin/customer-spotlight-editor` | Admin interface to manage spotlights |
| `/admin/customer-spotlight-editor/add` | Add new spotlight entry |
| `/admin/customer-spotlight-editor/edit/<id>` | Edit spotlight entry |
| `/admin/customer-spotlight-editor/delete/<id>` | Delete spotlight entry |

### Configuration

```python
# Optional: Configure the database path
app.config['CUSTOMER_SPOTLIGHT_DB'] = 'path/to/spotlight.db'

# Optional: Configure upload folder for images
app.config['CUSTOMER_SPOTLIGHT_UPLOAD_FOLDER'] = 'path/to/uploads'
```

### Including in Templates

Add the spotlight section to your page:

```html
<!-- Include the spotlight section template -->
<div id="customer-spotlight">
    {% include 'customer_spotlight/spotlight_section.html' %}
</div>
```

The template automatically includes the required CSS and JavaScript.

### Custom Styling (Per-Project Override)

The module provides **generic base styles** that work out of the box. To customize the look for your brand:

1. **Create a project-specific override CSS file** (e.g., `your-project/static/css/spotlight.css`)

2. **Use CSS variables for theming** (if your project has a theme.css):

```css
/* your-project/static/css/spotlight.css */
.spotlight-title {
    font-family: var(--font-display);
    color: var(--color-text);
    text-shadow: 1px 1px 0 var(--color-accent);
}

.customer-item {
    border: var(--border-width) solid var(--color-border);
}

.customer-item:hover {
    box-shadow: var(--shadow-hover);
}

.customer-overlay {
    background: var(--color-overlay);
    color: var(--color-text-inverse);
}

.customer-handle::before {
    color: var(--color-accent);
}
```

3. **Include the override CSS after the framework CSS**:

```html
<head>
    <!-- Framework base styles load automatically from the template -->

    <!-- Your project's theme variables -->
    <link rel="stylesheet" href="{{ url_for('static', filename='css/theme.css') }}">

    <!-- Your project's spotlight override (loads last to override base) -->
    <link rel="stylesheet" href="{{ url_for('static', filename='css/spotlight.css') }}">
</head>
```

### Database Schema

The module creates a `customer_spotlight` table:

```sql
CREATE TABLE customer_spotlight (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instagram_handle TEXT NOT NULL,
    image_path TEXT NOT NULL,
    display_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### API Response Format

`GET /api/customer-spotlight` returns:

```json
{
    "spotlights": [
        {
            "id": 1,
            "instagram_handle": "username",
            "image_url": "/customer-spotlight/images/photo.jpg",
            "display_order": 1
        }
    ],
    "total": 10
}
```

### JavaScript Integration

The included `spotlight.js` handles:
- Fetching data from the API
- Rendering spotlight cards
- Infinite scroll animation
- Loading states and error handling

To customize behavior, you can override the JavaScript:

```javascript
// After including spotlight.js, customize settings
if (window.CustomerSpotlight) {
    CustomerSpotlight.config.scrollSpeed = 30; // pixels per second
    CustomerSpotlight.config.cardWidth = 220;  // card width in pixels
}
```

### Troubleshooting

**Spotlight not showing:**
1. Check that the blueprint is registered
2. Verify the database has entries (check `/admin/customer-spotlight-editor`)
3. Check browser console for JavaScript errors
4. Verify the API endpoint returns data: `curl http://localhost:5001/api/customer-spotlight`

**Styling looks wrong:**
- The module ships with generic gray/neutral styles
- Create a project-specific CSS override file
- Ensure your override CSS loads AFTER the framework base styles
- Use CSS variables from your theme.css for consistent branding

**Images not loading:**
- Check the `CUSTOMER_SPOTLIGHT_UPLOAD_FOLDER` config
- Verify image files exist in the upload directory
- Check file permissions


