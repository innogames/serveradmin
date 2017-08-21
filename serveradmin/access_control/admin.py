from django.contrib.admin import site

from serveradmin.access_control.models import AccessControlGroup


site.register(AccessControlGroup)
