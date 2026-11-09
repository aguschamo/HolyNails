"""Etapa B4 — integridad del Django Admin (core).

Verifica que el panel administrativo no pueda saltarse las reglas de
negocio de B1, B2, B3 y B3.1:

- turnos: ``estado`` fuera del formulario, transiciones solo por
  acciones explícitas (respetando estados y turnos ya comenzados),
  ediciones validadas (futuro, horario, activos, cobertura, solape,
  medianoche, propio turno excluido) y eliminación deshabilitada;
- disponibilidades: pasado de solo lectura, profesional inamovible,
  cobertura de turnos futuros en edición y borrado, altas futuras;
- profesionales: sin desactivación inconsistente ni borrado destructivo;
- servicios: duración estable con agenda activa, sin borrado huérfano,
  desactivación permitida (B1).

Tests nuevos (no reemplazan ni modifican los existentes).
"""

from datetime import time, timedelta

from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from core.admin import DisponibilidadAdmin, ServicioAdmin
from core.models import Disponibilidad, Profesional, Servicio, Turno

User = get_user_model()


class BaseAdminCoreTest(TestCase):
    """Superusuario logueado + fixtures mínimas para probar /admin/."""

    def setUp(self):
        self.root = User.objects.create_superuser(
            'root', 'root@test.com', 'RootPass123!'
        )
        self.client.force_login(self.root)
        self.cliente = User.objects.create_user(
            'cliente', 'cliente@test.com', 'ClientePass123!'
        )
        self.profesional = Profesional.objects.create(nombre='Pro A')
        self.servicio = Servicio.objects.create(
            nombre='Semi', duracion=timedelta(minutes=30), precio='5000.00'
        )
        # Fecha futura (neutra para la regla "hora ya pasada") con una
        # franja de cobertura 09:00-12:00.
        self.fecha = timezone.localdate() + timedelta(days=1)
        Disponibilidad.objects.create(
            profesional=self.profesional, fecha=self.fecha,
            hora_inicio=time(9, 0), hora_fin=time(12, 0),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def crear_turno(self, hora=time(9, 0), estado='pendiente', fecha=None,
                    servicio=None, profesional=None):
        return Turno.objects.create(
            fecha=self.fecha if fecha is None else fecha,
            hora=hora,
            usuario=self.cliente,
            servicio=self.servicio if servicio is None else servicio,
            profesional=self.profesional if profesional is None else profesional,
            estado=estado,
        )

    @staticmethod
    def mensajes(response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def ejecutar_accion(self, nombre, turnos):
        return self.client.post(
            reverse('admin:core_turno_changelist'),
            {
                'action': nombre,
                '_selected_action': [str(t.pk) for t in turnos],
            },
        )


class TurnoFormAdminTests(BaseAdminCoreTest):
    """Validaciones del formulario de altas y ediciones de turnos."""

    def datos(self, **campos):
        datos = {
            'fecha': self.fecha.isoformat(),
            'hora': '09:00:00',
            'usuario': self.cliente.pk,
            'servicio': self.servicio.pk,
            'profesional': self.profesional.pk,
        }
        datos.update(campos)
        return datos

    def test_alta_con_fecha_pasada_rechazada(self):
        resp = self.client.post(
            reverse('admin:core_turno_add'),
            self.datos(fecha=(self.fecha - timedelta(days=3)).isoformat()),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'deben ser futuras')
        self.assertEqual(Turno.objects.count(), 0)

    def test_alta_con_hora_fuera_de_horario_rechazada(self):
        resp = self.client.post(
            reverse('admin:core_turno_add'),
            self.datos(hora='07:00:00'),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'debe estar entre')
        self.assertEqual(Turno.objects.count(), 0)

    def test_alta_sin_profesional_rechazada(self):
        datos = self.datos()
        datos.pop('profesional')
        resp = self.client.post(reverse('admin:core_turno_add'), datos)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Turno.objects.count(), 0)

    def test_alta_con_profesional_inactivo_rechazada(self):
        inactivo = Profesional.objects.create(nombre='Baja', is_active=False)
        resp = self.client.post(
            reverse('admin:core_turno_add'),
            self.datos(profesional=inactivo.pk),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'profesional seleccionado no está activo')
        self.assertEqual(Turno.objects.count(), 0)

    def test_alta_con_servicio_inactivo_rechazada(self):
        inactivo = Servicio.objects.create(
            nombre='Off', duracion=timedelta(minutes=30),
            precio='1000.00', is_active=False,
        )
        resp = self.client.post(
            reverse('admin:core_turno_add'),
            self.datos(servicio=inactivo.pk),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'servicio seleccionado está inactivo')
        self.assertEqual(Turno.objects.count(), 0)

    def test_alta_sin_cobertura_rechazada(self):
        # La franja del día es 09:00-12:00: las 15:00 quedan fuera.
        resp = self.client.post(
            reverse('admin:core_turno_add'),
            self.datos(hora='15:00:00'),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'no está dentro de la disponibilidad')
        self.assertEqual(Turno.objects.count(), 0)

    def test_alta_con_cruce_de_medianoche_rechazada(self):
        largo = Servicio.objects.create(
            nombre='Largo', duracion=timedelta(hours=4), precio='9000.00'
        )
        resp = self.client.post(
            reverse('admin:core_turno_add'),
            self.datos(servicio=largo.pk, hora='20:00:00'),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'cruzar la medianoche')
        self.assertEqual(Turno.objects.count(), 0)

    def test_alta_solapada_rechazada(self):
        # 09:00-09:30 ya ocupado: un alta a las 09:15 lo solapa.
        self.crear_turno(hora=time(9, 0))
        resp = self.client.post(
            reverse('admin:core_turno_add'),
            self.datos(hora='09:15:00'),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'superpone')
        self.assertEqual(Turno.objects.count(), 1)

    def test_alta_duplicada_rechazada(self):
        # Mismo profesional, fecha y hora: restricción activa de B3.1.
        self.crear_turno(hora=time(9, 0))
        resp = self.client.post(
            reverse('admin:core_turno_add'),
            self.datos(hora='09:00:00'),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Turno.objects.count(), 1)

    def test_alta_valida_nace_pendiente(self):
        resp = self.client.post(
            reverse('admin:core_turno_add'),
            self.datos(hora='10:00:00'),
        )
        self.assertEqual(resp.status_code, 302)
        turno = Turno.objects.get()
        self.assertEqual(turno.estado, 'pendiente')
        self.assertEqual(turno.hora, time(10, 0))

    def test_estado_ignorado_en_el_formulario(self):
        # Aunque el POST incluya "estado", el campo es de solo lectura:
        # no participa del formulario y el estado no cambia.
        turno = self.crear_turno(hora=time(10, 0))
        resp = self.client.post(
            reverse('admin:core_turno_change', args=[turno.pk]),
            self.datos(hora='10:00:00', estado='confirmado'),
        )
        self.assertEqual(resp.status_code, 302)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'pendiente')

    def test_edicion_de_turno_ya_comenzado_rechazada(self):
        ayer = timezone.localdate() - timedelta(days=1)
        turno = self.crear_turno(hora=time(9, 0), fecha=ayer)
        resp = self.client.post(
            reverse('admin:core_turno_change', args=[turno.pk]),
            self.datos(fecha=ayer.isoformat(), hora='10:00:00'),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'solo lectura')
        turno.refresh_from_db()
        self.assertEqual(turno.hora, time(9, 0))

    def test_edicion_valida_de_turno_futuro(self):
        turno = self.crear_turno(hora=time(9, 0))
        resp = self.client.post(
            reverse('admin:core_turno_change', args=[turno.pk]),
            self.datos(hora='10:00:00'),
        )
        self.assertEqual(resp.status_code, 302)
        turno.refresh_from_db()
        self.assertEqual(turno.hora, time(10, 0))

    def test_edicion_que_conserva_el_horario_no_se_rechaza_a_si_misma(self):
        # El propio turno queda excluido del chequeo de solape.
        turno = self.crear_turno(hora=time(9, 0))
        resp = self.client.post(
            reverse('admin:core_turno_change', args=[turno.pk]),
            self.datos(hora='09:00:00'),
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Turno.objects.count(), 1)

    def test_edicion_solapada_con_otro_activo_rechazada(self):
        self.crear_turno(hora=time(9, 0))
        otro = self.crear_turno(hora=time(11, 0))
        resp = self.client.post(
            reverse('admin:core_turno_change', args=[otro.pk]),
            self.datos(hora='09:15:00'),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'superpone')
        otro.refresh_from_db()
        self.assertEqual(otro.hora, time(11, 0))


