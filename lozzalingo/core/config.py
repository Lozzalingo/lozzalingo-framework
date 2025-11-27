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

    # Get DB_DIR from environment, or use a default if not set
    DB_DIR = os.getenv('DB_DIR', os.path.join(os.getcwd(), 'databases'))

    DATABASE_URL = os.getenv('DATABASE_URL')

    STATIC_FOLDER = os.getenv('STATIC_FOLDER', os.path.join(os.getcwd(), 'app', 'static')) 
    
    # OAuth settings
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID')
    GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET')
    
    # Email settings
    # Hostinger SMTP settings for no-reply@mariopintomma.com
    EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "no-reply@mariopintomma.com")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # Hostinger email password
    EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.hostinger.com")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))

    # Resend API settings (free tier: 3,000 emails/month)
    RESEND_API_KEY = os.getenv('RESEND_API_KEY') or os.getenv('RESEND')
    
    # Stripe settings
    STRIPE_PUBLIC_KEY_PK = os.getenv("STRIPE_PUBLIC_KEY_PK")
    STRIPE_PUBLIC_KEY_SK = os.getenv("STRIPE_PUBLIC_KEY_SK")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    # Database paths - use environment variables or fallback to DB_DIR
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