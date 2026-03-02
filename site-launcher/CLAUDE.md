# Site Launcher — AI-First Lozzalingo Site Creator

You are launching a new Lozzalingo-powered website. Follow these 5 phases in order.
Do NOT skip phases. Complete each phase before moving to the next.

**Reference paths:**
- Starter template: `../starter-template/`
- Framework core: `../lozzalingo/`
- Simplest working app: `../../laurencedotcomputer/` (use as primary reference)
- Deployment guide: `./DEPLOY.md`
- Framework CLAUDE.md: `../CLAUDE.md`
- Shared rules: `../../CLAUDE.md`

---

## Phase 1: Discovery

Ask the user these questions before writing any code. Present them conversationally — don't dump all at once. Group related questions together.

### 1.1 Site Identity
- **What's the site called?** (name, e.g. "My Portfolio")
- **Tagline?** (one-liner, e.g. "Projects and writing")
- **What's the purpose?** (portfolio, blog, e-commerce, community, SaaS landing page, etc.)

### 1.2 Domain & Hosting
- **Do you have a domain?** If yes, what is it?
- **Where will this run?**
  - A) Existing DigitalOcean droplet (143.110.152.203) — add alongside existing sites
  - B) New server — we'll provision one
  - C) Local only for now — deploy later

### 1.3 Features
Present this table and recommend based on the site's purpose:

| Module | Description | Recommended for |
|--------|-------------|-----------------|
| `analytics` | Visitor tracking, device detection, referrers | All sites |
| `auth` | Admin login, sessions, OAuth (Google/GitHub) | All sites |
| `dashboard` | Admin home panel, module registry | All sites |
| `news` / `news_public` | Blog/article editor + public display | Blogs, portfolios |
| `email` | Transactional emails via Resend/SES/SMTP | Sites with subscribers |
| `subscribers` | Email subscriber popup + management | Sites wanting a mailing list |
| `customer_spotlight` | Instagram-style photo gallery carousel | E-commerce, community |
| `merchandise` / `merchandise_public` | Product admin + embed API | E-commerce |
| `orders` | Order management | E-commerce |
| `external_api` | API key auth for external integrations | SaaS, integrations |
| `settings` | Site settings admin panel | All sites |
| `projects` / `projects_public` | Project portfolio + public display | Portfolios, dev sites |
| `quick_links` | Linktree-style link page | Personal brands |
| `crosspost` | Cross-post articles to LinkedIn, Medium, Substack, Threads | Blogs with distribution |
| `ops` | Server health monitoring, /health endpoint | All deployed sites |

**Note on module registration:**
- Most modules are auto-registered by `Lozzalingo(app)` via DEFAULT_CONFIG feature flags.
- `subscribers` and `crosspost` are NOT in DEFAULT_CONFIG — they require **manual blueprint registration** in `main.py` (see Phase 2.6 for how laurencedotcomputer does this).

Ask: "Which features do you want enabled? I'd recommend [X, Y, Z] for a [purpose] site."

### 1.4 Branding
- **Primary accent color?** (hex code, e.g. `#d4a855`) — used for buttons, highlights, links
- **Light or dark theme?** (affects bg, text, card colors)
- **Any specific font preference?** (defaults to Inter for body, Space Mono for headings)

### 1.5 API Keys (only ask for enabled features)
- **Resend API key?** (if email enabled — free at resend.com, 3,000 emails/month)
- **Google OAuth credentials?** (if auth with Google — from console.cloud.google.com)
- **GitHub OAuth credentials?** (if auth with GitHub — from github.com/settings/developers)
- **Stripe keys?** (if merchandise/orders enabled)
- Tell the user: "You can add these later in .env or via `/admin/settings/` after launch."

### 1.5b Stripe Setup (if merchandise/orders enabled)
Ask these additional Stripe questions:
- **New or existing Stripe account?** If existing, which one?
- **Need dual accounts?** (e.g., one for subscriptions/donations, one for merchandise — like Crowd Sauced + Aight Clothing)
- **Webhook path preference?** Default: `/stripe/webhook`
- Remind user: "After deploy, register the webhook URL in the Stripe dashboard: `https://<domain>/stripe/webhook`"
- Standard naming convention:
  - Primary: `STRIPE_PUBLISHABLE_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`
  - Secondary: `STRIPE_SECONDARY_PK`, `STRIPE_SECONDARY_SK`, `STRIPE_SECONDARY_WEBHOOK_SECRET`

