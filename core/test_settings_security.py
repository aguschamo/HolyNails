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
        env['CLOUDINARY_STORAGE_ENABLED'] = 'false'
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

    def test_csrf_trusted_origins_se_carga_como_lista_exacta(self):
        env = os.environ.copy()
        env.pop('CSRF_TRUSTED_ORIGINS', None)
        env['SECRET_KEY'] = 'test-only-secret-key-for-settings'
        env['CLOUDINARY_STORAGE_ENABLED'] = 'false'
        env['CSRF_TRUSTED_ORIGINS'] = 'https://admin.example.test'
        code = (
            'import dotenv\n'
            'dotenv.load_dotenv = lambda *args, **kwargs: None\n'
            'from config import settings\n'
            'import json\n'
            'print(json.dumps(settings.CSRF_TRUSTED_ORIGINS))\n'
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
            json.loads(result.stdout), ['https://admin.example.test']
        )

    def test_csrf_trusted_origins_rechaza_comodines(self):
        env = os.environ.copy()
        env.pop('CSRF_TRUSTED_ORIGINS', None)
        env['SECRET_KEY'] = 'test-only-secret-key-for-settings'
        env['CLOUDINARY_STORAGE_ENABLED'] = 'false'
        env['CSRF_TRUSTED_ORIGINS'] = 'https://*.example.test'
        code = (
            'import dotenv\n'
            'dotenv.load_dotenv = lambda *args, **kwargs: None\n'
            'from config import settings\n'
        )
        result = subprocess.run(
            [sys.executable, '-c', code],
            cwd=BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn('CSRF_TRUSTED_ORIGINS no admite comodines', result.stderr)


class ProxyHttpsCsrfTests(TestCase):
    """POST real al login admin con las comprobaciones CSRF activadas."""

    def post_login(self, proxy_proto=None, origin=None, include_token=True):
        client = Client(enforce_csrf_checks=True)
        headers = {'HTTP_HOST': HOST}
        if proxy_proto is not None:
            headers['HTTP_X_FORWARDED_PROTO'] = proxy_proto

        login_page = client.get('/admin/login/', **headers)
        self.assertEqual(login_page.status_code, 200)
        csrf_token = client.cookies[settings.CSRF_COOKIE_NAME].value

        headers['HTTP_ORIGIN'] = origin or f'https://{HOST}'
        data = {
            'username': 'missing-user',
            'password': 'invalid-password',
        }
        if include_token:
            data['csrfmiddlewaretoken'] = csrf_token
        return client.post('/admin/login/', data, **headers)

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

    @override_settings(
        DEBUG=False,
        ALLOWED_HOSTS=[HOST],
        CSRF_TRUSTED_ORIGINS=[f'https://{HOST}'],
        SECURE_PROXY_SSL_HEADER=None,
    )
    def test_origen_exacto_y_token_csrf_se_aceptan_sin_proxy_confiable(self):
        response = self.post_login()

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Verificación CSRF fallida')

    @override_settings(
        DEBUG=False,
        ALLOWED_HOSTS=[HOST],
        CSRF_TRUSTED_ORIGINS=[f'https://{HOST}'],
        SECURE_PROXY_SSL_HEADER=None,
    )
    def test_origen_exacto_no_omite_la_exigencia_del_token_csrf(self):
        response = self.post_login(include_token=False)

        self.assertEqual(response.status_code, 403)

    @override_settings(
        DEBUG=False,
        ALLOWED_HOSTS=[HOST],
        CSRF_TRUSTED_ORIGINS=[f'https://{HOST}'],
        SECURE_PROXY_SSL_HEADER=None,
    )
    def test_origen_diferente_sigue_rechazado(self):
        response = self.post_login(origin='https://attacker.example')

        self.assertEqual(response.status_code, 403)
