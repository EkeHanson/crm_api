from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated,AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from django_tenants.utils import tenant_context
from django.db import connection
from .models import JobApplication
from .serializers import JobApplicationSerializer
from talent_engine.models import JobRequisition
from core.models import Tenant
from rest_framework import serializers
from .permissions import IsSubscribedAndAuthorized
import logging
logger = logging.getLogger('job_applications')
from .tenant_utils import resolve_tenant_from_unique_link
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from collections import defaultdict
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction
logger = logging.getLogger('job_applications')
from django_tenants.utils import tenant_context
from django.db import connection
from django.db.models import Count
from talent_engine.models import JobRequisition
from talent_engine.serializers import JobRequisitionSerializer
logger = logging.getLogger('job_applications')



class JobApplicationsByRequisitionView(generics.ListAPIView):
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]

    def get_queryset(self):
        try:
            tenant = self.request.tenant
            job_requisition_id = self.kwargs['job_requisition_id']
            
            # Set schema and log
            connection.set_schema(tenant.schema_name)
            logger.debug(f"Schema set to: {connection.schema_name}")
            
            with tenant_context(tenant):
                # Verify job requisition exists and belongs to tenant
                try:
                    job_requisition = JobRequisition.objects.get(id=job_requisition_id, tenant=tenant)
                except JobRequisition.DoesNotExist:
                    logger.error(f"JobRequisition {job_requisition_id} not found for tenant {tenant.schema_name}")
                    raise generics.get_object_or_404(JobRequisition, id=job_requisition_id, tenant=tenant)
                
                # Get all applications for the job requisition
                applications = JobApplication.objects.filter(
                    tenant=tenant,
                    job_requisition=job_requisition
                ).select_related('job_requisition')
                
                logger.debug(f"Query: {applications.query}")
                logger.info(f"Retrieved {applications.count()} job applications for JobRequisition {job_requisition_id}")
                
                return applications
                
        except Exception as e:
            logger.exception(f"Error retrieving job applications for JobRequisition {job_requisition_id}")
            raise

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.db import connection
from django_tenants.utils import tenant_context
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

