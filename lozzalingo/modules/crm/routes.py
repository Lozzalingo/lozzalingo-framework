"""
CRM Routes
==========

Admin API for customer relationship management.
All routes require admin auth (session-based).

Endpoints:
- GET    /api/crm/dashboard                    Dashboard overview stats
- GET    /api/crm/customers                    Paginated customer list
- GET    /api/crm/customers/<id>               Customer detail
- PUT    /api/crm/customers/<id>               Update customer
- DELETE /api/crm/customers/<id>               Delete customer + related data
- GET    /api/crm/customers/<id>/activities     Paginated activity history
- POST   /api/crm/customers/<id>/recalculate   Force score recalculation

Exported helpers:
- init_crm_tables()
- create_customer(data) -> customer dict
- log_activity(customer_id, activity_type, **kwargs)
- recalculate_score(customer_id) -> score dict
"""

import json
import sqlite3
import os
import uuid
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, session, current_app
from . import crm_bp

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db_log(level, message, details=None):
    """Log to framework's persistent DB logger (survives container rebuilds)."""
    try:
        from lozzalingo.core import db_log
        db_log(level, 'crm', message, details)
    except Exception:
        pass


def get_db_config():
    """Get the database path from config or environment."""
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


def _get_crm_config():
    """Get CRM config from lozzalingo.yaml (via app.extensions)."""
    try:
        lozza = current_app.extensions.get('lozzalingo')
        if lozza:
            return lozza.config.get('crm', {})
    except RuntimeError:
        pass
    return {}


def _get_customer_prefix():
    """Get the customer number prefix, e.g. 'CG', 'CS', 'LC'."""
    crm_config = _get_crm_config()
    return crm_config.get('customer_prefix', 'CU')


def _get_scoring_weights():
    """Get scoring weights from config with defaults."""
    crm_config = _get_crm_config()
    scoring = crm_config.get('scoring', {})
    return {
        'booking_completed': scoring.get('booking_completed', 20),
        'email_opened': scoring.get('email_opened', 2),
        'email_clicked': scoring.get('email_clicked', 5),
        'website_visit': scoring.get('website_visit', 1),
        'product_used': scoring.get('product_used', 10),
        'app_interaction': scoring.get('app_interaction', 5),
        'returning_visitor': scoring.get('returning_visitor', 5),
        'decay_3_months': scoring.get('decay_3_months', -5),
        'decay_6_months': scoring.get('decay_6_months', -10),
        'decay_12_months': scoring.get('decay_12_months', -15),
    }


