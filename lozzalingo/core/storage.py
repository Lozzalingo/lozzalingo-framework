"""
Storage Utility
===============

Shared file upload with cloud (DigitalOcean Spaces) / local branching.
"""

import os
from flask import current_app
from ..modules.settings.helpers import is_cloud_storage, get_do_spaces_config


def upload_file(file_bytes, filename, subfolder):
    """Upload file to cloud storage or local filesystem.

    Args:
        file_bytes: Raw bytes of the processed file.
        filename: Target filename (e.g. "abc123.jpg").
        subfolder: Subfolder name (e.g. "quick-links", "blog", "projects").

    Returns:
        Public URL (cloud) or local path like "/static/blog/abc.jpg" (local).
    """
    if is_cloud_storage():
        return _upload_to_spaces(file_bytes, filename, subfolder)
    return _save_locally(file_bytes, filename, subfolder)


def _upload_to_spaces(file_bytes, filename, subfolder):
    """Upload to DigitalOcean Spaces via boto3."""
    import boto3
    config = get_do_spaces_config()
    region = config['region']
    space_name = config['space_name']
    access_key = config['access_key']
    secret_key = config['secret_key']

    app_prefix = current_app.config.get('SPACES_FOLDER', 'uploads')
    object_key = f"{app_prefix}/{subfolder}/{filename}"

    # Guess content type from extension
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    content_types = {
        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
        'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp',
    }
    content_type = content_types.get(ext, 'application/octet-stream')

    client = boto3.client(
        's3',
        region_name=region,
        endpoint_url=f"https://{region}.digitaloceanspaces.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )

    client.put_object(
        Bucket=space_name,
        Key=object_key,
        Body=file_bytes,
        ACL='public-read',
        ContentType=content_type,
    )

    return f"https://{space_name}.{region}.digitaloceanspaces.com/{object_key}"


def _save_locally(file_bytes, filename, subfolder):
    """Save to local static folder."""
    upload_dir = os.path.join(current_app.static_folder, subfolder)
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)
    with open(filepath, 'wb') as f:
        f.write(file_bytes)
    return f"/static/{subfolder}/{filename}"


def list_files(subfolder):
    """List image files in a storage subfolder.

    Returns list of {url, filename} dicts, newest first.
    """
    allowed = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    if is_cloud_storage():
        return _list_cloud_files(subfolder, allowed)
    return _list_local_files(subfolder, allowed)


def _list_cloud_files(subfolder, allowed):
    """List files from DigitalOcean Spaces."""
    import boto3
    config = get_do_spaces_config()
    region = config['region']
    space_name = config['space_name']

    app_prefix = current_app.config.get('SPACES_FOLDER', 'uploads')
    prefix = f"{app_prefix}/{subfolder}/"

    client = boto3.client(
        's3',
        region_name=region,
        endpoint_url=f"https://{region}.digitaloceanspaces.com",
        aws_access_key_id=config['access_key'],
        aws_secret_access_key=config['secret_key'],
    )

    images = []
    paginator = client.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=space_name, Prefix=prefix):
        for obj in page.get('Contents', []):
            key = obj['Key']
            filename = key.rsplit('/', 1)[-1]
            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
            if ext in allowed:
                url = f"https://{space_name}.{region}.digitaloceanspaces.com/{key}"
                images.append({
                    'url': url,
                    'filename': filename,
                    'last_modified': obj.get('LastModified'),
                })

    # Sort newest first
    images.sort(key=lambda x: x.get('last_modified') or '', reverse=True)
    # Strip internal field before returning
    for img in images:
        img.pop('last_modified', None)
    return images


def _list_local_files(subfolder, allowed):
    """List files from local static folder."""
    folder = os.path.join(current_app.static_folder, subfolder)
    if not os.path.isdir(folder):
        return []

    images = []
    for filename in os.listdir(folder):
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext in allowed:
            images.append({
                'url': f'/static/{subfolder}/{filename}',
                'filename': filename,
            })

    # Sort by modification time, newest first
    images.sort(
        key=lambda img: os.path.getmtime(os.path.join(folder, img['filename'])),
        reverse=True,
    )
    return images


def delete_file(file_url):
    """Delete a file by its URL (cloud or local).

    Returns True on success, raises on failure.
    """
    if not file_url:
        return False

    if 'digitaloceanspaces.com' in file_url:
        return _delete_cloud_file(file_url)
    return _delete_local_file(file_url)


def _delete_cloud_file(file_url):
    """Delete a file from DigitalOcean Spaces."""
    import boto3
    from urllib.parse import urlparse

    config = get_do_spaces_config()
    region = config['region']
    space_name = config['space_name']

    parsed = urlparse(file_url)
    # Object key is the path without leading slash
    object_key = parsed.path.lstrip('/')

    client = boto3.client(
        's3',
        region_name=region,
        endpoint_url=f"https://{region}.digitaloceanspaces.com",
        aws_access_key_id=config['access_key'],
        aws_secret_access_key=config['secret_key'],
    )

    client.delete_object(Bucket=space_name, Key=object_key)
    return True


def _delete_local_file(file_url):
    """Delete a file from local static folder."""
    # file_url looks like /static/subfolder/filename.jpg
    if file_url.startswith('/static/'):
        rel_path = file_url[len('/static/'):]
        full_path = os.path.join(current_app.static_folder, rel_path)
        if os.path.isfile(full_path):
            os.unlink(full_path)
            return True
    return False


def check_image_in_use(image_url):
    """Check if an image URL is referenced in quick_links, news_articles, or projects.

    Returns list of {type, title} for each item using the image.
    """
    references = []

    # Helper to safely query a table
    def _query_table(db_config_key, table, title_col='title'):
        try:
            from flask import current_app
            db_path = current_app.config.get(db_config_key)
            if not db_path:
                return
        except RuntimeError:
            return

        try:
            try:
                from database import Database
                db_connect = Database.connect
            except ImportError:
                import sqlite3
                db_connect = sqlite3.connect

            if not os.path.isfile(db_path):
                return

            with db_connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f'SELECT {title_col} FROM {table} WHERE image_url = ?',
                    (image_url,)
                )
                for row in cursor.fetchall():
                    references.append({'type': table, 'title': row[0]})
        except Exception as e:
            print(f"check_image_in_use error on {table}: {e}")

    # Also check content columns for inline images (news & projects)
    def _query_content(db_config_key, table, title_col='title'):
        try:
            from flask import current_app
            db_path = current_app.config.get(db_config_key)
            if not db_path:
                return
        except RuntimeError:
            return

        try:
            try:
                from database import Database
                db_connect = Database.connect
            except ImportError:
                import sqlite3
                db_connect = sqlite3.connect

            if not os.path.isfile(db_path):
                return

            with db_connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f'SELECT {title_col} FROM {table} WHERE content LIKE ?',
                    (f'%{image_url}%',)
                )
                for row in cursor.fetchall():
                    # Avoid duplicates if already matched on image_url column
                    ref = {'type': f'{table} (inline)', 'title': row[0]}
                    if ref not in references:
                        references.append(ref)
        except Exception as e:
            print(f"check_image_in_use content error on {table}: {e}")

    _query_table('QUICK_LINKS_DB', 'quick_links')
    _query_table('NEWS_DB', 'news_articles')
    _query_table('PROJECTS_DB', 'projects')
    _query_content('NEWS_DB', 'news_articles')
    _query_content('PROJECTS_DB', 'projects')

    return references
