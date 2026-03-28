from flask import Blueprint, jsonify, render_template, request, session, redirect, url_for, send_from_directory, make_response, current_app
import sqlite3
import os
from datetime import datetime, timedelta
import json
from lozzalingo.core import logger
from .analytics import get_analytics_db, get_analytics_table


_template_dir = os.path.join(os.path.dirname(__file__), 'templates')
_static_dir = os.path.join(os.path.dirname(__file__), 'static')

analytics_bp = Blueprint('analytics', __name__,
                        url_prefix='/admin/analytics',
                        template_folder=_template_dir,
                        static_folder=_static_dir)


def _get_news_db():
    """Get news DB path at request time (3-tier resolution)."""
    try:
        val = current_app.config.get('NEWS_DB')
        if val:
            return val
    except RuntimeError:
        pass
    try:
        from lozzalingo.core import Config
        if hasattr(Config, 'NEWS_DB'):
            return Config.NEWS_DB
    except ImportError:
        pass
    return os.getenv('NEWS_DB', 'news.db')


def _get_users_db():
    """Get users DB path at request time (3-tier resolution)."""
    try:
        val = current_app.config.get('USER_DB')
        if val:
            return val
    except RuntimeError:
        pass
    try:
        from lozzalingo.core import Config
        if hasattr(Config, 'USER_DB'):
            return Config.USER_DB
    except ImportError:
        pass
    return os.getenv('USER_DB', 'users.db')


def _get_merchandise_db():
    """Get merchandise DB path at request time (3-tier resolution)."""
    try:
        val = current_app.config.get('MERCHANDISE')
        if val:
            return val
    except RuntimeError:
        pass
    try:
        from lozzalingo.core import Config
        if hasattr(Config, 'MERCHANDISE'):
            return Config.MERCHANDISE
    except ImportError:
        pass
    return os.getenv('MERCHANDISE_DB', 'merchandise.db')

def _owner_fingerprint_filter():
    """SQL fragment to exclude owner/admin fingerprints from analytics queries."""
    try:
        exclude = current_app.config.get('ANALYTICS_EXCLUDE_FINGERPRINTS', [])
    except RuntimeError:
        return ''
    if not exclude:
        return ''
    safe = [h for h in exclude if h and all(c in '0123456789abcdef' for c in h)]
    if not safe:
        return ''
    placeholders = ','.join(f"'{h}'" for h in safe)
    return f"\n                AND (fingerprint_hash IS NULL OR fingerprint_hash NOT IN ({placeholders}))"


def check_admin_access():
    """Check if user is logged in and is an admin"""
    if 'admin_id' not in session:
        return False, "Not logged in as admin"
    return True, "Admin access granted"

def get_cutoff_date(days_param='7'):
    """Get cutoff date based on days parameter, supporting 'all' for all time"""
    if days_param == 'all':
        return datetime(2000, 1, 1)  # Far past date for "all time"
    else:
        try:
            days = int(days_param)
            return datetime.now() - timedelta(days=days)
        except (ValueError, TypeError):
            return datetime.now() - timedelta(days=7)  # Default to 7 days

def add_no_cache_headers(response):
    """Add headers to prevent browser caching of analytics data"""
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


_last_bot_reclassification = None

def _reclassify_stealth_bots():
    """Reclassify visitors that look human but behave like bots.

    Real browsers execute JS and fire page_exit/route_change/click events.
    Crawlers that render JS may trigger page_view_client but never produce
    interactive events. Fingerprints with only page_view_client events
    (and no page_exit, route_change, or click events) are reclassified as bots.

    Runs at most once per hour to avoid unnecessary DB writes.
    """
    global _last_bot_reclassification
    now = datetime.now()
    if _last_bot_reclassification and (now - _last_bot_reclassification).total_seconds() < 3600:
        return

    try:
        conn = get_db_connection(get_analytics_db())
        if not conn:
            return
        cursor = conn.cursor()

        # Find fingerprints classified as human that have page_view_client events
        # but zero interactive events (page_exit, route_change, button/link clicks)
        cursor.execute("""
            UPDATE analytics_log
            SET identity = 'bot'
            WHERE identity IN ('human', 'likely_human', 'possible_human')
            AND fingerprint_hash IS NOT NULL
            AND fingerprint_hash IN (
                SELECT fingerprint_hash
                FROM analytics_log
                WHERE fingerprint_hash IS NOT NULL
                GROUP BY fingerprint_hash
                HAVING
                    COUNT(CASE WHEN event_type = 'page_view_client' THEN 1 END) > 0
                    AND COUNT(CASE WHEN event_type IN (
                        'page_exit', 'route_change',
                        'internal_link_click'
                    ) OR event_type LIKE 'button_click_%'
                       OR event_type LIKE 'link_click_%'
                    THEN 1 END) = 0
            )
        """)
        reclassified = cursor.rowcount
        conn.commit()
        conn.close()

        if reclassified > 0:
            print(f"[Analytics] Reclassified {reclassified} stealth bot events")

        _last_bot_reclassification = now
    except Exception as e:
        print(f"[Analytics] Bot reclassification error: {e}")


def get_allowed_origins():
    """
    Get allowed origins for analytics API requests.

    Priority:
    1. ANALYTICS_ALLOWED_ORIGINS from app config (list)
    2. Dynamic: allow the current request's origin
    3. Always include localhost variants for development
    """
    allowed = set()

    # Always allow localhost for development
    allowed.add('http://localhost:5000')
    allowed.add('http://localhost:5001')
    allowed.add('http://127.0.0.1:5000')
    allowed.add('http://127.0.0.1:5001')

    # Check for configured origins
    if current_app.config.get('ANALYTICS_ALLOWED_ORIGINS'):
        configured = current_app.config['ANALYTICS_ALLOWED_ORIGINS']
        if isinstance(configured, list):
            allowed.update(configured)
        elif isinstance(configured, str):
            allowed.add(configured)

    # Dynamically allow the request's origin (makes development easy)
    origin = request.headers.get('Origin')
    if origin:
        allowed.add(origin)

    # Also allow based on Host header (for same-origin requests)
    host = request.headers.get('Host')
    if host:
        # Add both http and https variants
        if not host.startswith('http'):
            allowed.add(f'http://{host}')
            allowed.add(f'https://{host}')

    return list(allowed)


def is_valid_analytics_origin():
    """
    Check if the current request comes from a valid origin.

    Returns: (is_valid: bool, reason: str)
    """
    origin = request.headers.get('Origin')
    referer = request.headers.get('Referer')
    host = request.headers.get('Host')

    allowed_origins = get_allowed_origins()

    # Check origin header
    if origin and origin in allowed_origins:
        return True, "Valid origin"

    # Check referer header
    if referer:
        for allowed in allowed_origins:
            if referer.startswith(allowed):
                return True, "Valid referer"

    # Allow requests without origin/referer from localhost
    if not origin and not referer:
        if host and ('localhost' in host or '127.0.0.1' in host):
            return True, "Localhost request"

    return False, f"Invalid origin: {origin}"

def get_db_connection(db_path, init_if_missing=False):
    """Get database connection with error handling"""
    try:
        if not os.path.exists(db_path):
            if init_if_missing and db_path == get_analytics_db():
                # Initialize analytics database
                try:
                    from lozzalingo.modules.analytics.analytics import Analytics
                    Analytics.init_analytics_db()
                except Exception as e:
                    print(f"Could not initialize analytics DB: {e}")
                    return None
            else:
                return None
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Database connection error for {db_path}: {e}")
        return None

def normalize_page_url(raw_url):
    """Normalize URLs for analytics by removing tracking parameters and standardizing"""
    try:
        from urllib.parse import urlparse, parse_qs, urlunparse

        parsed = urlparse(raw_url)

        # Remove tracking parameters
        query_params = parse_qs(parsed.query)
        # Remove Facebook click ID, Google Analytics, etc.
        tracking_params = ['fbclid', 'gclid', 'utm_source', 'utm_medium', 'utm_campaign',
                          'utm_term', 'utm_content', '_ga', '_gid', 'ref']

        for param in tracking_params:
            query_params.pop(param, None)

        # Rebuild query string
        clean_query = '&'.join([f"{k}={v[0]}" for k, v in query_params.items() if v])

        # Normalize domain (remove www.)
        hostname = parsed.hostname
        if hostname and hostname.startswith('www.'):
            hostname = hostname[4:]

        # Rebuild URL
        if hostname:
            # For full URLs, return clean version
            scheme = parsed.scheme or 'https'
            clean_url = f"{scheme}://{hostname}{parsed.path}"
            if clean_query:
                clean_url += f"?{clean_query}"
            if parsed.fragment:
                clean_url += f"#{parsed.fragment}"
            return clean_url
        else:
            # For relative URLs, just clean the path
            clean_path = parsed.path
            if clean_query:
                clean_path += f"?{clean_query}"
            if parsed.fragment:
                clean_path += f"#{parsed.fragment}"
            return clean_path

    except Exception as e:
        # If parsing fails, return original URL
        print(f"URL normalization error for {raw_url}: {e}")
        return raw_url

@analytics_bp.route('/')
def dashboard():
    """Main analytics dashboard route"""
    is_admin, message = check_admin_access()

    if not is_admin:
        auth_bp_name = current_app.config.get('LOZZALINGO_AUTH_BLUEPRINT_NAME', 'auth')
        return redirect(url_for(f'{auth_bp_name}.login'))

    # Log analytics access
    admin_email = session.get('admin_email', 'Unknown')
    logger.info('analytics', f'Analytics dashboard accessed by {admin_email}',
               user_id=str(session.get('admin_id')))

    auth_bp_name = current_app.config.get('LOZZALINGO_AUTH_BLUEPRINT_NAME', 'auth')
    return render_template('analytics.html', auth_bp_name=auth_bp_name)

