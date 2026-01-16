"""
News Admin Routes
=================

Complete news/blog management extracted from Mario Pinto project.
Framework-ready with all features.
"""

from flask import render_template, request, redirect, url_for, session, jsonify
from . import news_bp
import os
import uuid
from datetime import datetime
import re

# ===== Database Helper Functions =====

def get_db_config():
    """Get database configuration"""
    try:
        from config import Config
        return Config.NEWS_DB if hasattr(Config, 'NEWS_DB') else 'news.db'
    except ImportError:
        return os.getenv('NEWS_DB', 'news.db')

def get_db_connection():
    """Get database connection function"""
    try:
        from database import Database
        return Database.connect
    except ImportError:
        import sqlite3
        return sqlite3.connect

def init_news_db():
    """Initialize news database with migrations"""
    news_db = get_db_config()
    db_connect = get_db_connection()

    try:
        # Create directory if it doesn't exist (only if there's a directory component)
        db_dir = os.path.dirname(news_db)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        with db_connect(news_db) as conn:
            cursor = conn.cursor()

            # First, create the table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS news_articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    slug TEXT NOT NULL UNIQUE,
                    content TEXT NOT NULL,
                    image_url TEXT,
                    status TEXT DEFAULT 'published',
                    email_sent BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    excerpt TEXT,
                    meta_title TEXT,
                    meta_description TEXT,
                    author_name TEXT,
                    author_email TEXT,
                    category_name TEXT,
                    source_id TEXT,
                    source_url TEXT
                )
            ''')

            # Now check if we need to migrate the table (add missing columns)
            cursor.execute("PRAGMA table_info(news_articles)")
            columns = [column[1] for column in cursor.fetchall()]

            # Add new columns for extended article data (from AI Blog Builder integration)
            new_columns = [
                ('status', 'TEXT DEFAULT "published"'),
                ('email_sent', 'BOOLEAN DEFAULT 0'),
                ('excerpt', 'TEXT'),
                ('meta_title', 'TEXT'),
                ('meta_description', 'TEXT'),
                ('author_name', 'TEXT'),
                ('author_email', 'TEXT'),
                ('category_name', 'TEXT'),
                ('source_id', 'TEXT'),
                ('source_url', 'TEXT'),
            ]
            for col_name, col_type in new_columns:
                if col_name not in columns:
                    print(f"Adding {col_name} column to news_articles table...")
                    try:
                        cursor.execute(f'ALTER TABLE news_articles ADD COLUMN {col_name} {col_type}')
                    except Exception as e:
                        print(f"Could not add column {col_name}: {e}")

            # Create indexes for faster lookups
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_slug ON news_articles(slug)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_status ON news_articles(status)')

            conn.commit()
            print("News database initialized successfully")
    except Exception as e:
        print(f"Error initializing news database: {e}")
        raise

def create_slug(title):
    """Create URL-friendly slug with uniqueness checking"""
    news_db = get_db_config()
    db_connect = get_db_connection()

    # Convert to lowercase and replace spaces with hyphens
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    slug = slug.strip('-')

    # Ensure uniqueness
    base_slug = slug
    counter = 1

    with db_connect(news_db) as conn:
        cursor = conn.cursor()
        while True:
            cursor.execute('SELECT id FROM news_articles WHERE slug = ?', (slug,))
            if not cursor.fetchone():
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

    return slug

def get_all_articles_db(status=None):
    """Get all articles with optional status filter"""
    news_db = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(news_db) as conn:
            cursor = conn.cursor()

            if status:
                cursor.execute('''
                    SELECT id, title, slug, content, image_url, status, email_sent, created_at, updated_at,
                           excerpt, meta_title, meta_description, author_name, author_email,
                           category_name, source_id, source_url
                    FROM news_articles
                    WHERE status = ?
                    ORDER BY created_at DESC
                ''', (status,))
            else:
                cursor.execute('''
                    SELECT id, title, slug, content, image_url, status, email_sent, created_at, updated_at,
                           excerpt, meta_title, meta_description, author_name, author_email,
                           category_name, source_id, source_url
                    FROM news_articles
                    ORDER BY created_at DESC
                ''')

            rows = cursor.fetchall()
            articles = []
            for row in rows:
                articles.append({
                    'id': row[0],
                    'title': row[1],
                    'slug': row[2],
                    'content': row[3],
                    'image_url': row[4],
                    'status': row[5],
                    'email_sent': bool(row[6]),
                    'created_at': row[7],
                    'updated_at': row[8],
                    'excerpt': row[9],
                    'meta_title': row[10],
                    'meta_description': row[11],
                    'author_name': row[12],
                    'author_email': row[13],
                    'category_name': row[14],
                    'source_id': row[15],
                    'source_url': row[16]
                })
            return articles
    except Exception as e:
        print(f"Error getting articles: {e}")
        return []

def create_article_db(title, content, image_url=None, status='draft',
                      excerpt=None, meta_title=None, meta_description=None,
                      author_name=None, author_email=None, category_name=None,
                      source_id=None, source_url=None):
    """Create new article in database"""
    news_db = get_db_config()
    db_connect = get_db_connection()

    slug = create_slug(title)

    try:
        with db_connect(news_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO news_articles (title, slug, content, image_url, status,
                    excerpt, meta_title, meta_description, author_name, author_email,
                    category_name, source_id, source_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (title, slug, content, image_url, status,
                  excerpt, meta_title, meta_description, author_name, author_email,
                  category_name, source_id, source_url))
            conn.commit()
            return cursor.lastrowid, slug
    except Exception as e:
        print(f"Error creating article: {e}")
        raise

def update_article_db(article_id, title, content, image_url=None, status=None,
                      excerpt=None, meta_title=None, meta_description=None,
                      author_name=None, author_email=None, category_name=None,
                      source_id=None, source_url=None):
    """Update existing article"""
    news_db = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(news_db) as conn:
            cursor = conn.cursor()

            # Get current article
            cursor.execute('SELECT title, slug, status FROM news_articles WHERE id = ?', (article_id,))
            current = cursor.fetchone()

            if not current:
                return False

            # Generate new slug if title changed
            slug = current[1]
            if current[0] != title:
                slug = create_slug(title)

            # Use current status if not provided
            if status is None:
                status = current[2]

            # Validate required data
            if not title.strip() or not content.strip():
                raise ValueError("Title and content cannot be empty")

            # Clean image_url
            if image_url is not None and not image_url.strip():
                image_url = None

            # Update the article with all fields
            cursor.execute('''
                UPDATE news_articles
                SET title = ?, slug = ?, content = ?, image_url = ?, status = ?,
                    excerpt = ?, meta_title = ?, meta_description = ?,
                    author_name = ?, author_email = ?, category_name = ?,
                    source_id = ?, source_url = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (title.strip(), slug, content.strip(), image_url, status,
                  excerpt, meta_title, meta_description,
                  author_name, author_email, category_name,
                  source_id, source_url, article_id))
            conn.commit()

            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error updating article: {e}")
        raise

