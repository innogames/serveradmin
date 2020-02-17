"""Serveradmin - Servershell

Copyright (c) 2019 InnoGames GmbH
"""

from django.conf.urls import url

from serveradmin.servershell.views import (
    index,
    autocomplete,
    get_results,
    export,
    edit,
    inspect,
    commit,
    new_object,
    clone_object,
    choose_ip_addr,
    store_command,
)


urlpatterns = [
    url(r'^$', index, name='servershell_index'),
    url(r'^autocomplete$', autocomplete, name='servershell_autocomplete'),
    url(r'^results$', get_results, name='servershell_results'),
    url(r'^export$', export, name='servershell_export'),
    url(r'^edit$', edit, name='servershell_edit'),
    url(r'^inspect$', inspect, name='servershell_inspect'),
    url(r'^commit$', commit, name='servershell_commit'),
    url(r'^new$', new_object, name='servershell_new'),
    url(r'^clone$', clone_object, name='servershell_clone'),
    url(
        r'^choose_ip_addr$',
        choose_ip_addr,
        name='servershell_choose_ip_addr',
    ),
    url(r'^store_command$', store_command, name='servershell_store_command'),
]
