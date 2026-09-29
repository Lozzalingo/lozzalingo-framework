"""
News Admin Routes
=================

Admin interface for news/blog article management.
Calls the centralised Blog Service (port 7219) for all article data.
"""

from flask import render_template, request, redirect, url_for, session, jsonify, current_app
from . import news_bp
import os
import uuid

from lozzalingo.core import db_log


# ===== Blog Service Client =====

def _get_blog_client():
    """Get a BlogClient instance."""
    from lozzalingo.clients.blog_client import BlogClient
    return BlogClient()


def _get_site_id():
    """Get the current site's identifier for blog service calls."""
    try:
        site_id = current_app.config.get('BLOG_SITE_ID')
        if site_id:
            return site_id
    except RuntimeError:
        pass
    return os.getenv('BLOG_SITE_ID', os.getenv('EMAIL_SITE_ID', 'unknown'))


# ===== Compatibility layer =====
# These functions match the old signatures so existing callers (news_public, sitemaps)
# continue to work without changes.

_POS_MAP = {'top': '0', 'center': '50', 'bottom': '100'}


def _normalize_pos(val):
    """Normalise image_position to a numeric string (0-100)."""
    if not val:
        return '50'
    return _POS_MAP.get(val, val)


def _service_to_legacy(article):
    """Convert a Blog Service article dict to the legacy format used by templates."""
    if not article:
        return None
    return {
        'id': article.get('id'),
        'title': article.get('title', ''),
        'slug': article.get('slug', ''),
        'content': article.get('content_html', ''),
        'image_url': article.get('og_image_url', ''),
        'status': article.get('status', 'draft'),
        'email_sent': False,
        'created_at': article.get('created_at', ''),
        'updated_at': article.get('updated_at', ''),
        'excerpt': article.get('excerpt', ''),
        'meta_title': article.get('seo_title', ''),
        'meta_description': article.get('seo_description', ''),
        'author_name': article.get('author', ''),
        'author_email': '',
        'category_name': article.get('category_name', ''),
        'source_id': '',
        'source_url': '',
        'crossposted_linkedin': False,
        'crossposted_medium': False,
        'crossposted_substack': False,
        'crossposted_twitter': False,
        'crossposted_threads': False,
        'image_position': _normalize_pos(article.get('image_position')),
        'ads_enabled': article.get('ads_enabled', True),
        'ads_shops': article.get('ads_shops'),
    }


def init_news_db():
    """No-op. The Blog Service manages its own database."""
    pass


def get_all_articles_db(status=None, category_name=None, exclude_categories=None):
    """Get all articles from the Blog Service with optional filters."""
    client = _get_blog_client()
    site_id = _get_site_id()

    result = client.list_articles(site_id=site_id, status=status, per_page=500)
    if not result:
        return []

    articles_raw = result.get('articles', result) if isinstance(result, dict) else result
    if not isinstance(articles_raw, list):
        articles_raw = []

    articles = [_service_to_legacy(a) for a in articles_raw]

    # Apply category filters client-side (the blog service may not support these directly)
    if category_name:
        articles = [a for a in articles if a.get('category_name') == category_name]

    if exclude_categories:
        articles = [
            a for a in articles
            if not a.get('category_name') or a.get('category_name') not in exclude_categories
        ]

    return articles


def get_article_db(article_id):
    """Get a single article by ID from the Blog Service."""
    client = _get_blog_client()
    result = client.get_article(article_id)
    return _service_to_legacy(result)


def get_article_by_slug_db(slug):
    """Get a single article by slug from the Blog Service."""
    client = _get_blog_client()
    site_id = _get_site_id()
    result = client.get_article_by_slug(slug, site_id=site_id)
    return _service_to_legacy(result)


def create_article_db(title, content, image_url=None, status='draft',
                      excerpt=None, meta_title=None, meta_description=None,
                      author_name=None, author_email=None, category_name=None,
                      source_id=None, source_url=None, image_position=None,
                      ads_enabled=True, ads_shops=None):
    """Create a new article via the Blog Service."""
    client = _get_blog_client()
    site_id = _get_site_id()

    result = client.create_article(
        site_id=site_id,
        title=title,
        content_html=content,
        status=status,
        excerpt=excerpt,
        author=author_name,
        seo_title=meta_title,
        seo_description=meta_description,
        og_image_url=image_url,
    )

    if result:
        return result.get('id'), result.get('slug', '')
    raise Exception('Failed to create article via Blog Service')


