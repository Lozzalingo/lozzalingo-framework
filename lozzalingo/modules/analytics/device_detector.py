import json
import re
from datetime import datetime
from lozzalingo.core import Database, Config
import hashlib
from .analytics import Analytics

class DeviceDetector:
    """Server-side device detection for analytics"""
    
    # Operating system patterns
    OS_PATTERNS = {
        'windows': [r'windows nt', r'win32', r'win64', r'windows'],
        'macos': [r'mac os x', r'macintosh', r'darwin'],
        'ios': [r'iphone', r'ipad', r'ipod'],
        'android': [r'android'],
        'linux': [r'linux', r'ubuntu', r'debian', r'fedora'],
        'chromeos': [r'cros', r'chromeos'],
        'unix': [r'unix', r'bsd'],
    }
    
    # Brand/manufacturer patterns
    BRAND_PATTERNS = {
        # Apple
        'apple': [r'iphone', r'ipad', r'ipod', r'mac os x', r'macintosh'],
        # Google
        'google': [r'pixel', r'nexus', r'chromebook'],
        # Samsung
        'samsung': [r'samsung', r'sm-', r'galaxy', r'gt-'],
        # Microsoft
        'microsoft': [r'windows phone', r'windows nt', r'xbox', r'surface'],
        # Manufacturers
        'huawei': [r'huawei', r'honor'],
        'xiaomi': [r'xiaomi', r'mi ', r'redmi'],
        'oneplus': [r'oneplus'],
        'sony': [r'sony', r'xperia', r'playstation'],
        'lg': [r'lg-', r'lge'],
        'htc': [r'htc'],
        'motorola': [r'motorola', r'moto'],
        'oppo': [r'oppo'],
        'vivo': [r'vivo'],
        'nokia': [r'nokia'],
        'lenovo': [r'lenovo'],
        'asus': [r'asus'],
        'acer': [r'acer'],
        'hp': [r'hp ', r'hewlett'],
        'dell': [r'dell'],
    }
    
    # Device patterns
    MOBILE_PATTERNS = [
        r'android.+mobile', r'iphone', r'ipod', r'blackberry', r'iemobile',
        r'opera mini', r'mobile', r'palm', r'windows ce', r'symbian',
        r'webos', r'bada', r'tizen', r'kaios'
    ]
    
    TABLET_PATTERNS = [
        r'ipad', r'android(?!.*mobile)', r'tablet', r'kindle', r'silk',
        r'playbook', r'rim tablet'
    ]
    
    TV_PATTERNS = [
        r'smart-tv', r'googletv', r'appletv', r'hbbtv', r'pov_tv', r'netcast',
        r'roku', r'dlnadoc', r'ce-html', r'xbox', r'playstation'
    ]
    
    CONSOLE_PATTERNS = [
        r'nintendo', r'xbox', r'playstation', r'vita', r'3ds', r'wii'
    ]
    
    BOT_PATTERNS = [
        r'bot', r'crawler', r'spider', r'scraper', r'scraping'
    ]

    @staticmethod
    def detect_os_and_brand(user_agent):
        """Detect operating system and brand from user agent"""
        if not user_agent:
            return {'os': 'unknown', 'brand': 'unknown'}
        
        ua_lower = user_agent.lower()
        
        # Detect operating system
        detected_os = 'unknown'
        for os_name, patterns in DeviceDetector.OS_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, ua_lower):
                    detected_os = os_name
                    break
            if detected_os != 'unknown':
                break
        
        # Detect brand/manufacturer
        detected_brand = 'unknown'
        for brand_name, patterns in DeviceDetector.BRAND_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, ua_lower):
                    detected_brand = brand_name
                    break
            if detected_brand != 'unknown':
                break
        
        # Special case: if we detect Windows but no specific brand, mark as generic PC
        if detected_os == 'windows' and detected_brand == 'unknown':
            detected_brand = 'pc'
        
        # Special case: if we detect Linux but no specific brand, mark as generic PC  
        if detected_os == 'linux' and detected_brand == 'unknown':
            detected_brand = 'pc'
        
        return {'os': detected_os, 'brand': detected_brand}
    
    @staticmethod
    def detect_device_from_ua(user_agent):
        """Detect device type from user agent only (server-side)"""
        if not user_agent:
            return {'device_type': 'unknown', 'confidence': 0, 'os': 'unknown', 'brand': 'unknown'}
        
        ua_lower = user_agent.lower()
        
        # Get OS and brand info
        os_brand_info = DeviceDetector.detect_os_and_brand(user_agent)
        
        # Check for bots first
        for pattern in DeviceDetector.BOT_PATTERNS:
            if re.search(pattern, ua_lower):
                return {
                    'device_type': 'bot', 
                    'confidence': 90,
                    'os': os_brand_info['os'],
                    'brand': os_brand_info['brand']
                }
        
        device_scores = {
            'mobile': 0,
            'tablet': 0,
            'desktop': 0,
            'tv': 0,
            'console': 0
        }
        
        # User agent pattern matching
        for pattern in DeviceDetector.MOBILE_PATTERNS:
            if re.search(pattern, ua_lower):
                device_scores['mobile'] += 30
        
        for pattern in DeviceDetector.TABLET_PATTERNS:
            if re.search(pattern, ua_lower):
                device_scores['tablet'] += 30
        
        for pattern in DeviceDetector.TV_PATTERNS:
            if re.search(pattern, ua_lower):
                device_scores['tv'] += 40
        
        for pattern in DeviceDetector.CONSOLE_PATTERNS:
            if re.search(pattern, ua_lower):
                device_scores['console'] += 40
        
        # Desktop indicators
        desktop_patterns = [r'windows nt', r'mac os x', r'linux', r'x11']
        for pattern in desktop_patterns:
            if re.search(pattern, ua_lower):
                device_scores['desktop'] += 20
        
        # Browser indicators (usually desktop/laptop)
        browser_patterns = [r'chrome', r'firefox', r'safari', r'edge', r'opera']
        browser_matches = sum(1 for pattern in browser_patterns if re.search(pattern, ua_lower))
        if browser_matches > 0:
            device_scores['desktop'] += 10
        
        # Special cases
        if 'ipad' in ua_lower or ('mac' in ua_lower and 'touch' in ua_lower):
            device_scores['tablet'] += 25
        
        if 'android' in ua_lower and 'mobile' not in ua_lower:
            device_scores['tablet'] += 20
        
        # If no strong indicators, assume desktop
        if all(score < 20 for score in device_scores.values()):
            device_scores['desktop'] = 30
        
        # Find top device type
        top_device = max(device_scores.items(), key=lambda x: x[1])
        
        return {
            'device_type': top_device[0] if top_device[1] > 0 else 'unknown',
            'confidence': min(top_device[1] * 2, 100),  # Scale confidence
            'scores': device_scores,
            'os': os_brand_info['os'],
            'brand': os_brand_info['brand']
        }
    
    @staticmethod
    def detect_device_comprehensive(user_agent, client_data=None):
        """Comprehensive device detection using both UA and client data"""
        # Start with UA detection
        ua_result = DeviceDetector.detect_device_from_ua(user_agent)
        
        if not client_data:
            return ua_result
        
        # Parse client data if it's a JSON string
        if isinstance(client_data, str):
            try:
                client_data = json.loads(client_data)
            except:
                return ua_result
        
        # Extract screen and touch data
        screen_width = client_data.get('screen_resolution', '0x0').split('x')[0]
        screen_height = client_data.get('screen_resolution', '0x0').split('x')[1]
        touch_points = client_data.get('max_touch_points', 0)
        
        try:
            screen_width = int(screen_width)
            screen_height = int(screen_height)
            touch_points = int(touch_points)
        except:
            return ua_result
        
        # Enhanced detection with client data
        device_scores = ua_result.get('scores', {
            'mobile': 0, 'tablet': 0, 'desktop': 0, 'tv': 0, 'console': 0
        })
        
        # Screen size analysis
        screen_area = screen_width * screen_height
        max_dimension = max(screen_width, screen_height)
        
        if max_dimension <= 480:
            device_scores['mobile'] += 30
        elif max_dimension <= 768:
            device_scores['mobile'] += 20
            device_scores['tablet'] += 10
        elif max_dimension <= 1024:
            device_scores['tablet'] += 25
            device_scores['desktop'] += 10
        elif max_dimension <= 1920:
            device_scores['desktop'] += 25
            device_scores['tv'] += 5
        else:
            device_scores['desktop'] += 20
            device_scores['tv'] += 15
        
        # Touch capability
        if touch_points > 0:
            device_scores['mobile'] += 15
            device_scores['tablet'] += 15
        else:
            device_scores['desktop'] += 10
            device_scores['tv'] += 5
        
        # Aspect ratio analysis
        if screen_width > 0 and screen_height > 0:
            aspect_ratio = max(screen_width, screen_height) / min(screen_width, screen_height)
            if aspect_ratio > 2.0:  # Ultra-wide
                device_scores['tv'] += 10
                device_scores['desktop'] += 10
        
        # Find the best match
        top_device = max(device_scores.items(), key=lambda x: x[1])
        
        # Additional metadata
        metadata = {
            'screen_width': screen_width,
            'screen_height': screen_height,
            'screen_area': screen_area,
            'touch_points': touch_points,
            'screen_size_category': DeviceDetector._get_screen_category(max_dimension),
            'is_touch_capable': touch_points > 0,
            'pixel_ratio': client_data.get('pixel_ratio', 1)
        }
        
        return {
            'device_type': top_device[0] if top_device[1] > 0 else 'unknown',
            'confidence': min(top_device[1], 100),
            'scores': device_scores,
            'metadata': metadata,
            'detection_method': 'comprehensive',
            'os': ua_result.get('os', 'unknown'),
            'brand': ua_result.get('brand', 'unknown')
        }
    
    @staticmethod
    def _get_screen_category(max_dimension):
        """Categorize screen size"""
        if max_dimension <= 480:
            return 'extra_small'
        elif max_dimension <= 768:
            return 'small'
        elif max_dimension <= 1024:
            return 'medium'
        elif max_dimension <= 1440:
            return 'large'
        elif max_dimension <= 1920:
            return 'extra_large'
        else:
            return 'ultra_large'


