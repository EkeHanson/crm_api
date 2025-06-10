# apps/care_coordination/models.py
from django.db import models
from users.models import CustomUser
from core.models import Tenant
from auditlog.registry import auditlog

class Shift(models.Model):
    STATE_SCHEDULED = 'scheduled'
    STATE_ACCEPTED = 'accepted'
    STATE_IN_PROGRESS = 'in_progress'
    STATE_COMPLETED = 'completed'
    STATE_MISSED = 'missed'
    STATE_REALLOCATED = 'reallocated'

    STATE_CHOICES = [
        (STATE_SCHEDULED, 'Scheduled'),
        (STATE_ACCEPTED, 'Accepted'),
        (STATE_IN_PROGRESS, 'In Progress'),
        (STATE_COMPLETED, 'Completed'),
        (STATE_MISSED, 'Missed'),
        (STATE_REALLOCATED, 'Reallocated'),
    ]

    state = models.CharField(max_length=20, choices=STATE_CHOICES, default=STATE_SCHEDULED)
    carer = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)

    def can_accept(self):
        return self.state == self.STATE_SCHEDULED

    def can_start(self):
        return self.state == self.STATE_ACCEPTED

    def accept(self):
        if self.can_accept():
            self.state = self.STATE_ACCEPTED
            self.save()
        else:
            raise ValueError("Cannot accept: shift is not in scheduled state.")

    def start(self):
        if self.can_start():
            self.state = self.STATE_IN_PROGRESS
            self.save()
        else:
            raise ValueError("Cannot start: shift is not in accepted state.")

class CareOutcome(models.Model):
    client = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    metric = models.CharField(max_length=100)  # e.g., 'mobility_improvement'
    value = models.FloatField()
    recorded_at = models.DateTimeField(auto_now_add=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)

# Register models with auditlog (only once)
auditlog.register(Shift)
auditlog.register(CareOutcome)