"""B10.3 — contrato de API del módulo «Clientas» (/api/clientas/).

La pantalla administrativa consume exactamente estos endpoints nuevos:

- ``GET /api/clientas/``: listado de cuentas con rol CLIENTE;
- ``GET /api/clientas/{id}/``: detalle de una clienta;
- ``GET /api/clientas/{id}/turnos/``: historial de turnos acotado;
- ``PATCH /api/clientas/{id}/``: activación / desactivación (is_active).

El módulo no reutiliza ``/api/users/`` (exige ``is_staff``, permite
cambiar roles y no expone ``is_active``); su comportamiento queda
intacto y sus tests siguen verdes. Aquí se cubre el contrato nuevo:
acceso por rol, acotado por identificador, activación/desactivación con
sus guardas, y que consultar el historial no altera los turnos.
"""

from datetime import time, timedelta

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from rest_framework import status

from core.models import Turno
from core.tests import BaseAPITest
from users.models import User


class BaseClientasTests(BaseAPITest):
    """Cuentas de los tres roles, turnos de dos clientas y catálogos."""

    def setUp(self):
        self.admin = self.crear_usuario(
            'admin', 'admin@test.com', role=User.Roles.ADMIN,
        )
        self.cliente = self.crear_usuario('carla', 'carla@test.com')
        self.cliente.nombre = 'Carla Gómez'
        self.cliente.save()
        self.otro_cliente = self.crear_usuario('otra', 'otra@test.com')
        self.otro_cliente.nombre = 'Ana Pérez'
        self.otro_cliente.save()
        self.pro_user = self.crear_usuario(
            'pro', 'pro@test.com', role=User.Roles.PERSONAL,
        )
        self.profesional = self.crear_profesional('María', usuario=self.pro_user)
        self.servicio = self.crear_servicio('Semi', duracion_minutos=30)
        # Fecha futura para que los turnos no se consideren comenzados.
        self.fecha = timezone.localdate() + timedelta(days=1)

    @staticmethod
    def url_list():
        return reverse('clientas-list')

    @staticmethod
    def url_detalle(pk):
        return reverse('clientas-detail', args=[pk])

    @staticmethod
    def url_historial(pk):
        return reverse('clientas-turnos', args=[pk])

    def crear_turno(self, usuario, estado='pendiente', hora=time(9, 0)):
        return Turno.objects.create(
            fecha=self.fecha,
            hora=hora,
            usuario=usuario,
            profesional=self.profesional,
            servicio=self.servicio,
            estado=estado,
        )


