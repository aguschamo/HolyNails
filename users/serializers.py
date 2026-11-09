import re
from io import BytesIO

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from PIL import Image, ImageOps, UnidentifiedImageError

from .invariantes import validar_rollo_d3
from .models import User

# B11.2 — límites de la foto de perfil.
LIMITE_FOTO_BYTES = 2 * 1024 * 1024  # 2 MB
FORMATOS_FOTO_PERMITIDOS = ('JPEG', 'PNG', 'WEBP')
LADO_MAXIMO_FOTO = 512



class UserSerializer(serializers.ModelSerializer):
    """Datos del usuario para el endpoint de perfil (ProfileView).

    `role` es de solo lectura: el rol no se modifica vía perfil, de modo que
    un usuario autenticado no puede auto-escalarse (ej: CLIENTE -> ADMIN).
    La gestión de roles autorizada vive en AdminUserSerializer, usada
    exclusivamente por UserViewSet (IsAdminUser).

    `email` valida unicidad con el mismo criterio que RegisterSerializer:
    no puede cambiarse por el email de otra cuenta, pero sí conservarse el
    propio (UniqueValidator excluye la instancia en actualizaciones).
    Se conservan `required=False` y `allow_blank=True` para no alterar el
    comportamiento existente del PUT /api/auth/profile/.
    """

    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        validators=[UniqueValidator(queryset=User.objects.all())],
    )
    # B11.2: URL pública de la foto persistida. Sólo lectura: la subida y
    # el borrado viven en ProfileFotoView (multipart), nunca en el PATCH
    # JSON de nombre/teléfono.
    foto_url = serializers.SerializerMethodField(read_only=True)
    es_profesional = serializers.SerializerMethodField(read_only=True)
    profesional_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'nombre', 'telefono', 'foto_url',
            'role', 'es_profesional', 'profesional_id',
        )
        read_only_fields = ('foto_url', 'role', 'es_profesional', 'profesional_id')

    def get_foto_url(self, obj):
        """URL de la foto (absoluta con request; sin contexto, relativa).

        Devuelve ``None`` cuando el usuario no tiene foto, para que el
        frontend distinga «sin foto» de «foto no cargada».
        """
        if not obj.foto:
            return None
        url = obj.foto.url
        request = self.context.get('request')
        if request is not None:
            return request.build_absolute_uri(url)
        return url

    def get_es_profesional(self, obj):
        profesional = getattr(obj, 'profesional', None)
        return profesional is not None and profesional.is_active

    def get_profesional_id(self, obj):
        profesional = getattr(obj, 'profesional', None)
        return profesional.id if (profesional and profesional.is_active) else None

    def validate_telefono(self, value):
        """Teléfono opcional: números y símbolos habituales, sin texto.

        B11.1: el valor se guarda recortado; un campo vacío limpia el
        teléfono (el modelo lo permite con ``blank=True``).
        """
        value = (value or '').strip()
        if value and not re.fullmatch(r'[0-9\s()+.-]{2,30}', value):
            raise serializers.ValidationError(
                'El teléfono sólo puede contener números, espacios y los '
                'símbolos + - ( ) .'
            )
        return value


class FotoPerfilSerializer(serializers.Serializer):
    """Valida y normaliza la foto subida a POST /api/auth/profile/foto/.

    El archivo que devuelve ya está procesado: orientación EXIF aplicada,
    tamaño máximo 512×512 conservando proporción y re-codificado a un
    formato admitido (PNG si conserva transparencia, JPEG en caso
    contrario). El nombre lo fija el backend vía ``ruta_foto_perfil``.
    """

    foto = serializers.ImageField(help_text='JPEG, PNG o WebP de hasta 2 MB.')

    def validate_foto(self, archivo):
        # 0) Posición inicial: la validación de Django/DRF pudo dejar el
        #    puntero al final del archivo.
        archivo.seek(0)

        # 1) Tamaño: límite duro antes de hacer cualquier proceso.
        if archivo.size > LIMITE_FOTO_BYTES:
            raise serializers.ValidationError(
                'La imagen no puede superar los 2 MB.'
            )

        # 2) Contenido real con Pillow: no se confía en la extensión ni en
        #    el MIME declarado por el navegador.
        try:
            with Image.open(archivo) as img:
                formato_real = img.format  # detectado por Pillow
                img.verify()
        except (UnidentifiedImageError, OSError, SyntaxError):
            raise serializers.ValidationError(
                'El archivo no es una imagen válida.'
            )

        if formato_real not in FORMATOS_FOTO_PERMITIDOS:
            raise serializers.ValidationError(
                'Formato no admitido. Usá una imagen JPEG, PNG o WebP.'
            )

        # 3) Normalización: verify() dejó el handle inutilizable, se reabre.
        archivo.seek(0)
        try:
            with Image.open(archivo) as img:
                # Orientación EXIF (fotos de celular rotadas).
                img = ImageOps.exif_transpose(img)
                # Redimensiona a como máximo 512×512 conservando proporción.
                img.thumbnail((LADO_MAXIMO_FOTO, LADO_MAXIMO_FOTO), Image.Resampling.LANCZOS)

                con_alfa = (
                    img.mode in ('RGBA', 'LA', 'PA')
                    or (img.mode == 'P' and 'transparency' in img.info)
                )
                if con_alfa:
                    img = img.convert('RGBA')
                    formato_salida, ext = 'PNG', 'png'
                else:
                    if img.mode not in ('RGB', 'L'):
                        img = img.convert('RGB')
                    formato_salida, ext = 'JPEG', 'jpg'

                buffer = BytesIO()
                if formato_salida == 'JPEG':
                    img.save(buffer, format='JPEG', quality=85, optimize=True)
                else:
                    img.save(buffer, format='PNG', optimize=True)
        except (OSError, ValueError):
            raise serializers.ValidationError(
                'La imagen está dañada o no se pudo procesar.'
            )

        # ContentFile con nombre controlado por el backend (la ruta final
        # genera el nombre único en ruta_foto_perfil).
        buffer.seek(0)
        return ContentFile(buffer.getvalue(), name=f'perfil.{ext}')