@analytics_bp.route('/api/overview-stats')
def get_overview_stats():
    """Get overview statistics"""
    is_admin, message = check_admin_access()
    if not is_admin:
        return jsonify({"error": message}), 403

    # Reclassify stealth bots before returning stats (runs at most once/hour)
    _reclassify_stealth_bots()

    days_param = request.args.get('days', '7')
    cutoff_date = get_cutoff_date(days_param)

    stats = {}

    # Analytics data
    conn = get_db_connection(get_analytics_db())
    if conn:
        try:
            cursor = conn.cursor()
            
            # Filter out only truly invalid IPs (keep development IPs for testing)
            # Filter out localhost, Docker, and private network IPs (RFC 1918)
            # 172.16-31.* is private, but 172.32+.* are real IPs (T-Mobile, Google, etc.)
            local_ip_filter = """
                AND ip IS NOT NULL
                AND ip NOT IN ('127.0.0.1', '::1', 'localhost', '')
                AND ip NOT LIKE '192.168.%'
                AND ip NOT LIKE '10.%'
                AND ip NOT LIKE '172.16.%'
                AND ip NOT LIKE '172.17.%'
                AND ip NOT LIKE '172.18.%'
                AND ip NOT LIKE '172.19.%'
                AND ip NOT LIKE '172.2_.%'
                AND ip NOT LIKE '172.30.%'
                AND ip NOT LIKE '172.31.%'
            """ + _owner_fingerprint_filter()

            # Total page views (only count page_view_client events, exclude localhost and bots)
            cursor.execute(f"SELECT COUNT(*) FROM analytics_log WHERE event_type = 'page_view_client' AND identity != 'bot' {local_ip_filter}")
            stats['total_page_views'] = cursor.fetchone()[0]

            # Recent page views (only count page_view_client events, exclude localhost and bots)
            cursor.execute(f"SELECT COUNT(*) FROM analytics_log WHERE event_type = 'page_view_client' AND identity != 'bot' AND datetime(timestamp) >= ? {local_ip_filter}", (cutoff_date,))
            stats['recent_page_views'] = cursor.fetchone()[0]

            # Unique human visitors (by fingerprint, only humans with page views, exclude localhost)
            cursor.execute(f"SELECT COUNT(DISTINCT fingerprint) FROM analytics_log WHERE event_type = 'page_view_client' AND fingerprint IS NOT NULL AND identity = 'human' AND datetime(timestamp) >= ? {local_ip_filter}", (cutoff_date,))
            stats['unique_visitors'] = cursor.fetchone()[0]

            # Human vs Bot breakdown (total page views per identity type)
            cursor.execute(f"SELECT identity, COUNT(*) FROM analytics_log WHERE event_type = 'page_view_client' AND identity IS NOT NULL AND datetime(timestamp) >= ? {local_ip_filter} GROUP BY identity", (cutoff_date,))
            identity_breakdown = dict(cursor.fetchall())
            stats['identity_breakdown'] = identity_breakdown

            # All analytics queries below use the same filter: human visitors only,
            # counted by unique fingerprint (not page views) for consistency with
            # the Unique Visitors / Human Visitors overview stats.

            # Top countries (unique human visitors per country)
            cursor.execute(f"""
                SELECT country, COUNT(DISTINCT fingerprint) as count
                FROM analytics_log
                WHERE event_type = 'page_view_client' AND country IS NOT NULL AND country != ''
                AND country NOT IN ('Local', 'Unknown')
                AND identity = 'human' AND fingerprint IS NOT NULL
                AND datetime(timestamp) >= ? {local_ip_filter}
                GROUP BY country
                ORDER BY count DESC
                LIMIT 10
            """, (cutoff_date,))
            stats['top_countries'] = [(row[0], row[1]) for row in cursor.fetchall()]

            # Device types (unique human visitors per device type)
            cursor.execute(f"""
                SELECT device_type, COUNT(DISTINCT fingerprint) as count
                FROM analytics_log
                WHERE event_type = 'page_view_client' AND device_type IS NOT NULL AND device_type != ''
                AND identity = 'human' AND fingerprint IS NOT NULL
                AND datetime(timestamp) >= ? {local_ip_filter}
                GROUP BY device_type
            """, (cutoff_date,))
            stats['device_types'] = dict(cursor.fetchall())

            # Top device brands (unique human visitors per brand)
            cursor.execute(f"""
                SELECT device_brand, COUNT(DISTINCT fingerprint) as count
                FROM analytics_log
                WHERE event_type = 'page_view_client' AND device_brand IS NOT NULL AND device_brand != ''
                AND identity = 'human' AND fingerprint IS NOT NULL
                AND datetime(timestamp) >= ? {local_ip_filter}
                GROUP BY device_brand
            """, (cutoff_date,))
            brand_results = cursor.fetchall()
            # Sort by count and convert to dict
            brand_results_sorted = sorted(brand_results, key=lambda x: x[1], reverse=True)[:10]
            stats['device_brands'] = dict(brand_results_sorted)

            # Top device OS (unique human visitors per OS)
            cursor.execute(f"""
                SELECT device_os, COUNT(DISTINCT fingerprint) as count
                FROM analytics_log
                WHERE event_type = 'page_view_client' AND device_os IS NOT NULL AND device_os != ''
                AND identity = 'human' AND fingerprint IS NOT NULL
                AND datetime(timestamp) >= ? {local_ip_filter}
                GROUP BY device_os
            """, (cutoff_date,))
            os_results = cursor.fetchall()
            # Sort by count and convert to dict
            os_results_sorted = sorted(os_results, key=lambda x: x[1], reverse=True)[:10]
            stats['device_os'] = dict(os_results_sorted)

            # Average device confidence (exclude localhost)
            cursor.execute(f"""
                SELECT AVG(CAST(device_confidence AS REAL)) as avg_confidence
                FROM analytics_log
                WHERE event_type = 'page_view_client' AND device_confidence IS NOT NULL AND device_confidence != '' {local_ip_filter}
            """)
            result = cursor.fetchone()
            stats['avg_device_confidence'] = round(result[0], 1) if result and result[0] else 0
            
        except Exception as e:
            print(f"Error getting analytics stats: {e}")
        finally:
            conn.close()
    
    # Subscribers data
    conn = get_db_connection(_get_users_db())
    if conn:
        try:
            cursor = conn.cursor()
            
            # Total subscribers (active only)
            cursor.execute("SELECT COUNT(*) FROM subscribers WHERE is_active = 1")
            stats['total_subscribers'] = cursor.fetchone()[0]
            
            # Active subscribers
            cursor.execute("SELECT COUNT(*) FROM subscribers WHERE is_active = 1")
            stats['active_subscribers'] = cursor.fetchone()[0]
            
            # Recent subscribers
            cursor.execute("SELECT COUNT(*) FROM subscribers WHERE datetime(subscribed_at) >= ?", (cutoff_date,))
            stats['recent_subscribers'] = cursor.fetchone()[0]
            
            # Subscription sources
            cursor.execute("""
                SELECT source, COUNT(*) as count 
                FROM subscribers 
                WHERE source IS NOT NULL 
                GROUP BY source
            """)
            stats['subscription_sources'] = dict(cursor.fetchall())
            
        except Exception as e:
            print(f"Error getting subscriber stats: {e}")
        finally:
            conn.close()
    
    # News data
    conn = get_db_connection(_get_news_db())
    if conn:
        try:
            cursor = conn.cursor()
            
            # Total articles
            cursor.execute("SELECT COUNT(*) FROM news_articles")
            stats['total_articles'] = cursor.fetchone()[0]
            
            # Recent articles
            cursor.execute("SELECT COUNT(*) FROM news_articles WHERE datetime(created_at) >= ?", (cutoff_date,))
            stats['recent_articles'] = cursor.fetchone()[0]
            
        except Exception as e:
            print(f"Error getting news stats: {e}")
        finally:
            conn.close()

    # Session analytics (back to analytics DB)
    conn = get_db_connection(get_analytics_db())
    if conn:
        try:
            cursor = conn.cursor()

            # Filter out only truly invalid IPs (keep development IPs for testing)
            # Filter out localhost, Docker, and private network IPs (RFC 1918)
            # 172.16-31.* is private, but 172.32+.* are real IPs (T-Mobile, Google, etc.)
            local_ip_filter = """
                AND ip IS NOT NULL
                AND ip NOT IN ('127.0.0.1', '::1', 'localhost', '')
                AND ip NOT LIKE '192.168.%'
                AND ip NOT LIKE '10.%'
                AND ip NOT LIKE '172.16.%'
                AND ip NOT LIKE '172.17.%'
                AND ip NOT LIKE '172.18.%'
                AND ip NOT LIKE '172.19.%'
                AND ip NOT LIKE '172.2_.%'
                AND ip NOT LIKE '172.30.%'
                AND ip NOT LIKE '172.31.%'
            """ + _owner_fingerprint_filter()

            # Average pages per session (exclude localhost)
            cursor.execute(f"""
                SELECT AVG(CAST(session_page_count AS REAL)) as avg_pages_per_session
                FROM analytics_log
                WHERE event_type = 'page_view_client'
                AND session_page_count IS NOT NULL AND session_page_count != ''
                AND datetime(timestamp) >= ? {local_ip_filter}
            """, (cutoff_date,))

            session_data = cursor.fetchone()
            stats['avg_pages_per_session'] = round(session_data[0], 1) if session_data and session_data[0] else 0

            # Average session time (use all events with time data, exclude localhost)
            cursor.execute(f"""
                SELECT AVG(CAST(time_spent_seconds AS REAL)) as avg_session_time,
                       COUNT(*) as count_with_time
                FROM analytics_log
                WHERE time_spent_seconds IS NOT NULL
                AND time_spent_seconds != ''
                AND CAST(time_spent_seconds AS REAL) > 0
                AND event_type IN ('page_exit', 'route_change') {local_ip_filter}
            """)

            time_data = cursor.fetchone()
            stats['avg_session_time'] = round(time_data[0], 1) if time_data and time_data[0] else 0
            stats['debug_time_count'] = time_data[1] if time_data else 0

        except Exception as e:
            print(f"Error getting session stats: {e}")
        finally:
            conn.close()

    response = make_response(jsonify(stats))
    return add_no_cache_headers(response)

