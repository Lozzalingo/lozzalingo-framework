from flask import Blueprint, render_template, jsonify, redirect, url_for, flash, request, current_app, make_response
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


# ===== Category Helpers =====

def _get_categories_config():
    """Read NEWS_CATEGORIES from app config. Returns [] if not configured."""
    try:
        return current_app.config.get('NEWS_CATEGORIES', [])
    except RuntimeError:
        return []


def _get_category_maps():
    """Returns (slug_to_name, name_to_slug) dicts from config."""
    categories = _get_categories_config()
    slug_to_name = {c['slug']: c['name'] for c in categories}
    name_to_slug = {c['name']: c['slug'] for c in categories}
    return slug_to_name, name_to_slug


def _get_gallery_excludes():
    """Returns list of category names where gallery=False."""
    categories = _get_categories_config()
    return [c['name'] for c in categories if not c.get('gallery', True)]


def _get_default_category_slug():
    """Returns the slug of the first category with gallery=True, or None."""
    categories = _get_categories_config()
    for c in categories:
        if c.get('gallery', True):
            return c['slug']
    return None


# ===== Template Globals =====

@news_public_bp.app_template_global()
def article_url(article):
    """Generate the correct URL for an article based on category config.

    If NEWS_CATEGORIES is configured, returns /<category-slug>/<article-slug>.
    Otherwise falls back to /news/<slug>.
    """
    slug = article.get('slug', '') if isinstance(article, dict) else article.slug
    categories = _get_categories_config()

    if not categories:
        return url_for('news.blog_post', slug=slug)

    cat_name = article.get('category_name', '') if isinstance(article, dict) else getattr(article, 'category_name', '')
    _, name_to_slug = _get_category_maps()

    cat_slug = name_to_slug.get(cat_name)
    if cat_slug:
        return f'/{cat_slug}/{slug}'

    # Fallback to default category or /news/<slug>
    default = _get_default_category_slug()
    if default:
        return f'/{default}/{slug}'
    return url_for('news.blog_post', slug=slug)


# ===== Sitemap Generator =====

def _generate_sitemap():
    """Generate a sitemap.xml from config + published news articles.

    Requires SITE_URL in app config. Optional configs:
    - SITEMAP_STATIC_PAGES: list of {'path': '/', 'changefreq': 'weekly', 'priority': '1.0'}
    - NEWS_CATEGORIES: used for category-based article URLs
    """
    from lozzalingo.modules.news.routes import get_all_articles_db

    site_url = current_app.config.get('SITE_URL', '').rstrip('/')
    static_pages = current_app.config.get('SITEMAP_STATIC_PAGES', [])
    categories = _get_categories_config()
    _, name_to_slug = _get_category_maps()
    default_slug = _get_default_category_slug()

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    # Static pages from config
    for page in static_pages:
        path = page.get('path', '/')
        changefreq = page.get('changefreq', 'weekly')
        priority = page.get('priority', '0.5')
        xml += f'    <url>\n'
        xml += f'        <loc>{site_url}{path}</loc>\n'
        xml += f'        <changefreq>{changefreq}</changefreq>\n'
        xml += f'        <priority>{priority}</priority>\n'
        xml += f'    </url>\n'

    # Published news articles
    articles = get_all_articles_db(status='published')
    for article in articles:
        slug = article.get('slug', '')
        updated_at = article.get('updated_at', '')
        cat_name = article.get('category_name', '')

        # Build URL using category routing
        if categories:
            cat_slug = name_to_slug.get(cat_name, default_slug or 'news')
            loc = f'{site_url}/{cat_slug}/{slug}'
        else:
            loc = f'{site_url}/news/{slug}'

        # Format date as ISO 8601
        lastmod = ''
        if updated_at:
            lastmod = updated_at.replace(' ', 'T') + '+00:00'

        xml += f'    <url>\n'
        xml += f'        <loc>{loc}</loc>\n'
        if lastmod:
            xml += f'        <lastmod>{lastmod}</lastmod>\n'
        xml += f'        <changefreq>monthly</changefreq>\n'
        xml += f'        <priority>0.7</priority>\n'
        xml += f'    </url>\n'

    xml += '</urlset>'

    response = make_response(xml)
    response.headers['Content-Type'] = 'application/xml'
    return response


# ===== Register Category Routes at App Level =====

