# apps/talent_engine/views.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import JobPosting
from .serializers import JobPostingSerializer
from django_tenants.utils import tenant_context

class JobPostingViewSet(viewsets.ModelViewSet):
    queryset = JobPosting.objects.all()
    serializer_class = JobPostingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self.request.user.tenant
        with tenant_context(tenant):
            return JobPosting.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        tenant = self.request.user.tenant
        with tenant_context(tenant):
            serializer.save(tenant=tenant, created_by=self.request.user)


# class JobPostingViewSet(viewsets.ModelViewSet):
#     module_name = 'Talent Engine'
#     permission_classes = [IsAuthenticated, ModuleAccessPermission]