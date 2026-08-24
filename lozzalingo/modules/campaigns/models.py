"""
Campaigns Models
================

Database schema and CRUD operations for email campaigns.
Tables live in USER_DB alongside subscribers.
Includes engagement tracking (opens, clicks, bounces).
"""

import json
import sqlite3
import os
import logging
import hashlib
import hmac
import base64
from datetime import datetime
from flask import current_app

logger = logging.getLogger(__name__)


def _db_log(level, message, details=None):
    """Log to framework's persistent DB logger"""
    try:
        from lozzalingo.core import db_log
        db_log(level, 'campaigns', message, details)
    except Exception:
        pass


def get_db_config():
    """Get the database path from config or environment (3-tier pattern)"""
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


def init_campaigns_db():
    """Create campaigns and campaign_sends tables in USER_DB"""
    try:
        db_path = get_db_config()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    subject TEXT NOT NULL DEFAULT '',
                    blocks TEXT NOT NULL DEFAULT '[]',
                    is_active BOOLEAN DEFAULT TRUE,
                    trigger TEXT DEFAULT 'manual',
                    send_count INTEGER DEFAULT 0,
                    last_sent_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS campaign_sends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    recipient_email TEXT NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'sent',
                    error_message TEXT,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_campaign_sends_campaign
                ON campaign_sends(campaign_id)
            ''')

            # --- Engagement tracking tables ---

            # Add engagement columns to campaign_sends if missing
            cursor.execute('PRAGMA table_info(campaign_sends)')
            existing_cols = {row[1] for row in cursor.fetchall()}

            if 'opened_at' not in existing_cols:
                cursor.execute('ALTER TABLE campaign_sends ADD COLUMN opened_at TIMESTAMP')
            if 'open_count' not in existing_cols:
                cursor.execute('ALTER TABLE campaign_sends ADD COLUMN open_count INTEGER DEFAULT 0')

            # Click tracking table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS campaign_clicks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    recipient_email TEXT NOT NULL,
                    url TEXT NOT NULL,
                    clicked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_campaign_clicks_campaign
                ON campaign_clicks(campaign_id)
            ''')

            # Email events table (bounces, complaints from SES)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS email_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    details_json TEXT,
                    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_email_events_email
                ON email_events(email)
            ''')

            conn.commit()
            logger.info("Campaigns database tables created/verified successfully")

    except Exception as e:
        logger.error(f"Error initializing campaigns database: {e}")
        _db_log('error', 'Failed to init campaigns DB', {'error': str(e)})
        raise


def get_campaign(campaign_id):
    """Get a single campaign by ID"""
    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM campaigns WHERE id = ?', (campaign_id,))
            row = cursor.fetchone()
            if row:
                return _row_to_dict(row)
            return None
    except Exception as e:
        logger.error(f"Error getting campaign {campaign_id}: {e}")
        _db_log('error', f'Error getting campaign {campaign_id}', {'error': str(e)})
        return None


def get_all_campaigns():
    """Get all campaigns ordered by most recent first"""
    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM campaigns ORDER BY updated_at DESC')
            return [_row_to_dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting all campaigns: {e}")
        _db_log('error', 'Error getting all campaigns', {'error': str(e)})
        return []


def save_campaign(data):
    """Create or update a campaign. Returns the campaign ID."""
    try:
        db_path = get_db_config()
        init_campaigns_db()

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            campaign_id = data.get('id')

            blocks_json = json.dumps(data.get('blocks', []))

            if campaign_id:
                cursor.execute('''
                    UPDATE campaigns
                    SET name = ?, subject = ?, blocks = ?, is_active = ?,
                        trigger = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (
                    data.get('name', ''),
                    data.get('subject', ''),
                    blocks_json,
                    data.get('is_active', True),
                    data.get('trigger', 'manual'),
                    campaign_id
                ))
            else:
                cursor.execute('''
                    INSERT INTO campaigns (name, subject, blocks, is_active, trigger)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    data.get('name', ''),
                    data.get('subject', ''),
                    blocks_json,
                    data.get('is_active', True),
                    data.get('trigger', 'manual')
                ))
                campaign_id = cursor.lastrowid

            conn.commit()
            logger.info(f"Saved campaign {campaign_id}: {data.get('name')}")
            return campaign_id

    except Exception as e:
        logger.error(f"Error saving campaign: {e}")
        _db_log('error', 'Error saving campaign', {'error': str(e)})
        return None


def duplicate_campaign(campaign_id):
    """Duplicate a campaign with '(Copy)' appended to the name. Returns new campaign ID."""
    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM campaigns WHERE id = ?', (campaign_id,))
            row = cursor.fetchone()
            if not row:
                return None

            cursor.execute('''
                INSERT INTO campaigns (name, subject, blocks, is_active, trigger)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                row['name'] + ' (Copy)',
                row['subject'],
                row['blocks'],
                row['is_active'],
                row['trigger']
            ))
            new_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Duplicated campaign {campaign_id} -> {new_id}")
            return new_id
    except Exception as e:
        logger.error(f"Error duplicating campaign {campaign_id}: {e}")
        _db_log('error', f'Error duplicating campaign {campaign_id}', {'error': str(e)})
        return None


