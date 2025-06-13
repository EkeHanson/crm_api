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
tenant = Tenant.objects.get(schema_name='abraham_ekene_onwon')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        username='admin',
        email='admin@ekeneonwon.com',
        password='qwerty',
        role='admin',
        tenant=tenant
    )

# python manage.py makemigrations  
# python manage.py migrate_schemas --shared  

from core.models import Tenant
from talent_engine.models import Subscription
tenant = Tenant.objects.get(schema_name='proliance')
Subscription.objects.create(tenant=tenant, module='recruitment', is_active=True)


# python manage.py showmigrations talent_engine
# python manage.py makemigrations talent_engine
# python manage.py migrate_schemas --shared
# python manage.py migrate_schemas


from core.models import Tenant
from subscriptions.models import Subscription
tenant = Tenant.objects.get(schema_name='abraham_ekene_onwon')
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
        print(tables)  # Should return [('talent_engine_job_requisition',)] if exists