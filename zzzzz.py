# python manage.py showmigrations talent_engine
# python manage.py makemigrations users talent_engine subscriptions job_application 
# python manage.py migrate_schemas --shared
# python manage.py migrate_schemas

#python manage.py shell
from core.models import Tenant, Domain
if not Tenant.objects.filter(schema_name='harvoxtech').exists():
    tenant = Tenant.objects.create(
        name='harvoxtech',
        schema_name='harvoxtech'
    )
    tenant.auto_create_schema = False
    tenant.save()
    Domain.objects.create(tenant=tenant, domain='harvoxtech.com', is_primary=True)
    Domain.objects.create(tenant=tenant, domain='localhost', is_primary=False)


#CREATE TENANT ADMIN USER 
# python manage.py shell
from core.models import Tenant
from users.models import CustomUser
from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='arts')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        username='admin',
        email='admin@artstraining.co.uk',
        password='qwerty',
        
        role='admin',
        first_name='Ernest',
        last_name='Bush',
        job_role='Care Manager',
        tenant=tenant
    )




from core.models import Tenant
from subscriptions.models import Subscription
tenant = Tenant.objects.get(schema_name='harvoxtech')
Subscription.objects.create(tenant=tenant, module='talent_engine', is_active=True)

from django.db import connection
from django_tenants.utils import schema_context

schema_name = 'abraham_ekene_onwon'
with schema_context(schema_name):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
            AND table_name = 'talent_engine_job_requisition';
        """, [schema_name])
        tables = cursor.fetchall()
        print(tables)  