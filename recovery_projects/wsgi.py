import os
from django.core.wsgi import get_wsgi_application

#os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'recovery_site.settings')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'recovery_projects.settings')

application = get_wsgi_application()
