"""B11.2 — foto de perfil persistente (POST/DELETE /api/auth/profile/foto/).

Cubre el ciclo completo de la foto:

- subida exitosa para los tres roles con persistencia en disco y URL
  devuelta en el perfil;
- normalización (máximo 512×512, orientación EXIF);
- reemplazo con limpieza del archivo anterior;
- eliminación de la foto propia;
- validaciones: límite de 2 MB, formatos admitidos (JPEG/PNG/WebP),
  archivos corruptos o que no son imágenes;
- seguridad: autenticación requerida, el endpoint no acepta elegir a
  otro usuario, campos protegidos intactos y foto anterior conservada
  cuando una subida falla.

Los medios de los tests viven en un MEDIA_ROOT temporal por test
(``setUp`` + ``addCleanup``): no se escribe nada en el almacenamiento
real del proyecto.
"""

import io
import os
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import FileSystemStorage
from django.test import override_settings
from django.urls import reverse

from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

from users.models import User

CONTENT_TYPES = {
    'JPEG': 'image/jpeg',
    'PNG': 'image/png',
    'WEBP': 'image/webp',
    'GIF': 'image/gif',
}


def imagen_bytes(formato='JPEG', tamano=(1600, 1200), modo='RGB',
                 color=(200, 30, 120), exif=None, ruido=False):
    """Genera bytes reales de una imagen con Pillow para los tests."""
    if ruido:
        # Ruido incompresible: garantiza un archivo grande (para el límite
        # de 2 MB) sin depender de la compresión del formato.
        ancho, alto = tamano
        img = Image.frombytes('RGB', (ancho, alto), os.urandom(ancho * alto * 3))
    else:
        img = Image.new(modo, tamano, color)
    buf = io.BytesIO()
    kwargs = {'format': formato}
    if exif is not None:
        kwargs['exif'] = exif
    img.save(buf, **kwargs)
    return buf.getvalue()


def subida(nombre, formato='JPEG', content_type=None, **kwargs):
    return SimpleUploadedFile(
        nombre,
        imagen_bytes(formato=formato, **kwargs),
        content_type=content_type or CONTENT_TYPES[formato],
    )


class BaseFotoPerfilTests(APITestCase):
    """MEDIA_ROOT temporal por test + una cuenta por rol."""

    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix='hn_fotos_test_')
        self._override = override_settings(MEDIA_ROOT=self.media_root)
        self._override.enable()
        self.addCleanup(self._override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)

        self.cliente = self.crear('carla', 'carla@holy.test', User.Roles.CLIENTE)
        self.personal = self.crear('maria', 'maria@holy.test', User.Roles.PERSONAL)
        self.admin = self.crear('admin', 'admin@holy.test', User.Roles.ADMIN)
        self.url = reverse('profile-foto')

    @staticmethod
    def crear(username, email, role):
        return User.objects.create_user(
            username=username,
            email=email,
            password='pass1234',
            nombre=username.title(),
            role=role,
        )

    def ruta_en_disco(self, usuario):
        return os.path.join(self.media_root, usuario.foto.name)

    def subir(self, usuario, archivo, **extras):
        self.client.force_authenticate(user=usuario)
        datos = {'foto': archivo}
        datos.update(extras)
        return self.client.post(self.url, datos, format='multipart')

    def eliminar(self, usuario):
        self.client.force_authenticate(user=usuario)
        return self.client.delete(self.url)


