import requests
import json
import re
import os
from datetime import datetime, timedelta
from lozzalingo.core import Database
import hashlib
from .referrer_tracker import ReferrerTracker
from flask import request as flask_request


def get_analytics_db():
    """Get analytics DB path with 3-tier resolution: app.config > Config > env var."""
    try:
        from flask import current_app
        val = current_app.config.get('ANALYTICS_DB')
        if val:
            return val
    except RuntimeError:
        pass
    try:
        from lozzalingo.core import Config
        if hasattr(Config, 'ANALYTICS_DB'):
            return Config.ANALYTICS_DB
    except ImportError:
        pass
    return os.getenv('ANALYTICS_DB', 'analytics_log.db')


def get_analytics_table():
    """Get analytics table name with 3-tier resolution: app.config > Config > env var."""
    try:
        from flask import current_app
        val = current_app.config.get('ANALYTICS_TABLE')
        if val:
            return val
    except RuntimeError:
        pass
    try:
        from lozzalingo.core import Config
        if hasattr(Config, 'ANALYTICS_TABLE'):
            return Config.ANALYTICS_TABLE
    except ImportError:
        pass
    return os.getenv('ANALYTICS_TABLE', 'analytics_log')


class Analytics:
    # Cache for geolocation data to reduce API calls
    _geo_cache = {}
    _cache_expiry = {}
    _CACHE_DURATION_HOURS = 24
    # Known bot user agent patterns
    BOT_PATTERNS = [
        r'bot', r'crawler', r'spider', r'scraper', r'scraping', r'wget', r'curl',
        r'python', r'requests', r'urllib', r'postman', r'insomnia', r'http',
        r'automated', r'headless', r'phantom', r'selenium', r'puppeteer',
        r'googlebot', r'google-inspectiontool', r'google-safety', r'google-extended',
        r'bingbot', r'slurp', r'duckduckbot', r'baiduspider',
        r'facebookexternalhit', r'twitterbot', r'linkedinbot', r'whatsapp',
        r'telegram', r'discord', r'slack', r'preview'
    ]
    
    # Human browser patterns
    HUMAN_PATTERNS = [
        r'mozilla', r'chrome', r'safari', r'firefox', r'edge', r'opera'
    ]

    @staticmethod
    def get_client_ip(request):
        """Extract client IP from request, handling proxies"""
        forwarded_ip = request.headers.get('X-Forwarded-For')
        if forwarded_ip:
            return forwarded_ip.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
            
        return request.remote_addr or 'unknown'
    
    @staticmethod
    def get_geo_data(ip):
        """Get geographical data for an IP address with caching"""
        if ip in ['127.0.0.1', 'localhost', 'unknown'] or ip.startswith(('192.168.', '10.', '172.')):
            return {'country': 'Local', 'region': 'Local', 'city': 'Local'}

        # Check cache first
        now = datetime.now()
        if ip in Analytics._geo_cache:
            # Check if cache is still valid
            if ip in Analytics._cache_expiry and Analytics._cache_expiry[ip] > now:
                print(f"Using cached geo data for {ip}")
                return Analytics._geo_cache[ip]
            else:
                # Cache expired, remove it
                del Analytics._geo_cache[ip]
                if ip in Analytics._cache_expiry:
                    del Analytics._cache_expiry[ip]

        # Make API call using ip-api.com (free, 45 req/min, no key needed)
        try:
            response = requests.get(f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,regionName,city", timeout=3)
            if response.status_code == 200:
                geo = response.json()
                if geo.get('status') == 'success':
                    geo_data = {
                        'country': geo.get("countryCode", "Unknown"),
                        'region': geo.get("regionName", "Unknown"),
                        'city': geo.get("city", "Unknown")
                    }
                    # Cache the result
                    Analytics._geo_cache[ip] = geo_data
                    Analytics._cache_expiry[ip] = now + timedelta(hours=Analytics._CACHE_DURATION_HOURS)
                    print(f"Cached geo data for {ip}: {geo_data}")
                    return geo_data
                else:
                    print(f"Geo lookup failed for {ip}: {geo.get('message', 'Unknown error')}")
            else:
                print(f"Geo lookup failed for {ip}: HTTP {response.status_code}")
        except Exception as e:
            print(f"Geo lookup failed for {ip}: {e}")

        return {'country': 'Unknown', 'region': 'Unknown', 'city': 'Unknown'}
    
    @staticmethod
    def detect_identity(user_agent, has_javascript=False, fingerprint=None):
        """Detect if request is from human or bot"""
        if not user_agent:
            return 'bot'
        
        user_agent_lower = user_agent.lower()
        
        # Strong bot indicators
        for pattern in Analytics.BOT_PATTERNS:
            if re.search(pattern, user_agent_lower):
                return 'bot'
        
        # JavaScript execution is a strong human indicator
        if has_javascript and fingerprint:
            return 'human'
        
        # Check for human browser patterns
        human_indicators = sum(1 for pattern in Analytics.HUMAN_PATTERNS 
                             if re.search(pattern, user_agent_lower))
        
        if human_indicators >= 2:
            return 'likely_human'
        elif human_indicators >= 1:
            return 'possible_human'
        
        return 'unknown'
    
    @staticmethod
    def hash_fingerprint(fingerprint):
        if not fingerprint:
            return None
        # Handle dict (deviceDetails) or string fingerprint
        if isinstance(fingerprint, dict):
            fingerprint = json.dumps(fingerprint, sort_keys=True)
        return hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()

    @staticmethod
    def log_page_view_client(request, fingerprint, client_data=None):
        """Log client-side page view with fingerprint"""
        Analytics.log_comprehensive_analytics(
            request, 'page_view_client', 
            fingerprint=fingerprint, 
            additional_data=client_data
        )
    
    @staticmethod
    def log_submission_analytics(request, email, fingerprint=None, form_data=None):
        """Log form submission analytics"""
        submission_data = {}
        if form_data:
            # Log form field presence without sensitive data
            submission_data = {
                'has_prompt': bool(form_data.get('prompt')),
                'prompt_length': len(form_data.get('prompt', '')),
                'has_image': bool(form_data.get('has_image')),
                'design_type': form_data.get('design'),
                'sex': form_data.get('sex'),
                'colour_group': form_data.get('colour_group'),
                'has_names': bool(form_data.get('first_name') and form_data.get('last_name')),
                'has_location': bool(form_data.get('location'))
            }
        
        Analytics.log_comprehensive_analytics(
            request, 'form_submission', 
            email=email, 
            fingerprint=fingerprint,
            additional_data=submission_data
        )
    
    @staticmethod
    def log_interaction(request, interaction_type, email=None, fingerprint=None, additional_data=None):
        """Log user interactions"""
        Analytics.log_comprehensive_analytics(
            request, 'interaction', 
            email=email, 
            fingerprint=fingerprint, 
            interaction_type=interaction_type,
            additional_data=additional_data
        )
    
    @staticmethod
    def log_route_analytics(request, route_data, fingerprint=None):
        """Log route-specific analytics data with improved handling"""
        try:
            # Extract route information from the client data
            route_info = route_data.get('route_info', {})
            
            # Handle both 'url' and 'to_url' field names for compatibility
            page_url = route_data.get('to_url') or route_data.get('url') or route_data.get('page_url')
            
            additional_data = {
                'route_name': route_info.get('route_name'),
                'from_route': route_data.get('from_route'),
                'to_route': route_data.get('to_route'), 
                'navigation_type': route_data.get('navigation_type'),
                'time_spent_seconds': route_data.get('time_spent_seconds'),
                'time_spent_ms': route_data.get('time_spent_ms'),
                'session_page_count': route_data.get('session_page_count'),
                'is_returning_visitor': route_data.get('is_returning_visitor', False),
                'route_history': json.dumps(route_data.get('route_history', [])),
                'url': page_url,
                'state': json.dumps(route_data.get('state')) if route_data.get('state') else None,
            }
            
            Analytics.log_comprehensive_analytics(
                request, 
                route_data.get('type', 'route_event'), 
                fingerprint=fingerprint,
                additional_data=additional_data
            )
            
            print(f"Route analytics logged: {route_data.get('from_route')} -> {route_data.get('to_route')}")
            
        except Exception as e:
            print(f"Failed to log route analytics: {e}")

    @staticmethod  
    def log_design_interaction(request, interaction_data, fingerprint=None):
        """Log design and prompt view interactions"""
        try:
            interaction_type = interaction_data.get('type')
            
            additional_data = {
                'design_id': interaction_data.get('design_id'),
                'design_title': interaction_data.get('design_title'),
                'image_url': interaction_data.get('image_url'),
                'creator_name': interaction_data.get('creator_name'),
                'listing_status': interaction_data.get('listing_status'),
                'category': interaction_data.get('category'),
                'view_source': interaction_data.get('view_source'),
                'listing_id': interaction_data.get('listing_id'),
                'platform': interaction_data.get('platform'),
                'original_prompt': interaction_data.get('original_prompt'),
                'prompt_length': interaction_data.get('prompt_length'),
            }
            
            Analytics.log_comprehensive_analytics(
                request,
                'interaction',
                fingerprint=fingerprint,
                interaction_type=interaction_type,
                additional_data=additional_data
            )
            
            print(f"Design interaction logged: {interaction_type} for design {interaction_data.get('design_id')}")
            
        except Exception as e:
            print(f"Failed to log design interaction: {e}")

    @staticmethod
    def log_comprehensive_analytics(request, event_type, email=None, fingerprint=None, interaction_type=None, additional_data=None):
        """Main analytics logging function"""
        try:
            print(f"[DEBUG ANALYTICS] Starting log_comprehensive_analytics with event_type: {event_type}")

            # Get request data
            ip = Analytics.get_client_ip(request)
            user_agent = request.headers.get('User-Agent', '')
            referer = request.headers.get('Referer', '')

            # Enhanced referrer tracking
            # Use client-side document.referrer when available (more accurate
            # than HTTP Referer which is always the page's own URL for JS fetches)
            doc_referrer = None
            url_params = dict(request.args) if hasattr(request, 'args') else {}
            if additional_data:
                doc_referrer = additional_data.get('referrer') or additional_data.get('document_referrer')
                # Extract UTM params from the page URL's query string
                search_params = additional_data.get('search_params', '')
                if search_params:
                    from urllib.parse import parse_qs
                    parsed_params = parse_qs(search_params.lstrip('?'))
                    # parse_qs returns lists, flatten to single values
                    for k, v in parsed_params.items():
                        if k.startswith('utm_') and v:
                            url_params[k] = v[0]
            referrer_url = doc_referrer or referer
            referrer_data = ReferrerTracker.parse_referrer(referrer_url, url_params, user_agent=user_agent)

            print(f"[DEBUG ANALYTICS] Request data - IP: {ip}, User-Agent: {user_agent[:50]}...")
            print(f"[DEBUG ANALYTICS] Enhanced referrer data: {referrer_data}")

            # Get geo data
            geo_data = Analytics.get_geo_data(ip)
            print(f"[DEBUG ANALYTICS] Geo data: {geo_data}")

            # Process fingerprint
            hashed_fingerprint = Analytics.hash_fingerprint(fingerprint) if fingerprint else None
            print(f"[DEBUG ANALYTICS] Fingerprint processed: {bool(fingerprint)}")

            # Detect identity
            identity = Analytics.detect_identity(user_agent, fingerprint is not None, fingerprint)
            print(f"[DEBUG ANALYTICS] Identity detected: {identity}")

            # Get device info from user agent using DeviceDetector
            from .device_detector import DeviceDetector
            device_detection = DeviceDetector.detect_device_from_ua(user_agent)
            device_type = device_detection.get('device_type', 'unknown')
            server_device_os = device_detection.get('os', 'unknown')
            server_device_brand = device_detection.get('brand', 'unknown')

            # Prepare data for database
            timestamp = datetime.now().isoformat()

            # Enhance additional_data with referrer information
            if additional_data is None:
                additional_data = {}

            # Add enhanced referrer data to additional_data
            additional_data['referrer_info'] = {
                'source': referrer_data['source'],
                'medium': referrer_data['medium'],
                'campaign': referrer_data['campaign'],
                'category': referrer_data['category'],
                'platform': referrer_data['platform'],
                'is_social': referrer_data['is_social'],
                'is_search': referrer_data['is_search'],
                'is_internal': referrer_data['is_internal'],
                'utm_source': referrer_data['utm_source'],
                'utm_medium': referrer_data['utm_medium'],
                'utm_campaign': referrer_data['utm_campaign'],
                'utm_content': referrer_data['utm_content'],
                'utm_term': referrer_data['utm_term']
            }

            additional_data_json = json.dumps(additional_data)

            print(f"[DEBUG ANALYTICS] Timestamp: {timestamp}")
            print(f"[DEBUG ANALYTICS] Additional data: {additional_data_json}")

            # Extract specific fields from additional_data
            # Use client-side data if available, otherwise fall back to server-side detection
            device_confidence = None
            device_os = server_device_os  # Default to server-side detection
            device_brand = server_device_brand  # Default to server-side detection
            url = None
            from_route = None
            to_route = None
            navigation_type = None
            time_spent_seconds = None
            session_page_count = None
            session_id = None

            if additional_data:
                device_confidence = additional_data.get('device_confidence')
                # Override with client-side data if available (more accurate)
                if additional_data.get('device_os'):
                    device_os = additional_data.get('device_os')
                if additional_data.get('device_brand'):
                    device_brand = additional_data.get('device_brand')
                url = additional_data.get('page_url') or additional_data.get('url')
                from_route = additional_data.get('from_route')
                to_route = additional_data.get('to_route')
                navigation_type = additional_data.get('navigation_type')
                time_spent_seconds = additional_data.get('time_spent_seconds') or additional_data.get('time_spent')
                # Cap time_spent at 15 minutes (900s) to filter out idle tabs
                if time_spent_seconds is not None:
                    try:
                        time_spent_seconds = min(float(time_spent_seconds), 900)
                    except (ValueError, TypeError):
                        pass
                session_page_count = additional_data.get('session_page_count')
                session_id = additional_data.get('session_id')

            analytics_db = get_analytics_db()
            analytics_table = get_analytics_table()

            print(f"[DEBUG ANALYTICS] About to connect to database: {analytics_db}")
            print(f"[DEBUG ANALYTICS] Table name: {analytics_table}")

            # Save to database - FIXED INSERT STATEMENT
            with Database.connect(analytics_db) as conn:
                cursor = conn.cursor()

                # Auto-create table if it doesn't exist (self-healing on first request)
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {analytics_table} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ip TEXT,
                        country TEXT,
                        region TEXT,
                        city TEXT,
                        timestamp TEXT NOT NULL,
                        user_agent TEXT,
                        referer TEXT,
                        fingerprint TEXT,
                        event_type TEXT NOT NULL,
                        interaction_type TEXT,
                        additional_data TEXT,
                        identity TEXT,
                        fingerprint_hash TEXT,
                        device_type TEXT,
                        device_confidence TEXT,
                        device_os TEXT,
                        device_brand TEXT,
                        url TEXT,
                        from_route TEXT,
                        to_route TEXT,
                        navigation_type TEXT,
                        time_spent_seconds TEXT,
                        session_page_count TEXT,
                        session_id TEXT
                    )
                """)

                # Auto-add columns if missing (existing DBs)
                cursor.execute(f"PRAGMA table_info({analytics_table})")
                existing_cols = {col[1] for col in cursor.fetchall()}
                if 'session_id' not in existing_cols:
                    cursor.execute(f"ALTER TABLE {analytics_table} ADD COLUMN session_id TEXT")
                if 'user_id' not in existing_cols:
                    cursor.execute(f"ALTER TABLE {analytics_table} ADD COLUMN user_id TEXT")

                # First, let's verify the table structure
                cursor.execute(f"PRAGMA table_info({analytics_table})")
                columns = cursor.fetchall()
                print(f"[DEBUG ANALYTICS] Table columns: {[col[1] for col in columns]}")

                # Use the exact column order from your schema
                insert_sql = f"""
                    INSERT INTO {analytics_table}
                    (ip, country, region, city, timestamp, user_agent, referer, fingerprint,
                     event_type, interaction_type, additional_data, identity, fingerprint_hash,
                     device_type, device_confidence, device_os, device_brand, url, from_route,
                     to_route, navigation_type, time_spent_seconds, session_page_count, session_id,
                     user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

                # Convert fingerprint dict to JSON string for storage
                fingerprint_str = json.dumps(fingerprint) if isinstance(fingerprint, dict) else fingerprint

                # Extract user_id if provided in additional_data
                user_id = additional_data.get('user_id') if additional_data else None

                values = (
                    ip, geo_data['country'], geo_data['region'], geo_data['city'],
                    timestamp, user_agent, referer, fingerprint_str,
                    event_type, interaction_type, additional_data_json, identity, hashed_fingerprint,
                    device_type, device_confidence, device_os, device_brand, url, from_route,
                    to_route, navigation_type, time_spent_seconds, session_page_count, session_id,
                    user_id
                )
                
                print(f"[DEBUG ANALYTICS] Executing insert with {len(values)} values")
                print(f"[DEBUG ANALYTICS] Values: {values}")
                
                cursor.execute(insert_sql, values)
                conn.commit()

                # Verify the insert worked
                cursor.execute(f"SELECT COUNT(*) FROM {analytics_table}")
                count = cursor.fetchone()[0]
                print(f"[DEBUG ANALYTICS] Total records in table after insert: {count}")
                
                print(f"[DEBUG ANALYTICS] Successfully inserted analytics record!")

        except Exception as e:
            import traceback
            print(f"[ERROR ANALYTICS] Failed to log analytics: {e}")
            print(f"[ERROR ANALYTICS] Traceback: {traceback.format_exc()}")

    @staticmethod
    def init_analytics_db():
        """Initialize the analytics database and table"""
        try:
            analytics_db = get_analytics_db()
            analytics_table = get_analytics_table()

            print(f"[DEBUG ANALYTICS] Initializing database: {analytics_db}")
            print(f"[DEBUG ANALYTICS] Table name: {analytics_table}")

            with Database.connect(analytics_db) as conn:
                cursor = conn.cursor()

                # Create analytics_log table matching your exact schema
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {analytics_table} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ip TEXT,
                        country TEXT,
                        region TEXT,
                        city TEXT,
                        timestamp TEXT NOT NULL,
                        user_agent TEXT,
                        referer TEXT,
                        fingerprint TEXT,
                        event_type TEXT NOT NULL,
                        interaction_type TEXT,
                        additional_data TEXT,
                        identity TEXT,
                        fingerprint_hash TEXT,
                        device_type TEXT,
                        device_confidence TEXT,
                        device_os TEXT,
                        device_brand TEXT,
                        url TEXT,
                        from_route TEXT,
                        to_route TEXT,
                        navigation_type TEXT,
                        time_spent_seconds TEXT,
                        session_page_count TEXT,
                        session_id TEXT,
                        user_id TEXT
                    )
                """)

                # Auto-add columns if missing (existing DBs)
                cursor.execute(f"PRAGMA table_info({analytics_table})")
                existing_cols = {col[1] for col in cursor.fetchall()}
                if 'session_id' not in existing_cols:
                    cursor.execute(f"ALTER TABLE {analytics_table} ADD COLUMN session_id TEXT")
                if 'user_id' not in existing_cols:
                    cursor.execute(f"ALTER TABLE {analytics_table} ADD COLUMN user_id TEXT")

                # Create indexes for better performance
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_timestamp ON {analytics_table}(timestamp)")
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_event_type ON {analytics_table}(event_type)")
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_identity ON {analytics_table}(identity)")
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_country ON {analytics_table}(country)")
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_fingerprint ON {analytics_table}(fingerprint)")
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_user_id ON {analytics_table}(user_id)")
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_fingerprint_hash ON {analytics_table}(fingerprint_hash)")

                conn.commit()

                # Verify table creation
                cursor.execute(f"PRAGMA table_info({analytics_table})")
                columns = cursor.fetchall()
                print(f"[DEBUG ANALYTICS] Table created with columns: {[col[1] for col in columns]}")
                
                print("Analytics database table created/verified successfully")

        except Exception as e:
            import traceback
            print(f"Error initializing analytics database: {e}")
            print(f"Traceback: {traceback.format_exc()}")

    @staticmethod
    def get_analytics_summary(days=7):
        """Get comprehensive analytics summary"""
        try:
            analytics_db = get_analytics_db()
            analytics_table = get_analytics_table()

            with Database.connect(analytics_db) as conn:
                cursor = conn.cursor()

                # Get events by type and identity
                cursor.execute(f"""
                    SELECT event_type, identity, COUNT(*)
                    FROM {analytics_table}
                    WHERE datetime(timestamp) >= datetime('now', '-{days} days')
                    GROUP BY event_type, identity
                    ORDER BY COUNT(*) DESC
                """)
                events_by_identity = cursor.fetchall()

                # Get unique users (humans only)
                cursor.execute(f"""
                    SELECT COUNT(DISTINCT fingerprint_hash)
                    FROM {analytics_table}
                    WHERE fingerprint_hash IS NOT NULL
                    AND identity IN ('human', 'likely_human')
                    AND datetime(timestamp) >= datetime('now', '-{days} days')
                """)
                unique_human_users = cursor.fetchone()[0]

                # Get bot vs human ratio
                cursor.execute(f"""
                    SELECT identity, COUNT(*)
                    FROM {analytics_table}
                    WHERE datetime(timestamp) >= datetime('now', '-{days} days')
                    GROUP BY identity
                """)
                identity_breakdown = dict(cursor.fetchall())

                # Get top countries (humans only)
                cursor.execute(f"""
                    SELECT country, COUNT(*)
                    FROM {analytics_table}
                    WHERE datetime(timestamp) >= datetime('now', '-{days} days')
                    AND country NOT IN ('Unknown', 'Local')
                    AND identity IN ('human', 'likely_human')
                    GROUP BY country
                    ORDER BY COUNT(*) DESC
                    LIMIT 5
                """)
                top_countries = cursor.fetchall()

                # Get interaction patterns (humans only)
                cursor.execute(f"""
                    SELECT interaction_type, COUNT(*)
                    FROM {analytics_table}
                    WHERE datetime(timestamp) >= datetime('now', '-{days} days')
                    AND event_type = 'interaction'
                    AND identity IN ('human', 'likely_human')
                    AND interaction_type IS NOT NULL
                    GROUP BY interaction_type
                    ORDER BY COUNT(*) DESC
                """)
                interactions = dict(cursor.fetchall())
                
                return {
                    'events_by_identity': events_by_identity,
                    'unique_human_users': unique_human_users,
                    'identity_breakdown': identity_breakdown,
                    'top_countries': top_countries,
                    'interactions': interactions,
                    'period_days': days
                }
                
        except Exception as e:
            print(f"Failed to get analytics summary: {e}")
            return None

    @staticmethod
    def get_design_analytics_summary(days=7):
        """Get design interaction analytics"""
        try:
            analytics_db = get_analytics_db()
            analytics_table = get_analytics_table()

            with Database.connect(analytics_db) as conn:
                cursor = conn.cursor()

                # Most viewed designs
                cursor.execute(f"""
                    SELECT
                        JSON_EXTRACT(additional_data, '$.design_id') as design_id,
                        JSON_EXTRACT(additional_data, '$.design_title') as design_title,
                        JSON_EXTRACT(additional_data, '$.creator_name') as creator_name,
                        COUNT(*) as view_count
                    FROM {analytics_table}
                    WHERE datetime(timestamp) >= datetime('now', '-{days} days')
                    AND interaction_type = 'design_view'
                    AND identity IN ('human', 'likely_human')
                    GROUP BY JSON_EXTRACT(additional_data, '$.design_id')
                    ORDER BY COUNT(*) DESC
                    LIMIT 20
                """)
                popular_designs = cursor.fetchall()

                # Most viewed prompts
                cursor.execute(f"""
                    SELECT
                        JSON_EXTRACT(additional_data, '$.design_id') as design_id,
                        JSON_EXTRACT(additional_data, '$.design_title') as design_title,
                        JSON_EXTRACT(additional_data, '$.creator_name') as creator_name,
                        COUNT(*) as prompt_views
                    FROM {analytics_table}
                    WHERE datetime(timestamp) >= datetime('now', '-{days} days')
                    AND interaction_type = 'prompt_view'
                    AND identity IN ('human', 'likely_human')
                    GROUP BY JSON_EXTRACT(additional_data, '$.design_id')
                    ORDER BY COUNT(*) DESC
                    LIMIT 20
                """)
                popular_prompts = cursor.fetchall()

                # Social sharing stats
                cursor.execute(f"""
                    SELECT
                        JSON_EXTRACT(additional_data, '$.platform') as platform,
                        COUNT(*) as shares
                    FROM {analytics_table}
                    WHERE datetime(timestamp) >= datetime('now', '-{days} days')
                    AND interaction_type = 'social_share'
                    AND identity IN ('human', 'likely_human')
                    GROUP BY JSON_EXTRACT(additional_data, '$.platform')
                    ORDER BY COUNT(*) DESC
                """)
                social_shares = dict(cursor.fetchall())

                # Etsy click-through stats
                cursor.execute(f"""
                    SELECT
                        JSON_EXTRACT(additional_data, '$.design_id') as design_id,
                        JSON_EXTRACT(additional_data, '$.design_title') as design_title,
                        JSON_EXTRACT(additional_data, '$.listing_id') as listing_id,
                        COUNT(*) as etsy_clicks
                    FROM {analytics_table}
                    WHERE datetime(timestamp) >= datetime('now', '-{days} days')
                    AND interaction_type = 'etsy_buy_click'
                    AND identity IN ('human', 'likely_human')
                    GROUP BY JSON_EXTRACT(additional_data, '$.design_id')
                    ORDER BY COUNT(*) DESC
                    LIMIT 15
                """)
                etsy_clicks = cursor.fetchall()

                # View source breakdown
                cursor.execute(f"""
                    SELECT
                        JSON_EXTRACT(additional_data, '$.view_source') as source,
                        COUNT(*) as views
                    FROM {analytics_table}
                    WHERE datetime(timestamp) >= datetime('now', '-{days} days')
                    AND interaction_type IN ('design_view', 'prompt_view')
                    AND identity IN ('human', 'likely_human')
                    GROUP BY JSON_EXTRACT(additional_data, '$.view_source')
                    ORDER BY COUNT(*) DESC
                """)
                view_sources = dict(cursor.fetchall())
                
                return {
                    'popular_designs': popular_designs,
                    'popular_prompts': popular_prompts,
                    'social_shares': social_shares,
                    'etsy_clicks': etsy_clicks,
                    'view_sources': view_sources,
                    'period_days': days
                }
                
        except Exception as e:
            print(f"Failed to get design analytics: {e}")
            return None

    @staticmethod
    def get_top_creators_by_views(days=7, limit=10):
        """Get creators with most design views"""
        try:
            analytics_db = get_analytics_db()
            analytics_table = get_analytics_table()

            with Database.connect(analytics_db) as conn:
                cursor = conn.cursor()

                cursor.execute(f"""
                    SELECT
                        JSON_EXTRACT(additional_data, '$.creator_name') as creator_name,
                        COUNT(*) as total_views,
                        COUNT(DISTINCT JSON_EXTRACT(additional_data, '$.design_id')) as unique_designs
                    FROM {analytics_table}
                    WHERE datetime(timestamp) >= datetime('now', '-{days} days')
                    AND interaction_type IN ('design_view', 'prompt_view')
                    AND identity IN ('human', 'likely_human')
                    AND JSON_EXTRACT(additional_data, '$.creator_name') IS NOT NULL
                    GROUP BY JSON_EXTRACT(additional_data, '$.creator_name')
                    ORDER BY COUNT(*) DESC
                    LIMIT {limit}
                """)

                return cursor.fetchall()
                
        except Exception as e:
            print(f"Failed to get creator analytics: {e}")
            return []

    @staticmethod
    def test_database_connection():
        """Test the database connection and table structure"""
        try:
            analytics_db = get_analytics_db()
            analytics_table = get_analytics_table()

            print(f"[TEST] Testing database connection to: {analytics_db}")

            with Database.connect(analytics_db) as conn:
                cursor = conn.cursor()

                # Check if table exists
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{analytics_table}'")
                table_exists = cursor.fetchone()
                print(f"[TEST] Table exists: {bool(table_exists)}")

                if table_exists:
                    # Check table structure
                    cursor.execute(f"PRAGMA table_info({analytics_table})")
                    columns = cursor.fetchall()
                    print(f"[TEST] Table columns: {[col[1] for col in columns]}")

                    # Check record count
                    cursor.execute(f"SELECT COUNT(*) FROM {analytics_table}")
                    count = cursor.fetchone()[0]
                    print(f"[TEST] Total records: {count}")

                    # Show recent records
                    cursor.execute(f"SELECT * FROM {analytics_table} ORDER BY timestamp DESC LIMIT 3")
                    recent = cursor.fetchall()
                    print(f"[TEST] Recent records: {len(recent)} found")
                    for record in recent:
                        print(f"[TEST] Record: {record[:5]}...")  # Show first 5 fields

                return True

        except Exception as e:
            import traceback
            print(f"[TEST] Database test failed: {e}")
            print(f"[TEST] Traceback: {traceback.format_exc()}")
            return False

    # =========================================================================
    # Conversion Tracking
    # =========================================================================
    # Call these from Stripe webhook handlers to log purchase conversions.
    # The fingerprint_hash links conversions back to visitor page views
    # for attribution analysis.
    #
    # Usage in a webhook handler:
    #   Analytics.log_conversion(
    #       order_id=order['id'],
    #       order_value=session_data['amount_total'],
    #       customer_email=customer_email,
    #       fingerprint_hash=session_data.get('metadata', {}).get('fingerprint_hash'),
    #       order_type='purchase',
    #       additional_data={'products': ['Product A', 'Product B']}
    #   )
    # =========================================================================

    @staticmethod
    def log_conversion(order_id, order_value, customer_email=None,
                       fingerprint_hash=None, user_id=None,
                       order_type='purchase', currency='GBP',
                       additional_data=None):
        """Log a purchase conversion event to the analytics table.

        Called from Stripe webhook handlers when a checkout completes.
        Links back to the visitor's page views via fingerprint_hash for
        attribution analysis.

        Args:
            order_id: The order/transaction ID
            order_value: Amount in smallest currency unit (pence/cents)
            customer_email: Buyer's email address
            fingerprint_hash: SHA-256 hash from the JS analytics tracker
            user_id: Authenticated user ID (if known)
            order_type: 'purchase', 'subscription', 'donation', 'coffee'
            currency: ISO currency code (default 'GBP')
            additional_data: Extra dict of conversion details
        """
        try:
            analytics_db = get_analytics_db()
            analytics_table = get_analytics_table()
            timestamp = datetime.now().isoformat()

            conversion_data = {
                'order_id': order_id,
                'order_value': order_value,
                'order_value_display': f"£{order_value / 100:.2f}" if order_value else '£0.00',
                'customer_email': customer_email,
                'order_type': order_type,
                'currency': currency,
            }
            if additional_data:
                conversion_data.update(additional_data)

            conversion_json = json.dumps(conversion_data)

            with Database.connect(analytics_db) as conn:
                cursor = conn.cursor()

                # Ensure user_id column exists
                cursor.execute(f"PRAGMA table_info({analytics_table})")
                existing_cols = {col[1] for col in cursor.fetchall()}
                if 'user_id' not in existing_cols:
                    cursor.execute(f"ALTER TABLE {analytics_table} ADD COLUMN user_id TEXT")

                cursor.execute(f"""
                    INSERT INTO {analytics_table}
                    (timestamp, event_type, interaction_type, additional_data,
                     fingerprint_hash, identity, user_id)
                    VALUES (?, 'conversion', ?, ?, ?, 'human', ?)
                """, (timestamp, order_type, conversion_json,
                      fingerprint_hash, user_id))
                conn.commit()

            print(f"[ANALYTICS] Conversion logged: order {order_id}, "
                  f"value {order_value}, type {order_type}")

        except Exception as e:
            print(f"[ERROR ANALYTICS] Failed to log conversion: {e}")
            try:
                from lozzalingo.core import db_log
                db_log('error', 'analytics', 'Failed to log conversion', {
                    'order_id': order_id, 'error': str(e)
                })
            except Exception:
                pass

    @staticmethod
    def link_user(fingerprint_hash, user_id, email=None):
        """Link an anonymous visitor (by fingerprint) to an authenticated user.

        Call this when a user logs in or completes checkout so that their
        prior anonymous page views can be attributed to them.

        Args:
            fingerprint_hash: The visitor's fingerprint hash
            user_id: The authenticated user ID (or email as fallback)
            email: Optional email to store alongside user_id
        """
        try:
            analytics_db = get_analytics_db()
            analytics_table = get_analytics_table()

            with Database.connect(analytics_db) as conn:
                cursor = conn.cursor()

                # Ensure user_id column exists
                cursor.execute(f"PRAGMA table_info({analytics_table})")
                existing_cols = {col[1] for col in cursor.fetchall()}
                if 'user_id' not in existing_cols:
                    cursor.execute(f"ALTER TABLE {analytics_table} ADD COLUMN user_id TEXT")

                # Update all records for this fingerprint that don't have a user_id yet
                cursor.execute(f"""
                    UPDATE {analytics_table}
                    SET user_id = ?
                    WHERE fingerprint_hash = ?
                    AND (user_id IS NULL OR user_id = '')
                """, (str(user_id), fingerprint_hash))

                updated = cursor.rowcount
                conn.commit()

            print(f"[ANALYTICS] Linked user {user_id} to fingerprint "
                  f"{fingerprint_hash[:12]}... ({updated} records updated)")

        except Exception as e:
            print(f"[ERROR ANALYTICS] Failed to link user: {e}")

    # =========================================================================
    # Attribution Queries
    # =========================================================================
    # These methods join conversion events back to first-touch page views
    # to answer: which content, referrers, and campaigns drive revenue?
    # =========================================================================

    @staticmethod
    def get_conversion_attribution(days=30, limit=20):
        """Get conversion attribution data: which referrer sources drive purchases.

        Joins conversion events to the earliest page_view_client for the same
        fingerprint_hash, extracting the referrer source/medium/campaign from
        the first touch.

        Returns list of dicts: {source, medium, campaign, conversions,
                                total_revenue, avg_order_value}
        """
        try:
            analytics_db = get_analytics_db()
            analytics_table = get_analytics_table()

            with Database.connect(analytics_db) as conn:
                cursor = conn.cursor()

                cursor.execute(f"""
                    WITH first_touch AS (
                        SELECT
                            fingerprint_hash,
                            MIN(timestamp) as first_visit,
                            -- Extract referrer info from the earliest page view
                            JSON_EXTRACT(additional_data, '$.referrer_info.source') as source,
                            JSON_EXTRACT(additional_data, '$.referrer_info.medium') as medium,
                            JSON_EXTRACT(additional_data, '$.referrer_info.campaign') as campaign,
                            url as landing_page
                        FROM {analytics_table}
                        WHERE event_type = 'page_view_client'
                        AND fingerprint_hash IS NOT NULL
                        AND datetime(timestamp) >= datetime('now', '-{days} days')
                        GROUP BY fingerprint_hash
                    ),
                    conversions AS (
                        SELECT
                            fingerprint_hash,
                            JSON_EXTRACT(additional_data, '$.order_value') as order_value,
                            timestamp as conversion_time
                        FROM {analytics_table}
                        WHERE event_type = 'conversion'
                        AND datetime(timestamp) >= datetime('now', '-{days} days')
                    )
                    SELECT
                        COALESCE(ft.source, 'direct') as source,
                        COALESCE(ft.medium, 'none') as medium,
                        COALESCE(ft.campaign, '') as campaign,
                        COUNT(*) as conversions,
                        COALESCE(SUM(c.order_value), 0) as total_revenue,
                        COALESCE(AVG(c.order_value), 0) as avg_order_value
                    FROM conversions c
                    LEFT JOIN first_touch ft ON c.fingerprint_hash = ft.fingerprint_hash
                    GROUP BY ft.source, ft.medium, ft.campaign
                    ORDER BY total_revenue DESC
                    LIMIT {limit}
                """)

                columns = ['source', 'medium', 'campaign', 'conversions',
                           'total_revenue', 'avg_order_value']
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]

                # Add display values
                for r in results:
                    r['total_revenue_display'] = f"£{(r['total_revenue'] or 0) / 100:.2f}"
                    r['avg_order_value_display'] = f"£{(r['avg_order_value'] or 0) / 100:.2f}"

                return results

        except Exception as e:
            print(f"[ERROR ANALYTICS] Failed to get conversion attribution: {e}")
            return []

    @staticmethod
    def get_landing_page_performance(days=30, limit=20):
        """Get landing page conversion performance.

        Which pages do visitors first land on, and which of those
        pages lead to the most conversions?

        Returns list of dicts: {landing_page, visitors, conversions,
                                conversion_rate, total_revenue}
        """
        try:
            analytics_db = get_analytics_db()
            analytics_table = get_analytics_table()

            with Database.connect(analytics_db) as conn:
                cursor = conn.cursor()

                cursor.execute(f"""
                    WITH first_touch AS (
                        SELECT
                            fingerprint_hash,
                            MIN(timestamp) as first_visit,
                            url as landing_page
                        FROM {analytics_table}
                        WHERE event_type = 'page_view_client'
                        AND fingerprint_hash IS NOT NULL
                        AND url IS NOT NULL
                        AND identity IN ('human', 'likely_human')
                        AND datetime(timestamp) >= datetime('now', '-{days} days')
                        GROUP BY fingerprint_hash
                    ),
                    page_visitors AS (
                        SELECT
                            landing_page,
                            COUNT(*) as visitors,
                            GROUP_CONCAT(fingerprint_hash) as fps
                        FROM first_touch
                        GROUP BY landing_page
                    ),
                    page_conversions AS (
                        SELECT
                            ft.landing_page,
                            COUNT(*) as conversions,
                            COALESCE(SUM(JSON_EXTRACT(c.additional_data, '$.order_value')), 0) as total_revenue
                        FROM {analytics_table} c
                        JOIN first_touch ft ON c.fingerprint_hash = ft.fingerprint_hash
                        WHERE c.event_type = 'conversion'
                        GROUP BY ft.landing_page
                    )
                    SELECT
                        pv.landing_page,
                        pv.visitors,
                        COALESCE(pc.conversions, 0) as conversions,
                        CASE WHEN pv.visitors > 0
                            THEN ROUND(CAST(COALESCE(pc.conversions, 0) AS FLOAT) / pv.visitors * 100, 2)
                            ELSE 0 END as conversion_rate,
                        COALESCE(pc.total_revenue, 0) as total_revenue
                    FROM page_visitors pv
                    LEFT JOIN page_conversions pc ON pv.landing_page = pc.landing_page
                    ORDER BY COALESCE(pc.total_revenue, 0) DESC, pv.visitors DESC
                    LIMIT {limit}
                """)

                columns = ['landing_page', 'visitors', 'conversions',
                           'conversion_rate', 'total_revenue']
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]

                for r in results:
                    r['total_revenue_display'] = f"£{(r['total_revenue'] or 0) / 100:.2f}"

                return results

        except Exception as e:
            print(f"[ERROR ANALYTICS] Failed to get landing page performance: {e}")
            return []

    @staticmethod
    def get_campaign_revenue(days=30, limit=20):
        """Get revenue breakdown by UTM campaign.

        Returns list of dicts: {utm_source, utm_medium, utm_campaign,
                                visitors, conversions, total_revenue}
        """
        try:
            analytics_db = get_analytics_db()
            analytics_table = get_analytics_table()

            with Database.connect(analytics_db) as conn:
                cursor = conn.cursor()

                cursor.execute(f"""
                    WITH utm_visitors AS (
                        SELECT
                            fingerprint_hash,
                            JSON_EXTRACT(additional_data, '$.referrer_info.utm_source') as utm_source,
                            JSON_EXTRACT(additional_data, '$.referrer_info.utm_medium') as utm_medium,
                            JSON_EXTRACT(additional_data, '$.referrer_info.utm_campaign') as utm_campaign,
                            MIN(timestamp) as first_visit
                        FROM {analytics_table}
                        WHERE event_type = 'page_view_client'
                        AND fingerprint_hash IS NOT NULL
                        AND JSON_EXTRACT(additional_data, '$.referrer_info.utm_source') IS NOT NULL
                        AND datetime(timestamp) >= datetime('now', '-{days} days')
                        GROUP BY fingerprint_hash
                    )
                    SELECT
                        uv.utm_source,
                        uv.utm_medium,
                        uv.utm_campaign,
                        COUNT(DISTINCT uv.fingerprint_hash) as visitors,
                        COUNT(DISTINCT c.fingerprint_hash) as conversions,
                        COALESCE(SUM(JSON_EXTRACT(c.additional_data, '$.order_value')), 0) as total_revenue
                    FROM utm_visitors uv
                    LEFT JOIN {analytics_table} c
                        ON c.fingerprint_hash = uv.fingerprint_hash
                        AND c.event_type = 'conversion'
                    GROUP BY uv.utm_source, uv.utm_medium, uv.utm_campaign
                    ORDER BY total_revenue DESC
                    LIMIT {limit}
                """)

                columns = ['utm_source', 'utm_medium', 'utm_campaign',
                           'visitors', 'conversions', 'total_revenue']
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]

                for r in results:
                    r['total_revenue_display'] = f"£{(r['total_revenue'] or 0) / 100:.2f}"
                    r['conversion_rate'] = round(
                        (r['conversions'] / r['visitors'] * 100) if r['visitors'] > 0 else 0, 2
                    )

                return results

        except Exception as e:
            print(f"[ERROR ANALYTICS] Failed to get campaign revenue: {e}")
            return []

    @staticmethod
    def get_time_to_conversion(days=30):
        """Get average time from first visit to purchase.

        Returns dict: {avg_hours, median_hours, min_hours, max_hours,
                       same_session_pct, total_conversions}
        """
        try:
            analytics_db = get_analytics_db()
            analytics_table = get_analytics_table()

            with Database.connect(analytics_db) as conn:
                cursor = conn.cursor()

                cursor.execute(f"""
                    WITH first_touch AS (
                        SELECT
                            fingerprint_hash,
                            MIN(timestamp) as first_visit
                        FROM {analytics_table}
                        WHERE event_type = 'page_view_client'
                        AND fingerprint_hash IS NOT NULL
                        AND datetime(timestamp) >= datetime('now', '-{days} days')
                        GROUP BY fingerprint_hash
                    ),
                    conversion_times AS (
                        SELECT
                            c.fingerprint_hash,
                            (julianday(c.timestamp) - julianday(ft.first_visit)) * 24 as hours_to_convert
                        FROM {analytics_table} c
                        JOIN first_touch ft ON c.fingerprint_hash = ft.fingerprint_hash
                        WHERE c.event_type = 'conversion'
                        AND datetime(c.timestamp) >= datetime('now', '-{days} days')
                    )
                    SELECT
                        ROUND(AVG(hours_to_convert), 1) as avg_hours,
                        ROUND(MIN(hours_to_convert), 1) as min_hours,
                        ROUND(MAX(hours_to_convert), 1) as max_hours,
                        COUNT(*) as total_conversions,
                        SUM(CASE WHEN hours_to_convert < 0.5 THEN 1 ELSE 0 END) as same_session
                    FROM conversion_times
                """)

                row = cursor.fetchone()
                if not row or row[3] == 0:
                    return {
                        'avg_hours': 0, 'min_hours': 0, 'max_hours': 0,
                        'total_conversions': 0, 'same_session_pct': 0
                    }

                total = row[3]
                same_session = row[4] or 0

                return {
                    'avg_hours': row[0] or 0,
                    'min_hours': row[1] or 0,
                    'max_hours': row[2] or 0,
                    'total_conversions': total,
                    'same_session_pct': round(same_session / total * 100, 1) if total > 0 else 0,
                }

        except Exception as e:
            print(f"[ERROR ANALYTICS] Failed to get time to conversion: {e}")
            return {
                'avg_hours': 0, 'min_hours': 0, 'max_hours': 0,
                'total_conversions': 0, 'same_session_pct': 0
            }

    @staticmethod
    def get_conversion_summary(days=30):
        """Get a high-level conversion summary.

        Returns dict with total conversions, revenue, conversion rate,
        and top referrer sources.
        """
        try:
            analytics_db = get_analytics_db()
            analytics_table = get_analytics_table()

            with Database.connect(analytics_db) as conn:
                cursor = conn.cursor()

                # Total conversions and revenue
                cursor.execute(f"""
                    SELECT
                        COUNT(*) as total_conversions,
                        COALESCE(SUM(JSON_EXTRACT(additional_data, '$.order_value')), 0) as total_revenue
                    FROM {analytics_table}
                    WHERE event_type = 'conversion'
                    AND datetime(timestamp) >= datetime('now', '-{days} days')
                """)
                conv_row = cursor.fetchone()

                # Unique visitors in the same period
                cursor.execute(f"""
                    SELECT COUNT(DISTINCT fingerprint_hash)
                    FROM {analytics_table}
                    WHERE event_type = 'page_view_client'
                    AND fingerprint_hash IS NOT NULL
                    AND identity IN ('human', 'likely_human')
                    AND datetime(timestamp) >= datetime('now', '-{days} days')
                """)
                visitors = cursor.fetchone()[0] or 0

                total_conversions = conv_row[0] or 0
                total_revenue = conv_row[1] or 0
                conversion_rate = round(
                    total_conversions / visitors * 100, 2
                ) if visitors > 0 else 0

                return {
                    'total_conversions': total_conversions,
                    'total_revenue': total_revenue,
                    'total_revenue_display': f"£{total_revenue / 100:.2f}",
                    'unique_visitors': visitors,
                    'conversion_rate': conversion_rate,
                    'period_days': days,
                }

        except Exception as e:
            print(f"[ERROR ANALYTICS] Failed to get conversion summary: {e}")
            return {
                'total_conversions': 0, 'total_revenue': 0,
                'total_revenue_display': '£0.00',
                'unique_visitors': 0, 'conversion_rate': 0,
                'period_days': days,
            }