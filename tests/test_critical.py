"""
Critical Integration Tests for Lozzalingo Framework
====================================================

~10 focused tests covering the integration points most likely to break.
Run with: pytest tests/test_critical.py -v

NOTE: pytest is listed under extras_require["dev"] in setup.py.
Install with: pip install -e ".[dev]"
"""

import os
import shutil
import tempfile
from unittest.mock import patch, MagicMock

import pytest
from flask import Flask

from lozzalingo import Lozzalingo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db_dir():
    """Create a temporary directory for test databases, cleaned up after."""
    d = tempfile.mkdtemp(prefix="lozzalingo-test-")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def app(tmp_db_dir):
    """Fully initialised Flask app with all Lozzalingo modules registered."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    app.config["DB_DIR"] = tmp_db_dir
    app.config["USER_DB"] = os.path.join(tmp_db_dir, "users.db")
    app.config["NEWS_DB"] = os.path.join(tmp_db_dir, "news.db")
    app.config["ANALYTICS_DB"] = os.path.join(tmp_db_dir, "analytics.db")
    app.config["PROJECTS_DB"] = os.path.join(tmp_db_dir, "projects.db")
    app.config["QUICK_LINKS_DB"] = os.path.join(tmp_db_dir, "quick_links.db")
    # Prevent real OAuth init -- no credentials set
    lozzalingo = Lozzalingo(app, {
        'features': {
            'projects': True,
            'projects_public': True,
            'quick_links': True,
        }
    })
    return app


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# 1. Framework initialisation -- Lozzalingo(app) does not raise
# ---------------------------------------------------------------------------

def test_framework_initialisation(tmp_db_dir):
    """Lozzalingo(app) boots without errors and stores itself on the app."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    app.config["DB_DIR"] = tmp_db_dir
    app.config["USER_DB"] = os.path.join(tmp_db_dir, "users.db")
    app.config["NEWS_DB"] = os.path.join(tmp_db_dir, "news.db")
    app.config["ANALYTICS_DB"] = os.path.join(tmp_db_dir, "analytics.db")
    app.config["PROJECTS_DB"] = os.path.join(tmp_db_dir, "projects.db")
    app.config["QUICK_LINKS_DB"] = os.path.join(tmp_db_dir, "quick_links.db")

    lozzalingo = Lozzalingo(app, {
        'features': {
            'projects': True,
            'projects_public': True,
            'quick_links': True,
        }
    })

    assert "lozzalingo" in app.extensions
    assert app.extensions["lozzalingo"] is lozzalingo


# ---------------------------------------------------------------------------
# 2. Config resolution -- DB paths are non-empty and contain expected names
# ---------------------------------------------------------------------------

def test_config_db_paths(app):
    """DB_DIR, USER_DB, NEWS_DB, ANALYTICS_DB resolve to non-empty paths
    containing expected filenames."""
    assert app.config["DB_DIR"], "DB_DIR must not be empty"
    assert "users.db" in app.config["USER_DB"]
    assert "news.db" in app.config["NEWS_DB"]
    assert "analytics.db" in app.config["ANALYTICS_DB"]


# ---------------------------------------------------------------------------
# 3. Email service init (Resend) -- init_app with Resend config does not crash
# ---------------------------------------------------------------------------

def test_email_service_init_resend(app):
    """EmailService.init_app() with Resend provider stores config correctly."""
    from lozzalingo.modules.email.email_service import EmailService

    svc = EmailService()
    app.config["RESEND_API_KEY"] = "re_test_fake_key_123"
    app.config["EMAIL_PROVIDER"] = "resend"
    app.config["EMAIL_BRAND_NAME"] = "TestBrand"

    with app.app_context():
        svc.init_app(app)

    assert svc.provider == "resend"
    assert svc.brand_name == "TestBrand"
    assert svc.api_key == "re_test_fake_key_123"


# ---------------------------------------------------------------------------
# 4. Email service init (SES) -- init_app with SES config does not crash
# ---------------------------------------------------------------------------

def test_email_service_init_ses(app):
    """EmailService.init_app() with SES provider does not crash even if
    boto3 is not installed (it logs a warning instead)."""
    from lozzalingo.modules.email.email_service import EmailService

    svc = EmailService()
    app.config["EMAIL_PROVIDER"] = "ses"
    app.config["AWS_REGION"] = "us-east-1"

    with app.app_context():
        svc.init_app(app)

    assert svc.provider == "ses"


