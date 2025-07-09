import logging

from django_tenants.utils import tenant_context
from allauth.socialaccount.models import SocialAccount

from rest_framework import viewsets, serializers, status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import CustomUser
from .serializers import CustomUserSerializer, UserCreateSerializer, AdminUserCreateSerializer
from core.models import Tenant

logger = logging.getLogger('users')


# views.py
import logging
from django_tenants.utils import tenant_context
from rest_framework import viewsets, serializers, status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from .models import CustomUser
from .serializers import CustomUserSerializer, UserCreateSerializer, AdminUserCreateSerializer
from core.models import Tenant

logger = logging.getLogger('users')

class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self.request.user.tenant
        with tenant_context(tenant):
            return CustomUser.objects.filter(tenant=tenant)

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
        logger.debug(f"Request files: {[(key, file.name, file.size) for key, file in request.FILES.items()]}")
        print(f"Request data: {dict(request.data)}")
        print(f"Request files: {[(key, file.name, file.size) for key, file in request.FILES.items()]}")

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
        else:
            logger.error(f"Validation error for tenant {request.user.tenant.schema_name}: {serializer.errors}")
            print(f"Validation error: {serializer.errors}")
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
                })
        except SocialAccount.DoesNotExist:
            logger.error(f"No social account found for user {user.email}")
            return Response({"error": "Social account not found"}, status=400)
        except Exception as e:
            logger.error(f"Error in social login callback: {str(e)}")
            return Response({"error": str(e)}, status=500)