"""
Cross-Post Service
==================

Singleton service for cross-posting content to LinkedIn, Medium, and Substack.
Lazy-initialized from Flask app config (same pattern as email_service).
"""

import os
from .content_transform import html_to_plain_text, html_for_medium
from .platforms import linkedin, medium, substack


class CrossPostService:
    """Cross-posting service — reads config from Flask app.config at call time."""

    def _get_config(self, key, default=''):
        """Get config value: app.config > Config class > env var."""
        try:
            from flask import current_app
            val = current_app.config.get(key)
            if val:
                return val
        except RuntimeError:
            pass
        try:
            from config import Config
            if hasattr(Config, key):
                return getattr(Config, key)
        except ImportError:
            pass
        return os.getenv(key, default)

    def post_to_linkedin(self, title, excerpt, canonical_url, image_url=None):
        """
        Post an article share to LinkedIn.

        Returns:
            dict with {success: bool, url: str, error: str}
        """
        token_file = self._get_config('CROSSPOST_LINKEDIN_TOKEN_FILE')
        if not token_file:
            return {'success': False, 'url': '', 'error': 'CROSSPOST_LINKEDIN_TOKEN_FILE not configured'}

        # Ensure excerpt is plain text
        plain_excerpt = html_to_plain_text(excerpt) if excerpt else ''
        # Truncate for LinkedIn (max ~700 chars for commentary is reasonable)
        if len(plain_excerpt) > 500:
            plain_excerpt = plain_excerpt[:497] + '...'

        return linkedin.post_article_share(
            token_file=token_file,
            title=title,
            excerpt=plain_excerpt,
            canonical_url=canonical_url,
            image_url=image_url,
        )

    def post_to_medium(self, title, html_content, canonical_url, tags=None):
        """
        Publish a full article to Medium.

        Returns:
            dict with {success: bool, url: str, error: str}
        """
        token = self._get_config('CROSSPOST_MEDIUM_TOKEN')
        if not token:
            return {'success': False, 'url': '', 'error': 'CROSSPOST_MEDIUM_TOKEN not configured'}

        site_url = self._get_config('EMAIL_WEBSITE_URL', '')
        processed_html = html_for_medium(html_content, site_url)

        return medium.publish_article(
            token=token,
            title=title,
            html_content=processed_html,
            canonical_url=canonical_url,
            tags=tags,
        )

    def post_to_substack(self, title, html_content, canonical_url=None):
        """
        Publish a full article to Substack.

        Returns:
            dict with {success: bool, url: str, error: str}
        """
        cookie = self._get_config('CROSSPOST_SUBSTACK_COOKIE')
        substack_url = self._get_config('CROSSPOST_SUBSTACK_URL')

        if not cookie:
            return {'success': False, 'url': '', 'error': 'CROSSPOST_SUBSTACK_COOKIE not configured'}
        if not substack_url:
            return {'success': False, 'url': '', 'error': 'CROSSPOST_SUBSTACK_URL not configured'}

        return substack.publish_article(
            cookie=cookie,
            substack_url=substack_url,
            title=title,
            html_content=html_content,
            canonical_url=canonical_url,
        )


# Singleton instance (same pattern as email_service)
crosspost_service = CrossPostService()
