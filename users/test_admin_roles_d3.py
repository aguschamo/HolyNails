"""B9.1 — el Django Admin de usuarios respeta el invariante D3.

Verifica que desde el panel administrativo no se pueda romper el
invariante PERSONAL–Profesional:

- crear un usuario con rol PERSONAL sin Profesional (impedido; el alta
  correcta es el flujo ``crear-con-usuario`` de la API);
- asignar PERSONAL a una cuenta sin vínculo;
- convertir una cuenta PERSONAL con vínculo a CLIENTE o ADMIN;
- comprobar al mismo tiempo que las ediciones válidas (roles sin vínculo
  y conservación del rol PERSONAL al editar) siguen funcionando, y que
  el no-op de guardar el mismo rol en una cuenta ADMIN con vínculo
  tampoco se bloquea (B10.0.2).

Patrones de users/test_admin_integridad.py (POST al endpoint del admin
y verificación de ``resp.context['adminform'].form.errors``).
"""

from django.test import TestCase
from django.urls import reverse

from core.models import Profesional
from users.models import User


class RolesAdminD3Tests(TestCase):
    """El form del admin valida role con la misma regla que la API."""

    def setUp(self):
        self.root = User.objects.create_superuser(
            'root', 'root@test.com', 'RootPass123!'
        )
        self.client.force_login(self.root)
        self.cliente = User.objects.create_user(
            'cliente', 'cliente@test.com', 'ClientePass123!',
            role=User.Roles.CLIENTE,
        )
        self.personal = User.objects.create_user(
            'personal', 'personal@test.com', 'PersonalPass123!',
            role=User.Roles.PERSONAL,
        )
        self.profesional = Profesional.objects.create(
            nombre='Pro D3', usuario=self.personal,
        )

    def url_add(self):
        return reverse('admin:users_user_add')

    def url_change(self, user):
        return reverse('admin:users_user_change', args=[user.pk])

    @staticmethod
    def errores(resp):
        return resp.context['adminform'].form.errors

    @staticmethod
    def payload_cambio(user, **extra):
        """Datos de POST del form de edición, con fecha/hora split (admin)."""
        datos = {
            'username': user.username,
            'email': user.email or '',
            'nombre': user.nombre,
            'role': user.role,
            'is_active': 'on' if user.is_active else '',
            'is_staff': 'on' if user.is_staff else '',
            'is_superuser': 'on' if user.is_superuser else '',
            'last_login': '',
            'date_joined_0': user.date_joined.strftime('%Y-%m-%d'),
            'date_joined_1': user.date_joined.strftime('%H:%M:%S.%f'),
            'groups': [],
            'user_permissions': [],
            'password': user.password,
        }
        datos.update(extra)
        return datos

    def test_alta_impide_rol_personal_sin_vinculo(self):
        resp = self.client.post(
            self.url_add(),
            {
                'username': 'nuevopersonal',
                'password1': 'NuevaClave123!',
                'password2': 'NuevaClave123!',
                'email': 'nuevopersonal@test.com',
                'nombre': 'Nuevo Personal',
                'role': 'PERSONAL',
                'is_active': 'on',
                'is_staff': '',
                'is_superuser': '',
            },
        )
        self.assertEqual(resp.status_code, 200)
        errores = self.errores(resp)
        self.assertIn('role', errores)
        # Explica que el alta con vínculo es el flujo crear-con-usuario.
        self.assertIn('crear-con-usuario', str(errores['role']))
        self.assertFalse(User.objects.filter(username='nuevopersonal').exists())

    def test_no_asigna_personal_a_cuenta_sin_vinculo(self):
        resp = self.client.post(
            self.url_change(self.cliente),
            self.payload_cambio(self.cliente, role='PERSONAL'),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('role', self.errores(resp))
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.role, User.Roles.CLIENTE)
        self.assertFalse(
            Profesional.objects.filter(usuario=self.cliente).exists()
        )

    def test_no_convierte_personal_en_cliente_con_vinculo(self):
        resp = self.client.post(
            self.url_change(self.personal),
            self.payload_cambio(self.personal, role='CLIENTE'),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('role', self.errores(resp))
        self.personal.refresh_from_db()
        self.assertEqual(self.personal.role, User.Roles.PERSONAL)
        # El vínculo queda intacto.
        self.profesional.refresh_from_db()
        self.assertEqual(self.profesional.usuario, self.personal)

    def test_no_convierte_personal_en_admin_con_vinculo(self):
        resp = self.client.post(
            self.url_change(self.personal),
            self.payload_cambio(self.personal, role='ADMIN'),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('role', self.errores(resp))
        self.personal.refresh_from_db()
        self.assertEqual(self.personal.role, User.Roles.PERSONAL)

    def test_edicion_valida_de_cliente_sin_vinculo_sigue_funcionando(self):
        # D3 no restringe transiciones de una cuenta sin vínculo: el form
        # solo bloquea lo que rompería el invariante.
        resp = self.client.post(
            self.url_change(self.cliente),
            self.payload_cambio(
                self.cliente, role='ADMIN', nombre='Cliente Editado',
            ),
        )
        self.assertEqual(resp.status_code, 302)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.role, User.Roles.ADMIN)
        self.assertEqual(self.cliente.nombre, 'Cliente Editado')

    def test_editar_personal_conservando_el_rol_no_se_bloquea(self):
        resp = self.client.post(
            self.url_change(self.personal),
            self.payload_cambio(self.personal, role='PERSONAL', nombre='Pro D3 Edited'),
        )
        self.assertEqual(resp.status_code, 302)
        self.personal.refresh_from_db()
        self.assertEqual(self.personal.role, User.Roles.PERSONAL)
        self.assertEqual(self.personal.nombre, 'Pro D3 Edited')
        self.profesional.refresh_from_db()
        self.assertEqual(self.profesional.usuario, self.personal)

    def test_editar_admin_vinculado_conservando_el_rol_no_se_bloquea(self):
        # B10.0.2: el no-op de guardar el mismo rol funciona también para
        # una cuenta ADMIN con Profesional vinculado (si no, el form no
        # podría ni guardarse sin demoverla).
        admin_vinc = User.objects.create_user(
            'adminvino', 'adminvino@test.com', 'AdminVinc123!',
            role=User.Roles.ADMIN,
        )
        Profesional.objects.create(nombre='Pro Admin', usuario=admin_vinc)
        resp = self.client.post(
            self.url_change(admin_vinc),
            self.payload_cambio(admin_vinc, role='ADMIN', nombre='Admin Editado'),
        )
        self.assertEqual(resp.status_code, 302)
        admin_vinc.refresh_from_db()
        self.assertEqual(admin_vinc.role, User.Roles.ADMIN)
        self.assertEqual(admin_vinc.nombre, 'Admin Editado')
