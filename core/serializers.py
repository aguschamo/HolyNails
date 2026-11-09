from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator
from django.db import IntegrityError, transaction
from django.utils import timezone
from datetime import time, datetime

from users.models import User
from users.serializers import RegisterSerializer

from .models import Servicio, Turno, Profesional, Disponibilidad

HORARIO_INICIO = time(9, 0)
HORARIO_FIN = time(20, 0)
GRANULARIDAD_MINUTOS = 15  # paso de generación de horarios disponibles


class ServicioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servicio
        fields = ('id', 'nombre', 'duracion', 'precio', 'is_active')


class ServicioPublicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servicio
        fields = ('id', 'nombre', 'duracion', 'precio')


class ProfesionalSerializer(serializers.ModelSerializer):
    """CRUD de profesionales con el invariante PERSONAL–Profesional (D3).

    - Vincular una cuenta CLIENTE la promueve a PERSONAL (una cuenta
      CLIENTE que gana vínculo pasa a ser la cuenta del trabajador);
      una cuenta ADMIN se puede vincular y **conserva su rol ADMIN**
      (no se demueve: perdería todos sus permisos administrativos).
    - Mientras exista un vínculo con una cuenta no se puede quitar ni
      reemplazar: el Personal conserva su Profesional (puede quedar
      inactivo, pero sigue vinculado).
    """

    class Meta:
        model = Profesional
        fields = ('id', 'nombre', 'usuario', 'is_active')

    def validate_usuario(self, value):
        """Un usuario no puede quedar vinculado a dos profesionales.

        Sin esta validación, el OneToOne violado se traduciría en un error
        500 en lugar de un 400. `value` puede ser None (desvincular).

        Además se preserva el invariante D3: el vínculo de un profesional
        que ya tiene cuenta es inmutable (no se quita ni se reemplaza), de
        modo que nunca queda una cuenta PERSONAL sin su Profesional. Solo
        se puede vincular una cuenta nueva desde ese estado.
        """
        if (
            self.instance is not None
            and self.instance.usuario_id
            and value != self.instance.usuario
        ):
            raise serializers.ValidationError(
                'No se puede quitar ni reemplazar la cuenta vinculada a '
                'este profesional: el vínculo se conserva mientras la '
                'cuenta exista. Desactivalo en lugar de modificar el '
                'vínculo.'
            )
        if value is None:
            return value
        vinculados = Profesional.objects.filter(usuario=value)
        if self.instance is not None:
            vinculados = vinculados.exclude(pk=self.instance.pk)
        if vinculados.exists():
            raise serializers.ValidationError(
                'Ese usuario ya está vinculado a otra profesional.'
            )
        return value

    def _promover_vinculado(self, usuario):
        """Toda cuenta vinculada pasa a PERSONAL (D3), salvo ADMIN.

        Una cuenta ADMIN que gana un Profesional conserva su rol: la
        demovería y perdería todos sus permisos administrativos (B10.0.2).
        Se ejecuta dentro de la misma transacción que el cambio de vínculo.
        """
        if usuario is None or usuario.role == User.Roles.ADMIN:
            return
        if usuario.role != User.Roles.PERSONAL:
            usuario.role = User.Roles.PERSONAL
            usuario.save(update_fields=['role'])

    def create(self, validated_data):
        with transaction.atomic():
            profesional = super().create(validated_data)
            self._promover_vinculado(validated_data.get('usuario'))
        return profesional

    def update(self, instance, validated_data):
        with transaction.atomic():
            profesional = super().update(instance, validated_data)
            self._promover_vinculado(profesional.usuario)
        return profesional


