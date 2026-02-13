"""
Enhanced Referrer Tracking System
Provides comprehensive referrer detection and categorization for analytics
"""

import re
from urllib.parse import urlparse, parse_qs
from typing import Dict, Optional, Tuple


class ReferrerTracker:
    """Enhanced referrer tracking and categorization"""

    # Social media platforms and their patterns
    SOCIAL_PLATFORMS = {
        'facebook.com': 'Facebook',
        'fb.me': 'Facebook',
        'instagram.com': 'Instagram',
        'twitter.com': 'Twitter/X',
        'x.com': 'Twitter/X',
        't.co': 'Twitter/X',
        'linkedin.com': 'LinkedIn',
        'youtube.com': 'YouTube',
        'youtu.be': 'YouTube',
        'tiktok.com': 'TikTok',
        'pinterest.com': 'Pinterest',
        'reddit.com': 'Reddit',
        'redd.it': 'Reddit',
        'snapchat.com': 'Snapchat',
        'whatsapp.com': 'WhatsApp',
        'telegram.org': 'Telegram',
        't.me': 'Telegram',
        'discord.gg': 'Discord',
        'discord.com': 'Discord'
    }

    # Search engines
    SEARCH_ENGINES = {
        'google.com': 'Google',
        'google.co.uk': 'Google',
        'google.pt': 'Google',
        'bing.com': 'Bing',
        'yahoo.com': 'Yahoo',
        'duckduckgo.com': 'DuckDuckGo',
        'yandex.com': 'Yandex',
        'baidu.com': 'Baidu',
        'com.google.android.googlequicksearchbox': 'Android Quick Search'
    }

    # Sports/MMA platforms
    SPORTS_PLATFORMS = {
        'ufc.com': 'UFC',
        'sherdog.com': 'Sherdog',
        'mmajunkie.usatoday.com': 'MMA Junkie',
        'mmamania.com': 'MMA Mania',
        'bloodyelbow.com': 'Bloody Elbow',
        'mmafighting.com': 'MMA Fighting',
        'espn.com': 'ESPN',
        'cbssports.com': 'CBS Sports',
        'si.com': 'Sports Illustrated'
    }

    # Portuguese media
    PORTUGUESE_MEDIA = {
        'record.pt': 'Record',
        'ojogo.pt': 'O Jogo',
        'abola.pt': 'A Bola',
        'rtp.pt': 'RTP',
        'publico.pt': 'Público',
        'observador.pt': 'Observador',
        'dn.pt': 'Diário de Notícias',
        'correiodemanha.pt': 'Correio da Manhã'
    }

    @staticmethod
    def parse_referrer(referrer_url: Optional[str], url_params: Dict = None) -> Dict:
        """
        Parse and categorize referrer information

        Args:
            referrer_url: The HTTP referer header value
            url_params: URL parameters from the current request

        Returns:
            Dict with referrer analysis results
        """
        result = {
            'source': 'Direct',
            'medium': 'direct',
            'campaign': None,
            'content': None,
            'term': None,
            'category': 'Direct Traffic',
            'platform': None,
            'is_social': False,
            'is_search': False,
            'is_internal': False,
            'raw_referrer': referrer_url,
            'utm_source': None,
            'utm_medium': None,
            'utm_campaign': None,
            'utm_content': None,
            'utm_term': None
        }

        # Parse URL parameters for UTM tracking
        if url_params:
            result.update(ReferrerTracker._parse_utm_params(url_params))

        # If no referrer URL, check for URL parameters
        if not referrer_url:
            if result['utm_source']:
                result['source'] = result['utm_source']
                result['medium'] = result['utm_medium'] or 'campaign'
                result['category'] = 'Campaign Traffic'
            return result

        # Parse the referrer URL
        try:
            parsed = urlparse(referrer_url)
            hostname = parsed.hostname

            if not hostname:
                return result

            hostname = hostname.lower().replace('www.', '')

            # Check if internal (self-referral)
            # Check against configured site domains + localhost
            internal_hosts = ['localhost', '127.0.0.1']
            try:
                from flask import current_app
                site_url = current_app.config.get('EMAIL_WEBSITE_URL', '')
                if site_url:
                    site_host = urlparse(site_url).hostname
                    if site_host:
                        internal_hosts.append(site_host.replace('www.', ''))
            except (RuntimeError, ImportError):
                pass
            if hostname in internal_hosts:
                result.update({
                    'source': 'Internal',
                    'medium': 'internal',
                    'category': 'Internal Navigation',
                    'is_internal': True
                })

                # Check for Facebook click tracking on internal referrals
                # (fbclid fallback — UTM override below takes priority)
                if 'fbclid=' in referrer_url:
                    result.update({
                        'source': 'Facebook',
                        'medium': 'social',
                        'category': 'Social Media',
                        'platform': 'Facebook',
                        'is_social': True,
                        'is_internal': False
                    })

            else:
                # Categorize external referrers
                result.update(ReferrerTracker._categorize_external_referrer(hostname, referrer_url))

        except Exception as e:
            print(f"Error parsing referrer URL: {e}")
            result.update({
                'source': 'Unknown',
                'medium': 'referral',
                'category': 'Other',
                'raw_referrer': referrer_url
            })

        # Override with UTM parameters if available — these are the most
        # reliable signal (e.g. utm_source=ig from Instagram mobile)
        if result['utm_source']:
            utm_key = result['utm_source'].lower()
            mapped = ReferrerTracker.UTM_SOURCE_MAP.get(utm_key)
            if mapped:
                source, medium, category, is_social, is_search = mapped
                result['source'] = source
                result['medium'] = result['utm_medium'] or medium
                result['category'] = category
                result['platform'] = source
                result['is_social'] = is_social
                result['is_search'] = is_search
                result['is_internal'] = False
            else:
                result['source'] = result['utm_source']
                result['medium'] = result['utm_medium'] or result['medium']
            if result['utm_campaign']:
                result['campaign'] = result['utm_campaign']
                result['category'] = 'Campaign Traffic'

        return result

    # Map common utm_source shorthand values to canonical platform names
    UTM_SOURCE_MAP = {
        'ig': ('Instagram', 'social', 'Social Media', True, False),
        'instagram': ('Instagram', 'social', 'Social Media', True, False),
        'fb': ('Facebook', 'social', 'Social Media', True, False),
        'facebook': ('Facebook', 'social', 'Social Media', True, False),
        'tw': ('Twitter/X', 'social', 'Social Media', True, False),
        'twitter': ('Twitter/X', 'social', 'Social Media', True, False),
        'x': ('Twitter/X', 'social', 'Social Media', True, False),
        'li': ('LinkedIn', 'social', 'Social Media', True, False),
        'linkedin': ('LinkedIn', 'social', 'Social Media', True, False),
        'yt': ('YouTube', 'social', 'Social Media', True, False),
        'youtube': ('YouTube', 'social', 'Social Media', True, False),
        'tiktok': ('TikTok', 'social', 'Social Media', True, False),
        'tt': ('TikTok', 'social', 'Social Media', True, False),
        'pinterest': ('Pinterest', 'social', 'Social Media', True, False),
        'reddit': ('Reddit', 'social', 'Social Media', True, False),
        'whatsapp': ('WhatsApp', 'social', 'Social Media', True, False),
        'telegram': ('Telegram', 'social', 'Social Media', True, False),
        'google': ('Google', 'cpc', 'Search Engine', False, True),
        'bing': ('Bing', 'cpc', 'Search Engine', False, True),
    }

    @staticmethod
    def _parse_utm_params(url_params: Dict) -> Dict:
        """Extract UTM parameters from URL"""
        return {
            'utm_source': url_params.get('utm_source'),
            'utm_medium': url_params.get('utm_medium'),
            'utm_campaign': url_params.get('utm_campaign'),
            'utm_content': url_params.get('utm_content'),
            'utm_term': url_params.get('utm_term')
        }

    @staticmethod
    def _categorize_external_referrer(hostname: str, full_url: str) -> Dict:
        """Categorize external referrer based on hostname and URL patterns"""
        result = {
            'source': hostname,
            'medium': 'referral',
            'category': 'Referral',
            'platform': None,
            'is_social': False,
            'is_search': False
        }

        # Check social media platforms
        for domain, platform in ReferrerTracker.SOCIAL_PLATFORMS.items():
            if domain in hostname:
                result.update({
                    'source': platform,
                    'medium': 'social',
                    'category': 'Social Media',
                    'platform': platform,
                    'is_social': True
                })
                return result

        # Check search engines (including Android app package names)
        for domain, engine in ReferrerTracker.SEARCH_ENGINES.items():
            if domain in hostname or domain in full_url:
                # Extract search query if possible
                search_term = ReferrerTracker._extract_search_term(full_url)
                result.update({
                    'source': engine,
                    'medium': 'organic',
                    'category': 'Search Engine',
                    'platform': engine,
                    'is_search': True,
                    'term': search_term
                })
                return result

        # Check sports/MMA platforms
        for domain, platform in ReferrerTracker.SPORTS_PLATFORMS.items():
            if domain in hostname:
                result.update({
                    'source': platform,
                    'medium': 'referral',
                    'category': 'Sports Media',
                    'platform': platform
                })
                return result

        # Check Portuguese media
        for domain, platform in ReferrerTracker.PORTUGUESE_MEDIA.items():
            if domain in hostname:
                result.update({
                    'source': platform,
                    'medium': 'referral',
                    'category': 'Portuguese Media',
                    'platform': platform
                })
                return result

        # Check for Facebook click tracking parameters
        if 'fbclid=' in full_url:
            result.update({
                'source': 'Facebook',
                'medium': 'social',
                'category': 'Social Media',
                'platform': 'Facebook',
                'is_social': True
            })
            return result

        # Check for other social tracking parameters
        if any(param in full_url for param in ['igshid=', 'utm_source=ig']):
            result.update({
                'source': 'Instagram',
                'medium': 'social',
                'category': 'Social Media',
                'platform': 'Instagram',
                'is_social': True
            })
            return result

        return result

    @staticmethod
    def _extract_search_term(search_url: str) -> Optional[str]:
        """Extract search term from search engine URLs"""
        try:
            parsed = urlparse(search_url)
            query_params = parse_qs(parsed.query)

            # Common search parameter names
            search_params = ['q', 'query', 'search', 'p', 'terms', 'wd']

            for param in search_params:
                if param in query_params:
                    terms = query_params[param]
                    if terms and terms[0]:
                        return terms[0]

        except Exception:
            pass

        return None

    @staticmethod
    def generate_display_name(referrer_data: Dict) -> str:
        """Generate a user-friendly display name for the traffic source"""
        if referrer_data['category'] == 'Campaign Traffic':
            if referrer_data['campaign']:
                return f"{referrer_data['source']} ({referrer_data['campaign']})"
            return referrer_data['source']

        if referrer_data['category'] == 'Social Media':
            return referrer_data['platform'] or referrer_data['source']

        if referrer_data['category'] == 'Search Engine':
            if referrer_data['term']:
                return f"{referrer_data['platform']} ({referrer_data['term'][:30]}...)" if len(referrer_data['term']) > 30 else f"{referrer_data['platform']} ({referrer_data['term']})"
            return referrer_data['platform'] or referrer_data['source']

        # Convert "Internal" to user-friendly "Direct" for display
        if referrer_data['category'] == 'Internal Navigation' or referrer_data['source'] == 'Internal':
            return 'Direct'

        return referrer_data['source']

    @staticmethod
    def get_category_color(category: str) -> str:
        """Get a consistent color for traffic source categories"""
        colors = {
            'Direct Traffic': '#6B7280',
            'Social Media': '#3B82F6',
            'Search Engine': '#10B981',
            'Campaign Traffic': '#F59E0B',
            'Sports Media': '#EF4444',
            'Portuguese Media': '#8B5CF6',
            'Referral': '#06B6D4',
            'Internal Navigation': '#84CC16',
            'Other': '#64748B'
        }
        return colors.get(category, '#64748B')