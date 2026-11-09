"""Etapa B3.1 — liberación de horarios cancelados.

La restricción única de ``Turno`` pasó a ser CONDICIONAL (índice único
parcial solo sobre turnos pendientes/confirmados): un turno cancelado
libera su (profesional, fecha, hora) para una nueva reserva, sin tocar el
registro original.

Tests nuevos (no reemplazan ni modifican los existentes):

- re-reserva sobre un turno cancelado en la misma hora → 201, con el
  cancelado original intacto y dos registros en la base;
- pendientes y confirmados siguen bloqueando el horario (400 con el
  mensaje de unicidad, sin registros extra);
- la condición se cumple en la BASE DE DATOS (índice parcial), no solo en
  el validador del serializer: dos activos en el mismo slot →
  ``IntegrityError``; un activo sobre un cancelado → permitido;
- carrera simulada sobre el slot liberado (``IntegrityError`` desde el
  guardado) → 400 controlado, sin registros nuevos (red de B3 intacta);
- flujo completo reservar → cancelar → re-reservar, con el horario
  reflejado correctamente en la consulta ``disponibles``;
- el rechazo por solape NO exacto sigue viniendo de las reglas de B1
  (mensaje «superpone»), no de la restricción única;
- dos turnos cancelados en el mismo horario coexisten en el historial.
"""

from datetime import time, timedelta
from unittest import mock

from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from rest_framework import status

from core.models import Turno
from core.tests import BaseAPITest


class BaseLiberacionTests(BaseAPITest):
    """Fixtures: franja 09:00-12:00 de mañana (fecha futura)."""

    def setUp(self):
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')
        self.profesional = self.crear_profesional('Pro')
        self.servicio30 = self.crear_servicio('Serv30', duracion_minutos=30)
        self.servicio60 = self.crear_servicio('Serv60', duracion_minutos=60)
        self.fecha = timezone.localdate() + timedelta(days=1)
        self.crear_disponibilidad(
            self.profesional, self.fecha, time(9, 0), time(12, 0)
        )

    def reservar(self, hora='09:00:00', servicio=None):
        """POST de reserva como cliente. Servicio por defecto: 30 min."""
        self.client.force_authenticate(user=self.cliente)
        return self.client.post(
            reverse('turno-list'),
            {
                'profesional': self.profesional.id,
                'servicio': (servicio or self.servicio30).id,
                'fecha': self.fecha.isoformat(),
                'hora': hora,
            },
            format='json',
        )

    def cancelar(self, turno):
        """POST de cancelación como dueño del turno (IsOwnerOrAdmin)."""
        self.client.force_authenticate(user=self.cliente)
        return self.client.post(
            reverse('turno-cancelar', kwargs={'pk': turno.pk}),
            {},
            format='json',
        )

    def horas_disponibles(self):
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get(
            reverse('turno-disponibles'),
            {
                'servicio': self.servicio30.id,
                'fecha': self.fecha.isoformat(),
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        return [item['hora'] for item in resp.data]

    def turnos_del_slot(self, hora=time(9, 0)):
        return Turno.objects.filter(
            fecha=self.fecha, hora=hora, profesional=self.profesional
        )


class ReReservaSobreCanceladoTests(BaseLiberacionTests):
    """Comportamiento central: el cancelado libera su horario."""

    def test_re_reserva_sobre_turno_cancelado_devuelve_201_y_conserva_historial(self):
        cancelado = Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='cancelado',
        )

        resp = self.reservar(hora='09:00:00')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # Dos registros en el mismo horario: el cancelado + el nuevo activo.
        self.assertEqual(self.turnos_del_slot().count(), 2)
        # El turno cancelado original permanece intacto.
        cancelado.refresh_from_db()
        self.assertEqual(cancelado.estado, 'cancelado')
        self.assertEqual(cancelado.servicio_id, self.servicio30.id)
        self.assertEqual(cancelado.fecha, self.fecha)
        self.assertEqual(cancelado.hora, time(9, 0))
        # El nuevo nace pendiente.
        nuevo = self.turnos_del_slot().exclude(pk=cancelado.pk).get()
        self.assertEqual(nuevo.estado, 'pendiente')

    def test_flujo_reservar_cancelar_re_reservar_con_disponibles(self):
        # 1) Reserva inicial: el horario queda ocupado.
        resp = self.reservar(hora='09:00:00')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        turno = self.turnos_del_slot().get(estado='pendiente')
        self.assertNotIn('09:00', self.horas_disponibles())

        # 2) El dueño cancela: el horario se libera y se ofrece.
        resp = self.cancelar(turno)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'cancelado')
        self.assertIn('09:00', self.horas_disponibles())

        # 3) Re-reserva del MISMO horario: aceptada.
        resp = self.reservar(hora='09:00:00')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # El cancelado sigue en el historial y el nuevo ocupa el slot.
        self.assertEqual(self.turnos_del_slot().count(), 2)
        self.assertEqual(
            self.turnos_del_slot().filter(estado='cancelado').count(), 1
        )
        self.assertEqual(
            self.turnos_del_slot().filter(estado='pendiente').count(), 1
        )
        # Y vuelve a estar ocupado en la consulta.
        self.assertNotIn('09:00', self.horas_disponibles())

    def test_dos_cancelados_en_el_mismo_horario_coexisten_en_historial(self):
        # Ciclo 1: reservar y cancelar.
        resp = self.reservar(hora='09:00:00')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        primero = self.turnos_del_slot().get(estado='pendiente')
        self.assertEqual(self.cancelar(primero).status_code, status.HTTP_200_OK)

        # Ciclo 2: re-reservar el liberado y cancelar de nuevo.
        resp = self.reservar(hora='09:00:00')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        segundo = self.turnos_del_slot().get(estado='pendiente')
        self.assertEqual(self.cancelar(segundo).status_code, status.HTTP_200_OK)

        # Ambos cancelados coexisten en el mismo horario (historial).
        cancelados = self.turnos_del_slot().filter(estado='cancelado')
        self.assertEqual(cancelados.count(), 2)
        self.assertCountEqual(
            [t.pk for t in cancelados], [primero.pk, segundo.pk]
        )

        # Y el horario queda libre para un tercer ciclo.
        resp = self.reservar(hora='09:00:00')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.turnos_del_slot().count(), 3)


