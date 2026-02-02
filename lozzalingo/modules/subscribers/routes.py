"""
Subscribers Routes
==================

Provides:
- POST / -- subscribe (accepts optional feed param)
- GET /stats -- subscriber count
- GET /unsubscribe -- unsubscribe page
- POST /unsubscribe -- process unsubscribe
- GET /export -- export list (admin auth required)

Exported helpers:
- get_all_subscriber_emails(feed=None)
- get_subscriber_count()
- init_subscribers_db()
"""

import json
import sqlite3
import os
import re
import logging
from datetime import datetime
from flask import request, jsonify, render_template, session, current_app
from . import subscribers_bp

# Email validation regex
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# Setup logging
logger = logging.getLogger(__name__)


def get_db_config():
    """Get the database path from config or environment"""
    try:
        val = current_app.config.get('USER_DB')
        if val:
            return val
    except RuntimeError:
        pass
    try:
        from config import Config
        return getattr(Config, 'USER_DB', None) or os.getenv('USER_DB', 'users.db')
    except ImportError:
        return os.getenv('USER_DB', 'users.db')


def _get_email_service():
    """Get the email service (optional import)"""
    try:
        from lozzalingo.modules.email.email_service import email_service
        return email_service
    except ImportError:
        pass
    try:
        from app.services.email_service import email_service
        return email_service
    except ImportError:
        pass
    return None


def _get_brand_name():
    """Get the brand name for user-facing messages"""
    try:
        return current_app.config.get('EMAIL_BRAND_NAME', 'our newsletter')
    except RuntimeError:
        return 'our newsletter'


