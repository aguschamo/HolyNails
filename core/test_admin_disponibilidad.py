"""B10.2 — contrato de API de la pantalla de horarios / disponibilidad.

La pantalla administrativa consume exactamente estos endpoints de
``/api/disponibilidades/``:

- ``GET /api/disponibilidades/`` (consulta acotada por rol: admin ve
  todas y PERSONAL sólo las suyas; la consulta de CLIENTE se conserva
  por compatibilidad con un test existente que la exige);
- ``POST /api/disponibilidades/`` (crear);
- ``PATCH /api/disponibilidades/{id}/`` (editar);
- ``DELETE /api/disponibilidades/{id}/`` (eliminar).

Las validaciones de modelo (horario, solape, unicidad) y la protección
de turnos existentes ya estaban cubiertas por ``core/tests.py``,
``core/test_disponibilidad_integridad.py``,
``core/test_conflictos_integridad.py`` y
``core/test_eliminacion_integridad.py``; acá se verifica el contrato
puntual que usa la nueva pantalla, incluido el acote de lectura por rol
que era la incompatibilidad detectada en el diagnóstico de B10.2.
"""

from datetime import time, timedelta

from django.urls import reverse
from django.utils import timezone

from rest_framework import status

from core.models import Disponibilidad, Turno
from core.tests import BaseAPITest
from users.models import User


