import logging
import jwt
from django.conf import settings
from django.db import transaction
from django_tenants.utils import tenant_context
from rest_framework import viewsets, status, serializers
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from allauth.socialaccount.models import SocialAccount
from .models import CustomUser
from .serializers import CustomUserSerializer, UserCreateSerializer, AdminUserCreateSerializer, UserBranchUpdateSerializer
from core.models import Tenant, Branch

logger = logging.getLogger('users')

# Existing views (unchanged)
class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self.request.user.tenant
        user = self.request.user
        with tenant_context(tenant):
            if user.role == 'team_manager':
                return CustomUser.objects.filter(tenant=tenant)
            elif user.role == 'recruiter' and user.branch:
                return CustomUser.objects.filter(tenant=tenant, branch=user.branch)
            return CustomUser.objects.filter(tenant=tenant, id=user.id)

    def perform_create(self, serializer):
        tenant = self.request.user.tenant
        if self.request.user.role != 'admin' and not self.request.user.is_superuser:
            raise serializers.ValidationError("Only admins or superusers can create users.")
        with tenant_context(tenant):
            serializer.save()

class UserCreateView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        logger.debug(f"User creation request for tenant {request.user.tenant.schema_name}: {dict(request.data)}")
        serializer = UserCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            try:
                user = serializer.save()
                refresh = RefreshToken.for_user(user)
                logger.info(f"User created: {user.email} (ID: {user.id}) for tenant {user.tenant.schema_name}")
                return Response({
                    'status': 'success',
                    'message': f"User {user.email} created successfully.",
                    'data': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'role': user.role,
                        'job_role': user.job_role,
                        'dashboard': user.dashboard,
                        'access_level': user.access_level,
                        'status': user.status,
                        'two_factor': user.two_factor,
                        'tenant_id': user.tenant.id,
                        'tenant_schema': user.tenant.schema_name,
                        'branch': user.branch.name if user.branch else None,
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Error creating user for tenant {request.user.tenant.schema_name}: {str(e)}", exc_info=True)
                return Response({
                    'status': 'error',
                    'message': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        logger.error(f"Validation error for tenant {request.user.tenant.schema_name}: {serializer.errors}")
        return Response({
            'status': 'error',
            'message': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

class AdminUserCreateView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = AdminUserCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = serializer.save()
                refresh = RefreshToken.for_user(user)
                logger.info(f"Admin user created: {user.email} for tenant {user.tenant.schema_name}")
                return Response({
                    'status': 'success',
                    'message': f"Admin user {user.email} created successfully.",
                    'data': {
                        'username': user.username,
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'job_role': user.job_role,
                        'tenant_id': user.tenant.id,
                        'tenant_schema': user.tenant.schema_name,
                        'branch': user.branch.name if user.branch else None,
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Error creating admin user: {str(e)}")
                return Response({
                    'status': 'error',
                    'message': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        logger.error(f"Validation error: {serializer.errors}")
        return Response({
            'status': 'error',
            'message': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

class SocialLoginCallbackView(APIView):
    def get(self, request):
        user = request.user
        if not user.is_authenticated:
            logger.error("User not authenticated after social login")
            return Response({"error": "Authentication failed"}, status=400)
        try:
            social_account = SocialAccount.objects.get(user=user)
            tenant = user.tenant
            with tenant_context(tenant):
                refresh = RefreshToken.for_user(user)
                return Response({
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'tenant_id': tenant.id,
                    'tenant_schema': tenant.schema_name,
                    'branch': user.branch.name if user.branch else None,
                })
        except SocialAccount.DoesNotExist:
            logger.error(f"No social account found for user {user.email}")
            return Response({"error": "Social account not found"}, status=400)
        except Exception as e:
            logger.error(f"Error in social login callback: {str(e)}")
            return Response({"error": str(e)}, status=500)

class UserBranchUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def get_tenant_from_token(self, request):
        try:
            if hasattr(request, 'tenant') and request.tenant:
                logger.debug(f"Tenant from request: {request.tenant.schema_name}")
                return request.tenant
            if hasattr(request.user, 'tenant') and request.user.tenant:
                logger.debug(f"Tenant from user: {request.user.tenant.schema_name}")
                return request.user.tenant
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

    def patch(self, request, user_id):
        tenant = self.get_tenant_from_token(request)
        with tenant_context(tenant):
            try:
                user = CustomUser.objects.get(id=user_id, tenant=tenant)
            except CustomUser.DoesNotExist:
                logger.error(f"User with ID {user_id} not found for tenant {tenant.schema_name}")
                return Response(
                    {"status": "error", "message": f"User with ID {user_id} not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Check permissions: Only admins, superusers, or team managers can update branch
            if not (request.user.is_superuser or request.user.role == 'admin' or request.user.role == 'team_manager'):
                logger.warning(f"Unauthorized branch update attempt by user {request.user.email} for user {user.email}")
                return Response(
                    {"status": "error", "message": "Only admins or team managers can update user branch"},
                    status=status.HTTP_403_FORBIDDEN
                )

            serializer = UserBranchUpdateSerializer(user, data=request.data, context={'request': request}, partial=True)
            if serializer.is_valid():
                try:
                    with transaction.atomic():
                        serializer.save()
                        logger.info(f"User {user.email} assigned to branch {user.branch.name if user.branch else 'None'} for tenant {tenant.schema_name}")
                        return Response(
                            {
                                "status": "success",
                                "message": f"User {user.email} branch updated successfully",
                                "data": CustomUserSerializer(user, context={'request': request}).data
                            },
                            status=status.HTTP_200_OK
                        )
                except Exception as e:
                    logger.error(f"Error updating branch for user {user.email} in tenant {tenant.schema_name}: {str(e)}")
                    return Response(
                        {"status": "error", "message": str(e)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            logger.error(f"Validation error for user {user.email} in tenant {tenant.schema_name}: {serializer.errors}")
            return Response(
                {"status": "error", "message": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

# New view for listing all users in a tenant
class TenantUsersListView(APIView):
    permission_classes = [IsAuthenticated]

    def get_tenant_from_token(self, request):
        try:
            if hasattr(request, 'tenant') and request.tenant:
                logger.debug(f"Tenant from request: {request.tenant.schema_name}")
                return request.tenant
            if hasattr(request.user, 'tenant') and request.user.tenant:
                logger.debug(f"Tenant from user: {request.user.tenant.schema_name}")
                return request.user.tenant
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

    def get(self, request):
        tenant = self.get_tenant_from_token(request)
        with tenant_context(tenant):
            # Check permissions: Only admins, superusers, or team managers can list all tenant users
            if not (request.user.is_superuser or request.user.role == 'admin' or request.user.role == 'team_manager'):
                logger.warning(f"Unauthorized tenant users list attempt by user {request.user.email}")
                return Response(
                    {"status": "error", "message": "Only admins or team managers can list all tenant users"},
                    status=status.HTTP_403_FORBIDDEN
                )

            try:
                users = CustomUser.objects.filter(tenant=tenant)
                serializer = CustomUserSerializer(users, many=True, context={'request': request})
                logger.info(f"Retrieved {users.count()} users for tenant {tenant.schema_name}")
                return Response(
                    {
                        "status": "success",
                        "message": f"Retrieved {users.count()} users for tenant {tenant.schema_name}",
                        "data": serializer.data
                    },
                    status=status.HTTP_200_OK
                )
            except Exception as e:
                logger.error(f"Error listing users for tenant {tenant.schema_name}: {str(e)}")
                return Response(
                    {"status": "error", "message": str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

# New view for listing all users in a branch
class BranchUsersListView(APIView):
    permission_classes = [IsAuthenticated]

    def get_tenant_from_token(self, request):
        try:
            if hasattr(request, 'tenant') and request.tenant:
                logger.debug(f"Tenant from request: {request.tenant.schema_name}")
                return request.tenant
            if hasattr(request.user, 'tenant') and request.user.tenant:
                logger.debug(f"Tenant from user: {request.user.tenant.schema_name}")
                return request.user.tenant
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

    def get(self, request, branch_id):
        tenant = self.get_tenant_from_token(request)
        with tenant_context(tenant):
            try:
                branch = Branch.objects.get(id=branch_id, tenant=tenant)
            except Branch.DoesNotExist:
                logger.error(f"Branch with ID {branch_id} not found for tenant {tenant.schema_name}")
                return Response(
                    {"status": "error", "message": f"Branch with ID {branch_id} not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Check permissions: Admins, superusers, team managers, or recruiters (if branch matches their own)
            if not (request.user.is_superuser or 
                    request.user.role == 'admin' or 
                    request.user.role == 'team_manager' or 
                    (request.user.role == 'recruiter' and request.user.branch == branch)):
                logger.warning(f"Unauthorized branch users list attempt by user {request.user.email} for branch {branch.name}")
                return Response(
                    {"status": "error", "message": "Only admins, team managers, or recruiters assigned to this branch can list users"},
                    status=status.HTTP_403_FORBIDDEN
                )

            try:
                users = CustomUser.objects.filter(tenant=tenant, branch=branch)
                serializer = CustomUserSerializer(users, many=True, context={'request': request})
                logger.info(f"Retrieved {users.count()} users for branch {branch.name} in tenant {tenant.schema_name}")
                return Response(
                    {
                        "status": "success",
                        "message": f"Retrieved {users.count()} users for branch {branch.name}",
                        "data": serializer.data
                    },
                    status=status.HTTP_200_OK
                )
            except Exception as e:
                logger.error(f"Error listing users for branch {branch_id} in tenant {tenant.schema_name}: {str(e)}")
                return Response(
                    {"status": "error", "message": str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )