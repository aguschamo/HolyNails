"""Tests de las transiciones de estado de turnos (TP9 etapa 1).

POST /api/turnos/{id}/confirmar/ y POST /api/turnos/{id}/cancelar/ aplican
las reglas de negocio acordadas (estados terminales, turnos futuros,
permisos por acción), y PUT/PATCH/DELETE sobre el detalle quedan bloqueados
para todos los usuarios (405).

Se reutiliza ``BaseAPITest`` de core/tests.py sin modificarlo. Patrones
alineados con core/tests.py y core/test_profesional_cuenta.py.
"""
from datetime import datetime, time, timedelta
from unittest import mock

from django.urls import reverse
from django.utils import timezone

from rest_framework import status

from core.models import Turno
from core.tests import BaseAPITest
from users.models import User


class BaseTransicionesTests(BaseAPITest):
    def setUp(self):
        self.admin = self.crear_usuario(
            'admin', 'admin@test.com', role=User.Roles.ADMIN, staff=True
        )
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')
        self.otro_cliente = self.crear_usuario('otro', 'otro@test.com')
        # La profesional es una cuenta User vinculada a Profesional, sin rol
        # propio: nace CLIENTE (mismo caso que el alta administrativa).
        self.pro_user = self.crear_usuario('pro', 'pro@test.com', role=User.Roles.PERSONAL)
        self.profesional = self.crear_profesional('Pro A', usuario=self.pro_user)
        self.servicio = self.crear_servicio('Semi', duracion_minutos=30)
        self.fecha_futura = timezone.localdate() + timedelta(days=1)
        self.fecha_pasada = timezone.localdate() - timedelta(days=1)

    def crear_turno(self, fecha=None, hora=time(10, 0), estado='pendiente',
                    usuario=None, profesional=None):
        return Turno.objects.create(
            fecha=self.fecha_futura if fecha is None else fecha,
            hora=hora,
            usuario=self.cliente if usuario is None else usuario,
            profesional=self.profesional if profesional is None else profesional,
            servicio=self.servicio,
            estado=estado,
        )

    def url_confirmar(self, turno):
        return reverse('turno-confirmar', kwargs={'pk': turno.pk})

    def url_cancelar(self, turno):
        return reverse('turno-cancelar', kwargs={'pk': turno.pk})

    def url_detalle(self, turno):
        return reverse('turno-detail', kwargs={'pk': turno.pk})

    def ahora_congelada(self, hora):
        """Fecha de hoy a las `hora` como fecha aware, para congelar now()."""
        return timezone.make_aware(datetime.combine(timezone.localdate(), hora))


class ConfirmacionTests(BaseTransicionesTests):
    """POST /api/turnos/{id}/confirmar/ — exclusivamente administrador."""

    def test_admin_confirma_un_turno_pendiente_futuro(self):
        turno = self.crear_turno()
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url_confirmar(turno), {}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['estado'], 'confirmado')
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'confirmado')

    def test_admin_no_puede_confirmar_un_turno_cancelado(self):
        turno = self.crear_turno(estado='cancelado')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url_confirmar(turno), {}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'cancelado')

    def test_admin_no_puede_confirmar_un_turno_ya_confirmado(self):
        turno = self.crear_turno(estado='confirmado')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url_confirmar(turno), {}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'confirmado')

    def test_cliente_no_puede_confirmar(self):
        turno = self.crear_turno()
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.post(self.url_confirmar(turno), {}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'pendiente')

    def test_profesional_no_puede_confirmar(self):
        # Turno asignado a la profesional y perteneciente a la clienta.
        turno = self.crear_turno()
        self.client.force_authenticate(user=self.pro_user)
        resp = self.client.post(self.url_confirmar(turno), {}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'pendiente')

    def test_anonimo_no_puede_confirmar(self):
        turno = self.crear_turno()
        resp = self.client.post(self.url_confirmar(turno), {}, format='json')

        self.assertIn(
            resp.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'pendiente')

    def test_no_se_puede_confirmar_un_turno_pasado(self):
        turno = self.crear_turno(fecha=self.fecha_pasada)
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url_confirmar(turno), {}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'pendiente')

    def test_no_se_puede_confirmar_un_turno_de_hoy_que_ya_paso(self):
        # Congelamos el reloj a las 12:00 de hoy: el turno de hoy a las 10:00
        # ya comenzó aunque su fecha sea la de hoy.
        turno = self.crear_turno(fecha=timezone.localdate(), hora=time(10, 0))
        congelado = self.ahora_congelada(time(12, 0))
        self.client.force_authenticate(user=self.admin)
        with mock.patch('django.utils.timezone.now', return_value=congelado):
            resp = self.client.post(self.url_confirmar(turno), {}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'pendiente')

    def test_se_puede_confirmar_un_turno_de_hoy_que_todavia_no_comenzo(self):
        # Un turno de hoy no es "pasado" si su hora todavía no llegó:
        # fecha de hoy + hora futura = turno futuro.
        turno = self.crear_turno(fecha=timezone.localdate(), hora=time(10, 0))
        congelado = self.ahora_congelada(time(9, 0))
        self.client.force_authenticate(user=self.admin)
        with mock.patch('django.utils.timezone.now', return_value=congelado):
            resp = self.client.post(self.url_confirmar(turno), {}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'confirmado')