# ---------------------------------------------------------------------------
# 5. Blueprint registration -- all 11 expected modules are registered
# ---------------------------------------------------------------------------

EXPECTED_MODULES = [
    "dashboard",
    "analytics",
    "auth",
    "news",
    "news_public",
    "email",
    "customer_spotlight",
    "merchandise",
    "merchandise_public",
    "orders",
    "external_api",
    "settings",
    "projects",
    "projects_public",
    "quick_links",
    "ops",
]


def test_all_blueprints_registered(app):
    """All 11 feature modules should be registered as blueprints."""
    lozzalingo_ext = app.extensions["lozzalingo"]
    registered = lozzalingo_ext.get_registered_modules()

    for mod in EXPECTED_MODULES:
        assert mod in registered, (
            f"Module '{mod}' was not registered. Registered: {registered}"
        )

    assert len(registered) == len(EXPECTED_MODULES)


# ---------------------------------------------------------------------------
# 6. Template context -- lozzalingo_config and brand_name are injected
# ---------------------------------------------------------------------------

def test_template_context_injection(app):
    """Context processor injects lozzalingo_config and brand_name."""
    with app.test_request_context("/"):
        # Gather all context processor results
        ctx = {}
        for func in app.template_context_processors[None]:
            ctx.update(func())

        assert "lozzalingo_config" in ctx, "lozzalingo_config missing from template context"
        assert "brand_name" in ctx, "brand_name missing from template context"
        assert isinstance(ctx["lozzalingo_config"], dict)
        assert isinstance(ctx["brand_name"], str)
        assert len(ctx["brand_name"]) > 0


# ---------------------------------------------------------------------------
# 7. Database directory creation -- _setup_database_dir creates the dir
# ---------------------------------------------------------------------------

def test_database_dir_creation():
    """_setup_database_dir creates the configured DB_DIR on disk."""
    d = tempfile.mkdtemp(prefix="lozzalingo-dbtest-")
    target = os.path.join(d, "sub", "databases")

    try:
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "test-secret"
        app.config["DB_DIR"] = target
        app.config["USER_DB"] = os.path.join(target, "users.db")
        app.config["NEWS_DB"] = os.path.join(target, "news.db")
        app.config["ANALYTICS_DB"] = os.path.join(target, "analytics.db")
        app.config["PROJECTS_DB"] = os.path.join(target, "projects.db")
        app.config["QUICK_LINKS_DB"] = os.path.join(target, "quick_links.db")

        Lozzalingo(app, {
            'features': {
                'projects': True,
                'projects_public': True,
                'quick_links': True,
            }
        })

        assert os.path.isdir(target), f"DB_DIR was not created at {target}"
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# 8. Config from YAML -- YAML keys are mapped to internal config keys
# ---------------------------------------------------------------------------

