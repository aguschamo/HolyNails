from datetime import datetime

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from .models import (
    Servicio,
    Turno,
    Profesional,
    Disponibilidad,
    HORARIO_INICIO,
    HORARIO_FIN,
    disponibilidad_cubre_turno,
    intervalos_se_solapan,
)
from .serializers import GRANULARIDAD_MINUTOS
from .views import _turno_ya_comenzo

# Estados que ocupan horario: los turnos cancelados liberan su
# (profesional, fecha, hora). Misma definición que la de las vistas y que
# la restricción única condicional de B3.1.
_ESTADOS_ACTIVOS = (Turno.Estado.PENDIENTE, Turno.Estado.CONFIRMADO)


class TurnoAdminForm(forms.ModelForm):
    """Formulario administrativo de turnos con las reglas de negocio.

    Reproduce en el admin las validaciones de la API sin tocar los
    ViewSets:

    - los turnos que ya comenzaron son de solo lectura (cualquier guardado
      se rechaza, comparando la fecha y hora originales del registro);
    - fecha y hora futuras, hora dentro del horario de atención;
    - servicio y profesional presentes y activos;
    - la duración no puede cruzar la medianoche;
    - el turno completo debe caber en una franja de disponibilidad;
    - sin solapamiento con otros turnos activos, excluyendo el propio
      turno.

    ``estado`` no participa del formulario (se declara de solo lectura en
    ``TurnoAdmin``): un turno nuevo nace ``pendiente`` y una edición no
    puede alterar el estado por esta vía.
    """

    class Meta:
        model = Turno
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # El modelo permite turnos legacy sin profesional (SET_NULL), pero
        # un turno sin profesional queda fuera de toda comprobación de
        # solape y cobertura: en el admin es obligatorio asignarlo (misma
        # exigencia que la creación de reservas por API).
        self.fields['profesional'].required = True

    def clean(self):
        cleaned_data = super().clean()

        # Edición de un turno que ya comenzó: rechazada sin importar qué
        # campo se haya tocado (se leen las fecha y hora ORIGINALES del
        # registro, previas a la edición).
        if self.instance.pk and _turno_ya_comenzo(
            self.instance.fecha, self.instance.hora
        ):
            raise forms.ValidationError(
                'Este turno ya comenzó: los turnos iniciados son de solo lectura.'
            )

        fecha = cleaned_data.get('fecha')
        hora = cleaned_data.get('hora')
        servicio = cleaned_data.get('servicio')
        profesional = cleaned_data.get('profesional')

        # Si falta un campo requerido, su propio error de campo ya se
        # informa; no se continúa con las comprobaciones que lo dependen.
        if not (fecha and hora and servicio and profesional):
            return cleaned_data

        if _turno_ya_comenzo(fecha, hora):
            raise forms.ValidationError(
                'La fecha y la hora del turno deben ser futuras. '
                'Elegí un horario posterior al actual.'
            )

        if not (HORARIO_INICIO <= hora <= HORARIO_FIN):
            raise forms.ValidationError(
                f'El horario del turno debe estar entre las '
                f'{HORARIO_INICIO:%H:%M} y las {HORARIO_FIN:%H:%M}.'
            )

        # A4 — intervalos de 15 minutos: misma regla que la API
        # (TurnoSerializer.validate), aplicada también al camino de
        # escritura del admin Django. Sin redondeos: se rechaza la hora
        # fuera de grilla.
        if (
            hora.minute % GRANULARIDAD_MINUTOS != 0
            or hora.second != 0
            or hora.microsecond != 0
        ):
            raise forms.ValidationError(
                'El horario del turno debe respetar intervalos de 15 minutos '
                '(minutos 00, 15, 30 o 45).'
            )

        if not profesional.is_active:
            raise forms.ValidationError(
                'El profesional seleccionado no está activo.'
            )

        if not servicio.is_active:
            raise forms.ValidationError(
                'El servicio seleccionado está inactivo.'
            )

        inicio = datetime.combine(fecha, hora)
        fin = inicio + servicio.duracion
        if fin.date() > fecha:
            raise forms.ValidationError(
                'La duración del servicio no puede cruzar la medianoche.'
            )

        # El turno completo debe caber en UNA franja de disponibilidad
        # (misma regla y misma función que la creación de reservas por API).
        turno_en_evaluacion = Turno(
            fecha=fecha, hora=hora, servicio=servicio, profesional=profesional,
        )
        cubierto = any(
            disponibilidad_cubre_turno(franja, turno_en_evaluacion)
            for franja in Disponibilidad.objects.filter(
                profesional=profesional, fecha=fecha
            )
        )
        if not cubierto:
            raise forms.ValidationError(
                'El horario del turno no está dentro de la disponibilidad '
                'del profesional.'
            )

        # Sin solapamiento con otros turnos activos del mismo profesional
        # y fecha; el propio turno queda excluido para que una edición que
        # conserve su horario no se rechace a sí misma.
        turnos = Turno.objects.filter(
            profesional=profesional, fecha=fecha, estado__in=_ESTADOS_ACTIVOS,
        )
        if self.instance.pk:
            turnos = turnos.exclude(pk=self.instance.pk)
        for otro in turnos:
            if not otro.servicio or not otro.servicio.duracion:
                continue
            otro_inicio, otro_fin = otro.intervalo()
            if intervalos_se_solapan(inicio, fin, otro_inicio, otro_fin):
                raise forms.ValidationError(
                    'El profesional ya tiene un turno que se superpone con '
                    'ese horario.'
                )

        return cleaned_data


