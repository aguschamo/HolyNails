from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ServicioViewSet,
    TurnoViewSet,
    ProfesionalViewSet,
    DisponibilidadViewSet,
)

router = DefaultRouter()
router.register(r'servicios', ServicioViewSet, basename='servicio')
router.register(r'turnos', TurnoViewSet, basename='turno')
router.register(r'profesionales', ProfesionalViewSet, basename='profesional')
router.register(r'disponibilidades', DisponibilidadViewSet, basename='disponibilidad')

urlpatterns = [
    path('', include(router.urls)),
]
