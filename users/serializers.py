# apps/users/serializers.py
from rest_framework import serializers
from .models import CustomUser, UserProfile
from core.models import Module, Tenant

# apps/users/serializers.py
from rest_framework import serializers
from .models import CustomUser
from core.models import Tenant, Domain

class AdminUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password', 'role']
        extra_kwargs = {
            'role': {'required': False, 'default': 'admin'},
            'email': {'required': True},
            'username': {'required': True},
        }

    def validate_email(self, value):
        # Extract domain from email
        try:
            domain = value.split('@')[1].lower()
        except IndexError:
            raise serializers.ValidationError("Invalid email format.")

        # Check if domain is associated with a tenant
        if not Domain.objects.filter(domain=domain).exists():
            raise serializers.ValidationError(f"No tenant found for domain '{domain}'.")

        # Check for duplicate email
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError(f"User with email '{value}' already exists.")
        return value

    def create(self, validated_data):
        # Extract domain from email
        email = validated_data['email']
        domain = email.split('@')[1].lower()
        domain_obj = Domain.objects.get(domain=domain)
        tenant = domain_obj.tenant
        password = validated_data.pop('password')

        from django_tenants.utils import tenant_context
        with tenant_context(tenant):
            user = CustomUser.objects.create_superuser(
                username=validated_data['username'],
                email=validated_data['email'],
                password=password,
                role='admin',
                tenant=tenant,
                is_active=True,
                is_staff=True,
                is_superuser=True
            )
        return user
    
class UserSerializer(serializers.ModelSerializer):
    modules = serializers.PrimaryKeyRelatedField(queryset=Module.objects.all(), many=True, required=False)
    password = serializers.CharField(write_only=True)
    is_superuser = serializers.BooleanField(default=False, required=False)

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'password', 'role', 'modules', 'is_superuser']
        read_only_fields = ['id']

    def validate(self, data):
        # Get tenant from request context
        try:
            tenant = self.context['request'].user.tenant
        except AttributeError:
            raise serializers.ValidationError("Request context or user tenant is missing.")

        # Ensure modules belong to the same tenant
        modules = data.get('modules', [])
        for module in modules:
            if module.tenant != tenant:
                raise serializers.ValidationError(f"Module {module.name} does not belong to tenant {tenant.name}.")

        # Validate role
        role = data.get('role')
        valid_roles = [role[0] for role in CustomUser.ROLES]  # Extract valid role keys
        if role and role not in valid_roles:
            raise serializers.ValidationError(f"Invalid role. Must be one of: {', '.join(valid_roles)}.")

        return data

    def create(self, validated_data):
        modules = validated_data.pop('modules', [])
        is_superuser = validated_data.pop('is_superuser', False)
        tenant = self.context['request'].user.tenant
        # Create user with validated data
        user = CustomUser.objects.create_user(
            **validated_data,
            tenant=tenant,
            is_superuser=is_superuser,
            is_staff=is_superuser  # Superusers need is_staff for admin access
        )
        # Create user profile and assign modules
        profile = UserProfile.objects.create(user=user)
        profile.modules.set(modules)
        return user