@analytics_bp.route('/api/traffic-timeline')
def get_traffic_timeline():
    """Get traffic timeline data"""
    is_admin, message = check_admin_access()
    if not is_admin:
        return jsonify({"error": message}), 403
    
    days = request.args.get('days', 7, type=int)
    
    conn = get_db_connection(get_analytics_db())
    if not conn:
        # Return empty data instead of error for fresh installs
        response = make_response(jsonify({'timeline': []}))
        return add_no_cache_headers(response)

    try:
        cursor = conn.cursor()

        # Filter out localhost and private IP addresses
        local_ip_filter = """
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
        """ + _owner_fingerprint_filter()

        cursor.execute(f"""
            SELECT DATE(timestamp) as date, COUNT(*) as views,
                   COUNT(DISTINCT CASE WHEN identity = 'human' THEN fingerprint END) as unique_visitors
            FROM analytics_log
            WHERE event_type = 'page_view_client' AND identity != 'bot' AND datetime(timestamp) >= datetime('now', '-{days} days') {local_ip_filter}
            GROUP BY DATE(timestamp)
            ORDER BY date
        """)

        timeline_data = []
        for row in cursor.fetchall():
            timeline_data.append({
                'date': row[0],
                'views': row[1],
                'unique_visitors': row[2]
            })

        response = make_response(jsonify({'timeline': timeline_data}))
        return add_no_cache_headers(response)

    except Exception as e:
        # Return empty data on error
        response = make_response(jsonify({'timeline': [], 'error': str(e)}))
        return add_no_cache_headers(response)
    finally:
        conn.close()

@analytics_bp.route('/api/recent-activity')
def get_recent_activity():
    """Get recent activity events"""
    is_admin, message = check_admin_access()
    if not is_admin:
        return jsonify({"error": message}), 403
    
    limit = request.args.get('limit', 20, type=int)
    
    conn = get_db_connection(get_analytics_db())
    if not conn:
        response = make_response(jsonify({'activities': []}))
        return add_no_cache_headers(response)

    try:
        cursor = conn.cursor()

        # For recent activity, show all IPs including local ones for development visibility
        # Only filter out completely invalid entries
        basic_filter = """
            AND ip IS NOT NULL
            AND ip != ''
        """ + _owner_fingerprint_filter()

        cursor.execute(f"""
            SELECT timestamp, event_type, country, city, identity,
                   interaction_type, device_type, device_brand, device_os,
                   device_confidence, url, from_route, to_route,
                   time_spent_seconds, session_page_count
            FROM analytics_log
            WHERE 1=1 {basic_filter}
            ORDER BY datetime(timestamp) DESC
            LIMIT ?
        """, (limit,))

        activities = []
        for row in cursor.fetchall():
            activities.append({
                'timestamp': row[0],
                'event_type': row[1] or 'Unknown',
                'location': f"{row[2]}, {row[3]}" if row[2] and row[3] else (row[2] or 'Unknown'),
                'identity': row[4] or 'Unknown',
                'email': 'Anonymous',  # Email not stored in analytics_log
                'interaction_type': row[5] or 'N/A',
                'device_type': row[6] or 'Unknown',
                'device_brand': row[7] or 'Unknown',
                'device_os': row[8] or 'Unknown',
                'device_confidence': row[9] or 'Unknown',
                'url': row[10] or 'N/A',
                'from_route': row[11] or 'N/A',
                'to_route': row[12] or 'N/A',
                'time_spent_seconds': row[13] or 'N/A',
                'session_page_count': row[14] or 'N/A'
            })

        response = make_response(jsonify({'activities': activities}))
        return add_no_cache_headers(response)

    except Exception as e:
        response = make_response(jsonify({'activities': [], 'error': str(e)}))
        return add_no_cache_headers(response)
    finally:
        conn.close()

@analytics_bp.route('/api/subscriber-details')
def get_subscriber_details():
    """Get detailed subscriber information"""
    is_admin, message = check_admin_access()
    if not is_admin:
        return jsonify({"error": message}), 403
    
    days = request.args.get('days', 7, type=int)
    limit = request.args.get('limit', 10, type=int)
    
    conn = get_db_connection(_get_users_db())
    if not conn:
        return jsonify({'recent_subscribers': [], 'subscription_trend': []})

    try:
        cursor = conn.cursor()

        # Recent subscribers
        cursor.execute("""
            SELECT email, subscribed_at, is_active, source, ip_address, is_confirmed
            FROM subscribers
            ORDER BY datetime(subscribed_at) DESC
            LIMIT ?
        """, (limit,))

        recent_subscribers = []
        for row in cursor.fetchall():
            recent_subscribers.append({
                'email': row[0],
                'subscribed_at': row[1],
                'is_active': bool(row[2]),
                'source': row[3] or 'Unknown',
                'ip_address': row[4] or 'Unknown',
                'is_confirmed': bool(row[5]) if row[5] is not None else True
            })
        
        # Subscription trend
        cutoff_date = datetime.now() - timedelta(days=days)
        cursor.execute("""
            SELECT DATE(subscribed_at) as date, COUNT(*) as count
            FROM subscribers 
            WHERE datetime(subscribed_at) >= ?
            GROUP BY DATE(subscribed_at)
            ORDER BY date
        """, (cutoff_date,))
        
        subscription_trend = []
        for row in cursor.fetchall():
            subscription_trend.append({
                'date': row[0],
                'count': row[1]
            })
        
        return jsonify({
            'recent_subscribers': recent_subscribers,
            'subscription_trend': subscription_trend
        })

    except Exception as e:
        print(f"Subscriber data error: {e}")
        return jsonify({'recent_subscribers': [], 'subscription_trend': []})
    finally:
        conn.close()

