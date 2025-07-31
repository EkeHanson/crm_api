import logging
import uuid
from django.conf import settings
from django.db import connection, models, transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from django_tenants.utils import tenant_context
from drf_spectacular.utils import extend_schema, OpenApiParameter, extend_schema_field
from rest_framework import generics, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Tenant, Branch
from job_application.permissions import BranchRestrictedPermission
from lumina_care.supabase_client import supabase
from users.models import CustomUser
from users.permissions import BranchRestrictedPermission as UsersBranchRestrictedPermission

from .models import (
    JobRequisition,
    VideoSession,
    Participant,
)
from .serializers import JobRequisitionSerializer, ComplianceItemSerializer,VideoSessionSerializer, ParticipantSerializer

logger = logging.getLogger('talent_engine')


class JobRequisitionBulkDeleteView(generics.GenericAPIView):
    serializer_class = JobRequisitionSerializer  # Added serializer_class
    permission_classes = [IsAuthenticated, BranchRestrictedPermission]

    def post(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            logger.warning("No IDs provided for bulk soft delete")
            return Response({"detail": "No IDs provided."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            tenant = request.tenant
            with tenant_context(tenant):
                if not all(isinstance(id, str) and id.startswith('PRO-') for id in ids):
                    logger.warning(f"Invalid ID format in: {ids}")
                    return Response({"detail": "All IDs must be in PRO-XXXX format."}, status=status.HTTP_400_BAD_REQUEST)
                queryset = JobRequisition.active_objects.filter(tenant=tenant, id__in=ids)
                if request.user.role == 'recruiter' and request.user.branch:
                    queryset = queryset.filter(branch=request.user.branch)
                count = queryset.count()
                if count == 0:
                    logger.warning("No active requisitions found for provided IDs")
                    return Response({"detail": "No requisitions found."}, status=status.HTTP_404_NOT_FOUND)
                with transaction.atomic():
                    for requisition in queryset:
                        requisition.soft_delete()
                return Response({"detail": f"Soft-deleted {count} requisition(s)."}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Bulk soft delete failed: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class JobRequisitionListCreateView(generics.ListCreateAPIView):
    serializer_class = JobRequisitionSerializer
    permission_classes = [IsAuthenticated, BranchRestrictedPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'role', 'branch']
    search_fields = ['title', 'status', 'requested_by__email', 'role', 'interview_location']

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)  # Use getattr for safety
        if not tenant:
            logger.error("No tenant associated with the request")
            raise serializers.ValidationError("Tenant not found.")
        connection.set_schema(tenant.schema_name)
        with connection.cursor() as cursor:
            cursor.execute("SHOW search_path;")
            search_path = cursor.fetchone()[0]
            logger.debug(f"Database search_path: {search_path}")
        queryset = JobRequisition.active_objects.filter(tenant=tenant)
        if self.request.user.branch:
            queryset = queryset.filter(branch=self.request.user.branch)
            print(self.request.user.branch)
        return queryset
    
    def perform_create(self, serializer):
        tenant = self.request.tenant
        user = self.request.user

        # Validate user and tenant
        if not isinstance(user, CustomUser) or user.tenant != tenant:
            logger.error(f"Invalid user {user.email} for tenant {tenant.schema_name}")
            raise serializers.ValidationError("Authenticated user is not valid for this tenant.")

        # Check if tenant has any branches
        has_branches = Branch.objects.filter(tenant=tenant).exists()

        # Enforce branch assignment only if tenant has branches
        if has_branches and not user.branch:
            logger.error(f"User {user.email} has no assigned branch in tenant {tenant.schema_name}")
            raise serializers.ValidationError("User must be assigned to a branch to create a requisition.")

        connection.set_schema(tenant.schema_name)
        serializer.save(
            tenant=tenant,
            requested_by=user,
            branch=user.branch if has_branches else None  # Set branch only if branches exist
        )
        logger.info(f"Job requisition created: {serializer.validated_data['title']} for tenant {tenant.schema_name} by user {user.email}")

    # def perform_create(self, serializer):
    #     tenant = self.request.tenant
    #     user = self.request.user
    #     if not isinstance(user, CustomUser) or user.tenant != tenant:
    #         logger.error(f"Invalid user {user.email} for tenant {tenant.schema_name}")
    #         raise serializers.ValidationError("Authenticated user is not valid for this tenant.")
    #     if not user.branch:
    #         logger.error(f"User {user.email} has no assigned branch in tenant {tenant.schema_name}")
    #         raise serializers.ValidationError("User must be assigned to a branch to create a requisition.")
    #     connection.set_schema(tenant.schema_name)
    #     serializer.save(
    #         tenant=tenant,
    #         requested_by=user,
    #         branch=user.branch
    #     )
    #     logger.info(f"Job requisition created: {serializer.validated_data['title']} for tenant {tenant.schema_name} by user {user.email}")


class JobRequisitionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = JobRequisitionSerializer
    permission_classes = [IsAuthenticated, BranchRestrictedPermission]
    lookup_field = 'id'

    def get_queryset(self):
        tenant = self.request.tenant
        connection.set_schema(tenant.schema_name)
        with connection.cursor() as cursor:
            cursor.execute("SHOW search_path;")
            search_path = cursor.fetchone()[0]
            logger.debug(f"Database search_path: {search_path}")
        queryset = JobRequisition.active_objects.filter(tenant=tenant)
        if self.request.user.role == 'recruiter' and self.request.user.branch:
            queryset = queryset.filter(branch=self.request.user.branch)
        return queryset

    def perform_update(self, serializer):
        tenant = self.request.tenant
        with tenant_context(tenant):
            serializer.save()
        logger.info(f"Job requisition updated: {serializer.instance.title} for tenant {tenant.schema_name}")

    def perform_destroy(self, instance):
        tenant = self.request.tenant
        with tenant_context(tenant):
            instance.soft_delete()
        logger.info(f"Job requisition soft-deleted: {instance.title} for tenant {tenant.schema_name}")

class JobRequisitionByLinkView(generics.RetrieveAPIView):
    serializer_class = JobRequisitionSerializer
    lookup_field = 'unique_link'
    permission_classes = []

    def get_queryset(self):
        unique_link = self.kwargs.get('unique_link', '')
        if not unique_link or '-' not in unique_link:
            logger.warning(f"Invalid unique_link format: {unique_link}")
            return JobRequisition.objects.none()
        try:
            tenant_schema = unique_link.split('-')[0]
            tenant = Tenant.objects.get(schema_name=tenant_schema)
            connection.set_schema(tenant.schema_name)
            with connection.cursor() as cursor:
                cursor.execute("SHOW search_path;")
                search_path = cursor.fetchone()[0]
                logger.debug(f"Database search_path: {search_path}")
            queryset = JobRequisition.active_objects.filter(tenant=tenant, publish_status=True)
            return queryset
        except Tenant.DoesNotExist:
            logger.warning(f"Tenant {tenant_schema} not found")
            return JobRequisition.objects.none()
        except Exception as e:
            logger.error(f"Error setting tenant context: {str(e)}")
            return JobRequisition.objects.none()

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            tenant_schema = instance.tenant.schema_name
            logger.info(f"Job requisition accessed via link: {instance.title} for tenant {tenant_schema}")
            return Response(serializer.data)
        except JobRequisition.DoesNotExist:
            logger.warning(f"Job with unique_link {kwargs.get('unique_link')} not found or not published")
            return Response({"detail": "Job not found or not published"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error retrieving job requisition: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SoftDeletedJobRequisitionsView(generics.ListAPIView):
    serializer_class = JobRequisitionSerializer
    permission_classes = [IsAuthenticated, BranchRestrictedPermission]

    def get_queryset(self):
        tenant = self.request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            raise generics.ValidationError("Tenant not found.")
        connection.set_schema(tenant.schema_name)
        with tenant_context(tenant):
            queryset = JobRequisition.objects.filter(tenant=tenant, is_deleted=True)
            if self.request.user.role == 'recruiter' and self.request.user.branch:
                queryset = queryset.filter(branch=self.request.user.branch)
            return queryset

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            logger.info(f"Retrieved {queryset.count()} soft-deleted job requisitions for tenant {request.tenant.schema_name}")
            return Response({
                "detail": f"Retrieved {queryset.count()} soft-deleted requisition(s).",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error listing soft-deleted job requisitions for tenant {request.tenant.schema_name}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RecoverSoftDeletedJobRequisitionsView(generics.GenericAPIView):
    serializer_class = JobRequisitionSerializer  # Added serializer_class
    permission_classes = [IsAuthenticated, BranchRestrictedPermission]

    def post(self, request, *args, **kwargs):
        try:
            tenant = request.tenant
            if not tenant:
                logger.error("No tenant associated with the request")
                return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)
            ids = request.data.get('ids', [])
            if not ids:
                logger.warning("No requisition IDs provided for recovery")
                return Response({"detail": "No requisition IDs provided."}, status=status.HTTP_400_BAD_REQUEST)
            connection.set_schema(tenant.schema_name)
            with tenant_context(tenant):
                queryset = JobRequisition.objects.filter(id__in=ids, tenant=tenant, is_deleted=True)
                if request.user.role == 'recruiter' and request.user.branch:
                    queryset = queryset.filter(branch=self.request.user.branch)
                if not queryset.exists():
                    logger.warning(f"No soft-deleted requisitions found for IDs {ids} in tenant {tenant.schema_name}")
                    return Response({"detail": "No soft-deleted requisitions found."}, status=status.HTTP_404_NOT_FOUND)
                recovered_count = 0
                with transaction.atomic():
                    for requisition in queryset:
                        requisition.restore()
                        recovered_count += 1
                logger.info(f"Successfully recovered {recovered_count} requisitions for tenant {tenant.schema_name}")
                return Response({
                    "detail": f"Successfully recovered {recovered_count} requisition(s)."
                }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error during recovery of requisitions for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PermanentDeleteJobRequisitionsView(generics.GenericAPIView):
    serializer_class = JobRequisitionSerializer  # Added serializer_class
    permission_classes = [IsAuthenticated, BranchRestrictedPermission]

    def post(self, request, *args, **kwargs):
        try:
            tenant = request.tenant
            if not tenant:
                logger.error("No tenant associated with the request")
                return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)
            ids = request.data.get('ids', [])
            if not ids:
                logger.warning("No requisition IDs provided for permanent deletion")
                return Response({"detail": "No requisition IDs provided."}, status=status.HTTP_400_BAD_REQUEST)
            connection.set_schema(tenant.schema_name)
            with tenant_context(tenant):
                queryset = JobRequisition.objects.filter(id__in=ids, tenant=tenant, is_deleted=True)
                if request.user.role == 'recruiter' and request.user.branch:
                    queryset = queryset.filter(branch=self.request.user.branch)
                if not queryset.exists():
                    logger.warning(f"No soft-deleted requisitions found for IDs {ids} in tenant {tenant.schema_name}")
                    return Response({"detail": "No soft-deleted requisitions found."}, status=status.HTTP_404_NOT_FOUND)
                deleted_count = queryset.delete()[0]
                logger.info(f"Successfully permanently deleted {deleted_count} requisitions for tenant {tenant.schema_name}")
                return Response({
                    "detail": f"Successfully permanently deleted {deleted_count} requisition(s)."
                }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error during permanent deletion of requisitions for tenant {tenant.schema_name if tenant else 'unknown'}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ComplianceItemView(APIView):
    serializer_class = ComplianceItemSerializer  # Added serializer_class
    permission_classes = [IsAuthenticated, BranchRestrictedPermission]

    def post(self, request, job_requisition_id):
        try:
            tenant = request.tenant
            with tenant_context(tenant):
                try:
                    job_requisition = JobRequisition.active_objects.get(id=job_requisition_id, tenant=tenant)
                except JobRequisition.DoesNotExist:
                    logger.error(f"JobRequisition {job_requisition_id} not found for tenant {tenant.schema_name}")
                    return Response({"detail": "Job requisition not found."}, status=status.HTTP_404_NOT_FOUND)
                if request.user.role == 'recruiter' and request.user.branch and job_requisition.branch != request.user.branch:
                    logger.error(f"Unauthorized access to JobRequisition {job_requisition_id} by user {request.user.email}")
                    return Response({"detail": "Not authorized to access this requisition."}, status=status.HTTP_403_FORBIDDEN)
                serializer = ComplianceItemSerializer(data=request.data)
                if serializer.is_valid():
                    item_data = serializer.validated_data
                    item_data.setdefault('status', 'pending')
                    item_data.setdefault('checked_by', None)
                    item_data.setdefault('checked_at', None)
                    new_item = job_requisition.add_compliance_item(
                        name=item_data['name'],
                        description=item_data.get('description', ''),
                        required=item_data.get('required', True),
                        status=item_data['status'],
                        checked_by=item_data['checked_by'],
                        checked_at=item_data['checked_at']
                    )
                    logger.info(f"Added compliance item to JobRequisition {job_requisition_id} for tenant {tenant.schema_name}")
                    return Response(ComplianceItemSerializer(new_item).data, status=status.HTTP_201_CREATED)
                logger.error(f"Invalid compliance item data for tenant {tenant.schema_name}: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(f"Error adding compliance item to JobRequisition {job_requisition_id}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, job_requisition_id, item_id):
        try:
            tenant = request.tenant
            with tenant_context(tenant):
                try:
                    job_requisition = JobRequisition.active_objects.get(id=job_requisition_id, tenant=tenant)
                except JobRequisition.DoesNotExist:
                    logger.error(f"JobRequisition {job_requisition_id} not found for tenant {tenant.schema_name}")
                    return Response({"detail": "Job requisition not found."}, status=status.HTTP_404_NOT_FOUND)
                if request.user.role == 'recruiter' and request.user.branch and job_requisition.branch != request.user.branch:
                    logger.error(f"Unauthorized access to JobRequisition {job_requisition_id} by user {request.user.email}")
                    return Response({"detail": "Not authorized to access this requisition."}, status=status.HTTP_403_FORBIDDEN)
                serializer = ComplianceItemSerializer(data=request.data)
                if serializer.is_valid():
                    item_data = serializer.validated_data
                    updated_item = job_requisition.update_compliance_item(
                        item_id=str(item_id),
                        name=item_data['name'],
                        description=item_data.get('description', ''),
                        required=item_data.get('required', True),
                        status=item_data.get('status', 'pending'),
                        checked_by=item_data.get('checked_by'),
                        checked_at=item_data.get('checked_at')
                    )
                    logger.info(f"Updated compliance item {item_id} for JobRequisition {job_requisition_id} for tenant {tenant.schema_name}")
                    return Response(ComplianceItemSerializer(updated_item).data, status=status.HTTP_200_OK)
                logger.error(f"Invalid compliance item data for tenant {tenant.schema_name}: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            logger.error(f"Compliance item {item_id} not found in JobRequisition {job_requisition_id} for tenant {tenant.schema_name}")
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(f"Error updating compliance item {item_id} for JobRequisition {job_requisition_id}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, job_requisition_id, item_id):
        try:
            tenant = request.tenant
            with tenant_context(tenant):
                try:
                    job_requisition = JobRequisition.active_objects.get(id=job_requisition_id, tenant=tenant)
                except JobRequisition.DoesNotExist:
                    logger.error(f"JobRequisition {job_requisition_id} not found for tenant {tenant.schema_name}")
                    return Response({"detail": "Job requisition not found."}, status=status.HTTP_404_NOT_FOUND)
                if request.user.role == 'recruiter' and request.user.branch and job_requisition.branch != request.user.branch:
                    logger.error(f"Unauthorized access to JobRequisition {job_requisition_id} by user {request.user.email}")
                    return Response({"detail": "Not authorized to access this requisition."}, status=status.HTTP_403_FORBIDDEN)
                job_requisition.remove_compliance_item(str(item_id))
                logger.info(f"Deleted compliance item {item_id} from JobRequisition {job_requisition_id} for tenant {tenant.schema_name}")
                return Response(status=status.HTTP_204_NO_CONTENT)
        except ValueError as e:
            logger.error(f"Compliance item {item_id} not found in JobRequisition {job_requisition_id} for tenant {tenant.schema_name}")
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(f"Error deleting compliance item {item_id} for JobRequisition {job_requisition_id}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        























class VideoSessionViewSet(viewsets.ModelViewSet):
    queryset = VideoSession.objects.all()
    serializer_class = VideoSessionSerializer
    permission_classes = [IsAuthenticated, BranchRestrictedPermission]

    def get_queryset(self):
        tenant = self.request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            raise serializers.ValidationError("Tenant not found.")
        connection.set_schema(tenant.schema_name)
        queryset = VideoSession.objects.filter(tenant=tenant)
        if self.request.user.role == 'recruiter' and self.request.user.branch:
            queryset = queryset.filter(job_application__branch=self.request.user.branch)
        return queryset

    def create(self, request, *args, **kwargs):
        tenant = request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)
        connection.set_schema(tenant.schema_name)
        data = request.data.copy()
        data['tenant'] = tenant.id  # Set tenant from request, not from POST data
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        logger.info(f"Video session created for job application {serializer.validated_data.get('job_application')} in tenant {tenant.schema_name}")
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        tenant = self.request.tenant
        with tenant_context(tenant):
            serializer.save(tenant=tenant)

    def perform_update(self, serializer):
        tenant = self.request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            raise serializers.ValidationError("Tenant not found.")
        connection.set_schema(tenant.schema_name)
        with tenant_context(tenant):
            serializer.save()
        logger.info(f"Video session updated: {serializer.instance.id} for tenant {tenant.schema_name}")

    def perform_destroy(self, instance):
        tenant = self.request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            raise serializers.ValidationError("Tenant not found.")
        connection.set_schema(tenant.schema_name)
        with tenant_context(tenant):
            instance.end_session()
        logger.info(f"Video session soft-deleted: {instance.id} for tenant {tenant.schema_name}")

    @extend_schema(
        description="Join a video session and create a participant entry (by user or candidate email)",
        parameters=[
            OpenApiParameter(name='session_id', type=str, required=True),
            OpenApiParameter(name='email', type=str, required=False)
        ]
    )
    @action(detail=False, methods=['post'])
    def join(self, request):
        tenant = request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)
        session_id = request.data.get('session_id')
        email = request.data.get('email')
        connection.set_schema(tenant.schema_name)
        with tenant_context(tenant):
            try:
                session = VideoSession.objects.get(id=session_id, is_active=True, tenant=tenant)
                # Authenticated user flow
                if request.user.is_authenticated:
                    if request.user.role == 'recruiter' and request.user.branch and session.job_application.branch != request.user.branch:
                        logger.error(f"Unauthorized access to session {session_id} by user {request.user.email}")
                        return Response({"detail": "Not authorized to access this session."}, status=status.HTTP_403_FORBIDDEN)
                    participant, created = Participant.objects.get_or_create(
                        session=session,
                        user=request.user,
                        defaults={'is_muted': False, 'is_camera_on': True}
                    )
                    logger.info(f"User {request.user.email} joined session {session_id} in tenant {tenant.schema_name}")
                    return Response(ParticipantSerializer(participant).data, status=status.HTTP_200_OK)
                # Candidate email flow
                elif email:
                    job_app = session.job_application
                    if job_app.email.lower() == email.lower():
                        participant, created = Participant.objects.get_or_create(
                            session=session,
                            candidate_email=email,
                            defaults={'is_muted': False, 'is_camera_on': True}
                        )
                        logger.info(f"Candidate {email} joined session {session_id} in tenant {tenant.schema_name}")
                        return Response(ParticipantSerializer(participant).data, status=status.HTTP_200_OK)
                    else:
                        logger.error(f"Email {email} not authorized for session {session_id}")
                        return Response({"detail": "Email not authorized for this session."}, status=status.HTTP_403_FORBIDDEN)
                else:
                    logger.error("No authentication or candidate email provided")
                    return Response({"detail": "Authentication or candidate email required."}, status=status.HTTP_400_BAD_REQUEST)
            except VideoSession.DoesNotExist:
                logger.error(f"Session {session_id} not found or inactive for tenant {tenant.schema_name}")
                return Response({'error': 'Session not found or inactive'}, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(
        description="Leave a video session",
        parameters=[
            OpenApiParameter(name='session_id', type=str, required=True)
        ]
    )
    @action(detail=False, methods=['post'])
    def leave(self, request):
        tenant = request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)
        session_id = request.data.get('session_id')
        connection.set_schema(tenant.schema_name)
        with tenant_context(tenant):
            try:
                participant = Participant.objects.get(
                    session__id=session_id,
                    session__tenant=tenant,
                    user=request.user,
                    left_at__isnull=True
                )
                if request.user.role == 'recruiter' and request.user.branch and participant.session.job_application.branch != request.user.branch:
                    logger.error(f"Unauthorized access to session {session_id} by user {request.user.email}")
                    return Response({"detail": "Not authorized to access this session."}, status=status.HTTP_403_FORBIDDEN)
                participant.left_at = timezone.now()
                participant.save()
                # Check if all participants have left to end the session
                if not Participant.objects.filter(session__id=session_id, left_at__isnull=True).exists():
                    session = VideoSession.objects.get(id=session_id)
                    session.end_session()
                logger.info(f"User {request.user.email} left session {session_id} in tenant {tenant.schema_name}")
                return Response({'status': 'Left session'}, status=status.HTTP_200_OK)
            except Participant.DoesNotExist:
                logger.error(f"Participant not found in session {session_id} for tenant {tenant.schema_name}")
                return Response({'error': 'Participant not found'}, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(
        description="Toggle mute status for a participant",
        parameters=[
            OpenApiParameter(name='session_id', type=str, required=True),
            OpenApiParameter(name='mute', type=bool, required=True)
        ]
    )
    @action(detail=False, methods=['post'])
    def toggle_mute(self, request):
        tenant = request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)
        session_id = request.data.get('session_id')
        mute = request.data.get('mute', False)
        connection.set_schema(tenant.schema_name)
        with tenant_context(tenant):
            try:
                participant = Participant.objects.get(
                    session__id=session_id,
                    session__tenant=tenant,
                    user=request.user,
                    left_at__isnull=True
                )
                if request.user.role == 'recruiter' and request.user.branch and participant.session.job_application.branch != request.user.branch:
                    logger.error(f"Unauthorized access to session {session_id} by user {request.user.email}")
                    return Response({"detail": "Not authorized to access this session."}, status=status.HTTP_403_FORBIDDEN)
                participant.is_muted = mute
                participant.save()
                logger.info(f"User {request.user.email} {'muted' if mute else 'unmuted'} in session {session_id} for tenant {tenant.schema_name}")
                return Response(ParticipantSerializer(participant).data, status=status.HTTP_200_OK)
            except Participant.DoesNotExist:
                logger.error(f"Participant not found in session {session_id} for tenant {tenant.schema_name}")
                return Response({'error': 'Participant not found'}, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(
        description="Toggle camera status for a participant",
        parameters=[
            OpenApiParameter(name='session_id', type=str, required=True),
            OpenApiParameter(name='camera_on', type=bool, required=True)
        ]
    )


    @action(detail=False, methods=['post'])
    def toggle_camera(self, request):
        tenant = request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)
        session_id = request.data.get('session_id')
        camera_on = request.data.get('camera_on', True)
        email = request.data.get('email')
        connection.set_schema(tenant.schema_name)
        with tenant_context(tenant):
            try:
                if request.user.is_authenticated:
                    participant = Participant.objects.get(
                        session__id=session_id,
                        session__tenant=tenant,
                        user=request.user,
                        left_at__isnull=True
                    )
                elif email:
                    participant = Participant.objects.get(
                        session__id=session_id,
                        session__tenant=tenant,
                        candidate_email=email,
                        left_at__isnull=True
                    )
                else:
                    return Response({"detail": "Authentication or candidate email required."}, status=status.HTTP_400_BAD_REQUEST)
                participant.is_camera_on = camera_on
                participant.save()
                return Response(ParticipantSerializer(participant).data, status=status.HTTP_200_OK)
            except Participant.DoesNotExist:
                return Response({'error': 'Participant not found'}, status=status.HTTP_404_NOT_FOUND)



    @extend_schema(
        description="Start recording a video session",
        parameters=[
            OpenApiParameter(name='session_id', type=str, required=True)
        ]
    )
    @action(detail=False, methods=['post'])
    def start_recording(self, request):
        tenant = request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)
        session_id = request.data.get('session_id')
        connection.set_schema(tenant.schema_name)
        with tenant_context(tenant):
            try:
                session = VideoSession.objects.get(id=session_id, is_active=True, tenant=tenant)
                if request.user.role == 'recruiter' and request.user.branch and session.job_application.branch != request.user.branch:
                    logger.error(f"Unauthorized access to session {session_id} by user {request.user.email}")
                    return Response({"detail": "Not authorized to access this session."}, status=status.HTTP_403_FORBIDDEN)
                # Placeholder for actual recording logic
                # In a real implementation, you would interface with a WebRTC recording service
                recording_path = f"recordings/{tenant.schema_name}/{session_id}/{uuid.uuid4()}.webm"
                # Note: Actual recording data should come from the WebRTC stream
                supabase.storage.from_(settings.SUPABASE_BUCKET).upload(
                    recording_path,
                    b"placeholder_recording_data",  # Replace with actual stream data
                    {"content-type": "video/webm"}
                )
                session.recording_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{settings.SUPABASE_BUCKET}/{recording_path}"
                session.save()
                logger.info(f"Recording started for session {session_id} in tenant {tenant.schema_name}")
                return Response({'recording_url': session.recording_url}, status=status.HTTP_200_OK)
            except VideoSession.DoesNotExist:
                logger.error(f"Session {session_id} not found or inactive for tenant {tenant.schema_name}")
                return Response({'error': 'Session not found or inactive'}, status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                logger.error(f"Error starting recording for session {session_id}: {str(e)}")
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(
        description="Update interview scores, notes, or tags",
        parameters=[
            OpenApiParameter(name='session_id', type=str, required=True)
        ]
    )
    @action(detail=False, methods=['post'])
    def update_interview_data(self, request):
        tenant = request.tenant
        if not tenant:
            logger.error("No tenant associated with the request")
            return Response({"detail": "Tenant not found."}, status=status.HTTP_400_BAD_REQUEST)
        session_id = request.data.get('session_id')
        scores = request.data.get('scores')
        notes = request.data.get('notes')
        tags = request.data.get('tags')
        connection.set_schema(tenant.schema_name)
        with tenant_context(tenant):
            try:
                session = VideoSession.objects.get(id=session_id, is_active=True, tenant=tenant)
                if request.user.role == 'recruiter' and request.user.branch and session.job_application.branch != request.user.branch:
                    logger.error(f"Unauthorized access to session {session_id} by user {request.user.email}")
                    return Response({"detail": "Not authorized to access this session."}, status=status.HTTP_403_FORBIDDEN)
                if scores is not None:
                    serializer = VideoSessionSerializer(data={'scores': scores}, partial=True)
                    serializer.is_valid(raise_exception=True)
                    session.scores = serializer.validated_data['scores']
                if notes is not None:
                    session.notes = notes
                if tags is not None:
                    serializer = VideoSessionSerializer(data={'tags': tags}, partial=True)
                    serializer.is_valid(raise_exception=True)
                    session.tags = serializer.validated_data['tags']
                session.save()
                logger.info(f"Updated interview data for session {session_id} in tenant {tenant.schema_name}")
                return Response(VideoSessionSerializer(session).data, status=status.HTTP_200_OK)
            except VideoSession.DoesNotExist:
                logger.error(f"Session {session_id} not found or inactive for tenant {tenant.schema_name}")
                return Response({'error': 'Session not found or inactive'}, status=status.HTTP_404_NOT_FOUND)