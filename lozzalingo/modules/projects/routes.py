"""
Projects Admin Routes
=====================

Project portfolio management forked from the news module.
- `status`: draft/published (controls public visibility)
- `project_status`: active/inactive (label shown on public page)
"""

from flask import render_template, request, redirect, url_for, session, jsonify
from . import projects_bp
import os
import uuid
from datetime import datetime
import re
import requests
from urllib.parse import urljoin, urlparse

# ===== Database Helper Functions =====

def get_db_config():
    """Get database configuration"""
    try:
        from flask import current_app
        val = current_app.config.get('PROJECTS_DB')
        if val:
            return val
    except RuntimeError:
        pass
    try:
        from config import Config
        return Config.PROJECTS_DB if hasattr(Config, 'PROJECTS_DB') else 'projects.db'
    except ImportError:
        return os.getenv('PROJECTS_DB', 'projects.db')

def get_db_connection():
    """Get database connection function"""
    try:
        from database import Database
        return Database.connect
    except ImportError:
        import sqlite3
        return sqlite3.connect

def init_projects_db():
    """Initialize projects database with migrations"""
    projects_db = get_db_config()
    db_connect = get_db_connection()

    try:
        db_dir = os.path.dirname(projects_db)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        with db_connect(projects_db) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    slug TEXT NOT NULL UNIQUE,
                    content TEXT NOT NULL,
                    image_url TEXT,
                    year INTEGER,
                    status TEXT DEFAULT 'draft',
                    project_status TEXT DEFAULT 'active',
                    excerpt TEXT,
                    meta_description TEXT,
                    technologies TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Migration: add missing columns
            cursor.execute("PRAGMA table_info(projects)")
            columns = [column[1] for column in cursor.fetchall()]

            new_columns = [
                ('year', 'INTEGER'),
                ('status', 'TEXT DEFAULT "draft"'),
                ('project_status', 'TEXT DEFAULT "active"'),
                ('excerpt', 'TEXT'),
                ('meta_description', 'TEXT'),
                ('technologies', 'TEXT'),
                ('year_end', 'INTEGER'),
                ('gross_earnings', 'REAL'),
                ('earnings_currency', 'TEXT DEFAULT "£"'),
                ('gallery_images', 'TEXT'),
                ('gallery_layout', 'TEXT DEFAULT "single"'),
                ('content_image_layout', 'TEXT DEFAULT "carousel"'),
                ('hero_image_align', 'TEXT DEFAULT "center center"'),
                ('email_sent', 'BOOLEAN DEFAULT 0'),
                ('earnings_label', 'TEXT'),
                ('insights', 'TEXT'),
                ('crossposted_linkedin', 'BOOLEAN DEFAULT 0'),
                ('crossposted_medium', 'BOOLEAN DEFAULT 0'),
                ('crossposted_substack', 'BOOLEAN DEFAULT 0'),
                ('crossposted_twitter', 'BOOLEAN DEFAULT 0'),
                ('crossposted_threads', 'BOOLEAN DEFAULT 0'),
                ('upvote_count', 'INTEGER DEFAULT 0'),
                ('external_url', 'TEXT'),
                ('fetched_content', 'TEXT'),
            ]
            for col_name, col_type in new_columns:
                if col_name not in columns:
                    print(f"Adding {col_name} column to projects table...")
                    try:
                        cursor.execute(f'ALTER TABLE projects ADD COLUMN {col_name} {col_type}')
                    except Exception as e:
                        print(f"Could not add column {col_name}: {e}")

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_projects_slug ON projects(slug)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_projects_project_status ON projects(project_status)')

            conn.commit()
            print("Projects database initialized successfully")

            # Tech registry table
            _init_tech_registry(conn)

            # Upvotes table
            _init_project_upvotes(conn)

    except Exception as e:
        print(f"Error initializing projects database: {e}")
        raise


def _init_tech_registry(conn):
    """Create tech_registry table if it doesn't exist."""
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tech_registry (
                name TEXT PRIMARY KEY,
                category TEXT NOT NULL
            )
        ''')
        conn.commit()
    except Exception as e:
        print(f"Error initializing tech_registry table: {e}")


def _init_project_upvotes(conn):
    """Create project_upvotes table if it doesn't exist."""
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_upvotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                fingerprint_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project_id, fingerprint_hash)
            )
        ''')
        conn.commit()
    except Exception as e:
        print(f"Error initializing project_upvotes table: {e}")


