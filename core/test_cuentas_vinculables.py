"""Cuentas disponibles para vincular a un profesional (A3).

``GET /api/profesionales/cuentas-disponibles/`` devuelve las cuentas de
usuario que todavía no están unidas a un profesional, con datos de
sólo lectura para distinguirlas (username, nombre, email, rol, estado).
La asociación en sí es el ``PATCH /api/profesionales/{id}/`` existente,
cubierto por ``test_profesional_cuenta.py`` (promoción de rol, OneToOne
y vínculo inmutable).

No se modifican datos persistentes: todo corre sobre la base de tests
en memoria.
"""
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Profesional

User = get_user_model()


class CuentasDisponiblesTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_a3', email='admin_a3@test.com', password='x',
            nombre='Admin A3', role=User.Roles.ADMIN,
        )
        self.personal = User.objects.create_user(
            username='personal_a3', email='personal_a3@test.com', password='x',
            role=User.Roles.PERSONAL,
        )
        self.cliente = User.objects.create_user(
            username='cliente_a3', email='cliente_a3@test.com', password='x',
            role=User.Roles.CLIENTE,
        )
        # Cuenta libre (candidata) y cuenta ya vinculada a otro profesional.
        self.libre = User.objects.create_user(
            username='cuenta_libre', email='libre@test.com', password='x',
            nombre='Cuenta Libre', role=User.Roles.CLIENTE,
        )
        self.ocupada = User.objects.create_user(
            username='cuenta_ocupada', email='ocupada@test.com', password='x',
            role=User.Roles.PERSONAL,
        )
        Profesional.objects.create(nombre='Ocupada', usuario=self.ocupada)
        self.url = '/api/profesionales/cuentas-disponibles/'

    def test_anonimo_recibe_401(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cliente_recibe_403(self):
        self.client.force_authenticate(user=self.cliente)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_personal_recibe_403(self):
        self.client.force_authenticate(user=self.personal)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_ve_solo_cuentas_sin_vinculo(self):
        self.client.force_authenticate(user=self.admin)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        datos = respuesta.json()
        usernames = [r['username'] for r in datos['results']]
        self.assertIn('cuenta_libre', usernames)
        # Una cuenta ya unida a un profesional no es candidata.
        self.assertNotIn('cuenta_ocupada', usernames)
        self.assertEqual(datos['count'], len(usernames))

    def test_expone_solo_datos_para_distinguir_sin_password(self):
        self.client.force_authenticate(user=self.admin)
        datos = self.client.get(self.url).json()
        libre = next(
            r for r in datos['results'] if r['username'] == 'cuenta_libre'
        )
        self.assertEqual(
            set(libre.keys()),
            {'id', 'username', 'nombre', 'email', 'role', 'is_active'},
        )
        self.assertEqual(libre['nombre'], 'Cuenta Libre')
        self.assertEqual(libre['email'], 'libre@test.com')
        self.assertEqual(libre['role'], User.Roles.CLIENTE)
        self.assertNotIn('password', libre)
