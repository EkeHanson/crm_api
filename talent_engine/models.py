from django.db import models
from django.db.models import Max
from django.utils.text import slugify
from users.models import CustomUser
from core.models import Tenant
import uuid

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

    id = models.CharField(primary_key=True, max_length=10, editable=False, unique=True)
    num_of_applications = models.IntegerField(default=0, help_text="Number of successful (hired) applications")
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='talent_requisitions')
    title = models.CharField(max_length=255)
    unique_link = models.CharField(max_length=255, unique=True, blank=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='rejected')
    requested_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='talent_requisitions')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    company_name = models.CharField(max_length=255, blank=True, null=True)
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, default='full_time')
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPE_CHOICES, default='on_site')
    company_address = models.TextField(blank=True, null=True)
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
    compliance_checklist = models.JSONField(default=list, blank=True)
    advert_banner = models.ImageField(upload_to='advert_banners/', blank=True, null=True)
    requested_date = models.DateField(auto_now_add=True)
    publish_status = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'talent_engine_job_requisition'

    def __str__(self):
        return f"{self.title} ({self.tenant.schema_name})"

    def save(self, *args, **kwargs):
        if not self.id:
            prefix = self.tenant.name[:3].upper()
            latest = JobRequisition.objects.filter(id__startswith=prefix).aggregate(Max('id'))['id__max']
            if latest:
                try:
                    number = int(latest.split('-')[1]) + 1
                except (IndexError, ValueError):
                    number = 1
            else:
                number = 1
            self.id = f"{prefix}-{number:04d}"

        if not self.unique_link:
            # Generate unique_link with tenant schema_name, job title, and UUID
            base_slug = slugify(f"{self.title}")
            short_uuid = str(uuid.uuid4())[:8]  # Use first 8 chars of UUID for uniqueness
            slug = f"{self.tenant.schema_name}-{base_slug}-{short_uuid}"
            # Ensure uniqueness (though UUID makes collisions unlikely)
            counter = 1
            original_slug = slug
            while JobRequisition.objects.filter(unique_link=slug).exists():
                slug = f"{original_slug}-{counter}"
                counter += 1
            self.unique_link = slug

        super().save(*args, **kwargs)