### 1.6 Custom Pages
- Default pages: Home (`/`), About (`/about`), Blog (`/blog` if news enabled)
- **Any additional pages?** (e.g. `/contact`, `/pricing`, `/portfolio`)

### 1.7 Port Assignment
Check existing ports and assign the next available:

| Port | App |
|------|-----|
| 5000 | starter-template (dev) |
| 5001 | crowd_sauced |
| 5002 | laurencedotcomputer |
| 5010 | Mario Pinto |
| 5020 | product-gap |

Suggest the next free port (e.g. 5003, 5004, etc.).
Ask: "I'll use port [XXXX] — does that work?"

### 1.8 Confirm Before Proceeding
Summarize all choices back to the user:
```
Site: [Name] — "[Tagline]"
Domain: [domain or "local only"]
Port: [XXXX]
Features: [list]
Theme: [light/dark], accent [#hex]
API keys: [provided / will add later]
Custom pages: [list or "defaults only"]
```
Ask: "Ready to scaffold?"

---

## Phase 2: Scaffold

After the user confirms, execute ALL of these steps automatically. Add console logging with prefixes (e.g. `[SITE_NAME]`) to every print statement — this is a mandatory Lozzalingo convention.

### 2.1 Copy Starter Template
```bash
cp -r /path/to/lozzalingo-framework/starter-template /path/to/Lozzalingo-python/<site_slug>
```
Where `<site_slug>` is the lowercased, hyphenated site name (e.g. "My Portfolio" → `my-portfolio`).

### 2.2 Create Framework Symlink
```bash
cd /path/to/Lozzalingo-python/<site_slug>
ln -s ../lozzalingo-framework/lozzalingo lozzalingo
```
This is the standard pattern — the symlink lets the app import `from lozzalingo import Lozzalingo` without pip install.

### 2.3 Create `config.py`
Model on `laurencedotcomputer/config.py`. Minimal version:

```python
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

    # Add per feature:
    # PROJECTS_DB = os.path.join(DB_DIR, 'projects.db')      # if projects enabled
    # QUICK_LINKS_DB = os.path.join(DB_DIR, 'quick_links.db') # if quick_links enabled

    # Stripe (standard naming — if merchandise/orders enabled)
    # STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
    # STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
    # STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')

    # Secondary Stripe (if dual accounts — uncomment if needed)
    # STRIPE_SECONDARY_PK = os.getenv('STRIPE_SECONDARY_PK', '')
    # STRIPE_SECONDARY_SK = os.getenv('STRIPE_SECONDARY_SK', '')
    # STRIPE_SECONDARY_WEBHOOK_SECRET = os.getenv('STRIPE_SECONDARY_WEBHOOK_SECRET', '')

    # Google OAuth (if auth with Google)
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')

    # Email (if email enabled)
    EMAIL_PROVIDER = os.getenv('EMAIL_PROVIDER', 'resend')
    RESEND_API_KEY = os.getenv('RESEND_API_KEY', '')
    EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS', '')
    EMAIL_BRAND_NAME = '<SITE_NAME>'
    EMAIL_BRAND_TAGLINE = '<TAGLINE>'
    EMAIL_WEBSITE_URL = '<SITE_URL>'
    EMAIL_SUPPORT_EMAIL = os.getenv('EMAIL_SUPPORT_EMAIL', '')
    EMAIL_ADMIN_EMAIL = os.getenv('EMAIL_ADMIN_EMAIL', '')

    # CORS (uncomment if API needs cross-origin access)
    # CORS_ORIGINS = os.getenv('CORS_ORIGINS', '').split(',') if os.getenv('CORS_ORIGINS') else []
```

Only include config for enabled features. Remove commented blocks for disabled features.

### 2.4 Customize `lozzalingo.yaml`
```yaml
site:
  name: "<SITE_NAME>"
  tagline: "<TAGLINE>"

features:
  analytics: true/false
  auth: true/false
  dashboard: true/false
  news: true/false
  news_public: true/false
  email: true/false
  customer_spotlight: true/false
  merchandise: true/false
  merchandise_public: true/false
  orders: true/false
  external_api: true/false
  settings: true/false
  projects: true/false
  projects_public: true/false
  quick_links: true/false
  ops: true/false

analytics:
  track_admin: false
```

