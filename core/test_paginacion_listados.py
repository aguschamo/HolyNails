"""Paginación de los listados de servicios y profesionales (A2).

Ambos endpoints usan la paginación global de DRF
(``PageNumberPagination``, ``PAGE_SIZE=10`` en ``config.settings``).
Estas pruebas verifican que devuelvan la estructura paginada y que
recorrer todas las páginas no duplique ni omita elementos: los ViewSets
ordenan por ``id`` para dar un orden determinístico (sin él DRF emite
``UnorderedObjectListWarning`` y el orden entre páginas no está
garantizado).

No se modifican datos persistentes: todo corre sobre la base de tests
en memoria que Django crea y destruye por sí solo.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from core.models import Profesional, Servicio

User = get_user_model()

# PAGE_SIZE=10: once registros fuerzan exactamente dos páginas.
CANTIDAD = 11


def _crear_servicios(cantidad):
    return [
        Servicio.objects.create(
            nombre=f'Servicio {i:02d}',
            duracion=timedelta(minutes=60),
            precio='5000.00',
        )
        for i in range(cantidad)
    ]


def _recorrer_todo(client, url):
    """Sigue ``next`` hasta agotar las páginas y devuelve los ids."""
    ids = []
    while url:
        datos = client.get(url).json()
        ids.extend(item['id'] for item in datos['results'])
        url = datos['next']
    return ids


def _advertencias_de_orden(capturadas):
    return [
        w for w in capturadas
        if 'UnorderedObjectListWarning' in type(w.message).__name__
    ]


class PaginacionServiciosTests(APITestCase):
    def setUp(self):
        self.servicios = _crear_servicios(CANTIDAD)

    def test_listado_devuelve_estructura_paginada(self):
        respuesta = self.client.get('/api/servicios/')
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual(datos['count'], CANTIDAD)
        self.assertEqual(len(datos['results']), 10)  # PAGE_SIZE
        self.assertIsNotNone(datos['next'])
        self.assertIsNone(datos['previous'])

    def test_recorrer_todas_las_paginas_no_duplica_ni_omite(self):
        ids = _recorrer_todo(self.client, '/api/servicios/')
        self.assertEqual(len(ids), CANTIDAD)
        self.assertEqual(len(set(ids)), CANTIDAD)
        self.assertEqual(set(ids), {s.id for s in self.servicios})

    def test_pagina_invalida_no_rompe_el_listado(self):
        # DRF responde 404 para una página fuera de rango; el listado
        # base sigue intacto.
        self.assertEqual(self.client.get('/api/servicios/?page=99').status_code, 404)
        self.assertEqual(self.client.get('/api/servicios/').json()['count'], CANTIDAD)

    def test_sin_advertencia_de_orden_al_paginar(self):
        import warnings

        with warnings.catch_warnings(record=True) as capturadas:
            warnings.simplefilter('always')
            self.client.get('/api/servicios/')
        self.assertEqual(_advertencias_de_orden(capturadas), [])


class PaginacionProfesionalesTests(APITestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username='consulta_profesionales', password='x',
        )
        self.profesionales = [
            Profesional.objects.create(nombre=f'Profesional {i:02d}')
            for i in range(CANTIDAD)
        ]

    def test_listado_autenticado_devuelve_estructura_paginada(self):
        self.client.force_authenticate(self.usuario)
        respuesta = self.client.get('/api/profesionales/')
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual(datos['count'], CANTIDAD)
        self.assertEqual(len(datos['results']), 10)  # PAGE_SIZE
        self.assertIsNotNone(datos['next'])

    def test_recorrer_todas_las_paginas_no_duplica_ni_omite(self):
        self.client.force_authenticate(self.usuario)
        ids = _recorrer_todo(self.client, '/api/profesionales/')
        self.assertEqual(len(ids), CANTIDAD)
        self.assertEqual(len(set(ids)), CANTIDAD)
        self.assertEqual(set(ids), {p.id for p in self.profesionales})

    def test_sin_advertencia_de_orden_al_paginar(self):
        import warnings

        self.client.force_authenticate(self.usuario)
        with warnings.catch_warnings(record=True) as capturadas:
            warnings.simplefilter('always')
            self.client.get('/api/profesionales/')
        self.assertEqual(_advertencias_de_orden(capturadas), [])