class ProfesionalConUsuarioSerializer(RegisterSerializer):
    """Alta administrativa: cuenta de usuario PERSONAL + registro Profesional.

    Crea la cuenta con el rol ``PERSONAL`` (D1/D3) y el registro
    ``Profesional`` vinculado dentro de una única transacción: si falla el
    vínculo, no queda creada una cuenta de usuario incompleta. Esta es la
    única vía de alta de PERSONAL, de modo que nunca existe un PERSONAL
    sin su Profesional.

    Reutiliza ``RegisterSerializer`` para validar username/email únicos y
    la contraseña con AUTH_PASSWORD_VALIDATORS.
    """

    nombre = serializers.CharField(max_length=150)
    nombre_profesional = serializers.CharField(max_length=150)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'nombre', 'nombre_profesional')

    def create(self, validated_data):
        nombre_profesional = validated_data.pop('nombre_profesional')
        try:
            with transaction.atomic():
                user = super().create(validated_data)
                user.role = User.Roles.PERSONAL
                user.save(update_fields=['role'])
                profesional = Profesional.objects.create(
                    usuario=user,
                    nombre=nombre_profesional,
                    is_active=True,
                )
        except IntegrityError:
            # La transacción ya revirtió la cuenta creada (si la hubo).
            raise serializers.ValidationError(
                'No se pudo crear el vínculo profesional. '
                'No se creó ninguna cuenta de usuario.'
            )
        return profesional


class DisponibilidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disponibilidad
        fields = ('id', 'profesional', 'fecha', 'hora_inicio', 'hora_fin')

    def validate_hora_inicio(self, value):
        if value and value < HORARIO_INICIO:
            raise serializers.ValidationError(
                f'La hora de inicio no puede ser anterior a {HORARIO_INICIO:%H:%M}.'
            )
        return value

    def validate_hora_fin(self, value):
        if value and value > HORARIO_FIN:
            raise serializers.ValidationError(
                f'La hora de fin no puede ser posterior a {HORARIO_FIN:%H:%M}.'
            )
        return value

    def validate(self, data):
        profesional = data.get('profesional') or getattr(self.instance, 'profesional', None)
        fecha = data.get('fecha') or getattr(self.instance, 'fecha', None)
        hora_inicio = data.get('hora_inicio') or getattr(self.instance, 'hora_inicio', None)
        hora_fin = data.get('hora_fin') or getattr(self.instance, 'hora_fin', None)

        # El pasado es de solo lectura: no se crean disponibilidades en
        # fechas anteriores a hoy ni se mueven existentes a ellas. (La
        # edición de una disponibilidad histórica se rechaza además en la
        # vista, aunque el cambio apunte a una fecha futura.)
        if fecha and fecha < timezone.localdate():
            raise serializers.ValidationError(
                'La fecha de la disponibilidad no puede ser anterior a hoy.'
            )

        if hora_inicio and hora_fin and hora_inicio >= hora_fin:
            raise serializers.ValidationError(
                'La hora de inicio debe ser anterior a la hora de fin.'
            )

        # No solaparse con otras disponibilidades del mismo profesional/fecha.
        if profesional and fecha and hora_inicio and hora_fin:
            qs = Disponibilidad.objects.filter(
                profesional=profesional, fecha=fecha
            ).exclude(pk=self.instance.pk if self.instance else None)
            for d in qs:
                if hora_inicio < d.hora_fin and d.hora_inicio < hora_fin:
                    raise serializers.ValidationError(
                        'Se superpone con otra disponibilidad existente para este profesional y fecha.'
                    )
        return data


