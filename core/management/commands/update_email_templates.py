from django.core.management.base import BaseCommand
from django_tenants.utils import get_tenant_model, tenant_context
from core.models import TenantConfig
import logging

logger = logging.getLogger('core')

class Command(BaseCommand):
    help = 'Add passwordReset email template to existing TenantConfig records'

    def handle(self, *args, **options):
        # Define the passwordReset template
        password_reset_template = {
            'passwordReset': {
                'content': (
                    'Hello [User Name],\n\n'
                    'You have requested to reset your password for [Company]. '
                    'Please use the following link to reset your password:\n\n'
                    '[Reset Link]\n\n'
                    'This link will expire in 1 hour.\n\n'
                    'Best regards,\n[Your Name]'
                ),
                'is_auto_sent': True
            }
        }

        # Get all tenants
        Tenant = get_tenant_model()
        tenants = Tenant.objects.all()

        for tenant in tenants:
            try:
                with tenant_context(tenant):
                    try:
                        config = TenantConfig.objects.get(tenant=tenant)
                        current_templates = config.email_templates or {}
                        
                        # Check if passwordReset template already exists
                        if 'passwordReset' not in current_templates:
                            # Update email_templates with the new passwordReset template
                            current_templates.update(password_reset_template)
                            config.email_templates = current_templates
                            config.save()
                            logger.info(f"Updated TenantConfig for tenant {tenant.schema_name} with passwordReset template")
                        else:
                            logger.info(f"passwordReset template already exists for tenant {tenant.schema_name}")
                    except TenantConfig.DoesNotExist:
                        # Create new TenantConfig if it doesn't exist
                        config = TenantConfig.objects.create(
                            tenant=tenant,
                            email_templates=password_reset_template
                        )
                        logger.info(f"Created new TenantConfig for tenant {tenant.schema_name} with passwordReset template")
            except Exception as e:
                logger.error(f"Failed to update TenantConfig for tenant {tenant.schema_name}: {str(e)}")
                self.stderr.write(f"Error updating tenant {tenant.schema_name}: {str(e)}")

        self.stdout.write(self.style.SUCCESS("Successfully updated all TenantConfig records with passwordReset template"))