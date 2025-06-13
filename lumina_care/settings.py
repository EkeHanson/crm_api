from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-!v)6(7@u983fg+8gdo1o)dr^59vvp3^ol*apr%c+$0n$#swz-1'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'cmvp-api-v1.onrender.com']


INSTALLED_APPS = [
    'corsheaders',
    'django_tenants',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',  # Required for allauth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.apple',
    'allauth.socialaccount.providers.microsoft',
    'django_filters',
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'viewflow.fsm',
    'auditlog',
    'core',
    'users',
    'talent_engine',
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
    'allauth.account.middleware.AccountMiddleware', 
]

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
)

SITE_ID = 1  # Required for django.contrib.sites

# allauth settings
ACCOUNT_LOGIN_METHODS = {'email': True}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'optional'
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

# Social providers configuration (example, configure later)
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    },
    'apple': {
        'APP': {
            'client_id': 'your.apple.client.id',
            'secret': 'your.apple.key.id',
            'key': 'your.apple.team.id',
            'certificate_key': '''-----BEGIN PRIVATE KEY-----
            YOUR_PRIVATE_KEY
            -----END PRIVATE KEY-----'''
        }
    },
    'microsoft': {
        'APP': {
            'client_id': 'your.microsoft.client.id',
            'secret': 'your.microsoft.client.secret',
            'tenant': 'common',  # For multi-tenant Azure AD
        },
        'SCOPE': ['User.Read', 'email'],
    }
}

# Update CORS for OAuth redirects
CORS_ALLOWED_ORIGINS = [
    'http://app.mydomain.com',
    'https://crm-frontend-react.vercel.app',
    'http://localhost:5173',
    'https://accounts.google.com',
    'https://appleid.apple.com',
    'https://login.microsoftonline.com',
]
CORS_ALLOW_CREDENTIALS = True

# Allow credentials (e.g., cookies, Authorization headers)
CORS_ALLOW_CREDENTIALS = True

ROOT_URLCONF = 'lumina_care.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'lumina_care.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

# DATABASES = {
#     'default': {
#         'ENGINE': 'django_tenants.postgresql_backend',
#         'NAME': 'lumina_care_db',
#         'USER': 'postgres',
#         'PASSWORD': 'qwerty',
#         'HOST': 'localhost',
#         'PORT': '5432',
#     }
# }


# DATABASES = {
#     'default': {
#         'ENGINE': 'django_tenants.postgresql_backend',
#         'NAME': 'railway',  # Corrected from 'railwa'
#         'USER': 'postgres',
#         'PASSWORD': 'ZnrmyuFkqrjnBVNqNwxJQEhyCheQQPFN',
#         'HOST': 'shinkansen.proxy.rlwy.net',
#         'PORT': '53839',
#         'CONN_MAX_AGE': 300,
#         'OPTIONS': {
#             'sslmode': 'require',
#             'connect_timeout': 15,
#         }
#     }
# }

DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': 'free_crm_db',
        'USER': 'free_crm_db_user',
        'PASSWORD': 'bYJ7EVs2icOwSEq4vD8CYK0prkxzlJaa',
        'HOST': 'dpg-d1617gvdiees73ek2n7g-a.oregon-postgres.render.com',
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
    'users',  # Ensure 'users' is in SHARED_APPS
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
    'compliance',
    'training',
    'care_coordination',
    'workforce',
    'analytics',
    'integrations',
]
AUTH_USER_MODEL = 'users.CustomUser'


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# lumina_care/settings.py
# Update REST_FRAMEWORK for allauth
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'allauth.account.auth_backends.AuthenticationBackend',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}


from datetime import timedelta
SOCIALACCOUNT_ADAPTER = 'users.adapters.CustomSocialAccountAdapter'

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'AUTH_HEADER_TYPES': ('Bearer',),
    'TOKEN_OBTAIN_SERIALIZER': 'lumina_care.views.CustomTokenSerializer',
}

# Add Logging: Add logging to track migration issues:
# lumina_care/settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'core': {'handlers': ['console'], 'level': 'INFO'},
        'users': {'handlers': ['console'], 'level': 'INFO'},
        'talent_engine': {'handlers': ['console'], 'level': 'INFO'},  # Added
        'subscriptions': {'handlers': ['console'], 'level': 'INFO'},  # Added
        'django.db.migrations': {'handlers': ['console'], 'level': 'DEBUG'},
    },
}