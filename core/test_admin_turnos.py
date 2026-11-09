"""B10.1 — contrato de API del panel administrativo de turnos.

La pantalla de administración consume exactamente dos cosas:

- ``GET /api/turnos/``: consulta general (todos los turnos del salón,
  sin ``?propios=true``), con ``usuario_nombre`` para identificar y
  buscar a la clienta (B10.1 agrega ese campo de solo lectura);
- ``POST /api/turnos/{id}/confirmar/`` y ``POST /api/turnos/{id}/cancelar/``
  con las transiciones de estado existentes.

Las reglas de negocio de las transiciones están cubiertas en profundidad
por ``core/test_transiciones_estado.py`` y el scoping por rol por
``core/tests.py`` y ``core/test_admin_compatibilidad.py``; acá se verifica
el contrato puntual que usa la pantalla (incluidos los bloqueos de
acceso y de transición inválida).
"""

from datetime import time, timedelta

from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Profesional, Servicio, Turno
from core.tests import BaseAPITest
from users.models import User


class ListadoAdminTurnosTests(BaseAPITest):
    """GET /api/turnos/ como lo consume el panel: general y con nombres."""

    def setUp(self):
        self.admin = self.crear_usuario(
            'admin', 'admin@test.com', role=User.Roles.ADMIN,
        )
        self.cliente = User.objects.create_user(
            username='cliente',
            email='cliente@test.com',
            password='pass1234',
            nombre='Carla Gómez',
            role=User.Roles.CLIENTE,
        )
        self.otra_cliente = User.objects.create_user(
            username='otra',
            email='otra@test.com',
            password='pass1234',
            nombre='Ana Pérez',
            role=User.Roles.CLIENTE,
        )
        self.pro_user = self.crear_usuario(
            'pro', 'pro@test.com', role=User.Roles.PERSONAL,
        )
        self.profesional = self.crear_profesional('María', usuario=self.pro_user)
        self.servicio30 = self.crear_servicio('Serv30', duracion_minutos=30)
        self.fecha = timezone.localdate() + timedelta(days=1)
        self.turno_cliente = Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='pendiente',
        )
        self.turno_otra = Turno.objects.create(
            fecha=self.fecha, hora=time(10, 0), usuario=self.otra_cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='confirmado',
        )

    def test_el_listado_admin_trae_el_nombre_de_las_clientas(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(reverse('turno-list'), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        por_id = {item['id']: item for item in resp.data['results']}
        turno = por_id[self.turno_cliente.id]
        # El nombre identifica a la clienta y el id del usuario se conserva
        # (otros flujos lo siguen usando como referencia).
        self.assertEqual(turno['usuario_nombre'], 'Carla Gómez')
        self.assertEqual(turno['usuario'], self.cliente.id)

    def test_el_listado_admin_es_general_sin_filtro_propio(self):
        # B10.1: la consulta administrativa no usa ?propios=true y trae
        # turnos de todas las clientas.
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(reverse('turno-list'), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in resp.data['results']]
        self.assertIn(self.turno_cliente.id, ids)
        self.assertIn(self.turno_otra.id, ids)
        nombres = {item['usuario_nombre'] for item in resp.data['results']}
        self.assertEqual(nombres, {'Carla Gómez', 'Ana Pérez'})

    def test_cliente_sigue_viendolo_suyo_con_su_nombre(self):
        # CLIENTE no accede al panel, pero el campo nuevo tampoco le
        # expone reservas ajenas.
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get(reverse('turno-list'), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 1)
        self.assertEqual(
            resp.data['results'][0]['usuario_nombre'], 'Carla Gómez',
        )


class TransicionesDesdeElPanelTests(APITestCase):
    """Confirmar / cancelar tal como los llama la pantalla (B10.1)."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin', email='admin@test.com', password='pass1234',
            nombre='Admin', role=User.Roles.ADMIN,
        )
        self.cliente = User.objects.create_user(
            username='cliente', email='cliente@test.com', password='pass1234',
            nombre='Carla Gómez', role=User.Roles.CLIENTE,
        )
        self.pro_user = User.objects.create_user(
            username='pro', email='pro@test.com', password='pass1234',
            nombre='María', role=User.Roles.PERSONAL,
        )
        self.profesional = Profesional.objects.create(
            nombre='María', usuario=self.pro_user,
        )
        self.servicio = Servicio.objects.create(
            nombre='Serv30', duracion=timedelta(minutes=30), precio='5000.00',
        )
        self.fecha = timezone.localdate() + timedelta(days=1)
        self.pendiente = Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio,
            estado='pendiente',
        )
        self.confirmado = Turno.objects.create(
            fecha=self.fecha, hora=time(10, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio,
            estado='confirmado',
        )
        self.cancelado = Turno.objects.create(
            fecha=self.fecha, hora=time(11, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio,
            estado='cancelado',
        )

    @staticmethod
    def url(accion, turno):
        return reverse(f'turno-{accion}', kwargs={'pk': turno.pk})

    def test_admin_confirma_un_turno_pendiente(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url('confirmar', self.pendiente), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['estado'], Turno.Estado.CONFIRMADO)
        # La respuesta de la transición también identifica a la clienta.
        self.assertEqual(resp.data['usuario_nombre'], 'Carla Gómez')
        self.pendiente.refresh_from_db()
        self.assertEqual(self.pendiente.estado, Turno.Estado.CONFIRMADO)

    def test_admin_cancela_un_turno_confirmado(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url('cancelar', self.confirmado), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['estado'], Turno.Estado.CANCELADO)
        self.confirmado.refresh_from_db()
        self.assertEqual(self.confirmado.estado, Turno.Estado.CANCELADO)

    def test_transicion_invalida_devuelve_400(self):
        # No se puede confirmar un turno cancelado (el backend es la
        # autoridad aunque el frontend oculte el botón).
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.url('confirmar', self.cancelado), format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.cancelado.refresh_from_db()
        self.assertEqual(self.cancelado.estado, Turno.Estado.CANCELADO)

    def test_cliente_no_puede_usar_las_acciones_del_panel(self):
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.post(self.url('confirmar', self.pendiente), format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.pendiente.refresh_from_db()
        self.assertEqual(self.pendiente.estado, Turno.Estado.PENDIENTE)

    def test_el_estado_no_se_modifica_con_un_patch_directo(self):
        # La pantalla nunca manda PATCH/PUT: el estado solo cambia por
        # las transiciones.
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            reverse('turno-detail', args=[self.pendiente.pk]),
            {'estado': 'confirmado'},
            format='json',
        )
        self.pendiente.refresh_from_db()
        self.assertEqual(self.pendiente.estado, Turno.Estado.PENDIENTE)
        self.assertNotEqual(
            (resp.status_code, self.pendiente.estado),
            (status.HTTP_200_OK, Turno.Estado.CONFIRMADO),
        )