@admin.register(Turno)
class TurnoAdmin(admin.ModelAdmin):
    """Turnos: formulario validado, transiciones por acciones, sin borrado.

    - ``estado`` es de solo lectura en el formulario: las transiciones
      únicas posibles son las acciones explícitas ``confirmar_turnos`` y
      ``cancelar_turnos``, que respetan las mismas reglas que la API
      (pendiente → confirmado; pendiente/confirmado → cancelado) y
      rechazan los turnos que ya comenzaron.
    - La eliminación está deshabilitada (interfaz y solicitudes
      directas): el historial de turnos, incluidos los cancelados, se
      conserva.
    """

    form = TurnoAdminForm
    list_display = ('fecha', 'hora', 'usuario', 'servicio', 'profesional', 'estado')
    list_filter = ('estado', 'fecha', 'profesional')
    search_fields = ('usuario__nombre',)
    readonly_fields = ('estado',)
    actions = ('confirmar_turnos', 'cancelar_turnos')

    def has_delete_permission(self, request, obj=None):
        # El historial de turnos es inmutable desde el panel: con permiso
        # falso tampoco queda registrada la acción "eliminar" en el
        # changelist ni es posible enviar la eliminación directamente.
        return False

    @admin.action(description='Confirmar los turnos seleccionados')
    def confirmar_turnos(self, request, queryset):
        self._transicionar_con_accion(
            request, queryset, Turno.Estado.CONFIRMADO, 'confirmado'
        )

    @admin.action(description='Cancelar los turnos seleccionados')
    def cancelar_turnos(self, request, queryset):
        self._transicionar_con_accion(
            request, queryset, Turno.Estado.CANCELADO, 'cancelado'
        )

    def _transicionar_con_accion(self, request, queryset, nuevo_estado, texto):
        """Aplica la transición turno por turno, informando cada resultado.

        No se usa un ``update()`` masivo: cada fila se relee con bloqueo
        dentro de su propia transacción y se valida individualmente con
        las mismas reglas de la API (etapa de transiciones): el turno no
        puede haber comenzado, confirmar exige estado ``pendiente`` y
        cancelar exige ``pendiente`` o ``confirmado``. Los turnos
        rechazados no se modifican y se reportan con mensajes de Django.
        """
        aplicados = 0
        rechazados = 0
        for turno_id in queryset.values_list('pk', flat=True):
            with transaction.atomic():
                turno = Turno.objects.select_for_update().get(pk=turno_id)
                motivo = self._motivo_rechazo_transicion(turno, nuevo_estado)
                if motivo:
                    rechazados += 1
                    self.message_user(
                        request,
                        f'Turno {turno.fecha} {turno.hora:%H:%M}: {motivo}',
                        level=messages.WARNING,
                    )
                    continue
                turno.estado = nuevo_estado
                turno.save(update_fields=['estado'])
                aplicados += 1
                self.message_user(
                    request,
                    f'Turno {turno.fecha} {turno.hora:%H:%M}: {texto}.',
                    level=messages.SUCCESS,
                )
        self.message_user(
            request,
            f'Resumen: {aplicados} turno(s) actualizado(s), '
            f'{rechazados} rechazado(s).',
            level=messages.SUCCESS if aplicados else messages.WARNING,
        )

    @staticmethod
    def _motivo_rechazo_transicion(turno, nuevo_estado):
        """Motivo de rechazo de la transición, o ``None`` si corresponde.

        Réplica de las reglas de ``TurnoViewSet._transicionar_estado``
        (turno no comenzado; confirmar solo desde pendiente; cancelar
        desde pendiente o confirmado, nunca dos veces).
        """
        if _turno_ya_comenzo(turno.fecha, turno.hora):
            return 'no se puede cambiar el estado de un turno que ya comenzó.'
        if nuevo_estado == Turno.Estado.CONFIRMADO:
            if turno.estado != Turno.Estado.PENDIENTE:
                return 'solo se pueden confirmar turnos pendientes.'
        elif turno.estado == Turno.Estado.CANCELADO:
            return 'ya está cancelado; no se puede volver a cancelar.'
        return None