class TurnoAccionAdminTests(BaseAdminCoreTest):
    """Acciones administrativas de transición de estado."""

    def test_confirmar_turno_pendiente(self):
        turno = self.crear_turno(hora=time(9, 0))
        resp = self.ejecutar_accion('confirmar_turnos', [turno])
        self.assertEqual(resp.status_code, 302)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, 'confirmado')
        texts = self.mensajes(resp)
        self.assertTrue(any('confirmado' in m for m in texts))
        self.assertTrue(any('Resumen: 1 turno(s) actualizado(s)' in m
                            for m in texts))

    def test_confirmar_rechaza_estados_invalidos(self):
        confirmado = self.crear_turno(hora=time(9, 0), estado='confirmado')
        cancelado = self.crear_turno(hora=time(10, 0), estado='cancelado')
        resp = self.ejecutar_accion(
            'confirmar_turnos', [confirmado, cancelado]
        )
        self.assertEqual(resp.status_code, 302)
        confirmado.refresh_from_db()
        cancelado.refresh_from_db()
        self.assertEqual(confirmado.estado, 'confirmado')
        self.assertEqual(cancelado.estado, 'cancelado')
        texts = self.mensajes(resp)
        self.assertTrue(any(
            'solo se pueden confirmar turnos pendientes' in m for m in texts
        ))

    def test_cancelar_turnos_pendiente_y_confirmado(self):
        pendiente = self.crear_turno(hora=time(9, 0))
        confirmado = self.crear_turno(hora=time(10, 0), estado='confirmado')
        resp = self.ejecutar_accion(
            'cancelar_turnos', [pendiente, confirmado]
        )
        self.assertEqual(resp.status_code, 302)
        pendiente.refresh_from_db()
        confirmado.refresh_from_db()
        self.assertEqual(pendiente.estado, 'cancelado')
        self.assertEqual(confirmado.estado, 'cancelado')
        texts = self.mensajes(resp)
        self.assertTrue(any('Resumen: 2 turno(s) actualizado(s)' in m
                            for m in texts))

    def test_cancelar_rechaza_ya_cancelado(self):
        cancelado = self.crear_turno(hora=time(9, 0), estado='cancelado')
        resp = self.ejecutar_accion('cancelar_turnos', [cancelado])
        self.assertEqual(resp.status_code, 302)
        cancelado.refresh_from_db()
        self.assertEqual(cancelado.estado, 'cancelado')
        texts = self.mensajes(resp)
        self.assertTrue(any('ya está cancelado' in m for m in texts))

    def test_acciones_rechazan_turnos_ya_comenzados(self):
        ayer = timezone.localdate() - timedelta(days=1)
        pasado = self.crear_turno(hora=time(9, 0), fecha=ayer)
        resp = self.ejecutar_accion('confirmar_turnos', [pasado])
        self.assertEqual(resp.status_code, 302)
        pasado.refresh_from_db()
        self.assertEqual(pasado.estado, 'pendiente')
        texts = self.mensajes(resp)
        self.assertTrue(any('ya comenzó' in m for m in texts))
        self.assertTrue(any('Resumen: 0 turno(s) actualizado(s), 1 rechazado(s)'
                            in m for m in texts))

    def test_accion_mixta_informa_exitos_y_rechazos(self):
        valido = self.crear_turno(hora=time(9, 0))
        cancelado = self.crear_turno(hora=time(10, 0), estado='cancelado')
        resp = self.ejecutar_accion(
            'confirmar_turnos', [valido, cancelado]
        )
        self.assertEqual(resp.status_code, 302)
        valido.refresh_from_db()
        cancelado.refresh_from_db()
        self.assertEqual(valido.estado, 'confirmado')
        self.assertEqual(cancelado.estado, 'cancelado')
        texts = self.mensajes(resp)
        self.assertTrue(any('Resumen: 1 turno(s) actualizado(s), 1 rechazado(s)'
                            in m for m in texts))
        self.assertTrue(any(m.startswith('Turno ') for m in texts))


