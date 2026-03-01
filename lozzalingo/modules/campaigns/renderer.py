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


def _render_bold(text):
    """Convert **bold** markdown to <strong> tags"""
    if not text:
        return text
    return re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)


def render_block(block, style, variables=None):
    """Render a single block to HTML with inline CSS"""
    variables = variables or {}
    block_type = block.get('type', 'paragraph')

    if block_type == 'heading':
        text = _substitute_variables(block.get('text', ''), variables)
        subtitle = _substitute_variables(block.get('subtitle', ''), variables)
        subtitle_html = ''
        if subtitle:
            subtitle_html = f'<p style="margin:4px 0 0;font-size:13px;color:{style["header_text"]};opacity:0.85;font-family:{style["font"]};">{subtitle}</p>'
        return f'''<table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr><td style="background-color:{style['header_bg']};padding:28px 32px;text-align:center;">
                <h1 style="margin:0;color:{style['header_text']};font-family:{style['font_heading']};font-size:22px;font-weight:bold;letter-spacing:1px;">{text}</h1>
                {subtitle_html}
            </td></tr>
        </table>'''

    elif block_type == 'paragraph':
        content = _substitute_variables(block.get('content', ''), variables)
        content = _render_bold(content)
        return f'<p style="margin:0 0 16px;color:{style["text"]};font-family:{style["font"]};font-size:15px;line-height:1.7;">{content}</p>'

    elif block_type == 'image':
        url = _substitute_variables(block.get('url', ''), variables)
        alt = block.get('alt', '')
        border_color = block.get('border_color', '')
        border_style = f'border:3px solid {border_color};' if border_color else ''
        return f'''<table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr><td style="text-align:center;padding:8px 0;">
                <img src="{url}" alt="{alt}" style="max-width:100%;height:auto;{border_style}border-radius:4px;" />
            </td></tr>
        </table>'''

    elif block_type == 'code_box':
        label = _substitute_variables(block.get('label', ''), variables)
        code = _substitute_variables(block.get('code', ''), variables)
        return f'''<table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr><td style="padding:16px 0;">
                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:{style['header_bg']};border-radius:8px;">
                    <tr><td style="padding:20px 24px;text-align:center;">
                        <p style="margin:0 0 8px;font-size:11px;color:{style['header_text']};opacity:0.7;font-family:{style['font']};text-transform:uppercase;letter-spacing:2px;">{label}</p>
                        <p style="margin:0;font-size:28px;font-weight:bold;color:#ffd700;font-family:'Courier New',monospace;letter-spacing:3px;">{code}</p>
                    </td></tr>
                </table>
            </td></tr>
        </table>'''

    elif block_type == 'button':
        text = _substitute_variables(block.get('text', 'Click Here'), variables)
        url = _substitute_variables(block.get('url', '#'), variables)
        bg_color = block.get('bg_color', style['btn_bg'])
        text_color = block.get('text_color', style['btn_text'])
        return f'''<table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr><td style="text-align:center;padding:16px 0;">
                <a href="{url}" style="display:inline-block;background-color:{bg_color};color:{text_color};text-decoration:none;padding:14px 32px;border-radius:6px;font-family:{style['font']};font-size:15px;font-weight:bold;" target="_blank">{text}</a>
            </td></tr>
        </table>'''

    elif block_type == 'note':
        text = _substitute_variables(block.get('text', ''), variables)
        color = block.get('color', style['text_secondary'])
        return f'<p style="margin:8px 0;color:{color};font-family:{style["font"]};font-size:12px;text-align:center;">{text}</p>'

    elif block_type == 'divider':
        return f'''<table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr><td style="padding:16px 0;">
                <hr style="border:none;border-top:1px solid {style['border']};margin:0;" />
            </td></tr>
        </table>'''

    return ''


def render_campaign(blocks, variables=None):
    """Render a full campaign (list of blocks) into a complete HTML email.

    Args:
        blocks: list of block dicts
        variables: dict of variable substitutions (e.g. {'CODE': 'GOLD-1-AB12'})

    Returns:
        Complete HTML email string with all inline CSS
    """
    variables = variables or {}
    style = _get_style()
    brand = _get_brand()

    blocks_html = '\n'.join(render_block(b, style, variables) for b in blocks)

    unsubscribe_url = variables.get('UNSUBSCRIBE_URL', brand['unsubscribe_url'])

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{brand['name']}</title>
</head>
<body style="margin:0;padding:0;background-color:{style['bg']};font-family:{style['font']};">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:{style['bg']};">
        <tr><td align="center" style="padding:24px 16px;">
            <table width="600" cellpadding="0" cellspacing="0" border="0" style="background-color:{style['card_bg']};border:1px solid {style['border']};border-radius:8px;overflow:hidden;">
                <tr><td>
                    {blocks_html}
                </td></tr>
                <!-- Content padding wrapper -->
                <tr><td style="padding:0 32px;">
                </td></tr>
            </table>
            <!-- Footer -->
            <table width="600" cellpadding="0" cellspacing="0" border="0">
                <tr><td style="padding:20px 32px;text-align:center;">
                    <p style="margin:0;font-size:12px;color:{style['text_secondary']};font-family:{style['font']};">
                        <a href="{brand['url']}" style="color:{style['link']};text-decoration:none;">{brand['name']}</a>
                        &nbsp;&middot;&nbsp;
                        <a href="{unsubscribe_url}" style="color:{style['text_secondary']};text-decoration:underline;">Unsubscribe</a>
                    </p>
                </td></tr>
            </table>
        </td></tr>
    </table>
</body>
</html>'''
