"""
Content Transform
=================

Utilities for converting Quill HTML to platform-specific formats.
"""

import re


def html_to_plain_text(html):
    """Strip HTML tags, convert <p>/<br> to newlines. For LinkedIn excerpts."""
    if not html:
        return ''
    text = html
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'</p>\s*<p[^>]*>', '\n\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&#39;', "'", text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def html_for_medium(quill_html, site_url=''):
    """Rewrite relative image URLs to absolute, strip data- attributes."""
    if not quill_html:
        return ''
    html = quill_html
    if site_url:
        site_url = site_url.rstrip('/')
        html = re.sub(r'src="(/[^"]*)"', f'src="{site_url}\\1"', html)
        html = re.sub(r'href="(/[^"]*)"', f'href="{site_url}\\1"', html)
    html = re.sub(r'\s+data-[a-z-]+="[^"]*"', '', html)
    return html


def html_to_markdown(quill_html):
    """Convert Quill HTML to Markdown for Substack."""
    if not quill_html:
        return ''

    md = quill_html

    # Headings
    md = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n\n', md, flags=re.DOTALL)
    md = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1\n\n', md, flags=re.DOTALL)
    md = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1\n\n', md, flags=re.DOTALL)

    # Bold / italic / code
    md = re.sub(r'<strong>(.*?)</strong>', r'**\1**', md)
    md = re.sub(r'<b>(.*?)</b>', r'**\1**', md)
    md = re.sub(r'<em>(.*?)</em>', r'*\1*', md)
    md = re.sub(r'<i>(.*?)</i>', r'*\1*', md)
    md = re.sub(r'<code>(.*?)</code>', r'`\1`', md)

    # Links
    md = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)', md)

    # Images
    md = re.sub(r'<img[^>]*src="([^"]*)"[^>]*/?\s*>', r'![](\1)\n\n', md)

    # Line breaks / paragraphs
    md = re.sub(r'<br\s*/?>', '\n', md)
    md = re.sub(r'</p>\s*', '\n\n', md)
    md = re.sub(r'<p[^>]*>', '', md)

    # Lists
    md = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', md, flags=re.DOTALL)
    md = re.sub(r'</?[ou]l[^>]*>', '\n', md)

    # Blockquotes
    md = re.sub(r'<blockquote[^>]*>(.*?)</blockquote>', lambda m: '> ' + m.group(1).strip() + '\n\n', md, flags=re.DOTALL)

    # Pre/code blocks
    md = re.sub(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>', r'```\n\1\n```\n\n', md, flags=re.DOTALL)

    # Strip remaining HTML tags
    md = re.sub(r'<[^>]+>', '', md)

    # HTML entities
    md = re.sub(r'&nbsp;', ' ', md)
    md = re.sub(r'&amp;', '&', md)
    md = re.sub(r'&lt;', '<', md)
    md = re.sub(r'&gt;', '>', md)
    md = re.sub(r'&#39;', "'", md)
    md = re.sub(r'&quot;', '"', md)

    # Clean up whitespace
    md = re.sub(r'\n{3,}', '\n\n', md)
    return md.strip()
