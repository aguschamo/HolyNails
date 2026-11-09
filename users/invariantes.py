"""Invariante PERSONAL–Profesional (D3): validación compartida.

Única implementación de las reglas de rol del invariante D3, usada por:

- ``AdminUserSerializer.validate_role`` (gestión de usuarios vía API), y
- el Django Admin de usuarios (``users/admin.py``), para que el panel
  administrativo tampoco pueda romper el invariante.

Reglas:

- alta (``instance`` es ``None``): no se crea un usuario con rol
  PERSONAL sin su Profesional; el alta correcta de PERSONAL con vínculo
  es el flujo ``POST /api/profesionales/crear-con-usuario/`` (no existe
  una operación atómica equivalente en el Django Admin);
- no se asigna el rol PERSONAL a una cuenta sin Profesional vinculado;
- una cuenta con Profesional vinculado no cambia de rol (en particular,
  PERSONAL -> CLIENTE está prohibido; tampoco PERSONAL -> ADMIN). El
  **no-op** (guardar el mismo rol sin cambio real) está permitido para
  cuentas vinculadas PERSONAL o ADMIN, de modo que una ADMIN con
  Profesional pueda conservar su rol; una cuenta CLIENTE con vínculo
  (estado inválido) sigue viéndose reparada hacia PERSONAL.

Lanza ``django.core.exceptions.ValidationError``: el Django Admin la
interpreta como error de campo y el serializer la traduce a DRF.
"""

from django.core.exceptions import ValidationError

from .models import User


def validar_rollo_d3(instance, value):
    """Valida el rol ``value`` para la cuenta ``instance`` (None = alta).

    Devuelve ``value`` si es válido; lanza ValidationError si la operación
    rompería el invariante D3.
    """
    vinculado = (
        instance is not None
        and getattr(instance, 'profesional', None) is not None
    )

    if instance is None:
        # Alta: la cuenta nueva nace sin vínculo posible.
        if value == User.Roles.PERSONAL:
            raise ValidationError(
                'No se puede crear un usuario con rol PERSONAL sin un '
                'Profesional vinculado. Usá POST /api/profesionales/'
                'crear-con-usuario/ para crear la cuenta y su vínculo '
                'en una única operación.'
            )
        return value

    if value == User.Roles.PERSONAL and not vinculado:
        raise ValidationError(
            'No se puede asignar el rol PERSONAL: la cuenta no tiene '
            'un Profesional vinculado.'
        )

    if value != User.Roles.PERSONAL and vinculado:
        # No-op: guardar el mismo rol sin cambio real está permitido para
        # las cuentas válidas con vínculo (PERSONAL y ADMIN). Una cuenta
        # CLIENTE con vínculo es un estado inválido que sigue
        # rechazándose para repararla hacia PERSONAL.
        if value == instance.role and instance.role in (
            User.Roles.PERSONAL,
            User.Roles.ADMIN,
        ):
            return value
        raise ValidationError(
            'No se puede cambiar el rol de una cuenta con un '
            'Profesional vinculado; solo se conserva el rol actual '
            '(PERSONAL o ADMIN). Desvinculá la cuenta antes de '
            'modificarla.'
        )

    return value