class SubidaTests(BaseFotoPerfilTests):
    """Subida exitosa, persistencia y URL devuelta."""

    @override_settings(PROFILE_PHOTO_UPLOAD_ENABLED=False)
    def test_subida_deshabilitada_responde_503_sin_guardar_archivos(self):
        resp = self.subir(self.cliente, subida('avatar.jpg'))

        self.assertEqual(
            resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE, resp.data
        )
        self.assertIn('no está habilitada', resp.data['detail'])
        self.assertEqual(os.listdir(self.media_root), [])
        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.foto)

    def test_subida_exitosa_persiste_la_foto_y_devuelve_su_url(self):
        resp = self.subir(self.cliente, subida('avatar.jpg'))

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.foto)
        self.assertTrue(self.cliente.foto.name.startswith('perfiles/'))
        self.assertIn('/media/perfiles/', resp.data['foto_url'])
        # El archivo existe realmente en disco (no es sólo un preview).
        self.assertTrue(os.path.exists(self.ruta_en_disco(self.cliente)))

    def test_el_profile_get_incluye_la_url_de_la_foto(self):
        self.subir(self.cliente, subida('avatar.jpg'))
        self.client.force_authenticate(user=self.cliente)

        resp = self.client.get(reverse('profile'))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('/media/perfiles/', resp.data['foto_url'])
        self.assertIn('http://testserver/media/', resp.data['foto_url'])

    def test_sin_foto_el_profile_devuelve_foto_url_nulo(self):
        self.client.force_authenticate(user=self.cliente)
        resp = self.client.get(reverse('profile'))
        self.assertIsNone(resp.data['foto_url'])

    def test_los_tres_roles_pueden_subir_su_foto(self):
        for rol, usuario in (('CLIENTE', self.cliente),
                             ('PERSONAL', self.personal),
                             ('ADMIN', self.admin)):
            with self.subTest(rol=rol):
                resp = self.subir(usuario, subida('foto.jpg'))
                self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
                usuario.refresh_from_db()
                self.assertTrue(usuario.foto)
                self.assertTrue(os.path.exists(self.ruta_en_disco(usuario)))

    def test_una_foto_grande_se_normaliza_a_como_maximo_512(self):
        resp = self.subir(self.cliente, subida('grande.png', formato='PNG',
                                               tamano=(2048, 1536)))
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

        self.cliente.refresh_from_db()
        with Image.open(self.ruta_en_disco(self.cliente)) as img:
            ancho, alto = img.size
        self.assertLessEqual(ancho, 512)
        self.assertLessEqual(alto, 512)
        # Proporción original 4:3 conservada: 512×384.
        self.assertEqual((ancho, alto), (512, 384))

    def test_se_aplica_la_orientacion_exif(self):
        # 800×400 (horizontal) con orientación EXIF 6 → debe guardarse
        # rotado como 400×800 (vertical).
        exif = Image.Exif()
        exif[0x0112] = 6
        resp = self.subir(
            self.cliente,
            subida('celular.jpg', tamano=(800, 400), exif=exif),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

        self.cliente.refresh_from_db()
        with Image.open(self.ruta_en_disco(self.cliente)) as img:
            # Rotada a 400×800 (vertical) y luego ajustada al máximo de
            # 512 por lado → 256×512. Sin exif_transpose sería 512×256.
            self.assertEqual(img.size, (256, 512))

    def test_acepta_png_y_webp(self):
        for formato in ('PNG', 'WEBP'):
            with self.subTest(formato=formato):
                resp = self.subir(
                    self.cliente,
                    subida(f'foto.{formato.lower()}', formato=formato),
                )
                self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
                self.cliente.refresh_from_db()
                self.assertTrue(self.cliente.foto)


class ReemplazoYBorradoTests(BaseFotoPerfilTests):
    """Reemplazo con limpieza y eliminación de la foto propia."""

    def test_reemplazar_la_foto_borra_el_archivo_anterior(self):
        self.subir(self.cliente, subida('una.jpg'))
        self.cliente.refresh_from_db()
        nombre_1 = self.cliente.foto.name
        ruta_1 = self.ruta_en_disco(self.cliente)

        resp = self.subir(self.cliente, subida('dos.png', formato='PNG'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.cliente.refresh_from_db()

        self.assertNotEqual(self.cliente.foto.name, nombre_1)
        self.assertFalse(os.path.exists(ruta_1))          # viejo eliminado
        self.assertTrue(os.path.exists(self.ruta_en_disco(self.cliente)))

    def test_eliminar_la_foto_borra_el_archivo_y_limpia_el_campo(self):
        self.subir(self.cliente, subida('una.jpg'))
        self.cliente.refresh_from_db()
        ruta = self.ruta_en_disco(self.cliente)

        resp = self.eliminar(self.cliente)

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.foto)
        self.assertFalse(os.path.exists(ruta))
        self.assertIsNone(resp.data['foto_url'])

    def test_eliminar_sin_foto_devuelve_400(self):
        resp = self.eliminar(self.cliente)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_fallo_al_guardar_referencia_conserva_foto_anterior_y_limpia_nueva(self):
        self.subir(self.cliente, subida('original.jpg'))
        self.cliente.refresh_from_db()
        anterior = self.cliente.foto.name
        ruta_anterior = self.ruta_en_disco(self.cliente)
        self.client.raise_request_exception = False

        with patch.object(User, 'save', side_effect=RuntimeError('db error')):
            resp = self.subir(self.cliente, subida('nueva.png', formato='PNG'))

        self.assertEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.foto.name, anterior)
        self.assertTrue(os.path.exists(ruta_anterior))
        self.assertEqual(os.listdir(os.path.join(self.media_root, 'perfiles')),
                         [os.path.basename(anterior)])

    def test_fallo_de_subida_durante_storage_conserva_foto_anterior(self):
        self.subir(self.cliente, subida('original.jpg'))
        self.cliente.refresh_from_db()
        anterior = self.cliente.foto.name
        ruta_anterior = self.ruta_en_disco(self.cliente)
        self.client.raise_request_exception = False

        with patch.object(
            FileSystemStorage, '_save', side_effect=OSError('storage unavailable')
        ):
            resp = self.subir(self.cliente, subida('nueva.jpg'))

        self.assertEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.foto.name, anterior)
        self.assertTrue(os.path.exists(ruta_anterior))

    def test_fallo_al_borrar_asset_remoto_limpia_referencia_y_responde_exito(self):
        self.subir(self.cliente, subida('original.jpg'))
        self.cliente.refresh_from_db()
        ruta_anterior = self.ruta_en_disco(self.cliente)

        with patch.object(
            FileSystemStorage, 'delete', side_effect=OSError('storage unavailable')
        ):
            resp = self.eliminar(self.cliente)

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.foto)
        # El borrado remoto fallido deja un huérfano recuperable, no una
        # referencia inválida guardada en el perfil.
        self.assertTrue(os.path.exists(ruta_anterior))


