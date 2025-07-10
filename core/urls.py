from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TenantViewSet, ModuleListView, TenantConfigView

router = DefaultRouter()
router.register(r'tenants', TenantViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('modules/', ModuleListView.as_view(), name='module_list'),
    path('config/', TenantConfigView.as_view(), name='tenant_config'),
]