class CancelacionTests(BaseTransicionesTests):
    """POST /api/turnos/{id}/cancelar/ — administrador o dueño del turno."""

    def test_cliente_cancela_su_turno_pendiente_futuro(self):
        turno = self.crear_turno()
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.post(self.url_cancelar(turno), {}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['estado'], 'cancelado')
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'cancelado')

    def test_cliente_cancela_su_turno_confirmado_futuro(self):
        turno = self.crear_turno(estado='confirmado')
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.post(self.url_cancelar(turno), {}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'cancelado')

    def test_admin_cancela_un_turno_pendiente(self):
        turno = self.crear_turno()
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url_cancelar(turno), {}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'cancelado')

    def test_admin_cancela_un_turno_confirmado(self):
        turno = self.crear_turno(estado='confirmado')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url_cancelar(turno), {}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'cancelado')

    def test_cliente_no_puede_cancelar_un_turno_ajeno(self):
        turno = self.crear_turno(usuario=self.otro_cliente)
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.post(self.url_cancelar(turno), {}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'pendiente')

    def test_profesional_no_puede_cancelar_un_turno_asignado(self):
        # La profesional no puede cancelar "su" turno solo por tenerlo
        # asignado: no es admin ni es el dueño de la reserva.
        turno = self.crear_turno()
        self.client.force_authenticate(user=self.pro_user)
        resp = self.client.post(self.url_cancelar(turno), {}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'pendiente')

    def test_anonimo_no_puede_cancelar(self):
        turno = self.crear_turno()
        resp = self.client.post(self.url_cancelar(turno), {}, format='json')

        self.assertIn(
            resp.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'pendiente')

    def test_no_se_puede_cancelar_un_turno_pasado(self):
        turno = self.crear_turno(fecha=self.fecha_pasada)
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url_cancelar(turno), {}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'pendiente')

    def test_no_se_puede_cancelar_un_turno_de_hoy_que_ya_paso(self):
        turno = self.crear_turno(fecha=timezone.localdate(), hora=time(10, 0))
        congelado = self.ahora_congelada(time(12, 0))
        self.client.force_authenticate(user=self.cliente)
        with mock.patch('django.utils.timezone.now', return_value=congelado):
            resp = self.client.post(self.url_cancelar(turno), {}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'pendiente')

    def test_no_se_puede_cancelar_dos_veces(self):
        # Los turnos cancelados son terminales: no se puede volver a cancelar.
        turno = self.crear_turno(estado='cancelado')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url_cancelar(turno), {}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'cancelado')


