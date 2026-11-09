"""B9 — modelo definitivo de roles ADMIN / PERSONAL / CLIENTE.

Cubre los puntos de la consigna B9 que no viven en otros archivos:

- solo existen tres roles (sin VENDEDOR);
- el registro público crea cuentas CLIENTE sin vínculo;
- el invariante PERSONAL–Profesional al crear y modificar usuarios vía
  API (UserViewSet + AdminUserSerializer);
- permisos de servicios exclusivos de ADMIN (D1);
- disponibilidades: PERSONAL solo gestiona las suyas;
- turnos: PERSONAL consulta su agenda laboral por ``como_profesional``
  y no reserva ni ve sus reservas como cliente (D4).

La eliminación de un Profesional vinculado se cubre en
``core/test_eliminacion_integridad.py`` y el alta por
``crear-con-usuario`` en ``core/test_profesional_cuenta.py``.
"""

from datetime import time, timedelta

from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Disponibilidad, Profesional, Servicio, Turno
from core.tests import BaseAPITest
from users.models import User


class RolesModeloTests(APITestCase):
    """El sistema tiene exactamente tres roles y el registro crea CLIENTE."""

    def test_solo_existen_tres_roles(self):
        self.assertEqual(
            set(User.Roles.values), {'ADMIN', 'CLIENTE', 'PERSONAL'}
        )
        self.assertEqual(
            [valor for valor, _ in User._meta.get_field('role').choices],
            ['ADMIN', 'CLIENTE', 'PERSONAL'],
        )
        # El rol retirado en B9 ya no existe en el modelo.
        self.assertFalse(hasattr(User.Roles, 'VENDEDOR'))

    def test_registro_publico_crea_cliente_sin_vinculo(self):
        resp = self.client.post(
            reverse('register'),
            {
                'username': 'nuevacuenta',
                'email': 'nuevacuenta@rol.test',
                'password': 'Clave-S3gura-2026',
                'nombre': 'Nueva Cuenta',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        user = User.objects.get(username='nuevacuenta')
        self.assertEqual(user.role, User.Roles.CLIENTE)
        # D3: un CLIENTE no tiene Profesional vinculado.
        self.assertFalse(Profesional.objects.filter(usuario=user).exists())


class InvariantePersonalTests(BaseAPITest):
    """D3 aplicado a la gestión de usuarios (UserViewSet, solo staff)."""

    def setUp(self):
        self.staff = self.crear_usuario(
            'staff', 'staff@test.com', role=User.Roles.ADMIN, staff=True,
        )
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')
        self.personal = self.crear_usuario(
            'personal', 'personal@test.com', role=User.Roles.PERSONAL,
        )
        self.profesional = self.crear_profesional(
            'Pro', usuario=self.personal,
        )
        self.url_users = reverse('user-list')

    def url_user(self, pk):
        return reverse('user-detail', args=[pk])

    def test_no_se_puede_crear_un_usuario_personal_sin_vinculo(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(
            self.url_users,
            {
                'username': 'sinpro',
                'email': 'sinpro@rol.test',
                'role': 'PERSONAL',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('PERSONAL', str(resp.data))
        self.assertFalse(User.objects.filter(username='sinpro').exists())

    def test_no_se_puede_convertir_un_cliente_en_personal_sin_vinculo(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.patch(
            self.url_user(self.cliente.pk), {'role': 'PERSONAL'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('role', resp.data)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.role, User.Roles.CLIENTE)

    def test_no_se_puede_convertir_personal_en_cliente_con_vinculo(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.patch(
            self.url_user(self.personal.pk), {'role': 'CLIENTE'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('role', resp.data)
        self.personal.refresh_from_db()
        self.assertEqual(self.personal.role, User.Roles.PERSONAL)
        # El vínculo sigue intacto.
        self.profesional.refresh_from_db()
        self.assertEqual(self.profesional.usuario, self.personal)

    def test_no_se_puede_convertir_personal_en_admin_con_vinculo(self):
        # Regla general: el vínculo define el rol PERSONAL; ninguna otra
        # transición de rol se permite mientras el vínculo exista.
        self.client.force_authenticate(user=self.staff)
        resp = self.client.patch(
            self.url_user(self.personal.pk), {'role': 'ADMIN'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.personal.refresh_from_db()
        self.assertEqual(self.personal.role, User.Roles.PERSONAL)

    def test_perfil_no_permite_autoescalarse(self):
        # Conservación de B1–B6: role es de solo lectura en el perfil.
        tokens = self.client.post(
            reverse('token_obtain_pair'),
            {'email': self.cliente.email, 'password': 'pass1234'},
            format='json',
        ).data
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
        resp = self.client.patch(
            reverse('profile'), {'role': 'PERSONAL'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.role, User.Roles.CLIENTE)


class PermisosServiciosTests(BaseAPITest):
    """D1: la gestión de servicios es exclusiva de ADMIN."""

    def setUp(self):
        self.admin = self.crear_usuario(
            'admin', 'admin@test.com', role=User.Roles.ADMIN, staff=True,
        )
        self.rol_admin = self.crear_usuario(
            'roladmin', 'roladmin@test.com', role=User.Roles.ADMIN,
        )
        self.personal = self.crear_usuario(
            'personal', 'personal@test.com', role=User.Roles.PERSONAL,
        )
        self.profesional = self.crear_profesional(
            'Pro', usuario=self.personal,
        )
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')
        self.servicio = self.crear_servicio('Semi', duracion_minutos=30)

    def url_servicio(self, pk=None):
        return reverse('servicio-detail', args=[pk or self.servicio.pk])

    def test_personal_no_puede_crear_servicio(self):
        self.client.force_authenticate(user=self.personal)
        resp = self.client.post(
            reverse('servicio-list'),
            {'nombre': 'Nuevo', 'duracion': '00:30:00', 'precio': 4000},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Servicio.objects.filter(nombre='Nuevo').exists())

    def test_personal_no_puede_editar_servicio(self):
        self.client.force_authenticate(user=self.personal)
        resp = self.client.patch(
            self.url_servicio(), {'precio': 9999}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.servicio.refresh_from_db()
        self.assertNotEqual(self.servicio.precio, 9999)

    def test_personal_no_puede_desactivar_servicio(self):
        self.client.force_authenticate(user=self.personal)
        resp = self.client.patch(
            self.url_servicio(), {'is_active': False}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.servicio.refresh_from_db()
        self.assertTrue(self.servicio.is_active)

    def test_cliente_no_puede_crear_servicio(self):
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.post(
            reverse('servicio-list'),
            {'nombre': 'Nuevo', 'duracion': '00:30:00', 'precio': 4000},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonimo_no_puede_crear_servicio(self):
        resp = self.client.post(
            reverse('servicio-list'),
            {'nombre': 'Nuevo', 'duracion': '00:30:00', 'precio': 4000},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rol_admin_sin_staff_puede_editar_servicio(self):
        self.client.force_authenticate(user=self.rol_admin)
        resp = self.client.patch(
            self.url_servicio(), {'precio': 6500}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.precio, 6500)

    def test_admin_puede_crear_servicio(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse('servicio-list'),
            {'nombre': 'Nuevo Admin', 'duracion': '00:30:00', 'precio': 4000},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)


class DisponibilidadPersonalTests(BaseAPITest):
    """PERSONAL gestiona sus propias disponibilidades y solo las suyas."""

    def setUp(self):
        self.personal = self.crear_usuario(
            'personal', 'personal@test.com', role=User.Roles.PERSONAL,
        )
        self.profesional = self.crear_profesional(
            'Pro', usuario=self.personal,
        )
        self.otro_profesional = self.crear_profesional('Otra')
        self.fecha = timezone.localdate() + timedelta(days=1)

    def payload(self, profesional):
        return {
            'profesional': profesional.id,
            'fecha': self.fecha.isoformat(),
            'hora_inicio': '14:00:00',
            'hora_fin': '16:00:00',
        }

    def test_personal_crea_su_disponibilidad(self):
        self.client.force_authenticate(user=self.personal)
        resp = self.client.post(
            reverse('disponibilidad-list'),
            self.payload(self.profesional),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

    def test_personal_no_crea_disponibilidad_de_otro_profesional(self):
        self.client.force_authenticate(user=self.personal)
        resp = self.client.post(
            reverse('disponibilidad-list'),
            self.payload(self.otro_profesional),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            Disponibilidad.objects.filter(
                profesional=self.otro_profesional
            ).exists()
        )

    def test_personal_no_edita_disponibilidad_de_otro_profesional(self):
        franja = Disponibilidad.objects.create(
            profesional=self.otro_profesional,
            fecha=self.fecha,
            hora_inicio=time(9, 0),
            hora_fin=time(12, 0),
        )
        self.client.force_authenticate(user=self.personal)
        resp = self.client.patch(
            reverse('disponibilidad-detail', args=[franja.pk]),
            {'hora_fin': '10:00:00'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        franja.refresh_from_db()
        self.assertEqual(franja.hora_fin, time(12, 0))


class TurnosPersonalTests(BaseAPITest):
    """D4: PERSONAL consulta su agenda laboral y no reserva."""

    def setUp(self):
        self.personal = self.crear_usuario(
            'personal', 'personal@test.com', role=User.Roles.PERSONAL,
        )
        self.profesional = self.crear_profesional(
            'Pro', usuario=self.personal,
        )
        self.cliente = self.crear_usuario('cliente', 'cliente@test.com')
        self.otro_profesional = self.crear_profesional('Otra')
        self.servicio30 = self.crear_servicio(
            'Serv30', duracion_minutos=30,
        )
        self.fecha = timezone.localdate() + timedelta(days=1)
        self.crear_disponibilidad(
            self.profesional, self.fecha, time(9, 0), time(12, 0),
        )
        # Turno laboral del personal (asignado a su profesional).
        self.turno_laboral = Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.cliente,
            profesional=self.profesional, servicio=self.servicio30,
            estado='pendiente',
        )
        # Reserva propia del personal hecha como clienta (con otro
        # profesional): no debe verse en su agenda laboral ni como cliente.
        self.turno_propio = Turno.objects.create(
            fecha=self.fecha, hora=time(9, 0), usuario=self.personal,
            profesional=self.otro_profesional, servicio=self.servicio30,
            estado='pendiente',
        )

    def url_turnos(self):
        return reverse('turno-list')

    def test_personal_ve_sus_turnos_laborales(self):
        self.client.force_authenticate(user=self.personal)
        resp = self.client.get(
            self.url_turnos(), {'como_profesional': 'true'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in resp.data['results']]
        self.assertIn(self.turno_laboral.id, ids)
        self.assertNotIn(self.turno_propio.id, ids)

    def test_personal_no_ve_sus_reservas_como_cliente(self):
        self.client.force_authenticate(user=self.personal)
        resp = self.client.get(self.url_turnos(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in resp.data['results']]
        self.assertNotIn(self.turno_propio.id, ids)
        self.assertNotIn(self.turno_laboral.id, ids)

    def test_personal_no_puede_crear_reservas(self):
        self.client.force_authenticate(user=self.personal)
        resp = self.client.post(
            self.url_turnos(),
            {
                'profesional': self.profesional.id,
                'servicio': self.servicio30.id,
                'fecha': self.fecha.isoformat(),
                'hora': '10:00:00',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Turno.objects.count(), 2)

    def test_cliente_sigue_pudiendo_reservar(self):
        # Regresión: la restricción D4 no afecta al flujo de CLIENTE.
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.post(
            self.url_turnos(),
            {
                'profesional': self.profesional.id,
                'servicio': self.servicio30.id,
                'fecha': self.fecha.isoformat(),
                'hora': '10:00:00',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        turno = Turno.objects.get(pk=resp.data['id'])
        self.assertEqual(turno.usuario, self.cliente)