def delete_article_db(article_id):
    """Delete article from database"""
    news_db = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(news_db) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM news_articles WHERE id = ?', (article_id,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error deleting article: {e}")
        raise

def get_article_db(article_id):
    """Get single article by ID"""
    news_db = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(news_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, title, slug, content, image_url, status, email_sent, created_at, updated_at,
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
                    'email_sent': bool(row[6]),
                    'created_at': row[7],
                    'updated_at': row[8],
                    'excerpt': row[9],
                    'meta_title': row[10],
                    'meta_description': row[11],
                    'author_name': row[12],
                    'author_email': row[13],
                    'category_name': row[14],
                    'source_id': row[15],
                    'source_url': row[16]
                }
            return None
    except Exception as e:
        print(f"Error getting article: {e}")
        return None

def get_article_by_slug_db(slug):
    """Get single article by slug"""
    news_db = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(news_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, title, slug, content, image_url, status, email_sent, created_at, updated_at,
                       excerpt, meta_title, meta_description, author_name, author_email,
                       category_name, source_id, source_url
                FROM news_articles WHERE slug = ?
            ''', (slug,))
            row = cursor.fetchone()

            if row:
                return {
                    'id': row[0],
                    'title': row[1],
                    'slug': row[2],
                    'content': row[3],
                    'image_url': row[4],
                    'status': row[5],
                    'email_sent': bool(row[6]),
                    'created_at': row[7],
                    'updated_at': row[8],
                    'excerpt': row[9],
                    'meta_title': row[10],
                    'meta_description': row[11],
                    'author_name': row[12],
                    'author_email': row[13],
                    'category_name': row[14],
                    'source_id': row[15],
                    'source_url': row[16]
                }
            return None
    except Exception as e:
        print(f"Error getting article by slug: {e}")
        return None

def toggle_article_status_db(article_id):
    """Toggle article status between draft and published"""
    news_db = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(news_db) as conn:
            cursor = conn.cursor()

            # Get current status
            cursor.execute('SELECT status FROM news_articles WHERE id = ?', (article_id,))
            result = cursor.fetchone()

            if not result:
                return None

            current_status = result[0]
            new_status = 'draft' if current_status == 'published' else 'published'

            # Update status
            cursor.execute('''
                UPDATE news_articles
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_status, article_id))
            conn.commit()

            return new_status
    except Exception as e:
        print(f"Error toggling article status: {e}")
        return None

