"""
Threads Platform Adapter
=========================

Posts to Threads via the official Graph API.
Uses the same 3-step flow: create container → poll → publish.
"""

import time
import requests


BASE_URL = "https://graph.threads.net/v1.0"


def post_text(access_token, user_id, text, url=None):
    """
    Post a text post to Threads with optional link.

    Args:
        access_token: Threads API access token
        user_id: Threads user ID
        text: Post text
        url: Optional URL to append

    Returns:
        dict with {success, url, error}
    """
    if not access_token or not user_id:
        return {'success': False, 'url': '', 'error': 'Missing Threads credentials'}

    # Append URL to text if provided
    post_text = f"{text}\n\n{url}" if url else text

    # Step 1: Create text container
    try:
        resp = requests.post(
            f"{BASE_URL}/{user_id}/threads",
            data={
                "media_type": "TEXT",
                "text": post_text,
                "access_token": access_token,
            },
            timeout=30,
        )
        resp.raise_for_status()
        container_id = resp.json()["id"]
    except requests.RequestException as e:
        error_detail = ''
        if hasattr(e, 'response') and e.response is not None:
            error_detail = e.response.text
        return {'success': False, 'url': '', 'error': f'Threads container error: {e} {error_detail}'.strip()}

    # Step 2: Wait for processing
    time.sleep(3)
    for _ in range(10):
        try:
            resp = requests.get(
                f"{BASE_URL}/{container_id}",
                params={"fields": "status,error_message", "access_token": access_token},
                timeout=15,
            )
            status = resp.json().get("status")
            if status == "FINISHED":
                break
            elif status == "ERROR":
                error = resp.json().get("error_message", "Unknown error")
                return {'success': False, 'url': '', 'error': f'Threads processing error: {error}'}
            time.sleep(3)
        except requests.RequestException:
            time.sleep(3)

    # Step 3: Publish
    try:
        resp = requests.post(
            f"{BASE_URL}/{user_id}/threads_publish",
            data={"creation_id": container_id, "access_token": access_token},
            timeout=30,
        )
        resp.raise_for_status()
        post_id = resp.json().get("id", "")
        post_url = f"https://www.threads.net/@/post/{post_id}" if post_id else ''
        return {'success': True, 'url': post_url, 'error': ''}
    except requests.RequestException as e:
        error_detail = ''
        if hasattr(e, 'response') and e.response is not None:
            error_detail = e.response.text
        return {'success': False, 'url': '', 'error': f'Threads publish error: {e} {error_detail}'.strip()}