# Enhanced Analytics class with device detection
class EnhancedAnalytics(Analytics):
    """Analytics with enhanced device detection"""
    
    @staticmethod
    def detect_comprehensive_identity(user_agent, has_javascript=False, fingerprint=None, client_data=None):
        """Enhanced identity detection including device information"""
        # Get basic identity
        basic_identity = Analytics.detect_identity(user_agent, has_javascript, fingerprint)
        
        # Get device information
        device_info = DeviceDetector.detect_device_comprehensive(user_agent, client_data)
        
        # Combine insights
        if device_info['device_type'] == 'bot':
            return 'bot'
        
        # If we detected a specific device type with high confidence, factor that in
        if device_info['confidence'] > 70:
            if basic_identity in ['human', 'likely_human'] and device_info['device_type'] in ['mobile', 'tablet', 'desktop']:
                return 'human'
            elif basic_identity == 'possible_human' and device_info['device_type'] in ['mobile', 'tablet', 'desktop']:
                return 'likely_human'
        
        return basic_identity
    
    @staticmethod
    def log_comprehensive_analytics(request, event_type, email=None, fingerprint=None, 
                                interaction_type=None, additional_data=None):
        """Enhanced logging with device detection and URL tracking"""
        try:
            # Get basic data
            ip = Analytics.get_client_ip(request)
            user_agent = request.headers.get('User-Agent', '')[:500]
            referer = request.headers.get('Referer', '')[:500] or None
            timestamp = datetime.utcnow().isoformat()
            
            # Extract URL from additional_data or request
            url = None
            if additional_data and 'page_url' in additional_data:
                url = additional_data['page_url'][:500]  # Limit URL length
            elif hasattr(request, 'url'):
                # Fallback to request URL if available
                url = request.url[:500]
            
            # Filter out URLs containing 'api' - skip logging
            if url and 'api' in url.lower():
                return
            
            # Process email
            email = email.strip().lower() if email else None
            
            # Get geo data
            geo_data = Analytics.get_geo_data(ip)
            
            # Enhanced device and identity detection
            client_data = additional_data.get('client_data') if additional_data else None
            device_info = DeviceDetector.detect_device_comprehensive(user_agent, client_data)
            
            # Enhanced identity detection
            has_javascript = fingerprint is not None
            identity = EnhancedAnalytics.detect_comprehensive_identity(
                user_agent, has_javascript, fingerprint, client_data
            )
            
            # Extract route change specific data from additional_data to match schema
            navigation_type = additional_data.get('navigation_type') if additional_data else None
            from_route = additional_data.get('from_route') if additional_data else None
            to_route = additional_data.get('to_route') if additional_data else None
            time_spent_seconds = additional_data.get('time_spent_seconds') if additional_data else None
            session_page_count = additional_data.get('session_page_count') if additional_data else None
            
            # Prepare comprehensive data
            comprehensive_data = {
                'has_javascript': has_javascript,
                'request_method': request.method,
                'content_type': request.headers.get('Content-Type', ''),
                'accept_language': request.headers.get('Accept-Language', '')[:100],
                'accept_encoding': request.headers.get('Accept-Encoding', '')[:100],
                'connection': request.headers.get('Connection', ''),
                'dnt': request.headers.get('DNT', ''),
                # Device information
                'device_type': device_info['device_type'],
                'device_confidence': device_info['confidence'],
                'device_os': device_info.get('os', 'unknown'),
                'device_brand': device_info.get('brand', 'unknown'),
                'device_scores': json.dumps(device_info.get('scores', {})),
                'device_metadata': json.dumps(device_info.get('metadata', {})),
                'detection_method': device_info.get('detection_method', 'ua_only')
            }
            
            # Merge with provided additional data
            if additional_data:
                comprehensive_data.update(additional_data)
            
            # Serialize additional data
            additional_data_json = json.dumps(comprehensive_data)

            # Hash the fingerprint if it exists
            fingerprint_hash = None
            if fingerprint:
                fingerprint_hash = hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()

            # Insert into database (matching existing schema)
            with Database.connect(Config.ANALYTICS_DB) as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    INSERT INTO {Config.ANALYTICS_TABLE} 
                    (ip, country, region, city, timestamp, user_agent, referer, email, 
                    fingerprint, event_type, interaction_type, additional_data, identity, 
                    fingerprint_hash, device_type, device_confidence, device_os, device_brand, url,
                    from_route, to_route, navigation_type, time_spent_seconds, session_page_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (ip, geo_data['country'], geo_data['region'], geo_data['city'], 
                    timestamp, user_agent, referer, email, fingerprint, event_type, 
                    interaction_type, additional_data_json, identity, fingerprint_hash,
                    device_info['device_type'], device_info['confidence'],
                    device_info.get('os', 'unknown'), device_info.get('brand', 'unknown'), url,
                    from_route, to_route, navigation_type, str(time_spent_seconds) if time_spent_seconds else None,
                    str(session_page_count) if session_page_count else None))
                conn.commit()
                
                # Enhanced logging output
                log_parts = [
                    f"Logged {event_type}",
                    f"from {identity}",
                    f"on {device_info['device_type']}",
                    f"({device_info.get('os', 'unknown')}/{device_info.get('brand', 'unknown')})",
                    f"({device_info['confidence']}% confidence)",
                    f"at {ip}"
                ]
                
                if email:
                    log_parts.append(f"({email})")
                else:
                    log_parts.append("(anonymous)")
                
                if url:
                    log_parts.append(f"- URL: {url}")
                
                # Add route change info to log if present
                if navigation_type and from_route and to_route:
                    log_parts.append(f"- Route: {from_route} -> {to_route} ({navigation_type})")
                    if time_spent_seconds:
                        log_parts.append(f"- Time spent: {time_spent_seconds}s")
                
                if session_page_count:
                    log_parts.append(f"- Session pages: {session_page_count}")
                
                
                print(" ".join(log_parts))
                    
        except Exception as e:
            print(f"Failed to log enhanced analytics: {e}")
    
    @staticmethod
    def get_device_analytics_summary(days=7):
        """Get device-specific analytics summary"""
        try:
            with Database.connect(Config.ANALYTICS_DB) as conn:
                cursor = conn.cursor()
                
                # Device type breakdown
                cursor.execute(f"""
                    SELECT device_type, COUNT(*), AVG(device_confidence)
                    FROM {Config.ANALYTICS_TABLE} 
                    WHERE datetime(timestamp) >= datetime('now', '-{days} days')
                    AND identity IN ('human', 'likely_human')
                    GROUP BY device_type
                    ORDER BY COUNT(*) DESC
                """)
                device_breakdown = cursor.fetchall()
                
                # Popular screen sizes
                cursor.execute(f"""
                    SELECT json_extract(additional_data, '$.screen_resolution') as resolution, COUNT(*)
                    FROM {Config.ANALYTICS_TABLE} 
                    WHERE datetime(timestamp) >= datetime('now', '-{days} days')
                    AND identity IN ('human', 'likely_human')
                    AND json_extract(additional_data, '$.screen_resolution') IS NOT NULL
                    GROUP BY resolution
                    ORDER BY COUNT(*) DESC
                    LIMIT 10
                """)
                screen_sizes = cursor.fetchall()
                
                return {
                    'device_breakdown': device_breakdown,
                    'popular_screen_sizes': screen_sizes,
                    'period_days': days
                }
                
        except Exception as e:
            print(f"Failed to get device analytics summary: {e}")
            return None