def get_all_tech_categories():
    """Return {name: category} dict from the tech_registry table."""
    projects_db = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(projects_db) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name, category FROM tech_registry')
            return {row[0]: row[1] for row in cursor.fetchall()}
    except Exception as e:
        print(f"Error reading tech_registry: {e}")
        return {}

# NOTE: Do NOT add fetched_content here — it can be several MB and would load
# on every homepage/list request. It is queried separately only where needed:
# get_project_db() for the editor, and the /embed endpoint.
_SELECT_COLS = '''id, title, slug, content, image_url, year, status, project_status,
                  excerpt, meta_description, technologies, created_at, updated_at,
                  year_end, gross_earnings, earnings_currency,
                  gallery_images, gallery_layout, hero_image_align, email_sent,
                  earnings_label, insights,
                  crossposted_linkedin, crossposted_medium, crossposted_substack,
                  crossposted_twitter, crossposted_threads,
                  upvote_count, external_url'''

def _row_to_dict(row):
    """Convert a DB row to a project dict"""
    d = {
        'id': row[0], 'title': row[1], 'slug': row[2], 'content': row[3],
        'image_url': row[4], 'year': row[5], 'status': row[6],
        'project_status': row[7], 'excerpt': row[8], 'meta_description': row[9],
        'technologies': row[10], 'created_at': row[11], 'updated_at': row[12],
    }
    # New columns may not exist in older DBs — guard with len checks
    d['year_end'] = row[13] if len(row) > 13 else None
    d['gross_earnings'] = row[14] if len(row) > 14 else None
    d['earnings_currency'] = row[15] if len(row) > 15 else None
    d['gallery_images'] = row[16] if len(row) > 16 else None
    d['gallery_layout'] = row[17] if len(row) > 17 else None
    d['hero_image_align'] = row[18] if len(row) > 18 else 'center center'
    d['email_sent'] = bool(row[19]) if len(row) > 19 else False
    d['earnings_label'] = row[20] if len(row) > 20 else None
    d['insights'] = row[21] if len(row) > 21 else None
    d['crossposted_linkedin'] = bool(row[22]) if len(row) > 22 else False
    d['crossposted_medium'] = bool(row[23]) if len(row) > 23 else False
    d['crossposted_substack'] = bool(row[24]) if len(row) > 24 else False
    d['crossposted_twitter'] = bool(row[25]) if len(row) > 25 else False
    d['crossposted_threads'] = bool(row[26]) if len(row) > 26 else False
    d['upvote_count'] = row[27] if len(row) > 27 else 0
    d['external_url'] = row[28] if len(row) > 28 else None
    return d

def create_slug(title):
    """Create URL-friendly slug with uniqueness checking"""
    projects_db = get_db_config()
    db_connect = get_db_connection()

    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    slug = slug.strip('-')

    base_slug = slug
    counter = 1

    with db_connect(projects_db) as conn:
        cursor = conn.cursor()
        while True:
            cursor.execute('SELECT id FROM projects WHERE slug = ?', (slug,))
            if not cursor.fetchone():
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

    return slug

def get_all_projects_db(status=None, project_status=None):
    """Get all projects with optional filters.
    status: 'draft' or 'published' (visibility)
    project_status: 'active' or 'inactive' (label)
    """
    projects_db = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(projects_db) as conn:
            cursor = conn.cursor()

            conditions = []
            params = []
            if status:
                conditions.append('status = ?')
                params.append(status)
            if project_status:
                conditions.append('project_status = ?')
                params.append(project_status)

            where = f' WHERE {" AND ".join(conditions)}' if conditions else ''

            cursor.execute(f'''
                SELECT {_SELECT_COLS}
                FROM projects{where}
                ORDER BY year DESC, created_at DESC
            ''', params)

            return [_row_to_dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error getting projects: {e}")
        return []

def create_project_db(title, content, image_url=None, year=None,
                      status='draft', project_status='active', excerpt=None,
                      meta_description=None, technologies=None,
                      year_end=None, gross_earnings=None, earnings_currency=None,
                      gallery_images=None, gallery_layout=None,
                      hero_image_align=None, earnings_label=None, insights=None,
                      external_url=None, fetched_content=None):
    """Create new project in database"""
    projects_db = get_db_config()
    db_connect = get_db_connection()

    slug = create_slug(title)

    try:
        with db_connect(projects_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO projects (title, slug, content, image_url, year,
                    status, project_status, excerpt, meta_description, technologies,
                    year_end, gross_earnings, earnings_currency,
                    gallery_images, gallery_layout, hero_image_align, earnings_label,
                    insights, external_url, fetched_content)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (title, slug, content, image_url, year,
                  status, project_status, excerpt, meta_description, technologies,
                  year_end, gross_earnings, earnings_currency,
                  gallery_images, gallery_layout, hero_image_align, earnings_label,
                  insights, external_url, fetched_content))
            conn.commit()
            return cursor.lastrowid, slug
    except Exception as e:
        print(f"Error creating project: {e}")
        raise

def update_project_db(project_id, title, content, image_url=None, year=None,
                      status=None, project_status=None, excerpt=None,
                      meta_description=None, technologies=None,
                      year_end=None, gross_earnings=None, earnings_currency=None,
                      gallery_images=None, gallery_layout=None,
                      hero_image_align=None, earnings_label=None, insights=None,
                      external_url=None, fetched_content=None):
    """Update existing project"""
    projects_db = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(projects_db) as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT title, slug, status, project_status FROM projects WHERE id = ?', (project_id,))
            current = cursor.fetchone()

            if not current:
                return False

            slug = current[1]
            if current[0] != title:
                slug = create_slug(title)

            if status is None:
                status = current[2]
            if project_status is None:
                project_status = current[3]

            if not title.strip():
                raise ValueError("Title cannot be empty")

            if image_url is not None and not image_url.strip():
                image_url = None

            cursor.execute('''
                UPDATE projects
                SET title = ?, slug = ?, content = ?, image_url = ?, year = ?,
                    status = ?, project_status = ?, excerpt = ?, meta_description = ?,
                    technologies = ?, year_end = ?, gross_earnings = ?,
                    earnings_currency = ?, gallery_images = ?, gallery_layout = ?,
                    hero_image_align = ?, earnings_label = ?, insights = ?,
                    external_url = ?, fetched_content = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (title.strip(), slug, content.strip(), image_url, year,
                  status, project_status, excerpt, meta_description,
                  technologies, year_end, gross_earnings, earnings_currency,
                  gallery_images, gallery_layout, hero_image_align, earnings_label,
                  insights, external_url, fetched_content, project_id))
            conn.commit()

            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error updating project: {e}")
        raise

def delete_project_db(project_id):
    """Delete project from database"""
    projects_db = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(projects_db) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM projects WHERE id = ?', (project_id,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error deleting project: {e}")
        raise

def get_project_db(project_id):
    """Get single project by ID"""
    projects_db = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(projects_db) as conn:
            cursor = conn.cursor()
            cursor.execute(f'SELECT {_SELECT_COLS}, fetched_content FROM projects WHERE id = ?', (project_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = _row_to_dict(row)
            d['fetched_content'] = row[29] if len(row) > 29 else None
            return d
    except Exception as e:
        print(f"Error getting project: {e}")
        return None

def get_project_by_slug_db(slug):
    """Get single project by slug"""
    projects_db = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(projects_db) as conn:
            cursor = conn.cursor()
            cursor.execute(f'SELECT {_SELECT_COLS} FROM projects WHERE slug = ?', (slug,))
            row = cursor.fetchone()
            return _row_to_dict(row) if row else None
    except Exception as e:
        print(f"Error getting project by slug: {e}")
        return None

def toggle_project_status_db(project_id):
    """Toggle project_status between active and inactive"""
    projects_db = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(projects_db) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT project_status FROM projects WHERE id = ?', (project_id,))
            result = cursor.fetchone()
            if not result:
                return None

            new_status = 'inactive' if result[0] == 'active' else 'active'
            cursor.execute('''
                UPDATE projects SET project_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_status, project_id))
            conn.commit()
            return new_status
    except Exception as e:
        print(f"Error toggling project status: {e}")
        return None

