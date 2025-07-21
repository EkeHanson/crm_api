# python manage.py showmigrations talent_engine
# python manage.py makemigrations users talent_engine subscriptions job_application 
# python manage.py migrate_schemas --shared
# python manage.py migrate_schemas

#python manage.py shell
from core.models import Tenant, Domain
if not Tenant.objects.filter(schema_name='getinride').exists():
    tenant = Tenant.objects.create(
        name='getinride',
        schema_name='getinride'
    )
    tenant.auto_create_schema = False
    tenant.save()
    Domain.objects.create(tenant=tenant, domain='getinride.com', is_primary=True)
    Domain.objects.create(tenant=tenant, domain='localhost', is_primary=False)


#CREATE TENANT ADMIN USER 
# python manage.py shell
from core.models import Tenant
from users.models import CustomUser
from django_tenants.utils import tenant_context
tenant = Tenant.objects.get(schema_name='getinride')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        username='support',
        email='support@getinride.com',
        password='qwerty',
        
        role='admin',
        first_name='Mature',
        last_name='Brainiac',
        job_role='Security Cordinator',
        tenant=tenant
    )


from core.models import Tenant
from subscriptions.models import Subscription
tenant = Tenant.objects.get(schema_name='getinride')
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