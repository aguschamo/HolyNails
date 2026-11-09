"""Etapa B1 — validaciones de creación de reservas y horarios disponibles.

Tests nuevos (no reemplazan ni modifican los existentes):

- profesional obligatorio en el alta (ausente y ``null``);
- servicios inactivos rechazados en la creación y en ``disponibles``;
- profesional inactivo rechazado;
- hoy con hora ya pasada rechazado / hoy con hora futura aceptado
  (reloj congelado con ``mock.patch`` sobre ``timezone.now``, mismo patrón
  que ``core/test_transiciones_estado.py``);
- ``disponibles``: fecha pasada rechazada y hoy sin horas ya pasadas;
- duración que cruza la medianoche rechazada;
- encaje exacto al final de la franja aceptado;
- turnos pendiente/confirmado bloquean horarios; cancelados lo liberan;
- turnos históricos sin profesional siguen siendo consultables.
"""

from datetime import datetime, time, timedelta
from unittest import mock

from django.urls import reverse
from django.utils import timezone

from rest_framework import status

from core.models import Servicio, Turno
from core.tests import BaseAPITest


class BaseReservaCreacionTests(BaseAPITest):
    """Fixtures compartidas.

    La fecha base es futura para que los casos que no dependen de la hora
    sean determinísticos a cualquier hora del día (la regla "hoy con la
    hora ya pasada" se ejerce con el reloj congelado en los tests puntuales).
    """

    def setUp(self):
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')
        self.profesional = self.crear_profesional('Pro')
        self.servicio30 = self.crear_servicio('Serv30', duracion_minutos=30)
        self.servicio60 = self.crear_servicio('Serv60', duracion_minutos=60)
        self.fecha = timezone.localdate() + timedelta(days=1)
        self.crear_disponibilidad(self.profesional, self.fecha, time(9, 0), time(12, 0))

    def url_turnos(self):
        return reverse('turno-list')

    def url_disponibles(self):
        return reverse('turno-disponibles')

    def payload_turno(self, **datos):
        payload = {
            'profesional': self.profesional.id,
            'servicio': self.servicio60.id,
            'fecha': self.fecha.isoformat(),
            'hora': '09:00:00',
        }
        payload.update(datos)
        return payload

    def reservar(self, **datos):
        self.client.force_authenticate(user=self.cliente)
        return self.client.post(
            self.url_turnos(), self.payload_turno(**datos), format='json'
        )

    def consultar_disponibles(self, **params):
        self.client.force_authenticate(user=self.cliente)
        payload = {
            'servicio': self.servicio60.id,
            'fecha': self.fecha.isoformat(),
        }
        payload.update(params)
        return self.client.get(self.url_disponibles(), payload, format='json')

    @staticmethod
    def ahora_congelada(hora):
        """Fecha de hoy a las `hora` como fecha aware, para congelar now()."""
        return timezone.make_aware(datetime.combine(timezone.localdate(), hora))

    @staticmethod
    def horas_de(resp):
        """Horas ('HH:MM') de la respuesta de ``disponibles``."""
        return [item['hora'] for item in resp.data]


