"""B9 — modelo definitivo de roles: VENDEDOR -> PERSONAL.

Dos movimientos (R1):

1. Opciones del campo ``role``: se retira ``VENDEDOR`` y se agrega
   ``PERSONAL`` (ADMIN y CLIENTE se conservan).
2. Datos:
   - todos los usuarios ``VENDEDOR`` pasan a ``PERSONAL``;
   - los usuarios ``CLIENTE`` que tengan un ``Profesional`` vinculado
     pasan a ``PERSONAL`` (son las cuentas de trabajadoras/es);
   - los ``CLIENTE`` sin vínculo no se modifican.

Reversibilidad razonable (no bit a bit): al revertir, un ``PERSONAL``
con Profesional vinculado vuelve a ``CLIENTE`` (el estado previo de los
CLIENTE vinculados) y un ``PERSONAL`` sin vínculo vuelve a ``VENDEDOR``
(los VENDEDOR no tenían Profesional). La ambigüedad solo afecta a casos
límite (un VENDEDOR que hubiera tenido vínculo).

La migración NO se aplica en esta etapa: solo se crea y se valida su
sintaxis y su lugar en el grafo de migraciones.
"""

from django.db import migrations, models


def forwards(apps, schema_editor):
    User = apps.get_model('users', 'User')
    Profesional = apps.get_model('core', 'Profesional')

    vinculados = set(
        Profesional.objects.exclude(usuario=None).values_list(
            'usuario_id', flat=True
        )
    )
    User.objects.filter(role='VENDEDOR').update(role='PERSONAL')
    User.objects.filter(role='CLIENTE', pk__in=vinculados).update(
        role='PERSONAL'
    )


def backwards(apps, schema_editor):
    User = apps.get_model('users', 'User')
    Profesional = apps.get_model('core', 'Profesional')

    vinculados = set(
        Profesional.objects.exclude(usuario=None).values_list(
            'usuario_id', flat=True
        )
    )
    User.objects.filter(role='PERSONAL', pk__in=vinculados).update(
        role='CLIENTE'
    )
    User.objects.filter(role='PERSONAL').exclude(pk__in=vinculados).update(
        role='VENDEDOR'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_disponibilidad_profesional_and_more'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('ADMIN', 'Admin'),
                    ('CLIENTE', 'Cliente'),
                    ('PERSONAL', 'Personal'),
                ],
                default='CLIENTE',
                max_length=20,
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