Set each feature to match the user's choices. Always keep `dashboard: true` (other modules depend on it).

**Note:** `subscribers` and `crosspost` are NOT in the YAML feature flags — they're registered manually in `main.py` (see Phase 2.6). Don't add them to lozzalingo.yaml.

### 2.5 Populate `.env`
Create from `.env.example`, filling in provided values:

```bash
# Generated by site-launcher
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">

# Email
RESEND_API_KEY=<provided or placeholder>
EMAIL_ADDRESS=noreply@<domain>

# OAuth
GOOGLE_CLIENT_ID=<provided or placeholder>
GOOGLE_CLIENT_SECRET=<provided or placeholder>
GITHUB_CLIENT_ID=<provided or placeholder>
GITHUB_CLIENT_SECRET=<provided or placeholder>
```

Generate the SECRET_KEY automatically — never leave it as a placeholder.

### 2.6 Rename `app.py` → `main.py` and Wire Up Config
All existing host apps use `main.py`. Rewrite based on the laurencedotcomputer pattern:

```python
"""
<SITE_NAME>
<underline>

Flask app using the Lozzalingo framework.
"""

import os
from flask import Flask, render_template
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
# ... add all Config attributes for enabled features

# Email config (if email enabled)
app.config['EMAIL_PROVIDER'] = Config.EMAIL_PROVIDER
app.config['RESEND_API_KEY'] = Config.RESEND_API_KEY
app.config['EMAIL_ADDRESS'] = Config.EMAIL_ADDRESS
app.config['EMAIL_BRAND_NAME'] = Config.EMAIL_BRAND_NAME
app.config['EMAIL_BRAND_TAGLINE'] = Config.EMAIL_BRAND_TAGLINE
app.config['EMAIL_WEBSITE_URL'] = Config.EMAIL_WEBSITE_URL
app.config['EMAIL_SUPPORT_EMAIL'] = Config.EMAIL_SUPPORT_EMAIL
app.config['EMAIL_ADMIN_EMAIL'] = Config.EMAIL_ADMIN_EMAIL

# Email templates (customize tone and style)
app.config['EMAIL_WELCOME'] = {
    'greeting': 'Thanks for subscribing',
    'intro': "You'll receive updates when new content is published.",
    'bullets': [
        'New posts and articles',
        'Project updates',
        'Announcements',
    ],
    'closing': 'Thanks for following along.',
    'signoff': '<SITE_NAME>',
}
app.config['EMAIL_STYLE'] = {
    # Light theme defaults:
    'bg': '#f5f5f0',
    'card_bg': '#ffffff',
    'header_bg': '#1a1a2e',
    'header_text': '#ffffff',
    'text': '#333333',
    'text_secondary': '#666666',
    'accent': '<PRIMARY_COLOR>',
    'highlight_bg': '#f0f0e8',
    'highlight_border': '<PRIMARY_COLOR>',
    'border': '#e0e0e0',
    'link': '<PRIMARY_COLOR>',
    'btn_bg': '<PRIMARY_COLOR>',
    'btn_text': '#ffffff',
    'footer_bg': '#1a1a2e',
    'font': "'Inter', 'Helvetica', sans-serif",
    'font_heading': "'Space Mono', 'Courier New', monospace",
}

# Session security
app.config['SESSION_COOKIE_SECURE'] = not app.debug
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# CORS (uncomment if needed for API access)
# from flask_cors import CORS
# CORS(app, origins=Config.CORS_ORIGINS)

# Ensure database directory exists
os.makedirs(Config.DB_DIR, exist_ok=True)

# ===== Lozzalingo Framework =====

from lozzalingo import Lozzalingo
lozzalingo = Lozzalingo(app)

# ===== Manual Blueprint Registration =====
# Modules NOT in DEFAULT_CONFIG need manual registration.

# Subscribers (if enabled):
# from lozzalingo.modules.subscribers import subscribers_bp
# app.register_blueprint(subscribers_bp)
# app.config['SUBSCRIBER_POPUP'] = {
#     'title': 'Stay in the Loop',
#     'subtitle': 'Get notified about new posts and projects.',
#     'show_feeds': False,
#     'scroll_trigger': '',
# }

# Crosspost (if enabled — requires news module):
# from lozzalingo.modules.crosspost import crosspost_bp
# app.register_blueprint(crosspost_bp)
# (Configure CROSSPOST_* keys in config.py for LinkedIn, Medium, Substack, Threads)

# ===== Template Loader =====
# Local templates override framework defaults

_fw_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lozzalingo', 'modules')

template_dirs = [
    FileSystemLoader('templates'),  # Local templates (highest priority)
]

# Add framework module template dirs for all enabled modules
# (only include modules that have templates)
for module_name in ['analytics', 'dashboard', 'news', 'news_public', 'settings',
                     'projects', 'projects_public', 'quick_links', 'subscribers']:
    module_path = os.path.join(_fw_base, module_name, 'templates')
    if os.path.isdir(module_path):
        template_dirs.append(FileSystemLoader(module_path))

app.jinja_loader = ChoiceLoader(template_dirs)


# ===== Routes =====

@app.route('/')
def home():
    """Home page"""
    print("[<SITE_PREFIX>] Home page loaded")
    return render_template('index.html')


@app.route('/about')
def about():
    """About page"""
    print("[<SITE_PREFIX>] About page loaded")
    return render_template('about.html')


# Add blog route if news enabled:
# @app.route('/blog')
# def blog():
#     """Blog listing page"""
#     from lozzalingo.modules.news.routes import get_all_articles_db, init_news_db
#     try:
#         init_news_db()
#         articles = get_all_articles_db(status='published')
#     except Exception as e:
#         print(f"[<SITE_PREFIX>] Error loading articles: {e}")
#         articles = []
#     return render_template('news_public/blog.html', articles=articles)


# ===== Run =====

if __name__ == '__main__':
    print("[<SITE_PREFIX>] Starting on port <PORT>...")
    app.run(debug=True, port=<PORT>, host='0.0.0.0')
```

