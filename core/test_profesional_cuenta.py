"""Tests del alta administrativa de profesionales con cuenta de usuario.

POST /api/profesionales/crear-con-usuario/ crea el ``User`` y el registro
``Profesional`` en una única transacción. Cubre: éxito, rollback si falla el
vínculo, username/email duplicados, contraseña inválida, campos obligatorios,
acceso denegado a clientes, edición/activación y conservación del rol.

Patrones alineados con core/tests.py y users/test_user_serializer.py.
"""
from unittest import mock

from django.db import IntegrityError
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Profesional
from users.models import User


class AltaProfesionalConUsuarioTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='pass1234',
            nombre='Admin',
            role=User.Roles.ADMIN,
        )
        self.admin.is_staff = True
        self.admin.save()
        self.cliente = User.objects.create_user(
            username='cliente1',
            email='cliente1@test.com',
            password='pass1234',
            nombre='Cliente Uno',
            role=User.Roles.CLIENTE,
        )
        self.url = reverse('profesional-crear-con-usuario')
        self.datos = {
            'nombre': 'María García',
            'username': 'maria',
            'email': 'maria@test.com',
            'password': 'Clave-S3gura-2026',
            'nombre_profesional': 'María',
        }

    def test_creacion_exitosa_de_usuario_y_profesional(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url, self.datos, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(username='maria')
        self.assertTrue(user.check_password('Clave-S3gura-2026'))
        self.assertEqual(user.nombre, 'María García')
        self.assertEqual(user.email, 'maria@test.com')
        # D1/D3: el alta administrativa crea cuentas PERSONAL; el acceso a
        # Mi agenda depende del vínculo activo con su Profesional.
        self.assertEqual(user.role, User.Roles.PERSONAL)
        # La contraseña no se devuelve en la respuesta.
        self.assertNotIn('password', resp.data)

        profesional = Profesional.objects.get(usuario=user)
        self.assertEqual(profesional.nombre, 'María')
        self.assertTrue(profesional.is_active)
        self.assertEqual(resp.data['id'], profesional.id)
        self.assertEqual(resp.data['usuario'], user.id)

    def test_rollback_si_falla_la_creacion_del_vinculo(self):
        self.client.force_authenticate(user=self.admin)
        with mock.patch(
            'core.serializers.Profesional.objects.create',
            side_effect=IntegrityError('vinculo fallido'),
        ):
            resp = self.client.post(self.url, self.datos, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # No queda una cuenta de usuario incompleta.
        self.assertFalse(User.objects.filter(username='maria').exists())
        self.assertEqual(Profesional.objects.count(), 0)

    def test_username_duplicado(self):
        User.objects.create_user(
            username='maria', email='otra@test.com', password='pass1234'
        )
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url, self.datos, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', resp.data)
        self.assertEqual(User.objects.filter(username='maria').count(), 1)
        self.assertEqual(Profesional.objects.count(), 0)

    def test_email_duplicado(self):
        User.objects.create_user(
            username='otra', email='maria@test.com', password='pass1234'
        )
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url, self.datos, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', resp.data)
        self.assertFalse(User.objects.filter(username='maria').exists())

    def test_password_invalida_no_crea_nada(self):
        datos = {**self.datos, 'password': '1234'}
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url, datos, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', resp.data)
        self.assertFalse(User.objects.filter(username='maria').exists())

    def test_campos_obligatorios(self):
        self.client.force_authenticate(user=self.admin)
        usuarios_antes = User.objects.count()
        resp = self.client.post(self.url, {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), usuarios_antes)
        self.assertEqual(Profesional.objects.count(), 0)

    def test_cliente_no_puede_crear(self):
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.post(self.url, self.datos, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(User.objects.filter(username='maria').exists())

    def test_anonimo_no_puede_crear(self):
        resp = self.client.post(self.url, self.datos, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(User.objects.filter(username='maria').exists())


class GestionAdministrativaProfesionalTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='pass1234',
            nombre='Admin',
            role=User.Roles.ADMIN,
        )
        self.admin.is_staff = True
        self.admin.save()
        self.cliente = User.objects.create_user(
            username='cliente1',
            email='cliente1@test.com',
            password='pass1234',
            nombre='Cliente Uno',
            role=User.Roles.CLIENTE,
        )
        self.pro_user = User.objects.create_user(
            username='maria',
            email='maria@test.com',
            password='pass1234',
            nombre='María García',
            role=User.Roles.PERSONAL,
        )
        self.profesional = Profesional.objects.create(
            nombre='María', usuario=self.pro_user, is_active=True
        )
        self.url = reverse('profesional-detail', args=[self.profesional.id])

    def test_editar_nombre_y_desactivar_reactivar(self):
        self.client.force_authenticate(user=self.admin)

        resp = self.client.patch(
            self.url, {'nombre': 'María Editada'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.profesional.refresh_from_db()
        self.assertEqual(self.profesional.nombre, 'María Editada')
        self.assertTrue(self.profesional.is_active)

        resp = self.client.patch(self.url, {'is_active': False}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.profesional.refresh_from_db()
        self.assertFalse(self.profesional.is_active)

        resp = self.client.patch(self.url, {'is_active': True}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.profesional.refresh_from_db()
        self.assertTrue(self.profesional.is_active)

    def test_cliente_no_puede_editar_ni_desactivar(self):
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.patch(self.url, {'is_active': False}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.profesional.refresh_from_db()
        self.assertTrue(self.profesional.is_active)

    def test_vincular_cuenta_libre_la_promueve_a_personal(self):
        # Vincular una cuenta CLIENTE la convierte en la cuenta del
        # trabajador: pasa a PERSONAL dentro de la misma operación.
        libre = User.objects.create_user(
            username='libre', email='libre@test.com', password='pass1234'
        )
        otro = Profesional.objects.create(nombre='Brenda')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            reverse('profesional-detail', args=[otro.id]),
            {'usuario': libre.id},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        otro.refresh_from_db()
        self.assertEqual(otro.usuario, libre)
        libre.refresh_from_db()
        self.assertEqual(libre.role, User.Roles.PERSONAL)

    def test_no_se_puede_vincular_usuario_de_otra_profesional(self):
        # "María" ya tiene vínculo con pro_user: no se le puede cambiar la
        # cuenta (D3: el vínculo existente es inmutable).
        libre = User.objects.create_user(
            username='libre', email='libre@test.com', password='pass1234'
        )
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            self.url, {'usuario': libre.id}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('usuario', resp.data)
        self.profesional.refresh_from_db()
        self.assertEqual(self.profesional.usuario, self.pro_user)

        # Además, una cuenta ya vinculada no puede pasarse a otra
        # profesional (OneToOne protegido con 400 en lugar de 500).
        otro = Profesional.objects.create(nombre='Brenda')
        resp = self.client.patch(
            reverse('profesional-detail', args=[otro.id]),
            {'usuario': self.pro_user.id},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('usuario', resp.data)
        otro.refresh_from_db()
        self.assertIsNone(otro.usuario)

    def test_no_se_puede_desvincular_una_cuenta(self):
        # D3: no se quita el vínculo de un profesional que ya tiene
        # cuenta; la alternativa es desactivarlo.
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(self.url, {'usuario': None}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('usuario', resp.data)
        self.profesional.refresh_from_db()
        self.assertEqual(self.profesional.usuario, self.pro_user)
        self.pro_user.refresh_from_db()
        self.assertEqual(self.pro_user.role, User.Roles.PERSONAL)

    def test_se_puede_vincular_una_cuenta_admin_conservando_su_rol(self):
        # B10.0.2: ADMIN puede tener Profesional asociado sin perder su
        # rol (vincularlo no lo demueve a PERSONAL).
        libre = User.objects.create_user(
            username='adminlibre',
            email='adminlibre@test.com',
            password='pass1234',
            role=User.Roles.ADMIN,
        )
        otro = Profesional.objects.create(nombre='Brenda')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            reverse('profesional-detail', args=[otro.id]),
            {'usuario': libre.id},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        otro.refresh_from_db()
        self.assertEqual(otro.usuario, libre)
        libre.refresh_from_db()
        self.assertEqual(libre.role, User.Roles.ADMIN)

    def test_editar_no_modifica_el_rol_del_usuario(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            self.url, {'nombre': 'María García Jr'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.pro_user.refresh_from_db()
        self.assertEqual(self.pro_user.role, User.Roles.PERSONAL)
