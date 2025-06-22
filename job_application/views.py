from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated,AllowAny
from django_tenants.utils import tenant_context
from django.db import connection
from .serializers import JobApplicationSerializer
from talent_engine.models import JobRequisition
from .permissions import IsSubscribedAndAuthorized
import logging
logger = logging.getLogger('job_applications')
from .tenant_utils import resolve_tenant_from_unique_link
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from django.db import transaction
import os
from django.conf import  settings
from rest_framework.views import APIView
from .models import JobApplication
from .utils import parse_resume, screen_resume


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


class ResumeScreeningView(APIView):
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request, job_requisition_id):
        try:
            tenant = request.tenant
            document_type = request.data.get('document_type')
            
            with tenant_context(tenant):
                # Verify job requisition exists
                try:
                    job_requisition = JobRequisition.objects.get(id=job_requisition_id, tenant=tenant)
                except JobRequisition.DoesNotExist:
                    logger.error(f"JobRequisition {job_requisition_id} not found for tenant {tenant.schema_name}")
                    return Response({"detail": "Job requisition not found."}, status=status.HTTP_404_NOT_FOUND)

                # Validate document_type
                if not document_type:
                    logger.error(f"Missing document_type for JobRequisition {job_requisition_id}")
                    return Response({"detail": "Document type is required."}, status=status.HTTP_400_BAD_REQUEST)
                
                documents_required = job_requisition.documents_required or []
                if not documents_required:
                    logger.error(f"No documents required for JobRequisition {job_requisition_id}")
                    return Response(
                        {"detail": "No documents are required for this job requisition."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Case-insensitive comparison
                document_type_lower = document_type.lower()
                documents_required_lower = [doc.lower() for doc in documents_required]
                if document_type_lower not in documents_required_lower:
                    logger.error(f"Invalid document_type '{document_type}' for JobRequisition {job_requisition_id}. Expected one of {documents_required}")
                    return Response(
                        {"detail": f"Invalid document type: {document_type}. Must be one of {documents_required}."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Find the original case-sensitive document_type for processing
                document_type = next(
                    (doc for doc in documents_required if doc.lower() == document_type_lower),
                    document_type
                )

                # Get number of candidates needed
                num_candidates = job_requisition.number_of_candidates or 5  # Default to 5 if not set

                # Get applications with resumes
                applications = JobApplication.objects.filter(
                    tenant=tenant,
                    job_requisition=job_requisition,
                    resume_status=True
                )

                if not applications.exists():
                    logger.warning(f"No applications with resumes found for JobRequisition {job_requisition_id}")
                    return Response({"detail": "No applications with resumes found."}, status=status.HTTP_400_BAD_REQUEST)

                results = []
                with transaction.atomic():
                    for app in applications:
                        # Find document matching the selected document_type (case-insensitive)
                        cv_doc = next(
                            (doc for doc in app.documents if doc['document_type'].lower() == document_type_lower),
                            None
                        )
                        if not cv_doc:
                            app.screening_status = 'failed'
                            app.screening_score = 0.0
                            app.save()
                            results.append({
                                "application_id": app.id,
                                "full_name": app.full_name,
                                "email": app.email,
                                "score": 0.0,
                                "screening_status": app.screening_status,
                            })
                            logger.debug(f"No matching document for application {app.id} with document_type {document_type}")
                            continue

                        resume_text = parse_resume(os.path.join(settings.MEDIA_ROOT, cv_doc['file_path']))
                        if not resume_text:
                            app.screening_status = 'failed'
                            app.screening_score = 0.0
                            app.save()
                            results.append({
                                "application_id": app.id,
                                "full_name": app.full_name,
                                "email": app.email,
                                "score": 0.0,
                                "screening_status": app.screening_status,
                            })
                            logger.debug(f"Failed to parse resume for application {app.id}")
                            continue

                        # Combine job requirements for screening
                        job_requirements = (
                            (job_requisition.job_description or '') + ' ' +
                            (job_requisition.qualification_requirement or '') + ' ' +
                            (job_requisition.experience_requirement or '') + ' ' +
                            (job_requisition.knowledge_requirement or '')
                        ).strip()
                        
                        score = screen_resume(resume_text, job_requirements)
                        app.screening_status = 'processed'
                        app.screening_score = score
                        app.save()

                        results.append({
                            "application_id": app.id,
                            "full_name": app.full_name,
                            "email": app.email,
                            "score": score,
                            "screening_status": app.screening_status,
                        })

                    # Sort by score and select top N candidates
                    results.sort(key=lambda x: x['score'], reverse=True)
                    shortlisted = results[:num_candidates]
                    shortlisted_ids = {item['application_id'] for item in shortlisted}

                    # Update statuses
                    for app in applications:
                        if app.id in shortlisted_ids:
                            app.status = 'shortlisted'
                        else:
                            app.status = 'rejected'
                        app.save()

                logger.info(f"Screened {len(results)} resumes using document type '{document_type}', shortlisted {len(shortlisted)} for JobRequisition {job_requisition_id}")
                return Response({
                    "detail": f"Screened {len(results)} applications using '{document_type}', shortlisted {len(shortlisted)} candidates.",
                    "shortlisted_candidates": shortlisted,
                    "number_of_candidates": num_candidates,
                    "document_type": document_type
                }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error screening resumes for JobRequisition {job_requisition_id}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
