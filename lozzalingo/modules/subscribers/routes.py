"""
Subscribers Routes
==================

Provides:
- POST / -- subscribe (accepts optional feed/feeds param)
- GET /stats -- subscriber count
- GET /feeds -- available feed categories (from app config) + popup config
- GET /manage -- manage subscription preferences page
- POST /manage -- update subscription preferences
- GET /unsubscribe -- unsubscribe page
- POST /unsubscribe -- process unsubscribe
- GET /export -- export list (admin auth required)
- GET /popup-editor -- admin popup config editor
- GET /popup-config -- return current popup config (admin)
- POST /popup-config -- save popup config (admin)

Exported helpers:
- get_all_subscriber_emails(feed=None)
- get_subscriber_count()
- init_subscribers_db()
"""

# INTEGRATION NOTE: This module provides /api/subscribers/* routes.
# If the consuming app has its own subscribers blueprint registered first,
# Flask route priority means the app's routes will take precedence.
# Shipping policy routes are NOT in this module - they belong in the app's
# merchandise blueprint (learned from Feb 2026 outage in Mario Pinto).

import json
import sqlite3
import os
import re
import logging
import time
import hashlib
from datetime import datetime
from flask import request, jsonify, render_template, session, current_app
from . import subscribers_bp

# Email validation regex — rejects consecutive dots, leading/trailing dots
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_%+-]+(\.[a-zA-Z0-9_%+-]+)*@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$')

# Setup logging
logger = logging.getLogger(__name__)

def _db_log(level, message, details=None):
    """Log to framework's persistent DB logger (survives container rebuilds)"""
    try:
        from lozzalingo.core import db_log
        db_log(level, 'subscribers', message, details)
    except Exception:
        pass  # Fall back to stdout logger only


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


def _get_feeds_config():
    """Get configured subscriber feeds from app config"""
    try:
        return current_app.config.get('SUBSCRIBER_FEEDS', [])
    except RuntimeError:
        return []


def _get_default_feed():
    """Get the default feed ID from app config"""
    try:
        return current_app.config.get('SUBSCRIBER_FEEDS_DEFAULT', '')
    except RuntimeError:
        return ''


# Configurable popup defaults — overridden by DB config or app.config['SUBSCRIBER_POPUP']
POPUP_DEFAULTS = {
    'title': 'Stay Updated',
    'subtitle': 'Get the latest news and exclusive content delivered straight to your inbox.',
    'button_text': 'Subscribe Now',
    'skip_text': 'No thanks, maybe later',
    'placeholder': 'Enter your email address',
    'time_delay': 30,
    'exit_intent': True,
    'scroll_trigger': '#news',
    'dismissal_days': 7,
    'button_bg': '',
    'button_color': '',
    'button_hover_bg': '',
    'show_feeds': True,
}


def _get_popup_config():
    """Get popup configuration: DB → app.config['SUBSCRIBER_POPUP'] → POPUP_DEFAULTS"""
    config = dict(POPUP_DEFAULTS)

    # Layer 2: app.config fallback
    try:
        app_popup = current_app.config.get('SUBSCRIBER_POPUP', {})
        if app_popup:
            config.update(app_popup)
    except RuntimeError:
        pass

    # Layer 1: DB config (highest priority)
    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT config FROM subscriber_popup_config LIMIT 1")
            row = cursor.fetchone()
            if row and row[0]:
                db_config = json.loads(row[0])
                config.update(db_config)
    except Exception:
        pass  # Table may not exist yet, or other DB error

    return config


def init_popup_config_table():
    """Create the subscriber_popup_config table (single-row JSON store) in USER_DB"""
    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS subscriber_popup_config (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    config TEXT NOT NULL DEFAULT '{}',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
    except Exception as e:
        logger.error(f"Error creating popup config table: {e}")


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

            # Migrate existing subscribers to default feed if configured
            try:
                default_feed = _get_default_feed()
                if default_feed:
                    cursor.execute(
                        "SELECT COUNT(*) FROM subscribers WHERE is_active = TRUE AND (feeds = '[]' OR feeds = '' OR feeds IS NULL)"
                    )
                    empty_count = cursor.fetchone()[0]
                    if empty_count > 0:
                        cursor.execute(
                            "UPDATE subscribers SET feeds = ? WHERE is_active = TRUE AND (feeds = '[]' OR feeds = '' OR feeds IS NULL)",
                            (json.dumps([default_feed]),)
                        )
                        conn.commit()
                        logger.info(f"Migrated {empty_count} subscribers to default feed: {default_feed}")
            except RuntimeError:
                pass  # No app context (e.g. during import)

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
# BOT DETECTION
# ===================

# In-memory rate limiter: {ip_hash: [timestamp, ...]}
_ip_signup_times = {}
_IP_RATE_LIMIT = 3          # max signups per IP
_IP_RATE_WINDOW = 3600      # per hour (seconds)
_MIN_SUBMIT_TIME = 3        # minimum seconds between form load and submit


def _is_scattered_dot_email(email):
    """Detect bot Gmail pattern: scattered dots like b.g.r.o.ds.ki@gmail.com"""
    local = email.split('@')[0]
    dot_count = local.count('.')
    char_count = len(local.replace('.', ''))
    if char_count == 0:
        return True
    dot_ratio = dot_count / char_count
    return dot_ratio > 0.15 and dot_count >= 3


def _check_ip_rate_limit(ip):
    """Rate limit signups per IP. Returns True if rate limited."""
    now = time.time()
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]

    # Clean old entries
    if ip_hash in _ip_signup_times:
        _ip_signup_times[ip_hash] = [
            t for t in _ip_signup_times[ip_hash]
            if now - t < _IP_RATE_WINDOW
        ]
    else:
        _ip_signup_times[ip_hash] = []

    if len(_ip_signup_times[ip_hash]) >= _IP_RATE_LIMIT:
        return True

    _ip_signup_times[ip_hash].append(now)
    return False