**Important replacements:**
- `<SITE_NAME>` → user's site name
- `<SITE_PREFIX>` → uppercase short prefix for logging (e.g. "MY_PORTFOLIO")
- `<PORT>` → assigned port number
- `<PRIMARY_COLOR>` → user's accent color
- Uncomment blog route if news is enabled
- Add additional custom page routes as needed
- Only include config lines for enabled features

### 2.7 Update Templates

**`templates/base.html`** — Update:
- Nav brand name
- Nav links (add/remove based on enabled features and custom pages)
- Footer copyright with site name

**`templates/index.html`** — Update:
- Hero heading and subtitle with site name and tagline
- Feature cards to only show enabled features
- Getting started section

**`templates/about.html`** — Update:
- Content to match site purpose

### 2.8 Update CSS Variables
Edit `static/css/style.css` to set the user's branding:

For a **dark theme**:
```css
:root {
    --color-bg: #0a0a0f;
    --color-text: #e8e0d4;
    --color-accent: <PRIMARY_COLOR>;
    --color-card-bg: #151520;
    --color-border: #2a2a3a;
}
```

For a **light theme**:
```css
:root {
    --color-bg: #f5f5f0;
    --color-text: #333333;
    --color-accent: <PRIMARY_COLOR>;
    --color-card-bg: #ffffff;
    --color-border: #e0e0e0;
}
```

### 2.9 Update Docker Files

**`Dockerfile`** — Change:
- Port from 5000 to assigned port
- `app:app` → `main:app` in gunicorn CMD
- Add `mkdir -p databases logs` in RUN

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p databases logs

ENV FLASK_APP=main.py
ENV PYTHONUNBUFFERED=1

EXPOSE <PORT>

CMD ["gunicorn", "--bind", "0.0.0.0:<PORT>", "--workers", "2", "--timeout", "120", "main:app"]
```

**`docker-compose.yml`** — Change:
- Service name to `<site_slug>_web`
- Container name to `<site_slug>_web`
- Port mapping to `<PORT>:<PORT>`
- Network name to `<site_slug>_network`
- Health check port

```yaml
services:
  <site_slug>_web:
    build: .
    container_name: <site_slug>_web
    restart: unless-stopped
    ports:
      - "<PORT>:<PORT>"
    volumes:
      - ./databases:/app/databases
      - ./logs:/app/logs
      - ./static/uploads:/app/static/uploads
      - ./.env:/app/.env:ro
    environment:
      - FLASK_ENV=production
      - PYTHONUNBUFFERED=1
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:<PORT>/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - <site_slug>_network

networks:
  <site_slug>_network:
    driver: bridge
