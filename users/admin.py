from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.core.exceptions import PermissionDenied

from .invariantes import validar_rollo_d3
from .models import User


class UserD3ChangeForm(UserChangeForm):
    """Formulario de edición de usuarios que respeta el invariante D3.

    Valida ``role`` con la misma función que el serializer de la API
    (``users/invariantes.py``): no se asigna PERSONAL sin Profesional
    vinculado ni se cambia el rol de una cuenta que conserve su vínculo
    (en particular PERSONAL -> CLIENTE); el no-op de guardar el mismo rol
    en cuentas vinculadas PERSONAL o ADMIN sí está permitido (B10.0.2).
    El vínculo en sí no se edita desde este formulario.
    """

    class Meta(UserChangeForm.Meta):
        model = User

    def clean_role(self):
        # Django invoca clean_<campo>() sin argumentos: el valor ya está
        # validado en self.cleaned_data.
        return validar_rollo_d3(self.instance, self.cleaned_data['role'])


class UserD3CreationForm(AdminUserCreationForm):
    """Formulario de alta de usuarios sin rol PERSONAL.

    Hereda de ``AdminUserCreationForm`` (la base del Django Admin) para
    conservar el campo ``usable_password`` del ``add_fieldsets`` y el
    manejo estándar de contraseñas; solo se agrega la validación D3.

    El Django Admin no puede crear una cuenta PERSONAL con su Profesional
    en una única operación atómica (el ``User`` y el ``Profesional`` viven
    en formularios distintos), por lo que el alta de PERSONAL queda
    impedida acá y debe realizarse con el flujo
    ``POST /api/profesionales/crear-con-usuario/``.
    """

    class Meta(AdminUserCreationForm.Meta):
        model = User

    def clean_role(self):
        return validar_rollo_d3(None, self.cleaned_data['role'])


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Usuarios: sin borrado de cuentas que tengan turnos, rol D3 seguro.

    - La eliminación está bloqueada si el usuario tiene turnos (el
      ``CASCADE`` borraría también el historial, incluidos los turnos
      cancelados). Los usuarios sin turnos siguen siendo eliminables.
    - La acción de eliminación múltiple por defecto no consulta permisos
      por objeto: se retira para que no pueda eludir esta protección (un
      POST directo con esa acción queda sin efecto porque la acción ya no
      está registrada).
    - Las contraseñas conservan el manejo estándar y seguro de Django:
      hash de solo lectura en el formulario y formulario dedicado de
      cambio con ``AUTH_PASSWORD_VALIDATORS``.
    - ``role`` se puede editar, pero validando el invariante D3 con la
      misma regla que la API (``users/invariantes.py``): no se crea ni se
      asigna PERSONAL sin Profesional vinculado y no se cambia el rol de
      una cuenta con vínculo (el no-op de conservar el rol actual en
      cuentas PERSONAL o ADMIN está permitido). El alta de PERSONAL con
      vínculo es el flujo ``crear-con-usuario`` de la API.
    """

    form = UserD3ChangeForm
    add_form = UserD3CreationForm

    list_display = ('nombre', 'email', 'role', 'is_staff')
    list_filter = ('role',)
    search_fields = ('nombre', 'email')

    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Datos adicionales', {'fields': ('nombre', 'role')}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ('Datos adicionales', {'fields': ('nombre', 'role')}),
    )

    @staticmethod
    def _motivo_bloqueo_borrado(obj):
        if obj.turnos.exists():
            return 'el usuario tiene turnos asociados.'
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
        # Red de seguridad por si la eliminación múltiple se reintegra:
        # el CASCADE borraría los turnos (historial incluido) de cada
        # usuario con reservas.
        for obj in queryset:
            if self._motivo_bloqueo_borrado(obj):
                raise PermissionDenied(
                    'No se pueden eliminar en bloque usuarios con turnos.'
                )
        super().delete_queryset(request, queryset)
