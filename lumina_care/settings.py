# lumina_care/settings.py
# -----------------------------------------------------------
# Django settings for Lumina Care CRM (multi-tenant, JWT)
# -----------------------------------------------------------

from pathlib import Path
from datetime import timedelta
import os
import sys
import environ
from logging.handlers import RotatingFileHandler

# -----------------------------------------------------------
# BASE PATHS & ENV
# -----------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / 'talent_engine'))

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))  # load .env

# -----------------------------------------------------------
# CORE SECURITY
# -----------------------------------------------------------
SECRET_KEY = env('DJANGO_SECRET_KEY', default='your-default-secret-key')
DEBUG = env('DEBUG', default=False)
ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=[])
FRONTEND_URL = env('FRONTEND_URL', default='http://localhost:5173')

# -----------------------------------------------------------
# APPLICATIONS
# -----------------------------------------------------------
INSTALLED_APPS = [
    'corsheaders',
    'django_tenants',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django_crontab',
    'django_filters',
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'viewflow.fsm',
    'auditlog',
    'channels',

    # Local apps
    'core',
    'users',
    'talent_engine',
    'job_application',
    'compliance',
    'training',
    'care_coordination',
    'workforce',
    'analytics',
    'integrations',
    'subscriptions',
]

# -----------------------------------------------------------
# MIDDLEWARE
# -----------------------------------------------------------
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'lumina_care.middleware.CustomTenantMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
]

AUTH_USER_MODEL = 'users.CustomUser'

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)


ASGI_APPLICATION = 'lumina_care.asgi.application'
# -----------------------------------------------------------
# SOCIAL PROVIDERS
# -----------------------------------------------------------
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    },
    'apple': {
        'APP': {
            'client_id': env('APPLE_CLIENT_ID', default=''),
            'secret': env('APPLE_KEY_ID', default=''),
            'key': env('APPLE_TEAM_ID', default=''),
            'certificate_key': env('APPLE_CERTIFICATE_KEY', default=''),
        }
    },
    'microsoft': {
        'APP': {
            'client_id': env('MICROSOFT_CLIENT_ID', default=''),
            'secret': env('MICROSOFT_CLIENT_SECRET', default=''),
            'tenant': 'common',
        },
        'SCOPE': ['User.Read', 'email'],
    }
}

# -----------------------------------------------------------
# DATABASE & TENANCY
# -----------------------------------------------------------
DATABASES = {
    'default': {
        **env.db('DATABASE_URL'),
        'ENGINE': 'django_tenants.postgresql_backend',
    }
}

# # VPS HOSTING
# DATABASES = {
#     'default': {
#         'ENGINE': 'django_tenants.postgresql_backend',
#         'NAME': config('DB_NAME', default='lumina_care_db'),
#         'USER': config('DB_USER', default='postgres'),
#         'PASSWORD': config('DB_PASSWORD', default='qwerty'),
#         'HOST': config('DB_HOST', default='localhost'),
#         'PORT': config('DB_PORT', default='5432'),
#         'CONN_MAX_AGE': 60,
#     }
# }

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql_backend',
#         'NAME': 'lumina_care_db',
#         'USER': 'lumina_care_db_user',
#         'PASSWORD': 'pzU2xz56HOYwWc0I18',
#         'HOST': '127.0.0.1',
#         'PORT': '5432',
#     }
# }


ROOT_URLCONF = 'lumina_care.urls'
WSGI_APPLICATION = 'lumina_care.wsgi.application'


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter']
TENANT_MODEL = "core.Tenant"
TENANT_DOMAIN_MODEL = "core.Domain"

SHARED_APPS = [
    'django_tenants',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.sites',
    'core',
    'users',
    'subscriptions',
]

TENANT_APPS = [
    'django.contrib.admin',
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'viewflow.fsm',
    'auditlog',
    'talent_engine',
    'job_application',
    'compliance',
    'training',
    'care_coordination',
    'workforce',
    'analytics',
    'integrations',
]

# -----------------------------------------------------------
# CORS
# -----------------------------------------------------------

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    'https://crm-frontend-react.vercel.app', # add your production frontend later
]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']
CORS_ALLOW_HEADERS = [
    'accept', 'authorization', 'content-type', 'origin', 'x-csrftoken', 'x-requested-with'
]

# -----------------------------------------------------------
# REST FRAMEWORK
# -----------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.JSONParser',
    ],
}

# -----------------------------------------------------------
# SIMPLE JWT
# -----------------------------------------------------------
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=120),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'AUTH_HEADER_TYPES': ('Bearer',),
    'TOKEN_OBTAIN_SERIALIZER': 'lumina_care.views.CustomTokenSerializer',
    'BLACKLIST_AFTER_ROTATION': True,
}

# -----------------------------------------------------------
# EMAIL
# -----------------------------------------------------------
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = env('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
EMAIL_DEBUG = env('EMAIL_DEBUG', default=False, cast=bool)

# -----------------------------------------------------------
# SUPABASE
# -----------------------------------------------------------
SUPABASE_URL = env('SUPABASE_URL', default='')
SUPABASE_KEY = env('SUPABASE_KEY', default='')
SUPABASE_BUCKET = env('SUPABASE_BUCKET', default='')

# -----------------------------------------------------------
# STATIC & MEDIA
# -----------------------------------------------------------
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# -----------------------------------------------------------
# LOGGING
# -----------------------------------------------------------
LOG_DIR = '/tmp/logs' if os.getenv('RENDER') else os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '{asctime} [{levelname}] {name}: {message}', 'style': '{'},
        'simple': {'format': '[{levelname}] {message}', 'style': '{'},
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'lumina_care.log'),
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'},
    },
    'loggers': {
        'django': {'handlers': ['file', 'console'], 'level': 'INFO', 'propagate': True},
        'core': {'handlers': ['file'], 'level': 'INFO', 'propagate': False},
        'users': {'handlers': ['file'], 'level': 'INFO', 'propagate': False},
        'talent_engine': {'handlers': ['file'], 'level': 'INFO', 'propagate': False},
        'job_application': {'handlers': ['file'], 'level': 'INFO', 'propagate': False},
        'subscriptions': {'handlers': ['file'], 'level': 'INFO', 'propagate': False},
    }
}

# -----------------------------------------------------------
# CRON JOBS
# -----------------------------------------------------------
CRONTAB_COMMAND_PREFIX = ''
CRONTAB_DJANGO_PROJECT_NAME = 'lumina_care'
CRONJOBS = [
    ('0 11 * * *', 'talent_engine.cron.close_expired_requisitions',
     f'>> {os.path.join(LOG_DIR, "lumina_care.log")} 2>&1'),
]

# -----------------------------------------------------------
# INTERNATIONALIZATION
# -----------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


WEB_PAGE_URL="https://crm-frontend-react.vercel.app"



CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}