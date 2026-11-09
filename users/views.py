from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from core.models import Turno
from core.permissions import IsAdmin
from core.serializers import TurnoSerializer

from .models import User
from .serializers import (
    AdminUserSerializer,
    ClienteAdminSerializer,
    EmailTokenObtainPairSerializer,
    FotoPerfilSerializer,
    RegisterSerializer,
    UserSerializer,
)


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.none()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'register'


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class ProfileFotoView(APIView):
    """Foto de perfil del usuario autenticado (B11.2).

    - POST /api/auth/profile/foto/: sube o reemplaza la foto propia.
    - DELETE /api/auth/profile/foto/: elimina la foto propia.

    Opera exclusivamente sobre ``request.user``: no existe ningún
    parámetro para elegir a quién modificar, de modo que es imposible
    alterar la foto de otra cuenta desde este endpoint. Recibe sólo
    multipart/form-data: la edición JSON de nombre y teléfono sigue en
    PATCH /api/auth/profile/, sin mezclar formatos.

    Garantías:
    - la validación ocurre ANTES de tocar el archivo guardado: si la
      subida falla, la foto anterior se conserva intacta;
    - al reemplazar, el archivo viejo se borra sólo después de persistir
      el nuevo con éxito y sólo si la ruta corresponde a fotos de perfil;
    - nunca modifica rol, email ni demás campos protegidos.
    """

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FotoPerfilSerializer(
            data=request.data, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        archivo = serializer.validated_data['foto']  # ya normalizado (≤512×512)

        usuario = request.user
        nombre_anterior = usuario.foto.name  # '' si no había foto

        try:
            # save() escribe el archivo con el nombre único de
            # ruta_foto_perfil; save=False evita escribir la fila todavía.
            usuario.foto.save(archivo.name, archivo, save=False)
            usuario.save(update_fields=['foto'])
        except Exception:
            # Reversión: si el archivo nuevo llegó a escribirse, se borra y
            # el usuario conserva su foto anterior (no se pierde nada).
            nuevo_nombre = usuario.foto.name
            if nuevo_nombre and nuevo_nombre != nombre_anterior:
                try:
                    usuario.foto.storage.delete(nuevo_nombre)
                except OSError:
                    pass
                usuario.foto.name = nombre_anterior
            raise

        # Éxito: recién ahora se elimina el archivo reemplazado. Sólo se
        # borra bajo perfiles/ (los archivos propios por construcción).
        if nombre_anterior and nombre_anterior != usuario.foto.name:
            if nombre_anterior.startswith('perfiles/'):
                try:
                    usuario.foto.storage.delete(nombre_anterior)
                except OSError:
                    pass

        return Response(
            UserSerializer(usuario, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request):
        usuario = request.user
        if not usuario.foto:
            return Response(
                {'detail': 'No tenés una foto de perfil para eliminar.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Se limpia el campo primero: si el borrado del archivo fallara,
        # quedaría un archivo huérfano (inofensivo) y no un apuntador roto.
        storage = usuario.foto.storage
        nombre = usuario.foto.name
        usuario.foto = ''
        usuario.save(update_fields=['foto'])
        if nombre.startswith('perfiles/'):
            try:
                storage.delete(nombre)
            except OSError:
                pass

        return Response(
            UserSerializer(usuario, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'


class LogoutView(APIView):
    """Revoca el refresh token enviado (lo agrega a la blacklist).

    El access token que autentica la petición NO queda invalidado: sigue
    siendo válido hasta su expiración (1 hora por defecto).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get('refresh')
        if not refresh or not isinstance(refresh, str):
            return Response(
                {'detail': 'Se requiere el refresh token en el campo "refresh".'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh)
            # Solo el dueño del refresh puede revocarlo: evita que cualquier
            # usuario autenticado invalide tokens ajenos si los obtiene.
            if str(token.payload.get(jwt_settings.USER_ID_CLAIM)) != str(
                request.user.pk
            ):
                return Response(
                    {'detail': 'Token inválido o revocado.'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            token.blacklist()
        except (TokenError, InvalidToken):
            return Response(
                {'detail': 'Token inválido o revocado.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_destroy(self, instance):
        """Un usuario con turnos no se elimina (historial incluido).

        Mismo criterio que el Django Admin (B4): el ``CASCADE`` de
        ``Turno.usuario`` borraría también los turnos cancelados, que son
        parte del historial. Si el usuario no tiene turnos, la
        eliminación procede y un ``Profesional`` vinculado queda con
        ``usuario = None`` (``SET_NULL``), como hasta ahora. Los
        permisos actuales no cambian.
        """
        if instance.turnos.exists():
            raise DRFValidationError(
                'No se puede eliminar el usuario: tiene turnos asociados.'
            )
        super().perform_destroy(instance)


class ClienteViewSet(viewsets.ModelViewSet):
    """Gestión de cuentas CLIENTE para el panel administrativo (B10.3).

    Endpoints: listado y detalle de cuentas con rol CLIENTE, historial de
    turnos de una clienta (``GET /api/clientas/{id}/turnos/``) y
    activación / desactivación vía ``is_active`` (``PATCH``).

    Reglas del módulo (el backend es la autoridad):

    - acceso exclusivo de administradores (staff o rol ADMIN: ``IsAdmin``);
    - el queryset sólo contiene cuentas CLIENTE: las cuentas ADMIN y
      PERSONAL no son consultables ni modificables desde acá (los
      identificadores manipulados devuelven 404);
    - sin borrado físico ni altas: ``DELETE`` y ``POST`` no están
      admitidos (405). El alta de clientas es el registro público y la
      baja se hace con ``is_active=False``;
    - ``role`` es de sólo lectura: este módulo no cambia roles;
    - un administrador no puede desactivarse a sí mismo (400);
    - consultar el historial no modifica los turnos (sólo lectura).

    Se crea como endpoint dedicado (y no se reutiliza ``/api/users/``)
    porque ese ViewSet exige ``is_staff`` (el rol ADMIN de la aplicación
    no lo es), su serializer permite cambiar ``role``, no expone
    ``is_active`` y sus tests de integridad fijan el comportamiento
    actual de DELETE.
    """

    queryset = User.objects.filter(role=User.Roles.CLIENTE).order_by(
        'nombre', 'username'
    )
    serializer_class = ClienteAdminSerializer
    permission_classes = [IsAdmin]
    # Sólo consulta y activación/desactivación: ni POST (el alta es el
    # registro público) ni DELETE (la baja es is_active=False).
    http_method_names = ['get', 'patch', 'head', 'options']

    def perform_update(self, serializer):
        """Impide que un administrador se desactive a sí mismo."""
        nuevo_estado = serializer.validated_data.get(
            'is_active', serializer.instance.is_active
        )
        if serializer.instance.pk == self.request.user.pk and not nuevo_estado:
            raise DRFValidationError(
                'No podés desactivar tu propia cuenta desde la gestión de clientas.'
            )
        serializer.save()

    @action(detail=True, methods=['get'])
    def turnos(self, request, pk=None):
        """Historial de turnos de la clienta, acotado a su cuenta.

        El identificador de la URL se valida contra el queryset de
        cuentas CLIENTE (404 si no corresponde) y el permiso de acceso
        es el mismo del módulo (``IsAdmin``): un identificador
        manipulado no expone información no autorizada. La consulta es
        de sólo lectura y conserva estados y relaciones originales.
        """
        cliente = self.get_object()
        qs = (
            Turno.objects.filter(usuario=cliente)
            .select_related('usuario', 'servicio', 'profesional')
            .order_by('-fecha', '-hora')
        )
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = TurnoSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(TurnoSerializer(qs, many=True).data)