@analytics_bp.route('/api/news-metrics')
def get_news_metrics():
    """Get news article metrics"""
    is_admin, message = check_admin_access()
    if not is_admin:
        return jsonify({"error": message}), 403
    
    days = request.args.get('days', 7, type=int)
    limit = request.args.get('limit', 10, type=int)
    
    conn = get_db_connection(_get_news_db())
    if not conn:
        return jsonify({'recent_articles': [], 'publishing_trend': []})

    try:
        cursor = conn.cursor()

        # Recent articles
        cursor.execute("""
            SELECT id, title, created_at, LENGTH(content) as content_length, slug
            FROM news_articles
            ORDER BY datetime(created_at) DESC
            LIMIT ?
        """, (limit,))

        recent_articles = []
        for row in cursor.fetchall():
            recent_articles.append({
                'id': row[0],
                'title': row[1],
                'created_at': row[2],
                'content_length': row[3],
                'slug': row[4] if len(row) > 4 else None
            })

        # Cross-reference with analytics to get view counts per article
        article_slugs = [a['slug'] for a in recent_articles if a.get('slug')]
        article_views = {}
        if article_slugs:
            try:
                analytics_conn = get_db_connection(get_analytics_db())
                if analytics_conn:
                    analytics_cursor = analytics_conn.cursor()
                    analytics_table = get_analytics_table()
                    # Match URLs containing the article slug (newsletter/<slug>)
                    like_clauses = ' OR '.join(['url LIKE ?' for _ in article_slugs])
                    like_params = [f'%/newsletter/{slug}%' for slug in article_slugs]
                    analytics_cursor.execute(f"""
                        SELECT url, COUNT(*) as views
                        FROM {analytics_table}
                        WHERE event_type = 'page_view_client'
                        AND identity != 'bot'
                        AND ({like_clauses})
                        GROUP BY url
                    """, like_params)
                    for row in analytics_cursor.fetchall():
                        for slug in article_slugs:
                            if f'/newsletter/{slug}' in row[0]:
                                article_views[slug] = article_views.get(slug, 0) + row[1]
                    analytics_conn.close()
            except Exception as e:
                print(f"Error fetching article views: {e}")

        for article in recent_articles:
            article['views'] = article_views.get(article.get('slug'), 0)
        
        # Publishing trend
        cutoff_date = datetime.now() - timedelta(days=days)
        cursor.execute("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM news_articles 
            WHERE datetime(created_at) >= ?
            GROUP BY DATE(created_at)
            ORDER BY date
        """, (cutoff_date,))
        
        publishing_trend = []
        for row in cursor.fetchall():
            publishing_trend.append({
                'date': row[0],
                'count': row[1]
            })
        
        return jsonify({
            'recent_articles': recent_articles,
            'publishing_trend': publishing_trend
        })

    except Exception as e:
        print(f"News data error: {e}")
        return jsonify({'recent_articles': [], 'publishing_trend': []})
    finally:
        conn.close()

@analytics_bp.route('/api/geographic-data')
def get_geographic_data():
    """Get detailed geographic analytics"""
    is_admin, message = check_admin_access()
    if not is_admin:
        return jsonify({"error": message}), 403
    
    days = request.args.get('days', 7, type=int)
    
    conn = get_db_connection(get_analytics_db())
    if not conn:
        return jsonify({'geographic_data': []})
    
    try:
        cursor = conn.cursor()
        
        # Check if analytics_log table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='analytics_log'")
        if not cursor.fetchone():
            return jsonify({'geographic_data': []})
        
        # Filter out localhost and private IP addresses
        local_ip_filter = """
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
        """ + _owner_fingerprint_filter()

        # Country and region data (from page views only, exclude localhost and bots)
        cursor.execute(f"""
            SELECT country, region, city, COUNT(*) as visits
            FROM analytics_log
            WHERE event_type = 'page_view_client'
            AND identity != 'bot'
            AND timestamp IS NOT NULL
            AND datetime(timestamp) >= datetime('now', '-{days} days')
            AND country IS NOT NULL AND country != '' {local_ip_filter}
            GROUP BY country, region, city
            ORDER BY visits DESC
            LIMIT 50
        """)
        
        geographic_data = []
        for row in cursor.fetchall():
            geographic_data.append({
                'country': row[0] or 'Unknown',
                'region': row[1] or '',
                'city': row[2] or '',
                'visits': row[3] or 0
            })
        
        return jsonify({'geographic_data': geographic_data})
    
    except Exception as e:
        print(f"Geographic data error: {e}")
        return jsonify({'geographic_data': []})
    finally:
        conn.close()

@analytics_bp.route('/api/log-interaction', methods=['POST'])
def log_interaction():
    """Log user interactions"""
    try:
        # Security: Validate request origin to prevent abuse from external sites
        is_valid_origin, reason = is_valid_analytics_origin()

        if not is_valid_origin:
            logger.warning('analytics', f'Rejected analytics request: {reason}')
            return jsonify({"error": "Invalid origin"}), 403

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Import Analytics class
        from .analytics import Analytics

        # Extract data
        interaction_type = data.get('type', 'unknown')
        device_details = data.get('deviceDetails')
        email = data.get('email')
        additional_data = {k: v for k, v in data.items() if k not in ['type', 'deviceDetails', 'email']}

        # DEBUG: Log what's calling this endpoint
        print(f"[DEBUG] /api/log-interaction called with type: {interaction_type}")
        print(f"[DEBUG] User-Agent: {request.headers.get('User-Agent', 'N/A')}")
        print(f"[DEBUG] Referer: {request.headers.get('Referer', 'N/A')}")

        # Log the interaction
        Analytics.log_comprehensive_analytics(
            request=request,
            event_type=interaction_type,
            email=email,
            fingerprint=device_details,
            interaction_type=interaction_type,
            additional_data=additional_data
        )

        return jsonify({"status": "logged", "type": interaction_type})

    except Exception as e:
        print(f"Error logging interaction: {e}")
        return jsonify({"error": str(e)}), 400

_unnamed_alerts_sent = {}  # {page: last_sent_date} — rate limit to once/day/page

@analytics_bp.route('/api/unnamed-elements', methods=['POST'])
def report_unnamed_elements():
    """Receive reports of unnamed links/buttons and email admin."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "ignored"}), 200

        page = data.get('page', '?')
        elements = data.get('elements', [])
        if not elements:
            return jsonify({"status": "ok"}), 200

        # Rate limit: once per page per day
        today = datetime.now().strftime('%Y-%m-%d')
        cache_key = f"{page}:{today}"
        if cache_key in _unnamed_alerts_sent:
            return jsonify({"status": "already_reported"}), 200
        _unnamed_alerts_sent[cache_key] = True

        # Clean old entries
        for k in list(_unnamed_alerts_sent.keys()):
            if not k.endswith(today):
                del _unnamed_alerts_sent[k]

        admin_email = current_app.config.get('EMAIL_ADMIN_EMAIL', '')
        brand = current_app.config.get('EMAIL_BRAND_NAME', 'Site')
        if not admin_email:
            logger.warning('analytics', f'Unnamed elements on {page} but no admin email configured')
            return jsonify({"status": "no_admin_email"}), 200

        # Build email
        rows = ''
        for el in elements[:30]:  # Cap at 30
            tag = el.get('tag', '?')
            text = el.get('text', '')[:60]
            href = el.get('href', '')[:80]
            classes = el.get('classes', '')[:80]
            rows += f'<tr><td style="padding:6px 10px;border:1px solid #333;">&lt;{tag}&gt;</td>'
            rows += f'<td style="padding:6px 10px;border:1px solid #333;">{text}</td>'
            rows += f'<td style="padding:6px 10px;border:1px solid #333;">{href}</td>'
            rows += f'<td style="padding:6px 10px;border:1px solid #333;">{classes}</td></tr>'

        html = f'''<div style="font-family:monospace;background:#0a0a0f;color:#e8e0d4;padding:24px;">
            <h2 style="color:#d4a855;">Unnamed Elements Detected</h2>
            <p><strong>Page:</strong> {page}</p>
            <p><strong>Count:</strong> {len(elements)} element(s) missing <code>name</code> attribute</p>
            <p style="color:#ff6b6b;">These will appear as "unnamed_link" or "unnamed" in analytics — add a <code>name</code> attribute to track them properly.</p>
            <table style="border-collapse:collapse;margin-top:12px;font-size:13px;">
                <tr style="background:#1a1a2e;">
                    <th style="padding:8px 10px;border:1px solid #333;color:#d4a855;">Tag</th>
                    <th style="padding:8px 10px;border:1px solid #333;color:#d4a855;">Text</th>
                    <th style="padding:8px 10px;border:1px solid #333;color:#d4a855;">Href</th>
                    <th style="padding:8px 10px;border:1px solid #333;color:#d4a855;">Classes</th>
                </tr>
                {rows}
            </table>
            <p style="margin-top:16px;color:#888;font-size:12px;">Fix: add <code>name="descriptive_name"</code> to each element.<br>
            This alert is sent once per page per day.</p>
        </div>'''

        try:
            from lozzalingo.modules.email.email_service import EmailService
            svc = EmailService()
            svc.send_email(
                [admin_email],
                f'[{brand}] {len(elements)} unnamed element(s) on {page}',
                html
            )
            logger.info('analytics', f'Sent unnamed elements alert for {page}: {len(elements)} elements')
        except Exception as e:
            logger.warning('analytics', f'Failed to send unnamed elements email: {e}')

        return jsonify({"status": "reported", "count": len(elements)})

    except Exception as e:
        logger.warning('analytics', f'Error in unnamed elements report: {e}')
        return jsonify({"status": "error"}), 200


@analytics_bp.route('/api/route-analytics')
def get_route_analytics():
    """Get route navigation analytics"""
    is_admin, message = check_admin_access()
    if not is_admin:
        return jsonify({"error": message}), 403

    days_param = request.args.get('days', '7')
    if days_param == 'all':
        days = 99999
    else:
        try:
            days = int(days_param)
        except (ValueError, TypeError):
            days = 7

    conn = get_db_connection(get_analytics_db())
    if not conn:
        return jsonify({'top_pages': [], 'user_journeys': [], 'session_stats': {'avg_pages_per_session': 0, 'max_pages_per_session': 0}})

    try:
        cursor = conn.cursor()

        # Filter out localhost and private IP addresses
        local_ip_filter = """
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
        """ + _owner_fingerprint_filter()

        # Most visited pages/routes (exclude localhost) with URL normalization
        # Step 1: Get visit counts from page_view_client events (exclude bots)
        cursor.execute(f"""
            SELECT url, COUNT(*) as visits
            FROM analytics_log
            WHERE event_type = 'page_view_client'
            AND identity != 'bot'
            AND url IS NOT NULL AND url != ''
            AND datetime(timestamp) >= datetime('now', '-{days} days') {local_ip_filter}
            AND url NOT LIKE '%/admin/%'
            AND url NOT LIKE '%/email-preview/%'
            AND url NOT LIKE '%/api/%'
            AND url NOT LIKE '%/news/editor%'
            GROUP BY url
            HAVING visits > 0
            ORDER BY visits DESC
        """)
        page_visits = cursor.fetchall()

        # Step 2: Get avg time from page_exit events (time attributed to correct url)
        # and route_change events (time is for from_url, stored in additional_data JSON)
        # Time queries include owner data (valid browsing time) but exclude bots
        time_filter = """
            AND identity != 'bot'
        """
        cursor.execute(f"""
            SELECT url, AVG(CAST(time_spent_seconds AS REAL)) as avg_time
            FROM analytics_log
            WHERE event_type = 'page_exit'
            AND time_spent_seconds IS NOT NULL AND time_spent_seconds != ''
            AND CAST(time_spent_seconds AS REAL) > 0
            AND url IS NOT NULL AND url != ''
            AND datetime(timestamp) >= datetime('now', '-{days} days') {time_filter}
            GROUP BY url
        """)
        # Normalize exit_times keys so they match normalized page URLs
        exit_times_normalized = {}
        for row in cursor.fetchall():
            norm_url = normalize_page_url(row[0])
            # Keep a running average if multiple raw URLs normalize to the same thing
            if norm_url in exit_times_normalized:
                exit_times_normalized[norm_url] = (exit_times_normalized[norm_url] + row[1]) / 2
            else:
                exit_times_normalized[norm_url] = row[1]

        # For route_change events, extract from_url from additional_data JSON
        # The time_spent_seconds on route_change is for the page the user LEFT (from_url)
        cursor.execute(f"""
            SELECT
                json_extract(additional_data, '$.from_url') as from_url,
                AVG(CAST(time_spent_seconds AS REAL)) as avg_time
            FROM analytics_log
            WHERE event_type = 'route_change'
            AND time_spent_seconds IS NOT NULL AND time_spent_seconds != ''
            AND CAST(time_spent_seconds AS REAL) > 0
            AND additional_data IS NOT NULL
            AND json_extract(additional_data, '$.from_url') IS NOT NULL
            AND datetime(timestamp) >= datetime('now', '-{days} days') {time_filter}
            GROUP BY from_url
        """)
        route_change_times_normalized = {}
        for row in cursor.fetchall():
            norm_url = normalize_page_url(row[0])
            if norm_url in route_change_times_normalized:
                route_change_times_normalized[norm_url] = (route_change_times_normalized[norm_url] + row[1]) / 2
            else:
                route_change_times_normalized[norm_url] = row[1]

        # Process and normalize URLs
        url_data = {}
        for row in page_visits:
            raw_url = row[0]
            visits = row[1]

            # Normalize URL by removing tracking parameters and standardizing
            normalized_url = normalize_page_url(raw_url)

            # Merge time from page_exit and route_change sources (using normalized keys)
            exit_time = exit_times_normalized.get(normalized_url)
            route_time = route_change_times_normalized.get(normalized_url)
            if exit_time and route_time:
                avg_time = (exit_time + route_time) / 2
            else:
                avg_time = exit_time or route_time or 0

            # Aggregate by normalized URL
            if normalized_url in url_data:
                url_data[normalized_url]['visits'] += visits
                # Weighted average for time spent
                total_time = (url_data[normalized_url]['avg_time_spent'] * url_data[normalized_url]['original_visits'] +
                             avg_time * visits)
                total_visits = url_data[normalized_url]['original_visits'] + visits
                url_data[normalized_url]['avg_time_spent'] = total_time / total_visits if total_visits > 0 else 0
                url_data[normalized_url]['original_visits'] = total_visits
            else:
                url_data[normalized_url] = {
                    'visits': visits,
                    'avg_time_spent': avg_time,
                    'original_visits': visits
                }

        # Convert to list and sort
        top_pages = []
        for normalized_url, data in sorted(url_data.items(), key=lambda x: x[1]['visits'], reverse=True)[:20]:
            top_pages.append({
                'url': normalized_url,
                'visits': data['visits'],
                'avg_time_spent': round(data['avg_time_spent'], 1)
            })

        # Ensure session_id column exists (added in later version)
        cursor.execute(f"PRAGMA table_info(analytics_log)")
        existing_cols = {col[1] for col in cursor.fetchall()}
        has_session_id = 'session_id' in existing_cols
        if not has_session_id:
            try:
                cursor.execute("ALTER TABLE analytics_log ADD COLUMN session_id TEXT")
                conn.commit()
                has_session_id = True
            except Exception:
                pass

        # User journeys — reconstruct page sequences per visitor from page_view/page_exit events
        if has_session_id:
            session_id_select = ', session_id'
            session_id_filter = "OR (session_id IS NOT NULL AND session_id != '')"
            session_id_order = 'COALESCE(session_id, fingerprint_hash)'
        else:
            session_id_select = ''
            session_id_filter = ''
            session_id_order = 'fingerprint_hash'

        cursor.execute(f"""
            SELECT fingerprint_hash, url, event_type, timestamp, time_spent_seconds {session_id_select}
            FROM analytics_log
            WHERE event_type IN ('page_view_client', 'page_exit')
            AND identity != 'bot'
            AND ((fingerprint_hash IS NOT NULL AND fingerprint_hash != '') {session_id_filter})
            AND datetime(timestamp) >= datetime('now', '-{days} days') {local_ip_filter}
            ORDER BY {session_id_order}, timestamp
        """)

        # Group events: prefer session_id, fall back to fingerprint + 30min gap
        from collections import defaultdict
        session_events = defaultdict(list)  # session_id -> events
        fingerprint_events = defaultdict(list)  # fingerprint_hash -> events (no session_id)
        for row in cursor.fetchall():
            event = {
                'url': row[1],
                'event_type': row[2],
                'timestamp': row[3],
                'time_spent': row[4]
            }
            sid = row[5] if has_session_id and len(row) > 5 else None
            if sid:  # has session_id
                session_events[sid].append(event)
            elif row[0]:  # has fingerprint_hash only
                fingerprint_events[row[0]].append(event)

        # Sessions from session_id are already grouped — no gap splitting needed
        all_sessions = list(session_events.values())

        # For fingerprint-only data, split into sessions by 30min gap
        for fp_hash, events in fingerprint_events.items():
            sessions = []
            current_session = []
            for i, event in enumerate(events):
                if i > 0:
                    try:
                        prev_time = datetime.fromisoformat(events[i-1]['timestamp'])
                        curr_time = datetime.fromisoformat(event['timestamp'])
                        if (curr_time - prev_time).total_seconds() > 1800:
                            if current_session:
                                sessions.append(current_session)
                            current_session = []
                    except (ValueError, TypeError):
                        pass
                current_session.append(event)
            if current_session:
                sessions.append(current_session)
            all_sessions.extend(sessions)

        user_journeys = []
        for session in all_sessions:
            # Build page sequence and collect timestamps for retrospective time calc
            pages = []
            page_view_timestamps = []
            exit_page = None
            # Track max exit time per URL (beacons may re-send with updated time)
            exit_times_by_url = {}
            for event in session:
                if event['event_type'] == 'page_view_client':
                    pages.append(normalize_page_url(event['url']))
                    page_view_timestamps.append(event['timestamp'])
                elif event['event_type'] == 'page_exit':
                    exit_page = normalize_page_url(event['url'])
                    try:
                        if event['time_spent']:
                            t = float(event['time_spent'])
                            url = normalize_page_url(event['url'])
                            exit_times_by_url[url] = max(exit_times_by_url.get(url, 0), t)
                    except (ValueError, TypeError):
                        pass

            # Total time from explicit exit beacons
            total_time = sum(exit_times_by_url.values())

            # Retrospective time: if no exit time data, calculate from gaps
            # between consecutive page_view_client timestamps
            if not total_time and len(page_view_timestamps) >= 2:
                try:
                    timestamps = [datetime.fromisoformat(t) for t in page_view_timestamps]
                    retro_time = 0
                    for i in range(1, len(timestamps)):
                        gap = (timestamps[i] - timestamps[i-1]).total_seconds()
                        # Cap individual page time at 15 min (ignore idle gaps)
                        if gap <= 900:
                            retro_time += gap
                    total_time = retro_time
                except (ValueError, TypeError):
                    pass

            if pages:
                # Deduplicate consecutive same-page views
                deduped = [pages[0]]
                for p in pages[1:]:
                    if p != deduped[-1]:
                        deduped.append(p)

                user_journeys.append({
                    'pages': deduped,
                    'page_count': len(deduped),
                    'exit_page': exit_page,
                    'timestamp': session[0]['timestamp'],
                    'total_time': round(total_time) if total_time else None
                })

        # Sort by most recent first, support pagination
        user_journeys.sort(key=lambda j: j['timestamp'], reverse=True)
        journey_offset = request.args.get('journey_offset', 0, type=int)
        journey_limit = request.args.get('journey_limit', 20, type=int)
        total_journeys = len(user_journeys)
        user_journeys = user_journeys[journey_offset:journey_offset + journey_limit]

        # Session analytics (exclude localhost)
        cursor.execute(f"""
            SELECT AVG(CAST(session_page_count AS REAL)) as avg_pages_per_session,
                   MAX(CAST(session_page_count AS REAL)) as max_pages_per_session
            FROM analytics_log
            WHERE event_type = 'page_view_client'
            AND session_page_count IS NOT NULL AND session_page_count != ''
            AND datetime(timestamp) >= datetime('now', '-{days} days') {local_ip_filter}
        """)

        session_data = cursor.fetchone()
        session_stats = {
            'avg_pages_per_session': round(session_data[0], 1) if session_data and session_data[0] else 0,
            'max_pages_per_session': int(session_data[1]) if session_data and session_data[1] else 0
        }

        return jsonify({
            'top_pages': top_pages,
            'user_journeys': user_journeys,
            'total_journeys': total_journeys,
            'session_stats': session_stats
        })

    except Exception as e:
        print(f"Route analytics error: {e}")
        return jsonify({'top_pages': [], 'user_journeys': [], 'session_stats': {'avg_pages_per_session': 0, 'max_pages_per_session': 0}})
    finally:
        conn.close()

@analytics_bp.route('/api/referer-data')
def get_referer_data():
    """Get referrer/traffic source analytics with enhanced categorization"""
    from .referrer_tracker import ReferrerTracker

    is_admin, message = check_admin_access()
    if not is_admin:
        return jsonify({"error": message}), 403

    days = request.args.get('days', 7, type=int)

    conn = get_db_connection(get_analytics_db())
    if not conn:
        response = make_response(jsonify({
            'top_referers': [],
            'category_breakdown': {},
            'medium_breakdown': {},
            'campaign_breakdown': {},
            'social_media_traffic': 0,
            'search_engine_traffic': 0,
            'total_visits': 0
        }))
        return add_no_cache_headers(response)

    try:
        cursor = conn.cursor()

        # Filter out localhost and private IP addresses
        local_ip_filter = """
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
        """ + _owner_fingerprint_filter()

        # Get the FIRST page view per unique visitor for accurate traffic source attribution.
        # Each visitor (fingerprint_hash) is counted exactly once, attributed to the source
        # that first brought them. This ensures the traffic sources total matches unique visitors.
        cursor.execute(f"""
            WITH first_visit AS (
                SELECT
                    fingerprint_hash,
                    MIN(rowid) as first_rowid
                FROM analytics_log
                WHERE event_type = 'page_view_client'
                AND identity = 'human'
                AND fingerprint_hash IS NOT NULL
                AND datetime(timestamp) >= datetime('now', '-{days} days')
                {local_ip_filter}
                GROUP BY fingerprint_hash
            )
            SELECT
                a.referer,
                COALESCE(
                    JSON_EXTRACT(a.additional_data, '$.referrer'),
                    JSON_EXTRACT(a.additional_data, '$.document_referrer')
                ) as doc_referrer,
                JSON_EXTRACT(a.additional_data, '$.utm_params') as utm_params_json,
                JSON_EXTRACT(a.additional_data, '$.search_params') as search_params,
                JSON_EXTRACT(a.additional_data, '$.referrer_info') as referrer_info_json,
                a.user_agent,
                a.rowid
            FROM first_visit fv
            JOIN analytics_log a ON a.rowid = fv.first_rowid
        """)

        # Process referrer data using enhanced tracker
        traffic_sources = {}
        detailed_sources = []

        for row in cursor.fetchall():
            referer = row[0]
            document_referrer = row[1]
            utm_params_json = row[2]
            search_params = row[3]
            referrer_info_json = row[4]
            row_user_agent = row[5]
            visits = 1  # Each row is one unique visitor

            # Multi-pronged detection:
            # 1. Try stored referrer_info first (already processed at ingestion)
            referrer_data = None
            if referrer_info_json:
                try:
                    import json as _json
                    stored = _json.loads(referrer_info_json)
                    # Use stored data if it identified a real source (not Direct/Internal)
                    if stored.get('source') and stored['source'] not in ('Direct', 'Internal'):
                        referrer_data = {
                            'source': stored['source'],
                            'medium': stored.get('medium', 'referral'),
                            'campaign': stored.get('utm_campaign') or stored.get('campaign'),
                            'content': None,
                            'term': None,
                            'category': stored.get('category', 'Referral'),
                            'platform': stored.get('platform'),
                            'is_social': stored.get('is_social', False),
                            'is_search': stored.get('is_search', False),
                            'is_internal': False,
                            'raw_referrer': document_referrer or referer,
                            'utm_source': stored.get('utm_source'),
                            'utm_medium': stored.get('utm_medium'),
                            'utm_campaign': stored.get('utm_campaign'),
                            'utm_content': stored.get('utm_content'),
                            'utm_term': stored.get('utm_term')
                        }
                except Exception:
                    pass

            # 2. Re-parse from referrer URL + UTM + user agent if stored info was Direct/Internal
            if not referrer_data:
                # Parse UTM parameters — try utm_params first, then search_params
                url_params = {}
                try:
                    if utm_params_json:
                        import json as _json
                        url_params = _json.loads(utm_params_json)
                except Exception:
                    pass
                if not url_params and search_params:
                    try:
                        from urllib.parse import parse_qs
                        parsed_params = parse_qs(search_params.lstrip('?'))
                        for k, v in parsed_params.items():
                            if k.startswith('utm_') and v:
                                url_params[k] = v[0]
                    except Exception:
                        pass

                has_doc_referrer = document_referrer and document_referrer != 'None' and document_referrer.strip()
                primary_referrer = document_referrer if has_doc_referrer else None

                # parse_referrer checks: referrer URL → UTM → user agent (in that order)
                referrer_data = ReferrerTracker.parse_referrer(primary_referrer, url_params, user_agent=row_user_agent)

            # Reclassify internal as Direct — an "internal" first page view just means
            # we don't know the original source
            if referrer_data.get('is_internal'):
                referrer_data.update({
                    'source': 'Direct',
                    'medium': 'direct',
                    'category': 'Direct Traffic',
                    'is_internal': False
                })

            # Get display name for aggregation
            display_name = ReferrerTracker.generate_display_name(referrer_data)

            # Aggregate by display name
            if display_name in traffic_sources:
                traffic_sources[display_name]['visits'] += visits
            else:
                traffic_sources[display_name] = {
                    'visits': visits,
                    'category': referrer_data['category'],
                    'source': referrer_data['source'],
                    'medium': referrer_data['medium'],
                    'platform': referrer_data['platform'],
                    'is_social': referrer_data['is_social'],
                    'is_search': referrer_data['is_search'],
                    'campaign': referrer_data['campaign']
                }

            # Store detailed data for additional insights
            detailed_sources.append({
                'display_name': display_name,
                'visits': visits,
                'referrer_data': referrer_data
            })

        # Convert to sorted list format
        top_referers = []
        for display_name, data in sorted(traffic_sources.items(), key=lambda x: x[1]['visits'], reverse=True)[:15]:
            top_referers.append([display_name, data['visits']])

        # Category breakdown
        category_stats = {}
        for display_name, data in traffic_sources.items():
            category = data['category']
            if category in category_stats:
                category_stats[category] += data['visits']
            else:
                category_stats[category] = data['visits']

        # Medium breakdown
        medium_stats = {}
        for display_name, data in traffic_sources.items():
            medium = data['medium']
            if medium in medium_stats:
                medium_stats[medium] += data['visits']
            else:
                medium_stats[medium] = data['visits']

        # Campaign breakdown
        campaign_stats = {}
        for display_name, data in traffic_sources.items():
            if data['campaign']:
                if data['campaign'] in campaign_stats:
                    campaign_stats[data['campaign']] += data['visits']
                else:
                    campaign_stats[data['campaign']] = data['visits']

        response = make_response(jsonify({
            'top_referers': top_referers,
            'category_breakdown': category_stats,
            'medium_breakdown': medium_stats,
            'campaign_breakdown': campaign_stats,
            'social_media_traffic': sum(data['visits'] for data in traffic_sources.values() if data['is_social']),
            'search_engine_traffic': sum(data['visits'] for data in traffic_sources.values() if data['is_search']),
            'total_visits': sum(data['visits'] for data in traffic_sources.values())
        }))
        return add_no_cache_headers(response)

    except Exception as e:
        print(f"Referer data error: {e}")
        response = make_response(jsonify({
            'top_referers': [],
            'category_breakdown': {},
            'medium_breakdown': {},
            'campaign_breakdown': {},
            'social_media_traffic': 0,
            'search_engine_traffic': 0,
            'total_visits': 0
        }))
        return add_no_cache_headers(response)
    finally:
        conn.close()

@analytics_bp.route('/api/log-enhanced-interaction', methods=['POST'])
def log_enhanced_interaction():
    """Enhanced analytics endpoint for comprehensive referrer tracking"""
    try:
        # Security: Validate request origin to prevent abuse from external sites
        is_valid_origin, reason = is_valid_analytics_origin()

        if not is_valid_origin:
            logger.warning('analytics', f'Rejected enhanced analytics request: {reason}')
            return jsonify({"error": "Invalid origin"}), 403

        # Get JSON data from request
        if request.content_type and 'application/json' in request.content_type:
            data = request.get_json()
        else:
            data = request.form.to_dict()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        print(f"[DEBUG] Enhanced analytics data received: {data}")

        # Extract referrer and UTM data from the enhanced payload
        referrer_data = data.get('referrer_data', {})
        utm_params = data.get('utm_params', {})
        social_params = data.get('social_params', {})
        custom_params = data.get('custom_params', {})

        # Combine all URL parameters for referrer parsing
        all_url_params = {**utm_params, **social_params, **custom_params}

        # Use the enhanced analytics system
        from .analytics import Analytics

        # Create enhanced additional_data
        enhanced_data = {
            'utm_params': utm_params,
            'social_params': social_params,
            'custom_params': custom_params,
            'referrer_data': referrer_data,
            'session_info': data.get('session_info', {}),
            'device_info': data.get('device_info', {}),
            'page_url': data.get('url'),
            'page_title': data.get('title'),
            'event_name': data.get('event_name'),
            'event_data': data.get('event_data', {})
        }

        # Log with enhanced analytics
        Analytics.log_comprehensive_analytics(
            request,
            data.get('event_type', 'enhanced_page_view'),
            fingerprint=data.get('fingerprint'),
            additional_data=enhanced_data
        )

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"[ERROR] Enhanced analytics logging failed: {e}")
        # Don't fail the client request just because analytics failed
        return jsonify({"status": "logged", "warning": "partial failure"}), 200

