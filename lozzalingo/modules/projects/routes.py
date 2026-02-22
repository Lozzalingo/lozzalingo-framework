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

_SELECT_COLS = '''id, title, slug, content, image_url, year, status, project_status,
                  excerpt, meta_description, technologies, created_at, updated_at,
                  year_end, gross_earnings, earnings_currency,
                  gallery_images, gallery_layout, content_image_layout'''

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
    d['content_image_layout'] = row[18] if len(row) > 18 else 'carousel'
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
                      content_image_layout=None):
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
                    gallery_images, gallery_layout, content_image_layout)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (title, slug, content, image_url, year,
                  status, project_status, excerpt, meta_description, technologies,
                  year_end, gross_earnings, earnings_currency,
                  gallery_images, gallery_layout, content_image_layout))
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
                      content_image_layout=None):
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

            if not title.strip() or not content.strip():
                raise ValueError("Title and content cannot be empty")

            if image_url is not None and not image_url.strip():
                image_url = None

            cursor.execute('''
                UPDATE projects
                SET title = ?, slug = ?, content = ?, image_url = ?, year = ?,
                    status = ?, project_status = ?, excerpt = ?, meta_description = ?,
                    technologies = ?, year_end = ?, gross_earnings = ?,
                    earnings_currency = ?, gallery_images = ?, gallery_layout = ?,
                    content_image_layout = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (title.strip(), slug, content.strip(), image_url, year,
                  status, project_status, excerpt, meta_description,
                  technologies, year_end, gross_earnings, earnings_currency,
                  gallery_images, gallery_layout, content_image_layout,
                  project_id))
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
            cursor.execute(f'SELECT {_SELECT_COLS} FROM projects WHERE id = ?', (project_id,))
            row = cursor.fetchone()
            return _row_to_dict(row) if row else None
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
        content_image_layout = data.get('content_image_layout') or 'carousel'

        if not title or not content:
            return jsonify({'error': 'Title and content are required'}), 400

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
            content_image_layout=content_image_layout
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
        content_image_layout = data.get('content_image_layout') or 'carousel'

        if not title or not content:
            return jsonify({'error': 'Title and content are required'}), 400

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
            content_image_layout=content_image_layout
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

    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

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
