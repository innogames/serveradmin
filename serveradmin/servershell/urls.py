from django.conf.urls import patterns, url

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns(
    'serveradmin.servershell.views',
    url(r'^$', 'index', name='servershell_index'),
    url(r'^autocomplete$', 'autocomplete', name='servershell_autocomplete'),
    url(r'^results$', 'get_results', name='servershell_results'),
)
