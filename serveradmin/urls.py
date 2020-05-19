"""Serveradmin

Copyright (c) 2020 InnoGames GmbH
"""

from importlib.util import find_spec

from django.apps import apps
from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.models import update_last_login
from django.contrib.auth.signals import user_logged_in
from django.contrib.auth.views import logout_then_login
from django.shortcuts import redirect

user_logged_in.disconnect(update_last_login)

admin.autodiscover()

urlpatterns = [
    url(r'^$', lambda req: redirect('servershell_index'), name='home'),
    url(r'^logout', logout_then_login, name='logout'),
    url(r'^admin/', admin.site.urls),
]

for app in apps.get_app_configs():
    name = app.name
    module_spec = find_spec(name + '.urls')
    if module_spec is not None:
        module = module_spec.loader.load_module()

    if name.startswith('serveradmin.') or name.startswith('serveradmin_'):
        urlpatterns.append(url(
            r'^{}/'.format(name[(len('serveradmin') + 1):]), include(module)
        ))
    elif name == 'igrestlogin':
        urlpatterns.append(url(r'^loginapi/', include(module)))

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
