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
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse

from serveradmin.serverdb.models import (
    ChangeCommit,
    ChangeDelete,
    Server,
    ServertypeAttribute, Change,
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
    date_settings = {
        'TIMEZONE': settings.TIME_ZONE,
        'RETURN_AS_TIMEZONE_AWARE': True,
    }

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

    if not Server.objects.filter(server_id=object_id).exists():
        messages.error(
            request,
            f'Object with id {object_id} does not or no longer exist.')
        return redirect(reverse('serverdb_changes'))

    server = get_object_or_404(Server, server_id=object_id)
    obj_history = Change.objects.filter(object_id=object_id)

    commit_id = request.GET.get('commit_id')
    if commit_id:
        obj_history = obj_history.filter(commit_id=commit_id)

    attribute_filter = request.GET.get('attribute_filter')
    if attribute_filter:
        obj_history = obj_history.filter(change_json__has_key=attribute_filter)

    obj_history = obj_history.order_by('-commit_id')
    obj_history = obj_history.select_related('commit__app', 'commit__user')

    page = request.GET.get('page', 1)
    pager = Paginator(obj_history, 25)
    page_obj = pager.get_page(page)

    return TemplateResponse(request, 'serverdb/history.html', {
        'changes': page_obj,
        'commit_id': commit_id,
        'object_id': object_id,
        'name': server.hostname,
        'attribute_filter': attribute_filter,
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
