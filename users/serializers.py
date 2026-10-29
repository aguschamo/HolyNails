from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User



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

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'nombre', 'role')
        read_only_fields = ('role',)


class AdminUserSerializer(UserSerializer):
    """Gestión administrativa de usuarios (UserViewSet, IsAdminUser).

    Único serializer API que permite modificar `role`; al estar protegido
    por IsAdminUser, solo el staff de Django puede usarlo.
    """

    role = serializers.ChoiceField(choices=User.Roles.choices, required=False)



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