class DisponibilidadAdminForm(forms.ModelForm):
    """Formulario administrativo de disponibilidades.

    Mantiene las validaciones de modelo (solape, rangos de horario,
    constraint única) y agrega las reglas de la API que el modelo no
    cubre: fechas no pasadas, profesional inamovible y cobertura de los
    turnos futuros activos del día de origen y del destino.
    """

    class Meta:
        model = Disponibilidad
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()

        profesional = cleaned_data.get('profesional')
        fecha = cleaned_data.get('fecha')
        hora_inicio = cleaned_data.get('hora_inicio')
        hora_fin = cleaned_data.get('hora_fin')

        # El pasado es de solo lectura: no se crean franjas históricas
        # (la edición de franjas pasadas se bloquea además en
        # ``has_change_permission``).
        if fecha and fecha < timezone.localdate():
            raise forms.ValidationError(
                'La fecha de la disponibilidad no puede ser anterior a hoy.'
            )

        if not (profesional and fecha and hora_inicio and hora_fin):
            return cleaned_data

        # El profesional de una franja existente no cambia (misma regla
        # que la API).
        if self.instance.pk and profesional.pk != self.instance.profesional_id:
            raise forms.ValidationError(
                'No se puede cambiar el profesional de una disponibilidad '
                'existente.'
            )

        # Solo las modificaciones (no las altas) pueden dejar turnos sin
        # cobertura: se valida el día DESTINO con la franja en su estado
        # final y, si la franja cambia de fecha, también el día ORIGEN
        # (donde esta franja ya no estará).
        if self.instance.pk:
            franja_final = Disponibilidad(
                profesional=profesional, fecha=fecha,
                hora_inicio=hora_inicio, hora_fin=hora_fin,
            )
            otras_destino = Disponibilidad.objects.filter(
                profesional=profesional, fecha=fecha,
            ).exclude(pk=self.instance.pk)
            self._exigir_cobertura(
                profesional, fecha, list(otras_destino) + [franja_final]
            )

            if fecha != self.instance.fecha:
                otras_origen = Disponibilidad.objects.filter(
                    profesional=self.instance.profesional_id,
                    fecha=self.instance.fecha,
                ).exclude(pk=self.instance.pk)
                self._exigir_cobertura(
                    self.instance.profesional,
                    self.instance.fecha,
                    list(otras_origen),
                )

        return cleaned_data

    @staticmethod
    def _exigir_cobertura(profesional, fecha, franjas):
        """Todo turno futuro activo del día debe caber en una franja."""
        turnos = Turno.objects.filter(
            profesional=profesional, fecha=fecha, estado__in=_ESTADOS_ACTIVOS,
        )
        for turno in turnos:
            if _turno_ya_comenzo(turno.fecha, turno.hora):
                continue
            if not any(
                disponibilidad_cubre_turno(franja, turno)
                for franja in franjas
            ):
                raise forms.ValidationError(
                    f'No se puede modificar: quedaría sin cobertura el turno '
                    f'del {turno.fecha} a las {turno.hora:%H:%M} (pendiente '
                    f'o confirmado).'
                )