def update_article_db(article_id, title, content, image_url=None, status=None,
                      excerpt=None, meta_title=None, meta_description=None,
                      author_name=None, author_email=None, category_name=None,
                      source_id=None, source_url=None, image_position=None,
                      ads_enabled=None, ads_shops=None):
    """Update an article via the Blog Service."""
    client = _get_blog_client()

    data = {
        'title': title,
        'content_html': content,
    }
    if image_url is not None:
        data['og_image_url'] = image_url
    if status is not None:
        data['status'] = status
    if excerpt is not None:
        data['excerpt'] = excerpt
    if meta_title is not None:
        data['seo_title'] = meta_title
    if meta_description is not None:
        data['seo_description'] = meta_description
    if author_name is not None:
        data['author'] = author_name

    result = client.update_article(article_id, data)
    return result is not None


def delete_article_db(article_id):
    """Delete an article via the Blog Service (soft delete)."""
    client = _get_blog_client()
    result = client.delete_article(article_id)
    return result is not None


def toggle_article_status_db(article_id):
    """Toggle article status between draft and published."""
    client = _get_blog_client()

    # Get current article to check its status
    article = client.get_article(article_id)
    if not article:
        return None

    current_status = article.get('status', 'draft')
    new_status = 'draft' if current_status == 'published' else 'published'

    if new_status == 'published':
        result = client.publish_article(article_id)
    else:
        result = client.update_article(article_id, {'status': 'draft'})

    if result:
        return new_status
    return None


def mark_email_sent_db(article_id):
    """Mark that email has been sent for this article.

    The Blog Service does not track email_sent natively, so this is a no-op
    that returns True for backwards compatibility.
    """
    return True


def create_slug(title):
    """No-op. The Blog Service generates slugs server-side."""
    import re
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


# ===== Routes =====

@news_bp.route('/')
@news_bp.route('/editor')
def news_editor():
    """News editor - main interface"""
    if 'admin_id' not in session:
        return redirect(url_for('admin.login', next=request.path))

    return render_template('news/news_editor.html')

@news_bp.route('/api/articles', methods=['GET'])
def get_articles():
    """Get all articles"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        articles = get_all_articles_db()
        return jsonify(articles)
    except Exception as e:
        db_log('error', 'news', f'Error getting articles: {e}')
        return jsonify({'error': str(e)}), 500

@news_bp.route('/api/articles/<int:article_id>', methods=['GET'])
def get_article(article_id):
    """Get single article"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        article = get_article_db(article_id)
        if article:
            return jsonify(article)
        return jsonify({'error': 'Article not found'}), 404
    except Exception as e:
        db_log('error', 'news', f'Error getting article: {e}')
        return jsonify({'error': str(e)}), 500

