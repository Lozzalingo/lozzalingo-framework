# Lozzalingo Framework - TODO

> **How to use this file:** Work through tasks in order. Each task has a checkbox. Mark complete with `[x]` when done. An AI assistant can read this file and PROJECT.md to understand the current state and continue work.

## Phase 1: Core Framework Simplification

### 1.1 Create Main Entry Point
- [x] Create `lozzalingo/__init__.py` with `Lozzalingo` class
- [x] Implement `Lozzalingo(app, config=None)` constructor
- [x] Add automatic blueprint registration based on config
- [x] Add YAML config file loading (`lozzalingo.yaml`)
- [x] Implement sensible defaults for all settings
- [x] Add PyYAML to setup.py dependencies

### 1.1b Remove Hardcoded "Mario Pinto" References
- [ ] Replace hardcoded titles in templates with `{{ config.brand_name }}`
- [ ] Update dashboard footer to use config
- [ ] Update CSS comments to be generic
- [ ] Update docstrings to be generic
- [ ] Make all branding configurable via `lozzalingo.yaml`

### 1.2 Auto-Injection System
- [x] Implement `after_request` hook to inject analytics scripts (in Lozzalingo class)
- [x] Auto-detect HTML responses (check Content-Type)
- [x] Inject scripts before `</body>` tag
- [x] Make injection configurable (skip admin pages by default)

### 1.3 Dynamic Origin Handling for Analytics
- [x] Remove hardcoded `allowed_origins` list from `analytics/routes.py`
- [x] Implement dynamic origin validation (accept request origin or use config)
- [x] Add `ANALYTICS_ALLOWED_ORIGINS` config option for explicit control
- [x] Default to allowing the request's origin (for development ease)
- [x] Created `get_allowed_origins()` and `is_valid_analytics_origin()` helpers

### 1.4 Auto-Initialize Databases
- [ ] Update `core/database.py` to auto-create tables on first use
- [ ] Remove need for manual `create_tables()` calls
- [ ] Ensure databases directory is created automatically
- [ ] Add migration support for schema changes (future)

---

## Phase 2: Starter Template (Complete Out-of-Box Project)

> **Goal:** Duplicate folder → Run one command → Full site with frontend + admin backend (like Django)

### 2.1 Create Template Structure
- [x] Create `starter-template/` directory
- [x] Create `starter-template/app.py` with Flask app + Lozzalingo init
- [x] Create `starter-template/requirements.txt` (flask, lozzalingo deps)
- [x] Create `starter-template/lozzalingo.yaml` with all modules enabled
- [x] Create `starter-template/.env.example` with required variables
- [x] Create `starter-template/run.sh` (one-command startup script)

### 2.2 Docker Support
- [x] Create `starter-template/Dockerfile`
- [x] Create `starter-template/docker-compose.yml`
- [x] Create `starter-template/.dockerignore`
- [x] Document both run methods (Flask dev server OR Docker)

### 2.3 Frontend Templates
- [x] Create `starter-template/templates/base.html` (proper HTML5 structure)
- [x] Create `starter-template/templates/index.html` (Hello World homepage)
- [x] Create `starter-template/templates/about.html` (example additional page)
- [x] Include navigation between pages
- [x] Include footer with year
- [x] Add minimal but professional CSS

### 2.4 Static Assets
- [x] Create `starter-template/static/css/style.css` (clean default styling)
- [x] Add robots.txt
- [ ] Add favicon.ico placeholder

### 2.5 Database Setup
- [x] Create `starter-template/databases/` directory with .gitkeep
- [x] Ensure all DBs auto-create on first run (via Lozzalingo class)
- [x] First-run setup via `/admin/create-admin`

### 2.6 Verify ALL Modules Work Out-of-Box
- [x] **Homepage:** Hello World displays at `/` (200)
- [x] **About:** `/about` works (200)
- [x] **Admin Login:** `/admin/login` works (200)
- [x] **Admin Dashboard:** `/admin/dashboard` redirects to login (302)
- [x] **Create Admin:** `/admin/create-admin` works (200)
- [x] **Analytics:** `/admin/analytics/` redirects to login (302)
- [x] **News Public:** `/news/` works (200)
- [x] **User Login:** `/login` works (200)
- [x] **User Register:** `/register` works (200)
- [x] **Sign In:** `/sign-in` works (200)
- [x] All 10 route tests passing

### 2.7 Starter Template README
- [x] Create `starter-template/README.md` with:
  - One-command quick start
  - Default admin credentials (or first-run instructions)
  - List of all available routes
  - How to customize
  - How to deploy

---

## Phase 3: Module Documentation

### 3.1 Documentation Structure
- [x] Create `docs/` directory
- [x] Create `docs/README.md` (documentation index)

### 3.2 Analytics Module Documentation
- [ ] Create `docs/analytics.md`
- [ ] Document what it tracks (page views, events, devices, referrers)
- [ ] Document admin dashboard features
- [ ] Document JavaScript API for custom events
- [ ] Document configuration options
- [ ] Add screenshots of dashboard

### 3.3 Dashboard Module Documentation
- [ ] Create `docs/dashboard.md`
- [ ] Document admin authentication flow
- [ ] Document first-time setup (`/admin/create-admin`)
- [ ] Document session variables set
- [ ] Document how to add custom dashboard cards
- [ ] Document styling/theming

