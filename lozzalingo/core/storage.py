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
