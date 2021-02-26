"""Serveradmin

Copyright (c) 2019 InnoGames GmbH
"""

import dateparser
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse

from serveradmin.serverdb.models import (
    ChangeAdd,
    ChangeCommit,
    ChangeDelete,
    ChangeUpdate,
    Server,
    ServertypeAttribute,
)
from serveradmin.serverdb.query_committer import CommitError, commit_query


@login_required
def changes(request):
    context = dict()
    column_filter = dict()
    q_filter = list()
    t_from = request.GET.get('from', '1 year ago')
    t_until = request.GET.get('until')
    hostname = request.GET.get('hostname')
    application = request.GET.get('application')
    date_settings = {'TIMEZONE': settings.TIME_ZONE}

    try:
        if hostname:
            object_id = Server.objects.get(hostname=hostname).server_id
        else:
            object_id = request.GET.get('object_id')
    except ObjectDoesNotExist:
        messages.error(request, 'Server does not exist')
        return TemplateResponse(request, 'serverdb/changes.html', {})

    if t_from:
        column_filter['change_on__gt'] = dateparser.parse(
            t_from,
            settings=date_settings,
        )
        context['from_understood'] = column_filter['change_on__gt']
    if t_until:
        column_filter['change_on__lt'] = dateparser.parse(
            t_until,
            settings=date_settings,
        )
        context['until_understood'] = column_filter['change_on__lt']
    if object_id:
        q_filter.append((
            Q(changeupdate__server_id=object_id) |
            Q(changedelete__server_id=object_id) |
            Q(changeadd__server_id=object_id)
        ))
    if application:
        q_filter.append((
            Q(app__name=application) | Q(user__username=application)
        ))

    commits = ChangeCommit.objects.filter(
        *q_filter,
        **column_filter,
    ).order_by('-change_on')
    paginator = Paginator(commits, 20)

    try:
        page = paginator.page(request.GET.get('page', 1))
    except (PageNotAnInteger, EmptyPage):
        page = paginator.page(1)

    context.update({
        'commits': page,
        'from': t_from,
        'until': t_until,
        'hostname': hostname,
        'object_id': object_id,
        'application': application,
    })
    return TemplateResponse(request, 'serverdb/changes.html', context)


@login_required
def history(request):
    object_id = request.GET.get('object_id')
    commit_id = request.GET.get('commit_id')
    search_string = request.GET.get('search_string')

    if not object_id:
        raise Http404

    # TODO: Change data model so that server_id is moved to ChangeCommit.
    #       To me this would make most sense. If that is not possible (why?!)
    #       write a proper (custom) query that performs.
    where = {'server_id': object_id}
    adds = ChangeAdd.objects.filter(**where)
    updates = ChangeUpdate.objects.filter(**where)
    deletes = ChangeDelete.objects.filter(**where)

    # @TODO Transform to PostgreSQL JSON and put a index here
    if search_string:
        adds = adds.filter(attributes_json__contains=search_string)
        updates = updates.filter(updates_json__contains=search_string)
        deletes = deletes.filter(attributes_json__contains=search_string)

    if commit_id:
        adds = adds.filter(commit__pk=commit_id)
        updates = updates.filter(commit__pk=commit_id)
        deletes = deletes.filter(commit__pk=commit_id)

    related = ('commit__app', 'commit__user')
    adds = adds.select_related(*related)
    updates = updates.select_related(*related)
    deletes = deletes.select_related(*related)

    change_list = ([('add', obj) for obj in adds] +
                   [('update', obj) for obj in updates] +
                   [('delete', obj) for obj in deletes])
    change_list.sort(key=lambda entry: entry[1].commit.change_on, reverse=True)

    server = Server.objects.filter(server_id=object_id)
    return TemplateResponse(request, 'serverdb/history.html', {
        'change_list': change_list,
        'commit_id': commit_id,
        'object_id': object_id,
        'name': server.get if server.exists() else object_id,
        'is_ajax': request.is_ajax(),
        'base_template': 'empty.html' if request.is_ajax() else 'base.html',
        'link': request.get_full_path(),
        'search_string': search_string,
    })


@login_required
def restore_deleted(request, change_commit_id):
    object_id = request.POST.get('object_id')
    deleted = get_object_or_404(
        ChangeDelete,
        server_id=object_id,
        commit__pk=change_commit_id,
    )

    server_obj = deleted.attributes

    # Remove consistent_via_attribute values they are implicit
    consistent_attribute_ids = ServertypeAttribute.objects.filter(
        servertype_id=server_obj['servertype']).exclude(
        consistent_via_attribute_id=None)
    for attribute in consistent_attribute_ids:
        server_obj.pop(attribute.attribute_id)

    try:
        commit = commit_query([server_obj], user=request.user)
        object_id = str(commit.created[0]['object_id'])
    except CommitError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, 'Restored object with new id ' + object_id)

    return redirect(reverse('serverdb_history') + '?object_id=' + object_id)