```

### 2.10 Update `run.sh`
Change:
- Banner to show site name
- Port references to assigned port
- `python app.py` → `python main.py`

```bash
#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}"
echo "=========================================="
echo "  <SITE_NAME>"
echo "=========================================="
echo -e "${NC}"

if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating .env file from template...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}Note: Edit .env with your configuration${NC}"
fi

mkdir -p databases

echo ""
echo -e "${GREEN}=========================================="
echo "  Starting server..."
echo "==========================================${NC}"
echo ""
echo "  Homepage:      http://localhost:<PORT>"
echo "  Admin Panel:   http://localhost:<PORT>/admin"
echo "  Create Admin:  http://localhost:<PORT>/admin/create-admin"
echo ""
echo -e "${YELLOW}  First time? Visit /admin/create-admin to set up your admin account${NC}"
echo ""

python main.py
```

### 2.11 Create Site-Level `CLAUDE.md`
Model on `laurencedotcomputer/CLAUDE.md`:

```markdown
# <SITE_NAME> - Claude Guidelines
Shared framework rules are auto-loaded from the parent `Lozzalingo-python/CLAUDE.md`.

## Architecture
- Flask site using the Lozzalingo framework
- Framework via symlink: `lozzalingo -> ../lozzalingo-framework/lozzalingo`
- Port <PORT> locally, behind nginx on server

## Key Rules
- Always add console logging with prefixes (e.g. `[<SITE_PREFIX>]`) when creating features
- Use CSS custom properties from style.css for all colors/fonts

## Key Files
- Entry point: `main.py` (blueprint registration, ChoiceLoader, routes)
- Config: `config.py` (DB paths, API keys, env vars)
- Feature flags: `lozzalingo.yaml`
- Templates: `templates/` (override framework defaults)
- CSS: `static/css/style.css`

## Databases (SQLite, in `databases/`)
- `users.db` - admin accounts, auth
- `news.db` - blog articles (if news enabled)
- `analytics_log.db` - page views, events (table: `analytics_log`)

## After Making Changes
- Test locally: `python main.py` (port <PORT>)
- Create admin locally: `localhost:<PORT>/admin/create-admin`
```

### 2.12 Delete `app.py` (if it exists)
The starter template no longer ships `app.py`, but remove it if present:
```bash
rm -f <site_slug>/app.py
```

### 2.13 Generate Nginx Config
Create `scripts/<site_slug>.nginx.conf` using the template from `starter-template/scripts/SITE_SLUG.nginx.conf`.

Replace all `<PLACEHOLDER>` values:
- `<DOMAIN>` → the site's domain
- `<PORT>` → the assigned port
- `<SITE_SLUG>` → the site slug
- `<SITE_NAME>` → the site name

The config includes:
- HTTP→HTTPS redirect
- SSL cert paths (Let's Encrypt)
- Proxy to localhost:PORT
- Static file serving with cache headers
- Block `.db` files and dotfiles
- Stripe webhook header passthrough

### 2.14 Generate Deploy Script
Create `scripts/deploy.sh` using the template from `starter-template/scripts/deploy.sh`.

Replace all `<PLACEHOLDER>` values:
- `<SERVER_IP>` → server IP (default: 143.110.152.203)
- `<SITE_SLUG>` → the site slug
- `<SITE_NAME>` → the site name
- `<DOMAIN>` → the site's domain

The script handles:
- SSH key check
- rsync with proper exclusions
- Framework clone/update on server
- Symlink creation
- Docker build + start
- Health check verification

### 2.15 Generate Test File
Create `tests/test_critical.py` from the template in `starter-template/tests/test_critical.py`.

The tests verify:
- App starts without errors
- `/health` returns 200
- Homepage returns 200

### 2.16 Post-Launch Reminder
After scaffolding, remind the user:
```
Post-launch setup:
1. Visit /admin/settings/ to configure API keys via the UI
2. Check the Setup Status banner for missing configuration
3. Register Stripe webhook URL in your Stripe dashboard
4. Configure email settings and test the connection
```

---

## Phase 3: Local Verification

Run the site locally and verify everything works.

### 3.1 Start the Server
```bash
cd /path/to/Lozzalingo-python/<site_slug>
bash run.sh
# Or directly: python main.py
```

### 3.2 Verify Core Routes
Check these URLs in order:
1. `http://localhost:<PORT>/` — Homepage loads with correct name/tagline
2. `http://localhost:<PORT>/health` — Returns JSON `{"status": "healthy", ...}`
3. `http://localhost:<PORT>/admin/login` — Login page renders

