"""
Thin client for the centralised Storage service.
Replaces direct DO Spaces / S3 / local file uploads with HTTP calls
to the Storage service.

Usage:
    from lozzalingo.clients.storage_client import StorageClient

    client = StorageClient()  # reads STORAGE_SERVICE_URL + STORAGE_API_KEY from env

    # Upload a file (file_obj is a file-like object or bytes)
    result = client.upload(file_obj, filename='photo.jpg', site_id='mario-pinto')
    # result = {"cdn_url": "https://cdn.../photo.jpg", "file_id": "abc123", "size_bytes": 45678}

    # Upload with image processing (resize + WebP) - handled server-side
    result = client.upload(file_obj, filename='hero.png', site_id='fat-big-quiz',
                           process_image=True, max_width=1200)

    # Upload without compression (for print-ready designs)
    result = client.upload(file_obj, filename='design.png', site_id='mario-pinto',
                           process_image=False)

    # Get a signed URL (for protected downloads)
    signed = client.get_signed_url(file_id='abc123', expires_in=3600)
    # signed = {"url": "https://...?Signature=...", "expires_at": "..."}

    # Delete a file
    client.delete(file_id='abc123')

    # List files in a subfolder
    files = client.list_files(subfolder='blog', site_id='crowd-sauced')
    # files = [{"url": "...", "filename": "...", "size_bytes": 1234}, ...]

For sites migrating from local file storage (e.g. Mario Pinto):
    Old: file.save(os.path.join(UPLOAD_FOLDER, filename))
    New: result = client.upload(file, filename=file.filename, site_id='mario-pinto')
         image_url = result['cdn_url']  # Use this in templates instead of /static/uploads/filename
"""

import os
import logging

logger = logging.getLogger(__name__)


