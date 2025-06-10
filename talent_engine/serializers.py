# apps/talent_engine/serializers.py
from rest_framework import serializers
from .models import JobPosting

class JobPostingSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobPosting
        fields = '__all__'

    def validate(self, data):
        tenant = self.context['request'].user.tenant
        if data['tenant'] != tenant:
            raise serializers.ValidationError("Cannot create job for another tenant.")
        return data