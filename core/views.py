from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from datetime import datetime, timedelta

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
from .serializers import (
    ServicioPublicoSerializer,
    ServicioSerializer,
    TurnoSerializer,
    ProfesionalSerializer,
    ProfesionalConUsuarioSerializer,
    DisponibilidadSerializer,
)
from .permissions import PuedeReservar, IsOwnerOrAdmin, EsProfesionalOAdmin, IsAdmin
from users.models import User
from users.serializers import CuentaVinculableSerializer

GRANULARIDAD_MINUTOS = 15


def is_admin(user):
    return user.is_staff or getattr(user, 'role', None) == 'ADMIN'


def _turno_ya_comenzo(fecha, hora):
    """True si un turno que empieza en ``fecha`` y ``hora`` ya comenzó.

    Compara fecha y hora en conjunto (no solo la fecha): un turno de hoy
    cuya hora ya pasó cuenta como pasado. timezone.now() devuelve una
    fecha aware (USE_TZ=True) y la hora local del turno se convierte con
    la zona horaria actual, igual que el resto del proyecto.

    Función de módulo para reutilizarla en la creación de reservas, en las
    transiciones de estado, en la consulta de horarios disponibles y en el
    mantenimiento de disponibilidades.
    """
    inicio = datetime.combine(fecha, hora)
    ahora = timezone.now()
    if timezone.is_aware(ahora):
        inicio = timezone.make_aware(inicio)
    return inicio <= ahora


def _es_conflicto_unico(exc):
    """True si un ``IntegrityError`` proviene de una restricción única.

    Cubre el mensaje de SQLite (``UNIQUE constraint failed``), el de
    PostgreSQL (``duplicate key value violates unique constraint``) y su
    SQLSTATE ``23505``. Cualquier otro ``IntegrityError`` no es un conflicto
    esperado y debe propagarse sin ocultarlo.
    """
    if getattr(exc, 'pgcode', None) == '23505':
        return True
    mensaje = str(exc).lower()
    return 'unique' in mensaje or 'duplicate key' in mensaje


