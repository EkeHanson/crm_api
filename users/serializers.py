from rest_framework import serializers
from .models import CustomUser, UserProfile, UserDocument
from core.models import Module, Tenant, RolePermission, Domain
import re
from django_tenants.utils import tenant_context
import logging

logger = logging.getLogger('users')


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['phone', 'gender', 'dob', 'street', 'city', 'state', 'zip_code', 'department']

    def validate(self, data):
        required_fields = ['phone', 'gender', 'dob', 'street', 'city', 'state', 'zip_code', 'department']
        for field in required_fields:
            if field not in data or not data[field]:
                raise serializers.ValidationError({field: "This field is required."})
        return data


class CustomUserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    modules = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name',
        source='profile.modules'
    )
    tenant = serializers.SlugRelatedField(
        read_only=True,
        slug_field='name'
    )

    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'role', 'job_role',
            'dashboard', 'access_level', 'status', 'two_factor', 'is_superuser',
            'profile', 'modules', 'tenant'
        ]
        read_only_fields = ['id', 'is_superuser']

class AdminUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = CustomUser
        fields = [
            'username', 'email', 'password', 'first_name', 'last_name', 'job_role',
            'role', 'dashboard', 'access_level', 'status', 'two_factor', 'is_superuser'
        ]
        extra_kwargs = {
            'role': {'required': False, 'default': 'admin'},
            'email': {'required': True},
            'is_superuser': {'default': True},
            'is_staff': {'default': True},
            'status': {'default': 'active'},
        }

    def validate_email(self, value):
        try:
            domain = value.split('@')[1].lower()
        except IndexError:
            raise serializers.ValidationError("Invalid email format.")
        if not Domain.objects.filter(domain=domain).exists():
            raise serializers.ValidationError(f"No tenant found for domain '{domain}'.")
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError(f"User with email '{value}' already exists.")
        return value

    def create(self, validated_data):
        email = validated_data['email']
        domain = email.split('@')[1].lower()
        domain_obj = Domain.objects.get(domain=domain)
        tenant = domain_obj.tenant
        password = validated_data.pop('password')
        validated_data['is_superuser'] = True
        validated_data['is_staff'] = True
        validated_data['role'] = validated_data.get('role', 'admin')
        validated_data['status'] = validated_data.get('status', 'active')

        from django_tenants.utils import tenant_context
        with tenant_context(tenant):
            user = CustomUser.objects.create_user(
                **validated_data,
                tenant=tenant,
                is_active=True
            )
            user.set_password(password)
            user.save()
            return user


class UserDocumentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(required=True)
    title = serializers.CharField(required=True)

    class Meta:
        model = UserDocument
        fields = ['id', 'title', 'file', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']

    def validate_file(self, value):
        if not value.name.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg')):
            raise serializers.ValidationError("Only PDF or image files are allowed.")
        if value.size > 10 * 1024 * 1024:  # 10MB limit
            raise serializers.ValidationError("File size cannot exceed 10MB.")
        return value

class UserCreateSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(required=True)
    modules = serializers.PrimaryKeyRelatedField(queryset=Module.objects.all(), many=True, required=False)
    documents = UserDocumentSerializer(many=True, required=False)
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    is_superuser = serializers.BooleanField(default=False, required=False)

    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'password', 'first_name', 'last_name', 'role', 'job_role',
            'dashboard', 'access_level', 'status', 'two_factor', 'is_superuser', 'profile',
            'modules', 'documents'
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'email': {'required': True},
            'username': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'dashboard': {'required': True},
            'status': {'required': True},
            'two_factor': {'required': True},
        }

    def to_internal_value(self, data):
        # Handle FormData with nested profile and documents
        mutable_data = data.copy()  # Create a mutable copy of the QueryDict

        # Parse profile fields (e.g., profile[phone], profile[city])
        profile_data = {}
        for key, value in data.items():
            if key.startswith('profile[') and key.endswith(']'):
                field_name = key[len('profile['):-1]
                profile_data[field_name] = value
        if profile_data:
            mutable_data['profile'] = profile_data
        else:
            raise serializers.ValidationError({'profile': 'This field is required.'})

        # Parse documents fields (e.g., documents[0][title], documents[0][file])
        documents_data = []
        document_indices = set()
        for key in data.keys():
            if key.startswith('documents[') and key.endswith('][title]') or key.endswith('][file]'):
                index = key.split('[')[1].split(']')[0]
                document_indices.add(index)
        for index in sorted(document_indices, key=int):
            title_key = f'documents[{index}][title]'
            file_key = f'documents[{index}][file]'
            if title_key in data and file_key in data:
                documents_data.append({
                    'title': data[title_key],
                    'file': data[file_key]
                })
            else:
                raise serializers.ValidationError({
                    'documents': f'Missing title or file for document index {index}.'
                })
        if documents_data:
            mutable_data['documents'] = documents_data

        return super().to_internal_value(mutable_data)

    def validate_username(self, value):
        if not re.match(r'^[a-zA-Z0-9_]+$', value):
            raise serializers.ValidationError("Username can only contain letters, numbers, or underscores.")
        tenant = self.context['request'].user.tenant
        if CustomUser.objects.filter(username=value, tenant=tenant).exists():
            raise serializers.ValidationError(f"Username '{value}' already exists for this tenant.")
        return value

    def validate_email(self, value):
        try:
            domain = value.split('@')[1].lower()
        except IndexError:
            raise serializers.ValidationError("Invalid email format.")
        if not Domain.objects.filter(domain=domain).exists():
            raise serializers.ValidationError(f"No tenant found for domain '{domain}'.")
        tenant = self.context['request'].user.tenant
        if CustomUser.objects.filter(email=value, tenant=tenant).exists():
            raise serializers.ValidationError(f"User with email '{value}' already exists.")
        return value

    def validate_job_role(self, value):
        if not value.strip():
            raise serializers.ValidationError("Job role cannot be empty.")
        if len(value) > 100:
            raise serializers.ValidationError("Job role cannot exceed 100 characters.")
        return value.strip()

    def validate(self, data):
        tenant = self.context['request'].user.tenant
        logger.debug(f"Validating user data for tenant: {tenant.schema_name}")

        role = data.get('role')
        valid_roles = [r[0] for r in CustomUser.ROLES]
        if role and role not in valid_roles:
            raise serializers.ValidationError(f"Invalid role. Must be one of: {', '.join(valid_roles)}.")

        dashboard = data.get('dashboard')
        valid_dashboards = [d[0] for d in CustomUser.DASHBOARD_TYPES]
        if dashboard and dashboard not in valid_dashboards:
            raise serializers.ValidationError(f"Invalid dashboard. Must be one of: {', '.join(valid_dashboards)}.")

        access_level = data.get('access_level')
        valid_access_levels = [a[0] for a in CustomUser.ACCESS_LEVELS]
        if access_level and access_level not in valid_access_levels:
            raise serializers.ValidationError(f"Invalid access level. Must be one of: {', '.join(valid_access_levels)}.")

        status = data.get('status')
        valid_statuses = [s[0] for s in CustomUser.STATUS_CHOICES]
        if status and status not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}.")

        two_factor = data.get('two_factor')
        valid_two_factor = [t[0] for t in CustomUser.TWO_FACTOR_CHOICES]
        if two_factor and two_factor not in valid_two_factor:
            raise serializers.ValidationError(f"Invalid two-factor option. Must be one of: {', '.join(valid_two_factor)}.")

        return data

    def create(self, validated_data):
        profile_data = validated_data.pop('profile')
        modules = validated_data.pop('modules', [])
        documents = validated_data.pop('documents', [])
        is_superuser = validated_data.pop('is_superuser', False)
        tenant = self.context['request'].user.tenant
        password = validated_data.pop('password')

        try:
            with tenant_context(tenant):
                user = CustomUser.objects.create_user(
                    **validated_data,
                    tenant=tenant,
                    is_superuser=is_superuser,
                    is_staff=is_superuser,
                    is_active=validated_data.get('status') == 'active'
                )
                user.set_password(password)
                user.save()
                logger.info(f"User created: {user.email} (ID: {user.id}) for tenant {tenant.schema_name}")

                profile = UserProfile.objects.create(user=user, **profile_data)
                profile.modules.set(modules)
                logger.debug(f"Profile created for user {user.email} with modules: {[m.name for m in modules]}")

                for module in modules:
                    RolePermission.objects.update_or_create(
                        role=user.role,
                        module=module,
                        tenant=tenant,
                        defaults={
                            'can_view': True,
                            'can_create': user.access_level == 'full',
                            'can_edit': user.access_level == 'full',
                            'can_delete': user.access_level == 'full',
                        }
                    )
                    logger.debug(f"RolePermission created for role {user.role}, module {module.name}, tenant {tenant.schema_name}")

                for doc_data in documents:
                    UserDocument.objects.create(
                        user=user,
                        tenant=tenant,
                        title=doc_data['title'],
                        file=doc_data['file']
                    )
                    logger.debug(f"Document created: {doc_data['title']} for user {user.email}")

                return user
        except Exception as e:
            logger.error(f"Error creating user for tenant {tenant.schema_name}: {str(e)}")
            raise serializers.ValidationError(f"Failed to create user: {str(e)}")