class JobApplicationListCreateView(generics.GenericAPIView):
    parser_classes = (MultiPartParser, FormParser)
    serializer_class = JobApplicationSerializer

    def get_permissions(self):
        """
        Override to apply different permissions based on the request method.
        - GET requires authentication and subscription authorization.
        - POST allows anyone (no authentication required).
        """
        if self.request.method == 'GET':
            return [IsAuthenticated(), IsSubscribedAndAuthorized()]
        return [AllowAny()]

    def get(self, request, *args, **kwargs):
        try:
            tenant = request.tenant
            if not tenant:
                logger.error("No tenant associated with the request")
                return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)

            logger.debug(f"User: {request.user}, Tenant: {tenant.schema_name}")
            logger.debug(f"Schema before set: {connection.schema_name}")
            connection.set_schema(tenant.schema_name)
            logger.debug(f"Schema after set: {connection.schema_name}")
            with connection.cursor() as cursor:
                cursor.execute("SHOW search_path;")
                search_path = cursor.fetchone()[0]
                logger.debug(f"Database search_path: {search_path}")

            with tenant_context(tenant):
                applications = JobApplication.objects.filter(tenant=tenant).select_related('job_requisition')
                logger.debug(f"Query: {applications.query}")
                serializer = self.get_serializer(applications, many=True)
                logger.info(f"Retrieved {len(applications)} job applications for tenant {tenant.schema_name}")
                return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Error retrieving job applications")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, *args, **kwargs):
        try: 
            unique_link = request.data.get("unique_link")
            
            if not unique_link:
                return Response({"detail": "Missing unique_link."}, status=status.HTTP_400_BAD_REQUEST)

            tenant, job_requisition = resolve_tenant_from_unique_link(unique_link)
       
            if tenant is None or job_requisition is None:
                return Response({"detail": "Invalid or expired job link."}, status=status.HTTP_400_BAD_REQUEST)

            request.tenant = tenant  # Required for serializer

            application_data = {
                "job_requisition": job_requisition.id,
                "full_name": request.data.get("full_name"),
                "email": request.data.get("email"),
                "phone": request.data.get("phone"),
                "qualification": request.data.get("qualification"),
                "experience": request.data.get("experience"),
                "knowledge_skill": request.data.get("knowledge_skill"),
                "cover_letter": request.data.get("cover_letter", ""),
                "resume_status": request.data.get("resume_status", False),
            }

            documents = []
            index = 0
            while True:
                doc_type = request.data.get(f"documents[{index}][document_type]")
                doc_file = request.data.get(f"documents[{index}][file]")
                if doc_type and doc_file:
                    documents.append({
                        "document_type": doc_type,
                        "file": doc_file
                    })
                    index += 1
                else:
                    break

            application_data["documents"] = documents

            serializer = JobApplicationSerializer(
                data=application_data,
                context={
                    "request": request,
                    "job_requisition": job_requisition
                }
            )

            if not serializer.is_valid():
                logger.error("Validation failed: %s", serializer.errors)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                application = serializer.save()
                return Response({
                    "detail": "Application submitted successfully.",
                    "application_id": application.id
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception("Unexpected error during job application submission")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# class JobApplicationListCreateView(generics.GenericAPIView):
#     parser_classes = (MultiPartParser, FormParser)
#     # permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]
#     serializer_class = JobApplicationSerializer

#     def get(self, request, *args, **kwargs):
#         try:
#             tenant = request.tenant
#             if not tenant:
#                 logger.error("No tenant associated with the request")
#                 return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)

#             logger.debug(f"User: {request.user}, Tenant: {tenant.schema_name}")
#             logger.debug(f"Schema before set: {connection.schema_name}")
#             connection.set_schema(tenant.schema_name)
#             logger.debug(f"Schema after set: {connection.schema_name}")
#             with connection.cursor() as cursor:
#                 cursor.execute("SHOW search_path;")
#                 search_path = cursor.fetchone()[0]
#                 logger.debug(f"Database search_path: {search_path}")

#             with tenant_context(tenant):
#                 applications = JobApplication.objects.filter(tenant=tenant).select_related('job_requisition')
#                 logger.debug(f"Query: {applications.query}")
#                 serializer = self.get_serializer(applications, many=True)
#                 logger.info(f"Retrieved {len(applications)} job applications for tenant {tenant.schema_name}")
#                 return Response(serializer.data, status=status.HTTP_200_OK)

#         except Exception as e:
#             logger.exception("Error retrieving job applications")
#             return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     def post(self, request, *args, **kwargs):
#         try: 
#             unique_link = request.data.get("unique_link")
            
#             if not unique_link:
#                 return Response({"detail": "Missing unique_link."}, status=status.HTTP_400_BAD_REQUEST)

#             tenant, job_requisition = resolve_tenant_from_unique_link(unique_link)
       
#             if tenant is None or job_requisition is None:
#                 return Response({"detail": "Invalid or expired job link."}, status=status.HTTP_400_BAD_REQUEST)

#             request.tenant = tenant  # Required for serializer

#             application_data = {
#                 "job_requisition": job_requisition.id,
#                 "full_name": request.data.get("full_name"),
#                 "email": request.data.get("email"),
#                 "phone": request.data.get("phone"),
#                 "qualification": request.data.get("qualification"),
#                 "experience": request.data.get("experience"),
#                 "knowledge_skill": request.data.get("knowledge_skill"),
#                 "cover_letter": request.data.get("cover_letter", ""),
#                 "resume_status": request.data.get("resume_status", False),
#             }


#             documents = []
#             index = 0
#             while True:
#                 doc_type = request.data.get(f"documents[{index}][document_type]")
#                 doc_file = request.data.get(f"documents[{index}][file]")
#                 if doc_type and doc_file:
#                     documents.append({
#                         "document_type": doc_type,
#                         "file": doc_file
#                     })
#                     index += 1
#                 else:
#                     break

#             application_data["documents"] = documents

#             serializer = JobApplicationSerializer(
#                 data=application_data,
#                 context={
#                     "request": request,
#                     "job_requisition": job_requisition
#                 }
#             )

#             if not serializer.is_valid():
#                 logger.error("Validation failed: %s", serializer.errors)
#                 return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#             with transaction.atomic():
#                 application = serializer.save()
#                 return Response({
#                     "detail": "Application submitted successfully.",
#                     "application_id": application.id
#                 }, status=status.HTTP_201_CREATED)

#         except Exception as e:
#             logger.exception("Unexpected error during job application submission")
#             return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class JobApplicationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]
    lookup_field = 'id'

    def get_queryset(self):
        tenant = self.request.tenant
        connection.set_schema(tenant.schema_name)
        logger.debug(f"Schema set to: {connection.schema_name}")
        return JobApplication.objects.filter(tenant=tenant)

    def perform_update(self, serializer):
        tenant = self.request.tenant
        with tenant_context(tenant):
            serializer.save()
        logger.info(f"Application updated: {serializer.instance.id} for tenant {tenant.schema_name}")

    def perform_destroy(self, instance):
        tenant = self.request.tenant
        with tenant_context(tenant):
            instance.delete()
        logger.info(f"Application deleted: {instance.id} for tenant {tenant.schema_name}")

class JobApplicationBulkDeleteView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]

    def post(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            logger.warning("No IDs provided for bulk delete")
            return Response({"detail": "No IDs provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tenant = request.tenant
            with tenant_context(tenant):
                applications = JobApplication.objects.filter(tenant=tenant, id__in=ids)
                count = applications.count()
                if count == 0:
                    logger.warning("No applications found for provided IDs")
                    return Response({"detail": "No applications found."}, status=status.HTTP_404_NOT_FOUND)
                applications.delete()
            logger.info(f"Bulk deleted {count} applications for tenant {tenant.schema_name}")
            return Response({"detail": f"Deleted {count} application(s)."}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Bulk delete failed: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
