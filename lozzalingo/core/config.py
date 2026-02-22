import os
from dotenv import load_dotenv

load_dotenv(override=True)

class Config:
    """
    Base configuration for Lozzalingo framework.
    Projects should provide database paths via environment variables.
    """
    # Flask settings
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'app/static/uploads')
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY')
    PROFILE_SECRET_KEY = os.getenv('PROFILE_SECRET_KEY')

    # INTEGRATION: DB paths use three-tier resolution: env var > app.config > default (CWD-relative).
    # NEVER use os.path.dirname(__file__) to compute DB paths in modules -- __file__-based paths
    # resolve incorrectly inside Docker containers. Always use these Config constants instead.
    DB_DIR = os.getenv('DB_DIR', os.path.join(os.getcwd(), 'databases'))

    DATABASE_URL = os.getenv('DATABASE_URL')

    STATIC_FOLDER = os.getenv('STATIC_FOLDER', os.path.join(os.getcwd(), 'app', 'static')) 
    
    # OAuth settings
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID')
    GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET')
    
    # Email settings
    EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "onboarding@resend.dev")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))

    # Resend API settings (free tier: 3,000 emails/month)
    RESEND_API_KEY = os.getenv('RESEND_API_KEY') or os.getenv('RESEND')
    
    # Stripe settings
    STRIPE_PUBLIC_KEY_PK = os.getenv("STRIPE_PUBLIC_KEY_PK")
    STRIPE_PUBLIC_KEY_SK = os.getenv("STRIPE_PUBLIC_KEY_SK")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    # Database paths -- env var > DB_DIR-relative default. All modules import these constants.
    # HOST APP CONFIG CHECKLIST: If your host app defines its own Config class (not inheriting
    # from this one), it MUST define ALL of the following attributes. Modules use a 3-tier
    # resolution pattern (app.config > Config with hasattr > env var fallback), but missing
    # attributes will cause AttributeError if the fallback chain doesn't catch them.
    #   DB paths: NEWS_DB, USER_DB, ANALYTICS_DB, MERCHANDISE
    #   Table names: ANALYTICS_TABLE (others are hardcoded in queries)
    NEWS_DB = os.getenv('NEWS_DB', os.path.join(DB_DIR, "news.db"))
    USER_DB = os.getenv('USER_DB', os.path.join(DB_DIR, "users.db"))
    ANALYTICS_DB = os.getenv('ANALYTICS_DB', os.path.join(DB_DIR, "analytics_log.db"))
    MERCHANDISE = os.getenv('MERCHANDISE_DB', os.path.join(DB_DIR, "merchandise.db"))

    # Table names
    NEWS_ARTICLES_TABLE = "news_articles"
    ANALYTICS_TABLE = "analytics_log"
    USERS_TABLE = "users"
    SUBSCRIBERS = "subscribers"
    ADMIN_TABLE = "admin"
    MERCHANDISE_TABLE = "merchandise"

    # YouTube API
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

    # Lozzalingo framework settings
    # Auth blueprint name - projects can override this if they register the auth blueprint with a different name
    LOZZALINGO_AUTH_BLUEPRINT_NAME = os.getenv("LOZZALINGO_AUTH_BLUEPRINT_NAME", "auth")

    # Port for local server (optional, projects can set this)
    port = int(os.getenv('PORT', '5000'))