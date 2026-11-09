"""B10.0.2 — compatibilidad de ADMIN con funciones de CLIENTE y PERSONAL.

Cubre las reglas de la etapa:

- ADMIN reserva turnos para sí mismo y el turno queda en su cuenta;
- ADMIN consulta sus propias reservas con ``?propios=true`` (el usuario
  se determina desde el token, nunca desde un ID enviado por el frontend)
  y sigue viendo todos los turnos en la consulta administrativa general;
- ``?como_profesional=true`` devuelve exclusivamente los turnos del
  Profesional asociado al ADMIN autenticado; sin vínculo → vacío;
- CLIENTE sigue viendo únicamente sus propias reservas (los parámetros
  manipulados no amplían lo que puede ver);
- ADMIN con Profesional asociado conserva todos sus permisos
  administrativos y gestiona su propia disponibilidad;
- vincular un Profesional a una cuenta ADMIN no cambia su rol.

Patrones alineados con core/tests.py (BaseAPITest) y
core/test_modelo_roles.py.
"""

from datetime import time, timedelta

from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Profesional, Turno
from core.tests import BaseAPITest
from users.models import User


class AdminReservaPropiaTests(BaseAPITest):
    """ADMIN agenda para sí mismo y consulta solo sus reservas propias."""

    def setUp(self):
        self.admin = self.crear_usuario(
            'admin', 'admin@test.com', role=User.Roles.ADMIN, staff=True,
        )
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')
        self.pro_user = self.crear_usuario('pro', 'pro@test.com', role=User.Roles.PERSONAL)
        self.profesional = self.crear_profesional('Pro A', usuario=self.pro_user)
        self.servicio30 = self.crear_servicio('Serv30', duracion_minutos=30)
        self.fecha = timezone.localdate() + timedelta(days=1)
        self.crear_disponibilidad(
            self.profesional, self.fecha, time(9, 0), time(12, 0),
        )
        # Reserva propia del admin (en el mismo profesional que la de la
        # clienta, para que «propios» no pueda confundirse con «todos»).
        self.turno_admin = Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.admin,
            profesional=self.profesional, servicio=self.servicio30,
            estado='pendiente',
        )
        # Reserva de la clienta.
        self.turno_cliente = Turno.objects.create(
            fecha=self.fecha, hora=time(10, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='pendiente',
        )

    def url_turnos(self):
        return reverse('turno-list')

    @staticmethod
    def ids(resp):
        return [item['id'] for item in resp.data['results']]

    def test_admin_puede_reservar_un_turno_propio(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.url_turnos(),
            {
                'profesional': self.profesional.id,
                'servicio': self.servicio30.id,
                'fecha': self.fecha.isoformat(),
                'hora': '11:00:00',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        # El turno queda asociado a la propia cuenta del admin.
        self.assertEqual(resp.data['usuario'], self.admin.id)
        turno = Turno.objects.get(pk=resp.data['id'])
        self.assertEqual(turno.usuario, self.admin)
        # Vincular reservar no altera nada del rol.
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, User.Roles.ADMIN)

    def test_admin_consulta_sus_reservas_con_propios(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(
            self.url_turnos(), {'propios': 'true'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = self.ids(resp)
        self.assertIn(self.turno_admin.id, ids)
        self.assertNotIn(self.turno_cliente.id, ids)

    def test_admin_sin_propios_sigue_viendo_todos(self):
        # La consulta administrativa general no cambia: sin el parámetro,
        # ADMIN ve todos los turnos.
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url_turnos(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = self.ids(resp)
        self.assertIn(self.turno_admin.id, ids)
        self.assertIn(self.turno_cliente.id, ids)

    def test_cliente_con_propios_sigue_viendo_lo_mismo_que_antes(self):
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get(
            self.url_turnos(), {'propios': 'true'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = self.ids(resp)
        self.assertIn(self.turno_cliente.id, ids)
        self.assertNotIn(self.turno_admin.id, ids)

    def test_parametro_de_usuario_ajeno_no_expande_la_visibilidad(self):
        # Un ID manipulado desde el frontend no sirve para ver reservas
        # ajenas: el parámetro no existe, el scoping por rol manda.
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get(
            self.url_turnos(),
            {'usuario': self.admin.id, 'propios': 'true'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = self.ids(resp)
        self.assertEqual(ids, [self.turno_cliente.id])

    def test_personal_no_puede_reservar_como_cliente(self):
        # D4 intacto: PERSONAL sigue excluido del flujo de reservas.
        self.client.force_authenticate(user=self.pro_user)
        resp = self.client.post(
            self.url_turnos(),
            {
                'profesional': self.profesional.id,
                'servicio': self.servicio30.id,
                'fecha': self.fecha.isoformat(),
                'hora': '11:00:00',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class AdminComoProfesionalTests(BaseAPITest):
    """``?como_profesional=true`` con ADMIN, con y sin Profesional."""

    def setUp(self):
        self.admin = self.crear_usuario(
            'admin', 'admin@test.com', role=User.Roles.ADMIN, staff=True,
        )
        self.admin_vinc = self.crear_usuario(
            'adminvino', 'adminvino@test.com', role=User.Roles.ADMIN,
        )
        self.pro_user = self.crear_usuario('pro', 'pro@test.com', role=User.Roles.PERSONAL)
        self.profesional = self.crear_profesional('Pro A', usuario=self.pro_user)
        self.profesional_admin = self.crear_profesional(
            'Pro del Admin', usuario=self.admin_vinc,
        )
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')
        self.servicio30 = self.crear_servicio('Serv30', duracion_minutos=30)
        self.fecha = timezone.localdate() + timedelta(days=1)
        # Turnos del profesional del admin vinculado.
        self.turno_del_admin = Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional_admin, servicio=self.servicio30,
            estado='pendiente',
        )
        # Turno de otro profesional.
        self.turno_ajeno = Turno.objects.create(
            fecha=self.fecha, hora=time(10, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='pendiente',
        )

    @staticmethod
    def ids(resp):
        return [item['id'] for item in resp.data['results']]

    def test_admin_vinculado_ve_exclusivamente_su_agenda_profesional(self):
        self.client.force_authenticate(user=self.admin_vinc)
        resp = self.client.get(
            reverse('turno-list'), {'como_profesional': 'true'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = self.ids(resp)
        self.assertIn(self.turno_del_admin.id, ids)
        self.assertNotIn(self.turno_ajeno.id, ids)

    def test_admin_sin_vinculo_no_tiene_agenda_profesional(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(
            reverse('turno-list'), {'como_profesional': 'true'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(resp), [])

    def test_admin_vinculado_como_profesional_con_propios_es_interseccion(self):
        # Unicamente las reservas que le pertenecen al admin DENTRO de su
        # agenda profesional (intersección, nunca amplía).
        turno_propio = Turno.objects.create(
            fecha=self.fecha, hora=time(11, 0), usuario=self.admin_vinc,
            profesional=self.profesional_admin, servicio=self.servicio30,
            estado='pendiente',
        )
        self.client.force_authenticate(user=self.admin_vinc)
        resp = self.client.get(
            reverse('turno-list'),
            {'como_profesional': 'true', 'propios': 'true'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = self.ids(resp)
        self.assertEqual(ids, [turno_propio.id])


class AdminPermisosVinculadoTests(APITestCase):
    """Vincular un Profesional a ADMIN no le quita permisos administrativos."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='pass1234',
            nombre='Admin',
            role=User.Roles.ADMIN,
        )
        self.admin.save()
        self.admin_vinc = User.objects.create_user(
            username='adminvino',
            email='adminvino@test.com',
            password='pass1234',
            nombre='Admin Vinculado',
            role=User.Roles.ADMIN,
        )
        self.cliente = User.objects.create_user(
            username='cliente',
            email='cliente@test.com',
            password='pass1234',
            nombre='Cliente',
            role=User.Roles.CLIENTE,
        )

    def test_vincular_admin_conserva_el_rol(self):
        otro = Profesional.objects.create(nombre='Pro B')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            reverse('profesional-detail', args=[otro.id]),
            {'usuario': self.admin_vinc.id},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.admin_vinc.refresh_from_db()
        self.assertEqual(self.admin_vinc.role, User.Roles.ADMIN)
        otro.refresh_from_db()
        self.assertEqual(otro.usuario, self.admin_vinc)

    def test_admin_vinculado_puede_crear_servicios(self):
        Profesional.objects.create(nombre='Pro B', usuario=self.admin_vinc)
        self.client.force_authenticate(user=self.admin_vinc)
        resp = self.client.post(
            reverse('servicio-list'),
            {'nombre': 'Nuevo Admin', 'duracion': '00:30:00', 'precio': 4000},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.admin_vinc.refresh_from_db()
        self.assertEqual(self.admin_vinc.role, User.Roles.ADMIN)

    def test_admin_vinculado_gestiona_su_propia_disponibilidad(self):
        profesional = Profesional.objects.create(
            nombre='Pro B', usuario=self.admin_vinc,
        )
        self.client.force_authenticate(user=self.admin_vinc)
        resp = self.client.post(
            reverse('disponibilidad-list'),
            {
                'profesional': profesional.id,
                'fecha': (timezone.localdate() + timedelta(days=1)).isoformat(),
                'hora_inicio': '14:00:00',
                'hora_fin': '16:00:00',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        # Y el rol sigue intacto tras gestionar su agenda.
        self.admin_vinc.refresh_from_db()
        self.assertEqual(self.admin_vinc.role, User.Roles.ADMIN)

    def test_admin_sin_profesional_no_tiene_agenda_profesional(self):
        # Sin vínculo: la vista como profesional está vacía (no tiene a
        # qué «Mi agenda» apuntar), pero la consulta general sigue íntegra.
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(
            reverse('turno-list'), {'como_profesional': 'true'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['results'], [])
