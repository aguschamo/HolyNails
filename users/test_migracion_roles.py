"""B9.1 — verificación de la migración de roles con datos de prueba.

Ejecuta las funciones ``forwards``/``backwards`` de
``users/migrations/0002_role_personal.py`` sobre la base aislada de tests
(SQLite en memoria de la suite de Django), sin ejecutar ``migrate`` sobre
la base de desarrollo ni tocar datos reales:

- ``VENDEDOR`` se convierte en ``PERSONAL``;
- ``CLIENTE`` con ``Profesional`` vinculado se convierte en ``PERSONAL``;
- ``CLIENTE`` sin ``Profesional`` permanece ``CLIENTE``;
- la reversión sigue la heurística documentada en la migración
  (``PERSONAL`` con vínculo -> ``CLIENTE``; ``PERSONAL`` sin vínculo ->
  ``VENDEDOR``).

Se importa el módulo de la migración por nombre (empieza con dígito) y se
le pasa ``django.apps.apps``, que implementa ``get_model`` — la misma
interfaz del ``apps`` de migraciones — sobre los modelos ya migrados de
la BD de tests. Los datos de ``role`` no se validan contra choices al
guardar (igual que al ejecutar la migración real), por lo que se puede
simular una base previa con ``VENDEDOR``.
"""

import importlib

from django.apps import apps as django_apps
from django.test import TestCase

from core.models import Profesional
from users.models import User

migracion = importlib.import_module('users.migrations.0002_role_personal')


class MigracionRolesDatosTests(TestCase):
    """La migración de datos convierte los roles según R1 y revierte."""

    def setUp(self):
        # Base previa a la migración (choices antiguos: VENDEDOR existía).
        self.vendedor = User.objects.create_user(
            username='vend', email='vend@test.com', password='pass1234',
            role='VENDEDOR',
        )
        self.cliente_vinculado = User.objects.create_user(
            username='clienteconpro', email='ccp@test.com',
            password='pass1234', role=User.Roles.CLIENTE,
        )
        self.profesional = Profesional.objects.create(
            nombre='Pro Migracion', usuario=self.cliente_vinculado,
        )
        self.cliente_libre = User.objects.create_user(
            username='clientelibre', email='cl@test.com',
            password='pass1234', role=User.Roles.CLIENTE,
        )

    def roles(self):
        return {
            'vendedor': User.objects.get(pk=self.vendedor.pk).role,
            'cliente_vinculado': User.objects.get(
                pk=self.cliente_vinculado.pk
            ).role,
            'cliente_libre': User.objects.get(pk=self.cliente_libre.pk).role,
        }

    def test_forwards_aplica_r1(self):
        migracion.forwards(django_apps, None)

        self.assertEqual(self.roles(), {
            'vendedor': User.Roles.PERSONAL,          # VENDEDOR -> PERSONAL
            'cliente_vinculado': User.Roles.PERSONAL,  # CLIENTE con vínculo
            'cliente_libre': User.Roles.CLIENTE,       # CLIENTE intacto
        })
        # El vínculo existente no se toca.
        self.profesional.refresh_from_db()
        self.assertEqual(self.profesional.usuario_id, self.cliente_vinculado.pk)

    def test_backwards_sigue_la_heuristica_documentada(self):
        migracion.forwards(django_apps, None)
        migracion.backwards(django_apps, None)

        self.assertEqual(self.roles(), {
            # PERSONAL con Profesional vinculado vuelve a CLIENTE...
            # ...y sin vínculo, a VENDEDOR (rol previo a la migración).
            'vendedor': 'VENDEDOR',
            'cliente_vinculado': User.Roles.CLIENTE,
            'cliente_libre': User.Roles.CLIENTE,  # nunca se tocó
        })
        self.profesional.refresh_from_db()
        self.assertEqual(self.profesional.usuario_id, self.cliente_vinculado.pk)

    def test_backwards_personal_sin_vinculo_directo_vuelve_a_vendedor(self):
        # Caso límite documentado: un PERSONAL sin vínculo que no provenga
        # del forward de un CLIENTE (p. ej. un VENDEDOR previo) revierte a
        # VENDEDOR, no a CLIENTE.
        User.objects.create_user(
            username='personalsinpro', email='psp@test.com',
            password='pass1234', role=User.Roles.PERSONAL,
        )
        migracion.backwards(django_apps, None)

        self.assertEqual(
            User.objects.get(username='personalsinpro').role,
            'VENDEDOR',
        )
