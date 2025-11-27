import requests
import json
import re
from datetime import datetime, timedelta
from lozzalingo.core import Database, Config
import hashlib
from .referrer_tracker import ReferrerTracker
from flask import request as flask_request

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
        r'googlebot', r'bingbot', r'slurp', r'duckduckbot', r'baiduspider',
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
            url_params = dict(request.args) if hasattr(request, 'args') else {}
            referrer_data = ReferrerTracker.parse_referrer(referer, url_params)

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
                time_spent_seconds = additional_data.get('time_spent_seconds')
                session_page_count = additional_data.get('session_page_count')

            print(f"[DEBUG ANALYTICS] About to connect to database: {Config.ANALYTICS_DB}")
            print(f"[DEBUG ANALYTICS] Table name: {Config.ANALYTICS_TABLE}")

            # Save to database - FIXED INSERT STATEMENT
            with Database.connect(Config.ANALYTICS_DB) as conn:
                cursor = conn.cursor()
                
                # First, let's verify the table structure
                cursor.execute(f"PRAGMA table_info({Config.ANALYTICS_TABLE})")
                columns = cursor.fetchall()
                print(f"[DEBUG ANALYTICS] Table columns: {[col[1] for col in columns]}")
                
                # Use the exact column order from your schema
                insert_sql = f"""
                    INSERT INTO {Config.ANALYTICS_TABLE}
                    (ip, country, region, city, timestamp, user_agent, referer, fingerprint,
                     event_type, interaction_type, additional_data, identity, fingerprint_hash,
                     device_type, device_confidence, device_os, device_brand, url, from_route,
                     to_route, navigation_type, time_spent_seconds, session_page_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                values = (
                    ip, geo_data['country'], geo_data['region'], geo_data['city'],
                    timestamp, user_agent, referer, fingerprint,
                    event_type, interaction_type, additional_data_json, identity, hashed_fingerprint,
                    device_type, device_confidence, device_os, device_brand, url, from_route,
                    to_route, navigation_type, time_spent_seconds, session_page_count
                )
                
                print(f"[DEBUG ANALYTICS] Executing insert with {len(values)} values")
                print(f"[DEBUG ANALYTICS] Values: {values}")
                
                cursor.execute(insert_sql, values)
                conn.commit()
                
                # Verify the insert worked
                cursor.execute(f"SELECT COUNT(*) FROM {Config.ANALYTICS_TABLE}")
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
            print(f"[DEBUG ANALYTICS] Initializing database: {Config.ANALYTICS_DB}")
            print(f"[DEBUG ANALYTICS] Table name: {Config.ANALYTICS_TABLE}")
            
            with Database.connect(Config.ANALYTICS_DB) as conn:
                cursor = conn.cursor()

                # Create analytics_log table matching your exact schema
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {Config.ANALYTICS_TABLE} (
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
                        session_page_count TEXT
                    )
                """)

                # Create indexes for better performance
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_timestamp ON {Config.ANALYTICS_TABLE}(timestamp)")
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_event_type ON {Config.ANALYTICS_TABLE}(event_type)")
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_identity ON {Config.ANALYTICS_TABLE}(identity)")
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_country ON {Config.ANALYTICS_TABLE}(country)")
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_fingerprint ON {Config.ANALYTICS_TABLE}(fingerprint)")

                conn.commit()
                
                # Verify table creation
                cursor.execute(f"PRAGMA table_info({Config.ANALYTICS_TABLE})")
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
            with Database.connect(Config.ANALYTICS_DB) as conn:
                cursor = conn.cursor()
                
                # Get events by type and identity
                cursor.execute(f"""
                    SELECT event_type, identity, COUNT(*) 
                    FROM {Config.ANALYTICS_TABLE} 
                    WHERE datetime(timestamp) >= datetime('now', '-{days} days')
                    GROUP BY event_type, identity
                    ORDER BY COUNT(*) DESC
                """)
                events_by_identity = cursor.fetchall()
                
                # Get unique users (humans only)
                cursor.execute(f"""
                    SELECT COUNT(DISTINCT fingerprint_hash) 
                    FROM {Config.ANALYTICS_TABLE} 
                    WHERE fingerprint_hash IS NOT NULL 
                    AND identity IN ('human', 'likely_human')
                    AND datetime(timestamp) >= datetime('now', '-{days} days')
                """)
                unique_human_users = cursor.fetchone()[0]
                
                # Get bot vs human ratio
                cursor.execute(f"""
                    SELECT identity, COUNT(*) 
                    FROM {Config.ANALYTICS_TABLE} 
                    WHERE datetime(timestamp) >= datetime('now', '-{days} days')
                    GROUP BY identity
                """)
                identity_breakdown = dict(cursor.fetchall())
                
                # Get top countries (humans only)
                cursor.execute(f"""
                    SELECT country, COUNT(*) 
                    FROM {Config.ANALYTICS_TABLE} 
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
                    FROM {Config.ANALYTICS_TABLE} 
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
            with Database.connect(Config.ANALYTICS_DB) as conn:
                cursor = conn.cursor()
                
                # Most viewed designs
                cursor.execute(f"""
                    SELECT 
                        JSON_EXTRACT(additional_data, '$.design_id') as design_id,
                        JSON_EXTRACT(additional_data, '$.design_title') as design_title,
                        JSON_EXTRACT(additional_data, '$.creator_name') as creator_name,
                        COUNT(*) as view_count
                    FROM {Config.ANALYTICS_TABLE}
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
                    FROM {Config.ANALYTICS_TABLE}
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
                    FROM {Config.ANALYTICS_TABLE}
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
                    FROM {Config.ANALYTICS_TABLE}
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
                    FROM {Config.ANALYTICS_TABLE}
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
            with Database.connect(Config.ANALYTICS_DB) as conn:
                cursor = conn.cursor()
                
                cursor.execute(f"""
                    SELECT 
                        JSON_EXTRACT(additional_data, '$.creator_name') as creator_name,
                        COUNT(*) as total_views,
                        COUNT(DISTINCT JSON_EXTRACT(additional_data, '$.design_id')) as unique_designs
                    FROM {Config.ANALYTICS_TABLE}
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
            print(f"[TEST] Testing database connection to: {Config.ANALYTICS_DB}")
            
            with Database.connect(Config.ANALYTICS_DB) as conn:
                cursor = conn.cursor()
                
                # Check if table exists
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{Config.ANALYTICS_TABLE}'")
                table_exists = cursor.fetchone()
                print(f"[TEST] Table exists: {bool(table_exists)}")
                
                if table_exists:
                    # Check table structure
                    cursor.execute(f"PRAGMA table_info({Config.ANALYTICS_TABLE})")
                    columns = cursor.fetchall()
                    print(f"[TEST] Table columns: {[col[1] for col in columns]}")
                    
                    # Check record count
                    cursor.execute(f"SELECT COUNT(*) FROM {Config.ANALYTICS_TABLE}")
                    count = cursor.fetchone()[0]
                    print(f"[TEST] Total records: {count}")
                    
                    # Show recent records
                    cursor.execute(f"SELECT * FROM {Config.ANALYTICS_TABLE} ORDER BY timestamp DESC LIMIT 3")
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