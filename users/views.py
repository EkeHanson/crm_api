from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import CustomUser
from .serializers import UserSerializer
from django_tenants.utils import tenant_context
from rest_framework import serializers

class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self.request.user.tenant
        with tenant_context(tenant):
            return CustomUser.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        tenant = self.request.user.tenant
        if self.request.user.role != 'admin' and not self.request.user.is_superuser:
            raise serializers.ValidationError("Only admins or superusers can create users.")
        with tenant_context(tenant):
            serializer.save()
