"""A4 — turnos en intervalos de 15 minutos.

La grilla de horarios disponibles se genera con paso
``GRANULARIDAD_MINUTOS`` (15): cupos en minutos 00, 15, 30 y 45. Estos
tests verifican que el backend rechace cualquier hora de inicio fuera
de grilla (incluidos segundos/microsegundos) en los dos caminos de
escritura de turnos:

- API ``POST /api/turnos/`` → ``TurnoSerializer.validate``;
- formulario del admin Django → ``TurnoAdminForm.clean``.

Sin redondeos automáticos: el valor se rechaza tal cual llega, con un
mensaje claro. No se modifican datos histórices: todo corre sobre la
base de tests en memoria.
"""

from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework import status

from core.models import Disponibilidad, Profesional, Servicio, Turno
from core.tests import BaseAPITest

User = get_user_model()


class Intervalo15MinutosAPITests(BaseAPITest):
    """``POST /api/turnos/`` sólo acepta horas en la grilla de 15 minutos."""

    def setUp(self):
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')
        self.profesional = self.crear_profesional('Pro')
        self.servicio30 = self.crear_servicio('Serv30', duracion_minutos=30)
        self.fecha = timezone.localdate() + timedelta(days=1)
        self.crear_disponibilidad(
            self.profesional, self.fecha, time(9, 0), time(12, 0)
        )

    def reservar(self, **datos):
        payload = {
            'profesional': self.profesional.id,
            'servicio': self.servicio30.id,
            'fecha': self.fecha.isoformat(),
            'hora': '09:00:00',
        }
        payload.update(datos)
        self.client.force_authenticate(user=self.cliente)
        return self.client.post(reverse('turno-list'), payload, format='json')

    def test_minutos_fuera_de_grilla_rechazados(self):
        for hora in ('09:05:00', '09:07:00', '09:20:00', '09:50:00'):
            with self.subTest(hora=hora):
                resp = self.reservar(hora=hora)
                self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn('intervalos de 15 minutos', str(resp.data))
        # Ninguna de las reservas fuera de grilla quedó persistida.
        self.assertEqual(Turno.objects.count(), 0)

    def test_segundos_fuera_de_grilla_rechazados(self):
        # Minuto válido pero con segundos: no es un cupo de la grilla.
        resp = self.reservar(hora='09:15:30')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('intervalos de 15 minutos', str(resp.data))
        self.assertEqual(Turno.objects.count(), 0)

    def test_los_cuatro_minutos_de_la_grilla_son_aceptados(self):
        # Un día distinto por cupo (a partir de mañana: setUp ya cubre
        # la base): sin solapes ni conflictos de unicidad.
        for dias, hora in enumerate(
            ('09:00:00', '09:15:00', '09:30:00', '09:45:00'), start=1
        ):
            fecha = self.fecha + timedelta(days=dias)
            self.crear_disponibilidad(
                self.profesional, fecha, time(9, 0), time(12, 0)
            )
            resp = self.reservar(fecha=fecha.isoformat(), hora=hora)
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Turno.objects.count(), 4)

    def test_error_de_intervalo_tiene_prioridad_sobre_disponibilidad(self):
        # 19:47 está dentro del horario de atención pero fuera de la
        # franja 09:00-12:00: sin la validación de grilla el error sería
        # «no está dentro de la disponibilidad»; el de intervalo debe
        # llegar primero y con su mensaje.
        resp = self.reservar(hora='19:47:00')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('intervalos de 15 minutos', str(resp.data))
        self.assertNotIn('disponibilidad', str(resp.data))
        self.assertEqual(Turno.objects.count(), 0)


class Intervalo15MinutosAdminTests(TestCase):
    """Formulario del admin Django: misma regla de grilla que la API."""

    def setUp(self):
        self.root = User.objects.create_superuser(
            'root', 'root@test.com', 'RootPass123!'
        )
        self.client.force_login(self.root)
        self.cliente = User.objects.create_user(
            'cliente', 'cliente@test.com', 'ClientePass123!'
        )
        self.profesional = Profesional.objects.create(nombre='Pro A')
        self.servicio = Servicio.objects.create(
            nombre='Semi', duracion=timedelta(minutes=30), precio='5000.00'
        )
        self.fecha = timezone.localdate() + timedelta(days=1)
        Disponibilidad.objects.create(
            profesional=self.profesional, fecha=self.fecha,
            hora_inicio=time(9, 0), hora_fin=time(12, 0),
        )

    def datos(self, **campos):
        datos = {
            'fecha': self.fecha.isoformat(),
            'hora': '09:00:00',
            'usuario': self.cliente.pk,
            'servicio': self.servicio.pk,
            'profesional': self.profesional.pk,
        }
        datos.update(campos)
        return datos

    def test_alta_con_minutos_fuera_de_grilla_rechazada(self):
        resp = self.client.post(
            reverse('admin:core_turno_add'), self.datos(hora='09:07:00'),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'intervalos de 15 minutos')
        self.assertEqual(Turno.objects.count(), 0)

    def test_alta_con_segundos_fuera_de_grilla_rechazada(self):
        resp = self.client.post(
            reverse('admin:core_turno_add'), self.datos(hora='09:15:30'),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'intervalos de 15 minutos')
        self.assertEqual(Turno.objects.count(), 0)

    def test_alta_en_la_grilla_aceptada(self):
        resp = self.client.post(
            reverse('admin:core_turno_add'), self.datos(hora='09:15:00'),
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Turno.objects.filter(hora=time(9, 15)).count(), 1)

    def test_edicion_hacia_minutos_fuera_de_grilla_rechazada(self):
        turno = Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            servicio=self.servicio, profesional=self.profesional,
        )
        resp = self.client.post(
            reverse('admin:core_turno_change', args=[turno.pk]),
            self.datos(hora='09:47:00'),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'intervalos de 15 minutos')
        turno.refresh_from_db()
        # El registro queda intacto: no se redondea ni se modifica.
        self.assertEqual(turno.hora, time(9, 0))
