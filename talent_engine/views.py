# apps/talent_engine/views.py
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import JobRequisition
from .serializers import JobRequisitionSerializer
from .permissions import IsSubscribedAndAuthorized
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
import logging

logger = logging.getLogger('talent_engine')

class JobRequisitionListCreateView(generics.ListCreateAPIView):
    serializer_class = JobRequisitionSerializer
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'role']
    search_fields = ['title', 'status', 'requested_by__email', 'role']

    def get_queryset(self):
        print(self.request.tenant.schema_name)
        logger.debug(f"User: {self.request.user}, Tenant: {self.request.tenant.schema_name}")
        return JobRequisition.objects.filter(tenant=self.request.tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)
        logger.info(f"Job requisition created: {serializer.validated_data['title']} for tenant {self.request.tenant.schema_name}")

class JobRequisitionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = JobRequisitionSerializer
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]
    lookup_field = 'id'

    def get_queryset(self):
        return JobRequisition.objects.filter(tenant=self.request.tenant)

    def perform_update(self, serializer):
        serializer.save()
        logger.info(f"Job requisition updated: {serializer.instance.title} for tenant {self.request.tenant.schema_name}")

    def perform_destroy(self, instance):
        logger.info(f"Job requisition deleted: {instance.title} for tenant {self.request.tenant.schema_name}")
        instance.delete()

class JobRequisitionBulkDeleteView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]

    def post(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            logger.warning("No IDs provided for bulk delete")
            return Response({"detail": "No IDs provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            requisitions = JobRequisition.objects.filter(tenant=request.tenant, id__in=ids)
            count = requisitions.count()
            if count == 0:
                logger.warning("No requisitions found for provided IDs")
                return Response({"detail": "No requisitions found."}, status=status.HTTP_404_NOT_FOUND)

            requisitions.delete()
            logger.info(f"Bulk deleted {count} job requisitions for tenant {request.tenant.schema_name}")
            return Response({"detail": f"Deleted {count} requisition(s)."}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Bulk delete failed: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)