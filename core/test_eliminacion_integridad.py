"""Etapa B6 — protección de eliminaciones en la API (core).

Verifica las protecciones de integridad del diagnóstico B5 sobre los
endpoints DELETE de servicios y profesionales:

- un servicio con turnos (cualquier estado) no se elimina → 400;
- un profesional con turnos o disponibilidades no se elimina → 400;
- un profesional vinculado a una cuenta no se elimina → 400 (D3);
- los permisos de escritura son exclusivos de ADMIN (D1): PERSONAL,
  CLIENTE y anónimos no escriben servicios ni profesionales;
- la visibilidad de los no admin (solo servicios activos) no cambia;
- regresión: DELETE de turnos sigue 405 y las disponibilidades
  conservan sus protecciones de B2/B3.

Se reutiliza ``BaseAPITest`` de core/tests.py sin modificarlo. Patrones
de los tests existentes de la serie.
"""

from datetime import time, timedelta

from django.urls import reverse
from django.utils import timezone

from rest_framework import status

from core.models import Disponibilidad, Profesional, Servicio, Turno
from core.tests import BaseAPITest
from users.models import User


class BaseEliminacionCoreTests(BaseAPITest):
    """Usuarios de prueba, profesional, servicio y fecha futura."""

    def setUp(self):
        self.admin = self.crear_usuario(
            'admin', 'admin@test.com', role=User.Roles.ADMIN, staff=True,
        )
        self.rol_admin = self.crear_usuario(
            'roladmin', 'roladmin@test.com', role=User.Roles.ADMIN,
        )
        self.personal = self.crear_usuario(
            'personal', 'personal@test.com', role=User.Roles.PERSONAL,
        )
        # D3: toda cuenta PERSONAL nace con su Profesional vinculado.
        self.personal_profesional = self.crear_profesional(
            'Pro Personal', usuario=self.personal,
        )
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')
        self.pro_user = self.crear_usuario(
            'pro', 'pro@test.com', role=User.Roles.PERSONAL,
        )
        self.profesional = self.crear_profesional(
            'Pro A', usuario=self.pro_user,
        )
        self.servicio = self.crear_servicio('Semi', duracion_minutos=30)
        # Fecha futura para que los turnos no se consideren comenzados.
        self.fecha = timezone.localdate() + timedelta(days=1)

    def url_servicio(self, pk=None):
        return reverse('servicio-detail', args=[pk or self.servicio.pk])

    def url_profesional(self, pk=None):
        return reverse('profesional-detail', args=[pk or self.profesional.pk])

    def crear_turno(self, estado='pendiente', hora=time(9, 0), **kwargs):
        datos = dict(
            fecha=self.fecha,
            hora=hora,
            usuario=kwargs.pop('usuario', self.cliente),
            profesional=kwargs.pop('profesional', self.profesional),
            servicio=kwargs.pop('servicio', self.servicio),
            estado=estado,
        )
        datos.update(kwargs)
        return Turno.objects.create(**datos)

    def crear_turnos(self):
        """Un turno pendiente, otro confirmado y otro cancelado."""
        return [
            self.crear_turno('pendiente', time(9, 0)),
            self.crear_turno('confirmado', time(10, 0)),
            self.crear_turno('cancelado', time(11, 0)),
        ]


