from .base import *

DEBUG = False

ALLOWED_HOSTS = ["masterchefai.pythonanywhere.com"]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')