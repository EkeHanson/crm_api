from rest_framework import serializers
from .models import CustomUser, UserProfile, UserDocument
from core.models import Module, RolePermission, Domain, Branch
import re
from django.utils import timezone
import logging
from .models import CustomUser, PasswordResetToken
from django_tenants.utils import tenant_context

logger = logging.getLogger('users')

# Existing serializers (unchanged, included for context)
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['phone', 'gender', 'dob', 'street', 'city', 'state', 'zip_code', 'department']

    def validate(self, data):
        required_fields = ['phone', 'gender', 'dob', 'street', 'city', 'state', 'zip_code', 'department']
        errors = {}
        for field in required_fields:
            if field not in data or not data[field]:
                errors[field] = "This field is required."
        if errors:
            raise serializers.ValidationError(errors)
        return data

class UserDocumentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(required=True)
    title = serializers.CharField(required=True)
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = UserDocument
        fields = ['id', 'title', 'file', 'uploaded_at', 'branch']
        read_only_fields = ['id', 'uploaded_at']

    def validate_file(self, value):
        if not value.name.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg')):
            raise serializers.ValidationError("Only PDF or image files are allowed.")
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("File size cannot exceed 10MB.")
        return value

class UserCreateSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(required=True)
    modules = serializers.PrimaryKeyRelatedField(queryset=Module.objects.all(), many=True, required=False)
    documents = UserDocumentSerializer(many=True, required=False)
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    is_superuser = serializers.BooleanField(default=False, required=False)
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'password', 'first_name', 'last_name', 'role', 'job_role',
            'dashboard', 'access_level', 'status', 'two_factor', 'is_superuser', 'profile',
            'modules', 'documents', 'branch'
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
        mutable_data = data.copy() if hasattr(data, 'copy') else dict(data)
        logger.debug(f"Request data: {dict(data)}")
        request = self.context.get('request')
        logger.debug(f"Request files: {[(key, file.name, file.size) for key, file in (request.FILES.items() if request else [])]}")

        profile_data = {}
        profile_fields = ['phone', 'gender', 'dob', 'street', 'city', 'state', 'zip_code', 'department']
        profile_errors = {}
        if 'profile' in data and isinstance(data['profile'], dict):
            logger.debug("Found nested profile dictionary")
            profile_data = data['profile']
            for field in profile_fields:
                if field not in profile_data or not profile_data[field]:
                    profile_errors[f'profile[{field}]'] = 'This field is required.'
        else:
            for field in profile_fields:
                key = f'profile[{field}]'
                if key in data:
                    value = data.get(key)
                    if value:
                        profile_data[field] = value
                    else:
                        profile_errors[f'profile[{field}]'] = 'This field is required.'
                else:
                    profile_errors[f'profile[{field}]'] = 'This field is required.'
        if profile_errors:
            logger.error(f"Profile validation errors: {profile_errors}")
            raise serializers.ValidationError({'profile': profile_errors})
        if not profile_data:
            logger.error("No valid profile fields found in request data")
            raise serializers.ValidationError({'profile': 'At least one profile field is required.'})
        mutable_data['profile'] = profile_data
        logger.debug(f"Parsed profile data: {profile_data}")

        documents_data = []
        document_indices = set()
        for key in data.keys():
            if key.startswith('documents[') and (key.endswith('][title]') or key.endswith('][file]') or key.endswith('][branch]')):
                index = key.split('[')[1].split(']')[0]
                document_indices.add(index)
        document_errors = {}
        for index in sorted(document_indices, key=int):
            title_key = f'documents[{index}][title]'
            file_key = f'documents[{index}][file]'
            branch_key = f'documents[{index}][branch]'
            title = data.get(title_key)
            file = request.FILES.get(file_key) if request else None
            branch = data.get(branch_key)
            logger.debug(f"Processing document {index}: title={title}, file={file.name if file else None}, branch={branch}")
            if title and file:
                try:
                    doc_serializer = UserDocumentSerializer(data={'title': title, 'file': file, 'branch': branch})
                    if doc_serializer.is_valid():
                        documents_data.append({'title': title, 'file': file, 'branch': branch})
                    else:
                        document_errors[f'documents[{index}]'] = doc_serializer.errors
                except Exception as e:
                    document_errors[f'documents[{index}]'] = f"Invalid document: {str(e)}"
            else:
                if not title:
                    document_errors[f'documents[{index}][title]'] = 'Document title is required.'
                if not file:
                    document_errors[f'documents[{index}][file]'] = 'Document file is required.'
        if document_errors:
            logger.error(f"Document validation errors: {document_errors}")
            raise serializers.ValidationError({'documents': document_errors})
        if documents_data:
            mutable_data['documents'] = documents_data
            logger.debug(f"Parsed documents data: {[{k: v.name if k == 'file' else v for k, v in doc.items()} for doc in documents_data]}")
        else:
            mutable_data['documents'] = []

        modules_data = []
        module_indices = set()
        for key in data.keys():
            if key.startswith('modules[') and key.endswith(']'):
                index = key.split('[')[1].split(']')[0]
                module_indices.add(index)
        for index in sorted(module_indices, key=int):
            module_id = data.get(f'modules[{index}]')
            if module_id:
                modules_data.append(module_id)
        mutable_data['modules'] = modules_data
        logger.debug(f"Parsed modules: {modules_data}")

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
        branch = validated_data.pop('branch', None)
        tenant = self.context['request'].user.tenant
        password = validated_data.pop('password')

        try:
            with tenant_context(tenant):
                user = CustomUser.objects.create_user(
                    **validated_data,
                    tenant=tenant,
                    branch=branch,
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
                        file=doc_data['file'],
                        branch=doc_data.get('branch')
                    )
                    logger.debug(f"Document created: {doc_data['title']} for user {user.email}")

                return user
        except Exception as e:
            logger.error(f"Error creating user for tenant {tenant.schema_name}: {str(e)}")
            raise serializers.ValidationError(f"Failed to create user: {str(e)}")

class CustomUserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    modules = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name',
        source='profile.modules'
    )
    tenant = serializers.SlugRelatedField(read_only=True, slug_field='name')
    branch = serializers.SlugRelatedField(read_only=True, slug_field='name', allow_null=True)

    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'role', 'job_role',
            'dashboard', 'access_level', 'status', 'two_factor', 'is_superuser',
            'profile', 'modules', 'tenant', 'branch'
        ]
        read_only_fields = ['id', 'is_superuser']

class AdminUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = CustomUser
        fields = [
            'username', 'email', 'password', 'first_name', 'last_name', 'job_role',
            'role', 'dashboard', 'access_level', 'status', 'two_factor', 'is_superuser', 'branch'
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

# New serializer for updating user branch
class UserBranchUpdateSerializer(serializers.ModelSerializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = CustomUser
        fields = ['branch']

    def validate_branch(self, value):
        if value is not None:
            tenant = self.context['request'].user.tenant
            with tenant_context(tenant):
                if not Branch.objects.filter(id=value.id, tenant=tenant).exists():
                    raise serializers.ValidationError(f"Branch with ID {value.id} does not belong to tenant {tenant.schema_name}.")
        return value

    def validate(self, data):
        tenant = self.context['request'].user.tenant
        user = self.instance
        if user.tenant != tenant:
            raise serializers.ValidationError("Cannot update branch for a user from a different tenant.")
        return data

    def update(self, instance, validated_data):
        instance.branch = validated_data.get('branch', instance.branch)
        instance.save()
        return instance
    



class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        tenant = self.context['request'].tenant
        with tenant_context(tenant):
            if not CustomUser.objects.filter(email=value, tenant=tenant).exists():
                raise serializers.ValidationError(f"No user found with email '{value}' for this tenant.")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(write_only=True, min_length=8, required=True)

    def validate_token(self, value):
        tenant = self.context['request'].tenant
        with tenant_context(tenant):
            try:
                reset_token = PasswordResetToken.objects.get(token=value, tenant=tenant)
                if reset_token.expires_at < timezone.now():
                    raise serializers.ValidationError("This token has expired.")
                if reset_token.used:
                    raise serializers.ValidationError("This token has already been used.")
            except PasswordResetToken.DoesNotExist:
                raise serializers.ValidationError("Invalid token.")
        return value

    def validate_new_password(self, value):
        if not any(c.isupper() for c in value) or not any(c.isdigit() for c in value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter and one number.")
        return value




# class PasswordResetConfirmSerializer(serializers.Serializer):
#     new_password = serializers.CharField(min_length=8, write_only=True)

#     def validate_new_password(self, value):
#         if not re.search(r'[A-Z]', value):
#             raise serializers.ValidationError("Password must contain at least one uppercase letter.")
#         if not re.search(r'[a-z]', value):
#             raise serializers.ValidationError("Password must contain at least one lowercase letter.")
#         if not re.search(r'[0-9]', value):
#             raise serializers.ValidationError("Password must contain at least one digit.")
#         if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
#             raise serializers.ValidationError("Password must contain at least one special character.")
#         return value










