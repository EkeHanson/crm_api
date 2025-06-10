
from rest_framework import serializers
# apps/core/views.py
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db import transaction
from .models import Tenant, Domain, Module, TenantConfig
from .serializers import TenantSerializer
import logging

logger = logging.getLogger('core')

class TenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                tenant = serializer.save()
                logger.info(f"Tenant created: {tenant.name} (schema: {tenant.schema_name})")
                return Response(serializer.data)
        except Exception as e:
            logger.error(f"Failed to create tenant: {str(e)}")
            raise serializers.ValidationError(f"Failed to create tenant: {str(e)}")

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        logger.info(f"Listing tenants: {[t['id'] for t in serializer.data]}")
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        logger.info(f"Retrieving tenant: {instance.id}")
        return Response(serializer.data)