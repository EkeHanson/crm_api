from django.db import models
from django.db.models import Max
from django.utils.text import slugify
from users.models import CustomUser
from core.models import Tenant, Branch
from django.utils import timezone
import uuid
import logging
from django.core.exceptions import ValidationError

logger = logging.getLogger('talent_engine')

def validate_compliance_checklist(value):
    if not isinstance(value, list):
        raise ValidationError("Compliance checklist must be a list.")
    for item in value:
        if not isinstance(item, dict) or 'name' not in item:
            raise ValidationError("Each compliance item must be a dictionary with a 'name' field.")

class ActiveRequisitionsManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class JobRequisition(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('pending', 'Pending'),
        ('closed', 'Closed'),
        ('rejected', 'Rejected'),
    ]
    ROLE_CHOICES = [
        ('staff', 'Staff'),
        ('admin', 'Admin'),
    ]
    JOB_TYPE_CHOICES = [
        ('full_time', 'Full-time'),
        ('part_time', 'Part-time'),
        ('contract', 'Contract'),
        ('freelance', 'Freelance'),
        ('internship', 'Internship'),
    ]
    LOCATION_TYPE_CHOICES = [
        ('on_site', 'On-site'),
        ('remote', 'Remote'),
        ('hybrid', 'Hybrid'),
    ]

    id = models.CharField(primary_key=True, max_length=20, editable=False, unique=True)
    job_requisition_code = models.CharField(max_length=50, unique=True, blank=True, null=True)
    job_application_code = models.CharField(max_length=50, unique=True, blank=True, null=True)
    compliance_checklist = models.JSONField(default=list, blank=True, validators=[validate_compliance_checklist])
    last_compliance_check = models.DateTimeField(null=True, blank=True)
    checked_by = models.CharField(max_length=255, null=True, blank=True)
    num_of_applications = models.IntegerField(default=0, help_text="Number of successful (hired) applications")
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='talent_requisitions')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=255)
    unique_link = models.CharField(max_length=255, unique=True, blank=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='rejected')
    requested_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='talent_requisitions')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    company_name = models.CharField(max_length=255, blank=True, null=True)
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, default='full_time')
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPE_CHOICES, default='on_site')
    company_address = models.TextField(blank=True, null=True)
    job_location = models.TextField(blank=True, null=True)
    interview_location = models.CharField(max_length=255, blank=True)
    salary_range = models.CharField(max_length=100, blank=True, null=True)
    job_description = models.TextField(blank=True, null=True)
    number_of_candidates = models.IntegerField(blank=True, null=True)
    qualification_requirement = models.TextField(blank=True, null=True)
    experience_requirement = models.TextField(blank=True, null=True)
    knowledge_requirement = models.TextField(blank=True, null=True)
    reason = models.TextField(blank=True, null=True)
    deadline_date = models.DateField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    responsibilities = models.JSONField(default=list, blank=True)
    documents_required = models.JSONField(default=list, blank=True)
    advert_banner = models.ImageField(upload_to='advert_banners/', blank=True, null=True)
    requested_date = models.DateField(auto_now_add=True)
    publish_status = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    active_objects = ActiveRequisitionsManager()

    class Meta:
        db_table = 'talent_engine_job_requisition'

    def __str__(self):
        return f"{self.title} ({self.tenant.schema_name})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        if not self.id:
            prefix = self.tenant.name[:3].upper()
            latest = JobRequisition.objects.filter(id__startswith=prefix).aggregate(Max('id'))['id__max']
            number = int(latest.split('-')[1]) + 1 if latest else 1
            self.id = f"{prefix}-{number:04d}"

        if not self.unique_link:
            base_slug = slugify(f"{self.title}")
            short_uuid = str(uuid.uuid4())[:8]
            slug = f"{self.tenant.schema_name}-{base_slug}-{short_uuid}"
            counter = 1
            original_slug = slug
            while JobRequisition.objects.filter(unique_link=slug).exists():
                slug = f"{original_slug}-{counter}"
                counter += 1
            self.unique_link = slug

        if not self.job_requisition_code:
            code_prefix = self.tenant.name[:2].upper()
            latest_code = JobRequisition.objects.filter(job_requisition_code__startswith=f"{code_prefix}-JR-").order_by('-job_requisition_code').first()
            new_number = int(latest_code.job_requisition_code.split('-')[-1]) + 1 if latest_code and latest_code.job_requisition_code else 1
            self.job_requisition_code = f"{code_prefix}-JR-{new_number:04d}"

        if not self.job_application_code:
            code_prefix = self.tenant.name[:2].upper()
            latest_app_code = JobRequisition.objects.filter(job_application_code__startswith=f"{code_prefix}-JA-").order_by('-job_application_code').first()
            new_number = int(latest_app_code.job_application_code.split('-')[-1]) + 1 if latest_app_code and latest_app_code.job_application_code else 1
            self.job_application_code = f"{code_prefix}-JA-{new_number:04d}"

        super().save(*args, **kwargs)

    def soft_delete(self):
        self.is_deleted = True
        self.save()
        logger.info(f"JobRequisition {self.id} soft-deleted for tenant {self.tenant.schema_name}")

    def restore(self):
        self.is_deleted = False
        self.save()
        logger.info(f"JobRequisition {self.id} restored for tenant {self.tenant.schema_name}")

    def add_compliance_item(self, name, description='', required=True, status='pending', checked_by=None, checked_at=None):
        new_item = {
            'id': str(uuid.uuid4()),
            'name': name,
            'description': description,
            'required': required,
            'status': status,
            'checked_by': checked_by,
            'checked_at': checked_at
        }
        self.compliance_checklist.append(new_item)
        self.last_compliance_check = checked_at or self.last_compliance_check
        self.checked_by = checked_by or self.checked_by
        self.save()
        return new_item

    def update_compliance_item(self, item_id, **kwargs):
        for item in self.compliance_checklist:
            if item["id"] == item_id:
                item.update(kwargs)
                if 'status' in kwargs and kwargs['status'] in ['completed', 'failed']:
                    item['checked_at'] = kwargs.get('checked_at', timezone.now().isoformat())
                    item['checked_by'] = kwargs.get('checked_by', item.get('checked_by'))
                    self.last_compliance_check = item['checked_at']
                    self.checked_by = item['checked_by']
                self.save()
                logger.info(f"Updated compliance item {item_id} for requisition {self.id}")
                return item
        logger.warning(f"Compliance item {item_id} not found in requisition {self.id}")
        raise ValueError("Compliance item not found")

    def remove_compliance_item(self, item_id):
        original_length = len(self.compliance_checklist)
        self.compliance_checklist = [item for item in self.compliance_checklist if item["id"] != item_id]
        if len(self.compliance_checklist) < original_length:
            self.save()
            logger.info(f"Removed compliance item {item_id} from requisition {self.id}")
        else:
            logger.warning(f"Compliance item {item_id} not found in requisition {self.id}")
            raise ValueError("Compliance item not found")