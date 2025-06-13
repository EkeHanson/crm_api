from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import JobRequisition
from .serializers import JobRequisitionSerializer
from .permissions import IsSubscribedAndAuthorized
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from django_tenants.utils import tenant_context
from django.db import connection
import logging
logger = logging.getLogger('talent_engine')


class JobRequisitionListCreateView(generics.ListCreateAPIView):
    serializer_class = JobRequisitionSerializer
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'role']
    search_fields = ['title', 'status', 'requested_by__email', 'role']


    def get_queryset(self):
        tenant = self.request.tenant
        logger.debug(f"User: {self.request.user}, Tenant: {tenant.schema_name}")
        logger.debug(f"Schema before set: {connection.schema_name}")
        connection.set_schema(tenant.schema_name)
        logger.debug(f"Schema after set: {connection.schema_name}")
        with connection.cursor() as cursor:
            cursor.execute("SHOW search_path;")
            search_path = cursor.fetchone()[0]
            logger.debug(f"Database search_path: {search_path}")
        queryset = JobRequisition.objects.filter(tenant=tenant)
        logger.debug(f"Query: {queryset.query}")
        return queryset

    def perform_create(self, serializer):
        tenant = self.request.tenant
        connection.set_schema(tenant.schema_name)
        serializer.save(tenant=tenant)
        logger.info(f"Job requisition created: {serializer.validated_data['title']} for tenant {tenant.schema_name}")

class JobRequisitionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = JobRequisitionSerializer
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]
    lookup_field = 'id'

    def get_queryset(self):
        tenant = self.request.tenant
        with tenant_context(tenant):
            return JobRequisition.objects.filter(tenant=tenant)

    def perform_update(self, serializer):
        tenant = self.request.tenant
        with tenant_context(tenant):
            serializer.save()
        logger.info(f"Job requisition updated: {serializer.instance.title} for tenant {tenant.schema_name}")

    def perform_destroy(self, instance):
        tenant = self.request.tenant
        with tenant_context(tenant):
            instance.delete()
        logger.info(f"Job requisition deleted: {instance.title} for tenant {tenant.schema_name}")

class JobRequisitionBulkDeleteView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]

    def post(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            logger.warning("No IDs provided for bulk delete")
            return Response({"detail": "No IDs provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tenant = request.tenant
            with tenant_context(tenant):
                requisitions = JobRequisition.objects.filter(tenant=tenant, id__in=ids)
                count = requisitions.count()
                if count == 0:
                    logger.warning("No requisitions found for provided IDs")
                    return Response({"detail": "No requisitions found."}, status=status.HTTP_404_NOT_FOUND)

                requisitions.delete()
            logger.info(f"Bulk deleted {count} job requisitions for tenant {tenant.schema_name}")
            return Response({"detail": f"Deleted {count} requisition(s)."}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Bulk delete failed: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)