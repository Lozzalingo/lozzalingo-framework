# Lozzalingo

A modular, reusable Flask admin dashboard framework.

## Features

### Admin Modules
- **Analytics Module**: Track visitor behavior, device types, referrers, and more
- **Authentication Module**: User login, session management, password changes
- **Dashboard Module**: Unified admin interface
- **News Module** (Admin): Create, edit, and manage news articles and blog posts
- **Orders Module**: Manage customer orders and email confirmations
- **Merchandise Module**: Product management for online stores

### Public Frontend Modules
- **News Public Module**: Public-facing blog/news display with template override support
  - Framework provides: Backend routes, database queries, content formatting
  - Projects provide: Custom styled templates matching site design

More modules coming soon!

## Installation

Install in editable mode for development:

```bash
pip install -e /path/to/lozzalingo-framework
```

Or install from source:

```bash
cd /path/to/lozzalingo-framework
pip install .
```

## Quick Start

### 1. Import and Register Blueprints

```python
from flask import Flask
from lozzalingo.modules.analytics import analytics_bp
from lozzalingo.modules.auth import auth_bp

app = Flask(__name__)

# Register blueprints
app.register_blueprint(analytics_bp, url_prefix='/admin/analytics')
app.register_blueprint(auth_bp, url_prefix='/admin')
```

### 2. Configure Your App

```python
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['USER_DB'] = 'path/to/your/database.db'
```

### 3. Run Your App

```python
if __name__ == '__main__':
    app.run(debug=True)
```

## Module Details

### Analytics Module

Provides comprehensive analytics tracking:
- Page views and unique visitors
- Device detection (desktop, mobile, tablet)
- Geographic location tracking
- Referrer tracking
- Custom event tracking

**Usage:**
```python
from lozzalingo.modules.analytics import analytics_bp, Analytics

app.register_blueprint(analytics_bp, url_prefix='/admin/analytics')

# Track events in your routes
Analytics.track_event(request, 'page_view', metadata={'page': 'home'})
```

### Auth Module

Provides admin authentication:
- Login/logout
- Session management
- Password change functionality
- Admin creation

**Usage:**
```python
from lozzalingo.modules.auth import auth_bp

app.register_blueprint(auth_bp, url_prefix='/admin')
```

Access:
- Login: `/admin/login`
- Dashboard: `/admin/dashboard`
- Change Password: `/admin/change-password`

### News Module (Admin)

Admin interface for managing news articles and blog posts:
- Create, edit, and delete articles
- Draft/published workflow
- Image upload support
- Slug generation
- Email tracking

**Usage:**
```python
from lozzalingo.modules.news import news_bp

app.register_blueprint(news_bp)  # Registers at /admin/news-editor
```

Access:
- News Editor: `/admin/news-editor`

### News Public Module

Public-facing blog/news display with template override support:
- Blog listing pages (`/news/blog`)
- Individual blog posts (`/news/<slug>`)
- Markdown-style content formatting
- Related articles
- Social sharing buttons

**Usage:**
```python
from lozzalingo.modules.news_public import news_public_bp

app.register_blueprint(news_public_bp)  # Registers at /news
```

**Template Override Pattern:**

The framework provides minimal base templates. Projects override them with custom styling:

```
your_project/
└── templates/
    └── news_public/
        ├── blog.html          # Override blog listing
        ├── blog_post.html     # Override individual post
        └── news.html          # Override news listing
```

Access:
- Blog listing: `/news/blog`
- News listing: `/news/`
- Individual posts: `/news/<slug>`
- API: `/news/api/articles`

## Development

### Project Structure

```
lozzalingo/
├── lozzalingo/
│   ├── __init__.py
│   ├── core/              # Shared utilities
│   └── modules/
│       ├── analytics/     # Analytics module
│       │   ├── templates/
│       │   ├── static/
│       │   └── *.py
│       ├── auth/          # Authentication module
│       │   ├── templates/
│       │   └── *.py
│       └── dashboard/     # Dashboard module
├── setup.py
└── README.md
```

### Contributing

This is currently an extraction from the Mario Pinto project. More modules will be added over time.

## License

MIT License

## Author

Laurence Stephan