class HealthView(APIView):
    """Health check público (Etapa 1B del TP10).

    GET /api/health/ devuelve un JSON fijo. No consulta la base de datos
    ni ningún otro recurso, y no exige autenticación: la lista de
    autenticadores está vacía para que una cabecera Authorization
    inválida tampoco pueda alterar la respuesta.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'status': 'ok', 'service': 'api'})


class ServicioViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        user = self.request.user
        # Orden fijo por id (A2): PageNumberPagination necesita un orden
        # determinístico para no duplicar ni saltar filas entre páginas;
        # sin él DRF emite UnorderedObjectListWarning. El orden aparente
        # (inserción) no cambia para los consumidores.
        if user.is_authenticated and is_admin(user):
            return Servicio.objects.all().order_by('id')
        return Servicio.objects.filter(is_active=True).order_by('id')

    def get_serializer_class(self):
        user = self.request.user
        is_safe = self.request.method in ('GET', 'HEAD', 'OPTIONS')
        if is_safe and not (user.is_authenticated and is_admin(user)):
            return ServicioPublicoSerializer
        return ServicioSerializer

    def get_permissions(self):
        # D1: la escritura de servicios es exclusiva de ADMIN; el resto
        # (CLIENTE, PERSONAL y anónimos) solo consulta los activos.
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return []
        return [IsAdmin()]

    def perform_destroy(self, instance):
        """Un servicio con turnos no se elimina (historial incluido).

        Mismo criterio que el Django Admin (B4): cualquier turno —
        pendiente, confirmado o cancelado — conserva referencia al
        servicio; borrarlo dejaría esos turnos sin ``servicio``, fuera de
        los chequeos de solape y cobertura (``Turno.intervalo()`` devuelve
        ``None``). La alternativa permitida es desactivar el servicio.
        La eliminación es exclusiva de ADMIN (D1).
        """
        if instance.turnos.exists():
            raise DRFValidationError(
                'No se puede eliminar el servicio: tiene turnos asociados. '
                'Desactivalo en lugar de eliminarlo.'
            )
        super().perform_destroy(instance)


class ProfesionalViewSet(viewsets.ModelViewSet):
    """CRUD de profesionales.

    Lectura: autenticados. Escritura: solo ADMIN (staff o rol ADMIN).
    PERSONAL y CLIENTE no pueden crear, editar ni eliminar profesionales.
    """

    # Orden fijo por id (A2): misma razón que ServicioViewSet — paginación
    # estable sin duplicados ni omisiones entre páginas.
    queryset = Profesional.objects.all().order_by('id')
    serializer_class = ProfesionalSerializer

    def get_permissions(self):
        # La lista de cuentas vinculables (A3) es exclusiva de ADMIN: este
        # método es la autoridad de permisos del ViewSet (el override
        # ignora el permission_classes del decorador @action), por lo que
        # el caso se declara acá además de en el decorador.
        if self.action == 'cuentas_disponibles':
            return [IsAdmin()]
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [IsAuthenticated()]
        return [IsAdmin()]

    def perform_destroy(self, instance):
        """Un profesional con turnos o disponibilidades no se elimina.

        Mismo criterio que el Django Admin (B4):

        - con turnos, el ``SET_NULL`` dejaría reservas de cualquier
          estado sin profesional, fuera de solape, cobertura y agenda;
        - con disponibilidades, el ``CASCADE`` borraría todas sus franjas.

        Además (D3) no se elimina un profesional vinculado a una cuenta:
        la eliminación dejaría a un usuario PERSONAL sin su Profesional.
        La alternativa permitida es desactivarlo (``is_active=False``).

        La fila se bloquea (``select_for_update``) dentro de la
        transacción **antes** de comprobar dependencias: la creación de
        turnos bloquea esa misma fila, de modo que una reserva
        concurrente no puede colarse entre la comprobación y el borrado.
        """
        with transaction.atomic():
            profesional = Profesional.objects.select_for_update().get(
                pk=instance.pk
            )
            if profesional.turnos.exists():
                raise DRFValidationError(
                    'No se puede eliminar el profesional: tiene turnos '
                    'asociados.'
                )
            if profesional.disponibilidades.exists():
                raise DRFValidationError(
                    'No se puede eliminar el profesional: tiene '
                    'disponibilidades asociadas.'
                )
            if profesional.usuario_id:
                raise DRFValidationError(
                    'No se puede eliminar el profesional: está vinculado a '
                    'una cuenta de usuario. Desactivalo en lugar de '
                    'eliminarlo.'
                )
            super().perform_destroy(profesional)

    @action(
        detail=False,
        methods=['post'],
        url_path='crear-con-usuario',
        url_name='crear-con-usuario',
        permission_classes=[IsAdmin],
    )
    def crear_con_usuario(self, request):
        """Alta administrativa de una cuenta PERSONAL con su Profesional.

        Crea el ``User`` con rol ``PERSONAL`` y el registro ``Profesional``
        en una única transacción (ver ProfesionalConUsuarioSerializer): si
        falla el vínculo, no queda la cuenta creada. Solo ADMIN; un cliente
        o personal recibe 403.
        """
        serializer = ProfesionalConUsuarioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profesional = serializer.save()
        return Response(
            ProfesionalSerializer(profesional).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=False,
        methods=['get'],
        url_path='cuentas-disponibles',
        url_name='cuentas-disponibles',
        permission_classes=[IsAdmin],
    )
    def cuentas_disponibles(self, request):
        """Cuentas de usuario sin vínculo profesional (A3).

        Listado de sólo lectura para que la administración elija a qué
        cuenta existente asociar un profesional sin cuenta, sin crear
        cuentas nuevas ni tocar contraseñas. Excluye las ya vinculadas:
        una cuenta sólo puede estar unida a un profesional y ese vínculo
        es inmutable (D3). Sólo ADMIN (staff o rol); anónimos reciben
        401 y otros roles 403.
        """
        usuarios = User.objects.filter(profesional__isnull=True).order_by('username')
        pagina = self.paginate_queryset(usuarios)
        serializer = CuentaVinculableSerializer(pagina, many=True)
        return self.get_paginated_response(serializer.data)


class DisponibilidadViewSet(viewsets.ModelViewSet):
    """Franjas horarias de trabajo de un profesional.

    Lectura (B10.2): un administrador ve todas las disponibilidades y un
    usuario con rol PERSONAL únicamente las de su profesional vinculado.
    El resto de las cuentas autenticadas conserva la consulta previa
    (compatible con ``test_consultar_disponibilidades_historicas_permitido``);
    el bloqueo de CLIENTE opera en la pantalla y en las operaciones de
    escritura. Escritura: solo el usuario vinculado al profesional
    o un administrador.

    Todas las operaciones de escritura bloquean la fila del profesional para
    evitar cambios concurrentes incompatibles con reservas existentes.
    """

    serializer_class = DisponibilidadSerializer

    def get_queryset(self):
        qs = Disponibilidad.objects.all().select_related('profesional')

        # Acote de lectura por rol (B10.2): el rol PERSONAL veía franjas
        # ajenas en el listado general, contra la regla "sólo las suyas".
        # Aplica sólo a los métodos seguros: en escritura el queryset
        # queda completo para que el chequeo de objeto
        # ``EsProfesionalOAdmin`` responda 403 (y no 404) cuando se
        # manipula el ID de una disponibilidad ajena, que es el contrato
        # que ya cubren los tests existentes. ADMIN (staff o rol) sigue
        # viendo todas; el resto de las cuentas autenticadas conserva la
        # consulta previa (la lectura de CLIENTE está cubierta por un
        # test existente que exige 200 con datos).
        if self.request.method in SAFE_METHODS:
            user = self.request.user
            if (
                user.is_authenticated
                and not is_admin(user)
                and getattr(user, 'role', None) == 'PERSONAL'
            ):
                # Personal: sólo su agenda (vacía si no tiene vínculo).
                qs = qs.filter(profesional__usuario=user)

        profesional_id = self.request.query_params.get('profesional')
        fecha = self.request.query_params.get('fecha')
        if profesional_id:
            qs = qs.filter(profesional_id=profesional_id)
        if fecha:
            qs = qs.filter(fecha=fecha)
        return qs.order_by('profesional', 'fecha', 'hora_inicio')

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [IsAuthenticated()]
        return [EsProfesionalOAdmin()]

    def _bloquear_profesional(self, profesional):
        """Adquiere un bloqueo real (SELECT FOR UPDATE) sobre la fila del profesional."""
        return Profesional.objects.select_for_update().get(pk=profesional.pk)

    def _turnos_activos_del_dia(self, profesional, fecha):
        """Turnos pendiente/confirmado que aún no comenzaron en esa fecha, con bloqueo.

        Los turnos pasados no bloquean el mantenimiento de disponibilidades
        aunque conserven estado pendiente o confirmado (no se modifican ni
        eliminan); los cancelados se excluyen por estado. El filtro temporal
        reutiliza ``_turno_ya_comenzo`` (misma regla que las transiciones de
        estado y la creación de reservas).
        """
        turnos = Turno.objects.select_for_update().filter(
            profesional=profesional, fecha=fecha,
            estado__in=[Turno.Estado.PENDIENTE, Turno.Estado.CONFIRMADO],
        )
        return [t for t in turnos if not _turno_ya_comenzo(t.fecha, t.hora)]

    def _validar_cobertura_turnos_futuros(self, profesional, fecha, franjas):
        """Toda franja recibida es un par ``(hora_inicio, hora_fin)`` de ese día.

        Cada turno futuro pendiente/confirmado del día debe caber íntegramente
        en UNA sola franja (sin unión de franjas contiguas). Los turnos sin
        servicio (``intervalo()`` devuelve ``None``) se omiten sin error.
        """
        for t in self._turnos_activos_del_dia(profesional, fecha):
            intervalo = t.intervalo()
            if not intervalo:
                continue
            t_inicio, t_fin = intervalo
            cubierto = any(
                t_inicio >= datetime.combine(fecha, hi)
                and t_fin <= datetime.combine(fecha, hf)
                for hi, hf in franjas
            )
            if not cubierto:
                raise DRFValidationError(
                    'No se puede modificar la franja: quedarían turnos futuros '
                    'pendientes o confirmados fuera de la disponibilidad del '
                    'profesional para ese día.'
                )

    def _validar_no_solapamiento_con_otras(self, profesional, fecha, hora_inicio, hora_fin, excluir_pk=None):
        """Valida que no se solapen con disponibilidades existentes del mismo profesional/fecha."""
        qs = Disponibilidad.objects.filter(
            profesional=profesional, fecha=fecha
        )
        if excluir_pk is not None:
            qs = qs.exclude(pk=excluir_pk)
        for d in qs:
            if intervalos_se_solapan(
                datetime.combine(fecha, hora_inicio),
                datetime.combine(fecha, hora_fin),
                datetime.combine(fecha, d.hora_inicio),
                datetime.combine(fecha, d.hora_fin),
            ):
                raise DRFValidationError(
                    'Se superpone con otra disponibilidad existente para este profesional y fecha.'
                )

    def create(self, request, *args, **kwargs):
        """Crea una disponibilidad serializando la reserva de la franja.

        Orden dentro de la transacción:
        1. validación de formato (serializer.is_valid)
        2. bloqueo de fila del profesional (select_for_update, evaluado inmediatamente)
        3. comprobación de permisos (usuario vinculado o admin)
        4. revalidación de solapamiento ya dentro del bloqueo
        5. guardado de la disponibilidad
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profesional = serializer.validated_data.get('profesional')
        fecha = serializer.validated_data.get('fecha')
        hora_inicio = serializer.validated_data.get('hora_inicio')
        hora_fin = serializer.validated_data.get('hora_fin')

        try:
            with transaction.atomic():
                profesional_bloqueado = self._bloquear_profesional(profesional)

                # 3. Comprobación de permisos: el usuario vinculado o un admin.
                # Un profesional sin usuario vinculado solo puede ser gestionado
                # por administradores (mismo criterio que EsProfesionalOAdmin a
                # nivel de objeto, aplicado acá porque en el alta no hay objeto
                # sobre el cual chequearlo).
                if not is_admin(request.user) and profesional_bloqueado.usuario != request.user:
                    if profesional_bloqueado.usuario is None:
                        raise PermissionDenied(
                            'Solo un administrador puede crear disponibilidades '
                            'de un profesional sin usuario vinculado.'
                        )
                    raise PermissionDenied(
                        'Solo el profesional vinculado o un administrador pueden crear su disponibilidad.'
                    )

                # 4. Revalidar solapamiento ya dentro del bloqueo.
                self._validar_no_solapamiento_con_otras(
                    profesional_bloqueado, fecha, hora_inicio, hora_fin
                )

                # 5. Guardar.
                serializer.save()
        except IntegrityError as exc:
            # Captura FUERA del atomic: la transacción ya fue revertida y no
            # se continúa dentro de una transacción rota. Solo los conflictos
            # de restricción única se traducen a 400; cualquier otro
            # IntegrityError se propaga sin ocultarlo.
            if not _es_conflicto_unico(exc):
                raise
            raise DRFValidationError(
                'Ya existe una disponibilidad para ese profesional, fecha y hora de inicio.'
            )

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        """Edita una disponibilidad serializando la modificación de la franja.

        Orden:
        1. obtener objeto y comprobar permisos
        2. rechazar ediciones de disponibilidades de fechas pasadas
        3. validación de formato (serializer.is_valid) y de fecha no pasada
        4. bloqueo de fila del profesional + rechazar cambio de profesional
        5. revalidación de solapamiento contra otras disponibilidades
        6. cobertura de turnos futuros en el día origen y en el día destino
        7. guardar únicamente si todo pasa
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        self.check_object_permissions(request, instance)

        # El pasado es de solo lectura: no se modifican disponibilidades de
        # fechas anteriores a hoy (ni siquiera para moverlas a otra fecha).
        if instance.fecha < timezone.localdate():
            raise DRFValidationError(
                'No se puede modificar una disponibilidad de una fecha pasada.'
            )

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        # No se permite cambiar el profesional de una disponibilidad existente.
        nuevo_profesional = serializer.validated_data.get('profesional', instance.profesional)
        if nuevo_profesional.pk != instance.profesional.pk:
            raise DRFValidationError(
                'No se puede cambiar el profesional de una disponibilidad existente.'
            )

        fecha_nueva = serializer.validated_data.get('fecha', instance.fecha)
        hora_inicio_nueva = serializer.validated_data.get('hora_inicio', instance.hora_inicio)
        hora_fin_nueva = serializer.validated_data.get('hora_fin', instance.hora_fin)

        try:
            with transaction.atomic():
                profesional_bloqueado = self._bloquear_profesional(instance.profesional)

                # 4. Revalidar solapamiento contra otras disponibilidades, excluyendo la propia.
                self._validar_no_solapamiento_con_otras(
                    profesional_bloqueado, fecha_nueva, hora_inicio_nueva, hora_fin_nueva,
                    excluir_pk=instance.pk,
                )

                # 5. Cobertura de turnos futuros en ambas fechas: si la franja
                # cambia de fecha, el día original pierde esta disponibilidad y
                # el día destino la gana. En ambos casos se tienen en cuenta las
                # demás disponibilidades existentes del mismo profesional.
                if fecha_nueva != instance.fecha:
                    franjas_dia_original = [
                        (d.hora_inicio, d.hora_fin)
                        for d in Disponibilidad.objects.filter(
                            profesional=profesional_bloqueado, fecha=instance.fecha
                        ).exclude(pk=instance.pk)
                    ]
                    self._validar_cobertura_turnos_futuros(
                        profesional_bloqueado, instance.fecha, franjas_dia_original
                    )

                franjas_dia_nuevo = [
                    (hora_inicio_nueva, hora_fin_nueva) if d.pk == instance.pk
                    else (d.hora_inicio, d.hora_fin)
                    for d in Disponibilidad.objects.filter(
                        profesional=profesional_bloqueado, fecha=fecha_nueva
                    )
                ]
                if fecha_nueva != instance.fecha:
                    # La franja se muda: aporta sus nuevos valores al día destino.
                    franjas_dia_nuevo.append((hora_inicio_nueva, hora_fin_nueva))
                self._validar_cobertura_turnos_futuros(
                    profesional_bloqueado, fecha_nueva, franjas_dia_nuevo
                )

                # 6. Guardar.
                serializer.save()
        except IntegrityError as exc:
            # Captura FUERA del atomic: sin transacción rota. Solo los
            # conflictos de restricción única (profesional, fecha,
            # hora_inicio) se traducen a 400; el resto se propaga.
            if not _es_conflicto_unico(exc):
                raise
            raise DRFValidationError(
                'No se pudo guardar la disponibilidad: ya existe otra con '
                'ese profesional, fecha y hora de inicio.'
            )

        return Response(serializer.data)

    def perform_destroy(self, instance):
        self.check_object_permissions(self.request, instance)

        # El pasado es de solo lectura: tampoco se eliminan franjas históricas.
        if instance.fecha < timezone.localdate():
            raise DRFValidationError(
                'No se puede eliminar una disponibilidad de una fecha pasada.'
            )

        profesional = instance.profesional
        fecha = instance.fecha
        hora_inicio = instance.hora_inicio
        hora_fin = instance.hora_fin

        with transaction.atomic():
            profesional_bloqueado = self._bloquear_profesional(profesional)
            turnos = self._turnos_activos_del_dia(profesional_bloqueado, fecha)

            for t in turnos:
                if not t.servicio or not t.servicio.duracion:
                    continue
                t_inicio, t_fin = t.intervalo()
                d_inicio = datetime.combine(fecha, hora_inicio)
                d_fin = datetime.combine(fecha, hora_fin)
                if intervalos_se_solapan(t_inicio, t_fin, d_inicio, d_fin):
                    raise DRFValidationError(
                        'No se puede eliminar esta disponibilidad: existen turnos '
                        'futuros pendientes o confirmados que dependen de esta franja horaria.'
                    )
            instance.delete()


class TurnoViewSet(viewsets.ModelViewSet):
    serializer_class = TurnoSerializer
    # Etapa 1 de gestión de turnos: el detalle solo admite consulta (GET) y
    # las acciones explícitas de estado (POST). PUT/PATCH/DELETE quedan
    # bloqueados para todos los usuarios (405) para no permitir modificaciones
    # directas de fecha, hora, servicio, profesional o estado, ni borrados
    # físicos. La creación de reservas (POST /api/turnos/) sigue activa.
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        """Permisos por acción.

        - confirmar: exclusivamente administrador (IsAdmin).
        - cancelar: administrador o dueño del turno (IsOwnerOrAdmin).
        - crear (POST /api/turnos/): usuarios autenticados que participen
          del flujo de reservas; PERSONAL no reserva (D4).
        - consultas: autenticado, y IsOwnerOrAdmin a nivel de objeto.
        """
        if self.action == 'confirmar':
            return [IsAuthenticated(), IsAdmin()]
        if self.action == 'cancelar':
            return [IsAuthenticated(), IsOwnerOrAdmin()]
        if self.request.method == 'POST':
            return [IsAuthenticated(), PuedeReservar()]
        return [IsAuthenticated(), IsOwnerOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        como_profesional = self.request.query_params.get('como_profesional') == 'true'

        # Vista como profesional: ver turnos asignados al profesional
        # vinculado al usuario autenticado (ADMIN, PERSONAL o CLIENTE con
        # vínculo). Sin vínculo o con profesional inactivo → vacío
        # (B10.0.2: ADMIN sin Profesional no tiene agenda profesional).
        if como_profesional:
            profesional = getattr(user, 'profesional', None)
            if profesional is None or not profesional.is_active:
                return Turno.objects.none()
            qs = Turno.objects.filter(profesional=profesional).select_related('usuario', 'servicio', 'profesional')
        elif is_admin(user):
            qs = Turno.objects.all().select_related('usuario', 'servicio', 'profesional')
        elif getattr(user, 'role', None) == 'CLIENTE':
            # Solo CLIENTE ve turnos propios como reserva. PERSONAL no
            # consulta la agenda como cliente (D4): su agenda laboral
            # entra exclusivamente por como_profesional=true.
            qs = Turno.objects.filter(usuario=user).select_related('servicio', 'profesional')
        else:
            qs = Turno.objects.none()

        # Filtro «mis turnos»: el usuario se determina SIEMPRE desde el
        # token autenticado (nunca desde un ID enviado por el frontend),
        # y se aplica después del scoping por rol para que sea una
        # intersección: nunca amplía lo que cada rol ya puede ver.
        if self.request.query_params.get('propios') == 'true':
            qs = qs.filter(usuario=user)

        profesional_id = self.request.query_params.get('profesional')
        if profesional_id:
            qs = qs.filter(profesional_id=profesional_id)
        return qs.order_by('fecha', 'hora')

    def create(self, request, *args, **kwargs):
        """Crea un turno serializando reservas del mismo profesional y fecha.

        Orden dentro de la transacción:
        1. validación de formato (serializer.is_valid)
        2. bloqueo de fila del profesional (select_for_update, evaluado inmediatamente)
        3. validación de disponibilidad y solapamiento (ya dentro del bloqueo)
        4. guardado del turno
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profesional = serializer.validated_data.get('profesional')
        fecha = serializer.validated_data.get('fecha')
        hora = serializer.validated_data.get('hora')
        servicio = serializer.validated_data.get('servicio')
        duracion = servicio.duracion if servicio else None

        try:
            with transaction.atomic():
                # 2. Bloqueo real de la fila del profesional (evaluado inmediatamente).
                if profesional:
                    profesional_bloqueado = Profesional.objects.select_for_update().get(
                        pk=profesional.pk
                    )
                else:
                    profesional_bloqueado = None

                # 3. Validaciones de negocio ya dentro del bloqueo.
                if profesional_bloqueado and not profesional_bloqueado.is_active:
                    raise DRFValidationError(
                        'El profesional seleccionado no está activo.'
                    )

                # Rechazar fechas pasadas y hoy con la hora ya comenzada,
                # comparando fecha y hora conjuntamente (misma regla y misma
                # función que las transiciones de estado de la etapa 1).
                if fecha and hora and _turno_ya_comenzo(fecha, hora):
                    raise DRFValidationError(
                        'La hora del turno ya pasó. Elegí un horario futuro.'
                    )

                if profesional_bloqueado and fecha and hora and servicio:
                    inicio_turno_dt = datetime.combine(fecha, hora)
                    fin_turno_dt = inicio_turno_dt + duracion

                    # Defensa adicional: si la duración cruzara la medianoche,
                    # fin_turno_dt.time() truncaría al día siguiente y el filtro
                    # de cobertura parecería cumplirse. El serializer ya lo
                    # rechaza; acá se garantiza antes de usar .time().
                    if fin_turno_dt.date() > fecha:
                        raise DRFValidationError(
                            'La duración del servicio no puede cruzar la medianoche.'
                        )

                    # Debe estar dentro de al menos una disponibilidad del
                    # profesional (una sola franja; no se unen franjas contiguas).
                    fin_turno = fin_turno_dt.time()
                    cubre = Disponibilidad.objects.filter(
                        profesional=profesional_bloqueado,
                        fecha=fecha,
                        hora_inicio__lte=hora,
                        hora_fin__gte=fin_turno,
                    ).exists()
                    if not cubre:
                        raise DRFValidationError(
                            'El horario solicitado no está dentro de la disponibilidad del profesional.'
                        )

                    # No solaparse con turnos activos existentes del mismo profesional.
                    turnos = Turno.objects.select_for_update().filter(
                        profesional=profesional_bloqueado, fecha=fecha,
                        estado__in=[Turno.Estado.PENDIENTE, Turno.Estado.CONFIRMADO],
                    )
                    nuevo_inicio = datetime.combine(fecha, hora)
                    nuevo_fin = nuevo_inicio + duracion
                    for t in turnos:
                        if not t.servicio or not t.servicio.duracion:
                            continue
                        t_inicio, t_fin = t.intervalo()
                        if intervalos_se_solapan(nuevo_inicio, nuevo_fin, t_inicio, t_fin):
                            raise DRFValidationError(
                                'El profesional ya tiene un turno que se superpone con ese horario.'
                            )

                # 4. Guardado dentro de la misma transacción.
                serializer.save(usuario=request.user)
        except IntegrityError as exc:
            # Captura FUERA del atomic: la transacción ya fue revertida y no
            # se continúa dentro de una transacción rota. Solo los conflictos
            # de restricción única (profesional, fecha, hora) se traducen a
            # 400; cualquier otro IntegrityError se propaga sin ocultarlo.
            if not _es_conflicto_unico(exc):
                raise
            raise DRFValidationError(
                'No se pudo crear el turno: ya existe una reserva para ese profesional, fecha y hora.'
            )

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        # Mantido para compatibilidad; la lógica real está en create().
        serializer.save(usuario=self.request.user)

    def _transicionar_estado(self, nuevo_estado):
        """Aplica una transición de estado atómica sobre un turno.

        El turno se vuelve a consultar con select_for_update dentro de la
        transacción y el estado se relee antes de cambiarlo, para que dos
        solicitudes concurrentes no ejecuten transiciones incompatibles
        (la segunda ve el resultado de la primera y recibe 400).

        Reglas de negocio (etapa 1):
        - El turno todavía no puede haber comenzado.
        - confirmar: solo pendiente → confirmado.
        - cancelar: pendiente o confirmado → cancelado (estado terminal).
        """
        # Búsqueda global (sin filtrar por usuario) + chequeo de permisos de
        # objeto: si el turno existe pero no pertenece al usuario, la
        # respuesta es 403 (falta de permisos) en lugar de un 404 que
        # enmascararía el rechazo; el 404 queda para turnos inexistentes.
        turno = get_object_or_404(Turno, pk=self.kwargs['pk'])
        self.check_object_permissions(self.request, turno)

        with transaction.atomic():
            turno_bloqueado = Turno.objects.select_for_update().get(pk=turno.pk)

            if _turno_ya_comenzo(turno_bloqueado.fecha, turno_bloqueado.hora):
                raise DRFValidationError(
                    'No se puede cambiar el estado de un turno que ya comenzó.'
                )

            estado_actual = turno_bloqueado.estado
            if nuevo_estado == Turno.Estado.CONFIRMADO:
                if estado_actual != Turno.Estado.PENDIENTE:
                    raise DRFValidationError(
                        'Solo se pueden confirmar turnos pendientes.'
                    )
            elif estado_actual == Turno.Estado.CANCELADO:
                raise DRFValidationError(
                    'Este turno ya está cancelado; no se puede volver a cancelar.'
                )

            turno_bloqueado.estado = nuevo_estado
            turno_bloqueado.save(update_fields=['estado'])

        return Response(TurnoSerializer(turno_bloqueado).data)

    @action(detail=True, methods=['post'])
    def confirmar(self, request, pk=None):
        """POST /api/turnos/{id}/confirmar/ — exclusivamente administrador."""
        return self._transicionar_estado(Turno.Estado.CONFIRMADO)

    @action(detail=True, methods=['post'])
    def cancelar(self, request, pk=None):
        """POST /api/turnos/{id}/cancelar/ — administrador o dueño del turno."""
        return self._transicionar_estado(Turno.Estado.CANCELADO)

    @action(detail=False, methods=['get'], url_path='disponibles', permission_classes=[IsAuthenticated])
    def disponibles(self, request):
        """Horarios libres para un servicio en una fecha, opcionalmente por profesional.

        Query params: servicio (id, requerido), fecha (YYYY-MM-DD, requerido),
                      profesional (id, opcional).

        Los turnos cancelados NO bloquean horarios.
        """
        servicio_id = request.query_params.get('servicio')
        fecha = request.query_params.get('fecha')
        profesional_id = request.query_params.get('profesional')

        if not servicio_id or not fecha:
            return Response(
                {'detail': 'Se requieren los parámetros "servicio" y "fecha".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            servicio = Servicio.objects.get(pk=servicio_id)
        except Servicio.DoesNotExist:
            return Response({'detail': 'Servicio no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        # Los servicios inactivos no se reservan: tampoco se ofrecen horarios.
        if not servicio.is_active:
            return Response(
                {'detail': 'El servicio seleccionado está inactivo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            fecha_obj = timezone.datetime.strptime(fecha, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return Response(
                {'detail': 'Fecha inválida. Usá el formato YYYY-MM-DD.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # No se ofrecen fechas anteriores a hoy.
        if fecha_obj < timezone.localdate():
            return Response(
                {'detail': 'La fecha no puede ser anterior a hoy.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        duracion = servicio.duracion
        profesionales = Profesional.objects.filter(is_active=True)
        if profesional_id:
            profesionales = profesionales.filter(pk=profesional_id)

        resultados = []
        for profesional in profesionales:
            disponibilidades = Disponibilidad.objects.filter(
                profesional=profesional, fecha=fecha_obj
            ).order_by('hora_inicio')
            # Solo turnos pendiente/confirmado bloquean; los cancelados liberan el horario.
            turnos = Turno.objects.filter(
                profesional=profesional, fecha=fecha_obj,
                estado__in=[Turno.Estado.PENDIENTE, Turno.Estado.CONFIRMADO],
            )

            for disp in disponibilidades:
                actual = datetime.combine(fecha_obj, disp.hora_inicio)
                fin_dia = datetime.combine(fecha_obj, disp.hora_fin)
                while actual + duracion <= fin_dia:
                    # Hoy no se ofrecen horarios cuya hora de inicio ya pasó
                    # (misma regla que la creación de reservas).
                    if _turno_ya_comenzo(fecha_obj, actual.time()):
                        actual += timedelta(minutes=GRANULARIDAD_MINUTOS)
                        continue
                    candidato = actual.time()
                    solapado = False
                    for t in turnos:
                        if not t.servicio or not t.servicio.duracion:
                            continue
                        t_inicio, t_fin = t.intervalo()
                        if intervalos_se_solapan(actual, actual + duracion, t_inicio, t_fin):
                            solapado = True
                            break
                    if not solapado:
                        resultados.append({
                            'profesional': profesional.id,
                            'profesional_nombre': str(profesional),
                            'fecha': fecha,
                            'hora': candidato.strftime('%H:%M'),
                        })
                    actual += timedelta(minutes=GRANULARIDAD_MINUTOS)

        return Response(resultados)
