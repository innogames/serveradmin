from django.conf.urls import patterns, include, url
from django.shortcuts import redirect
from django.conf.urls.static import static
from django.conf import settings

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns(
    '',
    url(r'^$', lambda req: redirect('servershell_index'),  name='home'),
    url(r'^servershell/', include('serveradmin.servershell.urls')),
    url(r'^dataset/', include('serveradmin.dataset.urls')),
    url(r'^apps/', include('serveradmin.apps.urls')),
    url(r'^api/', include('serveradmin.api.urls')),
    url(r'^documentation/', include('serveradmin.docs.urls')),
    url(r'^servermonitor/', include('serveradmin.servermonitor.urls')),
    url(r'^iprange/', include('serveradmin.iprange.urls')),
    url(r'^loginapi/', include('igrestlogin.urls')),
    url(r'^logout', 'django.contrib.auth.views.logout_then_login',
        name='logout'),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^comments/', include('comments.urls')),
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
