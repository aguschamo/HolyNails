from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    HealthView,
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
    # Etapa 1B: health check para monitoreo de producción. Público,
    # sin autenticación y sin consultar la base de datos.
    path('health/', HealthView.as_view(), name='health'),
    path('', include(router.urls)),
]
