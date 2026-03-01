"""
Campaign Renderer
=================

Converts campaign blocks (JSON) into complete HTML email with inline CSS.
Uses EMAIL_STYLE config for theming, matching the framework's email templates.
"""

import re
import logging
from flask import current_app

logger = logging.getLogger(__name__)

# Default email style (matches framework email_service defaults)
DEFAULT_STYLE = {
    'bg': '#f8f6f0',
    'card_bg': '#ffffff',
    'header_bg': '#2a2a2a',
    'header_text': '#f8f6f0',
    'text': '#2a2a2a',
    'text_secondary': '#666666',
    'accent': '#2a2a2a',
    'highlight_bg': '#f8f6f0',
    'highlight_border': '#2a2a2a',
    'border': '#d4c5a0',
    'link': '#2a2a2a',
    'btn_bg': '#2a2a2a',
    'btn_text': '#f8f6f0',
    'footer_bg': '#f8f6f0',
    'font': "'Georgia', serif",
    'font_heading': "'Georgia', serif",
}


def _get_style():
    """Get email style from app config or defaults"""
    try:
        custom = current_app.config.get('EMAIL_STYLE', {})
        style = dict(DEFAULT_STYLE)
        style.update(custom)
        return style
    except RuntimeError:
        return dict(DEFAULT_STYLE)


def _get_brand():
    """Get brand info from app config"""
    try:
        return {
            'name': current_app.config.get('EMAIL_BRAND_NAME', 'Newsletter'),
            'url': current_app.config.get('EMAIL_WEBSITE_URL', '#'),
            'unsubscribe_url': current_app.config.get('EMAIL_WEBSITE_URL', '') + '/api/subscribers/unsubscribe',
        }
    except RuntimeError:
        return {'name': 'Newsletter', 'url': '#', 'unsubscribe_url': '#'}


def resolve_variables(email, app=None):
    """Build a variable resolution dict for a specific recipient.

    Built-in variables:
        {{EMAIL}} - recipient email address
        {{UNSUBSCRIBE_URL}} - unsubscribe page URL

    Custom variables from app.config['CAMPAIGN_VARIABLES']:
        Each entry: { 'resolver': callable(email) -> str, 'preview_value': str }
    """
    the_app = app or current_app._get_current_object()
    brand = _get_brand()

    variables = {
        'EMAIL': email,
        'UNSUBSCRIBE_URL': brand['unsubscribe_url'] + '?email=' + email,
    }

    # Custom variables from host app
    custom_vars = the_app.config.get('CAMPAIGN_VARIABLES', {})
    for key, var_config in custom_vars.items():
        resolver = var_config.get('resolver')
        if resolver and callable(resolver):
            try:
                variables[key] = resolver(email)
            except Exception as e:
                logger.error(f"Error resolving variable {key} for {email}: {e}")
                variables[key] = var_config.get('preview_value', f'{{{{{key}}}}}')

    return variables


def _substitute_variables(text, variables):
    """Replace {{VAR}} placeholders with actual values"""
    if not text:
        return text
    for key, value in variables.items():
        text = text.replace(f'{{{{{key}}}}}', str(value))
    return text


def _render_inline(text):
    """Convert **bold** and *italic* markdown to HTML tags"""
    if not text:
        return text
    # Bold first (** **), then italic (* *)
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    return text


