"""Etapa B2 — integridad y permisos de disponibilidades.

Tests nuevos (no reemplazan ni modifican los existentes):

- fechas pasadas: no se crean, no se modifican, no se eliminan; sí se consultan;
- cambio de fecha: se valida la cobertura de turnos futuros tanto en el día
  origen (que pierde la franja) como en el día destino (que la gana);
- turnos pasados (aunque estén pendientes/confirmados) no bloquean el
  mantenimiento (reloj congelado para que sea determinístico);
- profesional sin usuario vinculado: creación/modificación/eliminación solo
  por administrador;
- turnos sin servicio: sin ``TypeError`` al modificar disponibilidades;
- turnos cancelados: no bloquean modificación ni eliminación;
- solapamientos rechazados, franjas contiguas permitidas y un turno que no
  puede cruzar el límite de dos franjas contiguas.
"""

from datetime import datetime, time, timedelta
from unittest import mock

from django.urls import reverse
from django.utils import timezone

from rest_framework import status

from core.models import Disponibilidad, Turno
from core.tests import BaseAPITest
from users.models import User


class BaseDisponibilidadIntegridadTests(BaseAPITest):
    def setUp(self):
        self.admin = self.crear_usuario('admin', 'admin@test.com', role=User.Roles.ADMIN, staff=True)
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')  # no vinculado
        self.pro_user = self.crear_usuario('pro', 'pro@test.com', role=User.Roles.PERSONAL)  # vinculado abajo
        self.profesional = self.crear_profesional('Pro', usuario=self.pro_user)
        self.profesional_sin_usuario = self.crear_profesional('ProSinUser')
        self.servicio30 = self.crear_servicio('Serv30', duracion_minutos=30)
        self.servicio60 = self.crear_servicio('Serv60', duracion_minutos=60)
        # Fecha futura neutra: los casos dependientes del reloj usan reloj congelado.
        self.fecha = timezone.localdate() + timedelta(days=1)

    def url_list(self):
        return reverse('disponibilidad-list')

    def url_detail(self, pk):
        return reverse('disponibilidad-detail', args=[pk])

    def crear_por_api(self, usuario, profesional=None, fecha=None,
                      ini='09:00:00', fin='12:00:00'):
        self.client.force_authenticate(user=usuario)
        return self.client.post(
            self.url_list(),
            {
                'profesional': (profesional or self.profesional).id,
                'fecha': (fecha or self.fecha).isoformat(),
                'hora_inicio': ini,
                'hora_fin': fin,
            },
            format='json',
        )

    def editar_por_api(self, usuario, pk, **campos):
        self.client.force_authenticate(user=usuario)
        return self.client.patch(self.url_detail(pk), campos, format='json')

    def eliminar_por_api(self, usuario, pk):
        self.client.force_authenticate(user=usuario)
        return self.client.delete(self.url_detail(pk), format='json')

    @staticmethod
    def ahora_congelada(hora, fecha=None):
        """Fecha (por defecto hoy) a las `hora` como aware, para congelar now()."""
        fecha = fecha or timezone.localdate()
        return timezone.make_aware(datetime.combine(fecha, hora))


class FechaPasadaTests(BaseDisponibilidadIntegridadTests):
    """El pasado es de solo lectura: crear, modificar y eliminar, rechazados."""

    def test_crear_disponibilidad_en_fecha_pasada_400(self):
        ayer = timezone.localdate() - timedelta(days=1)
        resp = self.crear_por_api(self.admin, fecha=ayer)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('anterior a hoy', str(resp.data))

    def test_modificar_disponibilidad_de_fecha_pasada_400(self):
        ayer = timezone.localdate() - timedelta(days=1)
        disp = self.crear_disponibilidad(self.profesional, ayer, time(9, 0), time(12, 0))

        # a) Edición sin cambiar la fecha.
        resp = self.editar_por_api(self.admin, disp.pk, hora_fin='13:00:00')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('fecha pasada', str(resp.data))

        # b) Edición que intenta moverla a una fecha futura: también rechazada.
        resp = self.editar_por_api(self.admin, disp.pk, fecha=self.fecha.isoformat())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('fecha pasada', str(resp.data))

        # La franja histórica queda intacta.
        disp.refresh_from_db()
        self.assertEqual(disp.fecha, ayer)
        self.assertEqual(disp.hora_fin, time(12, 0))

    def test_eliminar_disponibilidad_de_fecha_pasada_400(self):
        ayer = timezone.localdate() - timedelta(days=1)
        disp = self.crear_disponibilidad(self.profesional, ayer, time(9, 0), time(12, 0))
        resp = self.eliminar_por_api(self.admin, disp.pk)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('fecha pasada', str(resp.data))
        self.assertTrue(Disponibilidad.objects.filter(pk=disp.pk).exists())

    def test_consultar_disponibilidades_historicas_permitido(self):
        ayer = timezone.localdate() - timedelta(days=1)
        disp = self.crear_disponibilidad(self.profesional, ayer, time(9, 0), time(12, 0))
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get(
            self.url_list(),
            {'profesional': self.profesional.id, 'fecha': ayer.isoformat()},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in resp.data['results']]
        self.assertIn(disp.pk, ids)


