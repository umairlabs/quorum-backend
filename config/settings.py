import os
import logging
from pathlib import Path
from datetime import timedelta
import dotenv
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file if present
dotenv.load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = ['*']
CSRF_TRUSTED_ORIGINS = [
    'https://web-production-60035.up.railway.app',
    'https://quorum-frontend-drab.vercel.app',
]
# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third Party Apps
    'rest_framework',
    'corsheaders',
    'apps.purchases',

    # Project Apps
    'apps.authentication',
    'apps.dashboard',
    'apps.users',
    'apps.assets',
    'apps.maintenance',
    'apps.depreciation',
    'apps.audit',
    'apps.ai',
    'apps.notifications',
    'apps.reports',
    'apps.common',
    'apps.company_settings',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Password validation
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
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Karachi'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Media files (uploaded logos, etc.)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

from corsheaders.defaults import default_headers, default_methods


CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]


AUTH_USER_MODEL = 'users.User'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ---------------------------------------------------------------------------
# AI Configuration (OpenRouter)
# ---------------------------------------------------------------------------
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')


# ---------------------------------------------------------------------------
# Firebase Admin SDK Setup (for Push Notifications)
# ---------------------------------------------------------------------------
# Firebase setup is now optional and configured via environment variables
# To enable Firebase notifications:
# 1. Set FIREBASE_CREDENTIALS_PATH environment variable to path of service-account.json
# 2. The service-account.json should NOT be committed to version control
# 3. Store credentials securely in your deployment environment (CI/CD secrets, K8s secrets, etc.)

FIREBASE_CREDENTIALS_PATH = os.environ.get('FIREBASE_CREDENTIALS_PATH')

try:
    if FIREBASE_CREDENTIALS_PATH:
        import firebase_admin  # type: ignore
        from firebase_admin import credentials  # type: ignore

        cred_path = Path(FIREBASE_CREDENTIALS_PATH)
        if cred_path.exists():
            try:
                firebase_admin.get_app()
            except ValueError:
                cred = credentials.Certificate(str(cred_path))
                firebase_admin.initialize_app(cred)
        else:
            print(f"Warning: Firebase credentials file not found at {cred_path}")
except ImportError:
    print("Warning: firebase_admin not installed. Push notifications will be disabled.")
except Exception as e:
    print(f"Warning: Firebase Admin SDK initialization failed: {e}")

# OpenRouter AI Configuration
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')
OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'
OPENROUTER_MODEL = 'openai/gpt-4o-mini'


# ---------------------------------------------------------------------------
# Logging Configuration (Suppresses repetitive unread-count polling logs)
# ---------------------------------------------------------------------------
class SuppressUnreadCountFilter(logging.Filter):
    def filter(self, record):
        try:
            msg = record.getMessage()
            if '/api/notifications/unread-count/' in msg:
                return False
        except Exception:
            pass
        return True


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'suppress_unread_count': {
            '()': SuppressUnreadCountFilter,
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'filters': ['suppress_unread_count'],
        },
    },
    'loggers': {
        'django.server': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