class OperacionesGenericasTests(BaseTransicionesTests):
    """PUT/PATCH/DELETE del detalle están bloqueados para todos los usuarios."""

    def test_patch_no_permite_cambiar_el_estado(self):
        turno = self.crear_turno()
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            self.url_detalle(turno), {'estado': 'confirmado'}, format='json'
        )

        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'pendiente')

    def test_patch_no_permite_modificar_fecha_hora_servicio_o_profesional(self):
        turno = self.crear_turno()
        otro_servicio = self.crear_servicio('Otro', duracion_minutos=45)
        otro_profesional = self.crear_profesional('Pro B')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            self.url_detalle(turno),
            {
                'fecha': self.fecha_pasada.isoformat(),
                'hora': '12:00:00',
                'servicio': otro_servicio.id,
                'profesional': otro_profesional.id,
            },
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        turno.refresh_from_db()
        self.assertEqual(turno.fecha, self.fecha_futura)
        self.assertEqual(turno.hora, time(10, 0))
        self.assertEqual(turno.servicio, self.servicio)
        self.assertEqual(turno.profesional, self.profesional)

    def test_put_esta_bloqueado(self):
        turno = self.crear_turno()
        self.client.force_authenticate(user=self.admin)
        resp = self.client.put(
            self.url_detalle(turno),
            {
                'fecha': self.fecha_pasada.isoformat(),
                'hora': '12:00:00',
                'servicio': self.servicio.id,
                'profesional': self.profesional.id,
            },
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        turno.refresh_from_db()
        self.assertEqual(turno.fecha, self.fecha_futura)
        self.assertEqual(turno.hora, time(10, 0))

    def test_delete_esta_bloqueado(self):
        turno = self.crear_turno()
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self.url_detalle(turno))

        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Turno.objects.filter(pk=turno.pk).exists())

    def test_delete_de_un_cliente_tambien_esta_bloqueado(self):
        # Ni siquiera el dueño puede eliminar su turno físicamente.
        turno = self.crear_turno()
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.delete(self.url_detalle(turno))

        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Turno.objects.filter(pk=turno.pk).exists())

    def test_patch_de_un_cliente_tambien_esta_bloqueado(self):
        turno = self.crear_turno()
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.patch(
            self.url_detalle(turno), {'estado': 'cancelado'}, format='json'
        )

        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'pendiente')

    def test_el_turno_cancelado_sigue_existiendo_y_se_consulta_en_el_historial(self):
        turno = self.crear_turno()
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url_cancelar(turno), {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # No se elimina físicamente: sigue registrado para el historial.
        self.assertTrue(Turno.objects.filter(pk=turno.pk).exists())

        resp_list = self.client.get(reverse('turno-list'), format='json')
        self.assertEqual(resp_list.status_code, status.HTTP_200_OK)
        en_historial = [
            t for t in resp_list.data['results'] if t['id'] == turno.pk
        ]
        self.assertEqual(len(en_historial), 1)
        self.assertEqual(en_historial[0]['estado'], 'cancelado')

        # La clienta también puede consultarlo en su historial.
        self.client.force_authenticate(user=self.cliente)
        resp_cliente = self.client.get(reverse('turno-list'), format='json')
        self.assertEqual(resp_cliente.status_code, status.HTTP_200_OK)
        ids_cliente = [t['id'] for t in resp_cliente.data['results']]
        self.assertIn(turno.pk, ids_cliente)


class RegresionTests(BaseTransicionesTests):
    """Las funcionalidades existentes siguen intactas tras los cambios."""

    def test_la_creacion_de_turnos_sigue_funcionando(self):
        self.crear_disponibilidad(
            self.profesional, self.fecha_futura, time(9, 0), time(10, 0)
        )
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.post(
            reverse('turno-list'),
            {
                'profesional': self.profesional.id,
                'servicio': self.servicio.id,
                'fecha': self.fecha_futura.isoformat(),
                'hora': '09:00:00',
            },
            format='json',
        )

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        turno = Turno.objects.get(pk=resp.data['id'])
        self.assertEqual(turno.estado, 'pendiente')
        self.assertEqual(turno.usuario, self.cliente)

    def test_tras_cancelar_el_horario_se_libera(self):
        self.crear_disponibilidad(
            self.profesional, self.fecha_futura, time(9, 0), time(10, 0)
        )
        turno = self.crear_turno(hora=time(9, 0))
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url_cancelar(turno), {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.cliente)
        resp_disp = self.client.get(
            reverse('turno-disponibles'),
            {'servicio': self.servicio.id, 'fecha': self.fecha_futura.isoformat()},
            format='json',
        )
        self.assertEqual(resp_disp.status_code, status.HTTP_200_OK)
        horas = [item['hora'] for item in resp_disp.data]
        self.assertIn('09:00', horas)

    def test_tras_confirmar_el_horario_sigue_bloqueado(self):
        self.crear_disponibilidad(
            self.profesional, self.fecha_futura, time(9, 0), time(10, 0)
        )
        turno = self.crear_turno(hora=time(9, 0))
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url_confirmar(turno), {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.cliente)
        resp_disp = self.client.get(
            reverse('turno-disponibles'),
            {'servicio': self.servicio.id, 'fecha': self.fecha_futura.isoformat()},
            format='json',
        )
        self.assertEqual(resp_disp.status_code, status.HTTP_200_OK)
        horas = [item['hora'] for item in resp_disp.data]
        self.assertNotIn('09:00', horas)

    def test_las_consultas_de_cliente_siguen_restringidas_a_sus_turnos(self):
        turno_mio = self.crear_turno(usuario=self.cliente)
        # Distinta hora para no chocar con el UniqueConstraint
        # (profesional, fecha, hora) que comparten los turnos de prueba.
        turno_ajeno = self.crear_turno(usuario=self.otro_cliente, hora=time(11, 0))

        # La clienta cancela el suyo (transición exitosa)…
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.post(self.url_cancelar(turno_mio), {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # …y su listado sigue viendo solo los turnos propios.
        resp_list = self.client.get(reverse('turno-list'), format='json')
        self.assertEqual(resp_list.status_code, status.HTTP_200_OK)
        ids = [t['id'] for t in resp_list.data['results']]
        self.assertIn(turno_mio.pk, ids)
        self.assertNotIn(turno_ajeno.pk, ids)
