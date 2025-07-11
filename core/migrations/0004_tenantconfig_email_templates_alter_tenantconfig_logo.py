# Generated by Django 5.2.2 on 2025-07-10 08:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_tenant_default_from_email_tenant_email_host_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenantconfig',
            name='email_templates',
            field=models.JSONField(default=dict),
        ),
        migrations.AlterField(
            model_name='tenantconfig',
            name='logo',
            field=models.ImageField(blank=True, null=True, upload_to='tenant_logos/'),
        ),
    ]
