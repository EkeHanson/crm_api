

from django.db import models
from django.utils.text import slugify
from core.models import Tenant
from talent_engine.models import JobRequisition
import uuid
from django.db.models import JSONField

class JobApplication(models.Model):
    STATUS_CHOICES = [
        ('new', 'New'),
        ('shortlisted', 'Shortlisted'),
        ('rejected', 'Rejected'),
        ('hired', 'Hired'),
    ]

    id = models.CharField(max_length=10, primary_key=True, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='job_applications')
    job_requisition = models.ForeignKey(JobRequisition, on_delete=models.CASCADE, related_name='applications')
    full_name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)
    phone = models.CharField(max_length=20)
    qualification = models.TextField(max_length=255)
    experience = models.TextField(max_length=255)
    knowledge_skill = models.TextField(blank=True, null=True)
    cover_letter = models.TextField(blank=True, null=True)
    resume_status = models.BooleanField(default=True)  # True if resume uploaded, False if "noresume"
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    source = models.CharField(max_length=50, blank=True, null=True, default='Website')  # e.g., Website, LinkedIn, Referral
    documents = JSONField(default=list, blank=True)  # Stores list of documents: [{"document_type": str, "file_path": str, "uploaded_at": datetime}, ...]
    applied_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'job_applications_job_application'
        unique_together = ('tenant', 'job_requisition', 'email')  # Ensure one application per email per job

    def __str__(self):
        return f"{self.full_name} - {self.job_requisition.title} ({self.tenant.name})"

    # def save(self, *args, **kwargs):
    #     # Check if the status is changing to 'hired'
    #     is_hired = self.status == 'hired'
    #     was_hired = False
    #     if self.pk:  # If the instance already exists, check the previous status
    #         previous = JobApplication.objects.get(pk=self.pk)
    #         was_hired = previous.status == 'hired'

    #     # Existing ID generation logic
    #     if not self.id:
    #         prefix = self.tenant.name[:3].upper()
    #         latest = JobApplication.objects.filter(id__startswith=prefix).aggregate(models.Max('id'))['id__max']
    #         if latest:
    #             try:
    #                 number = int(latest.split('-')[1]) + 1
    #             except (IndexError, ValueError):
    #                 number = 1
    #         else:
    #             number = 1
    #         self.id = f"{prefix}-{number:04d}"

    #     super().save(*args, **kwargs)  # Save the application first

    #     # Update num_of_applications in JobRequisition
    #     if is_hired and not was_hired:
    #         # Increment if newly hired
    #         self.job_requisition.num_of_applications += 1
    #         self.job_requisition.save()
    #     elif was_hired and not is_hired:
    #         # Decrement if status changed from hired to something else
    #         self.job_requisition.num_of_applications = max(0, self.job_requisition.num_of_applications - 1)
    #         self.job_requisition.save()
    def save(self, *args, **kwargs):
        # Check if this is a new application
        is_new = not self.pk

        # Existing ID generation logic
        if not self.id:
            prefix = self.tenant.name[:3].upper()
            latest = JobApplication.objects.filter(id__startswith=prefix).aggregate(models.Max('id'))['id__max']
            if latest:
                try:
                    number = int(latest.split('-')[1]) + 1
                except (IndexError, ValueError):
                    number = 1
            else:
                number = 1
            self.id = f"{prefix}-{number:04d}"

        super().save(*args, **kwargs)  # Save the application first

        # Update num_of_applications in JobRequisition for new applications
        if is_new:
            self.job_requisition.num_of_applications += 1
            self.job_requisition.save()