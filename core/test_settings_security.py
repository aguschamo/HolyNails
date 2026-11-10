"""Tests de configuración de DEBUG y detección HTTPS detrás de un proxy."""

import json
import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import Client, SimpleTestCase, TestCase, override_settings


BASE_DIR = Path(__file__).resolve().parent.parent
HOST = 'api.example.test'


class DebugEnvironmentTests(SimpleTestCase):
    """La configuración envuelve DEBUG y las cookies de forma segura."""

    def assert_debug_configuration(self, debug_value, expected_debug):
        env = os.environ.copy()
        env.pop('DEBUG', None)
        env.pop('PROFILE_PHOTO_UPLOAD_ENABLED', None)
        env['SECRET_KEY'] = 'test-only-secret-key-for-settings'
        if debug_value is not None:
            env['DEBUG'] = debug_value

        code = (
            'import dotenv\n'
            'dotenv.load_dotenv = lambda *args, **kwargs: None\n'
            'from config import settings\n'
            'import json\n'
            'print(json.dumps([\n'
            '    settings.DEBUG,\n'
            '    settings.SESSION_COOKIE_SECURE,\n'
            '    settings.CSRF_COOKIE_SECURE,\n'
            '    settings.PROFILE_PHOTO_UPLOAD_ENABLED,\n'
            ']))\n'
        )
        result = subprocess.run(
            [sys.executable, '-c', code],
            cwd=BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, 'No se pudo cargar settings.')
        self.assertEqual(
            json.loads(result.stdout),
            [
                expected_debug,
                not expected_debug,
                not expected_debug,
                expected_debug,
            ],
        )

    def test_debug_ausente_es_false_y_usa_cookies_seguras(self):
        self.assert_debug_configuration(None, False)

    def test_debug_true_desactiva_cookies_secure(self):
        self.assert_debug_configuration('true', True)

    def test_debug_false_activa_cookies_secure(self):
        self.assert_debug_configuration('false', False)


class ProxyHttpsCsrfTests(TestCase):
    """POST real al login admin con las comprobaciones CSRF activadas."""

    def post_login(self, proxy_proto=None):
        client = Client(enforce_csrf_checks=True)
        headers = {'HTTP_HOST': HOST}
        if proxy_proto is not None:
            headers['HTTP_X_FORWARDED_PROTO'] = proxy_proto

        login_page = client.get('/admin/login/', **headers)
        self.assertEqual(login_page.status_code, 200)
        csrf_token = client.cookies[settings.CSRF_COOKIE_NAME].value

        headers['HTTP_ORIGIN'] = f'https://{HOST}'
        return client.post(
            '/admin/login/',
            {
                'username': 'missing-user',
                'password': 'invalid-password',
                'csrfmiddlewaretoken': csrf_token,
            },
            **headers,
        )

    @override_settings(
        DEBUG=False,
        ALLOWED_HOSTS=[HOST],
        CSRF_TRUSTED_ORIGINS=[],
        SECURE_PROXY_SSL_HEADER=None,
    )
    def test_origin_https_es_rechazado_sin_proxy_confiable(self):
        response = self.post_login(proxy_proto='https')

        self.assertEqual(response.status_code, 403)

    @override_settings(
        DEBUG=False,
        ALLOWED_HOSTS=[HOST],
        CSRF_TRUSTED_ORIGINS=[],
        SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    )
    def test_origin_https_y_token_csrf_se_aceptan_con_proxy_confiable(self):
        response = self.post_login(proxy_proto='https')

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Origin checking failed')

    @override_settings(
        DEBUG=False,
        ALLOWED_HOSTS=[HOST],
        CSRF_TRUSTED_ORIGINS=[],
        SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    )
    def test_origin_https_es_rechazado_si_falta_header_de_proxy(self):
        response = self.post_login()

        self.assertEqual(response.status_code, 403)
