"""Etapa B3 — conflictos de integridad y concurrencia.

Tests nuevos (no reemplazan ni modifican los existentes):

- duplicados secuenciales de restricción única (turno y disponibilidad):
  respuesta controlada 400 con mensaje, nunca 500, sin registros extra;
- la restricción única de Turno es CONDICIONAL (B3.1): re-reservar encima
  de un turno cancelado en la misma hora devuelve 201, conservando el
  cancelado y dejando dos registros;
- con la carrera real simulada (``IntegrityError`` lanzado desde el guardado
  para reproducir lo que haría la base en PostgreSQL), la vista responde 400
  porque la captura ocurre fuera del ``transaction.atomic``;
- un ``IntegrityError`` que NO proviene de una restricción única no se
  oculta: se propaga (500) en lugar de traducirse a 400.

Nota: la carrera verdadera (dos requests simultáneos) no es demostrable en
SQLite secuencial; ver el informe de B3 para la estrategia con PostgreSQL.
"""

from datetime import time, timedelta
from unittest import mock

from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

from rest_framework import status

from core.models import Disponibilidad, Turno
from core.tests import BaseAPITest
from users.models import User


class BaseConflictoTests(BaseAPITest):
    def setUp(self):
        self.admin = self.crear_usuario('admin', 'admin@test.com', role=User.Roles.ADMIN, staff=True)
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')
        self.pro_user = self.crear_usuario('pro', 'pro@test.com', role=User.Roles.PERSONAL)
        self.profesional = self.crear_profesional('Pro', usuario=self.pro_user)
        self.servicio60 = self.crear_servicio('Serv60', duracion_minutos=60)
        # Fecha futura: neutra respecto de la regla "hora ya pasada".
        self.fecha = timezone.localdate() + timedelta(days=1)

    def url_turnos(self):
        return reverse('turno-list')

    def url_disponibilidades(self):
        return reverse('disponibilidad-list')

    def reservar(self, hora='09:00:00'):
        self.client.force_authenticate(user=self.cliente)
        return self.client.post(
            self.url_turnos(),
            {
                'profesional': self.profesional.id,
                'servicio': self.servicio60.id,
                'fecha': self.fecha.isoformat(),
                'hora': hora,
            },
            format='json',
        )

    def crear_franja_por_api(self, ini='09:00:00', fin='12:00:00'):
        self.client.force_authenticate(user=self.pro_user)
        return self.client.post(
            self.url_disponibilidades(),
            {
                'profesional': self.profesional.id,
                'fecha': self.fecha.isoformat(),
                'hora_inicio': ini,
                'hora_fin': fin,
            },
            format='json',
        )

    @staticmethod
    def mensaje_unico():
        # Texto del UniqueTogetherValidator de DRF en español.
        return 'conjunto único'


class DuplicadosSecuencialesTests(BaseConflictoTests):
    """Los duplicados exactos ya devuelven 400 desde la validación."""

    def test_reserva_duplicada_devuelve_400_no_500(self):
        self.crear_disponibilidad(self.profesional, self.fecha, time(9, 0), time(12, 0))
        r1 = self.reservar()
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)

        r2 = self.reservar()  # mismo profesional, fecha y hora
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(self.mensaje_unico(), str(r2.data))
        # No se creó un registro duplicado.
        self.assertEqual(Turno.objects.count(), 1)

    def test_reserva_sobre_turno_cancelado_devuelve_201_y_conserva_historial(self):
        # B3.1: la restricción única es condicional (solo activos), así que
        # el turno cancelado libera su horario para una nueva reserva.
        self.crear_disponibilidad(self.profesional, self.fecha, time(9, 0), time(12, 0))
        cancelado = Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio60,
            estado='cancelado',
        )
        resp = self.reservar()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # Dos registros en el mismo horario: cancelado + nuevo activo.
        self.assertEqual(Turno.objects.count(), 2)
        self.assertEqual(Turno.objects.filter(estado='pendiente').count(), 1)
        # El turno cancelado original permanece intacto.
        cancelado.refresh_from_db()
        self.assertEqual(cancelado.estado, 'cancelado')
        self.assertEqual(cancelado.fecha, self.fecha)
        self.assertEqual(cancelado.hora, time(9, 0))

    def test_disponibilidad_duplicada_devuelve_400_no_500(self):
        r1 = self.crear_franja_por_api()
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)

        r2 = self.crear_franja_por_api()  # idéntica
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(self.mensaje_unico(), str(r2.data))
        self.assertEqual(Disponibilidad.objects.count(), 1)


class ManejoDeIntegrityErrorTests(BaseConflictoTests):
    """Simula el disparo real de la restricción única en la base.

    Se parchea ``save`` para lanzar ``IntegrityError`` justo donde lo haría
    la base en una carrera (los checks previos ya pasaron), de modo que se
    ejercita el ``except`` de las vistas: la captura ocurre fuera del
    ``transaction.atomic`` y la respuesta es 400, no 500.
    """

    def test_integrity_error_al_crear_turno_devuelve_400(self):
        self.crear_disponibilidad(self.profesional, self.fecha, time(9, 0), time(12, 0))
        with mock.patch.object(
            Turno, 'save',
            side_effect=IntegrityError(
                'UNIQUE constraint failed: core_turno.profesional_id, '
                'core_turno.fecha, core_turno.hora'
            ),
        ):
            resp = self.reservar()
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('ya existe una reserva', str(resp.data))
        # La transacción no dejó ningún registro.
        self.assertEqual(Turno.objects.count(), 0)

    def test_integrity_error_al_crear_disponibilidad_devuelve_400(self):
        with mock.patch.object(
            Disponibilidad, 'save',
            side_effect=IntegrityError(
                'UNIQUE constraint failed: core_disponibilidad.profesional_id, '
                'core_disponibilidad.fecha, core_disponibilidad.hora_inicio'
            ),
        ):
            resp = self.crear_franja_por_api()
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Ya existe una disponibilidad', str(resp.data))
        self.assertEqual(Disponibilidad.objects.count(), 0)

    def test_integrity_error_al_editar_disponibilidad_devuelve_400(self):
        disp = self.crear_disponibilidad(self.profesional, self.fecha, time(9, 0), time(12, 0))
        with mock.patch.object(
            Disponibilidad, 'save',
            side_effect=IntegrityError(
                'UNIQUE constraint failed: core_disponibilidad.profesional_id, '
                'core_disponibilidad.fecha, core_disponibilidad.hora_inicio'
            ),
        ):
            self.client.force_authenticate(user=self.pro_user)
            resp = self.client.patch(
                reverse('disponibilidad-detail', args=[disp.pk]),
                {'hora_fin': '13:00:00'},
                format='json',
            )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('ya existe otra', str(resp.data))
        # La franja no cambió.
        disp.refresh_from_db()
        self.assertEqual(disp.hora_fin, time(12, 0))

    def test_integrity_error_no_unico_no_se_oculta(self):
        # Un IntegrityError que NO es de restricción única (p. ej. FK rota
        # por un bug) no se traduce a 400: se propaga para que no quede
        # enmascarado como un conflicto esperado.
        self.crear_disponibilidad(self.profesional, self.fecha, time(9, 0), time(12, 0))
        with mock.patch.object(
            Turno, 'save',
            side_effect=IntegrityError('FOREIGN KEY constraint failed'),
        ):
            with self.assertRaises(IntegrityError):
                self.reservar()
