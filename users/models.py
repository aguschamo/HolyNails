import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


def ruta_foto_perfil(instance, filename):
    """Ruta de almacenamiento de la foto de perfil (B11.2).

    Nombre generado por el backend: nunca se usa el nombre que envía el
    usuario (evita rutas manipulables y colisiones). El sufijo aleatorio
    garantiza unicidad aunque dos subidas lleguen en el mismo instante y
    permite reemplazar fotos sin pisar archivos de otros usuarios. La
    extensión la fija el backend según el formato detectado por Pillow.
    """
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'jpg'
    return f'perfiles/user_{instance.pk}_{uuid.uuid4().hex}.{ext}'


class User(AbstractUser):
    class Roles(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        CLIENTE = 'CLIENTE', 'Cliente'
        PERSONAL = 'PERSONAL', 'Personal'

    nombre = models.CharField(max_length=150, blank=True, default='')
    # B11.1: teléfono de contacto editable desde el perfil. blank/default
    # '' para que la migración no requiera datos previos: los usuarios
    # existentes quedan compatibles sin migración de datos.
    telefono = models.CharField(max_length=30, blank=True, default='')
    # B11.2: foto de perfil persistente (almacenamiento local en MEDIA_ROOT,
    # carpeta perfiles/). '' = sin foto; blank/default compatibles con los
    # usuarios existentes sin migración de datos.
    foto = models.ImageField(upload_to=ruta_foto_perfil, blank=True, default='')
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.CLIENTE)

    def __str__(self):
        return self.nombre or self.username
