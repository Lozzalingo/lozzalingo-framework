"""
Admin Dashboard Routes
======================

Core admin dashboard functionality extracted from Mario Pinto project.
Provides authentication and dashboard interface for admin users.
"""

from flask import render_template, request, redirect, url_for, flash, session, jsonify
from . import dashboard_bp
import hashlib
import os
from datetime import datetime, timedelta

def _get_config_value(key, default=None):
    """Get configuration value: Flask app config first, then Config import, then env var"""
    try:
        from flask import current_app
        val = current_app.config.get(key)
        if val:
            return val
    except RuntimeError:
        pass
    try:
        from config import Config
        val = getattr(Config, key, None)
        if val:
            return val
    except ImportError:
        pass
    return os.getenv(key, default)

def hash_password(password):
    """Simple password hashing"""
    return hashlib.sha256(password.encode()).hexdigest()

def init_admin_table(db_connection_func, user_db_path):
    """
    Initialize admin table if it doesn't exist

    Args:
        db_connection_func: Function to connect to database
        user_db_path: Path to user database
    """
    try:
        with db_connection_func(user_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admin (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create email_logs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS email_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    email_type TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.commit()

            # Check if any admin exists
            cursor.execute("SELECT COUNT(*) FROM admin")
            admin_count = cursor.fetchone()[0]

            if admin_count == 0:
                print("No admin users found. Please create an admin account using the /admin/create-admin route.")

    except Exception as e:
        print(f"Error initializing admin table: {e}")

@dashboard_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login route"""
    # Get database connection function and path from config
    user_db = _get_config_value('USER_DB', 'users.db')

    try:
        from database import Database
        db_connect = Database.connect
    except ImportError:
        import sqlite3
        db_connect = sqlite3.connect

    # Initialize admin table on first access
    init_admin_table(db_connect, user_db)

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please enter both email and password', 'error')
            return render_template('dashboard/login.html')

        try:
            with db_connect(user_db) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, email FROM admin
                    WHERE email = ? AND password_hash = ?
                """, (email, hash_password(password)))

                admin = cursor.fetchone()

                if admin:
                    session['admin_id'] = admin[0]
                    session['admin_email'] = admin[1]
                    flash('Login successful', 'success')

                    # Redirect to admin dashboard
                    next_page = request.args.get('next')
                    return redirect(next_page or url_for('admin.dashboard'))
                else:
                    flash('Invalid email or password', 'error')

        except Exception as e:
            flash(f'Login error: {str(e)}', 'error')

    return render_template('dashboard/login.html')

@dashboard_bp.route('/logout')
def logout():
    """Admin logout route"""
    admin_email = session.get('admin_email', 'Unknown')
    session.pop('admin_id', None)
    session.pop('admin_email', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('admin.login'))

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
def dashboard():
    """Admin dashboard - the unified admin interface"""
    if 'admin_id' not in session:
        return redirect(url_for('admin.login', next=request.path))
    return render_template('dashboard/dashboard.html')

@dashboard_bp.route('/change-password', methods=['GET', 'POST'])
def change_password():
    """Change admin password"""
    if 'admin_id' not in session:
        return redirect(url_for('admin.login'))

    # Get database connection
    user_db = _get_config_value('USER_DB', 'users.db')

    try:
        from database import Database
        db_connect = Database.connect
    except ImportError:
        import sqlite3
        db_connect = sqlite3.connect

    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not all([current_password, new_password, confirm_password]):
            flash('All fields are required', 'error')
            return render_template('dashboard/change_password.html')

        if new_password != confirm_password:
            flash('New passwords do not match', 'error')
            return render_template('dashboard/change_password.html')

        if len(new_password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return render_template('dashboard/change_password.html')

        try:
            with db_connect(user_db) as conn:
                cursor = conn.cursor()

                # Verify current password
                cursor.execute("""
                    SELECT id FROM admin
                    WHERE id = ? AND password_hash = ?
                """, (session['admin_id'], hash_password(current_password)))

                if not cursor.fetchone():
                    flash('Current password is incorrect', 'error')
                    return render_template('dashboard/change_password.html')

                # Update password
                cursor.execute("""
                    UPDATE admin
                    SET password_hash = ?
                    WHERE id = ?
                """, (hash_password(new_password), session['admin_id']))

                conn.commit()
                flash('Password changed successfully', 'success')
                return redirect(url_for('admin.dashboard'))

        except Exception as e:
            flash(f'Error changing password: {str(e)}', 'error')

    return render_template('dashboard/change_password.html')

@dashboard_bp.route('/create-admin', methods=['GET', 'POST'])
def create_admin():
    """Create new admin (only accessible by existing admin or if no admins exist)"""
    # Get database connection
    user_db = _get_config_value('USER_DB', 'users.db')

    try:
        from database import Database
        db_connect = Database.connect
    except ImportError:
        import sqlite3
        db_connect = sqlite3.connect

    # Initialize admin table
    init_admin_table(db_connect, user_db)

    # Check if any admin exists
    with db_connect(user_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM admin")
        admin_count = cursor.fetchone()[0]

    # If admins exist, require authentication
    if admin_count > 0 and 'admin_id' not in session:
        return redirect(url_for('admin.login'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not all([email, password, confirm_password]):
            flash('All fields are required', 'error')
            return render_template('dashboard/create_admin.html')

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('dashboard/create_admin.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return render_template('dashboard/create_admin.html')

        try:
            with db_connect(user_db) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO admin (email, password_hash)
                    VALUES (?, ?)
                """, (email, hash_password(password)))

                conn.commit()
                flash(f'Admin {email} created successfully', 'success')
                return redirect(url_for('admin.dashboard'))

        except Exception as e:
            if 'UNIQUE constraint failed' in str(e):
                flash('An admin with this email already exists', 'error')
            else:
                flash(f'Error creating admin: {str(e)}', 'error')

    return render_template('dashboard/create_admin.html')

@dashboard_bp.route('/status')
def status():
    """Check admin login status (API endpoint)"""
    if 'admin_id' in session:
        return jsonify({
            'logged_in': True,
            'admin_email': session.get('admin_email')
        })
    else:
        return jsonify({'logged_in': False}), 401

@dashboard_bp.context_processor
def utility_processor():
    """
    Add utility functions to template context
    """
    def endpoint_exists(endpoint):
        """Check if a Flask endpoint exists"""
        try:
            from flask import current_app
            # Try to build the URL - if it fails, endpoint doesn't exist
            url_for(endpoint)
            return True
        except Exception:
            return False

    def current_year():
        """Return current year for footer"""
        return datetime.now().year

    return dict(
        endpoint_exists=endpoint_exists,
        current_year=current_year
    )

@dashboard_bp.route('/api/stats')
def api_stats():
    """
    API endpoint for dashboard statistics

    Returns stats for various admin dashboard cards.
    Makes database queries optional so sites can implement only what they need.
    """
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        # Get config
        analytics_db = _get_config_value('ANALYTICS_DB')
        news_db = _get_config_value('NEWS_DB')
        user_db = _get_config_value('USER_DB')

        # Get database connection
        try:
            from database import Database
            db_connect = Database.connect
        except ImportError:
            import sqlite3
            db_connect = sqlite3.connect

        stats = {
            'analytics': {
                'total_visitors': 0,
                'today_visitors': 0
            },
            'news': {
                'total_articles': 0,
                'recent_articles': 0
            },
            'admin': {
                'total_admins': 1
            }
        }

        # Get analytics stats (if database exists)
        if analytics_db and os.path.exists(analytics_db):
            try:
                with db_connect(analytics_db) as conn:
                    cursor = conn.cursor()
                    # Filter out localhost and private IPs
                    local_filter = """
                        AND ip IS NOT NULL
                        AND ip NOT IN ('127.0.0.1', '::1', 'localhost')
                        AND ip NOT LIKE '192.168.%'
                        AND ip NOT LIKE '10.%'
                        AND ip NOT LIKE '172.16.%'
                        AND ip NOT LIKE '172.17.%'
                        AND ip NOT LIKE '172.18.%'
                        AND ip NOT LIKE '172.19.%'
                        AND ip NOT LIKE '172.2_.%'
                        AND ip NOT LIKE '172.30.%'
                        AND ip NOT LIKE '172.31.%'
                    """

                    cursor.execute(f"SELECT COUNT(DISTINCT ip) FROM analytics_log WHERE 1=1 {local_filter}")
                    result = cursor.fetchone()
                    stats['analytics']['total_visitors'] = result[0] if result else 0

                    # Today's visitors
                    today = datetime.now().strftime('%Y-%m-%d')
                    cursor.execute(f"SELECT COUNT(DISTINCT ip) FROM analytics_log WHERE DATE(timestamp) = ? {local_filter}", (today,))
                    result = cursor.fetchone()
                    stats['analytics']['today_visitors'] = result[0] if result else 0
            except Exception as e:
                print(f"Analytics stats error: {e}")

        # Get news stats (if database exists)
        if news_db and os.path.exists(news_db):
            try:
                with db_connect(news_db) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM news_articles")
                    result = cursor.fetchone()
                    stats['news']['total_articles'] = result[0] if result else 0

                    # Recent articles (last 30 days)
                    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
                    cursor.execute("SELECT COUNT(*) FROM news_articles WHERE created_at >= ?", (thirty_days_ago,))
                    result = cursor.fetchone()
                    stats['news']['recent_articles'] = result[0] if result else 0
            except Exception as e:
                print(f"News stats error: {e}")

        # Get admin count
        if user_db and os.path.exists(user_db):
            try:
                with db_connect(user_db) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM admin")
                    result = cursor.fetchone()
                    stats['admin']['total_admins'] = result[0] if result else 1
            except Exception as e:
                print(f"Admin stats error: {e}")

        # Get merchandise stats (if database exists)
        try:
            merchandise_db = Config.MERCHANDISE_DB if hasattr(Config, 'MERCHANDISE_DB') else Config.MERCHANDISE if hasattr(Config, 'MERCHANDISE') else None
        except:
            merchandise_db = os.getenv('MERCHANDISE_DB')

        if merchandise_db and os.path.exists(merchandise_db):
            try:
                stats['merchandise'] = {
                    'total_products': 0,
                    'preorder_products': 0
                }
                with db_connect(merchandise_db) as conn:
                    cursor = conn.cursor()
                    # Total active products
                    cursor.execute("SELECT COUNT(*) FROM products WHERE is_active = 1")
                    result = cursor.fetchone()
                    stats['merchandise']['total_products'] = result[0] if result else 0

                    # Preorder products
                    cursor.execute("SELECT COUNT(*) FROM products WHERE is_active = 1 AND is_preorder = 1")
                    result = cursor.fetchone()
                    stats['merchandise']['preorder_products'] = result[0] if result else 0

                    # Order stats (orders table is in the same merchandise database)
                    try:
                        stats['orders'] = {
                            'total_orders': 0,
                            'recent_orders': 0
                        }
                        cursor.execute("SELECT COUNT(*) FROM orders")
                        result = cursor.fetchone()
                        stats['orders']['total_orders'] = result[0] if result else 0

                        # This week's orders
                        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                        cursor.execute("SELECT COUNT(*) FROM orders WHERE DATE(created_at) >= ?", (week_ago,))
                        result = cursor.fetchone()
                        stats['orders']['recent_orders'] = result[0] if result else 0
                    except Exception as e:
                        print(f"Order stats error: {e}")
            except Exception as e:
                print(f"Merchandise stats error: {e}")

        # Get customer spotlight stats (uses user_db)
        if user_db and os.path.exists(user_db):
            try:
                with db_connect(user_db) as conn:
                    cursor = conn.cursor()
                    # Check if table exists
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='customer_spotlight'")
                    if cursor.fetchone():
                        stats['customer_spotlight'] = {
                            'total_active': 0,
                            'size_savings_mb': 0
                        }
                        # Count active spotlights
                        cursor.execute("SELECT COUNT(*) FROM customer_spotlight WHERE is_active = 1")
                        result = cursor.fetchone()
                        stats['customer_spotlight']['total_active'] = result[0] if result else 0

                        # Calculate size savings (original - optimized)
                        cursor.execute("""
                            SELECT SUM(file_size), SUM(optimized_file_size)
                            FROM customer_spotlight
                            WHERE file_size IS NOT NULL
                        """)
                        result = cursor.fetchone()
                        if result and result[0]:
                            original_size = result[0] or 0
                            optimized_size = result[1] or original_size
                            savings_bytes = original_size - optimized_size
                            savings_mb = round(savings_bytes / (1024 * 1024), 2)
                            stats['customer_spotlight']['size_savings_mb'] = max(0, savings_mb)
            except Exception as e:
                print(f"Customer spotlight stats error: {e}")

        return jsonify(stats)

    except Exception as e:
        print(f"Error getting admin stats: {e}")
        return jsonify({'error': str(e)}), 500