def render_block(block, style, variables=None):
    """Render a single block to HTML with inline CSS"""
    variables = variables or {}
    block_type = block.get('type', 'paragraph')

    if block_type == 'heading':
        text = _substitute_variables(block.get('text', ''), variables)
        subtitle = _substitute_variables(block.get('subtitle', ''), variables)
        subtitle_html = ''
        if subtitle:
            subtitle_html = f'<p style="margin:6px 0 0;font-size:13px;color:{style["header_text"]};opacity:0.85;font-family:{style["font"]};">{subtitle}</p>'
        return f'''<div style="background:{style['header_bg']};color:{style['header_text']};padding:24px;text-align:center;">
            <p style="font-size:20px;margin:0;letter-spacing:2px;font-weight:normal;font-family:{style['font_heading']};">{text}</p>
            {subtitle_html}
        </div>'''

    elif block_type == 'paragraph':
        content = _substitute_variables(block.get('content', ''), variables)
        content = _render_inline(content)
        return f'<p style="font-size:16px;margin:0 0 16px 0;line-height:1.7;color:{style["text"]};font-family:{style["font"]};">{content}</p>'

    elif block_type == 'image':
        url = _substitute_variables(block.get('url', ''), variables)
        alt = block.get('alt', '')
        border_color = block.get('border_color', '')
        border_style = f'border:2px solid {border_color};' if border_color else ''
        return f'''<div style="text-align:center;margin:20px 0;">
                <img src="{url}" alt="{alt}" style="max-width:280px;height:auto;border-radius:6px;{border_style}" />
            </div>'''

    elif block_type == 'code_box':
        label = _substitute_variables(block.get('label', ''), variables)
        code = _substitute_variables(block.get('code', ''), variables)
        return f'''<div style="background:{style['header_bg']};padding:20px;margin:20px 0;text-align:center;border-radius:4px;">
                <p style="color:#999;font-size:11px;margin:0 0 6px 0;text-transform:uppercase;letter-spacing:2px;font-family:{style['font']};">{label}</p>
                <p style="color:#ffd700;font-size:26px;font-weight:bold;margin:0;letter-spacing:3px;font-family:'Courier New',monospace;">{code}</p>
            </div>'''

    elif block_type == 'button':
        text = _substitute_variables(block.get('text', 'Click Here'), variables)
        url = _substitute_variables(block.get('url', '#'), variables)
        bg_color = block.get('bg_color', style['btn_bg'])
        text_color = block.get('text_color', style['btn_text'])
        border_color = block.get('border_color', '')
        border_style = f'border:2px solid {border_color};' if border_color else ''
        return f'''<p style="text-align:center;margin:24px 0 16px 0;">
                <a href="{url}" style="display:inline-block;background:{bg_color};color:{text_color};padding:12px 24px;text-decoration:none;font-weight:bold;font-size:15px;font-family:{style['font']};{border_style}" target="_blank">{text}</a>
            </p>'''

    elif block_type == 'note':
        text = _substitute_variables(block.get('text', ''), variables)
        color = block.get('color', style['text_secondary'])
        return f'<p style="font-size:13px;color:{color};text-align:center;margin:0;font-family:{style["font"]};">{text}</p>'

    elif block_type == 'divider':
        return f'<hr style="border:none;border-top:1px solid {style["border"]};margin:16px 0;" />'

    return ''


def _add_utm_params(html, campaign_name):
    """Auto-tag href URLs with UTM parameters for campaign tracking"""
    if not campaign_name:
        return html
    # Slugify campaign name for utm_campaign
    slug = re.sub(r'[^a-z0-9]+', '-', campaign_name.lower()).strip('-')

    def _tag_url(match):
        url = match.group(1)
        # Skip mailto:, tel:, and anchor-only links
        if url.startswith(('mailto:', 'tel:', '#')):
            return match.group(0)
        separator = '&' if '?' in url else '?'
        return f'href="{url}{separator}utm_source=campaign&utm_medium=email&utm_campaign={slug}"'

    return re.sub(r'href="([^"]+)"', _tag_url, html)


def render_campaign(blocks, variables=None, campaign_name=None):
    """Render a full campaign (list of blocks) into a complete HTML email.

    Args:
        blocks: list of block dicts
        variables: dict of variable substitutions (e.g. {'CODE': 'GOLD-1-AB12'})
        campaign_name: campaign name for UTM tagging (optional)

    Returns:
        Complete HTML email string with all inline CSS
    """
    variables = variables or {}
    style = _get_style()
    brand = _get_brand()

    # Split heading blocks (rendered outside content padding) from body blocks
    heading_html = ''
    body_blocks = []
    for b in blocks:
        if b.get('type') == 'heading':
            heading_html += render_block(b, style, variables)
        else:
            body_blocks.append(b)

    body_html = '\n            '.join(render_block(b, style, variables) for b in body_blocks)

    unsubscribe_url = variables.get('UNSUBSCRIBE_URL', brand['unsubscribe_url'])

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{brand['name']}</title>
</head>
<body style="margin:0;padding:0;background-color:{style['bg']};font-family:{style['font']};">
    <div style="font-family:{style['font']};line-height:1.6;color:{style['text']};background:{style['bg']};max-width:560px;margin:0 auto;padding:24px;">
        <div style="background:{style['card_bg']};border:1px solid {style['border']};">
            {heading_html}

            <div style="padding:32px 28px;">
            {body_html}
            </div>

            <div style="background:{style['footer_bg']};padding:16px;text-align:center;font-size:12px;color:{style['text_secondary']};border-top:1px solid {style['border']};">
                <p style="margin:0;font-family:{style['font']};">{brand['name']}</p>
                <p style="margin:4px 0 0 0;font-family:{style['font']};"><a href="{unsubscribe_url}" style="color:{style['text_secondary']};">Unsubscribe</a> &middot; <a href="{brand['url']}" style="color:{style['text_secondary']};">Website</a></p>
            </div>
        </div>
    </div>
</body>
</html>'''

    if campaign_name:
        html = _add_utm_params(html, campaign_name)

    return html