### 3.3 Create First Admin
Guide the user:
1. Visit `http://localhost:<PORT>/admin/create-admin`
2. Create an admin account (username + password)
3. Log in at `/admin/login`
4. Verify the dashboard loads at `/admin/dashboard`

### 3.4 Verify Enabled Features
For each enabled feature, check its admin route:
- analytics: `/admin/analytics`
- news: `/admin/news`
- email: `/admin/email-preview/`
- customer_spotlight: `/admin/customer-spotlight-editor`
- merchandise: `/admin/merchandise`
- orders: `/admin/orders`
- settings: `/admin/settings`
- projects: `/admin/projects`
- quick_links: `/admin/quick-links`
- ops: `/admin/ops`

### 3.5 Ask User
"Everything looks good locally. Ready to deploy to a server, or do you want to keep working locally first?"

---

## Phase 4: Server Deployment

Only proceed if the user wants to deploy. Reference `./DEPLOY.md` for detailed steps.

### Option A: Existing DigitalOcean Droplet (143.110.152.203)

**Prerequisites:**
- SSH key added: `ssh-add ~/.ssh/id_ed25519_droplet`
- Test connection: `ssh -i ~/.ssh/id_ed25519_droplet root@143.110.152.203`

**Steps:**

1. **Deploy using generated script** (created in Phase 2.14):
   ```bash
   bash scripts/deploy.sh
   ```
   This handles: directory creation, rsync, framework clone/update, symlink, Docker build.

2. **Create production `.env` on server** (if first deploy):
   ```bash
   ssh root@143.110.152.203 "cat > /var/www/<site_slug>/.env << 'EOF'
   FLASK_ENV=production
   ENVIRONMENT=production
   FLASK_SECRET_KEY=<generated-secret>
   RESEND_API_KEY=<key>
   EMAIL_ADDRESS=noreply@<domain>
   EOF"
   ```

3. **Install Nginx config** (using generated config from Phase 2.13):
   ```bash
   scp -i ~/.ssh/id_ed25519_droplet scripts/<site_slug>.nginx.conf root@143.110.152.203:/etc/nginx/sites-available/<site_slug>
   ssh root@143.110.152.203 "ln -sf /etc/nginx/sites-available/<site_slug> /etc/nginx/sites-enabled/ && nginx -t && systemctl reload nginx"
   ```

4. **Set up SSL:**
   ```bash
   ssh root@143.110.152.203 "certbot --nginx -d <domain> --non-interactive --agree-tos -m <email>"
   ```

5. **Configure DNS:**
   - For `*.laurence.computer` subdomains: A record already points to 143.110.152.203 (wildcard)
   - For external domains: Add A record pointing to 143.110.152.203

6. **Verify deployment:**
   ```bash
   curl -s https://<domain>/health | python3 -m json.tool
   ```

7. **Post-deploy setup:**
   - Visit `https://<domain>/admin/create-admin` to create the first admin
   - Visit `https://<domain>/admin/settings/` to configure API keys via the UI
   - Register webhook URL in Stripe dashboard: `https://<domain>/stripe/webhook`

### Option B: New Server
See `./DEPLOY.md` sections 2-4 for server provisioning, hardening, and Docker installation. Then follow Option A steps 1-10.

### Option C: Local Only
Skip this phase entirely. The user can return to deploy later.

---

## Phase 5: Summary

Print a launch card summarizing everything:

```
============================================================
  <SITE_NAME> — Launch Complete
============================================================

  Local:  http://localhost:<PORT>
  Live:   https://<domain> (if deployed)
  Admin:  /admin/login
  Health: /health

  Enabled Features:
    - [list of enabled features]

  Key Files:
    - main.py        Entry point
    - config.py      Configuration
    - lozzalingo.yaml Feature flags
    - .env           Secrets (gitignored)

  Quick Commands:
    Local:  cd <path> && python main.py
    Docker: cd <path> && docker compose up -d --build
    Deploy: ssh root@143.110.152.203 "cd /var/www/<site_slug> && git pull && docker compose up -d --build"

============================================================
```

---

## Mandatory Framework Rules (Always Follow)

These rules apply to ALL code you write for Lozzalingo apps. They are copied here to ensure you always have them, even if the parent `CLAUDE.md` isn't loaded.

### Analytics Button Labeling
- Every `<button>` MUST have a `name="descriptive_snake_case"` attribute
- Every important `<a>` link MUST have a `name` attribute
- The analytics JS auto-captures clicks as `button_click_${name}` / `link_click_${name}`
- Falls back to `id` then `'unnamed'` — but `unnamed` is useless in analytics, so always set `name`

### Persistent Logging
- All 5xx responses are auto-logged to `app_logs` DB table via `_setup_error_logging()`
- For explicit logging: `from lozzalingo.core import db_log`
- Call pattern: `db_log('error', 'module_name', 'What happened', {'key': 'value'})`
- Levels: `debug`, `info`, `warning`, `error`, `critical`
- NEVER use only `logging.getLogger()` — stdout logs are lost on container rebuild
- All `except` blocks MUST include a `db_log('error', ...)` call

### Console Logging with Prefixes
- Every `print()` statement MUST have a prefix: `print("[SITE_PREFIX] message")`
- Use uppercase site abbreviation (e.g. `[MY_PORTFOLIO]`, `[CROWD_SAUCED]`)
- This applies to route handlers, error handlers, startup messages, and debug output

### Config Pattern (3-Tier Resolution)
All modules use this priority order:
1. `current_app.config.get('KEY')` — Flask app config (highest priority)
2. `Config.KEY` with `hasattr()` guard — framework default
3. `os.getenv('KEY', 'fallback')` — env var fallback

### Admin Creation Security
- "Create one here" link ONLY shown on localhost/127.0.0.1
- Production: admins created by logged-in admins only
- `/admin/create-admin` allows unauthenticated access when zero admins exist (bootstrap)

### Email Service
- Provider: `EMAIL_PROVIDER` env var ('resend', 'ses', or 'smtp')
- Required: `EMAIL_ADDRESS`, `EMAIL_BRAND_NAME`, `EMAIL_WEBSITE_URL`, `EMAIL_ADMIN_EMAIL`
- Customize per-host via `EMAIL_WELCOME` dict (greeting, intro, bullets, closing, signoff)
- Customize via `EMAIL_STYLE` dict (16 color/font keys)
- All templates inline-styled — no `<style>` blocks (email client compatibility)

### Stripe Key Naming Convention
- **Primary account:** `STRIPE_PUBLISHABLE_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`
- **Secondary account:** `STRIPE_SECONDARY_PK`, `STRIPE_SECONDARY_SK`, `STRIPE_SECONDARY_WEBHOOK_SECRET`
- NEVER use the old `STRIPE_PUBLIC_KEY_PK` / `STRIPE_PUBLIC_KEY_SK` naming
- Dual accounts: Crowd Sauced uses primary for credits/donations and Aight (secondary) for merchandise
- The `stripe_secondary` category in `/admin/settings/` supports configuring a second account via the UI

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'lozzalingo'"
The symlink is missing or broken. Fix:
```bash
cd <site_slug>
ls -la lozzalingo  # Should point to ../lozzalingo-framework/lozzalingo
ln -sf ../lozzalingo-framework/lozzalingo lozzalingo
```

### "ImportError: cannot import name 'Lozzalingo'"
Framework symlink exists but points to wrong directory. Check that `../lozzalingo-framework/lozzalingo/__init__.py` exists.

### "TemplateNotFound"
ChoiceLoader isn't configured, or the template path is wrong. Ensure `main.py` has the ChoiceLoader setup with both local and framework template directories.

### Port Already in Use
Check what's using the port:
```bash
lsof -i :<PORT>
```
Choose a different port and update `main.py`, `Dockerfile`, `docker-compose.yml`, and `run.sh`.

### Database Errors
Ensure the `databases/` directory exists:
```bash
mkdir -p databases
```
Databases auto-create on first request. If a DB is corrupted, delete it and restart.

### Docker Build Fails
Common causes:
- Missing `requirements.txt` dependency
- Incorrect `COPY` path in Dockerfile
- Port mismatch between `EXPOSE` and gunicorn `--bind`

### 502 Bad Gateway (After Deploy)
- Check container is running: `docker ps`
- Check container logs: `docker logs <container_name>`
- Verify Nginx proxy_pass port matches Docker port
- Check firewall: `ufw status` — port should NOT be open (Nginx proxies internally)
