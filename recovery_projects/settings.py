from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'dev-secret-key'
DEBUG = True
ALLOWED_HOSTS = ['*']

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'dashboard',

]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

ROOT_URLCONF = 'recovery_projects.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [ BASE_DIR / 'dashboard' / 'templates' ],
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

WSGI_APPLICATION = 'recovery_projects.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'recovery_db',
        'USER': 'postgres',
        'PASSWORD': 'L0V35L30NA4EVER',
        'HOST': 'db',
        'PORT': '5432',
    }
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Pacific/Efate'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [ BASE_DIR / 'dashboard' / 'static' ]
STATIC_ROOT = BASE_DIR / "staticfiles"  # <-- required for collectstatic

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Authentication redirects
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "recovery_project_create"
LOGOUT_REDIRECT_URL = "login"
