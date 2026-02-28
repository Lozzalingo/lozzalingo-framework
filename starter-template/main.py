"""
My Lozzalingo Site
==================

Flask app using the Lozzalingo framework.
"""

import os
from flask import Flask, render_template, send_from_directory
from jinja2 import ChoiceLoader, FileSystemLoader

# ===== App Setup =====

app = Flask(__name__)

# Load config
from config import Config
app.config['CSS_VERSION'] = Config.CSS_VERSION
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['DB_DIR'] = Config.DB_DIR
app.config['USER_DB'] = Config.USER_DB
app.config['NEWS_DB'] = Config.NEWS_DB
app.config['ANALYTICS_DB'] = Config.ANALYTICS_DB

# Stripe config (uncomment if merchandise/orders enabled)
# app.config['STRIPE_PUBLISHABLE_KEY'] = Config.STRIPE_PUBLISHABLE_KEY
# app.config['STRIPE_SECRET_KEY'] = Config.STRIPE_SECRET_KEY
# app.config['STRIPE_WEBHOOK_SECRET'] = Config.STRIPE_WEBHOOK_SECRET

# Google OAuth
app.config['GOOGLE_CLIENT_ID'] = Config.GOOGLE_CLIENT_ID
app.config['GOOGLE_CLIENT_SECRET'] = Config.GOOGLE_CLIENT_SECRET

# Email
app.config['EMAIL_PROVIDER'] = Config.EMAIL_PROVIDER
app.config['RESEND_API_KEY'] = Config.RESEND_API_KEY
app.config['EMAIL_ADDRESS'] = Config.EMAIL_ADDRESS
app.config['EMAIL_BRAND_NAME'] = Config.EMAIL_BRAND_NAME
app.config['EMAIL_BRAND_TAGLINE'] = Config.EMAIL_BRAND_TAGLINE
app.config['EMAIL_WEBSITE_URL'] = Config.EMAIL_WEBSITE_URL
app.config['EMAIL_SUPPORT_EMAIL'] = Config.EMAIL_SUPPORT_EMAIL
app.config['EMAIL_ADMIN_EMAIL'] = Config.EMAIL_ADMIN_EMAIL
app.config['EMAIL_WELCOME'] = {
    'greeting': 'Thanks for subscribing',
    'intro': "You'll receive updates when new content is published.",
    'bullets': [
        'New posts and articles',
        'Project updates',
        'Announcements',
    ],
    'closing': 'Thanks for following along.',
    'signoff': 'My Lozzalingo Site',
}
app.config['EMAIL_STYLE'] = {
    'bg': '#f5f5f0',
    'card_bg': '#ffffff',
    'header_bg': '#1a1a2e',
    'header_text': '#ffffff',
    'text': '#333333',
    'text_secondary': '#666666',
    'accent': '#2563eb',
    'highlight_bg': '#f0f0e8',
    'highlight_border': '#2563eb',
    'border': '#e0e0e0',
    'link': '#2563eb',
    'btn_bg': '#2563eb',
    'btn_text': '#ffffff',
    'footer_bg': '#1a1a2e',
    'font': "'Inter', 'Helvetica', sans-serif",
    'font_heading': "'Space Mono', 'Courier New', monospace",
}

# Session security
app.config['SESSION_COOKIE_SECURE'] = not app.debug
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Ensure database directory exists
os.makedirs(Config.DB_DIR, exist_ok=True)

# ===== Lozzalingo Framework =====

from lozzalingo import Lozzalingo
lozzalingo = Lozzalingo(app)

# ===== Template Loader =====
# Local templates override framework defaults

_fw_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lozzalingo', 'modules')

template_dirs = [
    FileSystemLoader('templates'),  # Local templates (highest priority)
]

# Add framework module template dirs for all enabled modules
for module_name in ['analytics', 'dashboard', 'news', 'news_public', 'settings',
                     'projects', 'projects_public', 'quick_links', 'subscribers']:
    module_path = os.path.join(_fw_base, module_name, 'templates')
    if os.path.isdir(module_path):
        template_dirs.append(FileSystemLoader(module_path))

app.jinja_loader = ChoiceLoader(template_dirs)


# ===== Routes =====

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static', 'img'),
                               'logo.png', mimetype='image/png')


@app.route('/')
def home():
    """Home page"""
    print("[STARTER] Home page loaded")
    return render_template('index.html')


@app.route('/about')
def about():
    """About page"""
    print("[STARTER] About page loaded")
    return render_template('about.html')


# Uncomment if news module is enabled:
# @app.route('/blog')
# def blog():
#     """Blog listing page"""
#     from lozzalingo.modules.news.routes import get_all_articles_db, init_news_db
#     try:
#         init_news_db()
#         articles = get_all_articles_db(status='published')
#     except Exception as e:
#         print(f"[STARTER] Error loading articles: {e}")
#         articles = []
#     return render_template('news_public/blog.html', articles=articles)


# ===== Run =====

if __name__ == '__main__':
    print("[STARTER] Starting on port 5000...")
    app.run(debug=True, port=5000, host='0.0.0.0')
