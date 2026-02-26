import os, sys
# ensure project root is on sys.path
proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, proj_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.dev')
import django
django.setup()
from django.template.loader import get_template
try:
    tpl = get_template('accounts/login.html')
    print('found', tpl)
except Exception as e:
    print('error', e)
