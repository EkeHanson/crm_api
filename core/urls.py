# apps/core/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TenantViewSet

router = DefaultRouter()
router.register(r'tenants', TenantViewSet)

urlpatterns = [
    path('', include(router.urls)),
]


# from core.models import Tenant, Domain    
# if not Tenant.objects.filter(schema_name='public').exists():
#      tenant = Tenant.objects.create(
#          name='Test Tenant',
#          schema_name='testTenant',
#          auto_create_schema=False
#      )
#      Domain.objects.create(tenant=tenant, domain='testTenant.com', is_primary=True)