def delete_campaign(campaign_id):
    """Delete a campaign and its send records"""
    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM campaign_sends WHERE campaign_id = ?', (campaign_id,))
            cursor.execute('DELETE FROM campaigns WHERE id = ?', (campaign_id,))
            conn.commit()
            logger.info(f"Deleted campaign {campaign_id}")
            return True
    except Exception as e:
        logger.error(f"Error deleting campaign {campaign_id}: {e}")
        _db_log('error', f'Error deleting campaign {campaign_id}', {'error': str(e)})
        return False


def get_sent_emails(campaign_id):
    """Get set of emails that have already been successfully sent this campaign"""
    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT recipient_email FROM campaign_sends WHERE campaign_id = ? AND status = ?',
                (campaign_id, 'sent')
            )
            return {row[0] for row in cursor.fetchall()}
    except Exception as e:
        logger.error(f"Error getting sent emails for campaign {campaign_id}: {e}")
        return set()


def record_send(campaign_id, recipient_email, status='sent', error_message=None):
    """Record a send attempt for a campaign"""
    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO campaign_sends (campaign_id, recipient_email, status, error_message)
                VALUES (?, ?, ?, ?)
            ''', (campaign_id, recipient_email, status, error_message))
            conn.commit()
    except Exception as e:
        logger.error(f"Error recording send for campaign {campaign_id}: {e}")
        _db_log('error', f'Error recording send', {'error': str(e)})


def increment_send_count(campaign_id):
    """Increment the send count and update last_sent_at"""
    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE campaigns
                SET send_count = send_count + 1, last_sent_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (campaign_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Error incrementing send count for campaign {campaign_id}: {e}")
        _db_log('error', f'Error incrementing send count', {'error': str(e)})


def get_triggered_campaigns(trigger_type):
    """Get all active campaigns with a specific trigger type"""
    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM campaigns WHERE is_active = 1 AND trigger = ?',
                (trigger_type,)
            )
            return [_row_to_dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting triggered campaigns: {e}")
        _db_log('error', 'Error getting triggered campaigns', {'error': str(e)})
        return []


def _row_to_dict(row):
    """Convert a sqlite3.Row to a dict with parsed blocks JSON"""
    d = dict(row)
    if 'blocks' in d and isinstance(d['blocks'], str):
        try:
            d['blocks'] = json.loads(d['blocks'])
        except (json.JSONDecodeError, TypeError):
            d['blocks'] = []
    return d


# ===================
# TRACKING ID ENCODING
# ===================

def _get_tracking_secret():
    """Get or generate a secret key for tracking ID signatures"""
    try:
        secret = current_app.config.get('SECRET_KEY', '')
        if secret:
            return secret.encode() if isinstance(secret, str) else secret
    except RuntimeError:
        pass
    return b'lozzalingo-tracking-default-key'


def generate_tracking_id(campaign_id, email):
    """Generate a signed tracking ID encoding campaign_id and recipient email.

    Format: base64(campaign_id:email):signature
    The signature prevents forging tracking IDs.
    """
    payload = f'{campaign_id}:{email}'
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode()
    secret = _get_tracking_secret()
    sig = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f'{payload_b64}.{sig}'


def decode_tracking_id(tracking_id):
    """Decode and verify a tracking ID. Returns (campaign_id, email) or (None, None)."""
    try:
        parts = tracking_id.rsplit('.', 1)
        if len(parts) != 2:
            return None, None

        payload_b64, sig = parts
        payload = base64.urlsafe_b64decode(payload_b64.encode()).decode()

        # Verify signature
        secret = _get_tracking_secret()
        expected_sig = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected_sig):
            logger.warning(f"[CAMPAIGNS_TRACKING] Invalid tracking signature")
            return None, None

        campaign_id_str, email = payload.split(':', 1)
        return int(campaign_id_str), email

    except Exception as e:
        logger.warning(f"[CAMPAIGNS_TRACKING] Error decoding tracking ID: {e}")
        return None, None


# ===================
# ENGAGEMENT RECORDING
# ===================

def record_open(campaign_id, email):
    """Record an email open event. Updates opened_at on first open, increments open_count."""
    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # Update the send record for this campaign + recipient
            cursor.execute('''
                UPDATE campaign_sends
                SET open_count = COALESCE(open_count, 0) + 1,
                    opened_at = COALESCE(opened_at, CURRENT_TIMESTAMP)
                WHERE campaign_id = ? AND recipient_email = ? AND status = 'sent'
            ''', (campaign_id, email))
            conn.commit()
            logger.info(f"[CAMPAIGNS_TRACKING] Open recorded: campaign={campaign_id}, email={email}")
    except Exception as e:
        logger.error(f"[CAMPAIGNS_TRACKING] Error recording open: {e}")
        _db_log('error', 'Error recording email open', {'error': str(e)})


def record_click(campaign_id, email, url):
    """Record a link click event."""
    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO campaign_clicks (campaign_id, recipient_email, url)
                VALUES (?, ?, ?)
            ''', (campaign_id, email, url))
            conn.commit()
            logger.info(f"[CAMPAIGNS_TRACKING] Click recorded: campaign={campaign_id}, url={url}")
    except Exception as e:
        logger.error(f"[CAMPAIGNS_TRACKING] Error recording click: {e}")
        _db_log('error', 'Error recording click', {'error': str(e)})


