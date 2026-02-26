from .base import *

# Development configuration
# -------------------------
# Override defaults from base where appropriate

DEBUG = env.bool("DEBUG", True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Send email to console in development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
