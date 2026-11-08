"""
External API Routes
===================

Provides API key authenticated endpoints for external services.

API Endpoints (require X-API-Key header):
- POST /api/external/articles - Create a new article
- GET /api/external/articles - List articles
- GET /api/external/articles/<id> - Get single article
- PUT /api/external/articles/<id> - Update article
- DELETE /api/external/articles/<id> - Delete article

Admin Endpoints (require admin session):
- GET /admin/api-keys - List all API keys
- POST /admin/api-keys - Create new API key
- DELETE /admin/api-keys/<id> - Revoke API key
"""

from flask import render_template, request, redirect, url_for, session, jsonify, current_app
from functools import wraps
from . import external_api_bp, external_api_admin_bp
import os
import secrets
import hashlib
from datetime import datetime

# ===== Database Helper Functions =====

def get_db_config():
    """Get database configuration - uses users.db for API keys"""
    try:
        from flask import current_app
        val = current_app.config.get('USER_DB')
        if val:
            return val
    except RuntimeError:
        pass
    try:
        from config import Config
        return Config.USER_DB if hasattr(Config, 'USER_DB') else 'databases/user_log.db'
    except ImportError:
        return os.getenv('USER_DB', 'databases/user_log.db')

def get_db_connection():
    """Get database connection function"""
    try:
        from database import Database
        return Database.connect
    except ImportError:
        import sqlite3
        return sqlite3.connect

def init_api_keys_db():
    """Initialize API keys table in user_log.db"""
    user_db = get_db_config()
    db_connect = get_db_connection()

    try:
        db_dir = os.path.dirname(user_db)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        with db_connect(user_db) as conn:
            cursor = conn.cursor()

            # Create API keys table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    key_hash TEXT NOT NULL UNIQUE,
                    key_prefix TEXT NOT NULL,
                    permissions TEXT DEFAULT 'articles:write',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used_at TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    created_by_admin_id INTEGER
                )
            ''')

            # Create index for faster lookups
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_key_hash ON api_keys(key_hash)')

            conn.commit()
            print("API keys table initialized successfully")
    except Exception as e:
        print(f"Error initializing API keys database: {e}")
        raise

def hash_api_key(key):
    """Hash an API key using SHA-256"""
    return hashlib.sha256(key.encode()).hexdigest()

def generate_api_key():
    """Generate a new API key (prefix_randomstring format)"""
    prefix = "lzl"  # lozzalingo prefix
    random_part = secrets.token_urlsafe(32)
    return f"{prefix}_{random_part}"

def validate_api_key(api_key):
    """Validate an API key and return its data if valid"""
    if not api_key:
        return None

    user_db = get_db_config()
    db_connect = get_db_connection()
    key_hash = hash_api_key(api_key)

    try:
        with db_connect(user_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, permissions, is_active
                FROM api_keys
                WHERE key_hash = ? AND is_active = 1
            ''', (key_hash,))
            row = cursor.fetchone()

            if row:
                # Update last_used_at
                cursor.execute('''
                    UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE id = ?
                ''', (row[0],))
                conn.commit()

                return {
                    'id': row[0],
                    'name': row[1],
                    'permissions': row[2],
                    'is_active': row[3]
                }
            return None
    except Exception as e:
        print(f"Error validating API key: {e}")
        return None

def create_api_key_db(name, admin_id=None, permissions='articles:write'):
    """Create a new API key and store hash in database"""
    user_db = get_db_config()
    db_connect = get_db_connection()

    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)
    key_prefix = api_key[:12] + "..."  # Show first 12 chars for identification

    try:
        with db_connect(user_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO api_keys (name, key_hash, key_prefix, permissions, created_by_admin_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, key_hash, key_prefix, permissions, admin_id))
            conn.commit()

            return {
                'id': cursor.lastrowid,
                'api_key': api_key,  # Only returned once at creation!
                'name': name,
                'key_prefix': key_prefix,
                'permissions': permissions
            }
    except Exception as e:
        print(f"Error creating API key: {e}")
        raise

