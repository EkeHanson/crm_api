# apps/talent_engine/serializers.py
from rest_framework import serializers
from .models import JobRequisition
from users.models import CustomUser

class JobRequisitionSerializer(serializers.ModelSerializer):
    requested_by = serializers.SlugRelatedField(
        slug_field='email',
        queryset=CustomUser.objects.all(),
        required=False
    )
    
    tenant = serializers.SlugRelatedField(
        slug_field='schema_name',
        read_only=True  # No queryset needed for read-only fields
    )

    class Meta:
        model = JobRequisition
        fields = [
            'id', 'tenant', 'title', 'status', 'requested_by', 'role',
            'qualification_requirement', 'experience_requirement',
            'knowledge_requirement', 'reason', 'requested_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant', 'requested_date', 'created_at', 'updated_at']

    def validate(self, data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            data['requested_by'] = request.user
        return data