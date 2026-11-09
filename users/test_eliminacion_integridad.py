"""Etapa B6 — protección de eliminaciones en la API (users).

Verifica la protección de integridad del diagnóstico B5 sobre el
endpoint DELETE de usuarios:

- un usuario con turnos (cualquier estado) no se elimina → 400;
- un usuario sin turnos se elimina → 204;
- una cuenta vinculada a un profesional sin turnos propios se elimina y
  el profesional queda con ``usuario = None`` (SET_NULL, comportamiento
  actual conservado);
- los permisos actuales se conservan (IsAdminUser: solo staff).

Se replican los patrones y convenciones de los tests existentes de la
serie (helpers de ``BaseAPITest`` de core/tests.py, sin modificarlo).
"""

from datetime import time, timedelta

from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Profesional, Servicio, Turno
from users.models import User


class BaseEliminacionUsuariosTests(APITestCase):
    """Usuarios de prueba, profesional, servicio y fecha futura."""

    def crear_usuario(self, username, email, role=User.Roles.CLIENTE, staff=False):
        user = User.objects.create_user(
            username=username,
            email=email,
            password='pass1234',
            nombre=username,
            role=role,
        )
        if staff:
            user.is_staff = True
            user.save()
        return user

    def setUp(self):
        self.admin = self.crear_usuario(
            'admin', 'admin@test.com', role=User.Roles.ADMIN, staff=True,
        )
        self.rol_admin = self.crear_usuario(
            'roladmin', 'roladmin@test.com', role=User.Roles.ADMIN,
        )
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')
        self.pro_user = self.crear_usuario('pro', 'pro@test.com')
        self.profesional = Profesional.objects.create(
            nombre='Pro A', usuario=self.pro_user,
        )
        self.servicio = Servicio.objects.create(
            nombre='Semi', duracion=timedelta(minutes=30), precio='5000.00',
        )
        # Fecha futura para que los turnos no se consideren comenzados.
        self.fecha = timezone.localdate() + timedelta(days=1)

    def url_usuario(self, pk):
        return reverse('user-detail', args=[pk])

    def crear_turno(self, usuario, estado='pendiente', hora=time(9, 0)):
        return Turno.objects.create(
            fecha=self.fecha,
            hora=hora,
            usuario=usuario,
            profesional=self.profesional,
            servicio=self.servicio,
            estado=estado,
        )


class UsuarioEliminacionTests(BaseEliminacionUsuariosTests):
    """DELETE /api/users/{id}/ — integridad y permisos actuales."""

    def test_staff_elimina_usuario_sin_turnos(self):
        libre = self.crear_usuario('libre', 'libre@test.com')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_usuario(libre.pk))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(pk=libre.pk).exists())

    def test_staff_no_elimina_usuario_con_turno_pendiente(self):
        turno = self.crear_turno(self.cliente, 'pendiente')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_usuario(self.cliente.pk))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('No se puede eliminar el usuario', str(resp.data))
        self.assertTrue(User.objects.filter(pk=self.cliente.pk).exists())
        turno.refresh_from_db()
        self.assertEqual(turno.usuario_id, self.cliente.pk)

    def test_staff_no_elimina_usuario_con_turno_confirmado(self):
        turno = self.crear_turno(self.cliente, 'confirmado')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_usuario(self.cliente.pk))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(User.objects.filter(pk=self.cliente.pk).exists())
        turno.refresh_from_db()
        self.assertEqual(turno.usuario_id, self.cliente.pk)

    def test_staff_no_elimina_usuario_con_turno_cancelado(self):
        # Incluidos los cancelados: son parte del historial.
        turno = self.crear_turno(self.cliente, 'cancelado')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_usuario(self.cliente.pk))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(User.objects.filter(pk=self.cliente.pk).exists())
        turno.refresh_from_db()
        self.assertEqual(turno.usuario_id, self.cliente.pk)

    def test_staff_no_elimina_usuario_con_varios_turnos(self):
        turnos = [
            self.crear_turno(self.cliente, 'pendiente', time(9, 0)),
            self.crear_turno(self.cliente, 'confirmado', time(10, 0)),
            self.crear_turno(self.cliente, 'cancelado', time(11, 0)),
        ]
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_usuario(self.cliente.pk))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(User.objects.filter(pk=self.cliente.pk).exists())
        self.assertEqual(Turno.objects.filter(usuario=self.cliente).count(), 3)
        for turno in turnos:
            turno.refresh_from_db()
            self.assertEqual(turno.usuario_id, self.cliente.pk)

    def test_eliminar_cuenta_vinculada_sin_turnos_deja_profesional_sin_usuario(
        self,
    ):
        # Comportamiento actual conservado: SET_NULL en Profesional.usuario.
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_usuario(self.pro_user.pk))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(pk=self.pro_user.pk).exists())
        self.profesional.refresh_from_db()
        self.assertIsNone(self.profesional.usuario_id)

    def test_no_eliminar_cuenta_vinculada_con_turnos_propios(self):
        turno = self.crear_turno(self.pro_user, 'pendiente')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_usuario(self.pro_user.pk))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(User.objects.filter(pk=self.pro_user.pk).exists())
        turno.refresh_from_db()
        self.assertEqual(turno.usuario_id, self.pro_user.pk)
        self.profesional.refresh_from_db()
        self.assertEqual(self.profesional.usuario_id, self.pro_user.pk)

    def test_eliminar_cuenta_vinculada_con_turnos_de_otros_permitido(self):
        # La regla es por turnos DEL USUARIO: turnos de otros clientes
        # atendidos por su profesional no impiden eliminar la cuenta.
        turno_otro = self.crear_turno(self.cliente, 'pendiente')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_usuario(self.pro_user.pk))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(pk=self.pro_user.pk).exists())
        self.profesional.refresh_from_db()
        self.assertIsNone(self.profesional.usuario_id)
        turno_otro.refresh_from_db()
        self.assertEqual(turno_otro.usuario_id, self.cliente.pk)
        self.assertEqual(turno_otro.profesional_id, self.profesional.pk)

    def test_rol_admin_sin_staff_no_puede_eliminar_usuarios(self):
        # Permiso actual (IsAdminUser): requiere is_staff.
        libre = self.crear_usuario('libre', 'libre@test.com')
        self.client.force_authenticate(user=self.rol_admin)
        resp = self.client.delete(self.url_usuario(libre.pk))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(User.objects.filter(pk=libre.pk).exists())

    def test_cliente_no_puede_eliminar_ni_se_a_si_mismo(self):
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.delete(self.url_usuario(self.cliente.pk))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(User.objects.filter(pk=self.cliente.pk).exists())

    def test_anonimo_no_puede_eliminar_usuarios(self):
        libre = self.crear_usuario('libre', 'libre@test.com')
        resp = self.client.delete(self.url_usuario(libre.pk))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(User.objects.filter(pk=libre.pk).exists())
