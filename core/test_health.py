"""Tests del endpoint de health check (Etapa 1B del TP10).

GET /api/health/ debe responder 200 con un JSON fijo, sin exigir
autenticación y sin tocar la base de datos (para que un monitoreo pueda
consultarlo aunque la BD esté caída).
"""
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