class StorageClient:
    """Thin HTTP client for the centralised Storage service."""

    def __init__(self, service_url=None, api_key=None):
        self.service_url = (
            service_url
            or os.getenv('STORAGE_SERVICE_URL', 'https://storage.laurence.computer')
        )
        self.api_key = api_key or os.getenv('STORAGE_API_KEY', '')

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload(self, file_obj, filename, site_id='', subfolder='',
               process_image=True, max_width=None):
        """Upload a file to the centralised Storage service.

        Args:
            file_obj: A file-like object (with .read()) or raw bytes.
            filename: Target filename (e.g. "photo.jpg").
            site_id: Identifier for the calling site (e.g. "mario-pinto").
            subfolder: Optional subfolder (e.g. "blog", "products").
            process_image: If True the service compresses/resizes images.
                           Set to False for print-ready uploads.
            max_width: Optional max pixel width for image resizing.

        Returns:
            dict with keys cdn_url, file_id, size_bytes on success.
            None if the service is unreachable or returns an error.
        """
        try:
            import requests as _requests
        except ImportError:
            logger.error('[StorageClient] requests library is not installed')
            return None

        if hasattr(file_obj, 'read'):
            file_bytes = file_obj.read()
        else:
            file_bytes = file_obj

        data = {
            'site_id': site_id or self._detect_site_id(),
            'subfolder': subfolder,
            'process_image': '1' if process_image else '0',
        }
        if max_width is not None:
            data['max_width'] = str(int(max_width))

        try:
            resp = _requests.post(
                f'{self.service_url}/api/storage/upload',
                files={'file': (filename, file_bytes)},
                data=data,
                headers={'X-Storage-Key': self.api_key},
                timeout=30,
            )
            if resp.status_code == 200:
                result = resp.json()
                logger.info(
                    '[StorageClient] Uploaded via service: %s',
                    result.get('cdn_url', ''),
                )
                return {
                    'cdn_url': result.get('cdn_url', ''),
                    'file_id': result.get('file_id', ''),
                    'size_bytes': result.get('size_bytes', 0),
                }
            logger.warning(
                '[StorageClient] Service returned %s: %s',
                resp.status_code,
                resp.text[:200],
            )
            return None
        except Exception as exc:
            logger.error('[StorageClient] Service unreachable: %s', exc)
            return None

    def upload_from_path(self, filepath, site_id='', subfolder='',
                         process_image=True, max_width=None):
        """Convenience method to upload a file from a local path.

        Args:
            filepath: Absolute or relative path to the file on disc.
            site_id: Identifier for the calling site.
            subfolder: Optional subfolder.
            process_image: If True the service compresses/resizes images.
            max_width: Optional max pixel width.

        Returns:
            dict with keys cdn_url, file_id, size_bytes on success.
            None on failure.
        """
        filename = os.path.basename(filepath)
        try:
            with open(filepath, 'rb') as fh:
                return self.upload(
                    fh,
                    filename=filename,
                    site_id=site_id,
                    subfolder=subfolder,
                    process_image=process_image,
                    max_width=max_width,
                )
        except FileNotFoundError:
            logger.error('[StorageClient] File not found: %s', filepath)
            return None

    # ------------------------------------------------------------------
    # Signed URLs
    # ------------------------------------------------------------------

    def get_signed_url(self, file_id, expires_in=3600):
        """Get a time-limited signed URL for a protected file.

        Args:
            file_id: The file identifier returned from upload().
            expires_in: Lifetime of the URL in seconds (default 3600).

        Returns:
            dict with keys url and expires_at on success.
            None on failure.
        """
        try:
            import requests as _requests
        except ImportError:
            logger.error('[StorageClient] requests library is not installed')
            return None

        try:
            resp = _requests.get(
                f'{self.service_url}/api/storage/signed-url/{file_id}',
                params={'expires_in': expires_in},
                headers={'X-Storage-Key': self.api_key},
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
            logger.warning(
                '[StorageClient] Signed URL request returned %s',
                resp.status_code,
            )
            return None
        except Exception as exc:
            logger.error('[StorageClient] Signed URL request failed: %s', exc)
            return None

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(self, file_id=None, file_url=None):
        """Delete a file from the Storage service.

        Provide either file_id or file_url. file_id takes priority.

        Returns:
            True on success, False on failure.
        """
        try:
            import requests as _requests
        except ImportError:
            logger.error('[StorageClient] requests library is not installed')
            return False

        payload = {}
        if file_id:
            payload['file_id'] = file_id
        elif file_url:
            payload['file_url'] = file_url
        else:
            logger.warning('[StorageClient] delete() called without file_id or file_url')
            return False

        try:
            resp = _requests.post(
                f'{self.service_url}/api/storage/delete',
                json=payload,
                headers={
                    'X-Storage-Key': self.api_key,
                    'Content-Type': 'application/json',
                },
                timeout=10,
            )
            if resp.status_code == 200:
                logger.info('[StorageClient] Deleted file: %s', file_id or file_url)
                return True
            logger.warning(
                '[StorageClient] Delete returned %s', resp.status_code
            )
            return False
        except Exception as exc:
            logger.error('[StorageClient] Delete failed: %s', exc)
            return False

    # ------------------------------------------------------------------
    # List files
    # ------------------------------------------------------------------

    def list_files(self, subfolder='', site_id=''):
        """List files in a subfolder.

        Returns:
            list of dicts with url, filename, size_bytes on success.
            Empty list on failure.
        """
        try:
            import requests as _requests
        except ImportError:
            logger.error('[StorageClient] requests library is not installed')
            return []

        params = {
            'site_id': site_id or self._detect_site_id(),
            'subfolder': subfolder,
        }

        try:
            resp = _requests.get(
                f'{self.service_url}/api/storage/list',
                params=params,
                headers={'X-Storage-Key': self.api_key},
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json().get('files', [])
            logger.warning(
                '[StorageClient] List returned %s', resp.status_code
            )
            return []
        except Exception as exc:
            logger.error('[StorageClient] List failed: %s', exc)
            return []

    # ------------------------------------------------------------------
    # File info
    # ------------------------------------------------------------------

    def get_file_info(self, file_id):
        """Get metadata for a single file.

        Returns:
            dict with file metadata on success, None on failure.
        """
        try:
            import requests as _requests
        except ImportError:
            logger.error('[StorageClient] requests library is not installed')
            return None

        try:
            resp = _requests.get(
                f'{self.service_url}/api/storage/info/{file_id}',
                headers={'X-Storage-Key': self.api_key},
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as exc:
            logger.error('[StorageClient] File info failed: %s', exc)
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _detect_site_id(self):
        """Try to detect the site ID from SITE_MONITOR_KEY env var.

        The key format is sm_{site_id}_{random}, so we extract the middle
        portion.
        """
        sm_key = os.getenv('SITE_MONITOR_KEY', '')
        if sm_key.startswith('sm_') and sm_key.count('_') >= 2:
            parts = sm_key.split('_')
            return '_'.join(parts[1:-1])
        return ''