class ServicioEliminacionTests(BaseEliminacionCoreTests):
    """DELETE /api/servicios/{id}/ — integridad y permisos actuales."""

    def test_admin_elimina_servicio_sin_turnos(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_servicio())
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Servicio.objects.filter(pk=self.servicio.pk).exists())

    def test_admin_no_elimina_servicio_con_turno_pendiente(self):
        turno = self.crear_turno('pendiente')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_servicio())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('No se puede eliminar el servicio', str(resp.data))
        self.assertTrue(Servicio.objects.filter(pk=self.servicio.pk).exists())
        turno.refresh_from_db()
        self.assertEqual(turno.servicio_id, self.servicio.pk)

    def test_admin_no_elimina_servicio_con_turno_confirmado(self):
        turno = self.crear_turno('confirmado')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_servicio())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Servicio.objects.filter(pk=self.servicio.pk).exists())
        turno.refresh_from_db()
        self.assertEqual(turno.servicio_id, self.servicio.pk)

    def test_admin_no_elimina_servicio_con_turno_cancelado(self):
        # Incluidos los cancelados: son parte del historial.
        turno = self.crear_turno('cancelado')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_servicio())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Servicio.objects.filter(pk=self.servicio.pk).exists())
        turno.refresh_from_db()
        self.assertEqual(turno.servicio_id, self.servicio.pk)

    def test_personal_no_elimina_servicio_con_turnos(self):
        # D1: aunque el servicio tuviera turnos, PERSONAL no gestiona
        # servicios: el permiso se rechaza antes de validar integridad.
        self.crear_turnos()
        self.client.force_authenticate(user=self.personal)
        resp = self.client.delete(self.url_servicio())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Servicio.objects.filter(pk=self.servicio.pk).exists())
        self.assertEqual(Turno.objects.filter(servicio=self.servicio).count(), 3)

    def test_personal_no_puede_eliminar_servicio_sin_turnos(self):
        # D1: los permisos de escritura de servicios son exclusivos de
        # ADMIN; PERSONAL recibe 403 aunque no haya dependencias.
        self.client.force_authenticate(user=self.personal)
        resp = self.client.delete(self.url_servicio())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Servicio.objects.filter(pk=self.servicio.pk).exists())

    def test_cliente_no_puede_eliminar_servicio(self):
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.delete(self.url_servicio())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Servicio.objects.filter(pk=self.servicio.pk).exists())

    def test_anonimo_no_puede_eliminar_servicio(self):
        resp = self.client.delete(self.url_servicio())
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(Servicio.objects.filter(pk=self.servicio.pk).exists())

    def test_personal_no_ve_servicio_inactivo(self):
        # Visibilidad: el queryset de los no admin solo incluye servicios
        # activos → 404 en lectura; y la escritura se niega con 403 (D1).
        self.servicio.is_active = False
        self.servicio.save()
        self.client.force_authenticate(user=self.personal)
        resp = self.client.get(self.url_servicio())
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        resp_delete = self.client.delete(self.url_servicio())
        self.assertEqual(resp_delete.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Servicio.objects.filter(pk=self.servicio.pk).exists())

    def test_admin_no_elimina_servicio_inactivo_con_turnos(self):
        self.servicio.is_active = False
        self.servicio.save()
        turno = self.crear_turno('pendiente')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_servicio())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Servicio.objects.filter(pk=self.servicio.pk).exists())
        turno.refresh_from_db()
        self.assertEqual(turno.servicio_id, self.servicio.pk)

    def test_admin_elimina_servicio_inactivo_sin_turnos(self):
        self.servicio.is_active = False
        self.servicio.save()
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_servicio())
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Servicio.objects.filter(pk=self.servicio.pk).exists())

    def test_rol_admin_sin_staff_elimina_servicio_sin_turnos(self):
        # Permiso actual (IsAdmin): el rol ADMIN sin staff también puede
        # eliminar.
        self.client.force_authenticate(user=self.rol_admin)
        resp = self.client.delete(self.url_servicio())
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Servicio.objects.filter(pk=self.servicio.pk).exists())