@analytics_bp.route('/api/ecommerce-analytics')
def get_ecommerce_analytics():
    """Get comprehensive e-commerce analytics"""
    is_admin, message = check_admin_access()
    if not is_admin:
        return jsonify({"error": message}), 403

    days = request.args.get('days', 7, type=int)

    # Get merchandise database connection from config
    merchandise_conn = get_db_connection(_get_merchandise_db())
    analytics_conn = get_db_connection(get_analytics_db())

    if not merchandise_conn or not analytics_conn:
        return jsonify({
            'sales_summary': {'completed_orders': 0, 'total_revenue': 0, 'avg_order_value': 0},
            'cart_analytics': {'add_to_cart_clicks': 0, 'checkout_clicks': 0, 'cart_page_views': 0, 'success_page_views': 0},
            'top_products': [],
            'conversion_funnel': {},
            'conversion_rates': {}
        })

    try:
        results = {}

        # Get actual sales data from merchandise database
        merchandise_cursor = merchandise_conn.cursor()
        analytics_cursor = analytics_conn.cursor()

        # 1. Sales vs Cart Analytics
        # Actual completed orders
        merchandise_cursor.execute("""
            SELECT
                COUNT(*) as completed_orders,
                SUM(total_amount) as total_revenue,
                AVG(total_amount) as avg_order_value
            FROM orders
            WHERE status = 'paid'
            AND datetime(created_at) >= datetime('now', '-{} days')
        """.format(days))

        sales_data = merchandise_cursor.fetchone()

        # Cart interactions from analytics
        owner_filter = _owner_fingerprint_filter()
        analytics_cursor.execute(f"""
            SELECT
                COUNT(CASE WHEN interaction_type = 'button_click' AND element_id LIKE '%add-to-cart%' THEN 1 END) as add_to_cart_clicks,
                COUNT(CASE WHEN interaction_type = 'button_click' AND element_id LIKE '%checkout%' THEN 1 END) as checkout_clicks,
                COUNT(CASE WHEN url LIKE '%/cart%' THEN 1 END) as cart_page_views,
                COUNT(CASE WHEN url LIKE '%/merchandise/success%' THEN 1 END) as success_page_views
            FROM analytics_log
            WHERE datetime(timestamp) >= datetime('now', '-{days} days')
            AND identity != 'bot'
            {owner_filter}
        """)

        cart_data = analytics_cursor.fetchone()

        # 2. Product Performance
        merchandise_cursor.execute("""
            SELECT
                p.name,
                p.id,
                SUM(oi.quantity) as units_sold,
                SUM(oi.price_at_time * oi.quantity) as revenue,
                COUNT(DISTINCT o.id) as orders_count
            FROM products p
            LEFT JOIN order_items oi ON p.id = oi.product_id
            LEFT JOIN orders o ON oi.order_id = o.id
            WHERE o.status = 'paid' AND datetime(o.created_at) >= datetime('now', '-{} days')
            GROUP BY p.id, p.name
            ORDER BY units_sold DESC
            LIMIT 10
        """.format(days))

        top_products = []
        for row in merchandise_cursor.fetchall():
            top_products.append({
                'name': row[0],
                'product_id': row[1],
                'units_sold': row[2] or 0,
                'revenue': row[3] or 0,
                'orders_count': row[4] or 0
            })

        # 3. Conversion Funnel
        funnel_data = {
            'product_views': 0,
            'add_to_cart': cart_data[0] if cart_data and cart_data[0] else 0,
            'cart_views': cart_data[2] if cart_data and cart_data[2] else 0,
            'checkout_initiated': cart_data[1] if cart_data and cart_data[1] else 0,
            'orders_completed': sales_data[0] if sales_data and sales_data[0] else 0
        }

        # Get product page views
        analytics_cursor.execute(f"""
            SELECT COUNT(*)
            FROM analytics_log
            WHERE url LIKE '%/merchandise/products%'
            AND event_type = 'page_view_client'
            AND datetime(timestamp) >= datetime('now', '-{days} days')
            AND identity != 'bot'
            {owner_filter}
        """)

        product_views = analytics_cursor.fetchone()
        funnel_data['product_views'] = product_views[0] if product_views else 0

        # Calculate conversion rates
        conversion_rates = {}
        if funnel_data['product_views'] > 0:
            conversion_rates['product_to_cart'] = (funnel_data['add_to_cart'] / funnel_data['product_views']) * 100
        if funnel_data['add_to_cart'] > 0:
            conversion_rates['cart_to_checkout'] = (funnel_data['checkout_initiated'] / funnel_data['add_to_cart']) * 100
        if funnel_data['checkout_initiated'] > 0:
            conversion_rates['checkout_to_order'] = (funnel_data['orders_completed'] / funnel_data['checkout_initiated']) * 100

        results = {
            'sales_summary': {
                'completed_orders': sales_data[0] if sales_data else 0,
                'total_revenue': (sales_data[1] / 100) if sales_data and sales_data[1] else 0,  # Convert from pence
                'avg_order_value': (sales_data[2] / 100) if sales_data and sales_data[2] else 0
            },
            'cart_analytics': {
                'add_to_cart_clicks': cart_data[0] if cart_data else 0,
                'checkout_clicks': cart_data[1] if cart_data else 0,
                'cart_page_views': cart_data[2] if cart_data else 0,
                'success_page_views': cart_data[3] if cart_data else 0
            },
            'top_products': top_products,
            'conversion_funnel': funnel_data,
            'conversion_rates': conversion_rates
        }

        return jsonify(results)

    except Exception as e:
        print(f"E-commerce analytics error: {e}")
        return jsonify({
            'sales_summary': {'completed_orders': 0, 'total_revenue': 0, 'avg_order_value': 0},
            'cart_analytics': {'add_to_cart_clicks': 0, 'checkout_clicks': 0, 'cart_page_views': 0, 'success_page_views': 0},
            'top_products': [],
            'conversion_funnel': {},
            'conversion_rates': {}
        })
    finally:
        if merchandise_conn:
            merchandise_conn.close()
        if analytics_conn:
            analytics_conn.close()

