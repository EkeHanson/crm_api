from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated,AllowAny
from django_tenants.utils import tenant_context
from django.db import connection
from .serializers import JobApplicationSerializer
from talent_engine.models import JobRequisition
from .permissions import IsSubscribedAndAuthorized
import logging
from talent_engine.serializers import JobRequisitionSerializer
logger = logging.getLogger('job_applications')
from .tenant_utils import resolve_tenant_from_unique_link
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from django.db import transaction
from django.core.files.storage import default_storage
from rest_framework.views import APIView
from .utils import parse_resume, screen_resume, extract_resume_fields
from .models import Schedule, JobApplication
from .serializers import ScheduleSerializer



class ResumeParseView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [AllowAny]

    def post(self, request):
        logger.info("Received request to parse resume")
        unique_link = request.data.get('unique_link')  # Expect unique_link in FormData
        if unique_link:
            tenant, _ = resolve_tenant_from_unique_link(unique_link)
            if not tenant:
                logger.error("Invalid or expired unique_link")
                return Response({"detail": "Invalid or expired job link."}, status=status.HTTP_400_BAD_REQUEST)
            request.tenant = tenant  # Set tenant for storage or context
        else:
            logger.warning("No unique_link provided; proceeding without tenant context")

        try:
            resume_file = request.FILES.get('resume')
            if not resume_file:
                logger.error("No resume file provided")
                return Response({"detail": "Resume file is required."}, status=status.HTTP_400_BAD_REQUEST)

            # Save the file temporarily
            temp_file_path = default_storage.save(f'temp_resumes/{resume_file.name}', resume_file)
            full_path = default_storage.path(temp_file_path)

            # Parse resume text
            resume_text = parse_resume(full_path)

            # Clean up temporary file
            default_storage.delete(temp_file_path)

            if not resume_text:
                logger.warning("Failed to extract text from resume")
                return Response({"detail": "Could not extract text from resume."}, status=status.HTTP_400_BAD_REQUEST)

            # Extract structured fields
            extracted_data = extract_resume_fields(resume_text)

            logger.info("Successfully parsed resume and extracted fields")
            return Response({
                "detail": "Resume parsed successfully",
                "data": extracted_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error parsing resume: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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



class PublishedJobRequisitionsWithShortlistedApplicationsView(generics.ListAPIView):
    """
    Retrieve all published job requisitions that have applications, along with their shortlisted applications.
    """
    # permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]
    serializer_class = JobRequisitionSerializer

    def get_queryset(self):
        try:
            tenant = self.request.tenant
            connection.set_schema(tenant.schema_name)
            logger.debug(f"Schema set to: {connection.schema_name}")

            with tenant_context(tenant):
                # Fetch published job requisitions that have at least one application
                queryset = JobRequisition.objects.filter(
                    tenant=tenant,
                    publish_status=True,
                    applications__isnull=False
                ).distinct()

                logger.debug(f"Query: {queryset.query}")
                logger.info(f"Retrieved {queryset.count()} published job requisitions with applications for tenant {tenant.schema_name}")
                return queryset

        except Exception as e:
            logger.exception("Error retrieving published job requisitions with applications")
            raise

    def list(self, request, *args, **kwargs):
        try:
            tenant = request.tenant
            queryset = self.get_queryset()
            job_requisition_serializer = self.get_serializer(queryset, many=True)

            # Create a dictionary to map job requisition IDs to their serialized data
            job_requisition_dict = {item['id']: item for item in job_requisition_serializer.data}

            # Fetch shortlisted applications for each job requisition
            response_data = []
            with tenant_context(tenant):
                for job_requisition in queryset:
                    shortlisted_applications = JobApplication.objects.filter(
                        tenant=tenant,
                        job_requisition=job_requisition,
                        status='shortlisted'
                    ).select_related('job_requisition')
                    
                    application_serializer = JobApplicationSerializer(shortlisted_applications, many=True)
                    
                    total_applications = JobApplication.objects.filter(
                        tenant=tenant,
                        job_requisition=job_requisition
                    ).count()
                    
                    # Use the job_requisition.id to get the corresponding serialized data
                    response_data.append({
                        'job_requisition': job_requisition_dict.get(job_requisition.id),
                        'shortlisted_applications': application_serializer.data,
                        'shortlisted_count': shortlisted_applications.count(),
                        'total_applications': total_applications
                    })

            logger.info(f"Retrieved {len(response_data)} job requisitions with shortlisted applications for tenant {tenant.schema_name}")
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Error processing job requisitions and shortlisted applications")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)  


class ResumeScreeningView(APIView):
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request, job_requisition_id):
        try:
            tenant = request.tenant
            document_type = request.data.get('document_type')
            # print("request.data")
            # print(request.data)
            # print("request.data")
            with tenant_context(tenant):
                try:
                    job_requisition = JobRequisition.objects.get(id=job_requisition_id, tenant=tenant)
                except JobRequisition.DoesNotExist:
                    logger.error(f"JobRequisition {job_requisition_id} not found for tenant {tenant.schema_name}")
                    return Response({"detail": "Job requisition not found."}, status=status.HTTP_404_NOT_FOUND)

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

                document_type_lower = document_type.lower()
                documents_required_lower = [doc.lower() for doc in documents_required]
                if document_type_lower not in documents_required_lower:
                    logger.error(f"Invalid document_type '{document_type}' for JobRequisition {job_requisition_id}. Expected one of {documents_required}")
                    return Response(
                        {"detail": f"Invalid document type: {document_type}. Must be one of {documents_required}."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                document_type = next(
                    (doc for doc in documents_required if doc.lower() == document_type_lower),
                    document_type
                )
                num_candidates = job_requisition.number_of_candidates or 5  # Default to 5 if not set

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
                        resume_text = parse_resume(cv_doc['file_path'])
                       # resume_text = parse_resume(os.path.join(settings.MEDIA_ROOT, cv_doc['file_path']))
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



class ScheduleListCreateView(generics.GenericAPIView):
    serializer_class = ScheduleSerializer

    def get_permissions(self):
        """
        Override to apply different permissions based on the request method.
        - GET requires authentication and subscription authorization.
        - POST requires authentication only.
        """
        if self.request.method == 'GET':
            return [IsAuthenticated(), IsSubscribedAndAuthorized()]
        return [IsAuthenticated()]

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
                queryset = Schedule.objects.filter(tenant=tenant).select_related('job_application')
                status_param = request.query_params.get('status', None)
                if status_param:
                    queryset = queryset.filter(status=status_param)
                logger.debug(f"Query: {queryset.query}")
                serializer = self.get_serializer(queryset.order_by('-created_at'), many=True)
                logger.info(f"Retrieved {queryset.count()} schedules for tenant {tenant.schema_name}")
                return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error retrieving schedules for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, *args, **kwargs):
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

            serializer = self.get_serializer(data=request.data, context={'request': request})
            if not serializer.is_valid():
                logger.error(f"Validation failed: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            with tenant_context(tenant):
                job_application_id = serializer.validated_data.get('job_application').id
                try:
                    job_application = JobApplication.objects.get(id=job_application_id, tenant=tenant)
                except JobApplication.DoesNotExist:
                    logger.error(f"JobApplication {job_application_id} not found for tenant {tenant.schema_name}")
                    return Response({"detail": "Job application not found."}, status=status.HTTP_404_NOT_FOUND)

                schedule = serializer.save(tenant=tenant, job_application=job_application)
                logger.info(f"Schedule created: {schedule.id} for job application {job_application_id} in tenant {tenant.schema_name}")
                return Response({
                    "detail": "Schedule created successfully.",
                    "schedule_id": schedule.id
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception(f"Error creating schedule for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ScheduleDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ScheduleSerializer
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]
    lookup_field = 'tenant_unique_id'

    def get_queryset(self):
        try:
            tenant = self.request.tenant
            if not tenant:
                logger.error("No tenant associated with the request")
                raise Exception("Tenant not found.")

            logger.debug(f"User: {self.request.user}, Tenant: {tenant.schema_name}")
            logger.debug(f"Schema before set: {connection.schema_name}")
            connection.set_schema(tenant.schema_name)
            logger.debug(f"Schema after set: {connection.schema_name}")
            with connection.cursor() as cursor:
                cursor.execute("SHOW search_path;")
                search_path = cursor.fetchone()[0]
                logger.debug(f"Database search_path: {search_path}")

            with tenant_context(tenant):
                queryset = Schedule.objects.filter(tenant=tenant).select_related('job_application')
                logger.debug(f"Query: {queryset.query}")
                return queryset

        except Exception as e:
            logger.exception(f"Error accessing schedule for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            raise

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            logger.info(f"Retrieved schedule {instance.tenant_unique_id} for tenant {request.tenant.schema_name}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error retrieving schedule {kwargs.get('tenant_unique_id')} for tenant {request.tenant.schema_name}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
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

            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            if not serializer.is_valid():
                logger.error(f"Validation failed for schedule {instance.tenant_unique_id}: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            with tenant_context(tenant):
                # Handle status updates (complete or cancel)
                status_value = serializer.validated_data.get('status')
                if status_value == 'completed' and instance.status == 'scheduled':
                    serializer.validated_data['cancellation_reason'] = None
                elif status_value == 'cancelled' and instance.status == 'scheduled':
                    cancellation_reason = request.data.get('cancellation_reason')
                    if not cancellation_reason:
                        logger.error(f"Attempt to cancel schedule {instance.tenant_unique_id} without reason for tenant {tenant.schema_name}")
                        return Response(
                            {"detail": "Cancellation reason is required."},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    serializer.validated_data['cancellation_reason'] = cancellation_reason
                elif status_value and status_value not in ['completed', 'cancelled']:
                    logger.error(f"Invalid status update {status_value} for schedule {instance.tenant_unique_id}")
                    return Response(
                        {"detail": "Invalid status update. Status must be 'completed' or 'cancelled'."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                serializer.save()
                logger.info(f"Schedule {instance.tenant_unique_id} updated for tenant {tenant.schema_name}")
                return Response({
                    "detail": "Schedule updated successfully.",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error updating schedule {kwargs.get('tenant_unique_id')} for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, *args, **kwargs):
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

            instance = self.get_object()
            with tenant_context(tenant):
                instance.delete()
                logger.info(f"Schedule deleted: {instance.tenant_unique_id} for tenant {tenant.schema_name}")
                return Response({"detail": "Schedule deleted successfully."}, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            logger.exception(f"Error deleting schedule {kwargs.get('tenant_unique_id')} for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class ScheduleBulkDeleteView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]

    def post(self, request, *args, **kwargs):
        try:
            tenant = request.tenant
            if not tenant:
                logger.error("No tenant associated with the request")
                return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)

            ids = request.data.get('ids', [])
            if not ids:
                logger.error("No schedule IDs provided for bulk deletion")
                return Response({"detail": "No schedule IDs provided."}, status=status.HTTP_400_BAD_REQUEST)

            logger.debug(f"User: {request.user}, Tenant: {tenant.schema_name}")
            connection.set_schema(tenant.schema_name)
            with tenant_context(tenant):
                deleted_count = Schedule.objects.filter(tenant_unique_id__in=ids, tenant=tenant).delete()[0]
                logger.info(f"Deleted {deleted_count} schedules for tenant {tenant.schema_name}")
                return Response({"detail": f"Successfully deleted {deleted_count} schedules."}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error deleting schedules for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)