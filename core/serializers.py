# apps/core/serializers.py
from rest_framework import serializers
from .models import Tenant, Domain, Module, TenantConfig, Branch
from django.utils import timezone
import re
import logging
from django.db import transaction
import uuid
import os
import mimetypes
from django.conf import settings
logger = logging.getLogger('core')
from django_tenants.utils import tenant_context
from services.supabase_storage import SupabaseStorageService
from lumina_care.supabase_client import supabase


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ['id', 'name', 'location', 'is_head_office', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_name(self, value):
        if not re.match(r'^[a-zA-Z0-9\s\-]+$', value):
            raise serializers.ValidationError("Branch name can only contain letters, numbers, spaces, or hyphens.")
        try:
            tenant = self.context['request'].user.tenant
        except AttributeError as e:
            logger.error(f"Error accessing request.user.tenant: {str(e)}")
            raise serializers.ValidationError("Tenant not found in request context")
        with tenant_context(tenant):
            if Branch.objects.filter(tenant=tenant, name=value).exists():
                raise serializers.ValidationError(f"Branch '{value}' already exists for this tenant.")
        return value

    def validate_is_head_office(self, value):
        if value:  # Only validate if is_head_office is True
            try:
                tenant = self.context['request'].user.tenant
            except AttributeError as e:
                logger.error(f"Error accessing request.user.tenant: {str(e)}")
                raise serializers.ValidationError("Tenant not found in request context")
            with tenant_context(tenant):
                # Exclude the current instance during updates
                existing_head_office = Branch.objects.filter(
                    tenant=tenant,
                    is_head_office=True
                ).exclude(id=self.instance.id if self.instance else None)
                if existing_head_office.exists():
                    raise serializers.ValidationError(
                        f"Another branch ('{existing_head_office.first().name}') is already set as head office for this tenant."
                    )
        return value

    def validate(self, data):
        try:
            tenant = self.context['request'].user.tenant
        except AttributeError as e:
            logger.error(f"Error accessing request.user.tenant: {str(e)}")
            raise serializers.ValidationError("Tenant not found in request context")
        data['tenant'] = tenant  # Set tenant from request context
        return data

    def create(self, validated_data):
        return super().create(validated_data)



class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ['id', 'domain', 'is_primary']


class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ['id', 'name', 'is_active']
        read_only_fields = ['id']

    def validate_name(self, value):
        if not re.match(r'^[a-zA-Z0-9\s\-]+$', value):
            raise serializers.ValidationError("Module name can only contain letters, numbers, spaces, or hyphens.")
        tenant = self.context['request'].user.tenant
        with tenant_context(tenant):
            if Module.objects.filter(name=value, tenant=tenant).exists():
                raise serializers.ValidationError(f"Module '{value}' already exists for this tenant.")
        return value

    def validate(self, data):
        try:
            tenant = self.context['request'].user.tenant
        except AttributeError as e:
            logger.error(f"Error accessing request.user.tenant: {str(e)}")
            raise serializers.ValidationError("Tenant not found in request context")
        data['tenant'] = tenant  # Set tenant from request context
        return data

class EmailTemplateSerializer(serializers.Serializer):
    content = serializers.CharField()
    is_auto_sent = serializers.BooleanField(default=False)


class TenantConfigSerializer(serializers.ModelSerializer):
    email_templates = serializers.DictField(
        child=EmailTemplateSerializer(),
        required=False
    )

    class Meta:
        model = TenantConfig
        fields = ['logo', 'custom_fields', 'email_templates']



class TenantSerializer(serializers.ModelSerializer):
    logo_file = serializers.FileField(write_only=True, required=False)

    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'title', 'schema_name', 'created_at', 'logo', 'logo_file',
            'email_host', 'email_port', 'email_use_ssl', 'email_host_user',
            'email_host_password', 'default_from_email', 'about_us'
        ]
        read_only_fields = ['id', 'created_at', 'schema_name', 'logo']

    def validate_name(self, value):
        if not re.match(r'^[a-zA-Z0-9\s\'-]+$', value):
            raise serializers.ValidationError("Tenant name can only contain letters, numbers, spaces, apostrophes, or hyphens.")
        return value

    def validate_schema_name(self, value):
        if not re.match(r'^[a-z0-9_]+$', value):
            raise serializers.ValidationError("Schema name can only contain lowercase letters, numbers, or underscores.")
        if Tenant.objects.filter(schema_name=value).exists():
            raise serializers.ValidationError("Schema name already exists.")
        return value

    def validate_domain(self, value):
        if not re.match(r'^[a-zA-Z0-9\-\.]+$', value):
            raise serializers.ValidationError("Invalid domain name.")
        if Domain.objects.filter(domain=value).exists():
            raise serializers.ValidationError(f"Domain '{value}' already exists.")
        return value

    def validate_logo_file(self, value):
        allowed_types = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError("Only image files are allowed for logo.")
        max_size = 5 * 1024 * 1024  # 5 MB
        if value.size > max_size:
            raise serializers.ValidationError("Logo file size exceeds 5 MB limit.")
        return value

    def create(self, validated_data):
        logo_file = validated_data.pop('logo_file', None)
        if logo_file:
            file_ext = os.path.splitext(logo_file.name)[1]
            filename = f"{uuid.uuid4()}{file_ext}"
            folder_path = f"tenant_logos/{timezone.now().strftime('%Y/%m/%d')}"
            path = f"{folder_path}/{filename}"
            content_type = mimetypes.guess_type(logo_file.name)[0]
            supabase.storage.from_(settings.SUPABASE_BUCKET).upload(
                path, logo_file.read(), {"content-type": content_type or 'application/octet-stream'}
            )
            file_url = supabase.storage.from_(settings.SUPABASE_BUCKET).get_public_url(path)
            validated_data['logo'] = file_url
        domain_name = validated_data.pop('domain')
        schema_name = validated_data.get('schema_name') or validated_data['name'].lower().replace(' ', '_').replace('-', '_')
        validated_data['schema_name'] = schema_name
        logger.info(f"Creating tenant with name: {validated_data['name']}, schema_name: {schema_name}, domain: {domain_name}")
        try:
            with transaction.atomic():
                tenant = Tenant.objects.create(**validated_data)
                logger.info(f"Tenant created: {tenant.id}, schema_name: {tenant.schema_name}")
                domain = Domain.objects.create(tenant=tenant, domain=domain_name, is_primary=True)
                logger.info(f"Domain created: {domain.domain} for tenant {tenant.id}")

                # Default email templates
                default_templates = {
                    'interviewScheduling': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'We’re pleased to invite you to an interview for the [Position] role at [Company].\n'
                            'Please let us know your availability so we can confirm a convenient time.\n\n'
                            'Best regards,\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    },
                    'interviewRescheduling': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'Due to unforeseen circumstances, we need to reschedule your interview originally set for [Old Date/Time]. '
                            'Kindly share a few alternative slots that work for you.\n\n'
                            'Thanks for your understanding,\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    },
                    'interviewRejection': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'Thank you for taking the time to interview. After careful consideration, '
                            'we have decided not to move forward.\n\n'
                            'Best wishes,\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    },
                    'interviewAcceptance': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'Congratulations! We are moving you to the next stage. We’ll follow up with next steps.\n\n'
                            'Looking forward,\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    },
                    'jobRejection': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'Thank you for applying. Unfortunately, we’ve chosen another candidate at this time.\n\n'
                            'Kind regards,\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    },
                    'jobAcceptance': {
                        'content': (
                            'Hello [Candidate Name],\n\n'
                            'We’re excited to offer you the [Position] role at [Company]! '
                            'Please find the offer letter attached.\n\n'
                            'Welcome aboard!\n[Your Name]'
                        ),
                        'is_auto_sent': False
                    }
                }

                # Create TenantConfig with default email templates
                try:
                    TenantConfig.objects.create(
                        tenant=tenant,
                        email_templates=default_templates
                    )
                    logger.info(f"TenantConfig created for tenant {tenant.id} with default email templates")
                except Exception as e:
                    logger.error(f"Failed to create TenantConfig for tenant {tenant.id}: {str(e)}")
                    raise

                # Create default modules
                default_modules = [
                    'Talent Engine', 'Compliance', 'Training', 'Care Coordination',
                    'Workforce', 'Analytics', 'Integrations', 'Assets Management', 'Payroll'
                ]
                for module_name in default_modules:
                    Module.objects.create(name=module_name, tenant=tenant)
                logger.info(f"Modules created for tenant {tenant.id}")

                try:
                    domains = tenant.domain_set.all()
                    logger.info(f"Domains for tenant {tenant.id}: {[d.domain for d in domains]}")
                except AttributeError as e:
                    logger.error(f"domain_set access failed: {str(e)}")
                    domains = Domain.objects.filter(tenant=tenant)
                    logger.info(f"Fallback domains for tenant {tenant.id}: {[d.domain for d in domains]}")
                return tenant
        except Exception as e:
            logger.error(f"Failed to create tenant or domain: {str(e)}")
            raise

    def update(self, instance, validated_data):
        logo_file = validated_data.pop('logo_file', None)
        if logo_file:
            file_ext = os.path.splitext(logo_file.name)[1]
            filename = f"{uuid.uuid4()}{file_ext}"
            folder_path = f"tenant_logos/{timezone.now().strftime('%Y/%m/%d')}"
            path = f"{folder_path}/{filename}"
            content_type = mimetypes.guess_type(logo_file.name)[0]
            supabase.storage.from_(settings.SUPABASE_BUCKET).upload(
                path, logo_file.read(), {"content-type": content_type or 'application/octet-stream'}
            )
            file_url = supabase.storage.from_(settings.SUPABASE_BUCKET).get_public_url(path)
            validated_data['logo'] = file_url
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        logo_path = instance.logo
        if logo_path:
            # If logo_path is already a URL, use it. Otherwise, generate Supabase public URL.
            if logo_path.startswith('http'):
                data['logo'] = logo_path
            else:
                # Generate Supabase public URL from path
                data['logo'] = supabase.storage.from_(settings.SUPABASE_BUCKET).get_public_url(logo_path)
        else:
            data['logo'] = ""
        return data