@analytics_bp.route('/api/sales-metrics')
def get_sales_metrics():
    """Get sales and revenue analytics (legacy endpoint)"""
    is_admin, message = check_admin_access()
    if not is_admin:
        return jsonify({"error": message}), 403

    days_param = request.args.get('days', '7')
    cutoff_date = get_cutoff_date(days_param)

    # Get merchandise database from config
    merch_db = _get_merchandise_db()

    conn = get_db_connection(merch_db)
    if not conn:
        return jsonify({
            'total_orders': 0,
            'total_revenue': 0,
            'recent_orders': 0,
            'recent_revenue': 0,
            'avg_order_value': 0,
            'sales_timeline': [],
            'recent_sales': [],
            'top_products': [],
            'size_breakdown': {}
        })

    try:
        cursor = conn.cursor()

        # Overall sales stats
        cursor.execute("SELECT COUNT(*), SUM(total_amount) FROM orders WHERE status = 'paid'")
        total_stats = cursor.fetchone()
        total_orders = total_stats[0] or 0
        total_revenue = total_stats[1] or 0

        # Recent sales stats
        cursor.execute("SELECT COUNT(*), SUM(total_amount) FROM orders WHERE status = 'paid' AND datetime(created_at) >= ?", (cutoff_date,))
        recent_stats = cursor.fetchone()
        recent_orders = recent_stats[0] or 0
        recent_revenue = recent_stats[1] or 0

        # Average order value
        avg_order_value = (total_revenue / total_orders) if total_orders > 0 else 0

        # Sales timeline (daily)
        cursor.execute("""
            SELECT DATE(created_at) as date, COUNT(*) as orders, SUM(total_amount) as revenue
            FROM orders
            WHERE status = 'paid' AND datetime(created_at) >= ?
            GROUP BY DATE(created_at)
            ORDER BY date
        """, (cutoff_date,))

        sales_timeline = []
        for row in cursor.fetchall():
            sales_timeline.append({
                'date': row[0],
                'orders': row[1],
                'revenue': row[2]
            })

        # Recent sales
        cursor.execute("""
            SELECT o.id, o.customer_email, o.total_amount, o.created_at, o.customer_name,
                   GROUP_CONCAT(p.name || ' (Size: ' || COALESCE(oi.size, 'N/A') || ')') as items
            FROM orders o
            LEFT JOIN order_items oi ON o.id = oi.order_id
            LEFT JOIN products p ON oi.product_id = p.id
            WHERE o.status = 'paid'
            GROUP BY o.id
            ORDER BY o.created_at DESC
            LIMIT 10
        """)

        recent_sales = []
        for row in cursor.fetchall():
            recent_sales.append({
                'order_id': row[0],
                'customer_email': row[1],
                'amount': row[2],
                'date': row[3],
                'customer_name': row[4] or 'N/A',
                'items': row[5] or 'No items'
            })

        # Top products by sales
        cursor.execute("""
            SELECT p.name, SUM(oi.quantity) as total_sold, SUM(oi.quantity * oi.price_at_time) as revenue
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            JOIN orders o ON oi.order_id = o.id
            WHERE o.status = 'paid' AND datetime(o.created_at) >= ?
            GROUP BY p.id, p.name
            ORDER BY total_sold DESC
            LIMIT 10
        """, (cutoff_date,))

        top_products = []
        for row in cursor.fetchall():
            top_products.append({
                'name': row[0],
                'quantity_sold': row[1],
                'revenue': row[2]
            })

        # Size breakdown for t-shirts
        cursor.execute("""
            SELECT oi.size, COUNT(*) as count
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            WHERE o.status = 'paid'
            AND oi.size IS NOT NULL
            AND oi.size != ''
            AND datetime(o.created_at) >= ?
            GROUP BY oi.size
            ORDER BY count DESC
        """, (cutoff_date,))

        size_breakdown = {}
        for row in cursor.fetchall():
            size_breakdown[row[0]] = row[1]

        response = make_response(jsonify({
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'recent_orders': recent_orders,
            'recent_revenue': recent_revenue,
            'avg_order_value': round(avg_order_value / 100, 2),  # Convert from pence to pounds
            'sales_timeline': sales_timeline,
            'recent_sales': recent_sales,
            'top_products': top_products,
            'size_breakdown': size_breakdown
        }))
        return add_no_cache_headers(response)

    except Exception as e:
        print(f"Sales data error: {e}")
        return jsonify({
            'total_orders': 0,
            'total_revenue': 0,
            'recent_orders': 0,
            'recent_revenue': 0,
            'avg_order_value': 0,
            'sales_timeline': [],
            'recent_sales': [],
            'top_products': [],
            'size_breakdown': {}
        })
    finally:
        conn.close()

