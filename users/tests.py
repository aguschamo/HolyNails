from datetime import timedelta

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

from .models import User


class AuthJWTTestCase(APITestCase):
    def setUp(self):
        cache.clear()
        self.password = 'Passw0rd-123'
        self.user = User.objects.create_user(
            username='cliente1',
            email='cliente1@holy.test',
            password=self.password,
            nombre='Cliente Uno',
            role=User.Roles.CLIENTE,
        )
        self.username = self.user.username
        self.login_url = reverse('token_obtain_pair')
        self.refresh_url = reverse('token_refresh')
        self.logout_url = reverse('logout')
        self.profile_url = reverse('profile')

    def login(self, **extra):
        payload = {'email': self.user.email, 'password': self.password}
        payload.update(extra)
        return self.client.post(self.login_url, payload, format='json')

    # ---------------------------------------------------------- login

    def test_login_email_valido_devuelve_tokens(self):
        res = self.login()
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.content)
        self.assertIn('access', res.data)
        self.assertIn('refresh', res.data)

    def test_login_username_valido_devuelve_tokens(self):
        res = self.login(email='', username=self.username)
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.content)

    def test_login_password_incorrecta_401(self):
        res = self.login(password='otra-password')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_email_inexistente_401(self):
        res = self.login(email='noexiste@holy.test')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_con_access_valido(self):
        tokens = self.login().data
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
        res = self.client.get(self.profile_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['email'], self.user.email)

    # -------------------------------------------------------- refresh

    def test_refresh_valido_devuelve_access_y_refresh_nuevo(self):
        refresh = self.login().data['refresh']
        res = self.client.post(self.refresh_url, {'refresh': refresh}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.content)
        self.assertIn('access', res.data)
        # Rotación habilitada: viene un refresh nuevo
        self.assertIn('refresh', res.data)
        self.assertNotEqual(res.data['refresh'], refresh)

    def test_refresh_rotado_no_se_puede_reutilizar(self):
        refresh = self.login().data['refresh']
        res1 = self.client.post(self.refresh_url, {'refresh': refresh}, format='json')
        self.assertEqual(res1.status_code, status.HTTP_200_OK, res1.content)
        # El refresh original fue rotado y puesto en la blacklist
        res2 = self.client.post(self.refresh_url, {'refresh': refresh}, format='json')
        self.assertEqual(res2.status_code, status.HTTP_401_UNAUTHORIZED)
        # El refresh nuevo (rotado) sí funciona
        res3 = self.client.post(
            self.refresh_url, {'refresh': res1.data['refresh']}, format='json'
        )
        self.assertEqual(res3.status_code, status.HTTP_200_OK, res3.content)

    def test_refresh_invalido_401(self):
        res = self.client.post(
            self.refresh_url, {'refresh': 'esto-no-es-un-jwt'}, format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_vencido_401(self):
        refresh = RefreshToken.for_user(self.user)
        refresh.set_exp(from_time=timezone.now() - timedelta(days=30))
        res = self.client.post(
            self.refresh_url, {'refresh': str(refresh)}, format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_firmado_con_otra_clave_401(self):
        refresh = RefreshToken.for_user(self.user)
        payload = refresh.payload
        payload['sub'] = str(self.user.pk)
        import jwt as pyjwt

        token = pyjwt.encode(
            payload, 'otra-clave-secreta-totalmente-distinta', algorithm='HS256'
        )
        res = self.client.post(self.refresh_url, {'refresh': token}, format='json')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # --------------------------------------------------------- logout

    def test_logout_revoca_el_refresh(self):
        tokens = self.login().data
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
        res = self.client.post(
            self.logout_url, {'refresh': tokens['refresh']}, format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT, res.content)
        # El refresh revocado no puede usarse para obtener tokens nuevos
        res2 = self.client.post(
            self.refresh_url, {'refresh': tokens['refresh']}, format='json'
        )
        self.assertEqual(res2.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_pone_el_refresh_en_la_blacklist(self):
        tokens = self.login().data
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
        self.client.post(self.logout_url, {'refresh': tokens['refresh']}, format='json')
        self.assertTrue(BlacklistedToken.objects.exists())

    def test_logout_access_sigue_valido_hasta_expirar(self):
        # Comportamiento documentado: la blacklist revoca el refresh, no el
        # access ya emitido. Se agrega este test para que un cambio futuro
        # de esta semántica rompa de forma explícita.
        tokens = self.login().data
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
        self.client.post(self.logout_url, {'refresh': tokens['refresh']}, format='json')
        res = self.client.get(self.profile_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_logout_sin_refresh_400(self):
        tokens = self.login().data
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
        res = self.client.post(self.logout_url, {}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        res2 = self.client.post(
            self.logout_url, {'refresh': ''}, format='json'
        )
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_con_refresh_invalido_401(self):
        tokens = self.login().data
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
        res = self.client.post(
            self.logout_url, {'refresh': 'token-basura'}, format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_con_refresh_de_otro_usuario_401(self):
        # Un usuario autenticado no debe poder revocar el refresh de otro.
        tokens = self.login().data
        other = User.objects.create_user(
            username='otra', email='otra@holy.test', password='x-Passw0rd-1'
        )
        other_refresh = str(RefreshToken.for_user(other))
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
        res = self.client.post(
            self.logout_url, {'refresh': other_refresh}, format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        # El refresh del otro usuario no quedó revocado
        self.assertFalse(BlacklistedToken.objects.exists())

    def test_logout_sin_autenticacion_401(self):
        tokens = self.login().data
        res = self.client.post(
            self.logout_url, {'refresh': tokens['refresh']}, format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        # El refresh NO fue revocado: sin access no hay logout
        res2 = self.client.post(
            self.refresh_url, {'refresh': tokens['refresh']}, format='json'
        )
        self.assertEqual(res2.status_code, status.HTTP_200_OK)

    def test_logout_refresh_ya_revocado_401(self):
        tokens = self.login().data
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
        res1 = self.client.post(
            self.logout_url, {'refresh': tokens['refresh']}, format='json'
        )
        self.assertEqual(res1.status_code, status.HTTP_204_NO_CONTENT)
        res2 = self.client.post(
            self.logout_url, {'refresh': tokens['refresh']}, format='json'
        )
        self.assertEqual(res2.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token_negro_lanza_token_error(self):
        # Contrato de simplejwt que LogoutView aprovecha: construir un
        # RefreshToken ya blacklisteado lanza TokenError, no una excepción
        # no controlada.
        refresh = RefreshToken.for_user(self.user)
        refresh.blacklist()
        with self.assertRaises(TokenError):
            RefreshToken(str(refresh))


class AuthPasswordValidationTestCase(APITestCase):
    """El backend aplica AUTH_PASSWORD_VALIDATORS en el registro."""

    def setUp(self):
        cache.clear()
        self.register_url = reverse('register')
        self.login_url = reverse('token_obtain_pair')

    def register(self, **extra):
        payload = {
            'username': 'nuevaclienta',
            'email': 'nueva@holy.test',
            'password': 'x',
            'nombre': 'Nueva Clienta',
        }
        payload.update(extra)
        return self.client.post(self.register_url, payload, format='json')

    def test_password_demasiado_corta(self):
        res = self.register(password='Ab1!')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', res.data)
        # Mensaje genérico de Django, sin datos sensibles
        self.assertIn('8', res.data['password'][0])

    def test_password_solo_numerica(self):
        res = self.register(password='1234567890')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', res.data)

    def test_password_comun(self):
        res = self.register(password='password123')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', res.data)

    def test_password_similar_al_username(self):
        res = self.register(
            username='marilina',
            email='marilina@holy.test',
            password='marilina2024',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', res.data)

    def test_password_no_expone_datos_sensibles(self):
        res = self.register(password='123')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        # La respuesta solo contiene el campo y mensajes estáticos
        self.assertEqual(list(res.data.keys()), ['password'])
        joined = ' '.join(res.data['password'])
        for secret in ('secret', 'SECRET_KEY', 'Traceback', 'sql'):
            self.assertNotIn(secret, joined)

    def test_password_valida_registra_y_permite_login(self):
        password = 'Passw0rd-xyz!'
        res = self.register(password=password)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.content)
        # create_user hashea: el usuario queda activo y el login funciona
        res2 = self.client.post(
            self.login_url,
            {'email': 'nueva@holy.test', 'password': password},
            format='json',
        )
        self.assertEqual(res2.status_code, status.HTTP_200_OK, res2.content)
        self.assertIn('access', res2.data)

    def test_contraseñas_débiles_no_crearán_usuario(self):
        self.register(password='123')
        self.assertFalse(User.objects.filter(email='nueva@holy.test').exists())


class AuthThrottleTestCase(APITestCase):
    """ScopedRateThrottle solo en login y registro.

    Determinismo: el throttle usa el cache (LocMem por defecto). Cada test
    empieza con cache.clear() en setUp; las tasas se alcanzan con peticiones
    secuenciales desde la misma IP (127.0.0.1), sin control de tiempo
    necesario porque el test no avanza el reloj dentro de la ventana.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='thr',
            email='thr@holy.test',
            password='Passw0rd-123',
        )
        self.login_url = reverse('token_obtain_pair')
        self.register_url = reverse('register')
        self.servicios_url = reverse('servicio-list')

    def test_login_supera_el_limite_y_devuelve_429(self):
        for _ in range(5):
            res = self.client.post(
                self.login_url,
                {'email': self.user.email, 'password': 'mala'},
                format='json',
            )
            self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        res = self.client.post(
            self.login_url,
            {'email': self.user.email, 'password': 'mala'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('Retry-After', res)

    def test_login_exitoso_también_consumela_cuota(self):
        # Comportamiento documentado de ScopedRateThrottle: la cuota se
        # consume por petición, no por fallo. Un humano equivocándose un
        # par de veces sigue estando muy por debajo de 5/min.
        for _ in range(5):
            res = self.client.post(
                self.login_url,
                {'email': self.user.email, 'password': 'Passw0rd-123'},
                format='json',
            )
            self.assertEqual(res.status_code, status.HTTP_200_OK)
        res = self.client.post(
            self.login_url,
            {'email': self.user.email, 'password': 'Passw0rd-123'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_registro_supera_el_limite_y_devuelve_429(self):
        for i in range(10):
            res = self.client.post(
                self.register_url,
                {
                    'username': f'user{i}',
                    'email': f'user{i}@holy.test',
                    'password': 'Passw0rd-xyz!',
                    'nombre': f'User {i}',
                },
                format='json',
            )
            self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.content)
        res = self.client.post(
            self.register_url,
            {
                'username': 'user10',
                'email': 'user10@holy.test',
                'password': 'Passw0rd-xyz!',
                'nombre': 'User 10',
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertFalse(User.objects.filter(username='user10').exists())

    def test_endpoints_ajenos_no_quedan_limitados(self):
        # Agota la cuota de login...
        for _ in range(6):
            self.client.post(
                self.login_url,
                {'email': self.user.email, 'password': 'mala'},
                format='json',
            )
        res_limited = self.client.post(
            self.login_url,
            {'email': self.user.email, 'password': 'mala'},
            format='json',
        )
        self.assertEqual(res_limited.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        # ...y los demás endpoints siguen respondiendo con normalidad
        res_servicios = self.client.get(self.servicios_url)
        self.assertEqual(res_servicios.status_code, status.HTTP_200_OK)
        res_refresh = self.client.post(
            reverse('token_refresh'), {'refresh': 'x'}, format='json'
        )
        # 401 (token inválido), no 429: el throttle no lo alcanza
        self.assertEqual(res_refresh.status_code, status.HTTP_401_UNAUTHORIZED)
