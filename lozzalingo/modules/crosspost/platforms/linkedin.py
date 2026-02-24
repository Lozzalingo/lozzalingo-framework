"""
LinkedIn Platform Adapter
=========================

Posts article shares via the LinkedIn Posts API.
Uses token from a JSON file (same format as social-engine).
"""

import json
import requests

API_BASE = "https://api.linkedin.com/rest"
API_VERSION = "202602"


def post_article_share(token_file, title, excerpt, canonical_url, image_url=None):
    """
    Post an article share to LinkedIn.

    Args:
        token_file: Path to linkedin_token.json with {access_token, person_urn}
        title: Article/project title
        excerpt: Short description text
        canonical_url: Link back to the original article
        image_url: Optional thumbnail URL

    Returns:
        dict with {success, url, error}
    """
    try:
        with open(token_file, 'r') as f:
            token_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return {'success': False, 'url': '', 'error': f'Token file error: {e}'}

    access_token = token_data.get('access_token', '')
    person_urn = token_data.get('person_urn', '')

    if not access_token or not person_urn:
        return {'success': False, 'url': '', 'error': 'Missing access_token or person_urn in token file'}

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Linkedin-Version": API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }

    # Build commentary text: title + excerpt
    commentary = f"{title}\n\n{excerpt}" if excerpt else title

    payload = {
        "author": person_urn,
        "commentary": commentary,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
        "content": {
            "article": {
                "source": canonical_url,
                "title": title,
                "description": excerpt or '',
            }
        },
    }

    # Add thumbnail if provided
    if image_url:
        payload["content"]["article"]["thumbnail"] = image_url

    try:
        resp = requests.post(
            f"{API_BASE}/posts",
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        post_id = resp.headers.get("x-restli-id", "")
        post_url = f"https://www.linkedin.com/feed/update/{post_id}" if post_id else ''
        return {'success': True, 'url': post_url, 'error': ''}
    except requests.RequestException as e:
        error_detail = ''
        if hasattr(e, 'response') and e.response is not None:
            error_detail = e.response.text
        return {'success': False, 'url': '', 'error': f'LinkedIn API error: {e} {error_detail}'.strip()}
