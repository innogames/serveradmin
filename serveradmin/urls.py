from django.conf import settings
from django.conf.urls import patterns, include, url
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.models import update_last_login
from django.contrib.auth.signals import user_logged_in
from django.shortcuts import redirect


user_logged_in.disconnect(update_last_login)

admin.autodiscover()

urlpatterns = patterns(
    '',
    url(r'^$', lambda req: redirect('servershell_index'),  name='home'),
    url(r'^servershell/', include('serveradmin.servershell.urls')),
    url(r'^serverdb/', include('serveradmin.serverdb.urls')),
    url(r'^apps/', include('serveradmin.apps.urls')),
    url(r'^api/', include('serveradmin.api.urls')),
    url(r'^documentation/', include('serveradmin.docs.urls')),
    url(r'^colocation/', include('serveradmin.colo.urls')),
    url(r'^loginapi/', include('igrestlogin.urls')),
    url(r'^logout', 'django.contrib.auth.views.logout_then_login',
        name='logout'),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^graphite/', include('serveradmin.graphite.urls')),
    url(r'^resources/', include('serveradmin.resources.urls')),
    url(r'^failoverlogin$', 'serveradmin.common.views.failoverlogin'),
    url(r'^check$', 'serveradmin.common.views.check'),
)

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
