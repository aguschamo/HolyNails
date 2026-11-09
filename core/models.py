from datetime import time, datetime, timedelta

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Servicio(models.Model):
    nombre = models.CharField(max_length=100)
    duracion = models.DurationField(validators=[MinValueValidator(timedelta(minutes=1))])
    precio = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} {'(Inactivo)' if not self.is_active else ''}"


class Profesional(models.Model):
    """Manicura/profesional que atiende turnos.

    Se vincula opcionalmente a un ``User`` del sistema para que pueda
    autenticarse y gestionar su propia disponibilidad, sin duplicar el
    modelo de usuarios ni crear credenciales paralelas.
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='profesional',
    )
    nombre = models.CharField(max_length=150, blank=True, default='')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        if self.nombre:
            return self.nombre
        if self.usuario:
            return self.usuario.username
        return 'Profesional sin nombre'


class Disponibilidad(models.Model):
    """Intervalo de trabajo de un profesional en una fecha dada.

    Un profesional puede tener varios intervalos en un mismo día
    (ej. 09:00-13:00 y 15:00-19:00).
    """

    profesional = models.ForeignKey(
        Profesional,
        on_delete=models.CASCADE,
        related_name='disponibilidades',
    )
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['profesional', 'fecha', 'hora_inicio'],
                name='unique_disponibilidad_profesional_fecha_hora_inicio',
            ),
        ]

    def clean(self):
        if self.hora_inicio and self.hora_fin and self.hora_inicio >= self.hora_fin:
            raise ValidationError('La hora de inicio debe ser anterior a la hora de fin.')
        if self.hora_inicio and self.hora_inicio < HORARIO_INICIO:
            raise ValidationError(f'La hora de inicio no puede ser anterior a {HORARIO_INICIO:%H:%M}.')
        if self.hora_fin and self.hora_fin > HORARIO_FIN:
            raise ValidationError(f'La hora de fin no puede ser posterior a {HORARIO_FIN:%H:%M}.')
        self._validar_no_solapamiento()

    def _validar_no_solapamiento(self):
        qs = Disponibilidad.objects.filter(
            profesional=self.profesional, fecha=self.fecha
        ).exclude(pk=self.pk)
        for d in qs:
            if self.hora_inicio < d.hora_fin and d.hora_inicio < self.hora_fin:
                raise ValidationError(
                    'Se superpone con otra disponibilidad existente para este profesional y fecha.'
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.profesional} {self.fecha} {self.hora_inicio}-{self.hora_fin}'


class Turno(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        CONFIRMADO = 'confirmado', 'Confirmado'
        CANCELADO = 'cancelado', 'Cancelado'

    fecha = models.DateField()
    hora = models.TimeField()
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='turnos'
    )
    profesional = models.ForeignKey(
        Profesional,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='turnos',
        help_text='Profesional que atiende el turno. Los turnos legacy pueden no tenerlo.',
    )
    servicio = models.ForeignKey(
        Servicio, on_delete=models.SET_NULL, null=True, related_name='turnos'
    )
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)

    class Meta:
        constraints = [
            # Unicidad solo entre turnos ACTIVOS (pendiente/confirmado):
            # un turno cancelado libera su (profesional, fecha, hora) para una
            # nueva reserva, pero se conserva en el historial. El índice único
            # parcial cubre solo las filas activas, de modo que dos turnos
            # pendientes/confirmados jamás ocupen el mismo horario. La
            # condición replica el mismo filtro "activo" que usan las vistas
            # (disponibles, solape en create y cobertura de disponibilidades).
            models.UniqueConstraint(
                fields=['profesional', 'fecha', 'hora'],
                name='unique_turno_activo_profesional_fecha_hora',
                condition=models.Q(
                    estado__in=['pendiente', 'confirmado']
                ),
            ),
        ]

    def __str__(self):
        return f"{self.fecha} {self.hora} - {self.usuario}"

    def intervalo(self):
        """Devuelve (inicio, fin) como datetimes, o None si no hay servicio/duración."""
        if not self.servicio or not self.servicio.duracion:
            return None
        inicio = datetime.combine(self.fecha, self.hora)
        fin = inicio + self.servicio.duracion
        return inicio, fin


def disponibilidad_cubre_turno(disponibilidad, turno):
    """Indica si el intervalo de ``disponibilidad`` cubre completamente el de ``turno``."""
    if not turno.servicio or not turno.servicio.duracion:
        return True
    t_inicio, t_fin = turno.intervalo()
    d_inicio = datetime.combine(disponibilidad.fecha, disponibilidad.hora_inicio)
    d_fin = datetime.combine(disponibilidad.fecha, disponibilidad.hora_fin)
    return t_inicio >= d_inicio and t_fin <= d_fin


def intervalos_se_solapan(inicio_a, fin_a, inicio_b, fin_b):
    """Devuelve True si los dos intervalos [inicio, fin) se solapan."""
    return inicio_a < fin_b and inicio_b < fin_a


# Rangos de horario compartidos (se reutilizan en serializers y views).
HORARIO_INICIO = timezone.datetime.min.time().replace(hour=9)
HORARIO_FIN = timezone.datetime.min.time().replace(hour=20)

from django.core.exceptions import ValidationError  # noqa: E402
