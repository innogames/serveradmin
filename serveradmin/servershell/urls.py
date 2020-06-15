"""Serveradmin - Servershell

Copyright (c) 2020 InnoGames GmbH
"""

from django.urls import path

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
    settings,
)


urlpatterns = [
    path('', index, name='servershell_index'),
    path('autocomplete', autocomplete, name='servershell_autocomplete'),
    path('results', get_results, name='servershell_results'),
    path('export', export, name='servershell_export'), # TODO remove
    path('edit', edit, name='servershell_edit'),
    path('inspect', inspect, name='servershell_inspect'),
    path('commit', commit, name='servershell_commit'),
    path('new', new_object, name='servershell_new'),
    path('clone', clone_object, name='servershell_clone'),
    path('choose_ip_addr', choose_ip_addr, name='servershell_choose_ip_addr'),
    path('settings', settings, name='servershell_save_settings'),
]