class AdminUserSerializer(UserSerializer):
    """Gestión administrativa de usuarios (UserViewSet, IsAdminUser).

    Único serializer API que permite modificar `role`; al estar protegido
    por IsAdminUser, solo el staff de Django puede usarlo.

    Valida además el invariante PERSONAL–Profesional (D3):

    - no se crea ni se asigna el rol PERSONAL sin un Profesional vinculado
      (el alta correcta es ``POST /api/profesionales/crear-con-usuario/``);
    - no se cambia el rol de una cuenta que conserve su Profesional
      vinculado (en particular, PERSONAL -> CLIENTE está prohibido); el
      no-op de guardar el mismo rol está permitido para cuentas vinculadas
      PERSONAL o ADMIN (B10.0.2: una ADMIN con Profesional conserva su
      rol).
    """

    role = serializers.ChoiceField(choices=User.Roles.choices, required=False)

    def validate_role(self, value):
        # Invariante D3 compartido con el Django Admin (users/invariantes.py):
        # una única implementación para API y panel administrativo.
        try:
            return validar_rollo_d3(self.instance, value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)



class ClienteAdminSerializer(UserSerializer):
    """Listado, detalle y activación de cuentas CLIENTE (B10.3).

    Serializer del módulo «Clientas» del panel administrativo
    (``/api/clientas/``). Expone sólo los datos visibles para la
    administración de cuentas CLIENTE: nunca la contraseña ni campos
    internos de autenticación. ``role`` es de sólo lectura (siempre
    CLIENTE en este endpoint): este módulo no cambia roles. El único
    campo escribible es ``is_active``, para la activación /
    desactivación de cuentas sin borrado físico.
    """

    # De sólo lectura acá: por sobre los campos declarados en
    # UserSerializer, para que el módulo no pueda alterar el email.
    email = serializers.EmailField(read_only=True)

    class Meta(UserSerializer.Meta):
        fields = ('id', 'username', 'email', 'nombre', 'role', 'is_active')
        read_only_fields = ('id', 'username', 'nombre', 'role')


class CuentaVinculableSerializer(serializers.ModelSerializer):
    """Cuentas sin vínculo profesional, candidatas a asociar (A3).

    Listado de sólo lectura para el módulo «Profesionales» del panel
    administrativo (``GET /api/profesionales/cuentas-disponibles/``):
    expone sólo datos ya existentes para distinguir las cuentas
    disponibles (username, nombre, email, rol y estado). Nunca la
    contraseña ni campos internos de autenticación. La asociación en sí
    entra por ``PATCH /api/profesionales/{id}/`` con el campo
    ``usuario`` (``ProfesionalSerializer`` valida el OneToOne, el vínculo
    inmutable D3 y la promoción de rol).
    """

    class Meta:
        model = User
        fields = ('id', 'username', 'nombre', 'email', 'role', 'is_active')
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all())]
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'nombre')

    def validate_password(self, value):
        # Aplica AUTH_PASSWORD_VALIDATORS (settings) a través del validador
        # estándar de Django. Se construye un User NO persistido con los
        # datos del formulario para que UserAttributeSimilarityValidator
        # pueda comparar la contraseña con username, email, etc.
        user = User(
            username=self.initial_data.get('username', ''),
            email=self.initial_data.get('email', ''),
            nombre=self.initial_data.get('nombre', ''),
        )
        try:
            validate_password(value, user=user)
        except DjangoValidationError as exc:
            # exc.messages: mensajes genéricos de Django, sin datos
            # sensibles. Se devuelven bajo el campo 'password'.
            raise serializers.ValidationError(exc.messages)
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            nombre=validated_data.get('nombre', ''),
            role=User.Roles.CLIENTE,
        )
        return user


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    email = serializers.EmailField(required=False, allow_blank=True, default='')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[self.username_field].required = False
        self.fields[self.username_field].allow_blank = True

    def validate(self, data):
        email = (data.get('email') or '').strip()
        password = data.get('password', '')

        if email:
            user = User.objects.filter(email__iexact=email).first()
            if user is not None and user.is_active and user.check_password(password):
                refresh = self.get_token(user)
                return {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            raise AuthenticationFailed(
                self.error_messages['no_active_account'],
                'no_active_account',
            )

        if not data.get(self.username_field):
            raise serializers.ValidationError({
                self.username_field: ['This field is required.'],
            })
        return super().validate(data)