class ProfesionalObligatorioTests(BaseReservaCreacionTests):
    """Toda reserva nueva exige profesional; lo histórico sigue consultable."""

    def test_reserva_sin_profesional_400(self):
        self.client.force_authenticate(user=self.cliente)
        payload = self.payload_turno()
        payload.pop('profesional')
        resp = self.client.post(self.url_turnos(), payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Debe seleccionar un profesional', str(resp.data))

    def test_reserva_con_profesional_null_400(self):
        resp = self.reservar(profesional=None)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Debe seleccionar un profesional', str(resp.data))

    def test_turno_historico_sin_profesional_sigue_consultable(self):
        turno = Turno.objects.create(
            fecha=timezone.localdate() - timedelta(days=30),
            hora=time(10, 0),
            usuario=self.cliente,
            profesional=None,
            servicio=self.servicio30,
            estado='confirmado',
        )
        self.client.force_authenticate(user=self.cliente)

        resp = self.client.get(
            reverse('turno-detail', kwargs={'pk': turno.pk}), format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(resp.data['profesional'])

        # Sigue apareciendo en el listado de su dueño.
        resp_list = self.client.get(self.url_turnos(), format='json')
        ids = [item['id'] for item in resp_list.data['results']]
        self.assertIn(turno.pk, ids)


class ServicioYProfesionalInactivoTests(BaseReservaCreacionTests):
    """Servicios/profesionales inactivos no se reservan ni se ofrecen."""

    def test_reserva_con_servicio_inactivo_400(self):
        # El ID viaja directo en el payload: la validación es del backend.
        self.servicio60.is_active = False
        self.servicio60.save()
        resp = self.reservar()
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('El servicio seleccionado está inactivo', str(resp.data))

    def test_reserva_con_profesional_inactivo_400(self):
        self.profesional.is_active = False
        self.profesional.save()
        resp = self.reservar()
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('El profesional seleccionado no está activo', str(resp.data))

    def test_disponibles_con_servicio_inactivo_400(self):
        self.servicio60.is_active = False
        self.servicio60.save()
        resp = self.consultar_disponibles()
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('El servicio seleccionado está inactivo', str(resp.data))


class FechaYHoraTests(BaseReservaCreacionTests):
    """Fecha y hora se comparan en conjunto contra el reloj del proyecto."""

    def test_reserva_hoy_con_hora_pasada_400(self):
        hoy = timezone.localdate()
        self.crear_disponibilidad(self.profesional, hoy, time(9, 0), time(12, 0))
        congelado = self.ahora_congelada(time(18, 0))
        with mock.patch('django.utils.timezone.now', return_value=congelado):
            resp = self.reservar(fecha=hoy.isoformat(), hora='09:00:00')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('La hora del turno ya pasó', str(resp.data))

    def test_reserva_hoy_con_hora_futura_201(self):
        hoy = timezone.localdate()
        self.crear_disponibilidad(self.profesional, hoy, time(9, 0), time(12, 0))
        congelado = self.ahora_congelada(time(8, 0))
        with mock.patch('django.utils.timezone.now', return_value=congelado):
            resp = self.reservar(fecha=hoy.isoformat(), hora='09:00:00')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Turno.objects.filter(fecha=hoy, hora=time(9, 0)).exists())

    def test_reserva_que_cruza_medianoche_400(self):
        servicio_largo = Servicio.objects.create(
            nombre='Serv360', duracion=timedelta(minutes=360), precio='9000.00'
        )
        # 19:00 + 6 h = 01:00 del día siguiente (dentro del horario 09-20).
        resp = self.reservar(servicio=servicio_largo.id, hora='19:00:00')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cruzar la medianoche', str(resp.data))

    def test_reserva_encaje_exacto_en_fin_de_franja_201(self):
        # Franja 14:00-15:00 y servicio de 60 min: el fin cae exacto en
        # hora_fin de la disponibilidad (una sola franja, sin unión).
        self.crear_disponibilidad(self.profesional, self.fecha, time(14, 0), time(15, 0))
        resp = self.reservar(hora='14:00:00')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Turno.objects.filter(fecha=self.fecha, hora=time(14, 0)).exists()
        )


class DisponiblesFechaTests(BaseReservaCreacionTests):
    """El endpoint de horarios aplica la misma regla de fecha y reloj."""

    def test_disponibles_para_fecha_pasada_400(self):
        ayer = (timezone.localdate() - timedelta(days=1)).isoformat()
        resp = self.consultar_disponibles(fecha=ayer)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('anterior a hoy', str(resp.data))

    def test_disponibles_hoy_no_ofrece_horas_pasadas(self):
        hoy = timezone.localdate()
        self.crear_disponibilidad(self.profesional, hoy, time(9, 0), time(12, 0))
        congelado = self.ahora_congelada(time(10, 0))
        with mock.patch('django.utils.timezone.now', return_value=congelado):
            resp = self.consultar_disponibles(fecha=hoy.isoformat())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        horas = self.horas_de(resp)
        self.assertNotIn('09:00', horas)
        # Igual a "ahora": ya comenzó, tampoco se ofrece.
        self.assertNotIn('10:00', horas)
        self.assertIn('10:15', horas)


class BloqueoPorEstadoTests(BaseReservaCreacionTests):
    """Solo los turnos pendiente/confirmado bloquean; cancelado libera."""

    def _turno(self, estado, hora=time(9, 0)):
        return Turno.objects.create(
            fecha=self.fecha,
            hora=hora,
            usuario=self.cliente,
            profesional=self.profesional,
            servicio=self.servicio30,
            estado=estado,
        )

    def test_turno_pendiente_bloquea_horario(self):
        self._turno('pendiente')
        # 09:15-10:15 (servicio 60) solapa con 09:00-09:30; se usa una hora
        # distinta para no chocar con la restricción única del modelo.
        resp = self.reservar(hora='09:15:00')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('superpone', str(resp.data))
        # Tampoco se ofrece en la consulta de horarios.
        resp_disp = self.consultar_disponibles()
        self.assertEqual(resp_disp.status_code, status.HTTP_200_OK)
        self.assertNotIn('09:00', self.horas_de(resp_disp))

    def test_turno_confirmado_bloquea_horario(self):
        self._turno('confirmado')
        resp = self.reservar(hora='09:15:00')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('superpone', str(resp.data))
        resp_disp = self.consultar_disponibles()
        self.assertEqual(resp_disp.status_code, status.HTTP_200_OK)
        self.assertNotIn('09:00', self.horas_de(resp_disp))

    def test_turno_cancelado_libera_horario(self):
        self._turno('cancelado')
        # La consulta sigue ofreciendo el horario.
        resp_disp = self.consultar_disponibles()
        self.assertEqual(resp_disp.status_code, status.HTTP_200_OK)
        self.assertIn('09:00', self.horas_de(resp_disp))
        # Y la alta en ese horario es aceptada. Se reserva a las 09:30 para
        # no chocar con la restricción única (profesional, fecha, hora) del
        # turno cancelado existente a las 09:00.
        resp = self.reservar(hora='09:30:00')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
