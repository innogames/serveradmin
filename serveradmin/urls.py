from django.conf.urls import patterns, include, url
from django.shortcuts import redirect

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns(
    '',
    url(r'^$', lambda req: redirect('api_list_functions'),  name='home'),
    url(r'^servershell/', include('serveradmin.servershell.urls')),
    url(r'^api/', include('serveradmin.api.urls')),
    url(r'^loginapi/', include('igrestlogin.urls')),
    url(r'^logout', 'django.contrib.auth.views.logout_then_login',
        name='logout'),
    url(r'^admin/', include(admin.site.urls)),
)