class TurnoEliminacionTests(BaseAdminCoreTest):
    """El historial de turnos no se puede eliminar."""

    def test_eliminacion_bloqueada_get_y_post(self):
        turno = self.crear_turno()
        url = reverse('admin:core_turno_delete', args=[turno.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.post(url, {'post': 'yes'}).status_code, 403
        )
        self.assertTrue(Turno.objects.filter(pk=turno.pk).exists())

    def test_accion_eliminar_multiple_no_disponible(self):
        turno = self.crear_turno()
        resp = self.ejecutar_accion('delete_selected', [turno])
        # La acción no está registrada: el POST directo queda sin efecto.
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Turno.objects.filter(pk=turno.pk).exists())


class DisponibilidadAdminTests(BaseAdminCoreTest):
    """Disponibilidades: pasado, profesional y cobertura."""

    def datos(self, **campos):
        datos = {
            'profesional': self.profesional.pk,
            'fecha': self.fecha.isoformat(),
            'hora_inicio': '09:00:00',
            'hora_fin': '12:00:00',
        }
        datos.update(campos)
        return datos

    def crear_franja_pasada(self):
        return Disponibilidad.objects.create(
            profesional=self.profesional,
            fecha=timezone.localdate() - timedelta(days=3),
            hora_inicio=time(9, 0), hora_fin=time(12, 0),
        )

    def test_franja_pasada_es_solo_lectura(self):
        pasada = self.crear_franja_pasada()
        url = reverse('admin:core_disponibilidad_change', args=[pasada.pk])
        # Se puede consultar…
        self.assertEqual(self.client.get(url).status_code, 200)
        # …pero no guardar cambios (solicitud directa incluida).
        resp = self.client.post(
            url,
            self.datos(
                fecha=pasada.fecha.isoformat(), hora_fin='13:00:00',
            ),
        )
        self.assertEqual(resp.status_code, 403)
        pasada.refresh_from_db()
        self.assertEqual(pasada.hora_fin, time(12, 0))

    def test_franja_pasada_no_se_puede_eliminar(self):
        pasada = self.crear_franja_pasada()
        url = reverse('admin:core_disponibilidad_delete', args=[pasada.pk])
        self.assertEqual(
            self.client.post(url, {'post': 'yes'}).status_code, 403
        )
        self.assertTrue(Disponibilidad.objects.filter(pk=pasada.pk).exists())

    def test_alta_en_fecha_pasada_rechazada(self):
        resp = self.client.post(
            reverse('admin:core_disponibilidad_add'),
            self.datos(fecha=(timezone.localdate() - timedelta(days=1))
                       .isoformat()),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'no puede ser anterior a hoy')
        self.assertEqual(Disponibilidad.objects.count(), 1)

    def test_alta_futura_valida(self):
        resp = self.client.post(
            reverse('admin:core_disponibilidad_add'),
            self.datos(hora_inicio='15:00:00', hora_fin='18:00:00'),
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Disponibilidad.objects.count(), 2)

    def test_no_se_puede_cambiar_el_profesional(self):
        franja = Disponibilidad.objects.get()
        otro = Profesional.objects.create(nombre='Pro B')
        resp = self.client.post(
            reverse('admin:core_disponibilidad_change', args=[franja.pk]),
            self.datos(profesional=otro.pk),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'cambiar el profesional')
        franja.refresh_from_db()
        self.assertEqual(franja.profesional_id, self.profesional.pk)

    def test_edicion_que_deja_turno_sin_cobertura_rechazada(self):
        # Turno 09:00-09:30: adelantar el inicio a las 09:15 lo deja
        # fuera de la franja.
        turno = self.crear_turno(hora=time(9, 0))
        franja = Disponibilidad.objects.get()
        resp = self.client.post(
            reverse('admin:core_disponibilidad_change', args=[franja.pk]),
            self.datos(hora_inicio='09:15:00'),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'sin cobertura')
        franja.refresh_from_db()
        self.assertEqual(franja.hora_inicio, time(9, 0))
        self.assertTrue(Turno.objects.filter(pk=turno.pk).exists())

    def test_edicion_que_conserva_cobertura_permitida(self):
        turno = self.crear_turno(hora=time(9, 0))
        franja = Disponibilidad.objects.get()
        resp = self.client.post(
            reverse('admin:core_disponibilidad_change', args=[franja.pk]),
            self.datos(hora_fin='13:00:00'),
        )
        self.assertEqual(resp.status_code, 302)
        franja.refresh_from_db()
        self.assertEqual(franja.hora_fin, time(13, 0))
        self.assertTrue(Turno.objects.filter(pk=turno.pk).exists())

    def test_mover_franja_deja_turnos_del_dia_origen_sin_cobertura(self):
        self.crear_turno(hora=time(9, 0))
        franja = Disponibilidad.objects.get()
        resp = self.client.post(
            reverse('admin:core_disponibilidad_change', args=[franja.pk]),
            self.datos(fecha=(self.fecha + timedelta(days=2)).isoformat()),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'sin cobertura')
        franja.refresh_from_db()
        self.assertEqual(franja.fecha, self.fecha)

    def test_mover_franja_sin_dependencias_permitida(self):
        franja = Disponibilidad.objects.get()
        nueva_fecha = self.fecha + timedelta(days=2)
        resp = self.client.post(
            reverse('admin:core_disponibilidad_change', args=[franja.pk]),
            self.datos(fecha=nueva_fecha.isoformat()),
        )
        self.assertEqual(resp.status_code, 302)
        franja.refresh_from_db()
        self.assertEqual(franja.fecha, nueva_fecha)

    def test_eliminar_franja_con_turno_dependiente_bloqueada(self):
        self.crear_turno(hora=time(9, 0))
        franja = Disponibilidad.objects.get()
        url = reverse('admin:core_disponibilidad_delete', args=[franja.pk])
        self.assertEqual(
            self.client.post(url, {'post': 'yes'}).status_code, 403
        )
        self.assertTrue(Disponibilidad.objects.filter(pk=franja.pk).exists())

    def test_eliminar_franja_sin_dependencias_permitida(self):
        franja = Disponibilidad.objects.get()
        url = reverse('admin:core_disponibilidad_delete', args=[franja.pk])
        self.assertEqual(
            self.client.post(url, {'post': 'yes'}).status_code, 302
        )
        self.assertFalse(Disponibilidad.objects.filter(pk=franja.pk).exists())

    def test_solape_se_sigue_validando_en_el_admin(self):
        # Las validaciones de modelo (B2) siguen activas en el formulario.
        resp = self.client.post(
            reverse('admin:core_disponibilidad_add'),
            self.datos(hora_inicio='10:00:00', hora_fin='11:00:00'),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'superpone')
        self.assertEqual(Disponibilidad.objects.count(), 1)

    def test_accion_eliminar_multiple_no_disponible(self):
        # Sin acciones registradas el changelist ni procesa el POST de
        # acción: la solicitud directa queda sin efecto (200) y nada se
        # borra.
        self.crear_turno(hora=time(9, 0))
        franja = Disponibilidad.objects.get()
        resp = self.client.post(
            reverse('admin:core_disponibilidad_changelist'),
            {
                'action': 'delete_selected',
                '_selected_action': [str(franja.pk)],
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Disponibilidad.objects.filter(pk=franja.pk).exists())

    def test_delete_queryset_bloquea_objetos_protegidos(self):
        # Red de seguridad del servidor para la eliminación múltiple,
        # aunque la acción por defecto esté retirada.
        pasada = self.crear_franja_pasada()
        instancia = DisponibilidadAdmin(Disponibilidad, site)
        request = RequestFactory().post('/')
        with self.assertRaises(PermissionDenied):
            instancia.delete_queryset(
                request, Disponibilidad.objects.filter(pk=pasada.pk)
            )
        self.assertTrue(Disponibilidad.objects.filter(pk=pasada.pk).exists())


class ProfesionalAdminTests(BaseAdminCoreTest):
    """Profesionales: desactivación y eliminación."""

    def datos(self, **campos):
        datos = {'nombre': 'Pro A', 'usuario': ''}
        datos.update(campos)
        return datos

    def test_no_desactivar_con_turno_futuro_activo(self):
        self.crear_turno(hora=time(9, 0))
        resp = self.client.post(
            reverse('admin:core_profesional_change', args=[self.profesional.pk]),
            self.datos(),  # sin is_active → baja
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'No se puede desactivar un profesional')
        self.profesional.refresh_from_db()
        self.assertTrue(self.profesional.is_active)

    def test_desactivar_con_turno_cancelado_permitido(self):
        self.crear_turno(hora=time(9, 0), estado='cancelado')
        resp = self.client.post(
            reverse('admin:core_profesional_change', args=[self.profesional.pk]),
            self.datos(),
        )
        self.assertEqual(resp.status_code, 302)
        self.profesional.refresh_from_db()
        self.assertFalse(self.profesional.is_active)

    def test_desactivar_sin_turnos_permitido(self):
        resp = self.client.post(
            reverse('admin:core_profesional_change', args=[self.profesional.pk]),
            self.datos(),
        )
        self.assertEqual(resp.status_code, 302)
        self.profesional.refresh_from_db()
        self.assertFalse(self.profesional.is_active)

    def test_no_eliminar_profesional_con_turnos(self):
        self.crear_turno(hora=time(9, 0))
        url = reverse(
            'admin:core_profesional_delete', args=[self.profesional.pk]
        )
        self.assertEqual(
            self.client.post(url, {'post': 'yes'}).status_code, 403
        )
        self.assertTrue(Profesional.objects.filter(pk=self.profesional.pk).exists())

    def test_no_eliminar_profesional_con_disponibilidades(self):
        # Sin turnos pero con franjas (el CASCADE las borraría todas).
        url = reverse(
            'admin:core_profesional_delete', args=[self.profesional.pk]
        )
        self.assertEqual(
            self.client.post(url, {'post': 'yes'}).status_code, 403
        )
        self.assertTrue(Profesional.objects.filter(pk=self.profesional.pk).exists())
        self.assertEqual(Disponibilidad.objects.count(), 1)

    def test_eliminar_profesional_sin_dependencias_permitido(self):
        libre = Profesional.objects.create(nombre='SinDep')
        url = reverse('admin:core_profesional_delete', args=[libre.pk])
        self.assertEqual(
            self.client.post(url, {'post': 'yes'}).status_code, 302
        )
        self.assertFalse(Profesional.objects.filter(pk=libre.pk).exists())


class ServicioAdminTests(BaseAdminCoreTest):
    """Servicios: duración, borrado y desactivación."""

    def datos(self, **campos):
        datos = {
            'nombre': 'Semi',
            'duracion': '0:30:00',
            'precio': '5000.00',
            'is_active': 'on',
        }
        datos.update(campos)
        return datos

    def test_no_cambiar_duracion_con_turno_futuro_activo(self):
        self.crear_turno(hora=time(9, 0))
        resp = self.client.post(
            reverse('admin:core_servicio_change', args=[self.servicio.pk]),
            self.datos(duracion='0:45:00'),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'No se puede cambiar la duración')
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.duracion, timedelta(minutes=30))

    def test_cambiar_duracion_con_turno_cancelado_permitido(self):
        self.crear_turno(hora=time(9, 0), estado='cancelado')
        resp = self.client.post(
            reverse('admin:core_servicio_change', args=[self.servicio.pk]),
            self.datos(duracion='0:45:00'),
        )
        self.assertEqual(resp.status_code, 302)
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.duracion, timedelta(minutes=45))

    def test_cambiar_precio_con_turnos_permitido(self):
        self.crear_turno(hora=time(9, 0))
        resp = self.client.post(
            reverse('admin:core_servicio_change', args=[self.servicio.pk]),
            self.datos(precio='6000.00'),
        )
        self.assertEqual(resp.status_code, 302)
        self.servicio.refresh_from_db()
        self.assertEqual(self.servicio.precio, 6000)

    def test_no_eliminar_servicio_con_turnos(self):
        self.crear_turno(hora=time(9, 0))
        url = reverse('admin:core_servicio_delete', args=[self.servicio.pk])
        self.assertEqual(
            self.client.post(url, {'post': 'yes'}).status_code, 403
        )
        self.assertTrue(Servicio.objects.filter(pk=self.servicio.pk).exists())

    def test_eliminar_servicio_sin_turnos_permitido(self):
        libre = Servicio.objects.create(
            nombre='Libre', duracion=timedelta(minutes=15), precio='100.00'
        )
        url = reverse('admin:core_servicio_delete', args=[libre.pk])
        self.assertEqual(
            self.client.post(url, {'post': 'yes'}).status_code, 302
        )
        self.assertFalse(Servicio.objects.filter(pk=libre.pk).exists())

    def test_desactivar_servicio_con_turnos_permitido(self):
        # B1: desactivar un servicio sigue permitido (solo deja de
        # ofrecerse para nuevas reservas).
        self.crear_turno(hora=time(9, 0))
        datos = self.datos()
        datos.pop('is_active')
        resp = self.client.post(
            reverse('admin:core_servicio_change', args=[self.servicio.pk]),
            datos,
        )
        self.assertEqual(resp.status_code, 302)
        self.servicio.refresh_from_db()
        self.assertFalse(self.servicio.is_active)

    def test_is_active_visible_en_listado(self):
        self.assertIn('is_active', ServicioAdmin.list_display)
        resp = self.client.get(reverse('admin:core_servicio_changelist'))
        self.assertEqual(resp.status_code, 200)
