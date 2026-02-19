"""
Quick Links Routes
==================

Admin CRUD + public display for quick links (linktree-style).
Supports image uploads with square cropping.
"""

from flask import render_template, request, redirect, url_for, session, jsonify
from . import quick_links_admin_bp, quick_links_bp
import os
import uuid
from datetime import datetime

# ===== Database Helper Functions =====

def get_db_config():
    """Get database configuration"""
    try:
        from flask import current_app
        val = current_app.config.get('QUICK_LINKS_DB')
        if val:
            return val
    except RuntimeError:
        pass
    try:
        from config import Config
        return Config.QUICK_LINKS_DB if hasattr(Config, 'QUICK_LINKS_DB') else 'quick_links.db'
    except ImportError:
        return os.getenv('QUICK_LINKS_DB', 'quick_links.db')

def get_db_connection():
    """Get database connection function"""
    try:
        from database import Database
        return Database.connect
    except ImportError:
        import sqlite3
        return sqlite3.connect

def init_quick_links_db():
    """Initialize quick links database"""
    db_path = get_db_config()
    db_connect = get_db_connection()

    try:
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        with db_connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS quick_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    image_url TEXT,
                    description TEXT,
                    sort_order INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Migration: add missing columns
            cursor.execute("PRAGMA table_info(quick_links)")
            columns = [column[1] for column in cursor.fetchall()]

            new_columns = [
                ('image_url', 'TEXT'),
                ('description', 'TEXT'),
                ('sort_order', 'INTEGER DEFAULT 0'),
                ('is_active', 'INTEGER DEFAULT 1'),
            ]
            for col_name, col_type in new_columns:
                if col_name not in columns:
                    try:
                        cursor.execute(f'ALTER TABLE quick_links ADD COLUMN {col_name} {col_type}')
                    except Exception as e:
                        print(f"Could not add column {col_name}: {e}")

            conn.commit()
            print("Quick links database initialized successfully")
    except Exception as e:
        print(f"Error initializing quick links database: {e}")
        raise

def get_all_links_db(active_only=False):
    """Get all links ordered by sort_order"""
    db_path = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(db_path) as conn:
            cursor = conn.cursor()

            if active_only:
                cursor.execute('''
                    SELECT id, title, url, image_url, description, sort_order, is_active,
                           created_at, updated_at
                    FROM quick_links WHERE is_active = 1
                    ORDER BY sort_order ASC, created_at DESC
                ''')
            else:
                cursor.execute('''
                    SELECT id, title, url, image_url, description, sort_order, is_active,
                           created_at, updated_at
                    FROM quick_links
                    ORDER BY sort_order ASC, created_at DESC
                ''')

            rows = cursor.fetchall()
            return [{
                'id': row[0],
                'title': row[1],
                'url': row[2],
                'image_url': row[3],
                'description': row[4],
                'sort_order': row[5],
                'is_active': bool(row[6]),
                'created_at': row[7],
                'updated_at': row[8],
            } for row in rows]
    except Exception as e:
        print(f"Error getting links: {e}")
        return []

def create_link_db(title, url, image_url=None, description=None):
    """Create new quick link"""
    db_path = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT MAX(sort_order) FROM quick_links')
            max_order = cursor.fetchone()[0]
            sort_order = (max_order or 0) + 1

            cursor.execute('''
                INSERT INTO quick_links (title, url, image_url, description, sort_order)
                VALUES (?, ?, ?, ?, ?)
            ''', (title, url, image_url, description, sort_order))
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        print(f"Error creating link: {e}")
        raise

def update_link_db(link_id, title, url, image_url=None, description=None):
    """Update existing quick link"""
    db_path = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE quick_links
                SET title = ?, url = ?, image_url = ?, description = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (title, url, image_url, description, link_id))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error updating link: {e}")
        raise

def delete_link_db(link_id):
    """Delete quick link"""
    db_path = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM quick_links WHERE id = ?', (link_id,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error deleting link: {e}")
        raise

def toggle_link_db(link_id):
    """Toggle link active status"""
    db_path = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT is_active FROM quick_links WHERE id = ?', (link_id,))
            result = cursor.fetchone()
            if not result:
                return None

            new_status = 0 if result[0] else 1
            cursor.execute('''
                UPDATE quick_links SET is_active = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_status, link_id))
            conn.commit()
            return bool(new_status)
    except Exception as e:
        print(f"Error toggling link: {e}")
        return None

def reorder_links_db(id_order):
    """Reorder links by list of IDs"""
    db_path = get_db_config()
    db_connect = get_db_connection()

    try:
        with db_connect(db_path) as conn:
            cursor = conn.cursor()
            for i, link_id in enumerate(id_order):
                cursor.execute('UPDATE quick_links SET sort_order = ? WHERE id = ?', (i, link_id))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error reordering links: {e}")
        return False


# ===== Admin Routes =====

@quick_links_admin_bp.route('/')
def quick_links_editor():
    """Quick links editor - main interface"""
    if 'admin_id' not in session:
        return redirect(url_for('admin.login', next=request.path))

    init_quick_links_db()
    return render_template('quick_links/quick_links_editor.html')

@quick_links_admin_bp.route('/api/links', methods=['GET'])
def get_links():
    """Get all links"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        init_quick_links_db()
        links = get_all_links_db()
        return jsonify(links)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@quick_links_admin_bp.route('/api/links', methods=['POST'])
def create_link():
    """Create new link"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.json
        title = data.get('title', '').strip()
        url = data.get('url', '').strip()
        image_url = data.get('image_url', '').strip() or None
        description = data.get('description', '').strip() or None

        if not title or not url:
            return jsonify({'error': 'Title and URL are required'}), 400

        link_id = create_link_db(title, url, image_url, description)
        return jsonify({'success': True, 'id': link_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@quick_links_admin_bp.route('/api/links/<int:link_id>', methods=['PUT'])
def update_link(link_id):
    """Update link"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.json
        title = data.get('title', '').strip()
        url = data.get('url', '').strip()
        image_url = data.get('image_url', '').strip() or None
        description = data.get('description', '').strip() or None

        if not title or not url:
            return jsonify({'error': 'Title and URL are required'}), 400

        success = update_link_db(link_id, title, url, image_url, description)
        if success:
            return jsonify({'success': True})
        return jsonify({'error': 'Link not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@quick_links_admin_bp.route('/api/links/<int:link_id>', methods=['DELETE'])
def delete_link(link_id):
    """Delete link"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        success = delete_link_db(link_id)
        if success:
            return jsonify({'success': True})
        return jsonify({'error': 'Link not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@quick_links_admin_bp.route('/api/links/<int:link_id>/toggle', methods=['POST'])
def toggle_link(link_id):
    """Toggle link active status"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        new_status = toggle_link_db(link_id)
        if new_status is not None:
            return jsonify({'success': True, 'is_active': new_status})
        return jsonify({'error': 'Link not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@quick_links_admin_bp.route('/api/links/reorder', methods=['POST'])
def reorder_links():
    """Reorder links"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.json
        id_order = data.get('order', [])
        if not id_order:
            return jsonify({'error': 'Order list required'}), 400

        success = reorder_links_db(id_order)
        if success:
            return jsonify({'success': True})
        return jsonify({'error': 'Failed to reorder'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@quick_links_admin_bp.route('/upload-image', methods=['POST'])
def upload_image():
    """Upload and crop image to square for quick links"""
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
        from flask import current_app

        UPLOAD_FOLDER = os.path.join(current_app.static_folder, 'quick-links')
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        file_ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)

        # Save raw file first
        file.save(filepath)

        # Server-side image processing
        mode = request.form.get('mode', 'crop')

        try:
            from PIL import Image

            if mode == 'pad':
                # Pad: place image centered on a coloured square
                pad_color = request.form.get('pad_color', '#000000')
                # Parse hex colour to RGB tuple
                pad_color = pad_color.lstrip('#')
                rgb = tuple(int(pad_color[i:i+2], 16) for i in (0, 2, 4))

                img = Image.open(filepath).convert('RGBA')
                size = max(img.width, img.height)
                bg = Image.new('RGBA', (size, size), rgb + (255,))
                x = (size - img.width) // 2
                y = (size - img.height) // 2
                bg.paste(img, (x, y), img)
                bg = bg.convert('RGB')
                bg = bg.resize((200, 200), Image.LANCZOS)
                bg.save(filepath)
            else:
                # Crop mode
                crop_x = request.form.get('crop_x')
                crop_y = request.form.get('crop_y')
                crop_w = request.form.get('crop_width')
                crop_h = request.form.get('crop_height')

                if crop_x is not None and crop_w is not None:
                    img = Image.open(filepath)
                    x = int(float(crop_x))
                    y = int(float(crop_y))
                    w = int(float(crop_w))
                    h = int(float(crop_h))
                    img = img.crop((x, y, x + w, y + h))
                    img = img.resize((200, 200), Image.LANCZOS)
                    img.save(filepath)
        except ImportError:
            # Pillow not installed - client-side will have to do
            pass
        except Exception as e:
            print(f"Image processing failed (using original): {e}")

        image_url = f"/static/quick-links/{unique_filename}"

        return jsonify({
            'success': True,
            'image_url': image_url,
            'filename': unique_filename
        })

    except Exception as e:
        print(f"Error uploading image: {e}")
        return jsonify({'error': 'Failed to upload image'}), 500


# ===== Public Routes =====

@quick_links_bp.route('/')
def quick_links_page():
    """Public quick links page"""
    init_quick_links_db()
    links = get_all_links_db(active_only=True)
    return render_template('quick_links/quick_links.html', links=links)

@quick_links_bp.route('/api/links', methods=['GET'])
def get_public_links():
    """Get active links API - public endpoint"""
    init_quick_links_db()
    links = get_all_links_db(active_only=True)
    return jsonify(links)
