"""
Thin client for the centralised Blog service.
Sites call this instead of querying local news.db directly.

Usage:
    from lozzalingo.clients.blog_client import BlogClient

    client = BlogClient()  # reads BLOG_SERVICE_URL + BLOG_API_KEY from env

    # List articles
    articles = client.list_articles(site_id='crowd-sauced', status='published')
    # articles = [{"id": 1, "title": "...", "slug": "...", ...}, ...]

    # Get single article
    article = client.get_article(1)

    # Get article by slug
    article = client.get_article_by_slug('my-article', site_id='crowd-sauced')

    # Create article
    result = client.create_article(
        site_id='crowd-sauced',
        title='My Article',
        content_html='<p>Hello</p>',
        status='draft',
    )

    # Update article
    client.update_article(1, {"title": "New Title"})

    # Delete article (soft delete)
    client.delete_article(1)

    # Toggle publish
    client.publish_article(1)
"""

import os

from lozzalingo.core import db_log


class BlogClient:
    """Synchronous client for the centralised Blog service."""

    def __init__(self, service_url=None, api_key=None, timeout=10):
        self.url = (service_url or os.getenv('BLOG_SERVICE_URL', '')).rstrip('/')
        self.key = api_key or os.getenv('BLOG_API_KEY', '')
        self.timeout = timeout

        if not self.url:
            db_log('warning', 'blog_client', 'BLOG_SERVICE_URL not set')

    def _headers(self):
        """Build request headers with authentication."""
        headers = {'Content-Type': 'application/json'}
        if self.key:
            headers['X-API-Key'] = self.key
        return headers

    def _request(self, method, path, json_data=None, params=None):
        """Make an HTTP request to the blog service.

        Returns the parsed JSON response on success, or None on failure.
        Never raises - logs errors and returns None.
        """
        if not self.url:
            db_log('error', 'blog_client', 'Cannot make request, BLOG_SERVICE_URL not set')
            return None

        full_url = f'{self.url}{path}'

        try:
            import requests
            response = requests.request(
                method,
                full_url,
                json=json_data,
                params=params,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            cls = type(e).__name__
            if 'Timeout' in cls:
                db_log('error', 'blog_client', f'Request timed out: {method} {path}')
            elif 'ConnectionError' in cls:
                db_log('error', 'blog_client', f'Connection failed: {method} {path}')
            elif 'HTTPError' in cls:
                resp = getattr(e, 'response', None)
                db_log('error', 'blog_client', f'HTTP error: {method} {path}', {
                    'status': resp.status_code if resp is not None else None,
                    'body': resp.text[:500] if resp is not None else None,
                })
            else:
                db_log('error', 'blog_client', f'Unexpected error: {method} {path}', {
                    'error': str(e),
                })
            return None

    # ------------------------------------------------------------------
    # Articles
    # ------------------------------------------------------------------

    def list_articles(self, site_id, status=None, category_id=None,
                      tag=None, search=None, page=1, per_page=50):
        """List articles with optional filters.

        Args:
            site_id: Identifier for the site.
            status: Filter by status (draft, published, deleted).
            category_id: Filter by category ID.
            tag: Filter by tag.
            search: Search in title and content.
            page: Page number (default 1).
            per_page: Results per page (default 50).

        Returns:
            Dict with articles list, total, page, per_page. Or None.
        """
        params = {'site_id': site_id, 'page': page, 'per_page': per_page}
        if status:
            params['status'] = status
        if category_id:
            params['category_id'] = category_id
        if tag:
            params['tag'] = tag
        if search:
            params['search'] = search
        return self._request('GET', '/api/blog/articles', params=params)

    def get_article(self, article_id):
        """Get a single article by ID.

        Args:
            article_id: The article record ID.

        Returns:
            Dict with article fields, or None.
        """
        return self._request('GET', f'/api/blog/articles/{article_id}')

    def get_article_by_slug(self, slug, site_id):
        """Get a single article by slug.

        Args:
            slug: The article slug.
            site_id: The site identifier.

        Returns:
            Dict with article fields, or None.
        """
        return self._request('GET', f'/api/blog/articles/slug/{slug}',
                             params={'site_id': site_id})

    def create_article(self, site_id, title, content_html='', status='draft',
                       excerpt=None, author=None, category_id=None,
                       seo_title=None, seo_description=None,
                       og_image_url=None, tags=None):
        """Create a new article.

        Args:
            site_id: Identifier for the site.
            title: Article title.
            content_html: HTML body content.
            status: Article status (draft, published).
            excerpt: Optional excerpt.
            author: Optional author name.
            category_id: Optional category ID.
            seo_title: Optional SEO title.
            seo_description: Optional SEO description.
            og_image_url: Optional Open Graph image URL.
            tags: Optional list of tag strings.

        Returns:
            Dict with id and slug on success, or None.
        """
        payload = {
            'site_id': site_id,
            'title': title,
            'content_html': content_html,
            'status': status,
        }
        if excerpt:
            payload['excerpt'] = excerpt
        if author:
            payload['author'] = author
        if category_id:
            payload['category_id'] = category_id
        if seo_title:
            payload['seo_title'] = seo_title
        if seo_description:
            payload['seo_description'] = seo_description
        if og_image_url:
            payload['og_image_url'] = og_image_url
        if tags:
            payload['tags'] = tags

        return self._request('POST', '/api/blog/articles', json_data=payload)

    def update_article(self, article_id, data):
        """Update an article.

        Args:
            article_id: The article record ID.
            data: Dict with fields to update.

        Returns:
            Dict with updated article, or None.
        """
        return self._request('PUT', f'/api/blog/articles/{article_id}', json_data=data)

    def delete_article(self, article_id):
        """Soft-delete an article.

        Args:
            article_id: The article record ID.

        Returns:
            Dict with confirmation, or None.
        """
        return self._request('DELETE', f'/api/blog/articles/{article_id}')

    def publish_article(self, article_id):
        """Publish a draft article.

        Args:
            article_id: The article record ID.

        Returns:
            Dict with updated article, or None.
        """
        return self._request('POST', f'/api/blog/articles/{article_id}/publish')

    # ------------------------------------------------------------------
    # Categories
    # ------------------------------------------------------------------

    def list_categories(self, site_id):
        """List categories for a site.

        Args:
            site_id: The site identifier.

        Returns:
            List of category dicts, or None.
        """
        return self._request('GET', '/api/blog/categories',
                             params={'site_id': site_id})

    def create_category(self, site_id, name, description='', parent_id=None,
                        sort_order=0):
        """Create a new category.

        Args:
            site_id: The site identifier.
            name: Category name.
            description: Optional description.
            parent_id: Optional parent category ID.
            sort_order: Sort order (default 0).

        Returns:
            Dict with id and slug, or None.
        """
        payload = {
            'site_id': site_id,
            'name': name,
            'description': description,
            'sort_order': sort_order,
        }
        if parent_id:
            payload['parent_id'] = parent_id
        return self._request('POST', '/api/blog/categories', json_data=payload)

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    def list_tags(self, site_id):
        """List all tags for a site with article counts.

        Args:
            site_id: The site identifier.

        Returns:
            List of tag dicts, or None.
        """
        return self._request('GET', '/api/blog/tags',
                             params={'site_id': site_id})
