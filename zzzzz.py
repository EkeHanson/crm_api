#python manage.py shell
from core.models import Tenant, Domain
if not Tenant.objects.filter(schema_name='public').exists():
    tenant = Tenant.objects.create(
        name='Public Tenant',
        schema_name='public'
    )
    tenant.auto_create_schema = False  # Set attribute after creation
    tenant.save()
    Domain.objects.create(tenant=tenant, domain='127.0.0.1', is_primary=True)
    Domain.objects.create(tenant=tenant, domain='localhost', is_primary=False)


#CREATE TENANT ADMIN USER 
# python manage.py shell
from core.models import Tenant
from users.models import CustomUser
from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='test_tenant')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        username='tenantadmin',
        email='admin@ekenehanson.com',
        password='qwerty',
        role='admin',
        tenant=tenant
    )

