# Lozzalingo Framework Documentation

This directory contains detailed documentation for each module in the Lozzalingo framework.

## Quick Start

See the main [README.md](../README.md) for installation and basic setup.

## Module Documentation

| Module | Description | Status |
|--------|-------------|--------|
| [Analytics](./analytics.md) | Page view tracking, events, device detection | Pending |
| [Dashboard](./dashboard.md) | Admin authentication and dashboard | Pending |
| [Auth](./auth.md) | User authentication (email, OAuth) | Pending |
| [Email](./email.md) | Email service with Resend API | Pending |
| [Customer Spotlight](./customer-spotlight.md) | Customer photo gallery | Pending |
| [News](./news.md) | Blog/news management | Pending |
| [Merchandise](./merchandise.md) | Product management | Pending |
| [Orders](./orders.md) | Order management | Pending |
| [External API](./external-api.md) | API key authentication | Pending |

## Configuration Reference

### Minimal Setup

```python
from flask import Flask
from lozzalingo import Lozzalingo

app = Flask(__name__)
lozzalingo = Lozzalingo(app)
```

### Configuration File (lozzalingo.yaml)

```yaml
site:
  name: "My Site"
  domain: "example.com"

features:
  analytics: true
  auth: true
  news: true
  email: true
  customer_spotlight: true
  merchandise: false
  orders: false

admin:
  email: "admin@example.com"

email:
  resend_api_key: "${RESEND_API_KEY}"
  from_address: "noreply@example.com"
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Flask secret key | Yes |
| `RESEND_API_KEY` | Resend API key for emails | Only if using email |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | Only if using Google OAuth |
| `GOOGLE_CLIENT_SECRET` | Google OAuth secret | Only if using Google OAuth |
| `DATABASE_URL` | PostgreSQL URL (optional) | No (defaults to SQLite) |

## HTML Requirements

For modules to work correctly, your templates should include:

### Analytics (automatic)
No requirements - scripts are auto-injected.

### Customer Spotlight
```html
<div id="customer-spotlight"></div>
```

### News Section
```html
<section id="news">
  <!-- News articles will be loaded here -->
</section>
```

## Extending the Framework

Each module documentation includes:
- Configuration options
- Template customization
- JavaScript APIs
- Database schema
- Extension points
