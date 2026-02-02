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

def get_news_db_config():
    """Get news database configuration"""
    try:
        from flask import current_app
        val = current_app.config.get('NEWS_DB')
        if val:
            return val
    except RuntimeError:
        pass
    try:
        from config import Config
        return Config.NEWS_DB if hasattr(Config, 'NEWS_DB') else 'databases/news.db'
    except ImportError:
        return os.getenv('NEWS_DB', 'databases/news.db')

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

# ===== News/Articles Helper Functions =====
# These reuse the news module's database functions

def get_news_article_db(article_id):
    """Get single article by ID from news database"""
    news_db = get_news_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(news_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, title, slug, content, image_url, status, created_at, updated_at,
                       excerpt, meta_title, meta_description, author_name, author_email,
                       category_name, source_id, source_url
                FROM news_articles WHERE id = ?
            ''', (article_id,))
            row = cursor.fetchone()

            if row:
                return {
                    'id': row[0],
                    'title': row[1],
                    'slug': row[2],
                    'content': row[3],
                    'image_url': row[4],
                    'status': row[5],
                    'created_at': row[6],
                    'updated_at': row[7],
                    'excerpt': row[8],
                    'meta_title': row[9],
                    'meta_description': row[10],
                    'author_name': row[11],
                    'author_email': row[12],
                    'category_name': row[13],
                    'source_id': row[14],
                    'source_url': row[15]
                }
            return None
    except Exception as e:
        print(f"Error getting article: {e}")
        return None

def get_all_news_articles_db(status=None, limit=50):
    """Get all articles from news database"""
    news_db = get_news_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(news_db) as conn:
            cursor = conn.cursor()

            if status:
                cursor.execute('''
                    SELECT id, title, slug, content, image_url, status, created_at, updated_at,
                           excerpt, meta_title, meta_description, author_name, author_email,
                           category_name, source_id, source_url
                    FROM news_articles
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (status, limit))
            else:
                cursor.execute('''
                    SELECT id, title, slug, content, image_url, status, created_at, updated_at,
                           excerpt, meta_title, meta_description, author_name, author_email,
                           category_name, source_id, source_url
                    FROM news_articles
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (limit,))

            rows = cursor.fetchall()
            return [{
                'id': row[0],
                'title': row[1],
                'slug': row[2],
                'content': row[3],
                'image_url': row[4],
                'status': row[5],
                'created_at': row[6],
                'updated_at': row[7],
                'excerpt': row[8],
                'meta_title': row[9],
                'meta_description': row[10],
                'author_name': row[11],
                'author_email': row[12],
                'category_name': row[13],
                'source_id': row[14],
                'source_url': row[15]
            } for row in rows]
    except Exception as e:
        print(f"Error getting articles: {e}")
        return []

def create_news_article_db(title, content, image_url=None, status='draft', slug=None,
                           excerpt=None, meta_title=None, meta_description=None,
                           author_name=None, author_email=None, category_name=None,
                           source_id=None, source_url=None):
    """Create new article in news database"""
    news_db = get_news_db_config()
    db_connect = get_db_connection()

    # Import slug creation from news module or create inline
    import re

    def create_slug(title, provided_slug=None):
        # Use provided slug if available
        if provided_slug:
            base = re.sub(r'[^\w\s-]', '', provided_slug.lower())
            base = re.sub(r'[-\s]+', '-', base)
            base = base.strip('-')
        else:
            base = re.sub(r'[^\w\s-]', '', title.lower())
            base = re.sub(r'[-\s]+', '-', base)
            base = base.strip('-')

        slug_candidate = base

        # Check uniqueness
        counter = 1
        with db_connect(news_db) as conn:
            cursor = conn.cursor()
            while True:
                cursor.execute('SELECT id FROM news_articles WHERE slug = ?', (slug_candidate,))
                if not cursor.fetchone():
                    break
                slug_candidate = f"{base}-{counter}"
                counter += 1
        return slug_candidate

    final_slug = create_slug(title, slug)

    try:
        with db_connect(news_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO news_articles (title, slug, content, image_url, status,
                    excerpt, meta_title, meta_description, author_name, author_email,
                    category_name, source_id, source_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (title, final_slug, content, image_url, status,
                  excerpt, meta_title, meta_description, author_name, author_email,
                  category_name, source_id, source_url))
            conn.commit()
            return cursor.lastrowid, final_slug
    except Exception as e:
        print(f"Error creating article: {e}")
        raise

def update_news_article_db(article_id, title=None, content=None, image_url=None, status=None,
                           excerpt=None, meta_title=None, meta_description=None,
                           author_name=None, author_email=None, category_name=None,
                           source_id=None, source_url=None):
    """Update existing article in news database"""
    news_db = get_news_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(news_db) as conn:
            cursor = conn.cursor()

            # Get current article with all fields
            cursor.execute('''
                SELECT title, slug, content, image_url, status,
                       excerpt, meta_title, meta_description, author_name, author_email,
                       category_name, source_id, source_url
                FROM news_articles WHERE id = ?
            ''', (article_id,))
            current = cursor.fetchone()

            if not current:
                return False

            # Use current values if not provided
            new_title = title if title is not None else current[0]
            new_content = content if content is not None else current[2]
            new_image_url = image_url if image_url is not None else current[3]
            new_status = status if status is not None else current[4]
            new_excerpt = excerpt if excerpt is not None else current[5]
            new_meta_title = meta_title if meta_title is not None else current[6]
            new_meta_description = meta_description if meta_description is not None else current[7]
            new_author_name = author_name if author_name is not None else current[8]
            new_author_email = author_email if author_email is not None else current[9]
            new_category_name = category_name if category_name is not None else current[10]
            new_source_id = source_id if source_id is not None else current[11]
            new_source_url = source_url if source_url is not None else current[12]

            # Generate new slug if title changed
            slug = current[1]
            if title and current[0] != title:
                import re
                slug = re.sub(r'[^\w\s-]', '', title.lower())
                slug = re.sub(r'[-\s]+', '-', slug)
                slug = slug.strip('-')

            cursor.execute('''
                UPDATE news_articles
                SET title = ?, slug = ?, content = ?, image_url = ?, status = ?,
                    excerpt = ?, meta_title = ?, meta_description = ?,
                    author_name = ?, author_email = ?, category_name = ?,
                    source_id = ?, source_url = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_title, slug, new_content, new_image_url, new_status,
                  new_excerpt, new_meta_title, new_meta_description,
                  new_author_name, new_author_email, new_category_name,
                  new_source_id, new_source_url, article_id))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error updating article: {e}")
        return False