def record_email_event(email, event_type, details=None):
    """Record a bounce, complaint, or other email event from SES."""
    try:
        db_path = get_db_config()
        details_json = json.dumps(details) if details else None
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO email_events (email, event_type, details_json)
                VALUES (?, ?, ?)
            ''', (email, event_type, details_json))
            conn.commit()
            logger.info(f"[CAMPAIGNS_TRACKING] Email event recorded: {event_type} for {email}")
    except Exception as e:
        logger.error(f"[CAMPAIGNS_TRACKING] Error recording email event: {e}")
        _db_log('error', 'Error recording email event', {'error': str(e)})


def deactivate_subscriber(email):
    """Set a subscriber's is_active to 0 (used for bounces/complaints)."""
    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE subscribers SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE email = ?',
                (email,)
            )
            conn.commit()
            if cursor.rowcount > 0:
                logger.info(f"[CAMPAIGNS_TRACKING] Subscriber deactivated: {email}")
                _db_log('warning', f'Subscriber auto-deactivated', {'email': email})
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"[CAMPAIGNS_TRACKING] Error deactivating subscriber: {e}")
        _db_log('error', 'Error deactivating subscriber', {'error': str(e)})
        return False


# ===================
# ENGAGEMENT QUERIES
# ===================

def get_campaign_engagement(campaign_id):
    """Get engagement stats for a single campaign."""
    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Send totals
            cursor.execute(
                "SELECT COUNT(*) FROM campaign_sends WHERE campaign_id = ? AND status = 'sent'",
                (campaign_id,)
            )
            total_sent = cursor.fetchone()[0]

            # Open stats
            cursor.execute(
                "SELECT COUNT(*) FROM campaign_sends WHERE campaign_id = ? AND opened_at IS NOT NULL",
                (campaign_id,)
            )
            unique_opens = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COALESCE(SUM(open_count), 0) FROM campaign_sends WHERE campaign_id = ?",
                (campaign_id,)
            )
            total_opens = cursor.fetchone()[0]

            # Click stats
            cursor.execute(
                "SELECT COUNT(*) FROM campaign_clicks WHERE campaign_id = ?",
                (campaign_id,)
            )
            total_clicks = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(DISTINCT recipient_email) FROM campaign_clicks WHERE campaign_id = ?",
                (campaign_id,)
            )
            unique_clickers = cursor.fetchone()[0]

            # Top clicked links
            cursor.execute('''
                SELECT url, COUNT(*) as click_count
                FROM campaign_clicks WHERE campaign_id = ?
                GROUP BY url ORDER BY click_count DESC LIMIT 10
            ''', (campaign_id,))
            top_links = [{'url': row[0], 'clicks': row[1]} for row in cursor.fetchall()]

            open_rate = round((unique_opens / total_sent * 100), 1) if total_sent > 0 else 0
            click_rate = round((unique_clickers / total_sent * 100), 1) if total_sent > 0 else 0

            return {
                'total_sent': total_sent,
                'unique_opens': unique_opens,
                'total_opens': total_opens,
                'open_rate': open_rate,
                'total_clicks': total_clicks,
                'unique_clickers': unique_clickers,
                'click_rate': click_rate,
                'top_links': top_links,
            }
    except Exception as e:
        logger.error(f"[CAMPAIGNS_TRACKING] Error getting engagement stats: {e}")
        _db_log('error', 'Error getting engagement stats', {'error': str(e)})
        return None


def get_inactive_subscribers(min_campaigns=1):
    """Get subscribers who have never opened any campaign email.

    Args:
        min_campaigns: minimum number of campaigns sent to qualify (default 1)
    """
    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    s.id, s.email, s.subscribed_at, s.is_active,
                    COUNT(cs.id) as campaigns_received,
                    MAX(cs.sent_at) as last_sent_at
                FROM subscribers s
                INNER JOIN campaign_sends cs ON cs.recipient_email = s.email AND cs.status = 'sent'
                LEFT JOIN campaign_sends cs_opened ON cs_opened.recipient_email = s.email AND cs_opened.opened_at IS NOT NULL
                WHERE s.is_active = 1
                AND cs_opened.id IS NULL
                GROUP BY s.email
                HAVING campaigns_received >= ?
                ORDER BY campaigns_received DESC
            ''', (min_campaigns,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"[CAMPAIGNS_TRACKING] Error getting inactive subscribers: {e}")
        _db_log('error', 'Error getting inactive subscribers', {'error': str(e)})
        return []


def bulk_deactivate_subscribers(email_list):
    """Deactivate a list of subscriber emails. Returns count of deactivated."""
    try:
        db_path = get_db_config()
        count = 0
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            for email in email_list:
                cursor.execute(
                    'UPDATE subscribers SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE email = ? AND is_active = 1',
                    (email,)
                )
                count += cursor.rowcount
            conn.commit()
            logger.info(f"[CAMPAIGNS_TRACKING] Bulk deactivated {count} subscribers")
            _db_log('info', f'Bulk deactivated {count} subscribers', {'count': count})
            return count
    except Exception as e:
        logger.error(f"[CAMPAIGNS_TRACKING] Error bulk deactivating subscribers: {e}")
        _db_log('error', 'Error bulk deactivating subscribers', {'error': str(e)})
        return 0
