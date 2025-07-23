# python manage.py showmigrations talent_engine
# python manage.py makemigrations users talent_engine subscriptions job_application core
# python manage.py migrate_schemas --shared
# python manage.py migrate_schemas

#python manage.py shell
from core.models import Tenant, Domain
if not Tenant.objects.filter(schema_name='public').exists():
    tenant = Tenant.objects.create(
        name='public',
        schema_name='public'
    )
    tenant.auto_create_schema = False
    tenant.save()
    Domain.objects.create(tenant=tenant, domain='127.0.0.1', is_primary=True)
    Domain.objects.create(tenant=tenant, domain='localhost', is_primary=False)
    
# python manage.py shell
from core.models import Tenant
from users.models import CustomUser
from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='proliance')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        username='ugochukwu',
        email='tonna.ezugwu@prolianceltd.com',
        password='qwerty',
        role='admin',
        first_name='Tonna',
        last_name='ChristEzugwuopher',
        job_role='A/QC',
        tenant=tenant
    )

from core.models import Tenant
from users.models import CustomUser
from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='proliance')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        username='info',
        email='info@prolianceltd.com',
        password='qwerty',
        role='admin',
        first_name='Gauis',
        last_name='Immanuel',
        job_role='Care Cordinator',
        tenant=tenant
    )
from core.models import Tenant
from users.models import CustomUser
from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='proliance')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        username='admin',
        email='admin@prolianceltd.com',
        password='qwerty',
        
        role='admin',
        first_name='Gauis',
        last_name='Immanuel',
        job_role='Care Cordinator',
        tenant=tenant
    )


from core.models import Tenant
from subscriptions.models import Subscription
tenant = Tenant.objects.get(schema_name='proliance')
Subscription.objects.create(tenant=tenant, module='talent_engine', is_active=True)