### 3.4 Auth Module Documentation
- [ ] Create `docs/auth.md`
- [ ] Document user authentication flow
- [ ] Document OAuth setup (Google, GitHub)
- [ ] Document email verification flow
- [ ] Document password reset flow
- [ ] Document session variables
- [ ] Document template customization

### 3.5 Email Module Documentation
- [ ] Create `docs/email.md`
- [ ] Document Resend API setup
- [ ] Document available email templates
- [ ] Document configuration options
- [ ] Document how to send emails programmatically
- [ ] Document email preview feature
- [ ] Document branding customization

### 3.6 Customer Spotlight Module Documentation
- [ ] Create `docs/customer-spotlight.md`
- [ ] Document required HTML (`<div id="customer-spotlight">`)
- [ ] Document admin interface
- [ ] Document API endpoint
- [ ] Document styling customization
- [ ] Document JavaScript configuration

### 3.7 News Module Documentation
- [ ] Create `docs/news.md`
- [ ] Document admin interface for creating articles
- [ ] Document public routes (`/news/`, `/news/<slug>`)
- [ ] Document template override pattern
- [ ] Document content formatting (markdown-style)
- [ ] Document API endpoints

### 3.8 Other Modules
- [ ] Create `docs/merchandise.md`
- [ ] Create `docs/orders.md`
- [ ] Create `docs/external-api.md`

---

## Phase 4: Update Main README

### 4.1 Rewrite README.md
- [ ] Add clear "Quick Start" section (5 steps max)
- [ ] Add "What's Included" section listing all modules
- [ ] Add "Configuration" section with examples
- [ ] Add "Starter Template" section
- [ ] Remove/archive old detailed integration instructions
- [ ] Add links to module documentation

---

## Phase 5: Testing & Validation

### 5.1 Manual Testing
- [ ] Test starter template fresh clone and run
- [ ] Test all admin routes work
- [ ] Test analytics tracks page views
- [ ] Test admin login/logout
- [ ] Test on different browsers

### 5.2 Create Test Site
- [ ] Create a simple test site using the framework
- [ ] Verify all features work end-to-end
- [ ] Document any issues found
- [ ] Fix issues

---

## Phase 6: Migration (Proof it Works)

### 6.1 Migrate crowd_sauced
- [ ] Create branch for migration
- [ ] Replace local analytics module with lozzalingo
- [ ] Replace local signin module with lozzalingo auth
- [ ] Replace local dashboard module with lozzalingo dashboard
- [ ] Test all functionality works identically
- [ ] Document migration steps taken
- [ ] Measure code reduction (lines removed vs added)

### 6.2 Document Migration Guide
- [ ] Create `docs/migration.md`
- [ ] Document common migration patterns
- [ ] Document gotchas and solutions

---

## Current Focus

**Phase 1 & 2 COMPLETE** - Framework and Starter Template ready!

**Completed:**
- Lozzalingo class with auto-registration of all 10 modules
- YAML config loading
- Auto-injection of analytics scripts
- Dynamic origin handling for analytics
- Complete starter template with all files

**Next:** Test the starter template to verify all modules work out-of-box (Phase 2.6)

---

## Notes

- Each task should be completable in one session
- Test after completing each section
- Update this file as you complete tasks
- Add new tasks if discovered during implementation

---

## Completed Tasks

- [x] Create PROJECT.md (2024-12-29)
- [x] Create TODO.md (2024-12-29)
- [x] Create docs/ directory structure (2024-12-29)
- [x] Create docs/README.md documentation index (2024-12-29)
- [x] Create starter-template/ directory (2024-12-29)
- [x] **Phase 1.1: Create Main Entry Point** (2024-12-29)
  - Created `Lozzalingo` class in `lozzalingo/__init__.py`
  - Implemented constructor with config merging
  - Added automatic blueprint registration for all 10 modules
  - Added YAML config file loading
  - Implemented sensible defaults
  - Added PyYAML to setup.py
- [x] **Phase 1.2: Auto-Injection System** (2024-12-29)
  - Implemented `after_request` hook for analytics script injection
  - Auto-detects HTML responses
  - Injects before `</body>` tag
  - Configurable (skips admin pages by default)
- [x] **Phase 1.3: Dynamic Origin Handling** (2024-12-29)
  - Removed hardcoded allowed_origins from analytics/routes.py
  - Created `get_allowed_origins()` and `is_valid_analytics_origin()` helpers
  - Origins now dynamically allowed based on request
  - Added `ANALYTICS_ALLOWED_ORIGINS` config option
- [x] **Phase 2: Starter Template** (2024-12-29)
  - Created `starter-template/app.py` - minimal Flask app with Lozzalingo
  - Created `templates/base.html`, `index.html`, `about.html`
  - Created `static/css/style.css` with professional styling
  - Created `lozzalingo.yaml`, `requirements.txt`, `.env.example`
  - Created `run.sh` one-command startup script
  - Created `Dockerfile` and `docker-compose.yml`
  - Created comprehensive `README.md`
  - Fixed import issues in auth module (email.py, utils.py, database.py)
  - Added `file_version()` and `current_year()` template globals
  - **All 10 route tests passing**