class ListadoClientasTests(BaseClientasTests):
    """GET /api/clientas/: sólo cuentas CLIENTE y sólo para ADMIN."""

    def test_admin_lista_solo_las_cuentas_cliente(self):
        # Hay también una cuenta ADMIN y una PERSONAL: no deben aparecer.
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url_list(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in resp.data['results']]
        self.assertIn(self.cliente.id, ids)
        self.assertIn(self.otro_cliente.id, ids)
        self.assertNotIn(self.admin.id, ids)
        self.assertNotIn(self.pro_user.id, ids)

    def test_el_listado_no_expone_datos_sensibles(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url_list(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for item in resp.data['results']:
            self.assertNotIn('password', item)
            self.assertNotIn('last_login', item)
            self.assertEqual(item['role'], User.Roles.CLIENTE)

    def test_anonimo_no_accede(self):
        resp = self.client.get(self.url_list(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cliente_no_accede_a_la_administracion(self):
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get(self.url_list(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_personal_no_accede_a_la_administracion(self):
        self.client.force_authenticate(user=self.pro_user)
        resp = self.client.get(self.url_list(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class DetalleYHistorialTests(BaseClientasTests):
    """Detalle e historial acotados a la clienta seleccionada."""

    def setUp(self):
        super().setUp()
        self.turno_pendiente = self.crear_turno(
            self.cliente, 'pendiente', time(9, 0),
        )
        self.turno_confirmado = self.crear_turno(
            self.cliente, 'confirmado', time(10, 0),
        )
        self.turno_cancelado = self.crear_turno(
            self.cliente, 'cancelado', time(11, 0),
        )
        self.turno_ajeno = self.crear_turno(
            self.otro_cliente, 'pendiente', time(12, 0),
        )
        self.client.force_authenticate(user=self.admin)

    def test_admin_consulta_el_detalle_de_una_clienta(self):
        resp = self.client.get(self.url_detalle(self.cliente.pk), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['id'], self.cliente.id)
        self.assertEqual(resp.data['nombre'], 'Carla Gómez')
        self.assertEqual(resp.data['email'], 'carla@test.com')
        self.assertEqual(resp.data['role'], User.Roles.CLIENTE)
        self.assertIn('is_active', resp.data)
        # Nunca datos internos de autenticación.
        self.assertNotIn('password', resp.data)

    def test_identificador_de_cuenta_admin_o_personal_devuelve_404(self):
        # IDs manipulados: fuera del queryset de clientas no hay datos.
        resp = self.client.get(self.url_detalle(self.admin.pk), format='json')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        resp = self.client.get(self.url_detalle(self.pro_user.pk), format='json')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_consulta_el_historial_acotado_a_la_clienta(self):
        resp = self.client.get(self.url_historial(self.cliente.pk), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in resp.data['results']]
        self.assertEqual(
            ids,
            [self.turno_cancelado.id, self.turno_confirmado.id, self.turno_pendiente.id],
        )
        # No se cuelan turnos de otras cuentas.
        self.assertNotIn(self.turno_ajeno.id, ids)
        estados = {item['estado'] for item in resp.data['results']}
        self.assertEqual(estados, {'pendiente', 'confirmado', 'cancelado'})

    def test_el_historial_identifica_fecha_hora_servicio_y_profesional(self):
        resp = self.client.get(self.url_historial(self.cliente.pk), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for item in resp.data['results']:
            self.assertEqual(item['fecha'], self.fecha.isoformat())
            self.assertIn('hora', item)
            self.assertEqual(item['servicio'], self.servicio.id)
            self.assertEqual(item['profesional'], self.profesional.id)
            self.assertEqual(item['usuario_nombre'], 'Carla Gómez')

    def test_historial_con_identificador_manipulado_no_expone_info(self):
        resp = self.client.get(self.url_historial(self.admin.pk), format='json')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        resp = self.client.get(self.url_historial(self.pro_user.pk), format='json')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_cliente_no_accede_al_historial_de_otras_cuentas(self):
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get(self.url_historial(self.otro_cliente.pk), format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_personal_no_accede_al_historial(self):
        self.client.force_authenticate(user=self.pro_user)
        resp = self.client.get(self.url_historial(self.cliente.pk), format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_consultar_el_historial_no_modifica_los_turnos(self):
        antes = {
            t.pk: (t.estado, t.usuario_id, t.profesional_id, t.servicio_id, t.fecha, t.hora)
            for t in Turno.objects.all()
        }
        resp = self.client.get(self.url_historial(self.cliente.pk), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for t in Turno.objects.all():
            self.assertEqual(
                (t.estado, t.usuario_id, t.profesional_id, t.servicio_id, t.fecha, t.hora),
                antes[t.pk],
            )


class ActivacionTests(BaseClientasTests):
    """Activación / desactivación con is_active, sin borrado físico."""

    def setUp(self):
        super().setUp()
        self.turno = self.crear_turno(self.cliente, 'pendiente', time(9, 0))
        self.client.force_authenticate(user=self.admin)

    def test_admin_desactiva_una_clienta(self):
        resp = self.client.patch(
            self.url_detalle(self.cliente.pk), {'is_active': False}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.is_active)

    def test_admin_reactiva_una_clienta_desactivada(self):
        resp = self.client.patch(
            self.url_detalle(self.cliente.pk), {'is_active': False}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        resp = self.client.patch(
            self.url_detalle(self.cliente.pk), {'is_active': True}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.is_active)

    def test_cuenta_desactivada_no_puede_autenticarse(self):
        resp = self.client.patch(
            self.url_detalle(self.cliente.pk), {'is_active': False}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        cache.clear()
        resp = self.client.post(
            reverse('token_obtain_pair'),
            {'email': self.cliente.email, 'password': 'pass1234'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_desactivar_no_elimina_la_cuenta_ni_sus_turnos(self):
        resp = self.client.patch(
            self.url_detalle(self.cliente.pk), {'is_active': False}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        # La cuenta sigue existiendo (baja lógica, no física)…
        self.assertTrue(User.objects.filter(pk=self.cliente.pk).exists())
        # …y sus turnos conservan estados y relaciones originales.
        self.turno.refresh_from_db()
        self.assertEqual(self.turno.estado, 'pendiente')
        self.assertEqual(self.turno.usuario_id, self.cliente.id)
        self.assertEqual(self.turno.profesional_id, self.profesional.id)
        self.assertEqual(self.turno.servicio_id, self.servicio.id)
        self.assertEqual(Turno.objects.filter(usuario=self.cliente).count(), 1)

    def test_no_puede_desactivar_cuenta_admin(self):
        resp = self.client.patch(
            self.url_detalle(self.admin.pk), {'is_active': False}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_no_puede_desactivar_cuenta_personal(self):
        resp = self.client.patch(
            self.url_detalle(self.pro_user.pk), {'is_active': False}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.pro_user.refresh_from_db()
        self.assertTrue(self.pro_user.is_active)

    def test_no_se_pueden_cambiar_roles_ni_el_email_desde_el_modulo(self):
        resp = self.client.patch(
            self.url_detalle(self.cliente.pk),
            {'role': User.Roles.ADMIN, 'email': 'intruso@test.com'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.role, User.Roles.CLIENTE)
        self.assertEqual(self.cliente.email, 'carla@test.com')

    def test_un_admin_no_es_clienta_y_no_se_encuentra_para_desactivarse(self):
        # La cuenta del administrador ni siquiera entra en el queryset:
        # no puede desactivarse a sí mismo desde este módulo.
        resp = self.client.patch(
            self.url_detalle(self.admin.pk), {'is_active': False}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_guarda_contra_la_auto_desactivacion(self):
        # Caso límite: una cuenta staff con rol CLIENTE sí entra en el
        # queryset y pasa IsAdmin; la guarda explícita la frena (400).
        staff_cliente = self.crear_usuario(
            'staffcli', 'staffcli@test.com', staff=True,
        )
        self.client.force_authenticate(user=staff_cliente)
        resp = self.client.patch(
            self.url_detalle(staff_cliente.pk), {'is_active': False}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('propia cuenta', str(resp.data))
        staff_cliente.refresh_from_db()
        self.assertTrue(staff_cliente.is_active)

    def test_delete_no_esta_admitido_no_hay_borrado_fisico(self):
        resp = self.client.delete(self.url_detalle(self.cliente.pk))
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(User.objects.filter(pk=self.cliente.pk).exists())
        self.assertEqual(Turno.objects.filter(usuario=self.cliente).count(), 1)

    def test_post_no_esta_admitido_el_alta_es_el_registro_publico(self):
        resp = self.client.post(
            self.url_list(), {'username': 'nueva', 'email': 'nueva@test.com'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertFalse(User.objects.filter(username='nueva').exists())