def _detect_bot(data, email, ip_address):
    """Run all bot detection checks. Returns (is_bot, reason) tuple."""
    # 1. Honeypot field — hidden input that only bots fill
    honeypot = data.get('website', '') or data.get('url', '')
    if honeypot:
        return True, 'honeypot'

    # 2. Timestamp check — form submitted too fast
    form_ts = data.get('_ts', 0)
    if form_ts:
        try:
            elapsed = time.time() - float(form_ts)
            if elapsed < _MIN_SUBMIT_TIME:
                return True, 'too_fast'
        except (ValueError, TypeError):
            pass

    # 3. Scattered dot Gmail pattern
    if '@gmail.com' in email and _is_scattered_dot_email(email):
        return True, 'scattered_dots'

    # 4. IP rate limiting
    if _check_ip_rate_limit(ip_address):
        return True, 'rate_limited'

    return False, None


# ===================
# PUBLIC API ROUTES
# ===================

@subscribers_bp.route('', methods=['POST'])
def subscribe():
    """Handle new subscription requests. Accepts optional 'feed' param."""
    init_subscribers_db()
    try:
        data = request.get_json()

        if not data or 'email' not in data:
            return jsonify({'error': 'Email address is required'}), 400

        email = data['email'].lower().strip()
        # Accept either 'feeds' (array) or 'feed' (string) for backwards compat
        feeds_input = data.get('feeds', [])
        feed = data.get('feed', '').strip()
        if feed and not feeds_input:
            feeds_input = [feed]
        # Clean the feeds list
        feeds_input = [f.strip() for f in feeds_input if isinstance(f, str) and f.strip()]

        if not validate_email(email):
            return jsonify({'error': 'Please enter a valid email address'}), 400

        ip_address = get_client_ip()

        # Bot detection — silently reject with a fake success response
        is_bot, reason = _detect_bot(data, email, ip_address)
        if is_bot:
            logger.info(f"Bot signup blocked: {email} (reason: {reason}, ip: {ip_address})")
            _db_log('warning', f'Bot signup blocked: {reason}', {'email': email, 'ip': ip_address})
            # Return fake success so bots think they subscribed
            brand_name = _get_brand_name()
            return jsonify({
                'message': f'Successfully subscribed! Welcome to {brand_name}.'
            }), 201
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

                # Add any new feeds to the subscriber's list
                feeds_changed = False
                if feeds_input:
                    # Replace feeds entirely with the new selection
                    if set(feeds_input) != set(current_feeds):
                        current_feeds = feeds_input
                        feeds_changed = True
                elif not current_feeds:
                    # No feeds specified and none existing — keep empty (= all)
                    pass

                if is_active and not feeds_changed:
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
                        'message': 'Subscription preferences updated!'
                    }), 200
            else:
                # Add new subscription
                feeds_list = feeds_input if feeds_input else []
                cursor.execute('''
                    INSERT INTO subscribers (email, ip_address, user_agent, source, feeds)
                    VALUES (?, ?, ?, ?, ?)
                ''', (email, ip_address, user_agent, 'website', json.dumps(feeds_list)))
                conn.commit()

                logger.info(f"New subscription added: {email}")
                _db_log('info', f'New subscriber: {email}', {'ip': ip_address})

                # Send welcome email
                svc = _get_email_service()
                if svc:
                    try:
                        svc.send_welcome_email(email)
                        logger.info(f"Welcome email sent to: {email}")
                        _db_log('info', f'Welcome email sent to: {email}')
                    except Exception as email_error:
                        logger.error(f"Failed to send welcome email to {email}: {email_error}")
                        _db_log('error', f'Failed to send welcome email to {email}', {'error': str(email_error)})

                # Send triggered campaigns (e.g. gold code email)
                try:
                    from lozzalingo.modules.campaigns.routes import send_triggered_campaigns
                    send_triggered_campaigns(email, 'new_subscriber')
                except ImportError:
                    pass  # Campaigns module not installed

                _notify_admin_subscriber(email, ip_address, user_agent, 'website')

                return jsonify({
                    'message': f'Successfully subscribed! Welcome to {brand_name}.'
                }), 201

    except sqlite3.Error as e:
        logger.error(f"Database error in subscribe: {e}")
        _db_log('error', f'Database error in subscribe', {'error': str(e)})
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Error in subscribe: {e}")
        _db_log('error', f'Error in subscribe', {'error': str(e)})
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
    init_subscribers_db()
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
    init_subscribers_db()
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
        _db_log('error', f'Database error in unsubscribe', {'error': str(e)})
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Error in unsubscribe: {e}")
        _db_log('error', f'Error in unsubscribe', {'error': str(e)})
        return jsonify({'error': 'An unexpected error occurred'}), 500


