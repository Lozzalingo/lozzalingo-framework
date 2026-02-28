import os
from dotenv import load_dotenv

load_dotenv()

IS_PRODUCTION = (
    os.getenv('ENVIRONMENT') == 'production' or
    os.getenv('FLASK_ENV') == 'production' or
    os.getenv('PRODUCTION') == '1'
)

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'databases')


class Config:
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    CSS_VERSION = '1'

    # Database paths
    DB_DIR = DB_DIR
    USER_DB = os.path.join(DB_DIR, 'users.db')
    NEWS_DB = os.path.join(DB_DIR, 'news.db')
    ANALYTICS_DB = os.path.join(DB_DIR, 'analytics_log.db')
    ANALYTICS_TABLE = 'analytics_log'
    # PROJECTS_DB = os.path.join(DB_DIR, 'projects.db')      # if projects enabled
    # QUICK_LINKS_DB = os.path.join(DB_DIR, 'quick_links.db') # if quick_links enabled

    # Stripe (uncomment if merchandise/orders enabled)
    # STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
    # STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
    # STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')

    # Google OAuth
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')

    # Email
    EMAIL_PROVIDER = os.getenv('EMAIL_PROVIDER', 'resend')
    RESEND_API_KEY = os.getenv('RESEND_API_KEY', '')
    EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS', '')
    EMAIL_BRAND_NAME = 'My Lozzalingo Site'
    EMAIL_BRAND_TAGLINE = 'Built with Lozzalingo Framework'
    EMAIL_WEBSITE_URL = os.getenv('BASE_URL', 'http://localhost:5000')
    EMAIL_SUPPORT_EMAIL = os.getenv('EMAIL_SUPPORT_EMAIL', '')
    EMAIL_ADMIN_EMAIL = os.getenv('EMAIL_ADMIN_EMAIL', '')
