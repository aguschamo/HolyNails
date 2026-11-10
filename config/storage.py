"""Django storage adapter for profile images in Cloudinary.

Cloudinary's official Python SDK supplies the API client; this small adapter
implements the Django Storage interface used by ``ImageField``.
"""

import os
import uuid
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


_CLOUDINARY_FOLDER = 'holy-nails'


def cloudinary_credentials_configured():
    """Return whether either supported credential format is complete."""
    cloudinary_url = os.environ.get('CLOUDINARY_URL', '').strip()
    if cloudinary_url:
        parsed = urlparse(cloudinary_url)
        return bool(
            parsed.scheme == 'cloudinary'
            and parsed.hostname
            and parsed.username
            and parsed.password
        )

    return all(
        os.environ.get(name, '').strip()
        for name in (
            'CLOUDINARY_CLOUD_NAME',
            'CLOUDINARY_API_KEY',
            'CLOUDINARY_API_SECRET',
        )
    )


@deconstructible
class CloudinaryMediaStorage(Storage):
    """Store Django media files as image assets in Cloudinary."""

    def __init__(self):
        if not cloudinary_credentials_configured():
            raise ImproperlyConfigured(
                'Cloudinary storage is selected but its credentials are '
                'missing or incomplete.'
            )

    @staticmethod
    def _sdk_config():
        import cloudinary

        cloudinary_url = os.environ.get('CLOUDINARY_URL', '').strip()
        if cloudinary_url:
            # The SDK reads CLOUDINARY_URL directly from the environment.
            cloudinary.config()
            return

        cloudinary.config(
            cloud_name=os.environ['CLOUDINARY_CLOUD_NAME'].strip(),
            api_key=os.environ['CLOUDINARY_API_KEY'].strip(),
            api_secret=os.environ['CLOUDINARY_API_SECRET'].strip(),
        )

    @staticmethod
    def _parts(name):
        normalized = str(name).replace('\\', '/').lstrip('/')
        stem, extension = os.path.splitext(normalized)
        if not stem or not extension:
            raise ValueError('Cloudinary media names must include an extension.')
        public_id = f'{_CLOUDINARY_FOLDER}/{stem}'
        return public_id, extension.lstrip('.').lower()

    def _save(self, name, content):
        import cloudinary.uploader

        public_id, extension = self._parts(name)
        # Model upload_to already includes a UUID. Add another unique suffix
        # at the storage boundary so other callers cannot overwrite an asset.
        stem = public_id.rsplit('/', 1)[-1]
        folder = public_id.rsplit('/', 1)[0]
        public_id = f'{folder}/{stem}_{uuid.uuid4().hex}'
        self._sdk_config()
        content.seek(0)
        result = cloudinary.uploader.upload(
            content,
            public_id=public_id,
            resource_type='image',
            overwrite=False,
            unique_filename=False,
            format=extension,
        )
        returned_id = result.get('public_id')
        returned_format = result.get('format')
        if not returned_id or not returned_format:
            raise ValueError('Cloudinary returned an incomplete image result.')
        # The stored name is relative and contains no credentials; the folder
        # prefix is reconstructed by _parts for URL and delete operations.
        return f'{returned_id.removeprefix(_CLOUDINARY_FOLDER + "/")}.{returned_format}'

    def url(self, name):
        import cloudinary

        public_id, extension = self._parts(name)
        self._sdk_config()
        return cloudinary.CloudinaryImage(public_id).build_url(
            format=extension,
            secure=True,
        )

    def delete(self, name):
        import cloudinary.uploader

        public_id, _extension = self._parts(name)
        self._sdk_config()
        result = cloudinary.uploader.destroy(
            public_id,
            resource_type='image',
            invalidate=True,
        )
        if result.get('result') not in ('ok', 'not found'):
            raise RuntimeError('Cloudinary did not confirm asset deletion.')

    def exists(self, name):
        # Profile asset names are UUID-backed and Cloudinary is configured to
        # reject overwrites. Avoid an Admin API request for each upload.
        return False
