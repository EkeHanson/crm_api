from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

class CustomUser(AbstractUser):
    ROLES = (
        ('admin', 'Admin'),
        ('hr', 'HR'),
        ('carer', 'Carer'),
        ('client', 'Client'),
        ('family', 'Family'),
        ('auditor', 'Auditor'),
        ('tutor', 'Tutor'),
        ('assessor', 'Assessor'),
        ('iqa', 'IQA'),
        ('eqa', 'EQA'),
    )

    username = models.CharField(max_length=150, blank=True, null=True, unique=False)  # Optional username
    email = models.EmailField(_('email address'), unique=True)  # Required and unique

    role = models.CharField(max_length=20, choices=ROLES, default='carer')
    job_role = models.CharField(max_length=255, blank=True, null=True, default='staff')
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []      

    def __str__(self):
        return self.email

class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    modules = models.ManyToManyField('core.Module', blank=True)