def delete_news_article_db(article_id):
    """Delete article from news database"""
    news_db = get_news_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(news_db) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM news_articles WHERE id = ?', (article_id,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error deleting article: {e}")
        return False

# ===== Public External API Routes (API Key Auth) =====

@external_api_bp.before_request
def ensure_api_keys_db():
    """Ensure API keys table exists before any request"""
    init_api_keys_db()

@external_api_bp.route('/articles', methods=['GET'])
@require_api_key
def get_articles_external():
    """Get all articles (external API)"""
    try:
        status = request.args.get('status')
        limit = request.args.get('limit', 50, type=int)
        articles = get_all_news_articles_db(status=status, limit=limit)
        return jsonify({
            'success': True,
            'articles': articles,
            'count': len(articles)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@external_api_bp.route('/articles/<int:article_id>', methods=['GET'])
@require_api_key
def get_article_external(article_id):
    """Get single article by ID (external API)"""
    try:
        article = get_news_article_db(article_id)
        if article:
            return jsonify({'success': True, 'article': article})
        return jsonify({'error': 'Article not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@external_api_bp.route('/articles', methods=['POST'])
@require_api_key
def create_article_external():
    """Create new article (external API)"""
    try:
        data = request.json

        if not data:
            return jsonify({'error': 'Request body required'}), 400

        title = data.get('title')
        content = data.get('content')
        image_url = data.get('image_url', '')
        status = data.get('status', 'draft')
        slug = data.get('slug')
        excerpt = data.get('excerpt')
        meta_title = data.get('meta_title')
        meta_description = data.get('meta_description')
        source_id = data.get('source_id')
        source_url = data.get('source_url')

        # Handle author - can be an object or individual fields
        author = data.get('author')
        if author and isinstance(author, dict):
            author_name = f"{author.get('name', '')}".strip() or None
            author_email = author.get('email')
        else:
            author_name = data.get('author_name')
            author_email = data.get('author_email')

        # Handle category - can be an object or individual fields
        category = data.get('category')
        if category and isinstance(category, dict):
            category_name = category.get('name')
        else:
            category_name = data.get('category_name')

        if not title or not content:
            return jsonify({'error': 'Title and content are required'}), 400

        article_id, final_slug = create_news_article_db(
            title=title,
            content=content,
            image_url=image_url,
            status=status,
            slug=slug,
            excerpt=excerpt,
            meta_title=meta_title,
            meta_description=meta_description,
            author_name=author_name,
            author_email=author_email,
            category_name=category_name,
            source_id=source_id,
            source_url=source_url
        )

        return jsonify({
            'success': True,
            'id': article_id,
            'slug': final_slug,
            'status': status,
            'message': 'Article created successfully'
        }), 201

    except Exception as e:
        print(f"Error creating article via external API: {e}")
        return jsonify({'error': str(e)}), 500

@external_api_bp.route('/articles/<int:article_id>', methods=['PUT'])
@require_api_key
def update_article_external(article_id):
    """Update article (external API)"""
    try:
        data = request.json

        if not data:
            return jsonify({'error': 'Request body required'}), 400

        # Handle author - can be an object or individual fields
        author = data.get('author')
        if author and isinstance(author, dict):
            author_name = f"{author.get('name', '')}".strip() or None
            author_email = author.get('email')
        else:
            author_name = data.get('author_name')
            author_email = data.get('author_email')

        # Handle category - can be an object or individual fields
        category = data.get('category')
        if category and isinstance(category, dict):
            category_name = category.get('name')
        else:
            category_name = data.get('category_name')

        success = update_news_article_db(
            article_id,
            title=data.get('title'),
            content=data.get('content'),
            image_url=data.get('image_url'),
            status=data.get('status'),
            excerpt=data.get('excerpt'),
            meta_title=data.get('meta_title'),
            meta_description=data.get('meta_description'),
            author_name=author_name,
            author_email=author_email,
            category_name=category_name,
            source_id=data.get('source_id'),
            source_url=data.get('source_url')
        )

        if success:
            return jsonify({'success': True, 'message': 'Article updated successfully'})
        return jsonify({'error': 'Article not found'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@external_api_bp.route('/articles/<int:article_id>', methods=['DELETE'])
@require_api_key
def delete_article_external(article_id):
    """Delete article (external API)"""
    try:
        success = delete_news_article_db(article_id)
        if success:
            return jsonify({'success': True, 'message': 'Article deleted successfully'})
        return jsonify({'error': 'Article not found'}), 404
    except Exception as e:
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
