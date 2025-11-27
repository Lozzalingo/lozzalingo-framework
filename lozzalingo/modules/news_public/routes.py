from flask import Blueprint, render_template, jsonify, redirect, url_for, flash
import re

news_public_bp = Blueprint('news', __name__, url_prefix='/news', template_folder='templates')

def format_content(content):
    """Format content by converting line breaks to HTML and handling basic formatting"""
    if not content:
        return ""

    # Replace multiple line breaks with paragraph breaks
    content = re.sub(r'\n\s*\n', '</p><p>', content)

    # Replace single line breaks with <br> tags
    content = re.sub(r'\n', '<br>', content)

    # Wrap the content in paragraphs
    content = f'<p>{content}</p>'

    # Clean up empty paragraphs
    content = re.sub(r'<p>\s*</p>', '', content)

    # Handle basic markdown-style formatting
    content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)  # Bold
    content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', content)  # Italic
    content = re.sub(r'`(.*?)`', r'<code>\1</code>', content)  # Inline code

    # Handle links [text](url)
    content = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2" target="_blank" rel="noopener">\1</a>', content)

    return content

# Add the filter to the blueprint
@news_public_bp.app_template_filter('format_content')
def format_content_filter(content):
    return format_content(content)

@news_public_bp.route('/')
def news_list():
    """Public news listing page - only shows published articles"""
    # Import here to avoid circular imports
    from lozzalingo.modules.news.routes import get_all_articles_db
    articles = get_all_articles_db(status='published')
    return render_template('news_public/news.html', articles=articles)

@news_public_bp.route('/blog')
def blog():
    """Dedicated blog page with better styling - only shows published articles"""
    # Import here to avoid circular imports
    from lozzalingo.modules.news.routes import get_all_articles_db
    articles = get_all_articles_db(status='published')
    return render_template('news_public/blog.html', articles=articles)

@news_public_bp.route('/<slug>')
def blog_post(slug):
    """Individual blog post page - only shows published articles"""
    # Import here to avoid circular imports
    from lozzalingo.modules.news.routes import get_article_by_slug_db
    article = get_article_by_slug_db(slug)
    if not article or article.get('status') != 'published':
        flash('Article not found', 'error')
        return redirect(url_for('news.blog'))

    # Get related articles (exclude current one, only published)
    from lozzalingo.modules.news.routes import get_all_articles_db
    all_articles = get_all_articles_db(status='published')
    related_articles = [a for a in all_articles if a['slug'] != slug][:3]

    return render_template('news_public/blog_post.html', article=article, related_articles=related_articles)

# API Routes - Public endpoint only
@news_public_bp.route('/api/articles', methods=['GET'])
def get_articles():
    """Get all published articles API - public endpoint"""
    # Import here to avoid circular imports
    from lozzalingo.modules.news.routes import get_all_articles_db
    articles = get_all_articles_db(status='published')
    return jsonify(articles)