class CambioDeFechaTests(BaseDisponibilidadIntegridadTests):
    """Al cambiar la fecha se valida la cobertura en el día origen y destino."""

    def test_cambiar_fecha_con_turnos_cubiertos_en_el_dia_original_200(self):
        # Día origen: A (la que se mueve, sin turnos) y B con un turno dentro.
        disp_a = self.crear_disponibilidad(self.profesional, self.fecha, time(14, 0), time(16, 0))
        self.crear_disponibilidad(self.profesional, self.fecha, time(10, 0), time(12, 0))
        Turno.objects.create(
            fecha=self.fecha, hora=time(11, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='pendiente',
        )
        otro_dia = self.fecha + timedelta(days=1)

        resp = self.editar_por_api(self.admin, disp_a.pk, fecha=otro_dia.isoformat())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        disp_a.refresh_from_db()
        self.assertEqual(disp_a.fecha, otro_dia)
        # El turno del día origen sigue cubierto por la franja B.
        self.assertTrue(
            Turno.objects.filter(fecha=self.fecha, hora=time(11, 0)).exists()
        )

    def test_rechazar_cambio_de_fecha_que_deja_turno_sin_cobertura_400(self):
        # Día origen con una única franja que contiene al turno.
        disp_a = self.crear_disponibilidad(self.profesional, self.fecha, time(9, 0), time(12, 0))
        Turno.objects.create(
            fecha=self.fecha, hora=time(10, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='pendiente',
        )
        otro_dia = self.fecha + timedelta(days=1)

        resp = self.editar_por_api(self.admin, disp_a.pk, fecha=otro_dia.isoformat())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('fuera de la disponibilidad', str(resp.data))
        # La franja no se movió: el turno no perdió cobertura.
        disp_a.refresh_from_db()
        self.assertEqual(disp_a.fecha, self.fecha)


class MantenimientoTurnosPasadosTests(BaseDisponibilidadIntegridadTests):
    """Los turnos ya comenzados no bloquean mantenimiento (reloj congelado)."""

    def test_mantenimiento_permitido_cuando_solo_hay_turnos_pasados(self):
        hoy = timezone.localdate()
        disp = self.crear_disponibilidad(self.profesional, hoy, time(9, 0), time(12, 0))
        Turno.objects.create(
            fecha=hoy, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='pendiente',
        )
        congelado = self.ahora_congelada(time(18, 0))

        with mock.patch('django.utils.timezone.now', return_value=congelado):
            resp_patch = self.editar_por_api(self.pro_user, disp.pk, hora_fin='13:00:00')
            self.assertEqual(resp_patch.status_code, status.HTTP_200_OK)

            resp_delete = self.eliminar_por_api(self.pro_user, disp.pk)
            self.assertEqual(resp_delete.status_code, status.HTTP_204_NO_CONTENT)

        # El turno histórico pendiente no fue modificado ni eliminado.
        self.assertTrue(
            Turno.objects.filter(fecha=hoy, hora=time(9, 0), estado='pendiente').exists()
        )


class PermisosSinUsuarioTests(BaseDisponibilidadIntegridadTests):
    """Profesional sin usuario vinculado: solo un administrador lo gestiona."""

    def test_usuario_no_admin_no_puede_crear_modificar_eliminar_403(self):
        # Creación.
        resp = self.crear_por_api(
            self.cliente, profesional=self.profesional_sin_usuario
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('administrador', str(resp.data))

        # Modificación y eliminación de una franja existente.
        disp = self.crear_disponibilidad(
            self.profesional_sin_usuario, self.fecha, time(9, 0), time(12, 0)
        )
        resp = self.editar_por_api(self.cliente, disp.pk, hora_fin='13:00:00')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        resp = self.eliminar_por_api(self.cliente, disp.pk)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Disponibilidad.objects.filter(pk=disp.pk).exists())

    def test_admin_puede_crear_modificar_eliminar(self):
        resp = self.crear_por_api(
            self.admin, profesional=self.profesional_sin_usuario
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        pk = resp.data['id']

        resp = self.editar_por_api(self.admin, pk, hora_fin='13:00:00')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        resp = self.eliminar_por_api(self.admin, pk)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Disponibilidad.objects.filter(pk=pk).exists())


class TurnosSinServicioTests(BaseDisponibilidadIntegridadTests):
    """intervalo() None (turno sin servicio) no produce TypeError."""

    def test_modificar_y_eliminar_con_turno_futuro_sin_servicio(self):
        disp = self.crear_disponibilidad(self.profesional, self.fecha, time(9, 0), time(12, 0))
        Turno.objects.create(
            fecha=self.fecha, hora=time(10, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=None,
            estado='pendiente',
        )

        # Antes de B2: TypeError al desempaquetar intervalo() → 500.
        resp = self.editar_por_api(self.pro_user, disp.pk, hora_fin='13:00:00')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        resp = self.eliminar_por_api(self.pro_user, disp.pk)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        # El turno histórico queda intacto.
        self.assertTrue(
            Turno.objects.filter(fecha=self.fecha, hora=time(10, 0), servicio=None).exists()
        )


class TurnosCanceladosTests(BaseDisponibilidadIntegridadTests):
    """Los turnos cancelados no bloquean modificación ni eliminación."""

    def test_turno_cancelado_no_bloquea_modificacion_ni_eliminacion(self):
        disp = self.crear_disponibilidad(self.profesional, self.fecha, time(9, 0), time(12, 0))
        Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='cancelado',
        )

        resp = self.editar_por_api(self.pro_user, disp.pk, hora_fin='13:00:00')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        resp = self.eliminar_por_api(self.pro_user, disp.pk)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)


class SolapamientoYContiguasTests(BaseDisponibilidadIntegridadTests):
    """Solape prohibido; contiguas permitidas; un turno no cruza franjas."""

    def test_solapamiento_rechazado_y_franjas_contiguas_permitidas(self):
        r1 = self.crear_por_api(self.pro_user, ini='09:00:00', fin='12:00:00')
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)

        # Solapada (11:00-13:00 pisa 09:00-12:00) → rechazada.
        r2 = self.crear_por_api(self.pro_user, ini='11:00:00', fin='13:00:00')
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)

        # Contigua (12:00-15:00 toca el fin de la primera) → permitida.
        r3 = self.crear_por_api(self.pro_user, ini='12:00:00', fin='15:00:00')
        self.assertEqual(r3.status_code, status.HTTP_201_CREATED)

    def test_turno_no_puede_cruzar_el_limite_de_dos_franjas_contiguas(self):
        # Franjas contiguas 09:00-12:00 y 12:00-15:00.
        self.crear_disponibilidad(self.profesional, self.fecha, time(9, 0), time(12, 0))
        self.crear_disponibilidad(self.profesional, self.fecha, time(12, 0), time(15, 0))
        self.client.force_authenticate(user=self.cliente)

        # 11:30 + 60 min = 12:30: no cabe entero en una sola franja → 400.
        resp = self.client.post(
            reverse('turno-list'),
            {
                'profesional': self.profesional.id,
                'servicio': self.servicio60.id,
                'fecha': self.fecha.isoformat(),
                'hora': '11:30:00',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('disponibilidad', str(resp.data))

        # 12:00 + 60 min = 13:00: cabe entero en la segunda franja → 201.
        resp = self.client.post(
            reverse('turno-list'),
            {
                'profesional': self.profesional.id,
                'servicio': self.servicio60.id,
                'fecha': self.fecha.isoformat(),
                'hora': '12:00:00',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
