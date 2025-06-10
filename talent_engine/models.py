# apps/talent_engine/models.py
from django.db import models
from users.models import CustomUser
from core.models import Tenant

class JobPosting(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Candidate(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE)
    cv_data = models.JSONField()  # Store parsed CV data
    ai_score = models.FloatField(null=True)  # AI-generated score
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)