def admin_required(f):
    """Decorator to require admin session on CRM routes."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


def _snake_to_camel(name):
    """Convert snake_case to camelCase for JSON responses."""
    parts = name.split('_')
    return parts[0] + ''.join(p.capitalize() for p in parts[1:])


def _customer_row_to_dict(row, columns):
    """Convert a sqlite3 row to a camelCase dict."""
    d = {}
    for i, col in enumerate(columns):
        key = _snake_to_camel(col)
        val = row[i]
        # Convert integer booleans
        if col in ('marketing_opt_in',):
            val = bool(val) if val is not None else False
        d[key] = val
    return d


def _activity_row_to_dict(row, columns):
    """Convert an activity row to a camelCase dict."""
    d = {}
    for i, col in enumerate(columns):
        key = _snake_to_camel(col)
        d[key] = row[i]
    return d


# ---------------------------------------------------------------------------
# Table initialisation
# ---------------------------------------------------------------------------

def init_crm_tables():
    """Create all CRM tables with CREATE TABLE IF NOT EXISTS."""
    try:
        db_path = get_db_config()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # --- customers ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS customers (
                    id TEXT PRIMARY KEY,
                    customer_number TEXT UNIQUE NOT NULL,
                    fingerprint TEXT,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    phone TEXT,
                    company TEXT,
                    job_title TEXT,
                    date_of_birth TEXT,
                    country TEXT,
                    region TEXT,
                    lat REAL,
                    lng REAL,
                    ip_address TEXT,
                    source TEXT,
                    status TEXT DEFAULT 'ACTIVE',
                    marketing_opt_in INTEGER DEFAULT 0,
                    total_spent INTEGER DEFAULT 0,
                    total_bookings INTEGER DEFAULT 0,
                    last_activity_at TEXT,
                    referral_name TEXT,
                    referral_email TEXT,
                    linkedin_url TEXT,
                    instagram_handle TEXT,
                    website_url TEXT,
                    notes TEXT,
                    terms_accepted_at TEXT,
                    privacy_accepted_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_customers_source ON customers(source)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_customers_status ON customers(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_customers_fingerprint ON customers(fingerprint)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_customers_number ON customers(customer_number)')

            # --- customer_activities ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS customer_activities (
                    id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    source TEXT,
                    channel TEXT,
                    product_ref TEXT,
                    product_model TEXT,
                    product_name TEXT,
                    product_category TEXT,
                    platform TEXT,
                    group_type TEXT,
                    audience TEXT,
                    location TEXT,
                    region TEXT,
                    country TEXT,
                    team_name TEXT,
                    event_date TEXT,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_activities_customer ON customer_activities(customer_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_activities_type ON customer_activities(type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_activities_created ON customer_activities(created_at)')

            # --- customer_scores ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS customer_scores (
                    id TEXT PRIMARY KEY,
                    customer_id TEXT UNIQUE NOT NULL,
                    score INTEGER DEFAULT 0,
                    breakdown TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_scores_score ON customer_scores(score)')

            # --- marketing_preferences ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS marketing_preferences (
                    id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    preference TEXT NOT NULL,
                    opted_in INTEGER DEFAULT 1,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES customers(id),
                    UNIQUE(customer_id, preference)
                )
            ''')

            # --- campaigns ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS campaigns (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    sent_at TEXT,
                    total_sent INTEGER DEFAULT 0,
                    total_opened INTEGER DEFAULT 0,
                    total_clicked INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # --- campaign_sends ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS campaign_sends (
                    id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    customer_id TEXT NOT NULL,
                    sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    opened INTEGER DEFAULT 0,
                    opened_at TEXT,
                    clicked INTEGER DEFAULT 0,
                    clicked_at TEXT,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sends_campaign ON campaign_sends(campaign_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sends_customer ON campaign_sends(customer_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sends_sent ON campaign_sends(sent_at)')

            # --- subscriber_confirmations ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS subscriber_confirmations (
                    id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    expires_at TEXT NOT NULL,
                    confirmed INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_confirmations_customer ON subscriber_confirmations(customer_id)')

            conn.commit()
            logger.info("[CRM] All CRM tables created/verified")

    except Exception as e:
        logger.error(f"[CRM] Error initialising CRM tables: {e}")
        _db_log('error', 'Failed to initialise CRM tables', {'error': str(e)})
        raise


# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------

def recalculate_score(customer_id):
    """Recalculate the marketing score for a customer. Returns the score dict."""
    db_path = get_db_config()
    weights = _get_scoring_weights()
    now = datetime.utcnow()

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Fetch customer
        cursor.execute('SELECT * FROM customers WHERE id = ?', (customer_id,))
        customer = cursor.fetchone()
        if not customer:
            return None

        # --- Profile score ---
        profile = 0
        if customer['email']:
            profile += 5
        if customer['phone']:
            profile += 5
        if customer['company']:
            profile += 10
        if customer['marketing_opt_in']:
            profile += 5

        # --- Purchase score ---
        purchase = customer['total_bookings'] * weights['booking_completed']

        # --- Advocacy score ---
        advocacy = 0
        if customer['referral_name'] or customer['referral_email']:
            advocacy += 10

        # --- Engagement score ---
        engagement = 0

        # Activity-based engagement
        cursor.execute(
            'SELECT type, COUNT(*) as cnt FROM customer_activities WHERE customer_id = ? GROUP BY type',
            (customer_id,)
        )
        for row in cursor.fetchall():
            activity_type = row['type']
            count = row['cnt']
            if activity_type == 'WEBSITE_VISIT':
                engagement += count * weights['website_visit']
            elif activity_type == 'PRODUCT_USED' or activity_type == 'GAME_PLAYED':
                engagement += count * weights['product_used']
            elif activity_type == 'APP_INTERACTION':
                engagement += count * weights['app_interaction']

        # Email engagement from campaign sends
        cursor.execute(
            'SELECT SUM(opened) as opens, SUM(clicked) as clicks FROM campaign_sends WHERE customer_id = ?',
            (customer_id,)
        )
        email_row = cursor.fetchone()
        if email_row:
            opens = email_row['opens'] or 0
            clicks = email_row['clicks'] or 0
            engagement += opens * weights['email_opened']
            engagement += clicks * weights['email_clicked']

        # Returning visitor bonus (activity within last 30 days)
        thirty_days_ago = (now - timedelta(days=30)).isoformat()
        cursor.execute(
            'SELECT COUNT(*) FROM customer_activities WHERE customer_id = ? AND created_at > ?',
            (customer_id, thirty_days_ago)
        )
        recent_count = cursor.fetchone()[0]
        if recent_count > 0:
            engagement += weights['returning_visitor']

        # --- Decay ---
        decay = 0
        last_activity = customer['last_activity_at']
        if last_activity:
            try:
                last_dt = datetime.fromisoformat(last_activity.replace('Z', '+00:00').replace('+00:00', ''))
                months_inactive = (now - last_dt).days / 30.0
                if months_inactive >= 12:
                    decay = weights['decay_12_months']
                elif months_inactive >= 6:
                    decay = weights['decay_6_months']
                elif months_inactive >= 3:
                    decay = weights['decay_3_months']
            except (ValueError, TypeError):
                pass

        total = max(0, profile + purchase + advocacy + engagement + decay)
        breakdown = {
            'profile': profile,
            'purchase': purchase,
            'advocacy': advocacy,
            'engagement': engagement,
            'decay': decay,
        }

        # Upsert score
        score_id = str(uuid.uuid4())
        updated_at = now.isoformat()
        cursor.execute('''
            INSERT INTO customer_scores (id, customer_id, score, breakdown, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(customer_id) DO UPDATE SET
                score = excluded.score,
                breakdown = excluded.breakdown,
                updated_at = excluded.updated_at
        ''', (score_id, customer_id, total, json.dumps(breakdown), updated_at))
        conn.commit()

        logger.info(f"[CRM] Recalculated score for {customer_id}: {total}")
        return {'score': total, 'breakdown': breakdown, 'updatedAt': updated_at}


# ---------------------------------------------------------------------------
# Customer number generation
# ---------------------------------------------------------------------------

def _generate_customer_number(cursor):
    """Generate the next customer number, e.g. '#CG0001'."""
    prefix = _get_customer_prefix()
    cursor.execute(
        "SELECT customer_number FROM customers WHERE customer_number LIKE ? ORDER BY customer_number DESC LIMIT 1",
        (f'#{prefix}%',)
    )
    row = cursor.fetchone()
    if row:
        try:
            last_num = int(row[0].replace(f'#{prefix}', ''))
            next_num = last_num + 1
        except (ValueError, IndexError):
            next_num = 1
    else:
        next_num = 1
    return f'#{prefix}{next_num:04d}'


# ---------------------------------------------------------------------------
# Public helpers (for use by other modules)
# ---------------------------------------------------------------------------

def create_customer(data):
    """
    Create a new customer record. Called by other modules (e.g. orders, subscribers).

    Args:
        data: dict with at minimum 'email', 'firstName', 'lastName'.
              Accepts camelCase keys.

    Returns:
        Customer dict (camelCase) or None on duplicate email.
    """
    init_crm_tables()
    db_path = get_db_config()

    customer_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    email = data.get('email', '').lower().strip()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Check for existing
        cursor.execute('SELECT id FROM customers WHERE email = ?', (email,))
        if cursor.fetchone():
            logger.info(f"[CRM] Customer already exists: {email}")
            return None

        customer_number = _generate_customer_number(cursor)

        cursor.execute('''
            INSERT INTO customers (
                id, customer_number, fingerprint, first_name, last_name, email,
                phone, company, job_title, date_of_birth, country, region,
                lat, lng, ip_address, source, status, marketing_opt_in,
                total_spent, total_bookings, last_activity_at,
                referral_name, referral_email, linkedin_url, instagram_handle,
                website_url, notes, terms_accepted_at, privacy_accepted_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            customer_id,
            customer_number,
            data.get('fingerprint'),
            data.get('firstName', data.get('first_name', '')),
            data.get('lastName', data.get('last_name', '')),
            email,
            data.get('phone'),
            data.get('company'),
            data.get('jobTitle', data.get('job_title')),
            data.get('dateOfBirth', data.get('date_of_birth')),
            data.get('country'),
            data.get('region'),
            data.get('lat'),
            data.get('lng'),
            data.get('ipAddress', data.get('ip_address')),
            data.get('source', 'website'),
            data.get('status', 'ACTIVE'),
            1 if data.get('marketingOptIn', data.get('marketing_opt_in', False)) else 0,
            data.get('totalSpent', data.get('total_spent', 0)),
            data.get('totalBookings', data.get('total_bookings', 0)),
            now,
            data.get('referralName', data.get('referral_name')),
            data.get('referralEmail', data.get('referral_email')),
            data.get('linkedinUrl', data.get('linkedin_url')),
            data.get('instagramHandle', data.get('instagram_handle')),
            data.get('websiteUrl', data.get('website_url')),
            data.get('notes'),
            data.get('termsAcceptedAt', data.get('terms_accepted_at')),
            data.get('privacyAcceptedAt', data.get('privacy_accepted_at')),
            now,
            now,
        ))
        conn.commit()

    logger.info(f"[CRM] Created customer {customer_number}: {email}")
    _db_log('info', f'Created customer {customer_number}', {'email': email})

    # Calculate initial score
    try:
        recalculate_score(customer_id)
    except Exception as e:
        logger.error(f"[CRM] Failed to calculate initial score: {e}")
        _db_log('error', 'Failed to calculate initial score', {'customer_id': customer_id, 'error': str(e)})

    return {
        'id': customer_id,
        'customerNumber': customer_number,
        'email': email,
    }


def log_activity(customer_id, activity_type, **kwargs):
    """
    Log a customer activity. Called by other modules.

    Args:
        customer_id: UUID of the customer
        activity_type: One of GAME_PLAYED, PRODUCT_USED, WEBSITE_VISIT,
                       APP_INTERACTION, FREE_CONTENT, ENQUIRY, SIGNUP
        **kwargs: Optional fields - source, channel, product_ref, product_model,
                  product_name, product_category, platform, group_type, audience,
                  location, region, country, team_name, event_date, metadata
    """
    init_crm_tables()
    db_path = get_db_config()
    activity_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # Convert metadata dict to JSON string
    metadata = kwargs.get('metadata')
    if metadata and isinstance(metadata, dict):
        metadata = json.dumps(metadata)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO customer_activities (
                id, customer_id, type, source, channel,
                product_ref, product_model, product_name, product_category,
                platform, group_type, audience,
                location, region, country, team_name, event_date,
                metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            activity_id, customer_id, activity_type,
            kwargs.get('source'), kwargs.get('channel'),
            kwargs.get('product_ref'), kwargs.get('product_model'),
            kwargs.get('product_name'), kwargs.get('product_category'),
            kwargs.get('platform'), kwargs.get('group_type'),
            kwargs.get('audience'), kwargs.get('location'),
            kwargs.get('region'), kwargs.get('country'),
            kwargs.get('team_name'), kwargs.get('event_date'),
            metadata, now,
        ))

        # Update last_activity_at on the customer
        cursor.execute(
            'UPDATE customers SET last_activity_at = ?, updated_at = ? WHERE id = ?',
            (now, now, customer_id)
        )
        conn.commit()

    logger.info(f"[CRM] Logged activity {activity_type} for {customer_id}")
    return activity_id


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@crm_bp.route('/dashboard', methods=['GET'])
@admin_required
def dashboard():
    """Dashboard overview stats."""
    init_crm_tables()
    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Total customers
            cursor.execute('SELECT COUNT(*) FROM customers')
            total = cursor.fetchone()[0]

            # Active customers
            cursor.execute("SELECT COUNT(*) FROM customers WHERE status = 'ACTIVE'")
            active = cursor.fetchone()[0]

            # Unsubscribed
            cursor.execute("SELECT COUNT(*) FROM customers WHERE status = 'UNSUBSCRIBED'")
            unsubscribed = cursor.fetchone()[0]

            # Bounced
            cursor.execute("SELECT COUNT(*) FROM customers WHERE status = 'BOUNCED'")
            bounced = cursor.fetchone()[0]

            # Average score
            cursor.execute('SELECT AVG(score) FROM customer_scores')
            avg_score_row = cursor.fetchone()
            avg_score = round(avg_score_row[0], 1) if avg_score_row[0] is not None else 0

            # Top 5 customers by score
            cursor.execute('''
                SELECT c.id, c.customer_number, c.first_name, c.last_name, c.email,
                       cs.score
                FROM customers c
                LEFT JOIN customer_scores cs ON cs.customer_id = c.id
                ORDER BY cs.score DESC
                LIMIT 5
            ''')
            top_customers = []
            for row in cursor.fetchall():
                top_customers.append({
                    'id': row[0],
                    'customerNumber': row[1],
                    'firstName': row[2],
                    'lastName': row[3],
                    'email': row[4],
                    'score': row[5] or 0,
                })

            # Recent activity count (last 30 days)
            thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
            cursor.execute(
                'SELECT COUNT(*) FROM customer_activities WHERE created_at > ?',
                (thirty_days_ago,)
            )
            recent_activities = cursor.fetchone()[0]

            # New customers this month
            month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0).isoformat()
            cursor.execute(
                'SELECT COUNT(*) FROM customers WHERE created_at >= ?',
                (month_start,)
            )
            new_this_month = cursor.fetchone()[0]

            return jsonify({
                'total': total,
                'active': active,
                'unsubscribed': unsubscribed,
                'bounced': bounced,
                'avgScore': avg_score,
                'topCustomers': top_customers,
                'recentActivities': recent_activities,
                'newThisMonth': new_this_month,
            }), 200

    except sqlite3.Error as e:
        logger.error(f"[CRM] Database error in dashboard: {e}")
        _db_log('error', 'Database error in dashboard', {'error': str(e)})
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"[CRM] Error in dashboard: {e}")
        _db_log('error', 'Error in dashboard', {'error': str(e)})
        return jsonify({'error': 'An unexpected error occurred'}), 500


@crm_bp.route('/customers', methods=['GET'])
@admin_required
def list_customers():
    """Paginated customer list with search, filters, and sorting."""
    init_crm_tables()
    try:
        db_path = get_db_config()

        # Query params
        search = request.args.get('search', '').strip()
        status = request.args.get('status', '').strip()
        min_score = request.args.get('min_score', type=int)
        max_score = request.args.get('max_score', type=int)
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc').upper()

        # Validate sort
        allowed_sort = {
            'created_at', 'updated_at', 'first_name', 'last_name',
            'email', 'customer_number', 'total_spent', 'total_bookings',
            'last_activity_at', 'score',
        }
        if sort_by not in allowed_sort:
            sort_by = 'created_at'
        if sort_order not in ('ASC', 'DESC'):
            sort_order = 'DESC'

        # Clamp pagination
        page = max(1, page)
        limit = max(1, min(200, limit))
        offset = (page - 1) * limit

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Build query
            where_clauses = []
            params = []

            if search:
                where_clauses.append('''(
                    c.email LIKE ? OR c.first_name LIKE ? OR c.last_name LIKE ?
                    OR c.company LIKE ? OR c.customer_number LIKE ?
                )''')
                like = f'%{search}%'
                params.extend([like, like, like, like, like])

            if status:
                where_clauses.append('c.status = ?')
                params.append(status)

            if min_score is not None:
                where_clauses.append('COALESCE(cs.score, 0) >= ?')
                params.append(min_score)

            if max_score is not None:
                where_clauses.append('COALESCE(cs.score, 0) <= ?')
                params.append(max_score)

            where_sql = ''
            if where_clauses:
                where_sql = 'WHERE ' + ' AND '.join(where_clauses)

            # Sort column
            if sort_by == 'score':
                order_col = 'COALESCE(cs.score, 0)'
            else:
                order_col = f'c.{sort_by}'

            # Count total
            count_sql = f'''
                SELECT COUNT(*) FROM customers c
                LEFT JOIN customer_scores cs ON cs.customer_id = c.id
                {where_sql}
            '''
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]

            # Fetch page
            data_sql = f'''
                SELECT c.*, COALESCE(cs.score, 0) as score
                FROM customers c
                LEFT JOIN customer_scores cs ON cs.customer_id = c.id
                {where_sql}
                ORDER BY {order_col} {sort_order}
                LIMIT ? OFFSET ?
            '''
            cursor.execute(data_sql, params + [limit, offset])

            # Get column names from cursor description
            col_names = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            customers = []
            for row in rows:
                d = {}
                for i, col in enumerate(col_names):
                    key = _snake_to_camel(col)
                    val = row[i]
                    if col == 'marketing_opt_in':
                        val = bool(val) if val is not None else False
                    d[key] = val
                customers.append(d)

            return jsonify({
                'customers': customers,
                'total': total,
                'page': page,
                'limit': limit,
                'totalPages': (total + limit - 1) // limit if limit > 0 else 0,
            }), 200

    except sqlite3.Error as e:
        logger.error(f"[CRM] Database error in list_customers: {e}")
        _db_log('error', 'Database error in list_customers', {'error': str(e)})
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"[CRM] Error in list_customers: {e}")
        _db_log('error', 'Error in list_customers', {'error': str(e)})
        return jsonify({'error': 'An unexpected error occurred'}), 500


@crm_bp.route('/customers/<customer_id>', methods=['GET'])
@admin_required
def get_customer(customer_id):
    """Full customer detail with score, activities, preferences, campaign sends."""
    init_crm_tables()
    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Customer
            cursor.execute('SELECT * FROM customers WHERE id = ?', (customer_id,))
            customer = cursor.fetchone()
            if not customer:
                return jsonify({'error': 'Customer not found'}), 404

            col_names = customer.keys()
            result = {}
            for col in col_names:
                key = _snake_to_camel(col)
                val = customer[col]
                if col == 'marketing_opt_in':
                    val = bool(val) if val is not None else False
                result[key] = val

            # Score
            cursor.execute(
                'SELECT score, breakdown, updated_at FROM customer_scores WHERE customer_id = ?',
                (customer_id,)
            )
            score_row = cursor.fetchone()
            if score_row:
                result['score'] = score_row['score']
                try:
                    result['scoreBreakdown'] = json.loads(score_row['breakdown']) if score_row['breakdown'] else {}
                except (json.JSONDecodeError, TypeError):
                    result['scoreBreakdown'] = {}
                result['scoreUpdatedAt'] = score_row['updated_at']
            else:
                result['score'] = 0
                result['scoreBreakdown'] = {}
                result['scoreUpdatedAt'] = None

            # Recent activities (last 20)
            cursor.execute(
                'SELECT * FROM customer_activities WHERE customer_id = ? ORDER BY created_at DESC LIMIT 20',
                (customer_id,)
            )
            activities = []
            for act in cursor.fetchall():
                ad = {}
                for col in act.keys():
                    ad[_snake_to_camel(col)] = act[col]
                activities.append(ad)
            result['recentActivities'] = activities

            # Marketing preferences
            cursor.execute(
                'SELECT preference, opted_in, updated_at FROM marketing_preferences WHERE customer_id = ?',
                (customer_id,)
            )
            prefs = []
            for pref in cursor.fetchall():
                prefs.append({
                    'preference': pref['preference'],
                    'optedIn': bool(pref['opted_in']),
                    'updatedAt': pref['updated_at'],
                })
            result['marketingPreferences'] = prefs

            # Campaign sends (last 20)
            cursor.execute('''
                SELECT cs.*, ca.name as campaign_name, ca.subject as campaign_subject
                FROM campaign_sends cs
                LEFT JOIN campaigns ca ON ca.id = cs.campaign_id
                WHERE cs.customer_id = ?
                ORDER BY cs.sent_at DESC LIMIT 20
            ''', (customer_id,))
            sends = []
            for send in cursor.fetchall():
                sends.append({
                    'id': send['id'],
                    'campaignId': send['campaign_id'],
                    'campaignName': send['campaign_name'],
                    'campaignSubject': send['campaign_subject'],
                    'sentAt': send['sent_at'],
                    'opened': bool(send['opened']),
                    'openedAt': send['opened_at'],
                    'clicked': bool(send['clicked']),
                    'clickedAt': send['clicked_at'],
                })
            result['campaignSends'] = sends

            return jsonify(result), 200

    except sqlite3.Error as e:
        logger.error(f"[CRM] Database error in get_customer: {e}")
        _db_log('error', 'Database error in get_customer', {'error': str(e)})
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"[CRM] Error in get_customer: {e}")
        _db_log('error', 'Error in get_customer', {'error': str(e)})
        return jsonify({'error': 'An unexpected error occurred'}), 500


@crm_bp.route('/customers/<customer_id>', methods=['PUT'])
@admin_required
def update_customer(customer_id):
    """Update allowed customer fields."""
    init_crm_tables()
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Map camelCase input to snake_case columns
        field_map = {
            'firstName': 'first_name',
            'lastName': 'last_name',
            'phone': 'phone',
            'company': 'company',
            'jobTitle': 'job_title',
            'dateOfBirth': 'date_of_birth',
            'country': 'country',
            'region': 'region',
            'source': 'source',
            'status': 'status',
            'marketingOptIn': 'marketing_opt_in',
            'referralName': 'referral_name',
            'referralEmail': 'referral_email',
            'linkedinUrl': 'linkedin_url',
            'instagramHandle': 'instagram_handle',
            'websiteUrl': 'website_url',
            'notes': 'notes',
        }

        updates = []
        values = []
        for camel_key, snake_key in field_map.items():
            if camel_key in data:
                val = data[camel_key]
                # Convert boolean to integer for SQLite
                if camel_key == 'marketingOptIn':
                    val = 1 if val else 0
                # Validate status
                if camel_key == 'status' and val not in ('ACTIVE', 'UNSUBSCRIBED', 'BOUNCED'):
                    return jsonify({'error': f'Invalid status: {val}'}), 400
                updates.append(f'{snake_key} = ?')
                values.append(val)

        if not updates:
            return jsonify({'error': 'No valid fields to update'}), 400

        updates.append('updated_at = ?')
        values.append(datetime.utcnow().isoformat())
        values.append(customer_id)

        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Check exists
            cursor.execute('SELECT id FROM customers WHERE id = ?', (customer_id,))
            if not cursor.fetchone():
                return jsonify({'error': 'Customer not found'}), 404

            sql = f"UPDATE customers SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(sql, values)
            conn.commit()

        logger.info(f"[CRM] Updated customer {customer_id}")
        _db_log('info', f'Updated customer {customer_id}', {'fields': list(data.keys())})

        # Recalculate score after update (profile fields may have changed)
        try:
            recalculate_score(customer_id)
        except Exception as e:
            logger.error(f"[CRM] Score recalculation failed after update: {e}")

        return jsonify({'message': 'Customer updated'}), 200

    except sqlite3.Error as e:
        logger.error(f"[CRM] Database error in update_customer: {e}")
        _db_log('error', 'Database error in update_customer', {'error': str(e)})
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"[CRM] Error in update_customer: {e}")
        _db_log('error', 'Error in update_customer', {'error': str(e)})
        return jsonify({'error': 'An unexpected error occurred'}), 500


@crm_bp.route('/customers/<customer_id>', methods=['DELETE'])
@admin_required
def delete_customer(customer_id):
    """Delete a customer and all related data."""
    init_crm_tables()
    try:
        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Check exists
            cursor.execute('SELECT email, customer_number FROM customers WHERE id = ?', (customer_id,))
            row = cursor.fetchone()
            if not row:
                return jsonify({'error': 'Customer not found'}), 404

            email, customer_number = row

            # Delete related data in order
            cursor.execute('DELETE FROM subscriber_confirmations WHERE customer_id = ?', (customer_id,))
            cursor.execute('DELETE FROM campaign_sends WHERE customer_id = ?', (customer_id,))
            cursor.execute('DELETE FROM marketing_preferences WHERE customer_id = ?', (customer_id,))
            cursor.execute('DELETE FROM customer_scores WHERE customer_id = ?', (customer_id,))
            cursor.execute('DELETE FROM customer_activities WHERE customer_id = ?', (customer_id,))
            cursor.execute('DELETE FROM customers WHERE id = ?', (customer_id,))
            conn.commit()

        logger.info(f"[CRM] Deleted customer {customer_number} ({email})")
        _db_log('info', f'Deleted customer {customer_number}', {'email': email})

        return jsonify({'message': 'Customer deleted'}), 200

    except sqlite3.Error as e:
        logger.error(f"[CRM] Database error in delete_customer: {e}")
        _db_log('error', 'Database error in delete_customer', {'error': str(e)})
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"[CRM] Error in delete_customer: {e}")
        _db_log('error', 'Error in delete_customer', {'error': str(e)})
        return jsonify({'error': 'An unexpected error occurred'}), 500


@crm_bp.route('/customers/<customer_id>/activities', methods=['GET'])
@admin_required
def list_activities(customer_id):
    """Paginated activity history for a customer."""
    init_crm_tables()
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        page = max(1, page)
        limit = max(1, min(200, limit))
        offset = (page - 1) * limit

        db_path = get_db_config()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Check customer exists
            cursor.execute('SELECT id FROM customers WHERE id = ?', (customer_id,))
            if not cursor.fetchone():
                return jsonify({'error': 'Customer not found'}), 404

            # Count
            cursor.execute(
                'SELECT COUNT(*) FROM customer_activities WHERE customer_id = ?',
                (customer_id,)
            )
            total = cursor.fetchone()[0]

            # Fetch page
            cursor.execute('''
                SELECT * FROM customer_activities
                WHERE customer_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (customer_id, limit, offset))

            col_names = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            activities = []
            for row in rows:
                d = {}
                for i, col in enumerate(col_names):
                    d[_snake_to_camel(col)] = row[i]
                activities.append(d)

            return jsonify({
                'activities': activities,
                'total': total,
                'page': page,
                'limit': limit,
                'totalPages': (total + limit - 1) // limit if limit > 0 else 0,
            }), 200

    except sqlite3.Error as e:
        logger.error(f"[CRM] Database error in list_activities: {e}")
        _db_log('error', 'Database error in list_activities', {'error': str(e)})
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"[CRM] Error in list_activities: {e}")
        _db_log('error', 'Error in list_activities', {'error': str(e)})
        return jsonify({'error': 'An unexpected error occurred'}), 500


@crm_bp.route('/customers/<customer_id>/recalculate', methods=['POST'])
@admin_required
def recalculate_customer_score(customer_id):
    """Force recalculation of a customer's score."""
    init_crm_tables()
    try:
        result = recalculate_score(customer_id)
        if result is None:
            return jsonify({'error': 'Customer not found'}), 404

        return jsonify(result), 200

    except sqlite3.Error as e:
        logger.error(f"[CRM] Database error in recalculate: {e}")
        _db_log('error', 'Database error in recalculate', {'error': str(e)})
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"[CRM] Error in recalculate: {e}")
        _db_log('error', 'Error in recalculate', {'error': str(e)})
        return jsonify({'error': 'An unexpected error occurred'}), 500