@news_bp.route('/api/articles', methods=['POST'])
def create_article():
    """Create new article"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.json
        title = data.get('title')
        content = data.get('content')
        image_url = data.get('image_url', '')
        status = data.get('status', 'draft')

        excerpt = data.get('excerpt') or None
        meta_title = data.get('meta_title') or None
        meta_description = data.get('meta_description') or None
        category_name = data.get('category_name') or None
        author_name = data.get('author_name') or None
        author_email = data.get('author_email') or None
        source_id = data.get('source_id') or None
        source_url = data.get('source_url') or None
        image_position = data.get('image_position') or 'center'
        ads_enabled = data.get('ads_enabled', True)
        ads_shops = data.get('ads_shops') or None

        if not title or not content:
            return jsonify({'error': 'Title and content are required'}), 400

        article_id, slug = create_article_db(
            title, content, image_url, status,
            excerpt=excerpt, meta_title=meta_title, meta_description=meta_description,
            author_name=author_name, author_email=author_email, category_name=category_name,
            source_id=source_id, source_url=source_url, image_position=image_position,
            ads_enabled=ads_enabled, ads_shops=ads_shops
        )

        return jsonify({
            'success': True,
            'id': article_id,
            'slug': slug,
            'status': status
        })
    except Exception as e:
        db_log('error', 'news', f'Error creating article: {e}')
        return jsonify({'error': str(e)}), 500

@news_bp.route('/api/articles/<int:article_id>', methods=['PUT'])
def update_article(article_id):
    """Update article"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.json
        title = data.get('title')
        content = data.get('content')
        image_url = data.get('image_url', '')
        status = data.get('status', 'draft')

        excerpt = data.get('excerpt') or None
        meta_title = data.get('meta_title') or None
        meta_description = data.get('meta_description') or None
        category_name = data.get('category_name') or None
        author_name = data.get('author_name') or None
        author_email = data.get('author_email') or None
        source_id = data.get('source_id') or None
        source_url = data.get('source_url') or None
        image_position = data.get('image_position') or 'center'
        ads_enabled = data.get('ads_enabled', True)
        ads_shops = data.get('ads_shops') or None

        if not title or not content:
            return jsonify({'error': 'Title and content are required'}), 400

        success = update_article_db(
            article_id, title, content, image_url, status,
            excerpt=excerpt, meta_title=meta_title, meta_description=meta_description,
            author_name=author_name, author_email=author_email, category_name=category_name,
            source_id=source_id, source_url=source_url, image_position=image_position,
            ads_enabled=ads_enabled, ads_shops=ads_shops
        )

        if success:
            return jsonify({'success': True, 'message': 'Article updated successfully'})
        return jsonify({'error': 'Article not found'}), 404
    except Exception as e:
        db_log('error', 'news', f'Error updating article: {e}')
        return jsonify({'error': str(e)}), 500

@news_bp.route('/api/articles/<int:article_id>', methods=['DELETE'])
def delete_article(article_id):
    """Delete article"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        success = delete_article_db(article_id)
        if success:
            return jsonify({'success': True})
        return jsonify({'error': 'Article not found'}), 404
    except Exception as e:
        db_log('error', 'news', f'Error deleting article: {e}')
        return jsonify({'error': str(e)}), 500

@news_bp.route('/api/articles/<int:article_id>/toggle-status', methods=['POST'])
def toggle_status(article_id):
    """Toggle article status between draft and published"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        new_status = toggle_article_status_db(article_id)
        if new_status:
            return jsonify({'success': True, 'status': new_status})
        return jsonify({'error': 'Article not found'}), 404
    except Exception as e:
        db_log('error', 'news', f'Error toggling status: {e}')
        return jsonify({'error': str(e)}), 500

@news_bp.route('/api/product-shops', methods=['GET'])
def get_product_shops():
    """Return configured product shops for the ad settings UI"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    from flask import current_app
    enabled = current_app.config.get('NEWS_EMBED_PRODUCTS', False)
    shops = current_app.config.get('NEWS_PRODUCT_SHOPS', [])

    return jsonify({
        'enabled': enabled,
        'shops': [{'name': s['name'], 'url': s['url'], 'origin': s['origin']} for s in shops]
    })


@news_bp.route('/upload-image', methods=['POST'])
def upload_image():
    """Upload image for articles"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'heic', 'heif'}

    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400

    try:
        from lozzalingo.core.storage import upload_file

        file_ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_ext}"

        file_bytes = file.read()
        image_url = upload_file(file_bytes, unique_filename, 'blog')

        return jsonify({
            'success': True,
            'image_url': image_url,
            'filename': unique_filename
        })

    except Exception as e:
        db_log('error', 'news', f'Error uploading image: {e}')
        return jsonify({'error': 'Failed to upload image'}), 500


