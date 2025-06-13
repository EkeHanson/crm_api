# apps/talent_engine/models.py
from django.db import models
from django.db.models import Max
from users.models import CustomUser
from core.models import Tenant

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

    id = models.CharField(primary_key=True, max_length=10, editable=False, unique=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='talent_requisitions')
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    requested_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='talent_requisitions')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    qualification_requirement = models.TextField()
    experience_requirement = models.TextField()
    knowledge_requirement = models.TextField()
    reason = models.TextField()
    requested_date = models.DateField(auto_now_add=True)
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
        
        super().save(*args, **kwargs)
