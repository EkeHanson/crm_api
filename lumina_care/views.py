# lumina_care/views.py
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django_tenants.utils import tenant_context
from core.models import Domain, Tenant
from users.models import CustomUser
import logging

logger = logging.getLogger(__name__)

class CustomTokenSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if not email:
            raise serializers.ValidationError("Email is required.")

        # Extract domain from email (e.g., user@testtenant.com -> testtenant.com)
        try:
            email_domain = email.split('@')[1]
        except IndexError:
            raise serializers.ValidationError("Invalid email format.")

        # Find tenant by domain
        domain = Domain.objects.filter(domain=email_domain).first()
        if not domain:
            raise serializers.ValidationError("No tenant found for this email domain.")

        tenant = domain.tenant
        logger.info(f"Authenticating user for tenant: {tenant.schema_name}")

        # Authenticate within tenant context
        with tenant_context(tenant):
            user = CustomUser.objects.filter(email=email).first()
            if not user or not user.check_password(password):
                raise serializers.ValidationError("Invalid credentials.")

            if not user.is_active:
                raise serializers.ValidationError("User account is inactive.")

            data = super().validate(attrs)
            data['tenant_id'] = tenant.id
            data['tenant_schema'] = tenant.schema_name
            return data

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenSerializer