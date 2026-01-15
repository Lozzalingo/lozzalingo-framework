"""
Customer Spotlight Routes
=========================

Provides:
- Public API to get spotlight entries
- Admin routes for managing spotlight entries
"""

import os
import sqlite3
import uuid
from datetime import datetime
from flask import render_template, request, jsonify, session, redirect, url_for, current_app
from werkzeug.utils import secure_filename
from . import customer_spotlight_bp


def get_db_path():
    """Get the database path from config or environment"""
    try:
        from config import Config
        return getattr(Config, 'USER_DB', None) or os.getenv('USER_DB', 'users.db')
    except ImportError:
        return os.getenv('USER_DB', 'users.db')


def get_spotlight_images_path():
    """Get the path where spotlight images are stored"""
    try:
        from config import Config
        base_path = getattr(Config, 'SPOTLIGHT_IMAGES_PATH', None)
        if base_path:
            return base_path
    except ImportError:
        pass

    # Default to customer_spotlight folder in static
    return os.path.join(os.path.dirname(__file__), 'static', 'images')


def init_table():
    """Initialize the customer spotlight table"""
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customer_spotlight (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instagram_handle TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                optimized_filename TEXT,
                image_path TEXT NOT NULL,
                optimized_image_path TEXT,
                file_size INTEGER,
                optimized_file_size INTEGER,
                width INTEGER,
                height INTEGER,
                is_active BOOLEAN DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_customer_spotlight_active ON customer_spotlight(is_active)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_customer_spotlight_order ON customer_spotlight(sort_order)')

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error initializing customer spotlight table: {e}")
        return False


def get_all_active():
    """Get all active customer spotlight entries"""
    try:
        init_table()
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, instagram_handle, original_filename, optimized_filename,
                   image_path, optimized_image_path, file_size, optimized_file_size,
                   width, height, sort_order, created_at
            FROM customer_spotlight
            WHERE is_active = 1
            ORDER BY sort_order ASC, created_at DESC
        ''')

        rows = cursor.fetchall()
        conn.close()

        spotlights = []
        for row in rows:
            # Use optimized image if available, otherwise use original
            image_url = row[5] if row[5] else row[4]

            spotlights.append({
                'id': row[0],
                'instagram_handle': row[1],
                'original_filename': row[2],
                'optimized_filename': row[3],
                'image_path': row[4],
                'optimized_image_path': row[5],
                'image_url': image_url,
                'file_size': row[6],
                'optimized_file_size': row[7],
                'width': row[8],
                'height': row[9],
                'sort_order': row[10],
                'created_at': row[11]
            })

        return spotlights
    except Exception as e:
        print(f"Error getting customer spotlights: {e}")
        return []


def get_all_spotlights():
    """Get all customer spotlight entries (for admin)"""
    try:
        init_table()
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, instagram_handle, original_filename, optimized_filename,
                   image_path, optimized_image_path, file_size, optimized_file_size,
                   width, height, is_active, sort_order, created_at, updated_at
            FROM customer_spotlight
            ORDER BY sort_order ASC, created_at DESC
        ''')

        rows = cursor.fetchall()
        conn.close()

        spotlights = []
        for row in rows:
            image_url = row[5] if row[5] else row[4]

            spotlights.append({
                'id': row[0],
                'instagram_handle': row[1],
                'original_filename': row[2],
                'optimized_filename': row[3],
                'image_path': row[4],
                'optimized_image_path': row[5],
                'image_url': image_url,
                'file_size': row[6],
                'optimized_file_size': row[7],
                'width': row[8],
                'height': row[9],
                'is_active': row[10],
                'sort_order': row[11],
                'created_at': row[12],
                'updated_at': row[13]
            })

        return spotlights
    except Exception as e:
        print(f"Error getting all customer spotlights: {e}")
        return []


# ===================
# PUBLIC API ROUTES
# ===================

@customer_spotlight_bp.route('/api/customer-spotlight')
def api_get_spotlights():
    """Get all active spotlight entries (public API)"""
    spotlights = get_all_active()
    return jsonify({
        'success': True,
        'spotlights': spotlights,
        'customers': spotlights,  # Alias for compatibility with Mario Pinto JS
        'count': len(spotlights)
    })


# ===================
# ADMIN ROUTES
# ===================

@customer_spotlight_bp.route('/admin/customer-spotlight-editor')
def admin_spotlights():
    """Admin page for managing customer spotlights"""
    if 'admin_id' not in session:
        return redirect(url_for('admin.login', next=request.path))

    return render_template('customer_spotlight/admin.html')


@customer_spotlight_bp.route('/admin/customer-spotlight-editor/spotlights')
def admin_api_get_spotlights():
    """Admin API to get all spotlights (including inactive)"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    spotlights = get_all_spotlights()
    return jsonify({
        'success': True,
        'spotlights': spotlights,
        'count': len(spotlights)
    })


@customer_spotlight_bp.route('/admin/customer-spotlight-editor/upload', methods=['POST'])
def admin_api_add_spotlight():
    """Admin API to add a new spotlight entry"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        instagram_handle = request.form.get('instagram_handle', '').strip()

        if not instagram_handle:
            return jsonify({'success': False, 'error': 'Instagram handle required'}), 400

        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'Image file required'}), 400

        file = request.files['image']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        # Secure the filename and generate unique name
        original_filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{original_filename}"

        # Ensure images directory exists
        images_path = get_spotlight_images_path()
        os.makedirs(images_path, exist_ok=True)

        # Save the file
        file_path = os.path.join(images_path, unique_filename)
        file.save(file_path)

        # Get file size
        file_size = os.path.getsize(file_path)

        # Create image URL path (relative to static)
        image_url = f"/customer-spotlight/static/images/{unique_filename}"

        # Insert into database
        init_table()
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get next sort order
        cursor.execute('SELECT MAX(sort_order) FROM customer_spotlight')
        max_order = cursor.fetchone()[0]
        next_order = (max_order or 0) + 1

        cursor.execute('''
            INSERT INTO customer_spotlight
            (instagram_handle, original_filename, image_path, file_size, sort_order)
            VALUES (?, ?, ?, ?, ?)
        ''', (instagram_handle, original_filename, image_url, file_size, next_order))

        spotlight_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'spotlight_id': spotlight_id,
            'message': f'Spotlight added for @{instagram_handle}'
        })

    except Exception as e:
        print(f"Error adding spotlight: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@customer_spotlight_bp.route('/admin/customer-spotlight-editor/update/<int:spotlight_id>', methods=['POST'])
def admin_api_update_spotlight(spotlight_id):
    """Admin API to update a spotlight entry"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        data = request.get_json()

        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        updates = []
        params = []

        if 'instagram_handle' in data:
            updates.append('instagram_handle = ?')
            params.append(data['instagram_handle'].strip())

        if 'sort_order' in data:
            updates.append('sort_order = ?')
            params.append(int(data['sort_order']))

        if 'is_active' in data:
            updates.append('is_active = ?')
            params.append(1 if data['is_active'] else 0)

        if updates:
            updates.append('updated_at = CURRENT_TIMESTAMP')
            params.append(spotlight_id)

            query = f"UPDATE customer_spotlight SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()

        conn.close()

        return jsonify({
            'success': True,
            'message': 'Spotlight updated successfully'
        })

    except Exception as e:
        print(f"Error updating spotlight: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@customer_spotlight_bp.route('/admin/customer-spotlight-editor/delete/<int:spotlight_id>', methods=['POST'])
def admin_api_delete_spotlight(spotlight_id):
    """Admin API to delete a spotlight entry"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get file path before deletion
        cursor.execute('SELECT image_path FROM customer_spotlight WHERE id = ?', (spotlight_id,))
        result = cursor.fetchone()

        if not result:
            conn.close()
            return jsonify({'success': False, 'error': 'Spotlight not found'}), 404

        # Delete from database
        cursor.execute('DELETE FROM customer_spotlight WHERE id = ?', (spotlight_id,))
        conn.commit()
        conn.close()

        # Optionally delete the file (commented out for safety)
        # if result[0]:
        #     try:
        #         full_path = os.path.join(get_spotlight_images_path(), os.path.basename(result[0]))
        #         if os.path.exists(full_path):
        #             os.remove(full_path)
        #     except Exception as file_error:
        #         print(f"Error deleting file: {file_error}")

        return jsonify({
            'success': True,
            'message': 'Spotlight deleted successfully'
        })

    except Exception as e:
        print(f"Error deleting spotlight: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@customer_spotlight_bp.route('/admin/customer-spotlight-editor/reorder', methods=['POST'])
def admin_api_reorder_spotlights():
    """Admin API to reorder spotlight entries"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    try:
        data = request.get_json()
        orders = data.get('orders', {})  # {spotlight_id: new_order}

        if not orders:
            return jsonify({'success': False, 'error': 'No order data provided'}), 400

        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        for spotlight_id, new_order in orders.items():
            cursor.execute('''
                UPDATE customer_spotlight
                SET sort_order = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_order, spotlight_id))

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Spotlights reordered successfully'
        })

    except Exception as e:
        print(f"Error reordering spotlights: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