@subscribers_bp.route('/export', methods=['GET'])
def export_subscribers():
    """Export subscribers list (admin auth required)"""
    init_subscribers_db()
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
# ADMIN POPUP CONFIG
# ===================

@subscribers_bp.route('/popup-editor', methods=['GET'])
def popup_editor():
    """Admin popup configuration editor page"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    init_popup_config_table()
    config = _get_popup_config()
    return render_template('subscribers/popup_editor.html', config=config)


@subscribers_bp.route('/popup-config', methods=['GET'])
def get_popup_config_api():
    """Return current popup config JSON (admin only)"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    return jsonify(_get_popup_config()), 200


@subscribers_bp.route('/popup-config', methods=['POST'])
def save_popup_config():
    """Save popup config JSON to DB (admin only)"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Whitelist allowed keys
        allowed = set(POPUP_DEFAULTS.keys())
        clean = {k: v for k, v in data.items() if k in allowed}

        init_popup_config_table()
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            conn.execute('''
                INSERT INTO subscriber_popup_config (id, config, updated_at)
                VALUES (1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET config = excluded.config, updated_at = excluded.updated_at
            ''', (json.dumps(clean),))
            conn.commit()

        return jsonify({'message': 'Popup config saved', 'config': clean}), 200

    except Exception as e:
        logger.error(f"Error saving popup config: {e}")
        return jsonify({'error': 'Failed to save config'}), 500


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


@subscribers_bp.route('/feeds', methods=['GET'])
def get_feeds():
    """Return available feed categories and popup config (public endpoint)"""
    feeds = _get_feeds_config()
    default_feed = _get_default_feed()
    return jsonify({
        'feeds': feeds,
        'default': default_feed,
        'popup': _get_popup_config()
    }), 200


@subscribers_bp.route('/manage', methods=['GET'])
def manage_page():
    """Show subscription management page"""
    email = request.args.get('email', '')
    return render_template('subscribers/manage.html', email=email)


@subscribers_bp.route('/manage', methods=['POST'])
def manage_preferences():
    """Update subscription feed preferences"""
    init_subscribers_db()
    try:
        data = request.get_json()
        if not data or 'email' not in data:
            return jsonify({'error': 'Email address is required'}), 400

        email = data['email'].lower().strip()
        new_feeds = data.get('feeds', [])

        if not validate_email(email):
            return jsonify({'error': 'Please enter a valid email address'}), 400

        # Clean feeds list
        new_feeds = [f.strip() for f in new_feeds if isinstance(f, str) and f.strip()]

        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT id, is_active, feeds FROM subscribers WHERE email = ?', (email,))
            existing = cursor.fetchone()

            if not existing:
                return jsonify({'error': 'Email address not found in our subscriber list.'}), 404

            subscriber_id = existing[0]

            if not new_feeds:
                # Empty feeds = unsubscribe from all
                cursor.execute('''
                    UPDATE subscribers
                    SET is_active = FALSE, feeds = '[]', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (subscriber_id,))
                conn.commit()
                logger.info(f"Unsubscribed from all: {email}")
                return jsonify({
                    'message': 'You have been unsubscribed from all emails.'
                }), 200
            else:
                cursor.execute('''
                    UPDATE subscribers
                    SET is_active = TRUE, feeds = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (json.dumps(new_feeds), subscriber_id))
                conn.commit()
                logger.info(f"Updated preferences for {email}: {new_feeds}")
                return jsonify({
                    'message': 'Your subscription preferences have been updated.',
                    'feeds': new_feeds
                }), 200

    except sqlite3.Error as e:
        logger.error(f"Database error in manage_preferences: {e}")
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Error in manage_preferences: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500


@subscribers_bp.route('/preferences', methods=['GET'])
def get_preferences():
    """Get current subscription preferences for an email"""
    init_subscribers_db()
    email = request.args.get('email', '').lower().strip()
    if not email or not validate_email(email):
        return jsonify({'error': 'Valid email is required'}), 400

    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT is_active, feeds FROM subscribers WHERE email = ?', (email,))
            row = cursor.fetchone()

            if not row:
                return jsonify({'found': False}), 200

            return jsonify({
                'found': True,
                'is_active': bool(row[0]),
                'feeds': json.loads(row[1]) if row[1] else []
            }), 200

    except Exception as e:
        logger.error(f"Error getting preferences: {e}")
        return jsonify({'error': 'An error occurred'}), 500


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