def toggle_publish_status_db(project_id):
    """Toggle status between draft and published"""
    projects_db = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(projects_db) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT status FROM projects WHERE id = ?', (project_id,))
            result = cursor.fetchone()
            if not result:
                return None

            new_status = 'draft' if result[0] == 'published' else 'published'
            cursor.execute('''
                UPDATE projects SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_status, project_id))
            conn.commit()
            return new_status
    except Exception as e:
        print(f"Error toggling publish status: {e}")
        return None

def _auto_seo(content, excerpt, meta_description):
    """Auto-generate excerpt/meta_description from content when left blank."""
    if excerpt and meta_description:
        return excerpt, meta_description

    # Strip HTML tags to get plain text
    plain = re.sub(r'<[^>]+>', '', content or '').strip()
    plain = re.sub(r'\s+', ' ', plain)

    if not excerpt and plain:
        if len(plain) <= 200:
            excerpt = plain
        else:
            truncated = plain[:200]
            last_space = truncated.rfind(' ')
            if last_space > 100:
                truncated = truncated[:last_space]
            excerpt = truncated + '...'

    if not meta_description and plain:
        if len(plain) <= 160:
            meta_description = plain
        else:
            truncated = plain[:160]
            last_space = truncated.rfind(' ')
            if last_space > 80:
                truncated = truncated[:last_space]
            meta_description = truncated + '...'

    return excerpt, meta_description


def fetch_external_content(url):
    """Fetch a full HTML page from *url* and prepare it for iframe-free embedding.

    Processing steps:
    1. Inject a viewport meta tag into <head> if one isn't already present.
    2. Inject a small responsive-fix <style> block into <head>.
    3. Rewrite relative src= and href= attributes to absolute URLs based on *url*.

    Returns the processed HTML string.
    """
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    html = resp.text

    # --- 1. Inject viewport meta if missing ---
    viewport_tag = '<meta name="viewport" content="width=device-width, initial-scale=1">'
    if 'name="viewport"' not in html and "name='viewport'" not in html:
        # Insert right after <head> (or <head ...>)
        html = re.sub(
            r'(<head[^>]*>)',
            r'\1\n' + viewport_tag,
            html,
            count=1,
            flags=re.IGNORECASE,
        )

    # --- 2. Inject responsive style block ---
    responsive_style = (
        '<style>'
        'html,body{overflow:hidden;max-width:100%;box-sizing:border-box}'
        'img,table{max-width:100%}'
        'pre{max-width:100%;overflow-x:auto;box-sizing:border-box}'
        '@media(max-width:768px){body{font-size:14px}h1{font-size:1.4em}h2{font-size:1.2em}h3{font-size:1.1em}}'
        '@media(max-width:480px){body{font-size:12px}h1{font-size:1.3em}h2{font-size:1.1em}}'
        '</style>'
    )
    html = re.sub(
        r'(<head[^>]*>)',
        r'\1\n' + responsive_style,
        html,
        count=1,
        flags=re.IGNORECASE,
    )

    # --- 3. Rewrite relative URLs to absolute ---
    _SKIP_PREFIXES = ('http://', 'https://', '//', 'data:', 'mailto:', '#', 'javascript:')

    def _make_absolute(match):
        attr = match.group(1)   # src or href
        quote = match.group(2)  # the quote character (' or ")
        value = match.group(3)  # the URL value
        if value.startswith(_SKIP_PREFIXES):
            return match.group(0)
        absolute = urljoin(url, value)
        return f'{attr}={quote}{absolute}{quote}'

    html = re.sub(
        r'(src|href)=(["\'])(.*?)\2',
        _make_absolute,
        html,
        flags=re.IGNORECASE,
    )

    return html


# ===== Routes =====

@projects_bp.route('/')
@projects_bp.route('/editor')
def projects_editor():
    """Projects editor - main interface"""
    if 'admin_id' not in session:
        return redirect(url_for('admin.login', next=request.path))

    init_projects_db()
    return render_template('projects/projects_editor.html')

@projects_bp.route('/api/projects', methods=['GET'])
def get_projects():
    """Get all projects"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        init_projects_db()
        projects = get_all_projects_db()
        # Strip heavy content fields from list response (loaded per-project on edit)
        for p in projects:
            p.pop('content', None)
            p.pop('fetched_content', None)
        return jsonify(projects)
    except Exception as e:
        print(f"Error getting projects: {e}")
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/api/projects/<int:project_id>', methods=['GET'])
def get_project(project_id):
    """Get single project"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        project = get_project_db(project_id)
        if project:
            return jsonify(project)
        return jsonify({'error': 'Project not found'}), 404
    except Exception as e:
        print(f"Error getting project: {e}")
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/api/projects', methods=['POST'])
def create_project():
    """Create new project"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.json
        title = data.get('title')
        content = data.get('content')
        image_url = data.get('image_url', '')
        year = data.get('year')
        status = data.get('status', 'draft')
        project_status = data.get('project_status', 'active')

        excerpt = data.get('excerpt') or None
        meta_description = data.get('meta_description') or None
        technologies = data.get('technologies') or None

        year_end = data.get('year_end')
        gross_earnings = data.get('gross_earnings')
        earnings_currency = data.get('earnings_currency') or None

        gallery_images = data.get('gallery_images') or None
        gallery_layout = data.get('gallery_layout') or None
        hero_image_align = data.get('hero_image_align') or None
        earnings_label = data.get('earnings_label') or None
        insights = data.get('insights') or None
        external_url = data.get('external_url') or None
        fetched_content = data.get('fetched_content') or None

        if not title:
            return jsonify({'error': 'Title is required'}), 400
        if not content and not external_url:
            return jsonify({'error': 'Content or External URL is required'}), 400
        if not content:
            content = ''

        if year:
            try:
                year = int(year)
            except (ValueError, TypeError):
                return jsonify({'error': 'Year must be a number'}), 400

        if year_end:
            try:
                year_end = int(year_end)
            except (ValueError, TypeError):
                return jsonify({'error': 'Year End must be a number'}), 400

        if gross_earnings:
            try:
                gross_earnings = float(gross_earnings)
            except (ValueError, TypeError):
                return jsonify({'error': 'Gross Earnings must be a number'}), 400

        # SEO auto-fallback: generate excerpt/meta_description from content
        excerpt, meta_description = _auto_seo(content, excerpt, meta_description)

        project_id, slug = create_project_db(
            title, content, image_url, year, status, project_status,
            excerpt=excerpt, meta_description=meta_description,
            technologies=technologies, year_end=year_end,
            gross_earnings=gross_earnings, earnings_currency=earnings_currency,
            gallery_images=gallery_images, gallery_layout=gallery_layout,
            hero_image_align=hero_image_align, earnings_label=earnings_label,
            insights=insights, external_url=external_url,
            fetched_content=fetched_content
        )

        return jsonify({
            'success': True,
            'id': project_id,
            'slug': slug,
            'status': status,
            'project_status': project_status
        })
    except Exception as e:
        print(f"Error creating project: {e}")
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/api/projects/<int:project_id>', methods=['PUT'])
def update_project(project_id):
    """Update project"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.json
        title = data.get('title')
        content = data.get('content')
        image_url = data.get('image_url', '')
        year = data.get('year')
        status = data.get('status')
        project_status = data.get('project_status')

        excerpt = data.get('excerpt') or None
        meta_description = data.get('meta_description') or None
        technologies = data.get('technologies') or None

        year_end = data.get('year_end')
        gross_earnings = data.get('gross_earnings')
        earnings_currency = data.get('earnings_currency') or None

        gallery_images = data.get('gallery_images') or None
        gallery_layout = data.get('gallery_layout') or None
        hero_image_align = data.get('hero_image_align') or None
        earnings_label = data.get('earnings_label') or None
        insights = data.get('insights') or None
        external_url = data.get('external_url') or None
        fetched_content = data.get('fetched_content') or None

        if not title:
            return jsonify({'error': 'Title is required'}), 400
        if not content and not external_url:
            return jsonify({'error': 'Content or External URL is required'}), 400
        if not content:
            content = ''

        if year:
            try:
                year = int(year)
            except (ValueError, TypeError):
                return jsonify({'error': 'Year must be a number'}), 400

        if year_end:
            try:
                year_end = int(year_end)
            except (ValueError, TypeError):
                return jsonify({'error': 'Year End must be a number'}), 400

        if gross_earnings:
            try:
                gross_earnings = float(gross_earnings)
            except (ValueError, TypeError):
                return jsonify({'error': 'Gross Earnings must be a number'}), 400

        # SEO auto-fallback: generate excerpt/meta_description from content
        excerpt, meta_description = _auto_seo(content, excerpt, meta_description)

        success = update_project_db(
            project_id, title, content, image_url, year, status, project_status,
            excerpt=excerpt, meta_description=meta_description,
            technologies=technologies, year_end=year_end,
            gross_earnings=gross_earnings, earnings_currency=earnings_currency,
            gallery_images=gallery_images, gallery_layout=gallery_layout,
            hero_image_align=hero_image_align, earnings_label=earnings_label,
            insights=insights, external_url=external_url,
            fetched_content=fetched_content
        )

        if success:
            return jsonify({'success': True, 'message': 'Project updated successfully'})
        return jsonify({'error': 'Project not found'}), 404
    except Exception as e:
        print(f"Error updating project: {e}")
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/api/projects/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete project"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        success = delete_project_db(project_id)
        if success:
            return jsonify({'success': True})
        return jsonify({'error': 'Project not found'}), 404
    except Exception as e:
        print(f"Error deleting project: {e}")
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/api/projects/<int:project_id>/toggle-status', methods=['POST'])
def toggle_status(project_id):
    """Toggle project_status between active and inactive"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        new_status = toggle_project_status_db(project_id)
        if new_status:
            return jsonify({'success': True, 'project_status': new_status})
        return jsonify({'error': 'Project not found'}), 404
    except Exception as e:
        print(f"Error toggling status: {e}")
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/api/projects/<int:project_id>/toggle-publish', methods=['POST'])
def toggle_publish(project_id):
    """Toggle status between draft and published"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        new_status = toggle_publish_status_db(project_id)
        if new_status:
            return jsonify({'success': True, 'status': new_status})
        return jsonify({'error': 'Project not found'}), 404
    except Exception as e:
        print(f"Error toggling publish: {e}")
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/upload-image', methods=['POST'])
def upload_image():
    """Upload image for projects"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'heic', 'heif'}

    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400

    try:
        from lozzalingo.core.storage import upload_file

        file_ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_ext}"

        file_bytes = file.read()
        image_url = upload_file(file_bytes, unique_filename, 'projects')

        return jsonify({
            'success': True,
            'image_url': image_url,
            'filename': unique_filename
        })

    except Exception as e:
        print(f"Error uploading image: {e}")
        return jsonify({'error': 'Failed to upload image'}), 500


@projects_bp.route('/crop-image', methods=['POST'])
def crop_image():
    """Crop an image server-side and re-upload (avoids CORS canvas issues)"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    url = data.get('url', '')
    cx = int(round(data.get('x', 0)))
    cy = int(round(data.get('y', 0)))
    cw = int(round(data.get('w', 0)))
    ch = int(round(data.get('h', 0)))

    if not url or cw <= 0 or ch <= 0:
        return jsonify({'error': 'Invalid crop parameters'}), 400

    try:
        from PIL import Image as PILImage
        from flask import current_app
        from lozzalingo.core.storage import upload_file
        import io

        # Download the image
        if url.startswith('/static/'):
            rel_path = url[len('/static/'):]
            full_path = os.path.join(current_app.static_folder, rel_path)
            with open(full_path, 'rb') as f:
                img_bytes = f.read()
        else:
            import urllib.request
            with urllib.request.urlopen(url) as resp:
                img_bytes = resp.read()

        # Open and crop
        img = PILImage.open(io.BytesIO(img_bytes))
        cropped = img.crop((cx, cy, cx + cw, cy + ch))

        # Convert to RGB if needed (for JPEG output)
        if cropped.mode in ('RGBA', 'P', 'LA'):
            cropped = cropped.convert('RGB')

        # Save to bytes
        buf = io.BytesIO()
        cropped.save(buf, format='JPEG', quality=85)
        cropped_bytes = buf.getvalue()

        # Upload via storage module
        unique_filename = f"{uuid.uuid4().hex}.jpg"
        image_url = upload_file(cropped_bytes, unique_filename, 'projects')

        return jsonify({'success': True, 'image_url': image_url})

    except Exception as e:
        print(f"Error cropping image: {e}")
        return jsonify({'error': str(e)}), 500


@projects_bp.route('/list-images', methods=['GET'])
def list_images():
    """List uploaded images for the image browser modal"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        from lozzalingo.core.storage import list_files
        folder = request.args.get('folder', 'projects')
        if folder not in ('quick-links', 'blog', 'projects'):
            folder = 'projects'
        images = list_files(folder)
        return jsonify(images)
    except Exception as e:
        print(f"Error listing images: {e}")
        return jsonify({'error': 'Failed to list images'}), 500


@projects_bp.route('/delete-image', methods=['POST'])
def delete_image():
    """Delete an image file, with in-use safety check"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        from lozzalingo.core.storage import delete_file, check_image_in_use
        data = request.json
        url = data.get('url', '')
        force = data.get('force', False)

        if not url:
            return jsonify({'error': 'URL required'}), 400

        refs = check_image_in_use(url)
        if refs and not force:
            return jsonify({
                'in_use': True,
                'references': refs,
                'message': f'Image is used by {len(refs)} item(s)'
            })

        delete_file(url)
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error deleting image: {e}")
        return jsonify({'error': str(e)}), 500


# ===== Tech Registry Routes =====

VALID_CATEGORIES = {'software', 'hardware', 'marketing', 'clients', 'equipment', 'logistics', 'materials', 'other'}

@projects_bp.route('/tech-registry')
def tech_registry():
    """Admin page for managing the technology category registry."""
    if 'admin_id' not in session:
        return redirect(url_for('admin.login', next=request.path))

    init_projects_db()
    return render_template('projects/tech_registry.html')


@projects_bp.route('/api/tech-registry', methods=['GET'])
def get_tech_registry():
    """Return all tech registry entries as a list."""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        init_projects_db()
        projects_db = get_db_config()
        db_connect = get_db_connection()

        with db_connect(projects_db) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name, category FROM tech_registry ORDER BY name')
            entries = [{'name': row[0], 'category': row[1]} for row in cursor.fetchall()]
        return jsonify(entries)
    except Exception as e:
        print(f"Error getting tech registry: {e}")
        return jsonify({'error': str(e)}), 500


@projects_bp.route('/api/tech-registry', methods=['POST'])
def add_tech_registry():
    """Add or update a tech registry entry."""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.json
        name = (data.get('name') or '').strip().lower()
        category = (data.get('category') or '').strip().lower()

        if not name:
            return jsonify({'error': 'Technology name is required'}), 400
        if category not in VALID_CATEGORIES:
            return jsonify({'error': f'Category must be one of: {", ".join(sorted(VALID_CATEGORIES))}'}), 400

        init_projects_db()
        projects_db = get_db_config()
        db_connect = get_db_connection()

        with db_connect(projects_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR REPLACE INTO tech_registry (name, category) VALUES (?, ?)',
                (name, category)
            )
            conn.commit()

        return jsonify({'success': True, 'name': name, 'category': category})
    except Exception as e:
        print(f"Error adding tech registry entry: {e}")
        return jsonify({'error': str(e)}), 500


@projects_bp.route('/api/projects/<int:project_id>/send-email', methods=['POST'])
def send_project_email(project_id):
    """Send project email to subscribers"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin access required'}), 401

    try:
        init_projects_db()
        project = get_project_db(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404

        # Get subscriber emails
        get_subscriber_emails = None
        try:
            from lozzalingo.modules.subscribers.routes import get_all_subscriber_emails
            get_subscriber_emails = get_all_subscriber_emails
        except ImportError:
            pass

        if get_subscriber_emails is None:
            return jsonify({'error': 'Subscribers module not available'}), 500

        subscribers = get_subscriber_emails()
        if not subscribers:
            return jsonify({
                'success': False,
                'message': 'No subscribers found',
                'subscriber_count': 0
            }), 200

        # Build project URL
        slug = project.get('slug', '')
        project_url = f"/projects/{slug}"

        # Prepare project data
        content = project.get('content', '')
        project_data = {
            'id': project['id'],
            'title': project['title'],
            'content': content,
            'slug': slug,
            'excerpt': project.get('excerpt') or (content[:300] + '...' if len(content) > 300 else content),
            'image_url': project.get('image_url', ''),
            'technologies': project.get('technologies', ''),
            'url': project_url
        }

        # Get email service
        email_svc = None
        try:
            from lozzalingo.modules.email.email_service import email_service
            email_svc = email_service
        except ImportError:
            pass

        if email_svc is None:
            return jsonify({'error': 'Email service not available'}), 500

        success = email_svc.send_project_notification(subscribers, project_data)

        if success:
            _mark_project_email_sent(project_id)
            return jsonify({
                'success': True,
                'message': f'Email sent successfully to {len(subscribers)} subscribers',
                'subscriber_count': len(subscribers)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to send email',
                'subscriber_count': len(subscribers)
            }), 500

    except Exception as e:
        print(f"Error sending project email: {e}")
        return jsonify({'error': str(e)}), 500


def _mark_project_email_sent(project_id):
    """Mark a project as having had its email sent"""
    projects_db = get_db_config()
    db_connect = get_db_connection()
    try:
        with db_connect(projects_db) as conn:
            conn.execute(
                'UPDATE projects SET email_sent = 1 WHERE id = ?',
                (project_id,)
            )
            conn.commit()
    except Exception as e:
        print(f"Error marking project email sent: {e}")


# ================================
# CROSS-POST PROJECT
# ================================

VALID_CROSSPOST_PLATFORMS = ('linkedin', 'medium', 'substack', 'twitter', 'threads')

@projects_bp.route('/api/projects/<int:project_id>/crosspost/<platform>', methods=['POST'])
def crosspost_project(project_id, platform):
    """Cross-post a project to an external platform"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin access required'}), 401

    if platform not in VALID_CROSSPOST_PLATFORMS:
        return jsonify({'error': f'Invalid platform. Must be one of: {", ".join(VALID_CROSSPOST_PLATFORMS)}'}), 400

    try:
        init_projects_db()
        project = get_project_db(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404

        if project.get('status') != 'published':
            return jsonify({'error': 'Only published projects can be cross-posted'}), 400

        # Build canonical URL
        from flask import current_app
        site_url = current_app.config.get('EMAIL_WEBSITE_URL', current_app.config.get('SITE_URL', ''))
        slug = project.get('slug', '')
        canonical_url = f"{site_url}/projects/{slug}" if site_url else f"/projects/{slug}"

        # Get crosspost service
        crosspost_svc = None
        try:
            from lozzalingo.modules.crosspost import crosspost_service
            crosspost_svc = crosspost_service
        except ImportError:
            pass

        if crosspost_svc is None:
            return jsonify({'error': 'Cross-post service not available'}), 500

        # Build image URL (absolute)
        image_url = project.get('image_url', '')
        if image_url and not image_url.startswith('http') and site_url:
            image_url = f"{site_url}{image_url}"

        # Dispatch to platform
        result = None
        if platform == 'linkedin':
            result = crosspost_svc.post_to_linkedin(
                title=project['title'],
                excerpt=project.get('excerpt') or project.get('content', '')[:300],
                canonical_url=canonical_url,
                image_url=image_url or None,
            )
        elif platform == 'medium':
            # Parse technologies into tags
            techs = project.get('technologies', '') or ''
            tags = [t.strip() for t in techs.split(',') if t.strip()][:5] if techs else None
            result = crosspost_svc.post_to_medium(
                title=project['title'],
                html_content=project.get('content', ''),
                canonical_url=canonical_url,
                tags=tags,
                image_url=image_url or None,
            )
        elif platform == 'substack':
            result = crosspost_svc.post_to_substack(
                title=project['title'],
                html_content=project.get('content', ''),
                canonical_url=canonical_url,
                image_url=image_url or None,
            )
        elif platform == 'twitter':
            result = crosspost_svc.post_to_twitter(
                title=project['title'],
                excerpt=project.get('excerpt') or project.get('content', '')[:300],
                canonical_url=canonical_url,
                image_url=image_url or None,
            )
        elif platform == 'threads':
            result = crosspost_svc.post_to_threads(
                title=project['title'],
                excerpt=project.get('excerpt') or project.get('content', '')[:300],
                canonical_url=canonical_url,
                image_url=image_url or None,
            )

        if result and result.get('success'):
            _mark_crosspost_sent(project_id, platform)
            return jsonify({
                'success': True,
                'platform': platform,
                'url': result.get('url', ''),
                'message': f'Successfully posted to {platform.title()}',
            })
        else:
            error_msg = result.get('error', 'Unknown error') if result else 'No result'
            return jsonify({'success': False, 'error': error_msg}), 500

    except Exception as e:
        print(f"Error cross-posting project: {e}")
        return jsonify({'error': str(e)}), 500


def _mark_crosspost_sent(project_id, platform):
    """Mark a project as having been cross-posted to a platform"""
    if platform not in VALID_CROSSPOST_PLATFORMS:
        return
    col = f'crossposted_{platform}'
    projects_db = get_db_config()
    db_connect = get_db_connection()
    try:
        with db_connect(projects_db) as conn:
            conn.execute(
                f'UPDATE projects SET {col} = 1 WHERE id = ?',
                (project_id,)
            )
            conn.commit()
    except Exception as e:
        print(f"Error marking project crosspost ({platform}): {e}")


@projects_bp.route('/api/tech-registry/<name>', methods=['DELETE'])
def delete_tech_registry(name):
    """Delete a tech registry entry."""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        init_projects_db()
        projects_db = get_db_config()
        db_connect = get_db_connection()

        with db_connect(projects_db) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM tech_registry WHERE name = ?', (name.lower(),))
            conn.commit()
            if cursor.rowcount > 0:
                return jsonify({'success': True})
            return jsonify({'error': 'Entry not found'}), 404
    except Exception as e:
        print(f"Error deleting tech registry entry: {e}")
        return jsonify({'error': str(e)}), 500


# ================================
# FETCH EXTERNAL CONTENT
# ================================

@projects_bp.route('/api/projects/fetch-external', methods=['POST'])
def fetch_external():
    """Fetch and process an external HTML page for embedding as project content."""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.get_json(silent=True) or {}
        url = (data.get('url') or '').strip()
        if not url:
            return jsonify({'error': 'URL is required'}), 400

        html = fetch_external_content(url)
        return jsonify({'success': True, 'html': html})
    except requests.RequestException as e:
        print(f"Error fetching external content: {e}")
        return jsonify({'error': f'Failed to fetch URL: {e}'}), 502
    except Exception as e:
        print(f"Error fetching external content: {e}")
        return jsonify({'error': str(e)}), 500
