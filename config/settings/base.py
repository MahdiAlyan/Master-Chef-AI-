"""
Django settings for ai_recipe_hub project.
"""

import os
import dj_database_url
import environ
from pathlib import Path
import sys

# --------------------------------------------------
# Base directory
# --------------------------------------------------
# Point at project root (one level above config package)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --------------------------------------------------
# Environment
# --------------------------------------------------
env = environ.Env(DEBUG=(bool, False))

if os.path.exists(BASE_DIR / ".env"):
    environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

if not SECRET_KEY and not DEBUG:
    raise RuntimeError("SECRET_KEY is required when DEBUG is False")

# --------------------------------------------------
# Applications
# --------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'recipes',
    'services',
]

# --------------------------------------------------
# Middleware
# --------------------------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

# --------------------------------------------------
# Templates
# --------------------------------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
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

WSGI_APPLICATION = 'config.wsgi.application'

# --------------------------------------------------
# Database
# --------------------------------------------------
DATABASE_URL = env("DATABASE_URL", default="")

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

if DATABASE_URL:
    try:
        parsed_db = dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=False)
        if parsed_db.get("ENGINE") == "django.db.backends.sqlite3":
            db_name = str(parsed_db.get("NAME", "")).strip()
            if db_name and not os.path.isabs(db_name):
                parsed_db["NAME"] = str((BASE_DIR / db_name).resolve())
        DATABASES = {"default": parsed_db}
    except Exception as e:
        print(f"[ai_recipe_hub] Invalid DATABASE_URL, falling back to SQLite: {e}", file=sys.stderr)

# --------------------------------------------------
# Auth validators
# --------------------------------------------------
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

# --------------------------------------------------
# Internationalization
# --------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = env("TIME_ZONE", default="UTC")
USE_I18N = True
USE_TZ = True
# --------------------------------------------------
# Static & media
# --------------------------------------------------
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# --------------------------------------------------
# Defaults
# --------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "recipes:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "master-ai-chef-cache",
    }
}
