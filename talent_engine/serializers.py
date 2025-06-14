from rest_framework import serializers
from .models import JobRequisition
from users.models import CustomUser

class JobRequisitionSerializer(serializers.ModelSerializer):
    requested_by = serializers.SerializerMethodField()
    tenant = serializers.SlugRelatedField(
        slug_field='schema_name',
        read_only=True
    )

    class Meta:
        model = JobRequisition
        fields = [
            'id', 'tenant', 'title', 'status', 'requested_by', 'role', 'company_name',
            'job_type', 'location_type', 'company_address', 'salary_range',
            'job_description', 'number_of_candidates', 'qualification_requirement',
            'experience_requirement', 'knowledge_requirement', 'reason',
            'deadline_date', 'start_date', 'responsibilities', 'documents_required',
            'compliance_checklist', 'advert_banner', 'requested_date', 'publish_status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant', 'requested_date', 'created_at', 'updated_at']

    def get_requested_by(self, obj):
        if obj.requested_by:
            return {
                'email': obj.requested_by.email,
                'first_name': obj.requested_by.first_name or '',
                'last_name': obj.requested_by.last_name or '',
            }
        return None

    def validate(self, data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            data['requested_by'] = request.user

        # Validate required fields when publishing
        if data.get('publish_status', False):
            required_fields = [
                'title', 'company_name', 'job_description', 'deadline_date', 'responsibilities',
                'documents_required', 'compliance_checklist'
            ]
            for field in required_fields:
                if not data.get(field):
                    raise serializers.ValidationError({field: f'{field.replace("_", " ").title()} is required to publish.'})
            if data.get('location_type') == 'on_site' and not data.get('company_address'):
                raise serializers.ValidationError({'company_address': 'Company Address is required for on-site jobs.'})
            if not data.get('responsibilities') or not any(r.strip() for r in data.get('responsibilities')):
                raise serializers.ValidationError({'responsibilities': 'At least one responsibility is required.'})

        return data