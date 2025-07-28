# CRM API

A multi-tenant CRM backend built with Django, Django REST Framework, and django-tenants.

---

## Features

- Multi-tenancy: Each tenant has its own schema and domains.
- Modular apps: users, job applications, talent engine, subscriptions, etc.
- JWT authentication.
- RESTful API endpoints for all core modules.
- Tenant/domain management via API and Django shell.

---

## Project Structure

- `core/` – Tenant and domain models, APIs.
- `users/` – Custom user model and user APIs.
- `talent_engine/` – Job requisition and video session APIs.
- `job_application/` – Job application APIs.
- `subscriptions/` – Subscription APIs.
- `lumina_care/` – Main Django project settings and URLs.

---

## Setup Instructions

### 1. Clone and Install

```sh
git clone <your-repo-url>
cd crm_api
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Database Setup

Database configuration is hardcoded in `lumina_care/settings.py`:
Create a postgres database and update these values in the `lumina_care/settings.py`

- Name: `db_name`
- User: `db_user`
- Password: `db_password`
- Host: `localhost`
- Port: `5432`

Ensure PostgreSQL is running and the database exists:

### 4. Migrations

Apply migrations for all apps and schemas:

```sh
python manage.py makemigrations users talent_engine subscriptions job_application core
python manage.py migrate_schemas --shared
python manage.py migrate_schemas
python manage.py showmigrations talent_engine
```

---

## Multi-Tenancy: Creating Tenants and Domains

Open the Django shell:

```sh
python manage.py shell
```

Create a tenant and domains:
Navigate to the zzzzz.py file and run these scripts in your python shell

## Creates a Public Tenant Table

```python
from core.models import Tenant, Domain
if not Tenant.objects.filter(schema_name='public').exists():
    tenant = Tenant.objects.create(
        name='public',
        schema_name='public'
    )
    tenant.auto_create_schema = False
    tenant.save()
    tenant.create_schema()  # Creates the schema in the DB
    Domain.objects.create(tenant=tenant, domain='127.0.0.1', is_primary=True)
    Domain.objects.create(tenant=tenant, domain='localhost', is_primary=False)
```

---

## Creates a Company Tenant Table

```python
from core.models import Tenant, Domain
if not Tenant.objects.filter(schema_name='company_name').exists():
    tenant = Tenant.objects.create(
        name='company_name',
        schema_name='company_name'
    )
    tenant.auto_create_schema = False
    tenant.save()
    tenant.create_schema()  # Creates the schema in the DB
    Domain.objects.create(tenant=tenant, domain='www.company_domain.com', is_primary=True)
```

---

## Creating Superusers for a Tenant

```python
from core.models import Tenant
from users.models import CustomUser
from django_tenants.utils import tenant_context

tenant = Tenant.objects.get(schema_name='company_name')
with tenant_context(tenant):
    CustomUser.objects.create_superuser(
        username='',
        email='',
        password='',
        role='admin',
        first_name='',
        last_name='',
        job_role='Product Manager',
        tenant=tenant
    )
```

---

## Running the Server

```sh
python manage.py runserver
```

---

## API Endpoints

### Authentication

- `POST /api/token/` – Obtain JWT token
- `POST /api/token/refresh/` – Refresh JWT token

### Tenants

- `GET /api/tenant/tenants/` – List tenants
- `POST /api/tenant/tenants/` – Create tenant
- `DELETE /api/tenant/tenants/<tenant_id>/` – Delete tenant

### Users

- `GET /api/user/users/` – List users
- `POST /api/user/create/` – Create user

### Talent Engine

- `GET /api/talent-engine/video-sessions/` – List video sessions
- `POST /api/talent-engine/requisitions/` – Create job requisition

### Job Applications

- `GET /api/talent-engine-job-applications/applications/` – List job applications

### Subscriptions

- `GET /api/subscriptions/` – List subscriptions

### API Docs

- `GET /api/docs/` – Swagger UI

---

## Management Commands

- Show migrations:  
  `python manage.py showmigrations <app_name>`
- Open Django shell:  
  `python manage.py shell`
- Create superuser for tenant:  
  See shell code above.

---

## Notes

- Tenant and domain records are stored in the `public` schema.
- Each tenant has its own schema for app data.
- Always call `tenant.create_schema()` after creating a tenant.
- Use the correct domain when accessing tenant-specific endpoints.

---

## Troubleshooting

- If you don’t see changes in the database, check your `.env` and database connection.
- For multi-line code in the shell, press `Enter` twice after pasting.
- For static files warning, create the missing `static` directory.

---

## License

MIT

---
