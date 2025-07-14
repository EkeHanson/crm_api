import logging
import os
import uuid
import pytz
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.mail import EmailMessage
from django.db import connection, transaction
from django.utils import timezone
from django_tenants.utils import tenant_context
from rest_framework import generics, serializers, status
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from core.utils.email_config import configure_email_backend
from core.models import TenantConfig
from talent_engine.models import JobRequisition
from talent_engine.serializers import JobRequisitionSerializer
from .models import JobApplication, Schedule
from .permissions import IsSubscribedAndAuthorized, BranchRestrictedPermission
from .serializers import JobApplicationSerializer, ScheduleSerializer, DocumentSerializer
from .tenant_utils import resolve_tenant_from_unique_link
from django_tenants.utils import schema_context
from .utils import parse_resume, screen_resume, extract_resume_fields

logger = logging.getLogger('job_applications')

class ResumeParseView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [AllowAny]

    def post(self, request):
        unique_link = request.data.get('unique_link')
        if unique_link:
            tenant, _ = resolve_tenant_from_unique_link(unique_link)
            if not tenant:
                logger.error("Invalid or expired unique_link")
                return Response({"detail": "Invalid or expired job link."}, status=status.HTTP_400_BAD_REQUEST)
            request.tenant = tenant
        else:
            logger.warning("No unique_link provided; proceeding without tenant context")

        try:
            resume_file = request.FILES.get('resume')
            if not resume_file:
                logger.error("No resume file provided")
                return Response({"detail": "Resume file is required."}, status=status.HTTP_400_BAD_REQUEST)

            temp_file_path = default_storage.save(f'temp_resumes/{resume_file.name}', resume_file)
            full_path = default_storage.path(temp_file_path)
            resume_text = parse_resume(full_path)
            default_storage.delete(temp_file_path)

            if not resume_text:
                logger.warning("Failed to extract text from resume")
                return Response({"detail": "Could not extract text from resume."}, status=status.HTTP_400_BAD_REQUEST)

            extracted_data = extract_resume_fields(resume_text)
            logger.info("Successfully parsed resume and extracted fields")
            return Response({
                "detail": "Resume parsed successfully",
                "data": extracted_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error parsing resume: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ResendRejectionEmailsView(APIView):
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized, BranchRestrictedPermission]
    parser_classes = [JSONParser]

    def post(self, request, job_requisition_id):
        try:
            tenant = request.tenant
            application_ids = request.data.get('application_ids', [])
            if not application_ids:
                logger.error("No application IDs provided for resending rejection emails")
                return Response({"detail": "Application IDs are required."}, status=status.HTTP_400_BAD_REQUEST)

            with tenant_context(tenant):
                try:
                    job_requisition = JobRequisition.objects.get(id=job_requisition_id, tenant=tenant)
                except JobRequisition.DoesNotExist:
                    logger.error(f"JobRequisition {job_requisition_id} not found for tenant {tenant.schema_name}")
                    return Response({"detail": "Job requisition not found."}, status=status.HTTP_404_NOT_FOUND)

                applications = JobApplication.active_objects.filter(
                    tenant=tenant,
                    job_requisition=job_requisition,
                    id__in=application_ids,
                    status='rejected'
                )
                if request.user.role == 'recruiter' and request.user.branch:
                    applications = applications.filter(branch=request.user.branch)

                if not applications.exists():
                    logger.warning(f"No rejected applications found for IDs {application_ids}")
                    return Response({"detail": "No rejected applications found."}, status=status.HTTP_400_BAD_REQUEST)

                failed_emails = []
                try:
                    tenant_config = TenantConfig.objects.get(tenant=tenant)
                    email_config = tenant_config.email_templates.get('interviewRejection', {})
                    
                    if not email_config.get('is_auto_sent', False):
                        logger.info(f"Auto-send not enabled for interviewRejection template for tenant {tenant.schema_name}")
                        return Response({"detail": "Auto-send is not enabled for rejection emails."}, status=status.HTTP_400_BAD_REQUEST)

                    email_template = email_config.get('content', '')
                    if not email_template:
                        logger.warning(f"No email template content found for interviewRejection for tenant {tenant.schema_name}")
                        return Response({"detail": "No email template content found."}, status=status.HTTP_400_BAD_REQUEST)

                    email_backend = configure_email_backend(tenant)
                    for app in applications:
                        try:
                            email_content = email_template.replace('[Candidate Name]', app.full_name)
                            email_content = email_content.replace('[Job Title]', job_requisition.title)
                            email_content = email_content.replace('[Your Name]', 'Hiring Manager')
                            email_content = email_content.replace('[your.email@proliance.com]', tenant.default_from_email or 'hiring@proliance.com')

                            email = EmailMessage(
                                subject=f'Application Update for {job_requisition.title} at Proliance',
                                body=email_content,
                                from_email=tenant.default_from_email or 'hiring@proliance.com',
                                to=[app.email],
                                connection=email_backend
                            )
                            email.send()
                            logger.info(f"Rejection email sent to {app.email} for JobRequisition {job_requisition.id}")
                        except Exception as e:
                            logger.error(f"Failed to send rejection email to {app.email}: {str(e)}")
                            failed_emails.append({
                                "application_id": app.id,
                                "full_name": app.full_name,
                                "email": app.email
                            })
                except TenantConfig.DoesNotExist:
                    logger.error(f"Tenant configuration not found for tenant {tenant.schema_name}")
                    return Response({"detail": "Tenant configuration not found."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                response_data = {
                    "detail": f"Attempted to resend rejection emails to {len(applications)} applicants.",
                    "failed_emails": failed_emails
                }
                return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error resending rejection emails for JobRequisition {job_requisition_id}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ResumeScreeningView(APIView):
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized, BranchRestrictedPermission]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def send_rejection_emails(self, tenant, job_requisition, applications):
        try:
            tenant_config = TenantConfig.objects.get(tenant=tenant)
            email_config = tenant_config.email_templates.get('interviewRejection', {})
            
            if not email_config.get('is_auto_sent', False):
                logger.info(f"Auto-send not enabled for interviewRejection template for tenant {tenant.schema_name}")
                return

            email_template = email_config.get('content', '')
            if not email_template:
                logger.warning(f"No email template content found for interviewRejection for tenant {tenant.schema_name}")
                return

            email_backend = configure_email_backend(tenant)
            for app in applications:
                if app.status == 'rejected':
                    try:
                        email_content = email_template.replace('[Candidate Name]', app.full_name)
                        email_content = email_content.replace('[Job Title]', job_requisition.title)
                        email_content = email_content.replace('[Your Name]', 'Hiring Manager')
                        email_content = email_content.replace('[your.email@proliance.com]', tenant.default_from_email or 'hiring@proliance.com')

                        email = EmailMessage(
                            subject=f'Application Update for {job_requisition.title} at Proliance',
                            body=email_content,
                            from_email=tenant.default_from_email or 'hiring@proliance.com',
                            to=[app.email],
                            connection=email_backend
                        )
                        email.send()
                        logger.info(f"Rejection email sent to {app.email} for JobRequisition {job_requisition.id}")
                    except Exception as e:
                        logger.error(f"Failed to send rejection email to {app.email}: {str(e)}")

        except TenantConfig.DoesNotExist:
            logger.error(f"Tenant configuration not found for tenant {tenant.schema_name}")
        except Exception as e:
            logger.error(f"Error in send_rejection_emails for tenant {tenant.schema_name}: {str(e)}")

    def post(self, request, job_requisition_id):
        try:
            tenant = request.tenant
            document_type = request.data.get('document_type')
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
                    logger.error(f"Invalid document_type '{document_type}' for JobRequisition {job_requisition_id}")
                    return Response(
                        {"detail": f"Invalid document type: {document_type}. Must be one of {documents_required}."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                document_type = next(
                    (doc for doc in documents_required if doc.lower() == document_type_lower),
                    document_type
                )
                num_candidates = job_requisition.number_of_candidates or 5

                applications = JobApplication.active_objects.filter(
                    tenant=tenant,
                    job_requisition=job_requisition,
                    resume_status=True
                )
                if request.user.role == 'recruiter' and request.user.branch:
                    applications = applications.filter(branch=request.user.branch)

                if not applications.exists():
                    logger.warning(f"No applications with resumes found for JobRequisition {job_requisition_id}")
                    return Response({"detail": "No applications with resumes found."}, status=status.HTTP_400_BAD_REQUEST)

                results = []
                with transaction.atomic():
                    for app in applications:
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
                                "employment_gaps": []
                            })
                            logger.debug(f"No matching document for application {app.id} with document_type {document_type}")
                            continue
                        resume_text = parse_resume(cv_doc['file_path'])
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
                                "employment_gaps": []
                            })
                            logger.debug(f"Failed to parse resume for application {app.id}")
                            continue

                        job_requirements = (
                            (job_requisition.job_description or '') + ' ' +
                            (job_requisition.qualification_requirement or '') + ' ' +
                            (job_requisition.experience_requirement or '') + ' ' +
                            (job_requisition.knowledge_requirement or '')
                        ).strip()
                        
                        score = screen_resume(resume_text, job_requirements)
                        resume_data = extract_resume_fields(resume_text)
                        employment_gaps = resume_data.get("employment_gaps", [])
                        logger.debug(f"Employment gaps for application {app.id}: {employment_gaps}")

                        app.screening_status = 'processed'
                        app.screening_score = score
                        app.employment_gaps = employment_gaps
                        app.save()

                        results.append({
                            "application_id": app.id,
                            "full_name": app.full_name,
                            "email": app.email,
                            "score": score,
                            "screening_status": app.screening_status,
                            "employment_gaps": employment_gaps
                        })

                    results.sort(key=lambda x: x['score'], reverse=True)
                    shortlisted = results[:num_candidates]
                    shortlisted_ids = {item['application_id'] for item in shortlisted}

                    for app in applications:
                        if app.id in shortlisted_ids:
                            app.status = 'shortlisted'
                        else:
                            app.status = 'rejected'
                        app.save()

                    self.send_rejection_emails(tenant, job_requisition, applications)

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

