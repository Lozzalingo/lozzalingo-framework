"""
Projects Public Routes
======================

Public-facing project portfolio pages and API.
"""

from flask import Blueprint, render_template, jsonify, redirect, url_for, flash, request, make_response, abort
import json
import re

projects_public_bp = Blueprint('projects', __name__, url_prefix='/projects', template_folder='templates')


def format_content(content):
    """Format content by converting line breaks to HTML and handling basic formatting"""
    if not content:
        return ""

    content = re.sub(r'\n\s*\n', '</p><p>', content)
    content = re.sub(r'\n', '<br>', content)
    content = f'<p>{content}</p>'
    content = re.sub(r'<p>\s*</p>', '', content)
    content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
    content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', content)
    content = re.sub(r'`(.*?)`', r'<code>\1</code>', content)
    content = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2" target="_blank" rel="noopener">\1</a>', content)

    return content


@projects_public_bp.app_template_filter('format_project_content')
def format_content_filter(content):
    return format_content(content)


@projects_public_bp.app_template_filter('parse_gallery')
def parse_gallery_filter(value):
    """Parse a JSON gallery string into a list of image URLs."""
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return []


@projects_public_bp.app_template_filter('parse_insights')
def parse_insights_filter(value):
    """Parse a JSON insights string into a list of {type, text} dicts."""
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return []


# ===== Routes =====

@projects_public_bp.route('/')
def projects_list():
    """Public projects listing - shows all published projects (active + inactive)."""
    from lozzalingo.modules.projects.routes import get_all_projects_db, init_projects_db, get_all_tech_categories
    init_projects_db()
    projects = get_all_projects_db(status='published')
    tech_categories = get_all_tech_categories()
    return render_template('projects_public/projects.html', projects=projects, tech_categories=tech_categories)


@projects_public_bp.route('/<slug>')
def project_detail(slug):
    """Individual project page."""
    from lozzalingo.modules.projects.routes import get_project_by_slug_db, get_all_projects_db, init_projects_db, get_all_tech_categories
    init_projects_db()
    project = get_project_by_slug_db(slug)

    if not project or project.get('status') != 'published':
        flash('Project not found', 'error')
        return redirect(url_for('projects.projects_list'))

    all_projects = get_all_projects_db(status='published')
    related_projects = [p for p in all_projects if p['slug'] != slug][:3]
    tech_categories = get_all_tech_categories()

    return render_template('projects_public/project_detail.html',
                         project=project, related_projects=related_projects,
                         tech_categories=tech_categories)


@projects_public_bp.route('/<slug>/embed')
def project_embed(slug):
    """Serve a project's content as a raw HTML page (for external-URL embeds)."""
    from lozzalingo.modules.projects.routes import get_project_by_slug_db, init_projects_db
    init_projects_db()
    project = get_project_by_slug_db(slug)

    if not project or not project.get('external_url'):
        abort(404)

    response = make_response(project.get('fetched_content') or project.get('content', ''))
    response.headers['Content-Type'] = 'text/html'
    return response


# ===== API Routes =====

@projects_public_bp.route('/api/projects', methods=['GET'])
def get_projects():
    """Get published projects API - public endpoint."""
    from lozzalingo.modules.projects.routes import get_all_projects_db, init_projects_db
    init_projects_db()
    projects = get_all_projects_db(status='published')
    return jsonify(projects)


@projects_public_bp.route('/api/projects/<int:project_id>/upvote', methods=['POST'])
def upvote_project(project_id):
    """Upvote a project (deduplicated by device fingerprint)."""
    from lozzalingo.modules.projects.routes import get_db_config, get_db_connection, init_projects_db

    data = request.get_json(silent=True) or {}
    fingerprint = data.get('fingerprint')
    if not fingerprint:
        return jsonify({'error': 'fingerprint required'}), 400

    try:
        from lozzalingo.modules.analytics.analytics import Analytics
        fingerprint_hash = Analytics.hash_fingerprint(fingerprint)
    except ImportError:
        import hashlib
        if isinstance(fingerprint, dict):
            fingerprint = json.dumps(fingerprint, sort_keys=True)
        fingerprint_hash = hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()

    init_projects_db()
    projects_db = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(projects_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR IGNORE INTO project_upvotes (project_id, fingerprint_hash) VALUES (?, ?)',
                (project_id, fingerprint_hash)
            )
            if cursor.rowcount > 0:
                cursor.execute(
                    'UPDATE projects SET upvote_count = upvote_count + 1 WHERE id = ?',
                    (project_id,)
                )
                conn.commit()
                cursor.execute('SELECT upvote_count FROM projects WHERE id = ?', (project_id,))
                row = cursor.fetchone()
                return jsonify({'success': True, 'upvote_count': row[0] if row else 0, 'already_voted': False})
            else:
                conn.commit()
                cursor.execute('SELECT upvote_count FROM projects WHERE id = ?', (project_id,))
                row = cursor.fetchone()
                return jsonify({'success': True, 'upvote_count': row[0] if row else 0, 'already_voted': True})
    except Exception as e:
        print(f"Error upvoting project: {e}")
        return jsonify({'error': str(e)}), 500


@projects_public_bp.route('/api/projects/upvote/check-batch', methods=['POST'])
def check_upvote_batch():
    """Check which projects a fingerprint already voted on."""
    from lozzalingo.modules.projects.routes import get_db_config, get_db_connection, init_projects_db

    data = request.get_json(silent=True) or {}
    fingerprint = data.get('fingerprint')
    project_ids = data.get('project_ids', [])

    if not fingerprint or not project_ids:
        return jsonify({'voted': []})

    try:
        from lozzalingo.modules.analytics.analytics import Analytics
        fingerprint_hash = Analytics.hash_fingerprint(fingerprint)
    except ImportError:
        import hashlib
        if isinstance(fingerprint, dict):
            fingerprint = json.dumps(fingerprint, sort_keys=True)
        fingerprint_hash = hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()

    init_projects_db()
    projects_db = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(projects_db) as conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' for _ in project_ids)
            cursor.execute(
                f'SELECT project_id FROM project_upvotes WHERE fingerprint_hash = ? AND project_id IN ({placeholders})',
                [fingerprint_hash] + [int(pid) for pid in project_ids]
            )
            voted = [row[0] for row in cursor.fetchall()]
            return jsonify({'voted': voted})
    except Exception as e:
        print(f"Error checking upvote batch: {e}")
        return jsonify({'voted': []})
