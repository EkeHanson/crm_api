# Generated by Django 5.2.2 on 2025-06-30 14:50

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0003_tenant_default_from_email_tenant_email_host_and_more'),
        ('talent_engine', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='jobrequisition',
            name='requested_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='talent_requisitions', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='jobrequisition',
            name='tenant',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='talent_requisitions', to='core.tenant'),
        ),
    ]
