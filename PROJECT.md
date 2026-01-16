# Lozzalingo Framework - Project Overview

## Vision

A plug-and-play Flask framework that lets you spin up new websites in minutes with built-in analytics, admin dashboard, email, and authentication - all working out of the box.

**Goal:** New site setup should be as simple as:
```python
from flask import Flask
from lozzalingo import Lozzalingo

app = Flask(__name__)
lozzalingo = Lozzalingo(app)
```

## Current State

The framework exists with 10 modules but:
- Integration is complex (900+ line INTEGRATION.md)
- No projects actually use it (Mario Pinto and crowd_sauced have local implementations)
- Requires manual configuration for each module
- Analytics requires editing framework source code for allowed origins
- No out-of-the-box template exists

## Target State

### 1. Simple Integration
- Single `Lozzalingo(app)` call enables everything
- Sensible defaults for all configuration
- Auto-detection of domains for analytics
- Auto-injection of tracking scripts
- Zero-config database initialization

### 2. Starter Template (Like Django's Batteries-Included Approach)
A complete, ready-to-run project at `/starter-template/` that you duplicate and run:

**What you get immediately:**
- Hello World frontend at `/`
- Full admin backend at `/admin` (like Django admin)
- All 10 modules working out of the box
- Analytics tracking from first page load
- Docker OR Flask dev server

**How to use:**
```bash
# Option 1: Flask dev server
cp -r starter-template my-new-site
cd my-new-site
pip install -r requirements.txt
python app.py
# Visit http://localhost:5000 → Hello World
# Visit http://localhost:5000/admin → Admin panel

# Option 2: Docker
cp -r starter-template my-new-site
cd my-new-site
docker-compose up
```

**Available routes out of box:**
| Route | Description |
|-------|-------------|
| `/` | Hello World homepage |
| `/about` | Example about page |
| `/admin/login` | Admin login |
| `/admin/dashboard` | Admin dashboard with all modules |
| `/admin/analytics` | Analytics dashboard |
| `/admin/news-editor` | News/blog editor |
| `/admin/customer-spotlight-editor` | Customer gallery manager |
| `/admin/email-preview` | Email template preview |
| `/admin/api-keys` | API key management |
| `/news/` | Public news/blog listing |
| `/login` | User login |
| `/register` | User registration |

### 3. Module Documentation
Each module gets a dedicated README explaining:
- What it does
- How to use it
- Required HTML attributes/classes for integration
- Configuration options
- Extension points

## Architecture

```
lozzalingo-framework/
├── lozzalingo/
│   ├── __init__.py              # Main Lozzalingo class - single entry point
│   ├── core/
│   │   ├── config.py            # Unified configuration with defaults
│   │   ├── database.py          # Auto-initializing database layer
│   │   └── injector.py          # NEW: Auto-inject scripts into responses
│   └── modules/
│       ├── analytics/           # Page view & event tracking
│       ├── auth/                # User authentication
│       ├── customer_spotlight/  # Customer gallery
│       ├── dashboard/           # Admin dashboard
│       ├── email/               # Email service
│       ├── external_api/        # API key auth
│       ├── merchandise/         # Product management
│       ├── news/                # News/blog admin
│       ├── news_public/         # Public blog display
│       └── orders/              # Order management
├── starter-template/            # Complete out-of-box project
│   ├── app.py                   # Flask app with Lozzalingo init
│   ├── templates/
│   │   ├── base.html            # Base template with nav, footer
│   │   ├── index.html           # Hello World homepage
│   │   └── about.html           # Example additional page
│   ├── static/
│   │   ├── css/style.css        # Clean default styling
│   │   ├── favicon.ico
│   │   └── robots.txt
│   ├── databases/               # Auto-created SQLite DBs
│   │   └── .gitkeep
│   ├── lozzalingo.yaml          # Site configuration (all modules on)
│   ├── requirements.txt         # All dependencies
│   ├── .env.example             # Environment template
│   ├── run.sh                   # One-command startup
│   ├── Dockerfile               # Production container
│   ├── docker-compose.yml       # Easy Docker deployment
│   └── README.md                # Quick start guide
├── docs/                        # NEW: Module documentation
│   ├── analytics.md
│   ├── auth.md
│   ├── dashboard.md
│   ├── email.md
│   └── ...
├── PROJECT.md                   # This file
├── TODO.md                      # Task tracking
└── README.md                    # Updated quick start

```

## Key Design Decisions

### 1. Auto-injection over manual setup
Instead of requiring users to add `<script>` tags, we inject them automatically via Flask's `after_request` hook into any HTML response.

### 2. Convention over configuration
- Database files go in `./databases/` by default
- Admin is always at `/admin`
- Analytics endpoint auto-allows the request origin

### 3. Progressive disclosure
- Basic usage: `Lozzalingo(app)` - everything works with defaults
- Customization: Pass config dict or use `lozzalingo.yaml`
- Advanced: Override individual modules or templates

### 4. Required HTML structure
For modules to work, templates need specific attributes:
- Analytics: No requirements (auto-tracks all pages)
- Customer Spotlight: `<div id="customer-spotlight"></div>`
- News: Links with `href="/news/..."`

## Success Criteria

1. **5-minute setup**: Clone starter-template, run, see Hello World with working analytics
2. **Zero framework code changes**: Adding a new site never requires editing lozzalingo source
3. **Self-documenting**: Each module README is complete enough to use without asking
4. **Actually used**: Migrate crowd_sauced to use the framework as proof

## Module Status

| Module | Works Standalone | Documented | Auto-init | Tested |
|--------|-----------------|------------|-----------|--------|
| analytics | Partial | No | No | No |
| auth | Partial | No | No | No |
| customer_spotlight | Partial | No | No | No |
| dashboard | Partial | No | No | No |
| email | Partial | No | No | No |
| external_api | Partial | No | No | No |
| merchandise | Partial | No | No | No |
| news | Partial | No | No | No |
| news_public | Partial | No | No | No |
| orders | Partial | No | No | No |

## Configuration Reference

### Minimal (defaults for everything)
```python
lozzalingo = Lozzalingo(app)
```

### Common customization
```python
lozzalingo = Lozzalingo(app, {
    'brand_name': 'My Site',
    'admin_email': 'admin@example.com',
})
```

### Full configuration (lozzalingo.yaml)
```yaml
site:
  name: "My Site"
  domain: "mysite.com"

admin:
  email: "admin@mysite.com"

email:
  resend_api_key: "${RESEND_API_KEY}"  # From environment
  from_address: "noreply@mysite.com"

analytics:
  enabled: true
  track_admin: false  # Don't track admin pages

features:
  auth: true
  news: true
  merchandise: false
  customer_spotlight: true
```

## Next Steps

See TODO.md for the complete task list. Work through items in order.