@analytics_bp.route('/api/ecommerce-funnel')
def get_ecommerce_funnel():
    """Get e-commerce funnel metrics from analytics events"""
    is_admin, message = check_admin_access()
    if not is_admin:
        return jsonify({"error": message}), 403

    days_param = request.args.get('days', '7')
    cutoff_date = get_cutoff_date(days_param)

    analytics_conn = get_db_connection(get_analytics_db())
    merch_conn = get_db_connection(_get_merchandise_db())

    if not analytics_conn:
        return jsonify({
            'product_views': 0,
            'add_to_cart': 0,
            'checkouts_initiated': 0,
            'conversions': 0,
            'abandoned': 0
        })

    try:
        cursor = analytics_conn.cursor()
        owner_filter = _owner_fingerprint_filter()

        # Count product views (custom_event with event_name = 'product_view')
        cursor.execute(f"""
            SELECT COUNT(*) FROM analytics_log
            WHERE event_type = 'custom_event'
            AND json_extract(additional_data, '$.event_name') = 'product_view'
            AND datetime(timestamp) >= ?
            AND identity != 'bot'
            {owner_filter}
        """, (cutoff_date,))
        product_views = cursor.fetchone()[0] or 0

        # Count add to cart events (custom_event with event_name = 'add_to_cart')
        cursor.execute(f"""
            SELECT COUNT(*) FROM analytics_log
            WHERE event_type = 'custom_event'
            AND json_extract(additional_data, '$.event_name') = 'add_to_cart'
            AND datetime(timestamp) >= ?
            AND identity != 'bot'
            {owner_filter}
        """, (cutoff_date,))
        add_to_cart = cursor.fetchone()[0] or 0

        # Count checkout initiated events (custom_event with event_name = 'checkout_initiated')
        cursor.execute(f"""
            SELECT COUNT(*) FROM analytics_log
            WHERE event_type = 'custom_event'
            AND json_extract(additional_data, '$.event_name') = 'checkout_initiated'
            AND datetime(timestamp) >= ?
            AND identity != 'bot'
            {owner_filter}
        """, (cutoff_date,))
        checkouts_initiated = cursor.fetchone()[0] or 0

        # Count actual conversions from orders table
        conversions = 0
        if merch_conn:
            merch_cursor = merch_conn.cursor()
            merch_cursor.execute("""
                SELECT COUNT(*) FROM orders
                WHERE status = 'paid'
                AND datetime(created_at) >= ?
            """, (cutoff_date,))
            conversions = merch_cursor.fetchone()[0] or 0

        # Calculate abandoned carts (checkouts initiated but not converted)
        abandoned = max(0, checkouts_initiated - conversions)

        response = jsonify({
            'product_views': product_views,
            'add_to_cart': add_to_cart,
            'checkouts_initiated': checkouts_initiated,
            'conversions': conversions,
            'abandoned': abandoned
        })
        return add_no_cache_headers(response)

    except Exception as e:
        print(f"E-commerce funnel error: {e}")
        return jsonify({
            'product_views': 0,
            'add_to_cart': 0,
            'checkouts_initiated': 0,
            'conversions': 0,
            'abandoned': 0
        })
    finally:
        if analytics_conn:
            analytics_conn.close()
        if merch_conn:
            merch_conn.close()