def mark_email_sent_db(article_id):
    """Mark that email has been sent for this article"""
    news_db = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(news_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE news_articles
                SET email_sent = 1
                WHERE id = ?
            ''', (article_id,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error marking email sent: {e}")
        return False

# ===== Routes =====

@news_bp.route('/')
@news_bp.route('/editor')
def news_editor():
    """News editor - main interface"""
    if 'admin_id' not in session:
        return redirect(url_for('admin.login', next=request.path))

    # Initialize database on first access
    init_news_db()
    return render_template('news/news_editor.html')

@news_bp.route('/api/articles', methods=['GET'])
def get_articles():
    """Get all articles"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        init_news_db()
        articles = get_all_articles_db()
        return jsonify(articles)
    except Exception as e:
        print(f"Error getting articles: {e}")
        return jsonify({'error': str(e)}), 500

@news_bp.route('/api/articles/<int:article_id>', methods=['GET'])
def get_article(article_id):
    """Get single article"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        article = get_article_db(article_id)
        if article:
            return jsonify(article)
        return jsonify({'error': 'Article not found'}), 404
    except Exception as e:
        print(f"Error getting article: {e}")
        return jsonify({'error': str(e)}), 500

@news_bp.route('/api/articles', methods=['POST'])
def create_article():
    """Create new article"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.json
        title = data.get('title')
        content = data.get('content')
        image_url = data.get('image_url', '')
        status = data.get('status', 'draft')

        # New fields
        excerpt = data.get('excerpt') or None
        meta_title = data.get('meta_title') or None
        meta_description = data.get('meta_description') or None
        category_name = data.get('category_name') or None
        author_name = data.get('author_name') or None
        author_email = data.get('author_email') or None
        source_id = data.get('source_id') or None
        source_url = data.get('source_url') or None

        if not title or not content:
            return jsonify({'error': 'Title and content are required'}), 400

        article_id, slug = create_article_db(
            title, content, image_url, status,
            excerpt=excerpt, meta_title=meta_title, meta_description=meta_description,
            author_name=author_name, author_email=author_email, category_name=category_name,
            source_id=source_id, source_url=source_url
        )

        return jsonify({
            'success': True,
            'id': article_id,
            'slug': slug,
            'status': status
        })
    except Exception as e:
        print(f"Error creating article: {e}")
        return jsonify({'error': str(e)}), 500

@news_bp.route('/api/articles/<int:article_id>', methods=['PUT'])
def update_article(article_id):
    """Update article"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.json
        title = data.get('title')
        content = data.get('content')
        image_url = data.get('image_url', '')
        status = data.get('status', 'draft')

        # New fields
        excerpt = data.get('excerpt') or None
        meta_title = data.get('meta_title') or None
        meta_description = data.get('meta_description') or None
        category_name = data.get('category_name') or None
        author_name = data.get('author_name') or None
        author_email = data.get('author_email') or None
        source_id = data.get('source_id') or None
        source_url = data.get('source_url') or None

        if not title or not content:
            return jsonify({'error': 'Title and content are required'}), 400

        success = update_article_db(
            article_id, title, content, image_url, status,
            excerpt=excerpt, meta_title=meta_title, meta_description=meta_description,
            author_name=author_name, author_email=author_email, category_name=category_name,
            source_id=source_id, source_url=source_url
        )

        if success:
            return jsonify({'success': True, 'message': 'Article updated successfully'})
        return jsonify({'error': 'Article not found'}), 404
    except Exception as e:
        print(f"Error updating article: {e}")
        return jsonify({'error': str(e)}), 500

@news_bp.route('/api/articles/<int:article_id>', methods=['DELETE'])
def delete_article(article_id):
    """Delete article"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        success = delete_article_db(article_id)
        if success:
            return jsonify({'success': True})
        return jsonify({'error': 'Article not found'}), 404
    except Exception as e:
        print(f"Error deleting article: {e}")
        return jsonify({'error': str(e)}), 500

@news_bp.route('/api/articles/<int:article_id>/toggle-status', methods=['POST'])
def toggle_status(article_id):
    """Toggle article status between draft and published"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        new_status = toggle_article_status_db(article_id)
        if new_status:
            return jsonify({'success': True, 'status': new_status})
        return jsonify({'error': 'Article not found'}), 404
    except Exception as e:
        print(f"Error toggling status: {e}")
        return jsonify({'error': str(e)}), 500

@news_bp.route('/upload-image', methods=['POST'])
def upload_image():
    """Upload image for articles"""
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
        UPLOAD_FOLDER = 'static/blog'
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        file_ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)

        file.save(filepath)
        image_url = f"/static/blog/{unique_filename}"

        return jsonify({
            'success': True,
            'image_url': image_url,
            'filename': unique_filename
        })

    except Exception as e:
        print(f"Error uploading image: {e}")
        return jsonify({'error': 'Failed to upload image'}), 500