@news_public_bp.record_once
def register_category_routes(state):
    """Register top-level /<category-slug>/<article-slug> routes on the app."""
    app = state.app
    categories = app.config.get('NEWS_CATEGORIES', [])

    if not categories:
        return

    for cat in categories:
        cat_slug = cat['slug']
        cat_name = cat['name']

        def make_view(category_slug, category_name):
            def category_article_view(article_slug):
                from lozzalingo.modules.news.routes import get_article_by_slug_db, get_all_articles_db
                article = get_article_by_slug_db(article_slug)

                if not article or article.get('status') != 'published':
                    flash('Article not found', 'error')
                    return redirect(url_for('news.blog'))

                # If article belongs to a different category, redirect to the correct one
                article_cat = article.get('category_name', '')
                _, name_to_slug = _get_category_maps()
                correct_slug = name_to_slug.get(article_cat, _get_default_category_slug())

                if correct_slug and correct_slug != category_slug:
                    return redirect(f'/{correct_slug}/{article_slug}', code=301)

                # Get related articles from same category
                all_articles = get_all_articles_db(status='published', category_name=category_name)
                related_articles = [a for a in all_articles if a['slug'] != article_slug][:3]

                # If not enough related articles from same category, fill from all
                if len(related_articles) < 3:
                    all_published = get_all_articles_db(status='published')
                    existing_slugs = {article_slug} | {a['slug'] for a in related_articles}
                    for a in all_published:
                        if a['slug'] not in existing_slugs:
                            related_articles.append(a)
                            if len(related_articles) >= 3:
                                break

                return render_template('news_public/blog_post.html',
                                     article=article, related_articles=related_articles)
            return category_article_view

        view_func = make_view(cat_slug, cat_name)
        endpoint = f'category_{cat_slug}'
        app.add_url_rule(f'/{cat_slug}/<article_slug>', endpoint=endpoint, view_func=view_func)
        print(f"[News] Registered category route: /{cat_slug}/<slug> -> {endpoint}")

    # Register /sitemap.xml at the app level if SITE_URL is configured
    site_url = app.config.get('SITE_URL')
    if site_url:
        def sitemap_xml_view():
            return _generate_sitemap()
        app.add_url_rule('/sitemap.xml', endpoint='sitemap_xml', view_func=sitemap_xml_view)
        print(f"[News] Registered /sitemap.xml for {site_url}")


# ===== Routes =====

@news_public_bp.route('/')
def news_list():
    """Public news listing page - only shows published articles.
    Excludes categories with gallery=False when NEWS_CATEGORIES is configured."""
    from lozzalingo.modules.news.routes import get_all_articles_db
    excludes = _get_gallery_excludes()
    if excludes:
        articles = get_all_articles_db(status='published', exclude_categories=excludes)
    else:
        articles = get_all_articles_db(status='published')
    return render_template('news_public/news.html', articles=articles)

@news_public_bp.route('/blog')
def blog():
    """Dedicated blog page with better styling - only shows published articles.
    Excludes categories with gallery=False when NEWS_CATEGORIES is configured."""
    from lozzalingo.modules.news.routes import get_all_articles_db
    excludes = _get_gallery_excludes()
    if excludes:
        articles = get_all_articles_db(status='published', exclude_categories=excludes)
    else:
        articles = get_all_articles_db(status='published')
    return render_template('news_public/blog.html', articles=articles)

@news_public_bp.route('/<slug>')
def blog_post(slug):
    """Individual blog post page.
    If NEWS_CATEGORIES is configured, 301 redirects to /<category-slug>/<slug>.
    Otherwise renders directly."""
    from lozzalingo.modules.news.routes import get_article_by_slug_db, get_all_articles_db
    article = get_article_by_slug_db(slug)

    if not article or article.get('status') != 'published':
        flash('Article not found', 'error')
        return redirect(url_for('news.blog'))

    # If categories are configured, redirect to the proper category URL
    categories = _get_categories_config()
    if categories:
        cat_name = article.get('category_name', '')
        _, name_to_slug = _get_category_maps()
        cat_slug = name_to_slug.get(cat_name, _get_default_category_slug())
        if cat_slug:
            return redirect(f'/{cat_slug}/{slug}', code=301)

    # No categories configured — render directly (original behavior)
    all_articles = get_all_articles_db(status='published')
    related_articles = [a for a in all_articles if a['slug'] != slug][:3]
    return render_template('news_public/blog_post.html', article=article, related_articles=related_articles)


# ===== API Routes =====

@news_public_bp.route('/api/articles', methods=['GET'])
def get_articles():
    """Get published articles API - public endpoint.
    Supports ?category=<name> and ?exclude_gallery=true query params."""
    from lozzalingo.modules.news.routes import get_all_articles_db

    category = request.args.get('category')
    exclude_gallery = request.args.get('exclude_gallery', '').lower() == 'true'

    kwargs = {'status': 'published'}

    if category:
        kwargs['category_name'] = category
    elif exclude_gallery:
        excludes = _get_gallery_excludes()
        if excludes:
            kwargs['exclude_categories'] = excludes

    articles = get_all_articles_db(**kwargs)
    return jsonify(articles)


@news_public_bp.route('/api/categories', methods=['GET'])
def get_categories():
    """Return NEWS_CATEGORIES config as JSON for frontend consumption."""
    categories = _get_categories_config()
    return jsonify({
        'categories': categories,
        'default': _get_default_category_slug()
    })