@news_bp.route('/list-images', methods=['GET'])
def list_images():
    """List uploaded images for the image browser modal"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        from lozzalingo.core.storage import list_files
        folder = request.args.get('folder', 'blog')
        if folder not in ('quick-links', 'blog', 'projects'):
            folder = 'blog'
        images = list_files(folder)
        return jsonify(images)
    except Exception as e:
        db_log('error', 'news', f'Error listing images: {e}')
        return jsonify({'error': 'Failed to list images'}), 500


@news_bp.route('/delete-image', methods=['POST'])
def delete_image():
    """Delete an image file, with in-use safety check"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        from lozzalingo.core.storage import delete_file, check_image_in_use
        data = request.json
        url = data.get('url', '')
        force = data.get('force', False)

        if not url:
            return jsonify({'error': 'URL required'}), 400

        refs = check_image_in_use(url)
        if refs and not force:
            return jsonify({
                'in_use': True,
                'references': refs,
                'message': f'Image is used by {len(refs)} item(s)'
            })

        delete_file(url)
        return jsonify({'success': True})
    except Exception as e:
        db_log('error', 'news', f'Error deleting image: {e}')
        return jsonify({'error': str(e)}), 500


# ================================
# SEND ARTICLE EMAIL
# ================================

@news_bp.route('/api/articles/<int:article_id>/send-email', methods=['POST'])
def send_article_email(article_id):
    """Send article email to subscribers, with optional feed filtering"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin access required'}), 401

    try:
        article = get_article_db(article_id)
        if not article:
            return jsonify({'error': 'Article not found'}), 404

        data = request.get_json(silent=True) or {}
        feed = data.get('feed', None)

        if feed == '__all__':
            feed = None
        elif feed is None:
            from flask import current_app
            category_name = article.get('category_name')
            if category_name:
                categories = current_app.config.get('NEWS_CATEGORIES', [])
                for cat in categories:
                    if cat.get('name') == category_name and cat.get('feed'):
                        feed = cat['feed']
                        break

        # Get subscriber emails via SubscribersClient
        try:
            from lozzalingo.clients.subscribers_client import SubscribersClient
            _subs = SubscribersClient()
            result = _subs.list_subscribers(status='confirmed')
            subscribers = [s['email'] for s in result.get('subscribers', [])] if result else []
        except Exception as e:
            db_log('error', 'news', f'Error fetching subscribers: {e}')
            subscribers = []

        if not subscribers:
            feed_msg = f' for feed "{feed}"' if feed else ''
            return jsonify({
                'success': False,
                'message': f'No subscribers found{feed_msg}',
                'subscriber_count': 0
            }), 200

        slug = article.get('slug', '')
        article_url = None
        category_name = article.get('category_name', '')
        if category_name:
            categories = current_app.config.get('NEWS_CATEGORIES', [])
            for cat in categories:
                if cat.get('name') == category_name:
                    article_url = f"/{cat['slug']}/{slug}"
                    break
        if not article_url:
            article_url = f"/news/{slug}"

        content = article.get('content', '')
        article_data = {
            'id': article['id'],
            'title': article['title'],
            'content': content,
            'slug': slug,
            'excerpt': article.get('excerpt') or (content[:300] + '...' if len(content) > 300 else content),
            'date': article.get('created_at', ''),
            'url': article_url,
            'image_url': article.get('image_url', ''),
        }

        try:
            from lozzalingo.clients.email_client import EmailClient
            _email = EmailClient()
            site_id = current_app.config.get('EMAIL_SITE_ID', os.getenv('EMAIL_SITE_ID', 'unknown'))
            brand = current_app.config.get('EMAIL_BRAND_NAME', 'News')
            website_url = current_app.config.get('EMAIL_WEBSITE_URL', '')
            title = article_data.get('title', 'Latest News')
            excerpt = article_data.get('excerpt', '')
            full_article_url = f"{website_url}{article_data.get('url', '')}"
            image_url = article_data.get('image_url', '')
            image_block = f'<a href="{full_article_url}"><img src="{image_url}" alt="{title}" style="width:100%;height:auto;display:block;" /></a>' if image_url else ''
            html = f'''<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:Georgia,serif;max-width:600px;margin:0 auto;padding:24px;">
<h1>{brand.upper()}</h1>
{image_block}
<h2>{title}</h2>
<p>{excerpt}</p>
<p><a href="{full_article_url}" name="read_full_article">Read Full Article</a></p>
<hr><p style="font-size:13px;"><a href="{website_url}/unsubscribe">Unsubscribe</a></p>
</body></html>'''
            result = _email.send_batch(
                recipients=subscribers,
                subject=f'New Update: {title}',
                html=html,
                site_id=site_id,
            )
            success = result is not None and result.get('success', False)
        except Exception as send_err:
            db_log('error', 'news', f'Failed to send news notification: {send_err}')
            success = False

        if success:
            mark_email_sent_db(article_id)
            return jsonify({
                'success': True,
                'message': f'Email sent successfully to {len(subscribers)} subscribers',
                'subscriber_count': len(subscribers)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to send email',
                'subscriber_count': len(subscribers)
            }), 500

    except Exception as e:
        db_log('error', 'news', f'Error sending article email: {e}')
        return jsonify({'error': str(e)}), 500


# ================================
# CROSS-POST ARTICLE
# ================================

VALID_CROSSPOST_PLATFORMS = ('linkedin', 'medium', 'substack', 'twitter', 'threads')

@news_bp.route('/api/articles/<int:article_id>/crosspost/<platform>', methods=['POST'])
def crosspost_article(article_id, platform):
    """Cross-post an article to an external platform"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin access required'}), 401

    if platform not in VALID_CROSSPOST_PLATFORMS:
        return jsonify({'error': f'Invalid platform. Must be one of: {", ".join(VALID_CROSSPOST_PLATFORMS)}'}), 400

    try:
        article = get_article_db(article_id)
        if not article:
            return jsonify({'error': 'Article not found'}), 404

        if article.get('status') != 'published':
            return jsonify({'error': 'Only published articles can be cross-posted'}), 400

        from flask import current_app
        site_url = current_app.config.get('EMAIL_WEBSITE_URL', current_app.config.get('SITE_URL', ''))
        slug = article.get('slug', '')

        canonical_url = None
        category_name = article.get('category_name', '')
        if category_name:
            categories = current_app.config.get('NEWS_CATEGORIES', [])
            for cat in categories:
                if cat.get('name') == category_name:
                    canonical_url = f"{site_url}/{cat['slug']}/{slug}"
                    break
        if not canonical_url:
            canonical_url = f"{site_url}/news/{slug}" if site_url else f"/news/{slug}"

        crosspost_svc = None
        try:
            from lozzalingo.modules.crosspost import crosspost_service
            crosspost_svc = crosspost_service
        except ImportError:
            pass

        if crosspost_svc is None:
            return jsonify({'error': 'Cross-post service not available'}), 500

        image_url = article.get('image_url', '')
        if image_url and not image_url.startswith('http') and site_url:
            image_url = f"{site_url}{image_url}"

        result = None
        if platform == 'linkedin':
            result = crosspost_svc.post_to_linkedin(
                title=article['title'],
                excerpt=article.get('excerpt') or article.get('content', '')[:300],
                canonical_url=canonical_url,
                image_url=image_url or None,
            )
        elif platform == 'medium':
            tags = None
            category = article.get('category_name')
            if category:
                tags = [category]
            result = crosspost_svc.post_to_medium(
                title=article['title'],
                html_content=article.get('content', ''),
                canonical_url=canonical_url,
                tags=tags,
                image_url=image_url or None,
            )
        elif platform == 'substack':
            result = crosspost_svc.post_to_substack(
                title=article['title'],
                html_content=article.get('content', ''),
                canonical_url=canonical_url,
                image_url=image_url or None,
            )
        elif platform == 'twitter':
            result = crosspost_svc.post_to_twitter(
                title=article['title'],
                excerpt=article.get('excerpt') or article.get('content', '')[:300],
                canonical_url=canonical_url,
                image_url=image_url or None,
            )
        elif platform == 'threads':
            result = crosspost_svc.post_to_threads(
                title=article['title'],
                excerpt=article.get('excerpt') or article.get('content', '')[:300],
                canonical_url=canonical_url,
                image_url=image_url or None,
            )

        if result and result.get('success'):
            return jsonify({
                'success': True,
                'platform': platform,
                'url': result.get('url', ''),
                'message': f'Successfully posted to {platform.title()}',
            })
        else:
            error_msg = result.get('error', 'Unknown error') if result else 'No result'
            return jsonify({'success': False, 'error': error_msg}), 500

    except Exception as e:
        db_log('error', 'news', f'Error cross-posting article: {e}')
        return jsonify({'error': str(e)}), 500
