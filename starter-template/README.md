# Lozzalingo Starter Template

A ready-to-run Flask application with all Lozzalingo modules enabled out of the box.

## Quick Start

### Option 1: Run with Python

```bash
# Make run script executable (first time only)
chmod +x run.sh

# Run the app
./run.sh
```

Or manually:

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install lozzalingo framework (from parent directory)
pip install -e ..

# Run the app
python app.py
```

### Option 2: Run with Docker

```bash
docker-compose up
```

## First Time Setup

1. Visit http://localhost:5000/admin/create-admin
2. Create your admin account
3. Login at http://localhost:5000/admin/login
4. Explore the admin dashboard

## Available Routes

### Frontend

| Route | Description |
|-------|-------------|
| `/` | Homepage |
| `/about` | About page |
| `/news/` | News/blog listing |
| `/login` | User login |
| `/register` | User registration |

### Admin Backend

| Route | Description |
|-------|-------------|
| `/admin/login` | Admin login |
| `/admin/dashboard` | Main dashboard |
| `/admin/analytics` | Analytics dashboard |
| `/admin/news-editor` | News/blog editor |
| `/admin/customer-spotlight-editor` | Customer gallery manager |
| `/admin/email-preview/` | Email template preview |
| `/admin/api-keys` | API key management |
| `/admin/create-admin` | Create admin account (first-time setup) |

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Key variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Flask secret key | Yes (for production) |
| `RESEND_API_KEY` | Resend API key for emails | No |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | No |
| `GOOGLE_CLIENT_SECRET` | Google OAuth secret | No |

### lozzalingo.yaml

Customize your site in `lozzalingo.yaml`:

```yaml
site:
  name: "My Site"
  tagline: "Welcome to my site"

features:
  analytics: true
  auth: true
  news: true
  email: false  # Disable modules you don't need
```

## Customization

### Templates

Edit files in `templates/`:
- `base.html` - Base template with nav and footer
- `index.html` - Homepage
- `about.html` - About page

### Styling

Edit `static/css/style.css` to customize the look.

CSS variables are defined at the top:

```css
:root {
    --color-primary: #2563eb;
    --color-text: #1e293b;
    /* ... */
}
```

### Adding Pages

1. Add a route in `app.py`:

```python
@app.route('/contact')
def contact():
    return render_template('contact.html')
```

2. Create `templates/contact.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>Contact Us</h1>
{% endblock %}
```

## Project Structure

```
starter-template/
├── app.py                  # Main Flask application
├── lozzalingo.yaml         # Framework configuration
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variables template
├── run.sh                  # One-command startup script
├── templates/
│   ├── base.html           # Base template
│   ├── index.html          # Homepage
│   └── about.html          # About page
├── static/
│   ├── css/style.css       # Main stylesheet
│   ├── favicon.ico         # Site favicon
│   └── robots.txt          # Search engine config
├── databases/              # SQLite databases (auto-created)
├── Dockerfile              # Docker build file
└── docker-compose.yml      # Docker Compose config
```

## Deployment

### With Docker

```bash
docker-compose up -d
```

### With Gunicorn

```bash
pip install gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 2 app:app
```

### Environment

For production, ensure:

1. `SECRET_KEY` is set to a secure random value
2. `FLASK_ENV=production`
3. Use a proper database (PostgreSQL) for high traffic

## Troubleshooting

### "No module named 'lozzalingo'"

Install the framework:

```bash
pip install -e /path/to/lozzalingo-framework
```

### Admin login not working

1. First, create an admin at `/admin/create-admin`
2. Make sure the `databases/` directory exists and is writable

### Analytics not tracking

Analytics scripts are auto-injected. Check:
1. Your page has a `</body>` tag
2. You're not on an `/admin/` page (admin pages are excluded by default)

## License

MIT License
