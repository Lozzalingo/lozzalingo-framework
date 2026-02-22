# Lozzalingo Framework - Claude Guidelines

## Architecture
- Batteries-included Flask admin framework, installed via `pip install` from git
- Entry point: `Lozzalingo(app)` in host app — auto-registers all modules
- Alternative: host apps can manually import individual blueprints (Mario Pinto does this)
- Version: 0.2.0, defined in `lozzalingo/__init__.py`

## Modules (16 total)
analytics, auth, customer_spotlight, dashboard, email, external_api, inkthreadable, merchandise, merchandise_public, news, news_public, orders, settings, subscribers

All enabled by default via `DEFAULT_CONFIG['features']`. Host apps can disable with:
```python
Lozzalingo(app, {'features': {'news': False}})
```

## Critical Warnings

### Adding New Modules
When adding a new module:
1. Create `lozzalingo/modules/<name>/__init__.py` with Blueprint
2. Create `lozzalingo/modules/<name>/routes.py`
3. Add feature flag to `DEFAULT_CONFIG['features']` in `__init__.py`
4. Add `_register_<name>()` method and call it from `_register_modules()`
5. Add module name to `EXPECTED_MODULES` list in `tests/test_critical.py`
6. **Host apps that manually register blueprints (Mario Pinto) need explicit import + register_blueprint()**
7. **Host apps with test mocks (Crowd Sauced) need the mock list updated**

### DB Schema Compatibility
- Different host apps have different DB schemas (e.g. Mario Pinto products table lacks `category`, `shop_name`, `print_on_demand`)
- Framework SQL queries MUST detect available columns dynamically using `PRAGMA table_info`
- Never assume optional columns exist — use safe defaults

### Admin Creation Security
- The "Create one here" link on the login page is ONLY shown when the host is localhost/127.0.0.1
- In production, the link is hidden — admins can only be created by logged-in admins via the dashboard
- The `/admin/create-admin` route still allows unauthenticated access when zero admins exist (bootstrap case)
- NEVER make the create-admin link publicly visible in production

### Dependencies
- `flask-cors` is required by `merchandise_public` — host apps must have it in their requirements.txt
- Core deps: Flask, Flask-SQLAlchemy, Flask-CORS, python-dotenv, requests, PyYAML

### Config Pattern for Modules
All modules MUST use the 3-tier `get_db_config()` pattern for DB paths and table names — NEVER access `Config.ANALYTICS_DB` (or similar) directly at module level. The pattern:
1. `current_app.config.get('KEY')` — Flask app config (highest priority)
2. `Config.KEY` with `hasattr()` guard — framework default
3. `os.getenv('KEY', 'fallback')` — env var fallback

This prevents `AttributeError` when host apps define their own Config class without all framework attributes.

### New Host App Setup
When creating a new host app:
1. Define a `Config` class with at minimum: `ANALYTICS_DB`, `ANALYTICS_TABLE`, `NEWS_DB`, `USER_DB`, `MERCHANDISE`
2. Or set equivalent env vars (`ANALYTICS_DB`, `NEWS_DB`, etc.)
3. Create a `databases/` directory — all DB files go here
4. The analytics table auto-creates on first request, but you can call `Analytics.init_analytics_db()` explicitly
5. Reference: `laurencedotcomputer` is the simplest host app example

## Host Apps
| App | Install Method | Registration | Server |
|-----|---------------|-------------|--------|
| Crowd Sauced | Symlink (`lozzalingo -> lozzalingo-repo/lozzalingo`) | Manual imports in `main.py` | DigitalOcean 143.110.152.203 |
| Mario Pinto | `pip install` from git | Manual imports in `app/__init__.py` | AWS EC2 eu-north-1 |

### Updating Framework on Servers
- **Crowd Sauced**: `cd /var/www/crowd-sauced/lozzalingo-repo && git pull` then `docker compose up -d --build` (must rebuild image)
- **Mario Pinto**: `docker compose exec -T web pip install --no-cache-dir --force-reinstall git+https://github.com/Lozzalingo/lozzalingo-framework.git@main` then `docker compose restart web`

## Key Files
- Entry point: `lozzalingo/__init__.py` (Lozzalingo class, module registration, config)
- Modules: `lozzalingo/modules/<name>/` (each has `__init__.py` + `routes.py`)
- Tests: `tests/test_critical.py` (10 tests, EXPECTED_MODULES list)
- Setup: `setup.py` (package metadata, dependencies)

## After Making Changes
- Run `pytest tests/test_critical.py -v` (install pytest via `pip install -e ".[dev]"`)
- Update EXPECTED_MODULES in tests if adding/removing modules
- Consider impact on ALL host apps — framework changes affect every site
