from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ClienteViewSet,
    EmailTokenObtainPairView,
    LogoutView,
    ProfileFotoView,
    ProfileView,
    RegisterView,
    UserViewSet,
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
# B10.3: módulo de clientas del panel administrativo. El basename es
# explícito para no chocar con el de UserViewSet (ambos sobre User).
router.register(r'clientas', ClienteViewSet, basename='clientas')

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/profile/', ProfileView.as_view(), name='profile'),
    # B11.2: subida (POST) y eliminación (DELETE) de la foto propia.
    path('auth/profile/foto/', ProfileFotoView.as_view(), name='profile-foto'),
]

urlpatterns += router.urls