def test_yaml_config_mapping(tmp_db_dir):
    """_map_yaml_config correctly maps site.name -> brand_name and
    admin.email -> email.admin_email."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    app.config["DB_DIR"] = tmp_db_dir
    app.config["USER_DB"] = os.path.join(tmp_db_dir, "users.db")
    app.config["NEWS_DB"] = os.path.join(tmp_db_dir, "news.db")
    app.config["ANALYTICS_DB"] = os.path.join(tmp_db_dir, "analytics.db")

    lz = Lozzalingo.__new__(Lozzalingo)
    lz._config = {}

    yaml_input = {
        "site": {"name": "My Test Site", "tagline": "A tagline"},
        "admin": {"email": "admin@test.com"},
        "features": {"news": False},
    }

    mapped = lz._map_yaml_config(yaml_input)

    assert mapped["brand_name"] == "My Test Site"
    assert mapped["brand_tagline"] == "A tagline"
    assert mapped["email"]["admin_email"] == "admin@test.com"
    assert mapped["features"]["news"] is False


# ---------------------------------------------------------------------------
# 9. Subscriber route exists -- POST /api/subscribers/ is registered
# ---------------------------------------------------------------------------

def test_subscriber_post_route_exists(tmp_db_dir):
    """When the subscribers blueprint is registered, POST /api/subscribers
    appears in the app's URL map.  The subscribers module is not auto-registered
    by Lozzalingo -- consuming apps register it explicitly."""
    from lozzalingo.modules.subscribers import subscribers_bp

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    app.config["DB_DIR"] = tmp_db_dir
    app.config["USER_DB"] = os.path.join(tmp_db_dir, "users.db")
    app.config["NEWS_DB"] = os.path.join(tmp_db_dir, "news.db")
    app.config["ANALYTICS_DB"] = os.path.join(tmp_db_dir, "analytics.db")
    app.config["PROJECTS_DB"] = os.path.join(tmp_db_dir, "projects.db")
    app.config["QUICK_LINKS_DB"] = os.path.join(tmp_db_dir, "quick_links.db")

    Lozzalingo(app, {
        'features': {
            'projects': True,
            'projects_public': True,
            'quick_links': True,
        }
    })
    app.register_blueprint(subscribers_bp)

    rules = [rule.rule for rule in app.url_map.iter_rules()]
    # Blueprint url_prefix is '/api/subscribers', route is '' -> '/api/subscribers'
    assert "/api/subscribers" in rules, (
        f"POST /api/subscribers route not found. Routes: {sorted(rules)}"
    )

    # Verify the route accepts POST
    post_methods = None
    for rule in app.url_map.iter_rules():
        if rule.rule == "/api/subscribers":
            post_methods = rule.methods
            break
    assert post_methods is not None
    assert "POST" in post_methods


# ---------------------------------------------------------------------------
# 10. Admin auth guard -- unauthenticated request to admin settings redirects
# ---------------------------------------------------------------------------

def test_admin_auth_redirect(client):
    """Unauthenticated GET to /admin/settings/ should redirect to login."""
    response = client.get("/admin/settings/", follow_redirects=False)
    # Should be a 302 redirect to the login page
    assert response.status_code == 302, (
        f"Expected 302 redirect, got {response.status_code}"
    )
    assert "/admin" in response.headers.get("Location", ""), (
        "Redirect location should point to /admin (login)"
    )


# ---------------------------------------------------------------------------
# 11. Template filters -- all custom Jinja filters are registered
# ---------------------------------------------------------------------------

EXPECTED_TEMPLATE_FILTERS = [
    "parse_gallery",
    "parse_insights",
    "format_project_content",
]


def test_template_filters_registered(app):
    """Custom Jinja template filters defined in blueprints must be available
    on the app after initialisation.  A missing filter causes
    TemplateAssertionError at render time."""
    registered_filters = app.jinja_env.filters

    for name in EXPECTED_TEMPLATE_FILTERS:
        assert name in registered_filters, (
            f"Template filter '{name}' is not registered. "
            f"Check that the blueprint defining it is imported and registered."
        )
        assert callable(registered_filters[name]), (
            f"Template filter '{name}' is registered but not callable."
        )


# ---------------------------------------------------------------------------
# 12. Health endpoint -- GET /health returns 200 with status and checks
# ---------------------------------------------------------------------------

def test_health_endpoint(client):
    """GET /health returns JSON with status field and checks dict.
    HTTP 200 for ok/warning, 503 for critical — both are valid."""
    response = client.get("/health")
    assert response.status_code in (200, 503), (
        f"Expected 200 or 503, got {response.status_code}"
    )
    data = response.get_json()
    assert "status" in data, "Health response missing 'status' field"
    assert data["status"] in ("ok", "warning", "critical")
    assert "checks" in data, "Health response missing 'checks' dict"
    assert "disk" in data["checks"]
    assert "memory" in data["checks"]
    assert "uptime" in data["checks"]


# ---------------------------------------------------------------------------
# 13. Ops admin auth guard -- unauthenticated request redirects to login
# ---------------------------------------------------------------------------

def test_ops_admin_auth_redirect(client):
    """Unauthenticated GET to /admin/ops/ should redirect to login."""
    response = client.get("/admin/ops/", follow_redirects=False)
    assert response.status_code == 302, (
        f"Expected 302 redirect, got {response.status_code}"
    )
    assert "/admin" in response.headers.get("Location", ""), (
        "Redirect location should point to /admin (login)"
    )
