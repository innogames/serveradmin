"""Serveradmin

Copyright (c) 2020 InnoGames GmbH
"""

from importlib.util import find_spec

from django.apps import apps
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.models import update_last_login
from django.contrib.auth.signals import user_logged_in
from django.contrib.auth.views import logout_then_login
from django.shortcuts import redirect
from django.urls import path, include

user_logged_in.disconnect(update_last_login)

admin.autodiscover()

urlpatterns = [
    path('', lambda req: redirect('servershell_index'), name='home'),
    path('logout', logout_then_login, name='logout'),
    path('admin/', admin.site.urls),
]

for app in apps.get_app_configs():
    name = app.name
    module_spec = find_spec(name + '.urls')
    if module_spec is None:
        continue

    module = module_spec.loader.load_module()

    if name.startswith('serveradmin.') or name.startswith('serveradmin_'):
        url_path = name[(len('serveradmin') + 1):]
        urlpatterns.append(path('{}/'.format(url_path), include(module)))
    elif name == 'igrestlogin':
        urlpatterns.append(path('loginapi/', include(module)))

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
