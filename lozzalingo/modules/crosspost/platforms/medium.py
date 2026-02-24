"""
Medium Platform Adapter
=======================

Publishes articles via the Medium official API.
Requires an integration token from medium.com/me/settings/security.
"""

import requests

API_BASE = "https://api.medium.com/v1"

# Cache user ID after first lookup
_cached_user_id = None


def _get_user_id(token):
    """Fetch the authenticated user's Medium ID (cached after first call)."""
    global _cached_user_id
    if _cached_user_id:
        return _cached_user_id

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    resp = requests.get(f"{API_BASE}/me", headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json().get('data', {})
    _cached_user_id = data.get('id')
    return _cached_user_id


def publish_article(token, title, html_content, canonical_url, tags=None, image_url=None):
    """
    Publish a full article to Medium.

    Args:
        token: Medium integration token
        title: Article title
        html_content: Full HTML content (already processed for Medium)
        canonical_url: Canonical URL pointing back to the original
        tags: List of tags (max 5)

    Returns:
        dict with {success, url, error}
    """
    if not token:
        return {'success': False, 'url': '', 'error': 'No Medium token configured'}

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        user_id = _get_user_id(token)
        if not user_id:
            return {'success': False, 'url': '', 'error': 'Could not fetch Medium user ID'}
    except requests.RequestException as e:
        return {'success': False, 'url': '', 'error': f'Medium user lookup failed: {e}'}

    # Medium allows max 5 tags
    if tags and len(tags) > 5:
        tags = tags[:5]

    # Prepend hero image if provided
    if image_url:
        html_content = f'<figure><img src="{image_url}" alt="{title}"></figure>\n{html_content}'

    payload = {
        "title": title,
        "contentFormat": "html",
        "content": html_content,
        "canonicalUrl": canonical_url,
        "publishStatus": "public",
    }
    if tags:
        payload["tags"] = tags

    try:
        resp = requests.post(
            f"{API_BASE}/users/{user_id}/posts",
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json().get('data', {})
        return {'success': True, 'url': data.get('url', ''), 'error': ''}
    except requests.RequestException as e:
        error_detail = ''
        if hasattr(e, 'response') and e.response is not None:
            error_detail = e.response.text
        return {'success': False, 'url': '', 'error': f'Medium API error: {e} {error_detail}'.strip()}