class JobApplicationWithSchedulesView(generics.RetrieveAPIView):
    serializer_class = JobApplicationSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        tenant = self.request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            raise generics.ValidationError("Tenant not found.")
        connection.set_schema(tenant.schema_name)
        logger.debug(f"Schema set to: {connection.schema_name}")
        return JobApplication.active_objects.filter(tenant=tenant).select_related('job_requisition')

    def retrieve(self, request, *args, **kwargs):
        try:
            unique_link = request.query_params.get('unique_link')
            if not unique_link:
                logger.error("No unique_link provided in the request")
                return Response({"detail": "Unique link is required."}, status=status.HTTP_400_BAD_REQUEST)

            tenant, job_requisition = resolve_tenant_from_unique_link(unique_link)
            if not tenant or not job_requisition:
                logger.error(f"Invalid or expired unique_link: {unique_link}")
                return Response({"detail": "Invalid or expired job link."}, status=status.HTTP_400_BAD_REQUEST)

            request.tenant = tenant
            connection.set_schema(tenant.schema_name)
            logger.debug(f"Schema set to: {connection.schema_name}")

            job_application_code = self.kwargs.get('code')
            email = self.kwargs.get('email')
            if not job_application_code or not email:
                logger.error("Missing job_application_code or email in request")
                return Response({"detail": "Both job application code and email are required."}, status=status.HTTP_400_BAD_REQUEST)

            with tenant_context(tenant):
                try:
                    job_application = JobApplication.active_objects.get(
                        job_requisition__job_application_code=job_application_code,
                        email=email,
                        tenant=tenant
                    )
                except JobApplication.DoesNotExist:
                    logger.error(f"JobApplication with job_application_code {job_application_code} and email {email} not found for tenant {tenant.schema_name}")
                    return Response({"detail": "Job application not found."}, status=status.HTTP_404_NOT_FOUND)
                except JobApplication.MultipleObjectsReturned:
                    logger.error(f"Multiple JobApplications found for job_application_code {job_application_code} and email {email} in tenant {tenant.schema_name}")
                    return Response({"detail": "Multiple job applications found. Please contact support."}, status=status.HTTP_400_BAD_REQUEST)

                job_application_serializer = self.get_serializer(job_application)
                job_requisition = job_application.job_requisition
                job_requisition_serializer = JobRequisitionSerializer(job_requisition)
                schedules = Schedule.active_objects.filter(
                    tenant=tenant,
                    job_application=job_application
                ).select_related('job_application')
                if request.user.is_authenticated and request.user.role == 'recruiter' and request.user.branch:
                    schedules = schedules.filter(branch=request.user.branch)
                schedule_serializer = ScheduleSerializer(schedules, many=True)

                response_data = {
                    'job_application': job_application_serializer.data,
                    'job_requisition': job_requisition_serializer.data,
                    'schedules': schedule_serializer.data,
                    'schedule_count': schedules.count()
                }

                logger.info(f"Retrieved job application with code {job_application_code} and email {email} with requisition {job_requisition.id} and {schedules.count()} schedules for tenant {tenant.schema_name}")
                return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error retrieving job application with code {self.kwargs.get('code')} and email {self.kwargs.get('email')} for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class JobApplicationsByRequisitionView(generics.ListAPIView):
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized, BranchRestrictedPermission]

    def get_queryset(self):
        try:
            tenant = self.request.tenant
            job_requisition_id = self.kwargs['job_requisition_id']
            connection.set_schema(tenant.schema_name)
            logger.debug(f"Schema set to: {connection.schema_name}")
            
            with tenant_context(tenant):
                try:
                    job_requisition = JobRequisition.objects.get(id=job_requisition_id, tenant=tenant)
                except JobRequisition.DoesNotExist:
                    logger.error(f"JobRequisition {job_requisition_id} not found for tenant {tenant.schema_name}")
                    raise generics.get_object_or_404(JobRequisition, id=job_requisition_id, tenant=tenant)
                
                applications = JobApplication.active_objects.filter(
                    tenant=tenant,
                    job_requisition=job_requisition
                ).select_related('job_requisition')
                if self.request.user.role == 'recruiter' and self.request.user.branch:
                    applications = applications.filter(branch=self.request.user.branch)
                
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
    serializer_class = JobRequisitionSerializer
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized, BranchRestrictedPermission]

    def get_queryset(self):
        try:
            tenant = self.request.tenant
            connection.set_schema(tenant.schema_name)
            logger.debug(f"Schema set to: {connection.schema_name}")

            with tenant_context(tenant):
                queryset = JobRequisition.objects.filter(
                    tenant=tenant,
                    publish_status=True,
                    applications__isnull=False,
                    applications__is_deleted=False
                ).distinct()
                if self.request.user.role == 'recruiter' and self.request.user.branch:
                    queryset = queryset.filter(applications__branch=self.request.user.branch)
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

            job_requisition_dict = {item['id']: item for item in job_requisition_serializer.data}

            response_data = []
            with tenant_context(tenant):
                for job_requisition in queryset:
                    shortlisted_applications = JobApplication.active_objects.filter(
                        tenant=tenant,
                        job_requisition=job_requisition,
                        status='shortlisted'
                    ).select_related('job_requisition')
                    if request.user.role == 'recruiter' and request.user.branch:
                        shortlisted_applications = shortlisted_applications.filter(branch=request.user.branch)
                    
                    application_serializer = JobApplicationSerializer(shortlisted_applications, many=True)
                    
                    total_applications = JobApplication.active_objects.filter(
                        tenant=tenant,
                        job_requisition=job_requisition
                    )
                    if request.user.role == 'recruiter' and request.user.branch:
                        total_applications = total_applications.filter(branch=request.user.branch)
                    total_applications = total_applications.count()
                    
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




