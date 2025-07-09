import logging
import jwt

from django.conf import settings
from django.db import transaction, connection

from rest_framework import viewsets, status, serializers
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from django_tenants.utils import tenant_context

from .models import Tenant, Domain, Module, TenantConfig
from .serializers import TenantSerializer, ModuleSerializer

logger = logging.getLogger('core')


class ModuleListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        tenant = request.user.tenant
        with tenant_context(tenant):
            modules = Module.objects.filter(is_active=True)
            serializer = ModuleSerializer(modules, many=True, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        tenant = request.user.tenant
        serializer = ModuleSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            try:
                with tenant_context(tenant):
                    with transaction.atomic():
                        module = serializer.save(tenant=tenant)
                        logger.info(f"Module created: {module.name} for tenant {tenant.schema_name}")
                        return Response(serializer.data, status=status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Error creating module: {str(e)}")
                return Response({
                    'status': 'error',
                    'message': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        logger.error(f"Validation error: {serializer.errors}")
        return Response({
            'status': 'error',
            'message': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

class TenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated]

    def get_tenant_from_token(self, request):
        try:
            if hasattr(request, 'tenant') and request.tenant:
                logger.debug(f"Tenant from request: {request.tenant.schema_name}")
                return request.tenant
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                logger.warning("No valid Bearer token provided")
                raise ValueError("Invalid token format")
            token = auth_header.split(' ')[1]
            decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            tenant_id = decoded_token.get('tenant_id')
            schema_name = decoded_token.get('tenant_schema')
            if tenant_id:
                tenant = Tenant.objects.get(id=tenant_id)
                logger.debug(f"Tenant extracted from token by ID: {tenant.schema_name}")
                return tenant
            elif schema_name:
                tenant = Tenant.objects.get(schema_name=schema_name)
                logger.debug(f"Tenant extracted from token by schema: {tenant.schema_name}")
                return tenant
            else:
                logger.warning("No tenant_id or schema_name in token")
                raise ValueError("Tenant not specified in token")
        except Tenant.DoesNotExist:
            logger.error("Tenant not found")
            raise serializers.ValidationError("Tenant not found")
        except jwt.InvalidTokenError:
            logger.error("Invalid JWT token")
            raise serializers.ValidationError("Invalid token")
        except Exception as e:
            logger.error(f"Error extracting tenant: {str(e)}")
            raise serializers.ValidationError(f"Error extracting tenant: {str(e)}")

    def get_queryset(self):
        tenant = self.get_tenant_from_token(self.request)
        logger.debug(f"Filtering queryset for tenant: {tenant.schema_name}")
        connection.set_schema(tenant.schema_name)
        with connection.cursor() as cursor:
            cursor.execute("SHOW search_path;")
            search_path = cursor.fetchone()[0]
            logger.debug(f"Database search_path: {search_path}")
        return Tenant.objects.filter(id=tenant.id)

    def perform_create(self, serializer):
        tenant = self.get_tenant_from_token(self.request)
        try:
            with transaction.atomic():
                with tenant_context(tenant):
                    new_tenant = serializer.save()
                    logger.info(f"Tenant created: {new_tenant.name} (schema: {new_tenant.schema_name}) for tenant {tenant.schema_name}")
                    return Response(serializer.data)
        except Exception as e:
            logger.error(f"Failed to create tenant: {str(e)}")
            raise serializers.ValidationError(f"Failed to create tenant: {str(e)}")

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        logger.info(f"Listing tenants: {[t['id'] for t in serializer.data]} for tenant {request.tenant.schema_name}")
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        tenant = self.get_tenant_from_token(request)
        instance = self.get_object()
        if instance.id != tenant.id:
            logger.warning(f"Unauthorized access attempt to tenant {instance.id} by tenant {tenant.id}")
            return Response({"detail": "Not authorized to access this tenant"}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(instance)
        logger.info(f"Retrieving tenant: {instance.id} for tenant {tenant.schema_name}")
        return Response(serializer.data)

    def perform_update(self, serializer):
        tenant = self.get_tenant_from_token(self.request)
        instance = self.get_object()
        if instance.id != tenant.id:
            logger.error(f"Unauthorized update attempt on tenant {instance.id} by tenant {tenant.id}")
            raise serializers.ValidationError("Not authorized to update this tenant")
        with tenant_context(tenant):
            serializer.save()
        logger.info(f"Tenant updated: {instance.name} for tenant {tenant.schema_name}")

    def perform_destroy(self, instance):
        tenant = self.get_tenant_from_token(self.request)
        if instance.id != tenant.id:
            logger.error(f"Unauthorized delete attempt on tenant {instance.id} by tenant {tenant.id}")
            raise serializers.ValidationError("Not authorized to delete this tenant")
        with tenant_context(tenant):
            instance.delete()
        logger.info(f"Tenant deleted: {instance.name} for tenant {tenant.schema_name}")