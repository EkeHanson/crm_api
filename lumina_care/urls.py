# lumina_care/urls.py
from django.urls import path, include
from django.http import JsonResponse
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from .views import CustomTokenObtainPairView

def root_view(request):
    return JsonResponse({
        'status': 'success',
        'message': 'Welcome to LUMINA Care OS API',
        'endpoints': {
            'tenants': '/api/tenant/tenants',
            'users': '/api/user/users',
            'docs': '/api/docs/',
            'token': '/api/token/'
        }
    })

urlpatterns = [
    path('', root_view, name='root'),
    path('api/tenant/', include('core.urls')),
    path('api/user/', include('users.urls')),
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]