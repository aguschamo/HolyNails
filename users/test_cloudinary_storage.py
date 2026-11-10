"""Cloudinary storage tests with the SDK fully mocked."""

import os
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import Mock, patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.storage import CloudinaryMediaStorage


BASE_DIR = Path(__file__).resolve().parent.parent


class CloudinaryMediaStorageTests(SimpleTestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'CLOUDINARY_CLOUD_NAME': 'test-cloud',
            'CLOUDINARY_API_KEY': 'test-key',
            'CLOUDINARY_API_SECRET': 'test-secret',
        })
        self.env.start()
        self.addCleanup(self.env.stop)

        self.sdk = types.ModuleType('cloudinary')
        self.sdk.config = Mock()

        self.uploader = types.ModuleType('cloudinary.uploader')
        self.uploader.upload = Mock()
        self.uploader.destroy = Mock()
        self.sdk.uploader = self.uploader
        self.sdk.CloudinaryImage = Mock()

        self.modules = patch.dict(sys.modules, {
            'cloudinary': self.sdk,
            'cloudinary.uploader': self.uploader,
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.storage = CloudinaryMediaStorage()

    def test_save_builds_unique_cloudinary_id_and_returns_relative_name(self):
        self.uploader.upload.side_effect = lambda _content, **kwargs: {
            'public_id': kwargs['public_id'],
            'format': kwargs['format'],
            'secure_url': 'https://res.cloudinary.com/test-cloud/image/upload/x.jpg',
        }
        content = Mock()
        content.seek = Mock()

        name = self.storage._save('perfiles/user_3_abcd.jpg', content)

        self.assertTrue(name.startswith('perfiles/user_3_abcd_'))
        self.assertTrue(name.endswith('.jpg'))
        upload_args = self.uploader.upload.call_args.kwargs
        self.assertTrue(upload_args['public_id'].startswith('holy-nails/perfiles/'))
        self.assertFalse(upload_args['overwrite'])
        self.assertEqual(upload_args['resource_type'], 'image')

    def test_url_is_secure_and_uses_cloudinary_public_id(self):
        image = Mock()
        image.build_url.return_value = 'https://res.cloudinary.com/test/image/upload/x.jpg'
        self.sdk.CloudinaryImage.return_value = image

        result = self.storage.url('perfiles/user_3_abcd.jpg')

        self.assertTrue(result.startswith('https://'))
        self.sdk.CloudinaryImage.assert_called_once_with(
            'holy-nails/perfiles/user_3_abcd'
        )
        image.build_url.assert_called_once_with(format='jpg', secure=True)

    def test_upload_failure_is_propagated_to_view_for_compensation(self):
        self.uploader.upload.side_effect = RuntimeError('upload failure')

        with self.assertRaisesMessage(RuntimeError, 'upload failure'):
            self.storage._save('perfiles/user_3_abcd.jpg', Mock())

    def test_delete_calls_cloudinary_destroy(self):
        self.uploader.destroy.return_value = {'result': 'ok'}

        self.storage.delete('perfiles/user_3_abcd.jpg')

        self.uploader.destroy.assert_called_once_with(
            'holy-nails/perfiles/user_3_abcd',
            resource_type='image',
            invalidate=True,
        )

    def test_delete_failure_is_reported_to_caller(self):
        self.uploader.destroy.return_value = {'result': 'error'}

        with self.assertRaises(RuntimeError):
            self.storage.delete('perfiles/user_3_abcd.jpg')

    def test_incomplete_credentials_fail_without_disclosing_values(self):
        with patch.dict(os.environ, {
            'CLOUDINARY_CLOUD_NAME': '',
            'CLOUDINARY_API_KEY': '',
            'CLOUDINARY_API_SECRET': '',
            'CLOUDINARY_URL': '',
        }, clear=False):
            with self.assertRaisesMessage(
                ImproperlyConfigured, 'credentials are missing or incomplete'
            ):
                CloudinaryMediaStorage()


class StorageSettingsTests(SimpleTestCase):
    def test_development_uses_filesystem_and_keeps_whitenoise(self):
        from django.conf import settings

        self.assertFalse(settings.CLOUDINARY_STORAGE_ENABLED)
        self.assertEqual(
            settings.STORAGES['default']['BACKEND'],
            'django.core.files.storage.FileSystemStorage',
        )
        self.assertEqual(
            settings.STORAGES['staticfiles']['BACKEND'],
            'whitenoise.storage.CompressedStaticFilesStorage',
        )

    def test_production_can_select_cloudinary_and_keeps_whitenoise(self):
        env = os.environ.copy()
        env.update({
            'DEBUG': 'false',
            'CLOUDINARY_STORAGE_ENABLED': 'true',
            'CLOUDINARY_URL': '',
            'CLOUDINARY_CLOUD_NAME': 'test-cloud',
            'CLOUDINARY_API_KEY': 'test-key',
            'CLOUDINARY_API_SECRET': 'test-secret',
            'SECRET_KEY': 'settings-test-key',
        })
        result = subprocess.run(
            [sys.executable, '-c', (
                'from config import settings; '
                'print(settings.STORAGES["default"]["BACKEND"]); '
                'print(settings.STORAGES["staticfiles"]["BACKEND"])'
            )],
            cwd=BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                'config.storage.CloudinaryMediaStorage',
                'whitenoise.storage.CompressedStaticFilesStorage',
            ],
        )

    def test_explicit_remote_selection_requires_credentials(self):
        env = os.environ.copy()
        for name in (
            'CLOUDINARY_URL', 'CLOUDINARY_CLOUD_NAME',
            'CLOUDINARY_API_KEY', 'CLOUDINARY_API_SECRET',
        ):
            env[name] = ''
        env.update({
            'DEBUG': 'true',
            'CLOUDINARY_STORAGE_ENABLED': 'true',
            'SECRET_KEY': 'settings-test-key',
        })
        result = subprocess.run(
            [sys.executable, '-c', 'from config import settings'],
            cwd=BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn('faltan credenciales completas', result.stderr)
        self.assertNotIn('test-secret', result.stderr)
