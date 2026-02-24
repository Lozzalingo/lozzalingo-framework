"""
Substack Platform Adapter
=========================

Publishes articles via the python-substack library (undocumented API).
Requires a substack.sid cookie extracted from browser dev tools.
"""

from ..content_transform import html_to_markdown

try:
    from substack import Api as SubstackApi
    SUBSTACK_AVAILABLE = True
except ImportError:
    SUBSTACK_AVAILABLE = False


def publish_article(cookie, substack_url, title, html_content, canonical_url=None):
    """
    Publish a full article to Substack.

    Args:
        cookie: substack.sid cookie value
        substack_url: Base URL of the Substack publication (e.g. https://example.substack.com)
        title: Article title
        html_content: Quill HTML content (will be converted to Markdown)
        canonical_url: Optional canonical URL (added as footer link)

    Returns:
        dict with {success, url, error}
    """
    if not SUBSTACK_AVAILABLE:
        return {'success': False, 'url': '', 'error': 'python-substack package not installed'}

    if not cookie:
        return {'success': False, 'url': '', 'error': 'No Substack cookie configured'}

    if not substack_url:
        return {'success': False, 'url': '', 'error': 'No Substack URL configured'}

    try:
        api = SubstackApi(
            email="",
            password="",
            substack_url=substack_url,
        )
        # Override auth with cookie
        api.session.cookies.set("substack.sid", cookie)

        # Convert HTML to Markdown
        markdown = html_to_markdown(html_content)

        # Append canonical link footer
        if canonical_url:
            markdown += f"\n\n---\n\n*Originally published at [{canonical_url}]({canonical_url})*"

        # Create draft then publish
        draft = api.post_draft(title=title, body_markdown=markdown)
        draft_id = draft.get('id')
        if not draft_id:
            return {'success': False, 'url': '', 'error': 'Failed to create Substack draft'}

        published = api.publish_draft(draft_id)
        post_url = ''
        if published:
            slug = published.get('slug', '')
            if slug:
                post_url = f"{substack_url.rstrip('/')}/p/{slug}"

        return {'success': True, 'url': post_url, 'error': ''}

    except Exception as e:
        return {'success': False, 'url': '', 'error': f'Substack error: {e}'}