@admin.register(Disponibilidad)
class DisponibilidadAdmin(admin.ModelAdmin):
    """Disponibilidades: pasado de solo lectura y cobertura garantizada.

    - Las franjas de fechas pasadas se pueden ver pero no editar ni
      eliminar (``has_change_permission``/``has_delete_permission`` por
      objeto; las solicitudes directas reciben 403).
    - Ninguna modificación ni eliminación puede dejar turnos futuros
      activos sin cobertura (día de origen y de destino).
    - La acción de eliminación múltiple por defecto no consulta permisos
      por objeto: se retira para que no pueda eludir estas protecciones
      (un POST directo con esa acción queda sin efecto porque la acción
      ya no está registrada).
    """

    form = DisponibilidadAdminForm
    list_display = ('profesional', 'fecha', 'hora_inicio', 'hora_fin')
    list_filter = ('fecha', 'profesional')
    search_fields = ('profesional__nombre',)

    @staticmethod
    def _motivo_bloqueo_borrado(obj):
        """Motivo por el que no puede eliminarse la franja, o ``None``."""
        if obj.fecha < timezone.localdate():
            return 'las disponibilidades de fechas pasadas son de solo lectura.'
        restantes = Disponibilidad.objects.filter(
            profesional=obj.profesional, fecha=obj.fecha,
        ).exclude(pk=obj.pk)
        turnos = Turno.objects.filter(
            profesional=obj.profesional, fecha=obj.fecha,
            estado__in=_ESTADOS_ACTIVOS,
        )
        for turno in turnos:
            if _turno_ya_comenzo(turno.fecha, turno.hora):
                continue
            if not any(
                disponibilidad_cubre_turno(franja, turno)
                for franja in restantes
            ):
                return (
                    f'quedaría sin cobertura el turno del {turno.fecha} a '
                    f'las {turno.hora:%H:%M} (pendiente o confirmado).'
                )
        return None

    def has_change_permission(self, request, obj=None):
        # El pasado es de solo lectura: con permiso falso la vista de
        # cambio devuelve 403 para cualquier guardado directo, aunque la
        # consulta (GET) sigue permitida por has_view_permission.
        if obj is not None and obj.fecha < timezone.localdate():
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and self._motivo_bloqueo_borrado(obj):
            return False
        return super().has_delete_permission(request, obj)

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    def delete_queryset(self, request, queryset):
        # Red de seguridad: si la eliminación múltiple se volviera a
        # registrar, ningún objeto protegido puede eliminarse en bloque.
        for obj in queryset:
            if self._motivo_bloqueo_borrado(obj):
                raise PermissionDenied(
                    'No se pueden eliminar en bloque disponibilidades '
                    'protegidas.'
                )
        super().delete_queryset(request, queryset)


class ProfesionalAdminForm(forms.ModelForm):
    """Formulario administrativo de profesionales.

    - No se permite desactivar un profesional que tenga turnos futuros
      activos: la agenda quedaría viva pero inaccesible para su cuenta
      vinculada (las vistas exigen ``is_active`` para gestionarla).
    - El vínculo con una cuenta es inmutable (D3): no se quita ni se
      reemplaza desde acá, para que nunca quede una cuenta PERSONAL sin
      su Profesional. La alternativa es desactivar el profesional.
    """

    class Meta:
        model = Profesional
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()

        if (
            self.instance.pk
            and self.instance.usuario_id
            and cleaned_data.get('usuario') != self.instance.usuario
        ):
            raise forms.ValidationError(
                'No se puede quitar ni reemplazar la cuenta vinculada a '
                'este profesional: el vínculo se conserva mientras la '
                'cuenta exista. Desactivalo en lugar de modificar el '
                'vínculo.'
            )

        if (
            self.instance.pk
            and self.instance.is_active
            and not cleaned_data.get('is_active')
        ):
            turnos = Turno.objects.filter(
                profesional=self.instance, estado__in=_ESTADOS_ACTIVOS,
            )
            if any(not _turno_ya_comenzo(t.fecha, t.hora) for t in turnos):
                raise forms.ValidationError(
                    'No se puede desactivar un profesional con turnos '
                    'futuros pendientes o confirmados: quedaría una agenda '
                    'activa que no podría gestionarse.'
                )

        return cleaned_data


