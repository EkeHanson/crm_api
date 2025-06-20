# lumina_care/views.py
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import serializers
from django_tenants.utils import tenant_context
from core.models import Domain, Tenant
from users.models import CustomUser
import logging
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
logger = logging.getLogger(__name__)
from users.serializers import CustomUserSerializer  # Import this


class CustomTokenSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if not email:
            raise serializers.ValidationError("Email is required.")

        try:
            email_domain = email.split('@')[1]
            logger.debug(f"Email domain extracted: {email_domain}")
        except IndexError:
            raise serializers.ValidationError("Invalid email format.")

        domain = Domain.objects.filter(domain=email_domain).first()
        if not domain:
            logger.error(f"No domain found for: {email_domain}")
            raise serializers.ValidationError("No tenant found for this email domain.")

        tenant = domain.tenant
        logger.info(f"Authenticating user for tenant: {tenant.schema_name}")

        with tenant_context(tenant):
            user = CustomUser.objects.filter(email=email).first()
            if not user or not user.check_password(password):
                logger.error(f"Invalid credentials for user: {email}")
                raise serializers.ValidationError("Invalid credentials.")

            if not user.is_active:
                logger.error(f"Inactive user: {email}")
                raise serializers.ValidationError("User account is inactive.")

            data = super().validate(attrs)
            refresh = RefreshToken.for_user(user)
            refresh['tenant_id'] = str(tenant.id)
            refresh['tenant_schema'] = tenant.schema_name

            data['refresh'] = str(refresh)
            data['access'] = str(refresh.access_token)
            data['tenant_id'] = str(tenant.id)
            data['tenant_schema'] = tenant.schema_name

            # 👇 Add user data here
            data['user'] = CustomUserSerializer(user).data

            logger.debug(f"Token data with user: {data}")
            return data

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenSerializer



class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        refresh = RefreshToken(attrs['refresh'])

        # Extract tenant info from token
        tenant_id = refresh.get('tenant_id', None)
        tenant_schema = refresh.get('tenant_schema', None)

        if not tenant_id or not tenant_schema:
            raise serializers.ValidationError("Invalid token: tenant info missing")

        try:
            tenant = Tenant.objects.get(id=tenant_id, schema_name=tenant_schema)
        except Tenant.DoesNotExist:
            raise serializers.ValidationError("Invalid tenant")

        # Switch to tenant context
        with tenant_context(tenant):
            # Let the parent class generate the new access token
            data = super().validate(attrs)
            # Optionally, re-add tenant info
            data['tenant_id'] = str(tenant.id)
            data['tenant_schema'] = tenant.schema_name
            return data

class CustomTokenRefreshView(TokenRefreshView):
    serializer_class = CustomTokenRefreshSerializer
