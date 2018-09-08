"""Serveradmin

Copyright (c) 2018 InnoGames GmbH
"""

from importlib.util import find_spec

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
    url(r'^admin/', include(admin.site.urls)),
]

for app in settings.INSTALLED_APPS:
    module_spec = find_spec(app + '.urls')
    if module_spec is not None:
        module = module_spec.loader.load_module()

    if app.startswith('serveradmin.') or app.startswith('serveradmin_'):
        urlpatterns.append(url(
            r'^{}/'.format(app[(len('serveradmin') + 1):]), include(module)
        ))
    elif app == 'igrestlogin':
        urlpatterns.append(url(r'^loginapi/', include(module)))

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
