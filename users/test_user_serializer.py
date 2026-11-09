"""Tests de UserSerializer: campos de identificación de profesional.

Cubre los valores de ``es_profesional`` y ``profesional_id`` para:
- usuario con profesional activo vinculado,
- usuario sin vínculo,
- usuario con profesional inactivo.

Son los campos read-only que consume el frontend (Navbar, ProfesionalRoute,
MiAgenda) para decidir el acceso a /mi-agenda.
"""
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Profesional

from .models import User
from .serializers import UserSerializer


class UserSerializerCamposProfesionalesTests(TestCase):
    """Valores de es_profesional/profesional_id según el vínculo con Profesional."""

    def crear_usuario(self, username):
        return User.objects.create_user(
            username=username,
            email=f'{username}@holy.test',
            password='pass1234',
            nombre=username,
            role=User.Roles.CLIENTE,
        )

    def test_usuario_con_profesional_activo(self):
        user = self.crear_usuario('pro')
        profesional = Profesional.objects.create(
            nombre='María', usuario=user, is_active=True
        )
        data = UserSerializer(user).data
        self.assertTrue(data['es_profesional'])
        self.assertEqual(data['profesional_id'], profesional.id)

    def test_usuario_sin_vinculo_profesional(self):
        user = self.crear_usuario('cliente')
        data = UserSerializer(user).data
        self.assertFalse(data['es_profesional'])
        self.assertIsNone(data['profesional_id'])

    def test_usuario_con_profesional_inactivo(self):
        user = self.crear_usuario('pro_inactivo')
        profesional = Profesional.objects.create(
            nombre='Baja', usuario=user, is_active=False
        )
        data = UserSerializer(user).data
        self.assertFalse(data['es_profesional'])
        self.assertIsNone(data['profesional_id'])
        # El id del profesional inactivo no se expone ni como referencia
        self.assertNotEqual(data['profesional_id'], profesional.id)


class ProfileEndpointCamposProfesionalesTests(APITestCase):
    """Los campos llegan en GET /api/auth/profile/ (lo que consume el frontend)."""

    def crear_usuario(self, username):
        return User.objects.create_user(
            username=username,
            email=f'{username}@holy.test',
            password='pass1234',
            nombre=username,
            role=User.Roles.CLIENTE,
        )

    def test_profile_incluye_campos_de_profesional_activo(self):
        user = self.crear_usuario('pro')
        profesional = Profesional.objects.create(
            nombre='María', usuario=user, is_active=True
        )
        self.client.force_authenticate(user=user)
        res = self.client.get(reverse('profile'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['es_profesional'])
        self.assertEqual(res.data['profesional_id'], profesional.id)

    def test_profile_incluye_false_null_para_cliente_sin_vinculo(self):
        user = self.crear_usuario('cliente')
        self.client.force_authenticate(user=user)
        res = self.client.get(reverse('profile'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data['es_profesional'])
        self.assertIsNone(res.data['profesional_id'])