@admin.register(Profesional)
class ProfesionalAdmin(admin.ModelAdmin):
    """Profesionales: sin desactivación inconsistente ni borrado destructivo.

    - ``is_active`` no puede pasar a falso con turnos futuros activos.
    - La eliminación está bloqueada si el profesional tiene turnos (el
      ``SET_NULL`` dejaría reservas futuras sin profesional, fuera de los
      chequeos de solape y cobertura), disponibilidades (el ``CASCADE``
      borraría todas sus franjas) o una cuenta vinculada (D3: dejaría a
      un usuario PERSONAL sin su Profesional).
    """

    form = ProfesionalAdminForm
    list_display = ('nombre', 'usuario', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('nombre', 'usuario__username', 'usuario__email')

    @staticmethod
    def _motivo_bloqueo_borrado(obj):
        if obj.turnos.exists():
            return 'el profesional tiene turnos asociados.'
        if obj.disponibilidades.exists():
            return 'el profesional tiene disponibilidades asociadas.'
        if obj.usuario_id:
            return 'el profesional está vinculado a una cuenta de usuario.'
        return None

    def has_delete_permission(self, request, obj=None):
        if obj is not None and self._motivo_bloqueo_borrado(obj):
            return False
        return super().has_delete_permission(request, obj)

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    def delete_queryset(self, request, queryset):
        # Red de seguridad por si la eliminación múltiple se reintegra.
        for obj in queryset:
            if self._motivo_bloqueo_borrado(obj):
                raise PermissionDenied(
                    'No se pueden eliminar en bloque profesionales con '
                    'dependencias.'
                )
        super().delete_queryset(request, queryset)


class ServicioAdminForm(forms.ModelForm):
    """Formulario administrativo de servicios.

    La duración no puede cambiar si el servicio tiene turnos futuros
    activos: ``Turno.intervalo()`` deriva de la duración y cambiarla
    alteraría retroactivamente los solapes y la cobertura de esas
    reservas. Desactivar el servicio sigue permitido (regla de B1).
    """

    class Meta:
        model = Servicio
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        duracion = cleaned_data.get('duracion')

        if (
            self.instance.pk
            and duracion is not None
            and duracion != self.instance.duracion
        ):
            turnos = Turno.objects.filter(
                servicio=self.instance, estado__in=_ESTADOS_ACTIVOS,
            )
            if any(not _turno_ya_comenzo(t.fecha, t.hora) for t in turnos):
                raise forms.ValidationError(
                    'No se puede cambiar la duración de un servicio con '
                    'turnos futuros pendientes o confirmados: cambiaría el '
                    'horario que esos turnos ocupan.'
                )

        return cleaned_data


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    """Servicios: duración estable con agenda activa, sin borrado huérfano.

    - Cambiar la duración está bloqueado con turnos futuros activos.
    - La eliminación está bloqueada si tiene turnos (el ``SET_NULL``
      dejaría turnos sin duración, fuera de todo chequeo de solape y
      cobertura).
    - Desactivar (``is_active=False``) sigue permitido: es la regla de B1.
    """

    form = ServicioAdminForm
    list_display = ('nombre', 'duracion', 'precio', 'is_active')
    search_fields = ('nombre',)

    @staticmethod
    def _motivo_bloqueo_borrado(obj):
        if obj.turnos.exists():
            return 'el servicio tiene turnos asociados.'
        return None

    def has_delete_permission(self, request, obj=None):
        if obj is not None and self._motivo_bloqueo_borrado(obj):
            return False
        return super().has_delete_permission(request, obj)

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    def delete_queryset(self, request, queryset):
        # Red de seguridad por si la eliminación múltiple se reintegra.
        for obj in queryset:
            if self._motivo_bloqueo_borrado(obj):
                raise PermissionDenied(
                    'No se pueden eliminar en bloque servicios con turnos.'
                )
        super().delete_queryset(request, queryset)
