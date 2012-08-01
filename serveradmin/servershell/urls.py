from django.conf.urls import patterns, url

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns(
    'serveradmin.servershell.views',
    url(r'^$', 'index', name='servershell_index'),
    url(r'^autocomplete$', 'autocomplete', name='servershell_autocomplete'),
    url(r'^results$', 'get_results', name='servershell_results'),
    url(r'^export$', 'export', name='servershell_export'),
    url(r'^edit$', 'list_and_edit', name='servershell_edit'),
    url(r'^list$', 'list_and_edit', name='servershell_list'),
)