class ValidacionTests(BaseFotoPerfilTests):
    """Límites y contenido real de los archivos."""

    def test_rechaza_archivo_mayor_a_2mb(self):
        grande = subida('grande.png', formato='PNG', tamano=(1200, 1200),
                        ruido=True)
        self.assertGreater(grande.size, 2 * 1024 * 1024)

        resp = self.subir(self.cliente, grande)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('2 MB', str(resp.data['foto']))
        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.foto)

    def test_rechaza_formato_no_admitido(self):
        resp = self.subir(self.cliente, subida('animada.gif', formato='GIF',
                                               tamano=(100, 100)))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Formato no admitido', str(resp.data['foto']))
        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.foto)

    def test_rechaza_archivo_corrupto(self):
        basura = SimpleUploadedFile(
            'rota.jpg',
            b'\xff\xd8\xff\xe0basura basura basura basura',
            content_type='image/jpeg',
        )
        resp = self.subir(self.cliente, basura)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('foto', resp.data)
        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.foto)

    def test_rechaza_un_archivo_que_no_es_imagen(self):
        texto = SimpleUploadedFile(
            'noimagen.png',
            b'esto es un archivo de texto con extension de imagen',
            content_type='image/png',
        )
        resp = self.subir(self.cliente, texto)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('foto', resp.data)
        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.foto)

    def test_una_subida_fallida_conserva_la_foto_anterior(self):
        self.subir(self.cliente, subida('original.jpg'))
        self.cliente.refresh_from_db()
        nombre_anterior = self.cliente.foto.name
        ruta_anterior = self.ruta_en_disco(self.cliente)

        # Falla en validación: no se toca nada de lo guardado.
        resp = self.subir(self.cliente, subida('mala.gif', formato='GIF'))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.foto.name, nombre_anterior)
        self.assertTrue(os.path.exists(ruta_anterior))


class SeguridadTests(BaseFotoPerfilTests):
    """Autenticación, alcance por usuario y campos protegidos."""

    def test_requiere_autenticacion_para_subir(self):
        resp = self.client.post(
            self.url, {'foto': subida('foto.jpg')}, format='multipart',
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_requiere_autenticacion_para_eliminar(self):
        resp = self.client.delete(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_permite_modificar_la_foto_de_otro_usuario(self):
        # El endpoint ignora cualquier identificador enviado: sólo opera
        # sobre request.user, así que el admin queda intacto.
        resp = self.subir(
            self.cliente,
            subida('mia.jpg'),
            user=str(self.admin.pk),
            id=str(self.admin.pk),
            username='admin',
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.foto)
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.foto)
        self.assertEqual(resp.data['id'], self.cliente.pk)

    def test_subir_foto_no_modifica_campos_protegidos(self):
        resp = self.subir(
            self.cliente,
            subida('foto.jpg'),
            role='ADMIN',
            email='nuevo@holy.test',
            nombre='Nombre Hackeado',
            telefono='999 999 999',
            is_staff='True',
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.role, User.Roles.CLIENTE)
        self.assertEqual(self.cliente.email, 'carla@holy.test')
        self.assertEqual(self.cliente.nombre, 'Carla')
        self.assertEqual(self.cliente.telefono, '')
        self.assertFalse(self.cliente.is_staff)
        # La respuesta devuelve el perfil real, sin datos alterados.
        self.assertEqual(resp.data['email'], 'carla@holy.test')

    def test_eliminar_no_modifica_campos_protegidos(self):
        self.subir(self.cliente, subida('foto.jpg'))
        resp = self.eliminar(self.cliente)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.role, User.Roles.CLIENTE)
        self.assertEqual(self.cliente.email, 'carla@holy.test')
        self.assertEqual(self.cliente.nombre, 'Carla')
