from django.conf.urls import patterns, url

urlpatterns = patterns(
    'serveradmin.servershell.views',
    url(r'^$', 'index', name='servershell_index'),
    url(r'^autocomplete$', 'autocomplete', name='servershell_autocomplete'),
    url(r'^results$', 'get_results', name='servershell_results'),
    url(r'^export$', 'export', name='servershell_export'),
    url(r'^edit$', 'list_and_edit', {'mode': 'edit'}, name='servershell_edit'),
    url(r'^list$', 'list_and_edit', {'mode': 'list'}, name='servershell_list'),
    url(r'^commit$', 'commit', name='servershell_commit'),
    url(r'^values$', 'get_values', name='servershell_values'),
    url(r'^new$', 'new_server', name='servershell_new'),
    url(
        r'^choose_ip_addr$',
        'choose_ip_addr',
        name='servershell_choose_ip_addr',
    ),
    url(r'^store_command$', 'store_command', name='servershell_store_command'),
)
