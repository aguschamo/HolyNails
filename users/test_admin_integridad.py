"""Etapa B4 — integridad del Django Admin (users).

Verifica que el panel administrativo de usuarios:

- exija acceso autenticado con permisos (anonimos y no-staff rechazados);
- impida eliminar usuarios con turnos (historial protegido, incluidos
  los cancelados) y permita eliminar los que no tienen;
- no exponga la acción de eliminación múltiple por defecto;
- conserve el manejo estándar y seguro de contraseñas de Django
  (hash de solo lectura, formulario dedicado, validators).

Tests nuevos (no reemplazan ni modifican los existentes).
"""

from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Turno

User = get_user_model()


class AccesoAdminUsersTests(TestCase):
    """Acceso y permisos sobre el admin de usuarios."""

    def test_anonimo_redirige_al_login(self):
        resp = self.client.get(reverse('admin:users_user_changelist'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/admin/login/', resp.url)

    def test_usuario_sin_staff_no_tiene_acceso(self):
        User.objects.create_user('normal', 'n@test.com', 'NormalPass123!')
        self.client.force_login(User.objects.get(username='normal'))
        resp = self.client.get(reverse('admin:users_user_changelist'))
        # Sin is_staff Django redirige al login del admin (no al panel).
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/admin/login/', resp.url)


class EliminacionUsuarioTests(TestCase):
    """La eliminación de usuarios respeta los turnos asociados."""

    def setUp(self):
        self.root = User.objects.create_superuser(
            'root', 'root@test.com', 'RootPass123!'
        )
        self.client.force_login(self.root)
        self.cliente = User.objects.create_user(
            'cliente', 'cliente@test.com', 'ClientePass123!'
        )

    def crear_turno(self, estado='pendiente'):
        return Turno.objects.create(
            fecha=timezone.localdate() + timedelta(days=1),
            hora=time(9, 0),
            usuario=self.cliente,
            estado=estado,
        )

    def test_no_eliminar_usuario_con_turnos(self):
        # Incluye turnos cancelados: el historial se conserva.
        self.crear_turno(estado='cancelado')
        url = reverse('admin:users_user_delete', args=[self.cliente.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.post(url, {'post': 'yes'}).status_code, 403
        )
        self.assertTrue(User.objects.filter(pk=self.cliente.pk).exists())
        self.assertEqual(Turno.objects.count(), 1)

    def test_eliminar_usuario_sin_turnos_permitido(self):
        libre = User.objects.create_user('libre', 'l@test.com', 'LibrePass123!')
        url = reverse('admin:users_user_delete', args=[libre.pk])
        self.assertEqual(
            self.client.post(url, {'post': 'yes'}).status_code, 302
        )
        self.assertFalse(User.objects.filter(pk=libre.pk).exists())

    def test_accion_eliminar_multiple_no_disponible(self):
        # Sin acciones registradas el changelist ni procesa el POST de
        # acción: la solicitud directa queda sin efecto (200) y nada se
        # borra.
        self.crear_turno()
        resp = self.client.post(
            reverse('admin:users_user_changelist'),
            {
                'action': 'delete_selected',
                '_selected_action': [str(self.cliente.pk)],
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.cliente.pk).exists())


class PasswordAdminTests(TestCase):
    """Las contraseñas conservan el manejo estándar de Django."""

    def setUp(self):
        self.root = User.objects.create_superuser(
            'root', 'root@test.com', 'RootPass123!'
        )
        self.client.force_login(self.root)
        self.cliente = User.objects.create_user(
            'cliente', 'cliente@test.com', 'ClientePass123!'
        )

    def test_alta_con_password_guarda_solo_el_hash(self):
        resp = self.client.post(
            reverse('admin:users_user_add'),
            {
                'username': 'nuevo',
                'password1': 'NuevaClave123!',
                'password2': 'NuevaClave123!',
                'email': 'nuevo@test.com',
                'nombre': 'Nuevo',
                'role': 'CLIENTE',
                'is_active': 'on',
                'is_staff': '',
                'is_superuser': '',
            },
        )
        self.assertEqual(resp.status_code, 302)
        nuevo = User.objects.get(username='nuevo')
        self.assertTrue(nuevo.check_password('NuevaClave123!'))
        self.assertNotIn('NuevaClave123!', nuevo.password)

    def test_pagina_de_cambio_no_expone_password_en_texto(self):
        resp = self.client.get(
            reverse('admin:users_user_change', args=[self.cliente.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'ClientePass123!')
        self.assertContains(resp, '**************')

    def test_formulario_de_password_valida_con_estandar_de_django(self):
        # Nombre de URL heredado de Django (UserAdmin.get_urls).
        url = reverse(
            'admin:auth_user_password_change', args=[self.cliente.pk]
        )
        # Contraseña demasiado corta (MinimumLengthValidator) → 200 con error.
        resp = self.client.post(
            url, {'password1': 'abc', 'password2': 'abc'}
        )
        self.assertEqual(resp.status_code, 200)
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.check_password('ClientePass123!'))

    def test_cambio_de_password_valido_se_aplica(self):
        url = reverse(
            'admin:auth_user_password_change', args=[self.cliente.pk]
        )
        resp = self.client.post(
            url, {'password1': 'NuevaClave123!', 'password2': 'NuevaClave123!'}
        )
        self.assertEqual(resp.status_code, 302)
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.check_password('NuevaClave123!'))
