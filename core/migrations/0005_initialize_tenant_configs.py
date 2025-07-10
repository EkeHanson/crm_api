# apps/core/migrations/0004_initialize_tenant_configs.py
from django.db import migrations
from django_tenants.utils import tenant_context

def create_tenant_configs(apps, schema_editor):
    Tenant = apps.get_model('core', 'Tenant')
    TenantConfig = apps.get_model('core', 'TenantConfig')
    
    # Default email templates
    default_templates = {
        'interviewScheduling': {
            'content': (
                'Hello [Candidate Name],\n\n'
                'We’re pleased to invite you to an interview for the [Position] role at [Company].\n'
                'Please let us know your availability so we can confirm a convenient time.\n\n'
                'Best regards,\n[Your Name]'
            ),
            'is_auto_sent': False
        },
        'interviewRescheduling': {
            'content': (
                'Hello [Candidate Name],\n\n'
                'Due to unforeseen circumstances, we need to reschedule your interview originally set for [Old Date/Time]. '
                'Kindly share a few alternative slots that work for you.\n\n'
                'Thanks for your understanding,\n[Your Name]'
            ),
            'is_auto_sent': False
        },
        'interviewRejection': {
            'content': (
                'Hello [Candidate Name],\n\n'
                'Thank you for taking the time to interview. After careful consideration, '
                'we have decided not to move forward.\n\n'
                'Best wishes,\n[Your Name]'
            ),
            'is_auto_sent': False
        },
        'interviewAcceptance': {
            'content': (
                'Hello [Candidate Name],\n\n'
                'Congratulations! We are moving you to the next stage. We’ll follow up with next steps.\n\n'
                'Looking forward,\n[Your Name]'
            ),
            'is_auto_sent': False
        },
        'jobRejection': {
            'content': (
                'Hello [Candidate Name],\n\n'
                'Thank you for applying. Unfortunately, we’ve chosen another candidate at this time.\n\n'
                'Kind regards,\n[Your Name]'
            ),
            'is_auto_sent': False
        },
        'jobAcceptance': {
            'content': (
                'Hello [Candidate Name],\n\n'
                'We’re excited to offer you the [Position] role at [Company]! '
                'Please find the offer letter attached.\n\n'
                'Welcome aboard!\n[Your Name]'
            ),
            'is_auto_sent': False
        }
    }

    for tenant in Tenant.objects.all():
        with tenant_context(tenant):
            if not TenantConfig.objects.filter(tenant=tenant).exists():
                TenantConfig.objects.create(
                    tenant=tenant,
                    email_templates=default_templates
                )
                print(f"Created TenantConfig for tenant {tenant.schema_name}")
            else:
                config = TenantConfig.objects.get(tenant=tenant)
                if not config.email_templates:  # Populate empty email_templates
                    config.email_templates = default_templates
                    config.save()
                    print(f"Populated email_templates for tenant {tenant.schema_name}")

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0003_tenant_default_from_email_tenant_email_host_and_more'),
    ]

    operations = [
        migrations.RunPython(create_tenant_configs),
    ]