"""
Lozzalingo - A Flask Admin Framework
====================================

A batteries-included Flask framework with admin dashboard, analytics,
authentication, and more - all working out of the box.

Quick Start:
    from flask import Flask
    from lozzalingo import Lozzalingo

    app = Flask(__name__)
    lozzalingo = Lozzalingo(app)

    # That's it! Visit /admin for the admin panel.

With configuration:
    lozzalingo = Lozzalingo(app, {
        'brand_name': 'My Site',
        'features': {
            'analytics': True,
            'auth': True,
            'news': False,  # Disable news module
        }
    })

Or use a YAML config file (lozzalingo.yaml in your app root):
    site:
      name: "My Site"
    features:
      analytics: true
      auth: true
"""

__version__ = '0.2.0'
__author__ = 'Laurence Stephan'

import os
import yaml
from flask import Flask


class Lozzalingo:
    """
    Main entry point for the Lozzalingo framework.

    Handles automatic registration of all modules with sensible defaults.
    """

    # Default configuration
    DEFAULT_CONFIG = {
        'brand_name': 'Lozzalingo Site',
        'brand_tagline': '',
        'secret_key': None,  # Will use app.secret_key or generate one

        # Database settings
        'db_dir': 'databases',

        # Feature flags - all enabled by default
        'features': {
            'analytics': True,
            'auth': True,
            'dashboard': True,
            'news': True,
            'news_public': True,
            'email': True,
            'customer_spotlight': True,
            'merchandise': True,
            'merchandise_public': True,
            'orders': True,
            'external_api': True,
            'settings': True,
            'projects': False,
            'projects_public': False,
            'quick_links': False,
        },

        # Analytics settings
        'analytics': {
            'track_admin': False,  # Don't track admin page views by default
            'allowed_origins': None,  # None = allow request origin (dynamic)
        },

        # Email settings
        'email': {
            'resend_api_key': None,  # From RESEND_API_KEY env var
            'from_address': None,
            'support_email': None,
            'admin_email': None,
        },

        # Auth settings
        'auth': {
            'google_client_id': None,
            'google_client_secret': None,
            'github_client_id': None,
            'github_client_secret': None,
        },
    }

    def __init__(self, app: Flask = None, config: dict = None):
        """
        Initialize Lozzalingo with a Flask app.

        Args:
            app: Flask application instance
            config: Optional configuration dict (overrides defaults and YAML)
        """
        self.app = app
        self._config = self._merge_config(config or {})
        self._registered_blueprints = []

        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask):
        """
        Initialize Lozzalingo with the Flask app.

        Can be used with application factory pattern:
            lozzalingo = Lozzalingo()
            lozzalingo.init_app(app)
        """
        self.app = app

        # Load YAML config if exists
        self._load_yaml_config()

        # Set up Flask config from our config
        self._configure_flask_app()

        # Ensure database directory exists
        self._setup_database_dir()

        # Register all enabled modules
        self._register_modules()

        # Set up auto-injection for analytics scripts
        self._setup_auto_injection()

        # Store reference on app for access in templates/routes
        app.extensions['lozzalingo'] = self

        # Add template context processor
        @app.context_processor
        def inject_lozzalingo():
            return {
                'lozzalingo_config': self.config,
                'brand_name': self.config.get('brand_name', 'Lozzalingo Site'),
            }

        # Add template global functions
        @app.template_global()
        def file_version(filename):
            """Generate a version string for static files based on modification time"""
            import time
            try:
                static_path = os.path.join(app.static_folder, filename)
                if os.path.exists(static_path):
                    return str(int(os.path.getmtime(static_path)))
                return str(int(time.time()))
            except:
                return "1"

        @app.template_global()
        def current_year():
            """Get current year for footer"""
            import time
            return time.strftime('%Y')

    @property
    def config(self) -> dict:
        """Get the merged configuration."""
        return self._config

    def _merge_config(self, user_config: dict) -> dict:
        """Merge user config with defaults (deep merge)."""
        result = self._deep_copy(self.DEFAULT_CONFIG)
        self._deep_merge(result, user_config)
        return result

    def _deep_copy(self, obj):
        """Deep copy a dict."""
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(item) for item in obj]
        return obj

    def _deep_merge(self, base: dict, override: dict):
        """Deep merge override into base (modifies base in place)."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def _load_yaml_config(self):
        """Load configuration from lozzalingo.yaml if it exists."""
        yaml_paths = [
            os.path.join(self.app.root_path, 'lozzalingo.yaml'),
            os.path.join(self.app.root_path, 'lozzalingo.yml'),
            os.path.join(os.getcwd(), 'lozzalingo.yaml'),
            os.path.join(os.getcwd(), 'lozzalingo.yml'),
        ]

        for yaml_path in yaml_paths:
            if os.path.exists(yaml_path):
                try:
                    with open(yaml_path, 'r') as f:
                        yaml_config = yaml.safe_load(f) or {}

                    # Map YAML structure to our config structure
                    mapped_config = self._map_yaml_config(yaml_config)
                    self._deep_merge(self._config, mapped_config)

                    self.app.logger.info(f"Loaded Lozzalingo config from {yaml_path}")
                    break
                except Exception as e:
                    self.app.logger.warning(f"Failed to load {yaml_path}: {e}")

    def _map_yaml_config(self, yaml_config: dict) -> dict:
        """Map YAML config structure to internal config structure."""
        # INTEGRATION: YAML keys != internal config keys. e.g. site.name -> brand_name,
        # admin.email -> email.admin_email. See mapping below; adding a YAML key without
        # mapping it here means it will be silently ignored.
        result = {}

        # Map site section
        if 'site' in yaml_config:
            site = yaml_config['site']
            if 'name' in site:
                result['brand_name'] = site['name']
            if 'tagline' in site:
                result['brand_tagline'] = site['tagline']

        # Map features section
        if 'features' in yaml_config:
            result['features'] = yaml_config['features']

        # Map admin section
        if 'admin' in yaml_config:
            admin = yaml_config['admin']
            if 'email' in admin:
                result.setdefault('email', {})['admin_email'] = admin['email']

        # Map email section
        if 'email' in yaml_config:
            result['email'] = yaml_config['email']

        # Map analytics section
        if 'analytics' in yaml_config:
            result['analytics'] = yaml_config['analytics']

        # Map auth section
        if 'auth' in yaml_config:
            result['auth'] = yaml_config['auth']

        return result

    def _configure_flask_app(self):
        """Configure Flask app with our settings."""
        # Secret key
        if not self.app.secret_key:
            secret = self._config.get('secret_key') or os.environ.get('SECRET_KEY')
            if secret:
                self.app.secret_key = secret
            else:
                # Generate a random one for development (warn in production)
                import secrets
                self.app.secret_key = secrets.token_hex(32)
                self.app.logger.warning(
                    "No SECRET_KEY set. Generated random key. "
                    "Set SECRET_KEY environment variable for production."
                )

        # Email configuration
        email_config = self._config.get('email', {})
        self.app.config.setdefault('RESEND_API_KEY',
            email_config.get('resend_api_key') or os.environ.get('RESEND_API_KEY'))
        self.app.config.setdefault('EMAIL_ADDRESS',
            email_config.get('from_address') or os.environ.get('EMAIL_ADDRESS'))
        self.app.config.setdefault('EMAIL_BRAND_NAME', self._config.get('brand_name'))
        self.app.config.setdefault('EMAIL_BRAND_TAGLINE', self._config.get('brand_tagline'))
        self.app.config.setdefault('EMAIL_SUPPORT_EMAIL', email_config.get('support_email'))
        self.app.config.setdefault('EMAIL_ADMIN_EMAIL', email_config.get('admin_email'))

        # Database configuration
        db_dir = os.path.join(self.app.root_path, self._config.get('db_dir', 'databases'))
        self.app.config.setdefault('DB_DIR', db_dir)
        self.app.config.setdefault('USER_DB', os.path.join(db_dir, 'users.db'))
        self.app.config.setdefault('NEWS_DB', os.path.join(db_dir, 'news.db'))
        self.app.config.setdefault('ANALYTICS_DB', os.path.join(db_dir, 'analytics.db'))
        self.app.config.setdefault('PROJECTS_DB', os.path.join(db_dir, 'projects.db'))
        self.app.config.setdefault('QUICK_LINKS_DB', os.path.join(db_dir, 'quick_links.db'))

        # Auth configuration
        auth_config = self._config.get('auth', {})
        self.app.config.setdefault('GOOGLE_CLIENT_ID',
            auth_config.get('google_client_id') or os.environ.get('GOOGLE_CLIENT_ID'))
        self.app.config.setdefault('GOOGLE_CLIENT_SECRET',
            auth_config.get('google_client_secret') or os.environ.get('GOOGLE_CLIENT_SECRET'))
        self.app.config.setdefault('GITHUB_CLIENT_ID',
            auth_config.get('github_client_id') or os.environ.get('GITHUB_CLIENT_ID'))
        self.app.config.setdefault('GITHUB_CLIENT_SECRET',
            auth_config.get('github_client_secret') or os.environ.get('GITHUB_CLIENT_SECRET'))

    def _setup_database_dir(self):
        """Ensure database directory exists."""
        # INTEGRATION: DB_DIR defaults to app.root_path-relative. Inside Docker, CWD and
        # root_path may differ from local dev -- always set DB_DIR explicitly via env var.
        db_dir = self.app.config.get('DB_DIR',
            os.path.join(self.app.root_path, 'databases'))
        os.makedirs(db_dir, exist_ok=True)

    def _register_modules(self):
        """Register all enabled module blueprints."""
        # INTEGRATION: Registration order matters. Dashboard must be first (other modules
        # reference its templates/routes). Email must come before orders/subscribers.
        features = self._config.get('features', {})

        # Dashboard (admin core) - always register first as other modules depend on it
        if features.get('dashboard', True):
            self._register_dashboard()

        # Analytics
        if features.get('analytics', True):
            self._register_analytics()

        # Auth (user authentication)
        if features.get('auth', True):
            self._register_auth()

        # News (admin)
        if features.get('news', True):
            self._register_news()

        # News Public
        if features.get('news_public', True):
            self._register_news_public()

        # Email
        if features.get('email', True):
            self._register_email()

        # Customer Spotlight
        if features.get('customer_spotlight', True):
            self._register_customer_spotlight()

        # Merchandise
        if features.get('merchandise', True):
            self._register_merchandise()

        # Merchandise Public API (product embed)
        if features.get('merchandise_public', True):
            self._register_merchandise_public()

        # Orders
        if features.get('orders', True):
            self._register_orders()

        # External API
        if features.get('external_api', True):
            self._register_external_api()

        # Settings
        if features.get('settings', True):
            self._register_settings()

        # Projects (admin)
        if features.get('projects', False):
            self._register_projects()

        # Projects Public
        if features.get('projects_public', False):
            self._register_projects_public()

        # Quick Links
        if features.get('quick_links', False):
            self._register_quick_links()

    def _register_dashboard(self):
        """Register the admin dashboard module."""
        try:
            from .modules.dashboard import dashboard_bp
            self.app.register_blueprint(dashboard_bp)
            self._registered_blueprints.append('dashboard')
            self.app.logger.debug("Registered dashboard module")
        except Exception as e:
            self.app.logger.error(f"Failed to register dashboard module: {e}")

    def _register_analytics(self):
        """Register the analytics module."""
        try:
            from .modules.analytics import analytics_bp
            self.app.register_blueprint(analytics_bp, url_prefix='/admin/analytics')
            self._registered_blueprints.append('analytics')
            self.app.logger.debug("Registered analytics module")
        except Exception as e:
            self.app.logger.error(f"Failed to register analytics module: {e}")

    def _register_auth(self):
        """Register the auth module."""
        try:
            from .modules.auth import auth_bp, configure_oauth, init_oauth, oauth
            self.app.register_blueprint(auth_bp)

            # Configure OAuth if credentials are available
            if (self.app.config.get('GOOGLE_CLIENT_ID') or
                self.app.config.get('GITHUB_CLIENT_ID')):
                configure_oauth(self.app)
                init_oauth(oauth)

            self._registered_blueprints.append('auth')
            self.app.logger.debug("Registered auth module")
        except Exception as e:
            self.app.logger.error(f"Failed to register auth module: {e}")

    def _register_news(self):
        """Register the news admin module."""
        try:
            from .modules.news import news_bp
            self.app.register_blueprint(news_bp)
            self._registered_blueprints.append('news')
            self.app.logger.debug("Registered news module")
        except Exception as e:
            self.app.logger.error(f"Failed to register news module: {e}")

    def _register_news_public(self):
        """Register the public news module."""
        try:
            from .modules.news_public import news_public_bp
            self.app.register_blueprint(news_public_bp)
            self._registered_blueprints.append('news_public')
            self.app.logger.debug("Registered news_public module")
        except Exception as e:
            self.app.logger.error(f"Failed to register news_public module: {e}")

    def _register_email(self):
        """Register the email module."""
        try:
            from .modules.email import email_preview_bp, email_service

            # Initialize email service
            email_service.init_app(self.app)

            # Register preview blueprint
            self.app.register_blueprint(email_preview_bp)
            self._registered_blueprints.append('email')
            self.app.logger.debug("Registered email module")
        except Exception as e:
            self.app.logger.error(f"Failed to register email module: {e}")

    def _register_customer_spotlight(self):
        """Register the customer spotlight module."""
        try:
            from .modules.customer_spotlight import customer_spotlight_bp
            self.app.register_blueprint(customer_spotlight_bp)
            self._registered_blueprints.append('customer_spotlight')
            self.app.logger.debug("Registered customer_spotlight module")
        except Exception as e:
            self.app.logger.error(f"Failed to register customer_spotlight module: {e}")

    def _register_merchandise(self):
        """Register the merchandise module."""
        try:
            from .modules.merchandise import merchandise_bp
            self.app.register_blueprint(merchandise_bp)
            self._registered_blueprints.append('merchandise')
            self.app.logger.debug("Registered merchandise module")
        except Exception as e:
            self.app.logger.error(f"Failed to register merchandise module: {e}")

    def _register_merchandise_public(self):
        """Register the public merchandise API module."""
        try:
            from .modules.merchandise_public import merchandise_public_bp
            self.app.register_blueprint(merchandise_public_bp)
            self._registered_blueprints.append('merchandise_public')
            self.app.logger.debug("Registered merchandise_public module")
        except Exception as e:
            self.app.logger.error(f"Failed to register merchandise_public module: {e}")

    def _register_orders(self):
        """Register the orders module."""
        try:
            from .modules.orders import orders_bp
            self.app.register_blueprint(orders_bp)
            self._registered_blueprints.append('orders')
            self.app.logger.debug("Registered orders module")
        except Exception as e:
            self.app.logger.error(f"Failed to register orders module: {e}")

    def _register_external_api(self):
        """Register the external API module."""
        try:
            from .modules.external_api import external_api_bp, external_api_admin_bp
            self.app.register_blueprint(external_api_bp)
            self.app.register_blueprint(external_api_admin_bp)
            self._registered_blueprints.append('external_api')
            self.app.logger.debug("Registered external_api module")
        except Exception as e:
            self.app.logger.error(f"Failed to register external_api module: {e}")

    def _register_settings(self):
        """Register the settings module."""
        try:
            from .modules.settings import settings_bp
            self.app.register_blueprint(settings_bp)
            self._registered_blueprints.append('settings')
            self.app.logger.debug("Registered settings module")
        except Exception as e:
            self.app.logger.error(f"Failed to register settings module: {e}")

    def _register_projects(self):
        """Register the projects admin module."""
        try:
            from .modules.projects import projects_bp
            self.app.register_blueprint(projects_bp)
            self._registered_blueprints.append('projects')
            self.app.logger.debug("Registered projects module")
        except Exception as e:
            self.app.logger.error(f"Failed to register projects module: {e}")

    def _register_projects_public(self):
        """Register the public projects module."""
        try:
            from .modules.projects_public import projects_public_bp
            self.app.register_blueprint(projects_public_bp)
            self._registered_blueprints.append('projects_public')
            self.app.logger.debug("Registered projects_public module")
        except Exception as e:
            self.app.logger.error(f"Failed to register projects_public module: {e}")

    def _register_quick_links(self):
        """Register the quick links module."""
        try:
            from .modules.quick_links import quick_links_admin_bp, quick_links_bp
            self.app.register_blueprint(quick_links_admin_bp)
            self.app.register_blueprint(quick_links_bp)
            self._registered_blueprints.append('quick_links')
            self.app.logger.debug("Registered quick_links module")
        except Exception as e:
            self.app.logger.error(f"Failed to register quick_links module: {e}")

    def _setup_auto_injection(self):
        """Set up automatic script injection for analytics."""
        # INTEGRATION: This after_request hook injects analytics JS into ALL HTML responses
        # (except /admin when track_admin=False). It modifies response bodies in-flight.
        # If your app returns HTML from non-admin routes, those responses WILL be modified.
        features = self._config.get('features', {})

        if not features.get('analytics', True):
            return

        @self.app.after_request
        def inject_analytics_scripts(response):
            """Inject analytics scripts into HTML responses."""
            # Only inject into HTML responses
            if response.content_type and 'text/html' not in response.content_type:
                return response

            # Don't inject into admin pages if configured
            analytics_config = self._config.get('analytics', {})
            if not analytics_config.get('track_admin', False):
                from flask import request
                if request.path.startswith('/admin'):
                    return response

            # Get the response data
            try:
                data = response.get_data(as_text=True)
            except Exception:
                return response

            # Check if </body> exists
            if '</body>' not in data.lower():
                return response

            # Inject analytics scripts before </body>
            analytics_scripts = '''
    <!-- Lozzalingo Analytics -->
    <script src="/admin/analytics/static/js/analytics.js"></script>
    <script src="/admin/analytics/static/js/device_analytics.js"></script>
'''

            # Find </body> case-insensitively and inject before it
            import re
            data = re.sub(
                r'(</body>)',
                analytics_scripts + r'\1',
                data,
                flags=re.IGNORECASE,
                count=1
            )

            response.set_data(data)
            return response

    def get_registered_modules(self) -> list:
        """Get list of registered module names."""
        return self._registered_blueprints.copy()


# Convenience exports
from .modules import analytics, auth, dashboard

__all__ = [
    'Lozzalingo',
    'analytics',
    'auth',
    'dashboard',
    '__version__',
]