def get_all_api_keys_db():
    """Get all API keys (without the actual key, just metadata)"""
    user_db = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(user_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, key_prefix, permissions, created_at, last_used_at, is_active
                FROM api_keys
                ORDER BY created_at DESC
            ''')

            rows = cursor.fetchall()
            return [{
                'id': row[0],
                'name': row[1],
                'key_prefix': row[2],
                'permissions': row[3],
                'created_at': row[4],
                'last_used_at': row[5],
                'is_active': bool(row[6])
            } for row in rows]
    except Exception as e:
        print(f"Error getting API keys: {e}")
        return []

def revoke_api_key_db(key_id):
    """Revoke an API key by setting is_active to false"""
    user_db = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(user_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE api_keys SET is_active = 0 WHERE id = ?
            ''', (key_id,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error revoking API key: {e}")
        return False

def delete_api_key_db(key_id):
    """Permanently delete an API key"""
    user_db = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(user_db) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM api_keys WHERE id = ?', (key_id,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error deleting API key: {e}")
        return False

# ===== Authentication Decorator =====

def require_api_key(f):
    """Decorator to require valid API key authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')

        if not api_key:
            return jsonify({
                'error': 'API key required',
                'message': 'Include X-API-Key header with your request'
            }), 401

        key_data = validate_api_key(api_key)
        if not key_data:
            return jsonify({
                'error': 'Invalid API key',
                'message': 'The provided API key is invalid or has been revoked'
            }), 401

        # Attach key data to request for use in route
        request.api_key_data = key_data
        return f(*args, **kwargs)

    return decorated_function

# Article management has moved to the Blog Service (blog.laurence.computer).

# ===== Public External API Routes (API Key Auth) =====

@external_api_bp.before_request
def ensure_tables():
    """Ensure API keys table exists before any request."""
    init_api_keys_db()

@external_api_bp.route('/articles', methods=['GET', 'POST'])
@external_api_bp.route('/articles/<path:rest>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def articles_gone(rest=None):
    """Articles endpoint retired. Use the Blog Service API instead."""
    return jsonify({
        'error': 'This endpoint has been retired.',
        'message': 'Article management has moved to the centralised Blog Service. '
                   'Use POST /api/blog/articles with your site API key.',
        'docs': 'https://blog.laurence.computer'
    }), 410

# ===== Projects External API Routes =====

@external_api_bp.route('/projects', methods=['GET'])
@require_api_key
def get_projects_external():
    """Get all projects (external API) - lightweight list for dropdowns"""
    try:
        from lozzalingo.modules.projects.routes import get_all_projects_db, init_projects_db
        init_projects_db()
        projects = get_all_projects_db()
        print(f"[ExternalAPI] Returning {len(projects)} projects")
        return jsonify({
            'success': True,
            'projects': [{
                'id': p['id'],
                'title': p['title'],
                'slug': p['slug'],
                'status': p.get('status', 'draft'),
                'project_status': p.get('project_status', 'active'),
                'image_url': p.get('image_url'),
            } for p in projects],
            'count': len(projects)
        })
    except ImportError:
        print("[ExternalAPI] Projects module not available")
        return jsonify({'success': False, 'error': 'Projects module not available'}), 404
    except Exception as e:
        print(f"[ExternalAPI] Error fetching projects: {e}")
        return jsonify({'error': str(e)}), 500

@external_api_bp.route('/projects/<int:project_id>', methods=['PUT'])
@require_api_key
def update_project_content_external(project_id):
    """Update project content only (external API) - leaves all other metadata untouched"""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Request body required'}), 400

        content = data.get('content')
        if not content:
            return jsonify({'error': 'Content is required'}), 400

        from lozzalingo.modules.projects.routes import get_db_config, get_db_connection, init_projects_db
        init_projects_db()

        projects_db = get_db_config()
        db_connect = get_db_connection()

        with db_connect(projects_db) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, slug FROM projects WHERE id = ?', (project_id,))
            row = cursor.fetchone()
            if not row:
                return jsonify({'error': 'Project not found'}), 404

            cursor.execute('''
                UPDATE projects SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
            ''', (content, project_id))
            conn.commit()
            print(f"[ExternalAPI] Updated project content: id={project_id}, slug={row[1]}")

        return jsonify({
            'success': True,
            'id': row[0],
            'slug': row[1],
            'message': 'Project content updated successfully'
        })
    except ImportError:
        print("[ExternalAPI] Projects module not available")
        return jsonify({'success': False, 'error': 'Projects module not available'}), 404
    except Exception as e:
        print(f"[ExternalAPI] Error updating project content: {e}")
        return jsonify({'error': str(e)}), 500

# ===== Admin Routes (Session Auth) =====

@external_api_admin_bp.before_request
def ensure_admin_db():
    """Ensure API keys table exists and admin is logged in"""
    init_api_keys_db()

@external_api_admin_bp.route('/')
def api_keys_manager():
    """API keys management interface"""
    if 'admin_id' not in session:
        return redirect(url_for('admin.login', next=request.path))

    return render_template('external_api/api_keys_manager.html')

@external_api_admin_bp.route('/api/keys', methods=['GET'])
def list_api_keys():
    """List all API keys"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        keys = get_all_api_keys_db()
        return jsonify(keys)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@external_api_admin_bp.route('/api/keys', methods=['POST'])
def create_api_key():
    """Create new API key"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.json
        name = data.get('name')

        if not name:
            return jsonify({'error': 'Name is required'}), 400

        permissions = data.get('permissions', 'articles:write')
        admin_id = session.get('admin_id')

        result = create_api_key_db(name, admin_id, permissions)

        return jsonify({
            'success': True,
            'id': result['id'],
            'api_key': result['api_key'],  # Only shown once!
            'name': result['name'],
            'key_prefix': result['key_prefix'],
            'permissions': result['permissions'],
            'message': 'API key created. Copy it now - it will not be shown again!'
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@external_api_admin_bp.route('/api/keys/<int:key_id>', methods=['DELETE'])
def delete_api_key(key_id):
    """Delete/revoke API key"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        # Use revoke (soft delete) instead of hard delete
        success = revoke_api_key_db(key_id)
        if success:
            return jsonify({'success': True, 'message': 'API key revoked successfully'})
        return jsonify({'error': 'API key not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@external_api_admin_bp.route('/api/keys/<int:key_id>/permanent', methods=['DELETE'])
def permanently_delete_api_key(key_id):
    """Permanently delete API key (cannot be undone)"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        success = delete_api_key_db(key_id)
        if success:
            return jsonify({'success': True, 'message': 'API key permanently deleted'})
        return jsonify({'error': 'API key not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
