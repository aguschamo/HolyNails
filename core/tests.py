from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import time, datetime, timedelta

from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Servicio, Turno, Profesional, Disponibilidad
from users.models import User


class BaseAPITest(APITestCase):
    """Utilidades compartidas para los tests de disponibilidad y turnos."""

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

    def crear_profesional(self, nombre='Profesional', usuario=None, activo=True):
        return Profesional.objects.create(
            nombre=nombre, usuario=usuario, is_active=activo
        )

    def crear_servicio(self, nombre='Servicio', duracion_minutos=30, precio='5000.00'):
        return Servicio.objects.create(
            nombre=nombre,
            duracion=timedelta(minutes=duracion_minutos),
            precio=precio,
        )

    def crear_disponibilidad(self, profesional, fecha, hora_inicio, hora_fin):
        return Disponibilidad.objects.create(
            profesional=profesional,
            fecha=fecha,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
        )


class ProfesionalYDisponibilidadTests(BaseAPITest):
    def setUp(self):
        self.admin = self.crear_usuario('admin', 'admin@test.com', role=User.Roles.ADMIN, staff=True)
        self.pro_user = self.crear_usuario('pro', 'pro@test.com', role=User.Roles.PERSONAL)
        self.profesional = self.crear_profesional('Manicura A', usuario=self.pro_user)
        self.otro_profesional = self.crear_profesional('Manicura B')
        self.servicio = self.crear_servicio('Semi', duracion_minutos=30)
        self.fecha = timezone.localdate()

    def test_admin_crea_profesional(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('profesional-list')
        data = {'nombre': 'Nuevo Pro', 'is_active': True}
        resp = self.client.post(url, data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Profesional.objects.filter(nombre='Nuevo Pro').count(), 1)

    def test_profesional_vinculado_edita_su_disponibilidad(self):
        """El usuario vinculado al profesional puede editar su disponibilidad."""
        disp = self.crear_disponibilidad(
            self.profesional, self.fecha, time(9, 0), time(14, 0)
        )
        self.client.force_authenticate(user=self.pro_user)
        url = reverse('disponibilidad-detail', args=[disp.id])
        resp = self.client.patch(
            url, {'hora_fin': time(13, 0).strftime('%H:%M')}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        disp.refresh_from_db()
        self.assertEqual(disp.hora_fin, time(13, 0))

    def test_personal_no_puede_editar_disponibilidad_de_otro_profesional(self):
        disp = self.crear_disponibilidad(
            self.otro_profesional, self.fecha, time(9, 0), time(14, 0)
        )
        self.client.force_authenticate(user=self.pro_user)
        url = reverse('disponibilidad-detail', args=[disp.id])
        resp = self.client.patch(
            url, {'hora_fin': time(13, 0).strftime('%H:%M')}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_se_pueden_solapar_disponibilidades_mismo_profesional_fecha(self):
        self.crear_disponibilidad(self.profesional, self.fecha, time(9, 0), time(12, 0))
        self.client.force_authenticate(user=self.admin)
        url = reverse('disponibilidad-list')
        resp = self.client.post(
            url,
            {
                'profesional': self.profesional.id,
                'fecha': self.fecha.isoformat(),
                'hora_inicio': '11:00:00',
                'hora_fin': '14:00:00',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_listar_disponibilidades_filtradas_por_profesional_y_fecha(self):
        d1 = self.crear_disponibilidad(self.profesional, self.fecha, time(9, 0), time(12, 0))
        otro_fecha = self.fecha + timedelta(days=1)
        d2 = self.crear_disponibilidad(self.profesional, otro_fecha, time(9, 0), time(12, 0))
        self.client.force_authenticate(user=self.admin)
        url = reverse('disponibilidad-list')
        resp = self.client.get(
            url, {'profesional': self.profesional.id, 'fecha': self.fecha.isoformat()}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in resp.data['results']]
        self.assertIn(d1.id, ids)
        self.assertNotIn(d2.id, ids)


class HorariosDisponiblesTests(BaseAPITest):
    def setUp(self):
        self.admin = self.crear_usuario('admin', 'admin@test.com', role=User.Roles.ADMIN, staff=True)
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')
        self.profesional = self.crear_profesional('Pro')
        self.servicio30 = self.crear_servicio('Serv30', duracion_minutos=30)
        self.servicio60 = self.crear_servicio('Serv60', duracion_minutos=60)
        # Fecha futura: con la regla "hoy con hora ya pasada" los tests de
        # disponibilidad a las 09:00 solo son determinísticos en otro día.
        self.fecha = timezone.localdate() + timedelta(days=1)

    def test_horarios_disponibles_requiere_servicio_y_fecha(self):
        self.client.force_authenticate(user=self.cliente)
        url = reverse('turno-disponibles')
        resp = self.client.get(url, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_horarios_disponibles_respeta_duracion_servicio(self):
        # Disponibilidad 09:00-11:00, servicio 60 min, paso 15 min.
        self.crear_disponibilidad(self.profesional, self.fecha, time(9, 0), time(11, 0))
        self.client.force_authenticate(user=self.cliente)
        url = reverse('turno-disponibles')
        resp = self.client.get(
            url, {'servicio': self.servicio60.id, 'fecha': self.fecha.isoformat()}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        horas = [item['hora'] for item in resp.data]
        # 09:00 (fin 10:00) y 09:30 (fin 10:30) caben; 10:00 (fin 11:00) cabe justo.
        self.assertIn('09:00', horas)
        self.assertIn('09:30', horas)
        self.assertIn('10:00', horas)
        # 10:30 no cabe (fin 11:30 > 11:00).
        self.assertNotIn('10:30', horas)

    def test_horarios_disponibles_excluye_turnos_ocupados(self):
        self.crear_disponibilidad(self.profesional, self.fecha, time(9, 0), time(10, 0))
        # Turno existente 09:00-09:30 con servicio de 30 min.
        Turno.objects.create(
            fecha=self.fecha,
            hora=time(9, 0),
            usuario=self.cliente,
            profesional=self.profesional,
            servicio=self.servicio30,
            estado='pendiente',
        )
        self.client.force_authenticate(user=self.cliente)
        url = reverse('turno-disponibles')
        resp = self.client.get(
            url, {'servicio': self.servicio30.id, 'fecha': self.fecha.isoformat()}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        horas = [item['hora'] for item in resp.data]
        # 09:00 está ocupado; 09:30+30=10:00 cabe justo.
        self.assertNotIn('09:00', horas)
        self.assertIn('09:30', horas)

    def test_filtrar_por_profesional(self):
        otro = self.crear_profesional('Otro')
        self.crear_disponibilidad(self.profesional, self.fecha, time(9, 0), time(10, 0))
        self.crear_disponibilidad(otro, self.fecha, time(9, 0), time(10, 0))
        self.client.force_authenticate(user=self.cliente)
        url = reverse('turno-disponibles')
        resp = self.client.get(
            url,
            {
                'servicio': self.servicio30.id,
                'fecha': self.fecha.isoformat(),
                'profesional': self.profesional.id,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for item in resp.data:
            self.assertEqual(item['profesional'], self.profesional.id)


class CreacionReservasTests(BaseAPITest):
    def setUp(self):
        self.admin = self.crear_usuario('admin', 'admin@test.com', role=User.Roles.ADMIN, staff=True)
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')
        self.profesional = self.crear_profesional('Pro')
        self.servicio30 = self.crear_servicio('Serv30', duracion_minutos=30)
        self.servicio60 = self.crear_servicio('Serv60', duracion_minutos=60)
        # Fecha futura para que las reservas a las 09:00 no caigan bajo la
        # regla "hoy con la hora ya pasada" (sin tocar aserciones).
        self.fecha = timezone.localdate() + timedelta(days=1)
        self.crear_disponibilidad(self.profesional, self.fecha, time(9, 0), time(10, 0))

    def url_turnos(self):
        return reverse('turno-list')

    def test_reserva_dentro_de_disponibilidad_201(self):
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.post(
            self.url_turnos(),
            {
                'profesional': self.profesional.id,
                'servicio': self.servicio30.id,
                'fecha': self.fecha.isoformat(),
                'hora': '09:00:00',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        turno = Turno.objects.get(id=resp.data['id'])
        self.assertEqual(turno.estado, 'pendiente')
        self.assertEqual(turno.usuario, self.cliente)
        self.assertEqual(turno.profesional, self.profesional)

    def test_reserva_fuera_de_disponibilidad_400(self):
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.post(
            self.url_turnos(),
            {
                'profesional': self.profesional.id,
                'servicio': self.servicio30.id,
                'fecha': self.fecha.isoformat(),
                'hora': '10:30:00',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reserva_que_cabe_justo_en_hora_fin_201(self):
        # Servicio 60 min a las 09:00 termina a las 10:00: cabe justo en la
        # disponibilidad 09:00-10:00.
        self.client.force_authenticate(user=self.cliente)
        resp_ok = self.client.post(
            self.url_turnos(),
            {
                'profesional': self.profesional.id,
                'servicio': self.servicio60.id,
                'fecha': self.fecha.isoformat(),
                'hora': '09:00:00',
            },
            format='json',
        )
        self.assertEqual(resp_ok.status_code, status.HTTP_201_CREATED)

    def test_reserva_superpuesta_con_turno_existente_400(self):
        Turno.objects.create(
            fecha=self.fecha,
            hora=time(9, 0),
            usuario=self.cliente,
            profesional=self.profesional,
            servicio=self.servicio30,
            estado='pendiente',
        )
        self.client.force_authenticate(user=self.cliente)
        # Intento turno 09:15 con servicio 30 min (fin 09:45) -> solapa con 09:00-09:30.
        resp = self.client.post(
            self.url_turnos(),
            {
                'profesional': self.profesional.id,
                'servicio': self.servicio30.id,
                'fecha': self.fecha.isoformat(),
                'hora': '09:15:00',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_dos_profesionales_pueden_atender_simultaneamente(self):
        otro_profesional = self.crear_profesional('Pro B')
        self.crear_disponibilidad(otro_profesional, self.fecha, time(9, 0), time(10, 0))
        self.client.force_authenticate(user=self.cliente)
        # Mismo día y hora, profesionales distintos: ambos deben poder reservarse.
        r1 = self.client.post(
            self.url_turnos(),
            {
                'profesional': self.profesional.id,
                'servicio': self.servicio30.id,
                'fecha': self.fecha.isoformat(),
                'hora': '09:00:00',
            },
            format='json',
        )
        r2 = self.client.post(
            self.url_turnos(),
            {
                'profesional': otro_profesional.id,
                'servicio': self.servicio30.id,
                'fecha': self.fecha.isoformat(),
                'hora': '09:00:00',
            },
            format='json',
        )
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Turno.objects.filter(fecha=self.fecha, hora=time(9, 0)).count(), 2)

    def test_cliente_solo_ve_sus_propios_turnos(self):
        otro_cliente = self.crear_usuario('otro', 'otro@test.com')
        Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30, estado='pendiente',
        )
        Turno.objects.create(
            fecha=self.fecha, hora=time(10, 0), usuario=otro_cliente,
            profesional=self.profesional, servicio=self.servicio30, estado='pendiente',
        )
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get(self.url_turnos(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in resp.data['results']]
        self.assertEqual(len(ids), 1)


class ReservaConcurrenciaTests(BaseAPITest):
    """Pruebas de solapamiento de intervalos y serialización de reservas.

    Nota: estos tests se ejecutan sobre SQLite, por lo que las peticiones son
    secuenciales. La lógica de bloqueo (select_for_update sobre el profesional
    dentro de transaction.atomic) se valida aquí comprobando que la segunda
    reserva sobre un horario ya ocupado es rechazada. En PostgreSQL el mismo
    código proporciona bloqueo de fila real ante solicitudes concurrentes.
    """

    def setUp(self):
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')
        self.profesional = self.crear_profesional('Pro')
        self.servicio30 = self.crear_servicio('Serv30', duracion_minutos=30)
        # Fecha futura: mantiene determinística la primera reserva a las 09:00
        # bajo la regla "hoy con la hora ya pasada".
        self.fecha = timezone.localdate() + timedelta(days=1)
        self.crear_disponibilidad(self.profesional, self.fecha, time(9, 0), time(10, 0))

    def url_turnos(self):
        return reverse('turno-list')

    def _reservar(self, hora_str):
        self.client.force_authenticate(user=self.cliente)
        return self.client.post(
            self.url_turnos(),
            {
                'profesional': self.profesional.id,
                'servicio': self.servicio30.id,
                'fecha': self.fecha.isoformat(),
                'hora': hora_str,
            },
            format='json',
        )

    def test_dos_turnos_intervalos_parcialmente_superpuestos_400(self):
        # Turno existente 09:00-09:30 (servicio 30 min).
        self.client.force_authenticate(user=self.cliente)
        self._reservar('09:00:00')
        # Intento 09:15 con servicio 30 min (fin 09:45): se solapa parcialmente.
        resp = self._reservar('09:15:00')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_segunda_reserva_mismo_horario_es_rechazada_400(self):
        # Primera reserva ocupa 09:00-09:30.
        r1 = self._reservar('09:00:00')
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        # Segunda reserva en el mismo horario debe ser rechazada.
        r2 = self._reservar('09:00:00')
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validacion_disponibilidad_despues_de_bloqueo(self):
        # Reserva fuera de la disponibilidad (10:30 no está en 09:00-10:00).
        resp = self._reservar('10:30:00')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class EstadosTurnoTests(BaseAPITest):
    """Pruebas de que solo turnos pendiente/confirmado bloquean horarios."""

    def setUp(self):
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')
        self.profesional = self.crear_profesional('Pro')
        self.servicio30 = self.crear_servicio('Serv30', duracion_minutos=30)
        # Fecha futura: el assertIn('09:00') de disponibles solo es válido
        # cuando hoy aún no pasaron las 09:00.
        self.fecha = timezone.localdate() + timedelta(days=1)
        self.crear_disponibilidad(self.profesional, self.fecha, time(9, 0), time(10, 0))

    def url_disponibles(self):
        return reverse('turno-disponibles')

    def test_turno_cancelado_libera_horario(self):
        # Turno cancelado a las 09:00 no debe bloquear ese horario.
        Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='cancelado',
        )
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get(
            self.url_disponibles(),
            {'servicio': self.servicio30.id, 'fecha': self.fecha.isoformat()},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        horas = [item['hora'] for item in resp.data]
        self.assertIn('09:00', horas)

    def test_turno_pendiente_bloquea_horario(self):
        Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='pendiente',
        )
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get(
            self.url_disponibles(),
            {'servicio': self.servicio30.id, 'fecha': self.fecha.isoformat()},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        horas = [item['hora'] for item in resp.data]
        self.assertNotIn('09:00', horas)

    def test_turno_confirmado_bloquea_horario(self):
        Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='confirmado',
        )
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get(
            self.url_disponibles(),
            {'servicio': self.servicio30.id, 'fecha': self.fecha.isoformat()},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        horas = [item['hora'] for item in resp.data]
        self.assertNotIn('09:00', horas)


class PermisosProfesionalTests(BaseAPITest):
    """Pruebas de permisos sobre gestión de profesionales."""

    def setUp(self):
        self.admin = self.crear_usuario('admin', 'admin@test.com', role=User.Roles.ADMIN, staff=True)
        self.personal = self.crear_usuario('personal', 'personal@test.com', role=User.Roles.PERSONAL)
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')
        self.profesional = self.crear_profesional('Pro')

    def test_personal_no_puede_crear_profesional(self):
        self.client.force_authenticate(user=self.personal)
        url = reverse('profesional-list')
        resp = self.client.post(
            url, {'nombre': 'Nuevo', 'is_active': True}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_personal_no_puede_modificar_profesional(self):
        self.client.force_authenticate(user=self.personal)
        url = reverse('profesional-detail', args=[self.profesional.id])
        resp = self.client.patch(
            url, {'nombre': 'Modificado'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_personal_no_puede_eliminar_profesional(self):
        self.client.force_authenticate(user=self.personal)
        url = reverse('profesional-detail', args=[self.profesional.id])
        resp = self.client.delete(url, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_puede_crear_profesional(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('profesional-list')
        resp = self.client.post(
            url, {'nombre': 'Nuevo Pro Admin', 'is_active': True}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_cliente_no_puede_crear_profesional(self):
        self.client.force_authenticate(user=self.cliente)
        url = reverse('profesional-list')
        resp = self.client.post(
            url, {'nombre': 'Nuevo', 'is_active': True}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class DisponibilidadProteccionTests(BaseAPITest):
    """Pruebas de protección de disponibilidades con turnos existentes."""

    def setUp(self):
        self.admin = self.crear_usuario('admin', 'admin@test.com', role=User.Roles.ADMIN, staff=True)
        self.pro_user = self.crear_usuario('pro', 'pro@test.com', role=User.Roles.PERSONAL)
        self.profesional = self.crear_profesional('Pro', usuario=self.pro_user)
        self.servicio30 = self.crear_servicio('Serv30', duracion_minutos=30)
        # Fecha futura: con la regla "los turnos pasados no bloquean el
        # mantenimiento", los turnos de hoy 09:00 dejarían de ejercer el
        # bloqueo a cualquier hora de ejecución posterior a las 09:00.
        self.fecha = timezone.localdate() + timedelta(days=1)
        self.disponibilidad = self.crear_disponibilidad(
            self.profesional, self.fecha, time(9, 0), time(10, 0)
        )

    def url_disponibilidad(self, pk=None):
        return reverse('disponibilidad-detail', args=[pk or self.disponibilidad.id])

    def test_no_eliminar_disponibilidad_con_turno_pendiente(self):
        Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.pro_user,
            profesional=self.profesional, servicio=self.servicio30,
            estado='pendiente',
        )
        self.client.force_authenticate(user=self.pro_user)
        resp = self.client.delete(self.url_disponibilidad(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Disponibilidad.objects.filter(pk=self.disponibilidad.id).exists())

    def test_no_eliminar_disponibilidad_con_turno_confirmado(self):
        Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.pro_user,
            profesional=self.profesional, servicio=self.servicio30,
            estado='confirmado',
        )
        self.client.force_authenticate(user=self.pro_user)
        resp = self.client.delete(self.url_disponibilidad(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Disponibilidad.objects.filter(pk=self.disponibilidad.id).exists())

    def test_puede_eliminar_disponibilidad_solo_con_turno_cancelado(self):
        Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.pro_user,
            profesional=self.profesional, servicio=self.servicio30,
            estado='cancelado',
        )
        self.client.force_authenticate(user=self.pro_user)
        resp = self.client.delete(self.url_disponibilidad(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Disponibilidad.objects.filter(pk=self.disponibilidad.id).exists())

    def test_no_reducir_franja_dejando_turno_activo_fuera(self):
        # Turno activo 09:00-09:30 dentro de la disponibilidad 09:00-10:00.
        Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.pro_user,
            profesional=self.profesional, servicio=self.servicio30,
            estado='pendiente',
        )
        self.client.force_authenticate(user=self.pro_user)
        # Intento reducir la franja a 09:00-09:15: el turno queda fuera.
        resp = self.client.patch(
            self.url_disponibilidad(),
            {'hora_fin': time(9, 15).strftime('%H:%M')},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_puede_reducir_franja_si_no_hay_turnos_afectados(self):
        self.client.force_authenticate(user=self.pro_user)
        resp = self.client.patch(
            self.url_disponibilidad(),
            {'hora_fin': time(9, 30).strftime('%H:%M')},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.disponibilidad.refresh_from_db()
        self.assertEqual(self.disponibilidad.hora_fin, time(9, 30))


class DisponibilidadConcurrenciaTests(BaseAPITest):
    """Pruebas de solapamiento y serialización de disponibilidades.

    Nota: estos tests se ejecutan sobre SQLite, por lo que las peticiones son
    secuenciales. La lógica de bloqueo (select_for_update sobre el profesional
    dentro de transaction.atomic) se valida aquí comprobando que una segunda
    disponibilidad solapada es rechazada después de que la primera ya se guardó.
    En PostgreSQL el mismo código proporciona bloqueo de fila real ante
    solicitudes concurrentes; en SQLite no es posible demostrar ese bloqueo
    real con tests unitarios secuenciales.
    """

    def setUp(self):
        self.pro_user = self.crear_usuario('pro', 'pro@test.com', role=User.Roles.PERSONAL)
        self.profesional = self.crear_profesional('Pro', usuario=self.pro_user)
        self.fecha = timezone.localdate()

    def url_disponibilidades(self):
        return reverse('disponibilidad-list')

    def url_disponibilidad(self, pk=None):
        return reverse('disponibilidad-detail', args=[pk])

    def _crear(self, hora_inicio, hora_fin):
        self.client.force_authenticate(user=self.pro_user)
        return self.client.post(
            self.url_disponibilidades(),
            {
                'profesional': self.profesional.id,
                'fecha': self.fecha.isoformat(),
                'hora_inicio': hora_inicio,
                'hora_fin': hora_fin,
            },
            format='json',
        )

    def _editar(self, pk, **campos):
        self.client.force_authenticate(user=self.pro_user)
        return self.client.patch(
            self.url_disponibilidad(pk), campos, format='json'
        )

    def test_crear_disponibilidad_solapada_es_rechazada(self):
        # Primera disponibilidad 09:00-11:00.
        r1 = self._crear('09:00:00', '11:00:00')
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        # Segunda disponibilidad 10:00-12:00: se solapa parcialmente.
        r2 = self._crear('10:00:00', '12:00:00')
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_crear_dos_disponibilidades_superpuestas_secucionalmente_400(self):
        # Simula el escenario de dos solicitudes para el mismo profesional y
        # fecha: la segunda debe ver la primera ya guardada y ser rechazada.
        r1 = self._crear('09:00:00', '10:00:00')
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        r2 = self._crear('09:30:00', '10:30:00')
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_editar_disponibilidad_generando_solapamiento_es_rechazada(self):
        r1 = self._crear('09:00:00', '10:00:00')
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        r2 = self._crear('11:00:00', '12:00:00')
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        # Intento editar la segunda para que sea 09:30-11:30: solapa con la primera.
        resp = self._editar(r2.data['id'], hora_inicio='09:30:00', hora_fin='11:30:00')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_editar_disponibilidad_sin_solapamiento_funciona(self):
        r1 = self._crear('09:00:00', '10:00:00')
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        # Editar la misma disponibilidad a un horario que no solapa con otras.
        resp = self._editar(r1.data['id'], hora_inicio='14:00:00', hora_fin='15:00:00')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.disponibilidad = self.profesional.disponibilidades.get(pk=r1.data['id'])
        self.assertEqual(self.disponibilidad.hora_inicio, time(14, 0))

    def test_no_se_puede_cambiar_el_profesional_al_editar(self):
        r1 = self._crear('09:00:00', '10:00:00')
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        otro_profesional = self.crear_profesional('Otro')
        resp = self._editar(r1.data['id'], profesional=otro_profesional.id)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_crear_disponibilidad_respeta_limite_09_20(self):
        self.client.force_authenticate(user=self.pro_user)
        # Antes de las 09:00.
        resp = self.client.post(
            self.url_disponibilidades(),
            {
                'profesional': self.profesional.id,
                'fecha': self.fecha.isoformat(),
                'hora_inicio': '08:00:00',
                'hora_fin': '09:00:00',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # Después de las 20:00.
        resp = self.client.post(
            self.url_disponibilidades(),
            {
                'profesional': self.profesional.id,
                'fecha': self.fecha.isoformat(),
                'hora_inicio': '20:00:00',
                'hora_fin': '21:00:00',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class ProfesionalTurnosConsultaTests(BaseAPITest):
    """Pruebas de consulta de turnos como profesional (GET /api/turnos/?como_profesional=true)."""

    def setUp(self):
        self.admin = self.crear_usuario('admin', 'admin@test.com', role=User.Roles.ADMIN, staff=True)
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')
        self.pro_user = self.crear_usuario('pro', 'pro@test.com', role=User.Roles.PERSONAL)
        self.otro_pro = self.crear_usuario('otropro', 'otropro@test.com', role=User.Roles.PERSONAL)
        self.profesional = self.crear_profesional('Pro A', usuario=self.pro_user, activo=True)
        self.otro_profesional = self.crear_profesional('Pro B', usuario=self.otro_pro, activo=True)
        # Cuenta PERSONAL con profesional inactivo vinculado (para probar
        # el rechazo de la vista como profesional). La clienta no tiene
        # vínculo (D3: CLIENTE sin Profesional).
        self.personal_inactivo = self.crear_usuario(
            'personalbaja', 'personalbaja@test.com', role=User.Roles.PERSONAL,
        )
        self.inactivo_profesional = self.crear_profesional(
            'Pro Inactivo', usuario=self.personal_inactivo, activo=False
        )
        self.servicio30 = self.crear_servicio('Serv30', duracion_minutos=30)
        self.fecha = timezone.localdate()

        # Turnos del profesional A (usuario vinculado: pro_user)
        self.turno_pro1 = Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30, estado='pendiente',
        )
        self.turno_pro2 = Turno.objects.create(
            fecha=self.fecha, hora=time(10, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30, estado='confirmado',
        )
        # Turno del profesional B (usuario vinculado: otro_pro)
        self.turno_otro_pro = Turno.objects.create(
            fecha=self.fecha, hora=time(11, 0), usuario=self.cliente,
            profesional=self.otro_profesional, servicio=self.servicio30, estado='pendiente',
        )
        # Turno sin profesional asignado
        self.turno_sin_profesional = Turno.objects.create(
            fecha=self.fecha, hora=time(12, 0), usuario=self.cliente,
            profesional=None, servicio=self.servicio30, estado='pendiente',
        )

    def url_turnos(self):
        return reverse('turno-list')

    def test_profesional_ve_sus_propias_reservas(self):
        self.client.force_authenticate(user=self.pro_user)
        resp = self.client.get(
            self.url_turnos(), {'como_profesional': 'true'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in resp.data['results']]
        self.assertIn(self.turno_pro1.id, ids)
        self.assertIn(self.turno_pro2.id, ids)
        self.assertNotIn(self.turno_otro_pro.id, ids)
        self.assertNotIn(self.turno_sin_profesional.id, ids)

    def test_profesional_no_ve_turnos_de_otra_profesional(self):
        self.client.force_authenticate(user=self.pro_user)
        resp = self.client.get(
            self.url_turnos(), {'como_profesional': 'true'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in resp.data['results']]
        self.assertNotIn(self.turno_otro_pro.id, ids)

    def test_cliente_con_como_profesional_no_ve_turnos_ajenos(self):
        # La clienta no tiene vínculo Profesional (D3), así que la vista
        # como profesional no le devuelve nada.
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get(
            self.url_turnos(), {'como_profesional': 'true'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in resp.data['results']]
        self.assertEqual(ids, [])
        # Pero sigue viendo sus propios turnos como clienta (sin el parámetro).
        resp_sin_param = self.client.get(self.url_turnos(), format='json')
        ids_propias = [item['id'] for item in resp_sin_param.data['results']]
        self.assertIn(self.turno_pro1.id, ids_propias)

    def test_profesional_inactivo_no_ve_turnos(self):
        # Cuenta PERSONAL cuyo Profesional está inactivo: no ve su agenda.
        self.client.force_authenticate(user=self.personal_inactivo)
        resp = self.client.get(
            self.url_turnos(), {'como_profesional': 'true'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in resp.data['results']]
        self.assertEqual(ids, [])

    def test_admin_ve_todos_los_turnos(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url_turnos(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in resp.data['results']]
        self.assertIn(self.turno_pro1.id, ids)
        self.assertIn(self.turno_pro2.id, ids)
        self.assertIn(self.turno_otro_pro.id, ids)
        self.assertIn(self.turno_sin_profesional.id, ids)

    def test_clienta_sin_profesional_ve_sus_propios_turnos_normalmente(self):
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get(self.url_turnos(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in resp.data['results']]
        self.assertIn(self.turno_pro1.id, ids)
        self.assertIn(self.turno_pro2.id, ids)
        self.assertIn(self.turno_otro_pro.id, ids)
        self.assertIn(self.turno_sin_profesional.id, ids)


