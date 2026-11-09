from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdmin(BasePermission):
    """Solo administradores (staff de Django o rol ADMIN del sistema)."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.is_staff or getattr(request.user, 'role', None) == 'ADMIN'


class IsOwnerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        # Unificamos el criterio de Admin: staff de Django o rol ADMIN del sistema
        is_admin = request.user.is_staff or getattr(request.user, 'role', None) == 'ADMIN'
        return is_admin or obj.usuario == request.user


class EsProfesionalOAdmin(BasePermission):
    """Permite administrar la disponibilidad de un profesional solo a:

    - el usuario vinculado a ese profesional (profesional.usuario == request.user), o
    - un administrador (staff o rol ADMIN).
    """

    def has_object_permission(self, request, view, obj):
        is_admin = request.user.is_staff or getattr(request.user, 'role', None) == 'ADMIN'
        profesional_usuario = getattr(obj.profesional, 'usuario', None)
        return is_admin or profesional_usuario == request.user


class PuedeReservar(BasePermission):
    """D4: la creación de reservas no está disponible para PERSONAL.

    Las cuentas PERSONAL consultan sus turnos laborales desde MiAgenda
    (``?como_profesional=true``) y no participan del flujo de reservas de
    CLIENTE. ADMIN/staff conservan sus permisos.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff or getattr(request.user, 'role', None) == 'ADMIN':
            return True
        return getattr(request.user, 'role', None) != 'PERSONAL'


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS
