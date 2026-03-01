"""
Campaigns Models
================

Database schema and CRUD operations for email campaigns.
Tables live in USER_DB alongside subscribers.
"""

import json
import sqlite3
import os
import logging
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
