"""B11.1 — edición del perfil vía PATCH /api/auth/profile/.

El formulario del frontend consume exactamente este contrato:

- ``GET`` devuelve los datos actuales, incluido el nuevo ``telefono``;
- ``PATCH`` persiste ``nombre`` y ``telefono`` para los tres roles
  (CLIENTE, PERSONAL y ADMIN);
- ``role``, ``email`` y ``username`` no se alteran al guardar desde el
  formulario (el formulario ni siquiera los envía; el serializer mantiene
  ``role`` de sólo lectura y el email conserva su validación de unicidad);
- validaciones de ``telefono`` (símbolos y longitud) devueltas por campo;
- campos sensibles (contraseña, último login) nunca expuestos.

Los tests previos de role inmutable (``ProfileRoleInmutableTestCase``),
unicidad de email (``EmailUnicoPerfilTestCase``) y campos de profesional
(``test_user_serializer.py``) siguen siendo la autoridad de esas reglas
y deben continuar verdes.
"""

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from users.models import User


class BasePerfilEditableTests(APITestCase):
    """Una cuenta por rol con teléfono vacío y la URL del perfil."""

    def setUp(self):
        self.cliente = self.crear('carla', 'carla@holy.test', User.Roles.CLIENTE)
        self.personal = self.crear('maria', 'maria@holy.test', User.Roles.PERSONAL)
        self.admin = self.crear('admin', 'admin@holy.test', User.Roles.ADMIN)
        self.url = reverse('profile')

    @staticmethod
    def crear(username, email, role):
        return User.objects.create_user(
            username=username,
            email=email,
            password='pass1234',
            nombre=username.title(),
            role=role,
        )

    def editar(self, usuario, payload):
        self.client.force_authenticate(user=usuario)
        return self.client.patch(self.url, payload, format='json')


class LecturaTests(BasePerfilEditableTests):
    """GET /api/auth/profile/ expone el teléfono y nunca datos sensibles."""

    def test_el_profile_incluye_el_telefono_vacio_por_defecto(self):
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('telefono', resp.data)
        self.assertEqual(resp.data['telefono'], '')

    def test_el_profile_no_expone_password_ni_ultimo_login(self):
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertNotIn('password', resp.data)
        self.assertNotIn('last_login', resp.data)

    def test_sin_autenticacion_no_consulta_el_profile(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class EdicionTests(BasePerfilEditableTests):
    """Persistencia de nombre y teléfono para los tres roles."""

    def _verificar(self, usuario, nombre_nuevo, telefono_nuevo):
        resp = self.editar(
            usuario, {'nombre': nombre_nuevo, 'telefono': telefono_nuevo},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        usuario.refresh_from_db()
        self.assertEqual(usuario.nombre, nombre_nuevo)
        self.assertEqual(usuario.telefono, telefono_nuevo)

    def test_un_cliente_edita_su_nombre_y_telefono(self):
        self._verificar(self.cliente, 'Carla Gómez', '+54 9 11 5555-4321')

    def test_un_personal_edita_su_nombre_y_telefono(self):
        self._verificar(self.personal, 'María García', '011 4444 0000')

    def test_un_admin_edita_su_nombre_y_telefono(self):
        self._verificar(self.admin, 'Admin Uno', '(011) 5555.1234')

    def test_un_telefono_en_blanco_limpia_el_campo(self):
        self._verificar(self.cliente, 'Carla', '1155554321')
        resp = self.editar(self.cliente, {'telefono': ''})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.telefono, '')

    def test_el_telefono_se_guarda_recortado(self):
        resp = self.editar(self.cliente, {'telefono': '  11 5555 4321  '})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.telefono, '11 5555 4321')


class ValidacionTelefonoTests(BasePerfilEditableTests):
    """El backend es la autoridad de la validación del teléfono."""

    def test_un_telefono_con_texto_es_rechazado(self):
        resp = self.editar(self.cliente, {'telefono': 'llamar a la tarde'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('telefono', resp.data)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.telefono, '')

    def test_un_telefono_demasiado_largo_es_rechazado(self):
        resp = self.editar(self.cliente, {'telefono': '1' * 31})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('telefono', resp.data)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.telefono, '')

    def test_un_telefono_de_un_solo_caracter_es_rechazado(self):
        resp = self.editar(self.cliente, {'telefono': '1'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('telefono', resp.data)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.telefono, '')


class CamposProtegidosTests(BasePerfilEditableTests):
    """Guardar el perfil no altera rol, email ni permisos."""

    def test_guardar_no_modifica_el_rol(self):
        resp = self.editar(
            self.cliente,
            {'nombre': 'Carla', 'telefono': '1155554321', 'role': 'ADMIN'},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.role, User.Roles.CLIENTE)
        self.assertFalse(self.cliente.is_staff)

    def test_guardar_sin_email_conserva_el_email(self):
        resp = self.editar(
            self.cliente, {'nombre': 'Carla Gómez', 'telefono': '1155554321'},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.email, 'carla@holy.test')

    def test_guardar_no_permite_el_email_de_otra_cuenta(self):
        resp = self.editar(self.cliente, {'email': self.admin.email})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.email, 'carla@holy.test')
