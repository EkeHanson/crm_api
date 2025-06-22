from rest_framework import serializers
from .models import JobApplication
from talent_engine.models import JobRequisition
import logging
from django.conf import settings
from django.utils import timezone
import os
import uuid


logger = logging.getLogger('job_applications')

class DocumentSerializer(serializers.Serializer):
    document_type = serializers.CharField(max_length=50)
    file = serializers.FileField(write_only=True)
    file_url = serializers.SerializerMethodField(read_only=True)
    uploaded_at = serializers.DateTimeField(read_only=True, default=timezone.now)

    def get_file_url(self, obj):
        file_path = obj.get('file_path', None)
        if file_path:
            return f"{settings.MEDIA_URL}{file_path}"
        return None

    def validate_file(self, value):
        # Allow PDF and Word documents
        allowed_types = [
            'application/pdf',
            'application/msword',  # .doc
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'  # .docx
        ]
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                f"Invalid file type: {value.content_type}. Only PDF and Word (.doc, .docx) files are allowed."
            )
        # Enforce file size limit (e.g., 50 MB)
        max_size = 50 * 1024 * 1024  # 50 MB in bytes
        if value.size > max_size:
            raise serializers.ValidationError(f"File size exceeds 50 MB limit.")
        return value

    def validate_document_type(self, value):
        if value == 'resume':  # Always allow resume
            return value

        job_requisition = self.context.get('job_requisition')
        if not job_requisition:
            raise serializers.ValidationError("Job requisition context is missing.")
        
        documents_required = job_requisition.documents_required or []
        if documents_required and value not in documents_required:
            raise serializers.ValidationError(
                f"Invalid document type: {value}. Must be one of {documents_required}."
            )
        return value

class JobApplicationSerializer(serializers.ModelSerializer):
    documents = DocumentSerializer(many=True, required=False)
    job_requisition_id = serializers.CharField(source='job_requisition.id', read_only=True)
    tenant_schema = serializers.CharField(source='tenant.schema_name', read_only=True)

    class Meta:
        model = JobApplication
        fields = [
            'id', 'tenant', 'tenant_schema', 'job_requisition', 'job_requisition_id',
            'full_name', 'email', 'phone', 'qualification', 'experience','screening_status', 'screening_score',
            'knowledge_skill', 'cover_letter', 'resume_status', 'status', 'source',
            'documents', 'applied_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant', 'tenant_schema', 'job_requisition_id', 'applied_at', 'created_at', 'updated_at']

    def validate(self, data):
        logger.debug(f"Validating data: {data}")
        job_requisition = data.get('job_requisition')
        if not job_requisition:
            raise serializers.ValidationError("Job requisition is required.")
        if not job_requisition.publish_status:
            raise serializers.ValidationError("This job is not published.")

        documents_required = job_requisition.documents_required or []
        documents_data = data.get('documents', [])
        logger.debug(f"Documents required: {documents_required}, Provided: {[doc['document_type'] for doc in documents_data]}")

        # Validate required documents
        if documents_required:
            provided_types = {doc['document_type'] for doc in documents_data}
            missing_docs = [doc for doc in documents_required if doc not in provided_types]
            if missing_docs:
                raise serializers.ValidationError(
                    f"Missing required documents: {', '.join(missing_docs)}."
                )

        return data

    def create(self, validated_data):
        documents_data = validated_data.pop('documents', [])
        tenant = self.context['request'].tenant
        validated_data['tenant'] = tenant
        logger.debug(f"Creating application for tenant: {tenant.schema_name}, job: {validated_data['job_requisition'].title}")

        # Process documents
        documents = []
        for doc_data in documents_data:
            file = doc_data['file']
            # Generate file path
            # Generate file path
            folder_path = f"application_documents/{timezone.now().strftime('%Y/%m/%d')}"
            os.makedirs(folder_path, exist_ok=True)  # ✅ Create directories if not exist

            upload_path = os.path.join(
                folder_path, f"{uuid.uuid4()}{os.path.splitext(file.name)[1]}"
            ).replace("\\", "/")  # Normalize to forward slashes

            # Save file to storage
            # with open(upload_path, 'wb+') as destination:
            #     for chunk in file.chunks():
            #         destination.write(chunk)
            try:
                with open(upload_path, 'wb+') as destination:
                    for chunk in file.chunks():
                        destination.write(chunk)
            except Exception as e:
                logger.error(f"Failed to save file {upload_path}: {str(e)}")
                raise serializers.ValidationError(f"Failed to save file: {str(e)}")

                    
            documents.append({
                'document_type': doc_data['document_type'],
                'file_path': upload_path,
                'uploaded_at': timezone.now().isoformat()
            })

        validated_data['documents'] = documents
        application = JobApplication.objects.create(**validated_data)
        logger.info(f"Application created: {application.id} for {application.full_name}")
        return application

    def get_fields(self):
        fields = super().get_fields()
        if 'documents' in fields:
            fields['documents'].child.context.update({'job_requisition': self.context.get('job_requisition')})
        return fields