class ListadoPorRolTests(BaseAPITest):
    """GET /api/disponibilidades/: ADMIN ve todas y PERSONAL sólo las suyas.

    La lectura de CLIENTE no se acota acá: ``FechaPasadaTests.
    test_consultar_disponibilidades_historicas_permitido`` (cobertura
    existente) exige que pueda consultar franjas; su bloqueo opera en la
    pantalla de administración y en las operaciones de escritura
    (``ClienteOperacionesTests``).
    """

    def setUp(self):
        self.admin = self.crear_usuario(
            'admin', 'admin@test.com', role=User.Roles.ADMIN,
        )
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')
        self.pro_user = self.crear_usuario(
            'pro', 'pro@test.com', role=User.Roles.PERSONAL,
        )
        self.profesional = self.crear_profesional('Pro A', usuario=self.pro_user)
        self.otro_user = self.crear_usuario(
            'otro', 'otro@test.com', role=User.Roles.PERSONAL,
        )
        self.otro_profesional = self.crear_profesional('Pro B', usuario=self.otro_user)
        self.fecha = timezone.localdate() + timedelta(days=1)
        self.disp_propia = self.crear_disponibilidad(
            self.profesional, self.fecha, time(9, 0), time(12, 0),
        )
        self.disp_ajena = self.crear_disponibilidad(
            self.otro_profesional, self.fecha, time(14, 0), time(16, 0),
        )

    @staticmethod
    def url_list():
        return reverse('disponibilidad-list')

    @staticmethod
    def ids_de(resp):
        return [item['id'] for item in resp.data['results']]

    def test_admin_consulta_las_disponibilidades_de_todos_los_profesionales(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.url_list(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = self.ids_de(resp)
        self.assertIn(self.disp_propia.id, ids)
        self.assertIn(self.disp_ajena.id, ids)

    def test_admin_filtra_por_profesional_y_fecha(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(
            self.url_list(),
            {'profesional': self.profesional.id, 'fecha': self.fecha.isoformat()},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = self.ids_de(resp)
        self.assertIn(self.disp_propia.id, ids)
        self.assertNotIn(self.disp_ajena.id, ids)

    def test_personal_solo_consulta_sus_propias_disponibilidades(self):
        self.client.force_authenticate(user=self.pro_user)
        resp = self.client.get(self.url_list(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = self.ids_de(resp)
        self.assertIn(self.disp_propia.id, ids)
        self.assertNotIn(self.disp_ajena.id, ids)

    def test_personal_no_consulta_disponibilidades_ajenas_aunque_pida_ese_profesional(self):
        # Manipulando el query param: la intersección con el acote por rol
        # sigue sin exponer franjas de otro profesional.
        self.client.force_authenticate(user=self.pro_user)
        resp = self.client.get(
            self.url_list(), {'profesional': self.otro_profesional.id}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids_de(resp), [])

    def test_cliente_conserva_la_consulta_previa_de_disponibilidades(self):
        # La lectura de CLIENTE es un comportamiento previo protegido por
        # ``test_consultar_disponibilidades_historicas_permitido``: el
        # bloqueo de CLIENTE en B10.2 es de pantalla y de operaciones de
        # escritura (ver ClienteOperacionesTests), no de consulta.
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get(self.url_list(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn(self.disp_propia.id, self.ids_de(resp))


class OperacionesAdminTests(BaseAPITest):
    """ADMIN crea, edita y elimina disponibilidades de cualquier profesional."""

    def setUp(self):
        self.admin = self.crear_usuario(
            'admin', 'admin@test.com', role=User.Roles.ADMIN,
        )
        self.profesional = self.crear_profesional('Pro A')
        self.fecha = timezone.localdate() + timedelta(days=1)
        self.disponibilidad = self.crear_disponibilidad(
            self.profesional, self.fecha, time(9, 0), time(12, 0),
        )
        self.client.force_authenticate(user=self.admin)

    def test_admin_crea_disponibilidad_para_cualquier_profesional(self):
        resp = self.client.post(
            reverse('disponibilidad-list'),
            {
                'profesional': self.profesional.id,
                'fecha': self.fecha.isoformat(),
                'hora_inicio': '14:00:00',
                'hora_fin': '16:00:00',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(
            Disponibilidad.objects.filter(
                profesional=self.profesional,
                fecha=self.fecha,
                hora_inicio=time(14, 0),
                hora_fin=time(16, 0),
            ).exists(),
        )

    def test_admin_edita_disponibilidad_de_cualquier_profesional(self):
        resp = self.client.patch(
            reverse('disponibilidad-detail', args=[self.disponibilidad.pk]),
            {'hora_fin': '11:00:00'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.disponibilidad.refresh_from_db()
        self.assertEqual(self.disponibilidad.hora_fin, time(11, 0))

    def test_admin_elimina_disponibilidad_de_cualquier_profesional(self):
        resp = self.client.delete(
            reverse('disponibilidad-detail', args=[self.disponibilidad.pk]),
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Disponibilidad.objects.filter(pk=self.disponibilidad.pk).exists())


class OperacionesPersonalTests(BaseAPITest):
    """PERSONAL administra las suyas; no puede tocar las ajenas."""

    def setUp(self):
        self.pro_user = self.crear_usuario(
            'pro', 'pro@test.com', role=User.Roles.PERSONAL,
        )
        self.profesional = self.crear_profesional('Pro A', usuario=self.pro_user)
        self.otro_user = self.crear_usuario(
            'otro', 'otro@test.com', role=User.Roles.PERSONAL,
        )
        self.otro_profesional = self.crear_profesional('Pro B', usuario=self.otro_user)
        self.fecha = timezone.localdate() + timedelta(days=1)
        self.disp_propia = self.crear_disponibilidad(
            self.profesional, self.fecha, time(9, 0), time(12, 0),
        )
        self.disp_ajena = self.crear_disponibilidad(
            self.otro_profesional, self.fecha, time(9, 0), time(12, 0),
        )

    @staticmethod
    def url_list():
        return reverse('disponibilidad-list')

    @staticmethod
    def url_detalle(pk):
        return reverse('disponibilidad-detail', args=[pk])

    def test_personal_crea_su_disponibilidad(self):
        self.client.force_authenticate(user=self.pro_user)
        resp = self.client.post(
            self.url_list(),
            {
                'profesional': self.profesional.id,
                'fecha': self.fecha.isoformat(),
                'hora_inicio': '14:00:00',
                'hora_fin': '16:00:00',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(
            Disponibilidad.objects.filter(
                profesional=self.profesional, hora_inicio=time(14, 0),
            ).exists(),
        )

    def test_personal_edita_su_disponibilidad(self):
        self.client.force_authenticate(user=self.pro_user)
        resp = self.client.patch(
            self.url_detalle(self.disp_propia.pk), {'hora_fin': '11:00:00'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.disp_propia.refresh_from_db()
        self.assertEqual(self.disp_propia.hora_fin, time(11, 0))

    def test_personal_elimina_su_disponibilidad(self):
        self.client.force_authenticate(user=self.pro_user)
        resp = self.client.delete(self.url_detalle(self.disp_propia.pk))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Disponibilidad.objects.filter(pk=self.disp_propia.pk).exists())
        # La franja ajena queda intacta.
        self.assertTrue(Disponibilidad.objects.filter(pk=self.disp_ajena.pk).exists())

    def test_personal_no_crea_disponibilidad_para_otro_profesional(self):
        self.client.force_authenticate(user=self.pro_user)
        resp = self.client.post(
            self.url_list(),
            {
                'profesional': self.otro_profesional.id,
                'fecha': self.fecha.isoformat(),
                'hora_inicio': '14:00:00',
                'hora_fin': '16:00:00',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Disponibilidad.objects.count(), 2)

    def test_personal_no_edita_disponibilidad_ajena_manipulando_el_id(self):
        self.client.force_authenticate(user=self.pro_user)
        resp = self.client.patch(
            self.url_detalle(self.disp_ajena.pk), {'hora_fin': '11:00:00'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.disp_ajena.refresh_from_db()
        self.assertEqual(self.disp_ajena.hora_fin, time(12, 0))

    def test_personal_no_elimina_disponibilidad_ajena_manipulando_el_id(self):
        self.client.force_authenticate(user=self.pro_user)
        resp = self.client.delete(self.url_detalle(self.disp_ajena.pk))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Disponibilidad.objects.filter(pk=self.disp_ajena.pk).exists())

    def test_personal_no_reasigna_su_disponibilidad_a_otro_profesional(self):
        # El cuerpo intenta cambiar la pertenencia: el backend lo rechaza
        # y la franja sigue siendo del profesional original.
        self.client.force_authenticate(user=self.pro_user)
        resp = self.client.patch(
            self.url_detalle(self.disp_propia.pk),
            {'profesional': self.otro_profesional.id},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.disp_propia.refresh_from_db()
        self.assertEqual(self.disp_propia.profesional, self.profesional)


class ClienteOperacionesTests(BaseAPITest):
    """CLIENTE no accede a las operaciones de disponibilidad."""

    def setUp(self):
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')
        self.profesional = self.crear_profesional('Pro A')
        self.fecha = timezone.localdate() + timedelta(days=1)
        self.disponibilidad = self.crear_disponibilidad(
            self.profesional, self.fecha, time(9, 0), time(12, 0),
        )
        self.client.force_authenticate(user=self.cliente)

    def test_cliente_no_puede_crear(self):
        resp = self.client.post(
            reverse('disponibilidad-list'),
            {
                'profesional': self.profesional.id,
                'fecha': self.fecha.isoformat(),
                'hora_inicio': '14:00:00',
                'hora_fin': '16:00:00',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Disponibilidad.objects.count(), 1)

    def test_cliente_no_puede_editar(self):
        resp = self.client.patch(
            reverse('disponibilidad-detail', args=[self.disponibilidad.pk]),
            {'hora_fin': '11:00:00'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.disponibilidad.refresh_from_db()
        self.assertEqual(self.disponibilidad.hora_fin, time(12, 0))

    def test_cliente_no_puede_eliminar(self):
        resp = self.client.delete(
            reverse('disponibilidad-detail', args=[self.disponibilidad.pk]),
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Disponibilidad.objects.filter(pk=self.disponibilidad.pk).exists())


class ValidacionesDeHorarioTests(BaseAPITest):
    """Las validaciones de horario y solapamiento siguen vigentes."""

    def setUp(self):
        self.admin = self.crear_usuario(
            'admin', 'admin@test.com', role=User.Roles.ADMIN,
        )
        self.profesional = self.crear_profesional('Pro A')
        self.fecha = timezone.localdate() + timedelta(days=1)
        self.disponibilidad = self.crear_disponibilidad(
            self.profesional, self.fecha, time(9, 0), time(12, 0),
        )
        self.client.force_authenticate(user=self.admin)

    @staticmethod
    def url_list():
        return reverse('disponibilidad-list')

    @staticmethod
    def url_detalle(pk):
        return reverse('disponibilidad-detail', args=[pk])

    def test_fin_igual_o_anterior_a_inicio_se_rechaza(self):
        resp = self.client.post(
            self.url_list(),
            {
                'profesional': self.profesional.id,
                'fecha': self.fecha.isoformat(),
                'hora_inicio': '14:00:00',
                'hora_fin': '14:00:00',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_solape_en_creacion_se_rechaza(self):
        resp = self.client.post(
            self.url_list(),
            {
                'profesional': self.profesional.id,
                'fecha': self.fecha.isoformat(),
                'hora_inicio': '11:00:00',
                'hora_fin': '14:00:00',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_solape_en_edicion_se_rechaza(self):
        # Otra franja el mismo día 14:00-16:00; mover la existente a
        # 15:00-17:00 se solaparía.
        self.crear_disponibilidad(
            self.profesional, self.fecha, time(14, 0), time(16, 0),
        )
        resp = self.client.patch(
            self.url_detalle(self.disponibilidad.pk),
            {'hora_inicio': '15:00:00', 'hora_fin': '17:00:00'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class IntegridadConTurnosTests(BaseAPITest):
    """Administrar disponibilidades no toca los turnos existentes."""

    def setUp(self):
        self.admin = self.crear_usuario(
            'admin', 'admin@test.com', role=User.Roles.ADMIN,
        )
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')
        self.profesional = self.crear_profesional('Pro A')
        self.servicio = self.crear_servicio('Serv30', duracion_minutos=30)
        self.fecha = timezone.localdate() + timedelta(days=1)
        self.disponibilidad = self.crear_disponibilidad(
            self.profesional, self.fecha, time(9, 0), time(12, 0),
        )
        self.turno = Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio,
            estado='pendiente',
        )

    def test_no_se_elimina_una_disponibilidad_de_la_que_dependen_turnos(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(
            reverse('disponibilidad-detail', args=[self.disponibilidad.pk]),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Disponibilidad.objects.filter(pk=self.disponibilidad.pk).exists())
        # El turno queda intacto: no hay efectos secundarios.
        self.turno.refresh_from_db()
        self.assertEqual(self.turno.estado, 'pendiente')

    def test_editar_una_disponibilidad_no_modifica_sus_turnos(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            reverse('disponibilidad-detail', args=[self.disponibilidad.pk]),
            {'hora_fin': '11:00:00'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.turno.refresh_from_db()
        self.assertEqual(self.turno.fecha, self.fecha)
        self.assertEqual(self.turno.hora, time(9, 0))
        self.assertEqual(self.turno.estado, 'pendiente')