class JobApplicationListCreateView(generics.GenericAPIView):
    parser_classes = (MultiPartParser, FormParser)
    serializer_class = JobApplicationSerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated(), IsSubscribedAndAuthorized(), BranchRestrictedPermission()]
        return [AllowAny()]

    def get_queryset(self):
        tenant = self.request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            raise serializers.ValidationError("Tenant not found.")
        connection.set_schema(tenant.schema_name)
        with connection.cursor() as cursor:
            cursor.execute("SHOW search_path;")
            search_path = cursor.fetchone()[0]
            logger.debug(f"Database search_path: {search_path}")
        queryset = JobApplication.active_objects.filter(tenant=tenant).select_related('job_requisition')
        if self.request.user.branch:
        # if self.request.user.role == 'recruiter' and self.request.user.branch:
            queryset = queryset.filter(branch=self.request.user.branch)
        return queryset

    def get(self, request, *args, **kwargs):
        try:
            applications = self.get_queryset()
            serializer = self.get_serializer(applications, many=True)
            logger.info(f"Retrieved {len(applications)} job applications for tenant {request.tenant.schema_name}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error retrieving job applications: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, *args, **kwargs):
        try:
            unique_link = request.data.get("unique_link")
            if not unique_link:
                logger.error("Missing unique_link in POST request")
                return Response({"detail": "Missing unique_link."}, status=status.HTTP_400_BAD_REQUEST)

            tenant, job_requisition = resolve_tenant_from_unique_link(unique_link)
            if not tenant or not job_requisition:
                logger.error(f"Invalid or expired unique_link: {unique_link}")
                return Response({"detail": "Invalid or expired job link."}, status=status.HTTP_400_BAD_REQUEST)

            request.tenant = tenant
            connection.set_schema(tenant.schema_name)

            application_data = {
                "job_requisition": job_requisition.id,
                "full_name": request.data.get("full_name"),
                "email": request.data.get("email"),
                "phone": request.data.get("phone"),
                "qualification": request.data.get("qualification"),
                "experience": request.data.get("experience"),
                "knowledge_skill": request.data.get("knowledge_skill"),
                "date_of_birth": request.data.get("date_of_birth"),
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
                logger.error(f" Validation failed: {serializer.errors}")
                print(f" Validation failed: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                application = serializer.save()
                logger.info(f"Application created: {application.id} for tenant {tenant.schema_name}")
                return Response({
                    "detail": "Application submitted successfully.",
                    "application_id": application.id
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception(f"Unexpected error during job application submission: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)



class JobApplicationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized, BranchRestrictedPermission]
    lookup_field = 'id'

    def get_queryset(self):
        tenant = self.request.tenant
        connection.set_schema(tenant.schema_name)
        logger.debug(f"Schema set to: {connection.schema_name}")
        queryset = JobApplication.active_objects.filter(tenant=tenant)
        if self.request.user.role == 'recruiter' and self.request.user.branch:
            queryset = queryset.filter(branch=self.request.user.branch)
        return queryset

    def perform_update(self, serializer):
        tenant = self.request.tenant
        with tenant_context(tenant):
            serializer.save()
            logger.info(f"Application updated: {serializer.instance.id} for tenant {tenant.schema_name}")

    def perform_destroy(self, instance):
        tenant = self.request.tenant
        with tenant_context(tenant):
            instance.soft_delete()
            logger.info(f"Application soft-deleted: {instance.id} for tenant {tenant.schema_name}")

class JobApplicationBulkDeleteView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized, BranchRestrictedPermission]

    def post(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            logger.warning("No IDs provided for bulk soft delete")
            return Response({"detail": "No IDs provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tenant = request.tenant
            with tenant_context(tenant):
                applications = JobApplication.active_objects.filter(tenant=tenant, id__in=ids)
                if request.user.role == 'recruiter' and request.user.branch:
                    applications = applications.filter(branch=request.user.branch)
                count = applications.count()
                if count == 0:
                    logger.warning("No active applications found for provided IDs")
                    return Response({"detail": "No applications found."}, status=status.HTTP_404_NOT_FOUND)
                with transaction.atomic():
                    for application in applications:
                        application.soft_delete()
                    logger.info(f"Soft-deleted {count} applications for tenant {tenant.schema_name}")
            return Response({"detail": f"Soft-deleted {count} application(s)."}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Bulk soft delete failed: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SoftDeletedJobApplicationsView(generics.ListAPIView):
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized, BranchRestrictedPermission]

    def get_queryset(self):
        tenant = self.request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            raise generics.ValidationError("Tenant not found.")

        logger.debug(f"User: {self.request.user}, Tenant: {tenant.schema_name}")
        connection.set_schema(tenant.schema_name)
        with tenant_context(tenant):
            queryset = JobApplication.objects.filter(tenant=tenant, is_deleted=True).select_related('job_requisition')
            if self.request.user.role == 'recruiter' and self.request.user.branch:
                queryset = queryset.filter(branch=self.request.user.branch)
            logger.debug(f"Query: {queryset.query}")
            return queryset

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            logger.info(f"Retrieved {queryset.count()} soft-deleted job applications for tenant {request.tenant.schema_name}")
            return Response({
                "detail": f"Retrieved {queryset.count()} soft-deleted application(s).",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error listing soft-deleted job applications for tenant {request.tenant.schema_name}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RecoverSoftDeletedJobApplicationsView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized, BranchRestrictedPermission]

    def post(self, request, *args, **kwargs):
        logger.debug(f"Received POST request to recover job applications: {request.data}")
        try:
            tenant = request.tenant
            if not tenant:
                logger.error("No tenant associated with the request")
                return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)

            ids = request.data.get('ids', [])
            if not ids:
                logger.warning("No application IDs provided for recovery")
                return Response({"detail": "No application IDs provided."}, status=status.HTTP_400_BAD_REQUEST)

            connection.set_schema(tenant.schema_name)
            with tenant_context(tenant):
                applications = JobApplication.objects.filter(id__in=ids, tenant=tenant, is_deleted=True)
                if request.user.role == 'recruiter' and request.user.branch:
                    applications = applications.filter(branch=request.user.branch)
                if not applications.exists():
                    logger.warning(f"No soft-deleted applications found for IDs {ids} in tenant {tenant.schema_name}")
                    return Response({"detail": "No soft-deleted applications found."}, status=status.HTTP_404_NOT_FOUND)

                recovered_count = 0
                with transaction.atomic():
                    for application in applications:
                        application.restore()
                        recovered_count += 1

                logger.info(f"Successfully recovered {recovered_count} applications for tenant {tenant.schema_name}")
                return Response({
                    "detail": f"Successfully recovered {recovered_count} application(s)."
                }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error during recovery of applications for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PermanentDeleteJobApplicationsView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized, BranchRestrictedPermission]

    def post(self, request, *args, **kwargs):
        logger.debug(f"Received POST request to permanently delete job applications: {request.data}")
        try:
            tenant = request.tenant
            if not tenant:
                logger.error("No tenant associated with the request")
                return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)

            ids = request.data.get('ids', [])
            if not ids:
                logger.warning("No application IDs provided for permanent deletion")
                return Response({"detail": "No application IDs provided."}, status=status.HTTP_400_BAD_REQUEST)

            connection.set_schema(tenant.schema_name)
            with tenant_context(tenant):
                applications = JobApplication.objects.filter(id__in=ids, tenant=tenant, is_deleted=True)
                if request.user.role == 'recruiter' and request.user.branch:
                    applications = applications.filter(branch=request.user.branch)
                if not applications.exists():
                    logger.warning(f"No soft-deleted applications found for IDs {ids} in tenant {tenant.schema_name}")
                    return Response({"detail": "No soft-deleted applications found."}, status=status.HTTP_404_NOT_FOUND)

                deleted_count = applications.delete()[0]
                logger.info(f"Successfully permanently deleted {deleted_count} applications for tenant {tenant.schema_name}")
                return Response({
                    "detail": f"Successfully permanently deleted {deleted_count} application(s)."
                }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error during permanent deletion of applications for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class ScheduleListCreateView(generics.GenericAPIView):
    serializer_class = ScheduleSerializer
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized, BranchRestrictedPermission]

    def get_queryset(self):
        tenant = self.request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            raise serializers.ValidationError("Tenant not found.")
        connection.set_schema(tenant.schema_name)
        with connection.cursor() as cursor:
            cursor.execute("SHOW search_path;")
            search_path = cursor.fetchone()[0]
            logger.debug(f"Database search_path: {search_path}")
        queryset = Schedule.active_objects.filter(tenant=tenant).select_related('job_application')
        if self.request.user.branch:
            queryset = queryset.filter(branch=self.request.user.branch)
        status_param = self.request.query_params.get('status', None)
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset

    def get(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset.order_by('-created_at'), many=True)
            logger.info(f"Retrieved {queryset.count()} schedules for tenant {request.tenant.schema_name}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error retrieving schedules for tenant {request.tenant.schema_name}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, *args, **kwargs):
        try:
            tenant = self.request.tenant
            if not tenant:
                logger.error("No tenant associated with the request")
                return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)

            logger.debug(f"User: {request.user}, Tenant: {tenant.schema_name}")
            connection.set_schema(tenant.schema_name)
            with connection.cursor() as cursor:
                cursor.execute("SHOW search_path;")
                search_path = cursor.fetchone()[0]
                logger.debug(f"Database search_path: {search_path}")

            # Validate email configuration from Tenant model
            required_email_fields = ['email_host', 'email_port', 'email_host_user', 'email_host_password', 'default_from_email']
            missing_fields = [field for field in required_email_fields if not getattr(tenant, field)]
            if missing_fields:
                logger.error(f"Missing email configuration fields for tenant {tenant.schema_name}: {missing_fields}")
                return Response(
                    {"detail": f"Missing email configuration: {', '.join(missing_fields)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            data = request.data.copy()
            job_application_ids = data.get('job_application', [])
            if not isinstance(job_application_ids, list):
                job_application_ids = [job_application_ids]

            if not job_application_ids:
                logger.error("No job application IDs provided")
                return Response({"detail": "At least one job application ID is required."}, status=status.HTTP_400_BAD_REQUEST)

            created_schedules = []
            with tenant_context(tenant):
                try:
                    config = TenantConfig.objects.get(tenant=tenant)
                    email_template = config.email_templates.get('interviewScheduling', {})
                    template_content = email_template.get('content', '')
                    is_auto_sent = email_template.get('is_auto_sent', False)
                except TenantConfig.DoesNotExist:
                    logger.warning(f"TenantConfig not found for tenant {tenant.schema_name}")
                    template_content = ''
                    is_auto_sent = False

                for job_application_id in job_application_ids:
                    serializer = self.get_serializer(data={**data, 'job_application': job_application_id}, context={'request': request})
                    if not serializer.is_valid():
                        logger.error(f"Validation failed for job application {job_application_id}: {serializer.errors}")
                        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

                    try:
                        job_application = JobApplication.active_objects.get(id=job_application_id, tenant=tenant)
                    except JobApplication.DoesNotExist:
                        logger.error(f"JobApplication {job_application_id} not found for tenant {tenant.schema_name}")
                        return Response({"detail": f"Job application {job_application_id} not found."}, status=status.HTTP_404_NOT_FOUND)

                    with transaction.atomic():
                        timezone_str = serializer.validated_data.get('timezone', 'UTC')
                        interview_date_time = serializer.validated_data['interview_date_time']
                        interview_date = interview_date_time.strftime("%d %b %Y")
                        interview_time = interview_date_time.astimezone(pytz.timezone(timezone_str)).strftime("%I:%M %p")
                        location = serializer.validated_data.get('meeting_link') if serializer.validated_data['meeting_mode'] == 'Virtual' else serializer.validated_data.get('interview_address', '')
                        placeholders = {
                            '[Candidate Name]': job_application.full_name,
                            '[Position]': job_application.job_requisition.title,
                            '[Company]': tenant.name,
                            '[Insert Date]': interview_date,
                            '[Insert Time]': interview_time,
                            '[Meeting Mode]': 'Zoom' if serializer.validated_data['meeting_mode'] == 'Virtual' else 'On-site',
                            '[Zoom / Google Meet / On-site – Insert Address or Link]': location,
                            '[Name(s) & Position(s)]': request.user.get_full_name() or 'Hiring Team',
                            '[Your Name]': request.user.get_full_name() or 'Hiring Team',
                            '[your.email@proliance.com]': tenant.default_from_email or 'no-reply@proliance.com',
                            '[Dashboard Link]': f"{settings.WEB_PAGE_URL}/application-dashboard/{job_application.job_requisition.job_application_code}/{job_application.email}/{job_application.job_requisition.unique_link}",
                            '[Timezone]': timezone_str,
                        }

                        email_body = data.get('message', template_content)
                        if not data.get('message') and template_content:
                            for placeholder, value in placeholders.items():
                                email_body = email_body.replace(placeholder, str(value))

                        schedule = serializer.save(
                            tenant=tenant,
                            job_application=job_application,
                            branch=request.user.branch if request.user.is_authenticated and request.user.branch else job_application.branch,
                            #branch=request.user.branch if request.user.is_authenticated and request.user.role == 'recruiter' and request.user.branch else job_application.branch,
                            message=email_body if is_auto_sent else ''
                        )
                        created_schedules.append(schedule.id)

                        if is_auto_sent:
                            try:
                                email_connection = configure_email_backend(tenant)
                                # Log email configuration settings
                                print(f"Email configuration for tenant {tenant.schema_name}: "
                                            f"host={tenant.email_host}, "
                                            f"port={tenant.email_port}, "
                                            f"use_ssl={tenant.email_use_ssl}, "
                                            f"host_user={tenant.email_host_user}, "
                                            f"host_password={'*' * len(tenant.email_host_password) if tenant.email_host_password else None}, "
                                            f"default_from_email={tenant.default_from_email}")
                                
                                logger.info(f"Email configuration for tenant {tenant.schema_name}: "
                                            f"host={tenant.email_host}, "
                                            f"port={tenant.email_port}, "
                                            f"use_ssl={tenant.email_use_ssl}, "
                                            f"host_user={tenant.email_host_user}, "
                                            f"host_password={'*' * len(tenant.email_host_password) if tenant.email_host_password else None}, "
                                            f"default_from_email={tenant.default_from_email}")
                                
                                email_subject = f"Interview Schedule for {job_application.job_requisition.title}"
                                email = EmailMessage(
                                    subject=email_subject,
                                    body=email_body,
                                    from_email=tenant.default_from_email or 'no-reply@proliance.com',
                                    to=[job_application.email],
                                    connection=email_connection,
                                )
                                email.content_subtype = 'html'
                                email.send(fail_silently=False)
                                logger.info(f"Email sent to {job_application.email} for schedule {schedule.id} in tenant {tenant.schema_name}")
                            except Exception as email_error:
                                logger.exception(f"Failed to send email for schedule {schedule.id} to {job_application.email}: {str(email_error)}")
                                return Response({"detail": f"Failed to send email: {str(email_error)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response({
                "detail": "Schedules created successfully.",
                "schedule_ids": created_schedules
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception(f"Error creating schedules for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)




class TimezoneChoicesView(APIView):
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized]

    def get(self, request):
        timezone_choices = [
            {"value": value, "label": label} for value, label in Schedule.TIMEZONE_CHOICES
        ]
        return Response(timezone_choices, status=status.HTTP_200_OK)

class ScheduleDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ScheduleSerializer
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized, BranchRestrictedPermission]
    lookup_field = 'id'

    def get_queryset(self):
        try:
            tenant = self.request.tenant
            if not tenant:
                logger.error("No tenant associated with the request")
                raise Exception("Tenant not found.")

            logger.debug(f"User: {self.request.user}, Tenant: {tenant.schema_name}")
            connection.set_schema(tenant.schema_name)
            logger.debug(f"Schema after set: {connection.schema_name}")
            with connection.cursor() as cursor:
                cursor.execute("SHOW search_path;")
                search_path = cursor.fetchone()[0]
                logger.debug(f"Database search_path: {search_path}")

            with tenant_context(tenant):
                queryset = Schedule.active_objects.filter(tenant=tenant).select_related('job_application')
                if self.request.user.role == 'recruiter' and self.request.user.branch:
                    queryset = queryset.filter(branch=self.request.user.branch)
                logger.debug(f"Query: {queryset.query}")
                return queryset

        except Exception as e:
            logger.exception(f"Error accessing schedule for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            raise

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            logger.info(f"Retrieved schedule {instance.id} for tenant {request.tenant.schema_name}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error retrieving schedule {kwargs.get('id')} for tenant {request.tenant.schema_name}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
        try:
            tenant = request.tenant
            if not tenant:
                logger.error("No tenant associated with the request")
                return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)

            logger.debug(f"User: {request.user}, Tenant: {tenant.schema_name}")
            connection.set_schema(tenant.schema_name)
            logger.debug(f"Schema after set: {connection.schema_name}")
            with connection.cursor() as cursor:
                cursor.execute("SHOW search_path;")
                search_path = cursor.fetchone()[0]
                logger.debug(f"Database search_path: {search_path}")

            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            if not serializer.is_valid():
                logger.error(f"Validation failed for schedule {instance.id}: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            with tenant_context(tenant):
                status_value = serializer.validated_data.get('status')
                if status_value == 'completed' and instance.status == 'scheduled':
                    serializer.validated_data['cancellation_reason'] = None
                elif status_value == 'cancelled' and instance.status == 'scheduled':
                    cancellation_reason = request.data.get('cancellation_reason')
                    if not cancellation_reason:
                        logger.error(f"Attempt to cancel schedule {instance.id} without reason for tenant {tenant.schema_name}")
                        return Response(
                            {"detail": "Cancellation reason is required."},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    serializer.validated_data['cancellation_reason'] = cancellation_reason
                elif status_value and status_value not in ['completed', 'cancelled']:
                    logger.error(f"Invalid status update {status_value} for schedule {instance.id}")
                    return Response(
                        {"detail": "Invalid status update. Status must be 'completed' or 'cancelled'."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                serializer.save()
                logger.info(f"Schedule {instance.id} updated for tenant {tenant.schema_name}")
                return Response({
                    "detail": "Schedule updated successfully.",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error updating schedule {kwargs.get('id')} for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, *args, **kwargs):
        try:
            tenant = request.tenant
            if not tenant:
                logger.error("No tenant associated with the request")
                return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)

            logger.debug(f"User: {request.user}, Tenant: {tenant.schema_name}")
            connection.set_schema(tenant.schema_name)
            logger.debug(f"Schema after set: {connection.schema_name}")
            with connection.cursor() as cursor:
                cursor.execute("SHOW search_path;")
                search_path = cursor.fetchone()[0]
                logger.debug(f"Database search_path: {search_path}")

            instance = self.get_object()
            with tenant_context(tenant):
                instance.soft_delete()
                logger.info(f"Schedule soft-deleted: {instance.id} for tenant {tenant.schema_name}")
                return Response({"detail": "Schedule soft-deleted successfully."}, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            logger.exception(f"Error soft-deleting schedule {kwargs.get('id')} for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ScheduleBulkDeleteView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized, BranchRestrictedPermission]

    def post(self, request, *args, **kwargs):
        logger.debug(f"Received POST request to bulk soft-delete schedules: {request.data}")
        try:
            tenant = request.tenant
            if not tenant:
                logger.error("No tenant associated with the request")
                return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)

            ids = request.data.get('ids', [])
            if not ids:
                logger.warning("No schedule IDs provided for bulk soft deletion")
                return Response({"detail": "No schedule IDs provided."}, status=status.HTTP_400_BAD_REQUEST)

            connection.set_schema(tenant.schema_name)
            with tenant_context(tenant):
                schedules = Schedule.active_objects.filter(id__in=ids, tenant=tenant)
                if request.user.role == 'recruiter' and request.user.branch:
                    schedules = schedules.filter(branch=request.user.branch)
                if not schedules.exists():
                    logger.warning(f"No active schedules found for IDs {ids} in tenant {tenant.schema_name}")
                    return Response({"detail": "No schedules found."}, status=status.HTTP_404_NOT_FOUND)

                deleted_count = 0
                with transaction.atomic():
                    for schedule in schedules:
                        schedule.soft_delete()
                        deleted_count += 1

                logger.info(f"Successfully soft-deleted {deleted_count} schedules for tenant {tenant.schema_name}")
                return Response({
                    "detail": f"Successfully soft-deleted {deleted_count} schedule(s)."
                }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error during bulk soft deletion of schedules for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SoftDeletedSchedulesView(generics.ListAPIView):
    serializer_class = ScheduleSerializer
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized, BranchRestrictedPermission]

    def get_queryset(self):
        tenant = self.request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            raise generics.ValidationError("Tenant not found.")

        logger.debug(f"User: {self.request.user}, Tenant: {tenant.schema_name}")
        connection.set_schema(tenant.schema_name)
        with tenant_context(tenant):
            queryset = Schedule.objects.filter(tenant=tenant, is_deleted=True).select_related('job_application')
            if self.request.user.role == 'recruiter' and self.request.user.branch:
                queryset = queryset.filter(branch=self.request.user.branch)
            logger.debug(f"Query: {queryset.query}")
            return queryset

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            logger.info(f"Retrieved {queryset.count()} soft-deleted schedules for tenant {request.tenant.schema_name}")
            return Response({
                "detail": f"Retrieved {queryset.count()} soft-deleted schedule(s).",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error listing soft-deleted schedules for tenant {request.tenant.schema_name}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RecoverSoftDeletedSchedulesView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized, BranchRestrictedPermission]

    def post(self, request, *args, **kwargs):
        logger.debug(f"Received POST request to recover schedules: {request.data}")
        try:
            tenant = request.tenant
            if not tenant:
                logger.error("No tenant associated with the request")
                return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)

            ids = request.data.get('ids', [])
            if not ids:
                logger.warning("No schedule IDs provided for recovery")
                return Response({"detail": "No schedule IDs provided."}, status=status.HTTP_400_BAD_REQUEST)

            connection.set_schema(tenant.schema_name)
            with tenant_context(tenant):
                schedules = Schedule.objects.filter(id__in=ids, tenant=tenant, is_deleted=True)
                if request.user.role == 'recruiter' and request.user.branch:
                    schedules = schedules.filter(branch=request.user.branch)
                if not schedules.exists():
                    logger.warning(f"No soft-deleted schedules found for IDs {ids} in tenant {tenant.schema_name}")
                    return Response({"detail": "No soft-deleted schedules found."}, status=status.HTTP_404_NOT_FOUND)

                recovered_count = 0
                with transaction.atomic():
                    for schedule in schedules:
                        schedule.restore()
                        recovered_count += 1

                logger.info(f"Successfully recovered {recovered_count} schedules for tenant {tenant.schema_name}")
                return Response({
                    "detail": f"Successfully recovered {recovered_count} schedule(s)."
                }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error during recovery of schedules for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PermanentDeleteSchedulesView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized, BranchRestrictedPermission]

    def post(self, request, *args, **kwargs):
        logger.debug(f"Received POST request to permanently delete schedules: {request.data}")
        try:
            tenant = request.tenant
            if not tenant:
                logger.error("No tenant associated with the request")
                return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)

            ids = request.data.get('ids', [])
            if not ids:
                logger.warning("No schedule IDs provided for permanent deletion")
                return Response({"detail": "No schedule IDs provided."}, status=status.HTTP_400_BAD_REQUEST)

            connection.set_schema(tenant.schema_name)
            with tenant_context(tenant):
                schedules = Schedule.objects.filter(id__in=ids, tenant=tenant, is_deleted=True)
                if request.user.role == 'recruiter' and request.user.branch:
                    schedules = schedules.filter(branch=request.user.branch)
                if not schedules.exists():
                    logger.warning(f"No soft-deleted schedules found for IDs {ids} in tenant {tenant.schema_name}")
                    return Response({"detail": "No soft-deleted schedules found."}, status=status.HTTP_404_NOT_FOUND)

                deleted_count = schedules.delete()[0]
                logger.info(f"Successfully permanently deleted {deleted_count} schedules for tenant {tenant.schema_name}")
                return Response({
                    "detail": f"Successfully permanently deleted {deleted_count} schedule(s)."
                }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error during permanent deletion of schedules for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class ComplianceStatusUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsSubscribedAndAuthorized, BranchRestrictedPermission]

    def post(self, request, application_id, item_id):
        try:
            tenant = request.tenant
            connection.set_schema(tenant.schema_name)
            with tenant_context(tenant):
                try:
                    application = JobApplication.active_objects.get(id=application_id, tenant=tenant)
                except JobApplication.DoesNotExist:
                    logger.error(f"JobApplication {application_id} not found for tenant {tenant.schema_name}")
                    return Response({"detail": "Job application not found."}, status=status.HTTP_404_NOT_FOUND)

                if request.user.role == 'recruiter' and request.user.branch and application.branch != request.user.branch:
                    logger.error(f"User {request.user.id} not authorized to access application {application_id} in branch {application.branch}")
                    return Response({"detail": "Not authorized to access this application."}, status=status.HTTP_403_FORBIDDEN)

                status = request.data.get('status')
                notes = request.data.get('notes', '')
                if status not in ['pending', 'passed', 'failed']:
                    logger.error(f"Invalid compliance status: {status}")
                    return Response({"detail": "Invalid status. Must be 'pending', 'passed', or 'failed'."}, status=status.HTTP_400_BAD_REQUEST)

                updated_item = application.update_compliance_status(
                    item_id=item_id,
                    status=status,
                    checked_by=request.user,
                    notes=notes
                )
                logger.info(f"Compliance status updated for item {item_id} in application {application_id}")
                return Response({
                    "detail": "Compliance status updated successfully.",
                    "compliance_item": updated_item
                }, status=status.HTTP_200_OK)

        except ValueError as ve:
            logger.error(f"Compliance item {item_id} not found in application {application_id}: {str(ve)}")
            return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(f"Error updating compliance status for application {application_id}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class ApplicantComplianceUploadView(APIView):
    permission_classes = []  # No authentication required

    def put(self, request, job_application_id):
        try:
            # Extract unique_link from request data
            unique_link = request.POST.get('unique_link')
            if not unique_link:
                logger.error("Missing unique_link in PUT request")
                return Response({"detail": "Missing unique_link."}, status=status.HTTP_400_BAD_REQUEST)

            # Resolve tenant and job requisition from unique_link
            tenant, _ = resolve_tenant_from_unique_link(unique_link)
            if not tenant:
                logger.error(f"Invalid or expired unique_link: {unique_link}")
                return Response({"detail": "Invalid or expired job link."}, status=status.HTTP_400_BAD_REQUEST)

            # Set tenant context
            request.tenant = tenant
            with schema_context(tenant.schema_name):
                # Fetch the job application within the tenant context
                try:
                    application = JobApplication.active_objects.get(id=job_application_id)
                except JobApplication.DoesNotExist:
                    logger.error(f"JobApplication {job_application_id} not found for tenant {tenant.schema_name}")
                    return Response({"detail": "Job application not found."}, status=status.HTTP_404_NOT_FOUND)

                # Prepare data for processing
                files = request.FILES.getlist('documents')
                document_ids = request.POST.getlist('document_ids')  # Get compliance item IDs
                document_names = request.POST.getlist('document_names')  # Get compliance item names

                if not files or len(files) != len(document_ids) or len(files) != len(document_names):
                    return Response({"detail": "Mismatch in documents, document_ids, or document_names."}, status=status.HTTP_400_BAD_REQUEST)

                # Create a mapping of compliance item IDs to names from JobRequisition
                compliance_checklist = {item['id']: item['name'] for item in application.job_requisition.compliance_checklist}

                # Validate document_ids against compliance_checklist
                for doc_id in document_ids:
                    if doc_id not in compliance_checklist:
                        return Response({"detail": f"Invalid compliance item ID: {doc_id}"}, status=status.HTTP_400_BAD_REQUEST)

                documents_data = []
                for i, (file, doc_id, doc_name) in enumerate(zip(files, document_ids, document_names)):
                    # Validate that the document_name matches the compliance checklist name
                    if doc_name != compliance_checklist.get(doc_id):
                        logger.warning(f"Document name {doc_name} does not match compliance checklist name {compliance_checklist.get(doc_id)} for ID {doc_id}")
                        # Optionally, you can enforce strict matching or use the compliance_checklist name
                        doc_name = compliance_checklist[doc_id]

                    folder_path = os.path.join('compliance_documents', timezone.now().strftime('%Y/%m/%d'))
                    full_folder_path = os.path.join(settings.MEDIA_ROOT, folder_path)
                    os.makedirs(full_folder_path, exist_ok=True)
                    file_extension = os.path.splitext(file.name)[1]
                    filename = f"{uuid.uuid4()}{file_extension}"
                    upload_path = os.path.join(folder_path, filename).replace('\\', '/')
                    full_upload_path = os.path.join(settings.MEDIA_ROOT, upload_path)

                    try:
                        with open(full_upload_path, 'wb+') as destination:
                            for chunk in file.chunks():
                                destination.write(chunk)
                        logger.debug(f"File saved successfully: {full_upload_path}")
                    except Exception as e:
                        logger.error(f"Failed to save file {full_upload_path}: {str(e)}")
                        return Response({"error": f"Failed to save file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                    file_url = f"/media/{upload_path.lstrip('/')}"
                    documents_data.append({
                        'document_type': doc_id,  # Use the compliance item ID
                        'file': file,
                        'file_url': file_url,
                        'uploaded_at': timezone.now().isoformat()
                    })

                # Update compliance_status
                updated_compliance_status = application.compliance_status.copy() if application.compliance_status else []
                for doc_id, doc_name, doc_data in zip(document_ids, document_names, documents_data):
                    for item in updated_compliance_status:
                        if str(item.get('id')) == str(doc_id):
                            item['name'] = compliance_checklist[doc_id]  # Ensure name is set correctly
                            item['document'] = {
                                'file_url': doc_data['file_url'],
                                'uploaded_at': doc_data['uploaded_at']
                            }
                            item['status'] = 'uploaded'
                            item['notes'] = ''
                            break
                    else:
                        # If the compliance item doesn't exist, create a new one
                        updated_compliance_status.append({
                            'id': doc_id,
                            'name': compliance_checklist[doc_id],
                            'description': '',
                            'required': True,
                            'status': 'uploaded',
                            'checked_by': None,
                            'checked_at': None,
                            'notes': '',
                            'document': {
                                'file_url': doc_data['file_url'],
                                'uploaded_at': doc_data['uploaded_at']
                            }
                        })

                # Update the application
                with transaction.atomic():
                    application.compliance_status = updated_compliance_status
                    application.save()

                # Serialize the updated application
                serializer = JobApplicationSerializer(application, context={'request': request})
                return Response({
                    "detail": "Compliance documents uploaded successfully.",
                    "compliance_status": serializer.data['compliance_status']
                }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error uploading compliance documents for application {job_application_id}: {str(e)}")
            #print(f"Error uploading compliance documents for application {job_application_id}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)