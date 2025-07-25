# lumina_care/urls.py
from django.urls import path, include
from django.http import JsonResponse
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from .views import CustomTokenObtainPairView, TokenValidateView
from django.conf import settings
from django.conf.urls.static import static

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

    path('api/talent-engine/', include('talent_engine.urls')),  # Updated
    path('api/subscriptions/', include('subscriptions.urls')),  # Added
    path('api/talent-engine-job-applications/', include('job_application.urls')),
    
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/validate/', TokenValidateView.as_view(), name='token_validate'),

    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    # path('accounts/', include('allauth.urls')),  # OAuth endpoints
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

