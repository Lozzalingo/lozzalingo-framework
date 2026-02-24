# Lozzalingo Framework - Claude Guidelines
Shared framework rules are auto-loaded from the parent `Lozzalingo-python/CLAUDE.md`.

## Architecture
- Batteries-included Flask admin framework, installed via `pip install` from git
- Entry point: `Lozzalingo(app)` in host app — auto-registers all modules
- Alternative: host apps can manually import individual blueprints (Mario Pinto does this)
- Version: 0.2.0, defined in `lozzalingo/__init__.py`

## Modules (17 total)
analytics, auth, customer_spotlight, dashboard, email, external_api, inkthreadable, merchandise, merchandise_public, news, news_public, ops, orders, settings, subscribers

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

### Dependencies
- `flask-cors` is required by `merchandise_public` — host apps must have it in their requirements.txt
- Core deps: Flask, Flask-SQLAlchemy, Flask-CORS, python-dotenv, requests, PyYAML

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
| laurence.computer | Symlink (`lozzalingo -> ../lozzalingo-framework/lozzalingo`) | `Lozzalingo(app)` auto | DigitalOcean 143.110.152.203 |
| Crowd Sauced | Symlink (`lozzalingo -> lozzalingo-repo/lozzalingo`) | Manual imports in `main.py` | DigitalOcean 143.110.152.203 |
| Mario Pinto | `pip install` from git | Manual imports in `app/__init__.py` | AWS EC2 eu-north-1 |

### Updating Framework on Servers
- **laurence.computer**: `cd /var/www/laurence.computer/lozzalingo-repo && git pull` then `docker compose up -d --build`
- **Crowd Sauced**: `cd /var/www/crowd-sauced/lozzalingo-repo && git pull` then `docker compose up -d --build`
- **Mario Pinto**: `docker compose exec -T web pip install --no-cache-dir --force-reinstall git+https://github.com/Lozzalingo/lozzalingo-framework.git@main` then `docker compose restart web`

## Key Files
- Entry point: `lozzalingo/__init__.py` (Lozzalingo class, module registration, config)
- Modules: `lozzalingo/modules/<name>/` (each has `__init__.py` + `routes.py`)
- Tests: `tests/test_critical.py` (13 tests, EXPECTED_MODULES list)
- Setup: `setup.py` (package metadata, dependencies)
- Server hardening: `scripts/server-setup.sh` (swap, Docker cleanup, log rotation, unattended-upgrades)

## Ops Module
- **Public endpoint**: `GET /health` — JSON health check (no auth), returns `{status, checks: {disk, memory, uptime}, issues}`
- **Admin dashboard**: `/admin/ops` — disk/memory/swap/uptime/load cards, error feed, Docker cleanup
- **Alerts**: `lozzalingo/modules/ops/alerts.py` — email alerts rate-limited to 1 per issue type per 6h via `app_logs` (source=`ops_alert`)
- **Banner injection**: `_setup_ops_banner_injection()` in `__init__.py` — injects amber/red warning bar on admin pages when issues are detected
- **Monitoring**: `_setup_ops_monitoring()` — runs health checks every 5min on admin page loads, triggers alerts if thresholds crossed
- **Thresholds**: disk 80%=warning/90%=critical, memory 85%/95%, no swap=warning, >10 errors/hour=error_spike
- **Two-blueprint pattern** (same as `external_api`): `ops_health_bp` (public) + `ops_admin_bp` (admin)
- **Host apps with manual registration** (Mario Pinto, Crowd Sauced) need: `from lozzalingo.modules.ops import ops_health_bp, ops_admin_bp` + `register_blueprint()` for both

## After Making Changes
- Run `pytest tests/test_critical.py -v` (install pytest via `pip install -e ".[dev]"`)
- Update EXPECTED_MODULES in tests if adding/removing modules
- Consider impact on ALL host apps — framework changes affect every site
