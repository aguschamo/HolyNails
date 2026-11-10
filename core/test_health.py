"""Tests del endpoint de health check (Etapa 1B del TP10).

GET /api/health/ debe responder 200 con un JSON fijo, sin exigir
autenticación y sin tocar la base de datos (para que un monitoreo pueda
consultarlo aunque la BD esté caída).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

RESPUESTA_ESPERADA = {'status': 'ok', 'service': 'api'}


class HealthEndpointTests(APITestCase):
    """Respuesta de GET /api/health/."""

    def setUp(self):
        self.url = reverse('health')

    def test_responde_http_200(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.content)

    def test_devuelve_json_exacto_esperado(self):
        res = self.client.get(self.url)
        self.assertEqual(res.json(), RESPUESTA_ESPERADA)

    def test_acceso_sin_autenticacion(self):
        """Sin credenciales responde 200; una cabecera inválida también."""
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.content)

        res_con_token_invalido = self.client.get(
            self.url, HTTP_AUTHORIZATION='Bearer token-invalido'
        )
        self.assertEqual(
            res_con_token_invalido.status_code, status.HTTP_200_OK,
            res_con_token_invalido.content,
        )

    def test_no_consulta_la_base_de_datos(self):
        """Responde sin ninguna query: sigue vivo aunque la BD esté caída."""
        with self.assertNumQueries(0):
            res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.content)


class RailwayAllowedHostsEnvironmentTests(SimpleTestCase):
    """Valida ALLOWED_HOSTS desde el entorno en un proceso Django aislado."""

    def test_healthcheck_host_es_aceptado_desde_la_variable_de_entorno(self):
        env = {
            key: os.environ[key]
            for key in ('PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP')
            if key in os.environ
        }
        env.update({
            'DJANGO_SETTINGS_MODULE': 'config.settings',
            'DEBUG': 'false',
            'CLOUDINARY_STORAGE_ENABLED': 'false',
            'ALLOWED_HOSTS': 'api.example.test,healthcheck.railway.app',
            'SECRET_KEY': 'test-only-secret-key-for-settings',
        })
        code = (
            'import dotenv\n'
            'dotenv.load_dotenv = lambda *args, **kwargs: None\n'
            'import django\n'
            'django.setup()\n'
            'from django.conf import settings\n'
            'from django.test import Client\n'
            'response = Client().get(\n'
            '    "/api/health/", HTTP_HOST="healthcheck.railway.app"\n'
            ')\n'
            'import json\n'
            'print(json.dumps({\n'
            '    "debug": settings.DEBUG,\n'
            '    "allowed_hosts": settings.ALLOWED_HOSTS,\n'
            '    "status_code": response.status_code,\n'
            '}))\n'
        )
        result = subprocess.run(
            [sys.executable, '-c', code],
            cwd=Path(__file__).resolve().parent.parent,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, 'No se pudo cargar settings.')
        self.assertEqual(
            json.loads(result.stdout),
            {
                'debug': False,
                'allowed_hosts': [
                    'api.example.test',
                    'healthcheck.railway.app',
                ],
                'status_code': status.HTTP_200_OK,
            },
        )
