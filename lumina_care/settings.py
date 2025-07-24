
from pathlib import Path
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import timedelta
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / 'talent_engine'))

SECRET_KEY = config('SECRET_KEY', default='django-insecure-!v)6(7@u983fg+8gdo1o)dr^59vvp3^ol*apr%c+$0n$#swz-1')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='127.0.0.1,localhost,cmvp-api-v1.onrender.com,temp.artstraining.co.uk').split(',')

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
    # 'allauth',
    # 'allauth.account',
    # 'allauth.socialaccount',
    # 'allauth.socialaccount.providers.google',
    # 'allauth.socialaccount.providers.apple',
    # 'allauth.socialaccount.providers.microsoft',
    'django_crontab',
    'django_filters',
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'viewflow.fsm',
    'auditlog',
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
    # 'allauth.account.middleware.AccountMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
]

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    # 'allauth.account.auth_backends.AuthenticationBackend',
)


ACCOUNT_LOGIN_METHODS = {'email': True}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'optional'
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    },
    'apple': {
        'APP': {
            'client_id': config('APPLE_CLIENT_ID', default='your.apple.client.id'),
            'secret': config('APPLE_KEY_ID', default='your.apple.key.id'),
            'key': config('APPLE_TEAM_ID', default='your.apple.team.id'),
            'certificate_key': config('APPLE_CERTIFICATE_KEY', default=''),
        }
    },
    'microsoft': {
        'APP': {
            'client_id': config('MICROSOFT_CLIENT_ID', default='your.microsoft.client.id'),
            'secret': config('MICROSOFT_CLIENT_SECRET', default='your.microsoft.client.secret'),
            'tenant': 'common',
        },
        'SCOPE': ['User.Read', 'email'],
    }
}

CORS_ALLOWED_ORIGINS = [
    'https://crm-frontend-react.vercel.app',
    "https://cmvp-api-v1.onrender.com",
    'http://localhost:5173',
]

#CORS_ALLOW_ALL_ORIGINS = True


CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']
CORS_ALLOW_HEADERS = ['accept', 'authorization', 'content-type', 'origin', 'x-csrftoken', 'x-requested-with']

ROOT_URLCONF = 'lumina_care.urls'
WSGI_APPLICATION = 'lumina_care.wsgi.application'

#FOR HOSTING ON NAMECHEAP

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


DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': 'crm_database_l66m',
        'USER': 'crm_database_l66m_user',
        'PASSWORD': 'lSK570C0FzOFlKIDyECGG7rd2VU9YyTO',
        'HOST': 'dpg-d208jbje5dus73d4h87g-a.oregon-postgres.render.com',
        'PORT': '5432',
    }
}


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
AUTH_USER_MODEL = 'users.CustomUser'


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')  # Add this line
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        # 'allauth.account.auth_backends.AuthenticationBackend',
    ),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.JSONParser',
    ],
}

SOCIALACCOUNT_ADAPTER = 'users.adapters.CustomSocialAccountAdapter'
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=120),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'AUTH_HEADER_TYPES': ('Bearer',),
    'TOKEN_OBTAIN_SERIALIZER': 'lumina_care.views.CustomTokenSerializer',
    'BLACKLIST_AFTER_ROTATION': True,
}

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
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'},
    },
    'loggers': {
        'django': {'handlers': ['file', 'console'], 'level': 'INFO', 'propagate': True},
        'django.db.backends': {'handlers': ['file'], 'level': 'ERROR'},
        'core': {'handlers': ['file'], 'level': 'INFO', 'propagate': False},
        'users': {'handlers': ['file'], 'level': 'INFO', 'propagate': False},
        'talent_engine': {'handlers': ['file'], 'level': 'INFO', 'propagate': False},
        'job_application': {'handlers': ['file'], 'level': 'INFO', 'propagate': False},
        'subscriptions': {'handlers': ['file'], 'level': 'INFO', 'propagate': False},
    }
}

CRONTAB_COMMAND_PREFIX = ''
CRONTAB_DJANGO_PROJECT_NAME = 'lumina_care'
CRONJOBS = [
    ('0 11 * * *', 'talent_engine.cron.close_expired_requisitions', f'>> {os.path.join(LOG_DIR, "lumina_care.log")} 2>&1'),
]

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='ekenehanson@gmail.com')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='pduw cpmw dgoq adrp')
DEFAULT_FROM_EMAIL = config('EMAIL_HOST_USER', default='ekenehanson@gmail.com')
EMAIL_DEBUG = True

FILE_UPLOAD_MAX_MEMORY_SIZE = 3145728  # 3MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 3145728  # 3MB

WEB_PAGE_URL = 'https://crm-frontend-react.vercel.app'
#WEB_PAGE_URL = 'http://localhost:5173'


SUPABASE_URL="https://gkvgqvosnetifsonhxuo.supabase.co"
SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imdrdmdxdm9zbmV0aWZzb25oeHVvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTI2NTU0OTcsImV4cCI6MjA2ODIzMTQ5N30.foh7w4Ko-wGwMc9GW7ZX2YswK8d4J51wel532mjPTfw"
SUPABASE_BUCKET="luminacaremedia"