class ProfesionalEliminacionTests(BaseEliminacionCoreTests):
    """DELETE /api/profesionales/{id}/ — integridad y permisos actuales."""

    def test_admin_elimina_profesional_sin_dependencias(self):
        libre = self.crear_profesional('SinDep')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_profesional(libre.pk))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Profesional.objects.filter(pk=libre.pk).exists())

    def test_admin_no_elimina_profesional_con_turno_pendiente(self):
        turno = self.crear_turno('pendiente')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_profesional())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('No se puede eliminar el profesional', str(resp.data))
        self.assertTrue(Profesional.objects.filter(pk=self.profesional.pk).exists())
        turno.refresh_from_db()
        self.assertEqual(turno.profesional_id, self.profesional.pk)

    def test_admin_no_elimina_profesional_con_turno_confirmado(self):
        turno = self.crear_turno('confirmado')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_profesional())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Profesional.objects.filter(pk=self.profesional.pk).exists())
        turno.refresh_from_db()
        self.assertEqual(turno.profesional_id, self.profesional.pk)

    def test_admin_no_elimina_profesional_con_turno_cancelado(self):
        turno = self.crear_turno('cancelado')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_profesional())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Profesional.objects.filter(pk=self.profesional.pk).exists())
        turno.refresh_from_db()
        self.assertEqual(turno.profesional_id, self.profesional.pk)

    def test_admin_no_elimina_profesional_con_disponibilidades(self):
        franja = self.crear_disponibilidad(
            self.profesional, self.fecha, time(9, 0), time(12, 0),
        )
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_profesional())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('disponibilidades asociadas', str(resp.data))
        self.assertTrue(Profesional.objects.filter(pk=self.profesional.pk).exists())
        self.assertTrue(Disponibilidad.objects.filter(pk=franja.pk).exists())

    def test_admin_no_elimina_profesional_con_turnos_y_disponibilidades(self):
        # Ante ambas dependencias se informa primero la de los turnos.
        self.crear_turnos()
        self.crear_disponibilidad(
            self.profesional, self.fecha, time(9, 0), time(12, 0),
        )
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_profesional())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('tiene turnos asociados', str(resp.data))
        self.assertTrue(Profesional.objects.filter(pk=self.profesional.pk).exists())
        self.assertEqual(Disponibilidad.objects.count(), 1)
        self.assertEqual(Turno.objects.count(), 3)

    def test_admin_no_elimina_profesional_vinculado(self):
        # D3: sin turnos ni disponibilidades, pero vinculado a la cuenta
        # PERSONAL pro_user: eliminarlo la dejaría sin su Profesional.
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_profesional())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('vinculado', str(resp.data))
        self.assertTrue(Profesional.objects.filter(pk=self.profesional.pk).exists())
        self.assertEqual(self.profesional.usuario_id, self.pro_user.pk)
        self.pro_user.refresh_from_db()
        self.assertEqual(self.pro_user.role, User.Roles.PERSONAL)

    def test_admin_no_puede_desvincular_la_cuenta_personal(self):
        # Mismo invariante por la vía de edición: el vínculo es inmutable
        # mientras la cuenta exista.
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            self.url_profesional(), {'usuario': None}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('usuario', resp.data)
        self.profesional.refresh_from_db()
        self.assertEqual(self.profesional.usuario_id, self.pro_user.pk)

    def test_personal_no_puede_eliminar_profesional(self):
        self.client.force_authenticate(user=self.personal)
        resp = self.client.delete(self.url_profesional())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Profesional.objects.filter(pk=self.profesional.pk).exists())

    def test_cliente_no_puede_eliminar_profesional(self):
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.delete(self.url_profesional())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Profesional.objects.filter(pk=self.profesional.pk).exists())

    def test_anonimo_no_puede_eliminar_profesional(self):
        resp = self.client.delete(self.url_profesional())
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(Profesional.objects.filter(pk=self.profesional.pk).exists())

    def test_rol_admin_sin_staff_elimina_profesional_sin_dependencias(self):
        libre = self.crear_profesional('SinDep')
        self.client.force_authenticate(user=self.rol_admin)
        resp = self.client.delete(self.url_profesional(libre.pk))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Profesional.objects.filter(pk=libre.pk).exists())


class RegresionEliminacionTests(BaseEliminacionCoreTests):
    """Las protecciones previas (B1–B3.1) siguen intactas."""

    def test_delete_turno_sigue_devolviendo_405(self):
        turno = self.crear_turno('pendiente')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(
            reverse('turno-detail', args=[turno.pk])
        )
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Turno.objects.filter(pk=turno.pk).exists())

    def test_delete_disponibilidad_con_turno_activo_sigue_rechazada(self):
        franja = self.crear_disponibilidad(
            self.profesional, self.fecha, time(9, 0), time(12, 0),
        )
        self.crear_turno('pendiente', time(9, 0))
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(
            reverse('disponibilidad-detail', args=[franja.pk])
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Disponibilidad.objects.filter(pk=franja.pk).exists())

    def test_delete_disponibilidad_sin_turnos_sigue_permitida(self):
        franja = self.crear_disponibilidad(
            self.profesional, self.fecha, time(9, 0), time(12, 0),
        )
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(
            reverse('disponibilidad-detail', args=[franja.pk])
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Disponibilidad.objects.filter(pk=franja.pk).exists())