class TurnoSerializer(serializers.ModelSerializer):
    # Nombre visible de la clienta: el panel de administración necesita
    # identificar y buscar por nombre (B10.1), pero no existe un endpoint
    # de usuarios accesible para una cuenta ADMIN sin ``is_staff``
    # (``UserViewSet`` exige ``IsAdminUser``). Se expone de solo lectura
    # sin tocar el campo ``usuario`` (id), que consumen otros flujos.
    usuario_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Turno
        fields = (
            'id', 'fecha', 'hora', 'usuario', 'usuario_nombre',
            'servicio', 'profesional', 'estado',
        )
        read_only_fields = ('usuario', 'estado', 'usuario_nombre')

    def get_usuario_nombre(self, obj):
        """Nombre de la cuenta del turno (``User.__str__``: nombre o username)."""
        usuario = getattr(obj, 'usuario', None)
        if usuario is None:
            return None
        return usuario.nombre or usuario.username

    def get_unique_together_validators(self):
        """Restricción única sobre turnos ACTIVOS (pendiente/confirmado).

        El modelo define la constraint con ``condition`` (índice único
        parcial). El validador automático que DRF deriva de ella exige
        ``condition_fields=('estado',)``, pero ``estado`` es de solo
        lectura: nunca llega a ``attrs`` y ``enforce_required_fields``
        rechazaría todo el alta con «Este campo es requerido».

        Se sustituye por un ``UniqueTogetherValidator`` equivalente cuyo
        queryset base ya viene filtrado a activos: sin ``condition`` no
        hay ``condition_fields`` (no se exige ``estado``), el mensaje de
        error por defecto es idéntico al actual («…deben formar un
        conjunto único») y la semántica coincide con la de la constraint
        de BD: solo dos turnos activos compiten por el mismo
        (profesional, fecha, hora); los cancelados quedan fuera de la
        consulta y liberan el horario.

        Este método se usa únicamente para construir los validadores;
        ``Meta.validators`` sigue sin declararse, de modo que
        ``get_uniqueness_extra_kwargs()`` conserva su comportamiento
        habitual (B1 intacto, p. ej. ``profesional`` con
        ``default=None``).
        """
        return [
            UniqueTogetherValidator(
                queryset=Turno.objects.filter(
                    estado__in=[
                        Turno.Estado.PENDIENTE,
                        Turno.Estado.CONFIRMADO,
                    ]
                ),
                fields=('profesional', 'fecha', 'hora'),
            )
        ]

    def validate(self, data):
        fecha = data.get('fecha') or getattr(self.instance, 'fecha', None)
        hora = data.get('hora') or getattr(self.instance, 'hora', None)
        profesional = data.get('profesional') or getattr(self.instance, 'profesional', None)
        servicio = data.get('servicio') or getattr(self.instance, 'servicio', None)

        # Fecha no pasada.
        if fecha and fecha < timezone.localdate():
            raise serializers.ValidationError(
                'La fecha del turno no puede ser anterior a hoy.'
            )

        # Hora dentro del horario de atención.
        if hora and not (HORARIO_INICIO <= hora <= HORARIO_FIN):
            raise serializers.ValidationError(
                f'El horario debe estar entre las {HORARIO_INICIO:%H:%M} y las {HORARIO_FIN:%H:%M}.'
            )

        # A4 — intervalos de 15 minutos: la grilla de horarios disponibles
        # se genera con paso GRANULARIDAD_MINUTOS, así que una hora fuera
        # de grilla no corresponde a ningún cupo. Se valida en el backend
        # (serializer), cubriendo toda escritura de turnos vía API, sin
        # redondeos automáticos: el valor se rechaza tal cual llegó.
        if hora and (
            hora.minute % GRANULARIDAD_MINUTOS != 0
            or hora.second != 0
            or hora.microsecond != 0
        ):
            raise serializers.ValidationError(
                'El horario de inicio debe respetar intervalos de 15 minutos '
                '(minutos 00, 15, 30 o 45).'
            )

        # Profesional obligatorio en toda reserva nueva. Los turnos
        # históricos sin profesional siguen existiendo y siendo consultables:
        # esta validación solo corre en el alta vía API (los registros
        # antiguos no se migran ni se modifican).
        if not profesional:
            raise serializers.ValidationError('Debe seleccionar un profesional.')

        if not profesional.is_active:
            raise serializers.ValidationError(
                'El profesional seleccionado no está activo.'
            )

        # El servicio debe existir para calcular la duración.
        if not servicio:
            raise serializers.ValidationError('Debe seleccionar un servicio.')

        # No se permite reservar con servicios inactivos, aunque el cliente
        # envíe directamente el ID del servicio.
        if not servicio.is_active:
            raise serializers.ValidationError(
                'El servicio seleccionado está inactivo.'
            )

        # La duración completa del servicio no puede cruzar la medianoche:
        # con fin calculado sobre datetime completo no se trunca como con .time().
        if fecha and hora:
            fin_turno = datetime.combine(fecha, hora) + servicio.duracion
            if fin_turno.date() > fecha:
                raise serializers.ValidationError(
                    'La duración del servicio no puede cruzar la medianoche.'
                )

        return data
