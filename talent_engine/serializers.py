from rest_framework import serializers
from .models import JobRequisition
from users.models import CustomUser
import logging

logger = logging.getLogger('talent_engine')
from rest_framework import serializers
from django.contrib.auth.models import User
import uuid

class ComplianceItemSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False, default=uuid.uuid4)
    name = serializers.CharField(max_length=255)
    # description = serializers.CharField(max_length=1000, allow_blank=True, default='')
    required = serializers.BooleanField(default=True)
    status = serializers.ChoiceField(choices=['pending', 'completed', 'failed'], default='pending')
    checked_by = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(),
        allow_null=True,  # Allow null for requisition compliance items
        required=False    # Not required for creation/update
    )
    checked_at = serializers.DateTimeField(allow_null=True, default=None)

    def validate(self, data):
        # Ensure checked_by and checked_at are consistent
        if data.get('status') in ['completed', 'failed'] and not data.get('checked_by'):
            raise serializers.ValidationError("checked_by is required when status is completed or failed.")
        if data.get('checked_by') and not data.get('checked_at'):
            raise serializers.ValidationError("checked_at is required when checked_by is provided.")
        return data
class JobRequisitionSerializer(serializers.ModelSerializer):
    requested_by = serializers.SerializerMethodField()
    tenant = serializers.SlugRelatedField(slug_field='schema_name', read_only=True)
    tenant_domain = serializers.SerializerMethodField()
    compliance_checklist = serializers.SerializerMethodField()

    class Meta:
        model = JobRequisition
        fields = [
            'id', 'tenant', 'tenant_domain', 'title', 'unique_link', 'status', 'requested_by', 'role', 'company_name',
            'job_type', 'location_type', 'company_address', 'salary_range',
            'job_description', 'number_of_candidates', 'qualification_requirement',
            'experience_requirement', 'knowledge_requirement', 'reason', 'job_requisition_code', 'job_application_code',
            'deadline_date', 'start_date', 'responsibilities', 'documents_required',
            'compliance_checklist', 'advert_banner', 'requested_date', 'publish_status',
            'is_deleted', 'created_at', 'updated_at', 'num_of_applications', 'job_location'
        ]
        read_only_fields = ['id', 'tenant', 'tenant_domain', 'unique_link', 'requested_date', 'is_deleted', 'created_at', 'updated_at']

    def get_requested_by(self, obj):
        if obj.requested_by:
            return {
                'email': obj.requested_by.email,
                'first_name': obj.requested_by.first_name or '',
                'last_name': obj.requested_by.last_name or '',
                'job_role': obj.requested_by.job_role or '',
            }
        return None

    def get_tenant_domain(self, obj):
        primary_domain = obj.tenant.domain_set.filter(is_primary=True).first()
        return primary_domain.domain if primary_domain else None

    def get_compliance_checklist(self, obj):
        serialized_items = []
        for item in obj.compliance_checklist:
            if isinstance(item, dict) and 'name' in item:
                serialized_item = ComplianceItemSerializer(item).data
                if serialized_item is not None:  # Ensure no None values are included
                    serialized_items.append(serialized_item)
            else:
                # logger.warning(f"Skipping invalid compliance item: {item}")
                pass
        return serialized_items

    def validate_compliance_checklist(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Compliance checklist must be a list.")
        for item in value:
            if not isinstance(item, dict) or not item.get("name"):
                raise serializers.ValidationError("Each compliance item must be a dictionary with a 'name' field.")
        return value

    def create(self, validated_data):
        compliance_checklist = validated_data.pop('compliance_checklist', [])
        instance = super().create(validated_data)
        for item in compliance_checklist:
            instance.add_compliance_item(
                name=item["name"],
                description=item.get("description", ""),
                required=item.get("required", True)
            )
        return instance

    def update(self, instance, validated_data):
        compliance_checklist = validated_data.pop('compliance_checklist', None)
        instance = super().update(instance, validated_data)
        if compliance_checklist is not None:
            instance.compliance_checklist = []
            for item in compliance_checklist:
                instance.add_compliance_item(
                    name=item["name"],
                    description=item.get("description", ""),
                    required=item.get("required", True)
                )
        return instance