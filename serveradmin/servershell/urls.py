"""Serveradmin - Servershell

Copyright (c) 2020 InnoGames GmbH
"""

from django.urls import path
from django.views.generic.base import TemplateView

from serveradmin.servershell.views import (
    index,
    autocomplete,
    get_results,
    edit,
    inspect,
    commit,
    new_object,
    clone_object,
    choose_ip_address,
    settings,
    diff,
    attribute_selection,
)


urlpatterns = [
    path('', index, name='servershell_index'),
    path('autocomplete', autocomplete, name='servershell_autocomplete'),
    path('results', get_results, name='servershell_results'),
    path('edit', edit, name='servershell_edit'),
    path('inspect', inspect, name='servershell_inspect'),
    path('commit', commit, name='servershell_commit'),
    path('new', new_object, name='servershell_new'),
    path('clone', clone_object, name='servershell_clone'),
    path('choose_ip_address', choose_ip_address, name='servershell_choose_ip_address'),
    path('settings', settings, name='servershell_save_settings'),
    path('diff', diff, name='servershell_diff'),
    path('selection', attribute_selection, name='servershell_attribute_selection'),
    path('opensearch.xml', TemplateView.as_view(template_name='servershell/opensearch.xml'), name='opensearch.xml'),
]