@analytics_bp.route('/api/button-clicks')
def get_button_clicks():
    """Get button click analytics"""
    is_admin, message = check_admin_access()
    if not is_admin:
        return jsonify({"error": message}), 403

    days_param = request.args.get('days', '7')
    cutoff_date = get_cutoff_date(days_param)

    analytics_conn = get_db_connection(get_analytics_db())

    if not analytics_conn:
        return jsonify({
            'top_buttons': [],
            'commerce_buttons': []
        })

    try:
        cursor = analytics_conn.cursor()

        # Get all button clicks (interaction_type starts with 'button_click_')
        # Filter out unnamed buttons
        owner_filter = _owner_fingerprint_filter()
        cursor.execute(f"""
            SELECT interaction_type, COUNT(*) as count
            FROM analytics_log
            WHERE interaction_type LIKE 'button_click_%'
            AND interaction_type NOT LIKE '%unnamed%'
            AND datetime(timestamp) >= ?
            AND identity = 'human'
            {owner_filter}
            GROUP BY interaction_type
            ORDER BY count DESC
            LIMIT 15
        """, (cutoff_date,))

        all_buttons = []
        for row in cursor.fetchall():
            all_buttons.append({
                'button_name': row[0],
                'count': row[1]
            })

        # Define commerce-specific button patterns
        commerce_patterns = [
            'add_to_cart',
            'accept-shipping-policy',
            'view_cart',
            'checkout',
            'continue_shopping',
            'close_cart'
        ]

        # Filter commerce buttons
        commerce_buttons = [
            btn for btn in all_buttons
            if any(pattern in btn['button_name'] for pattern in commerce_patterns)
        ]

        # If we don't have enough commerce buttons from regular clicks, check custom_events
        if len(commerce_buttons) < 3:
            cursor.execute(f"""
                SELECT json_extract(additional_data, '$.event_name') as event_name, COUNT(*) as count
                FROM analytics_log
                WHERE event_type = 'custom_event'
                AND json_extract(additional_data, '$.event_name') IN ('add_to_cart', 'product_view', 'checkout_initiated')
                AND datetime(timestamp) >= ?
                AND identity != 'bot'
                {owner_filter}
                GROUP BY event_name
                ORDER BY count DESC
            """, (cutoff_date,))

            for row in cursor.fetchall():
                commerce_buttons.append({
                    'button_name': row[0],
                    'count': row[1]
                })

        response = jsonify({
            'top_buttons': all_buttons[:10],
            'commerce_buttons': commerce_buttons[:6]
        })
        return add_no_cache_headers(response)

    except Exception as e:
        print(f"Button click analytics error: {e}")
        return jsonify({
            'top_buttons': [],
            'commerce_buttons': []
        })
    finally:
        if analytics_conn:
            analytics_conn.close()


# ── Mission Ctrl Summary Endpoint ────────────────────────────────────────────

@analytics_bp.route('/api/summary')
def api_analytics_summary():
    """Public summary endpoint for Mission Ctrl. Protected by API key, not admin session."""
    key = request.args.get('key', '')
    expected_key = os.getenv('MISSION_CTRL_API_KEY', '')
    if not expected_key or key != expected_key:
        return jsonify({'error': 'Unauthorized'}), 403

    days = request.args.get('days', '1')
    try:
        days_int = int(days)
    except ValueError:
        days_int = 1

    analytics_conn = None
    try:
        analytics_db = get_analytics_db()
        analytics_table = get_analytics_table()
        analytics_conn = sqlite3.connect(analytics_db)
        cursor = analytics_conn.cursor()
        owner_filter = _owner_fingerprint_filter()

        # Unique human visitors
        cursor.execute(f"""
            SELECT COUNT(DISTINCT fingerprint_hash)
            FROM {analytics_table}
            WHERE fingerprint_hash IS NOT NULL
            AND identity IN ('human', 'likely_human')
            AND datetime(timestamp) >= datetime('now', '-{days_int} days')
            {owner_filter}
        """)
        unique_visitors = cursor.fetchone()[0]

        # Identity breakdown
        cursor.execute(f"""
            SELECT identity, COUNT(*)
            FROM {analytics_table}
            WHERE datetime(timestamp) >= datetime('now', '-{days_int} days')
            GROUP BY identity
        """)
        identity_breakdown = dict(cursor.fetchall())

        human_visitors = identity_breakdown.get('human', 0) + identity_breakdown.get('likely_human', 0)
        bot_hits = identity_breakdown.get('bot', 0)
        page_views = sum(identity_breakdown.values())

        # Top countries (humans only)
        cursor.execute(f"""
            SELECT country, COUNT(*) as cnt
            FROM {analytics_table}
            WHERE datetime(timestamp) >= datetime('now', '-{days_int} days')
            AND country NOT IN ('Unknown', 'Local', '')
            AND identity IN ('human', 'likely_human')
            {owner_filter}
            GROUP BY country
            ORDER BY cnt DESC
            LIMIT 10
        """)
        top_countries = [{'name': r[0], 'count': r[1]} for r in cursor.fetchall()]

        # Top pages (humans only)
        cursor.execute(f"""
            SELECT COALESCE(url, from_route, 'unknown') as page, COUNT(*) as cnt
            FROM {analytics_table}
            WHERE datetime(timestamp) >= datetime('now', '-{days_int} days')
            AND identity IN ('human', 'likely_human')
            AND event_type = 'page_view_client'
            {owner_filter}
            GROUP BY page
            ORDER BY cnt DESC
            LIMIT 10
        """)
        top_pages = [{'path': r[0], 'views': r[1]} for r in cursor.fetchall()]

        # Top referrers
        cursor.execute(f"""
            SELECT referer, COUNT(*) as cnt
            FROM {analytics_table}
            WHERE datetime(timestamp) >= datetime('now', '-{days_int} days')
            AND identity IN ('human', 'likely_human')
            AND referer IS NOT NULL AND referer != ''
            {owner_filter}
            GROUP BY referer
            ORDER BY cnt DESC
            LIMIT 10
        """)
        top_referrers = [{'name': r[0], 'count': r[1]} for r in cursor.fetchall()]

        return jsonify({
            'unique_visitors': unique_visitors,
            'human_visitors': human_visitors,
            'page_views': page_views,
            'bot_hits': bot_hits,
            'top_countries': top_countries,
            'top_pages': top_pages,
            'top_referrers': top_referrers,
            'identity_breakdown': identity_breakdown,
            'period_days': days_int,
        })

    except Exception as e:
        print(f"Analytics summary error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if analytics_conn:
            analytics_conn.close()