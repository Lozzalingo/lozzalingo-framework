"""
Twitter/X Platform Adapter
===========================

Posts tweets via the Twitter API v2 using OAuth 1.0a (tweepy).
Free tier allows 1,500 tweets/month.
"""

import requests
from requests_oauthlib import OAuth1


API_BASE = "https://api.twitter.com/2"


def post_tweet(api_key, api_secret, access_token, access_token_secret,
               text, url=None):
    """
    Post a tweet with optional link.

    Args:
        api_key: Twitter API key (consumer key)
        api_secret: Twitter API secret (consumer secret)
        access_token: OAuth access token
        access_token_secret: OAuth access token secret
        text: Tweet text (will be truncated to fit with URL)
        url: Optional URL to append

    Returns:
        dict with {success, url, error}
    """
    if not all([api_key, api_secret, access_token, access_token_secret]):
        return {'success': False, 'url': '', 'error': 'Missing Twitter API credentials'}

    # Build tweet text with URL
    # Twitter counts URLs as 23 chars. Max tweet = 280 chars.
    if url:
        max_text_len = 280 - 24  # 23 for URL + 1 for space
        if len(text) > max_text_len:
            text = text[:max_text_len - 3] + '...'
        tweet_text = f"{text} {url}"
    else:
        if len(text) > 280:
            text = text[:277] + '...'
        tweet_text = text

    auth = OAuth1(api_key, api_secret, access_token, access_token_secret)

    try:
        resp = requests.post(
            f"{API_BASE}/tweets",
            json={"text": tweet_text},
            auth=auth,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json().get('data', {})
        tweet_id = data.get('id', '')
        tweet_url = f"https://x.com/i/web/status/{tweet_id}" if tweet_id else ''
        return {'success': True, 'url': tweet_url, 'error': ''}
    except requests.RequestException as e:
        error_detail = ''
        if hasattr(e, 'response') and e.response is not None:
            error_detail = e.response.text
        return {'success': False, 'url': '', 'error': f'Twitter API error: {e} {error_detail}'.strip()}