def init_subscribers_db():
    """Initialize the subscribers table in the database"""
    try:
        db_path = get_db_config()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Create subscribers table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS subscribers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    ip_address TEXT,
                    user_agent TEXT,
                    source TEXT DEFAULT 'website',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    feeds TEXT DEFAULT '[]'
                )
            ''')

            # Create indexes
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_subscribers_email
                ON subscribers(email)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_subscribers_active
                ON subscribers(is_active, subscribed_at)
            ''')

            # Migrate: add feeds column if missing
            cursor.execute("PRAGMA table_info(subscribers)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'feeds' not in columns:
                cursor.execute("ALTER TABLE subscribers ADD COLUMN feeds TEXT DEFAULT '[]'")
                logger.info("Migrated subscribers table: added feeds column")

            conn.commit()
            logger.info("Subscribers database table created/verified successfully")

    except Exception as e:
        logger.error(f"Error initializing subscribers database: {e}")
        raise


def validate_email(email):
    """Validate email format"""
    if not email or len(email) > 255:
        return False
    return EMAIL_REGEX.match(email.lower().strip()) is not None


def get_client_ip():
    """Get client IP address from request"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr


# ===================
# PUBLIC API ROUTES
# ===================

@subscribers_bp.route('', methods=['POST'])
def subscribe():
    """Handle new subscription requests. Accepts optional 'feed' param."""
    try:
        data = request.get_json()

        if not data or 'email' not in data:
            return jsonify({'error': 'Email address is required'}), 400

        email = data['email'].lower().strip()
        feed = data.get('feed', '').strip()  # Optional feed category

        if not validate_email(email):
            return jsonify({'error': 'Please enter a valid email address'}), 400

        ip_address = get_client_ip()
        user_agent = request.headers.get('User-Agent', '')[:500]
        brand_name = _get_brand_name()
        db_path = get_db_config()

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Check if email already exists
            cursor.execute('SELECT id, is_active, feeds FROM subscribers WHERE email = ?', (email,))
            existing = cursor.fetchone()

            if existing:
                subscriber_id, is_active, feeds_json = existing
                current_feeds = json.loads(feeds_json) if feeds_json else []

                # If a feed was specified and not already in the list, add it
                feed_added = False
                if feed and feed not in current_feeds:
                    current_feeds.append(feed)
                    feed_added = True

                if is_active and not feed_added:
                    return jsonify({
                        'message': 'You are already subscribed!'
                    }), 200

                # Reactivate or update feeds
                cursor.execute('''
                    UPDATE subscribers
                    SET is_active = TRUE,
                        updated_at = CURRENT_TIMESTAMP,
                        ip_address = ?,
                        user_agent = ?,
                        feeds = ?
                    WHERE id = ?
                ''', (ip_address, user_agent, json.dumps(current_feeds), subscriber_id))
                conn.commit()

                if not is_active:
                    logger.info(f"Reactivated subscription for: {email}")
                    _notify_admin_subscriber(email, ip_address, user_agent, 'website (reactivated)')
                    return jsonify({
                        'message': 'Welcome back! Your subscription has been reactivated.'
                    }), 200
                else:
                    logger.info(f"Updated feeds for: {email}")
                    return jsonify({
                        'message': f'Successfully subscribed to {feed} updates!'
                    }), 200
            else:
                # Add new subscription
                feeds_list = [feed] if feed else []
                cursor.execute('''
                    INSERT INTO subscribers (email, ip_address, user_agent, source, feeds)
                    VALUES (?, ?, ?, ?, ?)
                ''', (email, ip_address, user_agent, 'website', json.dumps(feeds_list)))
                conn.commit()

                logger.info(f"New subscription added: {email}")

                # Send welcome email
                svc = _get_email_service()
                if svc:
                    try:
                        svc.send_welcome_email(email)
                        logger.info(f"Welcome email sent to: {email}")
                    except Exception as email_error:
                        logger.error(f"Failed to send welcome email to {email}: {email_error}")

                _notify_admin_subscriber(email, ip_address, user_agent, 'website')

                return jsonify({
                    'message': f'Successfully subscribed! Welcome to {brand_name}.'
                }), 201

    except sqlite3.Error as e:
        logger.error(f"Database error in subscribe: {e}")
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Error in subscribe: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500


def _notify_admin_subscriber(email, ip_address, user_agent, source):
    """Send admin notification about new/reactivated subscriber"""
    svc = _get_email_service()
    if svc:
        try:
            subscriber_details = {
                'email': email,
                'subscribed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'ip_address': ip_address,
                'user_agent': user_agent,
                'source': source
            }
            svc.send_admin_subscriber_notification(subscriber_details)
            logger.info(f"Admin notification sent for subscriber: {email}")
        except Exception as e:
            logger.error(f"Failed to send admin notification for {email}: {e}")


@subscribers_bp.route('/stats', methods=['GET'])
def get_subscriber_stats():
    """Get subscriber statistics"""
    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM subscribers WHERE is_active = TRUE')
            count = cursor.fetchone()[0]

            cursor.execute('SELECT MAX(subscribed_at) FROM subscribers WHERE is_active = TRUE')
            last_updated = cursor.fetchone()[0]

            return jsonify({
                'count': count,
                'last_updated': last_updated
            }), 200

    except sqlite3.Error as e:
        logger.error(f"Database error in get_subscriber_stats: {e}")
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Error in get_subscriber_stats: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500


@subscribers_bp.route('/unsubscribe', methods=['GET'])
def unsubscribe_page():
    """Show unsubscribe page"""
    return render_template('subscribers/unsubscribe.html')


@subscribers_bp.route('/unsubscribe', methods=['POST'])
def unsubscribe():
    """Handle unsubscribe requests"""
    try:
        data = request.get_json()

        if not data or 'email' not in data:
            return jsonify({'error': 'Email address is required'}), 400

        email = data['email'].lower().strip()

        if not validate_email(email):
            return jsonify({'error': 'Please enter a valid email address'}), 400

        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE subscribers
                SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE email = ? AND is_active = TRUE
            ''', (email,))

            if cursor.rowcount > 0:
                conn.commit()
                logger.info(f"Unsubscribed: {email}")
                return jsonify({
                    'message': 'Successfully unsubscribed from our newsletter.'
                }), 200
            else:
                return jsonify({
                    'message': 'Email address not found in our subscriber list.'
                }), 404

    except sqlite3.Error as e:
        logger.error(f"Database error in unsubscribe: {e}")
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Error in unsubscribe: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500


@subscribers_bp.route('/export', methods=['GET'])
def export_subscribers():
    """Export subscribers list (admin auth required)"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT email, subscribed_at, source, ip_address, feeds
                FROM subscribers
                WHERE is_active = TRUE
                ORDER BY subscribed_at DESC
            ''')

            subscribers = []
            for row in cursor.fetchall():
                subscribers.append({
                    'email': row[0],
                    'subscribed_at': row[1],
                    'source': row[2],
                    'ip_address': row[3],
                    'feeds': json.loads(row[4]) if row[4] else []
                })

            return jsonify({
                'subscribers': subscribers,
                'total_count': len(subscribers),
                'exported_at': datetime.now().isoformat()
            }), 200

    except sqlite3.Error as e:
        logger.error(f"Database error in export_subscribers: {e}")
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Error in export_subscribers: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500


# ===================
# HELPER FUNCTIONS
# ===================

def get_subscriber_count():
    """Helper function to get current subscriber count"""
    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM subscribers WHERE is_active = TRUE')
            return cursor.fetchone()[0]
    except Exception:
        return 0


def get_all_subscriber_emails(feed=None):
    """Get all active subscriber email addresses, optionally filtered by feed.

    Args:
        feed: If provided, only return subscribers who are subscribed to this feed.
              Subscribers with an empty feeds list (or '[]') receive ALL feeds.
    """
    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT email, feeds FROM subscribers WHERE is_active = TRUE ORDER BY subscribed_at DESC'
            )

            if feed is None:
                # No filter -- return all active subscribers
                return [row[0] for row in cursor.fetchall()]

            # Filter by feed: include if subscriber has this feed OR has empty feeds (= all)
            emails = []
            for row in cursor.fetchall():
                subscriber_feeds = json.loads(row[1]) if row[1] else []
                if not subscriber_feeds or feed in subscriber_feeds:
                    emails.append(row[0])
            return emails

    except Exception as e:
        logger.error(f"Error getting subscriber emails: {e}")
        return []