class BloqueoPorTurnosActivosTests(BaseLiberacionTests):
    """Pendientes y confirmados siguen protegidos."""

    def test_turno_pendiente_sigue_bloqueando_el_horario(self):
        Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='pendiente',
        )

        resp = self.reservar(hora='09:00:00')

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('conjunto único', str(resp.data))
        # No se creó ningún registro extra.
        self.assertEqual(self.turnos_del_slot().count(), 1)

    def test_turno_confirmado_sigue_bloqueando_el_horario(self):
        Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='confirmado',
        )

        resp = self.reservar(hora='09:00:00')

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('conjunto único', str(resp.data))
        self.assertEqual(self.turnos_del_slot().count(), 1)


class RestriccionEnBaseDeDatosTests(BaseLiberacionTests):
    """La garantía la da el índice único PARCIAL, no solo el validador.

    Se crea vía ORM directo (sin pasar por DRF) para ejercitar la
    constraint de la base de datos tal cual.
    """

    def test_dos_turnos_activos_mismo_horario_violan_la_constraint(self):
        Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='pendiente',
        )

        # Segundo turno ACTIVO en el mismo slot: la base lo rechaza.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Turno.objects.create(
                    fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
                    profesional=self.profesional, servicio=self.servicio30,
                    estado='confirmado',
                )

        # Solo existe el primero: la transacción fallida no dejó nada.
        self.assertEqual(self.turnos_del_slot().count(), 1)

    def test_turno_activo_sobre_cancelado_no_viola_la_constraint(self):
        Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='cancelado',
        )

        # Un turno activo en el mismo slot del cancelado: permitido por el
        # índice parcial (la restricción vieja lo habría rechazado).
        nuevo = Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='pendiente',
        )

        self.assertEqual(self.turnos_del_slot().count(), 2)
        self.assertEqual(nuevo.estado, 'pendiente')

    def test_turnos_cancelados_no_entran_en_el_indice(self):
        # Dos cancelados en el mismo slot: ninguno indexado → sin error.
        Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='cancelado',
        )
        Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='cancelado',
        )
        self.assertEqual(self.turnos_del_slot().count(), 2)


class CarreraSobreSlotLiberadoTests(BaseLiberacionTests):
    """La red de B3 (IntegrityError → 400) cubre el índice parcial."""

    def test_integrity_error_al_re_reservar_slot_liberado_devuelve_400(self):
        # El slot está libre porque el turno anterior fue cancelado…
        cancelado = Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='cancelado',
        )
        # …pero otra petición ganó la carrera: el guardado levanta la
        # restricción única (mismo origen que en una carrera real).
        with mock.patch.object(
            Turno, 'save',
            side_effect=IntegrityError(
                'UNIQUE constraint failed: core_turno.profesional_id, '
                'core_turno.fecha, core_turno.hora'
            ),
        ):
            resp = self.reservar(hora='09:00:00')

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('ya existe una reserva', str(resp.data))
        # Sin registros nuevos: solo quedó el turno cancelado original.
        self.assertEqual(self.turnos_del_slot().count(), 1)
        cancelado.refresh_from_db()
        self.assertEqual(cancelado.estado, 'cancelado')


class SolapeTrasLiberarTests(BaseLiberacionTests):
    """Las reglas de solape de B1 siguen intactas tras la liberación."""

    def test_solape_no_exacto_con_el_nuevo_activo_devuelve_400_superpone(self):
        # Slot 09:00 liberado por un cancelado y re-reservado con un
        # servicio de 60 min (09:00-10:00).
        Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='cancelado',
        )
        resp = self.reservar(hora='09:00:00', servicio=self.servicio60)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        # Intento a las 09:30 con servicio de 30 min (09:30-10:00):
        # NO es un duplicado exacto de la restricción única, pero solapa
        # con el nuevo activo → lo rechazan las reglas de solape de B1.
        resp = self.reservar(hora='09:30:00', servicio=self.servicio30)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('superpone', str(resp.data))
        # Solo el activo de 09:00 quedó creado; el cancelado, intacto.
        activos = self.turnos_del_slot().filter(
            estado__in=['pendiente', 'confirmado']
        )
        self.assertEqual(activos.count(), 1)
        self.assertEqual(
            self.turnos_del_slot().filter(estado='cancelado').count(), 1
        )
