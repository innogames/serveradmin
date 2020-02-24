"""Serveradmin

Copyright (c) 2019 InnoGames GmbH
"""

import dateparser

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse

from serveradmin.serverdb.models import (
    ChangeCommit,
    ChangeAdd,
    ChangeUpdate,
    ChangeDelete,
    Server)
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
        object_id = request.GET.get('object_id') if not hostname else Server.objects.get(hostname=hostname).server_id
    except ObjectDoesNotExist:
        messages.error(request, 'Server does not exist')
        return TemplateResponse(request, 'serverdb/changes.html', {})

    if t_from:
        column_filter['change_on__gt'] = dateparser.parse(t_from, settings=date_settings)
        context['from_understood'] = column_filter['change_on__gt']
    if t_until:
        column_filter['change_on__lt'] = dateparser.parse(t_until, settings=date_settings)
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

    commits = ChangeCommit.objects.filter(*q_filter, **column_filter).order_by('-change_on')
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
    server_id = request.GET.get('server_id')
    if not server_id:
        raise Http404

    try:
        commit_id = int(request.GET['commit'])
    except (KeyError, ValueError):
        commit_id = None

    adds = ChangeAdd.objects.filter(server_id=server_id).select_related()
    updates = ChangeUpdate.objects.filter(server_id=server_id).select_related()
    deletes = ChangeDelete.objects.filter(server_id=server_id).select_related()

    if commit_id:
        adds = adds.filter(commit__pk=commit_id)
        updates = updates.filter(commit__pk=commit_id)
        deletes = deletes.filter(commit__pk=commit_id)

    change_list = ([('add', obj) for obj in adds] +
                   [('update', obj) for obj in updates] +
                   [('delete', obj) for obj in deletes])
    change_list.sort(key=lambda entry: entry[1].commit.change_on, reverse=True)

    for change in change_list:
        commit = change[1].commit
        if commit.user:
            commit.commit_by = commit.user.get_full_name()
        elif commit.app:
            commit.commit_by = commit.app.name
        else:
            commit.commit_by = 'unknown'

    return TemplateResponse(request, 'serverdb/history.html', {
        'change_list': change_list,
        'commit_id': commit_id,
        'server_id': server_id,
        'is_ajax': request.is_ajax(),
        'base_template': 'empty.html' if request.is_ajax() else 'base.html',
        'link': request.get_full_path()
    })


@login_required
def restore_deleted(request, change_commit):
    deleted = get_object_or_404(
        ChangeDelete,
        server_id=request.POST.get('server_id'),
        commit__pk=change_commit,
    )

    server_obj = deleted.attributes
    try:
        commit_query([server_obj], user=request.user)
    except CommitError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, 'Server restored.')

    return redirect(
        reverse('serverdb_history') +
        '?server_id=' + str(server_obj['object_id'])
    )
