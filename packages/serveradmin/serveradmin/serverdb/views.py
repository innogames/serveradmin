"""Serveradmin

Copyright (c) 2022 InnoGames GmbH
"""

import dateparser
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q, Subquery, OuterRef, Prefetch, CharField, QuerySet
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Coalesce, Cast
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.functional import cached_property

from serveradmin import settings
from serveradmin.serverdb.models import (
    ChangeCommit,
    Server,
    ServertypeAttribute,
    Change,
)
from serveradmin.serverdb.query_committer import CommitError, commit_query


def _parse_object_ids(values: list[str]) -> list[int]:
    """Parse object ids from (possibly comma separated) request values

    Invalid entries are silently ignored.
    """
    object_ids = []
    for value in values:
        for object_id in value.split(','):
            object_id = object_id.strip()
            if object_id.isdigit() and int(object_id) not in object_ids:
                object_ids.append(int(object_id))

    return object_ids


def _annotate_hostname(changes: QuerySet) -> QuerySet:
    """Annotate changes with the hostname of their object

    The hostname is fetched either from the server table or from the change
    entry where the object was deleted.
    """
    server_hostname = Server.objects.filter(
        server_id=OuterRef('object_id')).values('hostname')
    # Workaround: In previous versions of Serveradmin restoring objects with
    # the same id was possible, so we can end up with objects being deleted
    # multiple times. We only take the latest into account.
    change_hostname = Change.objects.filter(
        object_id=OuterRef('object_id'),
        change_type=Change.Type.DELETE).values('change_json').order_by('-id')[:1]

    return changes.annotate(hostname=Coalesce(
        Subquery(server_hostname),
        Cast(
            KeyTextTransform('hostname', Subquery(change_hostname)),
            output_field=CharField())
    ))


@login_required
def changes(request):
    commits = ChangeCommit.objects.all().order_by('-change_on')
    date_settings = {
        'TIMEZONE': settings.TIME_ZONE, 'RETURN_AS_TIMEZONE_AWARE': True
    }

    f_commit = request.GET.get('commit_id')
    if f_commit:
        commits = commits.filter(pk=f_commit)

    f_from = request.GET.get('from')
    if f_from:
        f_from = dateparser.parse(f_from, settings=date_settings)
        commits = commits.filter(change_on__gt=f_from)

    f_until = request.GET.get('until')
    if f_until:
        f_until = dateparser.parse(f_until, settings=date_settings)
        commits = commits.filter(change_on__lt=f_until)

    f_hostname = request.GET.get('hostname')
    if f_hostname:
        # Display all changes that have or had this hostname
        object_ids = set(Change.objects.filter(
            change_type__in=[Change.Type.CREATE, Change.Type.DELETE],
            change_json__hostname=f_hostname).values_list(
            'change_json__object_id', flat=True))
        commits = commits.filter(change__object_id__in=object_ids)

    f_object_ids = _parse_object_ids(request.GET.getlist('object_id'))
    f_object_id = ','.join(str(i) for i in f_object_ids)
    if f_object_ids:
        commits = commits.filter(
            change__object_id__in=f_object_ids).distinct()

    f_user_or_app = request.GET.get('user_or_app')
    if f_user_or_app:
        commits = commits.filter(
            Q(app__name=f_user_or_app) | Q(user__username=f_user_or_app))

    f_attribute = request.GET.get('attribute')
    if f_attribute:
        # Only allow attribute filter if another filter is set (not fully index)
        if f_hostname or f_object_id or f_user_or_app:
            commits = commits.filter(change__change_json__has_key=f_attribute)
        else:
            f_attribute = None

    commits = commits.select_related('app', 'user')
    commits = commits.prefetch_related(Prefetch(
        'change_set', queryset=_annotate_hostname(Change.objects.all())))

    class NoCountPaginator(Paginator):
        @cached_property
        def count(self):
            return 2**32

    paginator = NoCountPaginator(commits, 20)
    page = paginator.get_page(request.GET.get('page', 1))
    # Defaulting to first page when exceeding page range does not work here
    # because of the override count.
    if len(page.object_list) == 0:
        page = paginator.get_page(1)

    return TemplateResponse(request, 'serverdb/changes.html', {
        'commits': page,
        'from': f_from,
        'until': f_until,
        'hostname': f_hostname,
        'object_id': f_object_id,
        'commit_id': f_commit,
        'user_or_app': f_user_or_app,
        'attribute': f_attribute,
    })


@login_required
def history(request):
    object_ids = _parse_object_ids(request.GET.getlist('object_id'))
    hostnames = request.GET.getlist('hostname')
    if not object_ids and not hostnames:
        return HttpResponseBadRequest(
            'object_id or hostname parameter is mandatory')

    servers = list(Server.objects.filter(
        Q(server_id__in=object_ids) | Q(hostname__in=hostnames)
    ).order_by('hostname'))

    missing = [str(i) for i in object_ids
               if i not in {s.server_id for s in servers}]
    missing += [h for h in hostnames if h not in {s.hostname for s in servers}]
    if not servers:
        messages.error(
            request,
            f'Object(s) {", ".join(missing)} do not or no longer exist.')
        return redirect(reverse('serverdb_changes'))
    if missing:
        messages.warning(
            request,
            f'Object(s) {", ".join(missing)} do not or no longer exist.')

    server_ids = [s.server_id for s in servers]
    obj_history = Change.objects.filter(object_id__in=server_ids)

    commit_id = request.GET.get('commit_id')
    if commit_id:
        obj_history = obj_history.filter(commit_id=commit_id)

    attribute_filter = request.GET.get('attribute_filter')
    if attribute_filter:
        obj_history = obj_history.filter(change_json__has_key=attribute_filter)

    obj_history = obj_history.order_by('-commit_id', '-id')
    obj_history = obj_history.select_related('commit__app', 'commit__user')
    obj_history = _annotate_hostname(obj_history)

    page = request.GET.get('page', 1)
    pager = Paginator(obj_history, 25)
    page_obj = pager.get_page(page)

    no_history_attributes = ServertypeAttribute.objects.filter(
        servertype_id__in={s.servertype_id for s in servers},
        attribute__history=False,
    ).order_by('attribute_id').values_list(
        'attribute_id', flat=True).distinct()

    if len(servers) == 1:
        name = servers[0].hostname
    else:
        name = f'{len(servers)} objects'

    return TemplateResponse(request, 'serverdb/history.html', {
        'changes': page_obj,
        'commit_id': commit_id,
        'object_ids': server_ids,
        'object_ids_query': '&'.join(f'object_id={i}' for i in server_ids),
        'name': name,
        'hostnames': [s.hostname for s in servers],
        'attribute_filter': attribute_filter,
        'no_history_attributes': no_history_attributes,
    })


@login_required
def recreate(request, change_id):
    change = get_object_or_404(Change, pk=change_id)
    server_object = change.change_json

    # Remove related_via_attribute and "computed" attributes they are implicit
    # and have no values in the database.
    servertype_id = server_object['servertype']
    exclude = ServertypeAttribute.objects.filter(servertype_id=servertype_id)
    exclude = exclude.filter(
        ~Q(related_via_attribute=None) |
        Q(attribute__type__in=['supernet', 'domain', 'reverse'])
    ).values_list('attribute_id', flat=True)

    for attribute_id in exclude:
        if attribute_id in server_object:
            server_object.pop(attribute_id)

    try:
        changes_obj, _ = commit_query([server_object], user=request.user)
        object_id = str(changes_obj.created[0]['object_id'])
    except (CommitError, ValidationError) as error:
        messages.error(request, str(error))
        return redirect(reverse('serverdb_changes'))
    else:
        messages.success(request, f'Restored object with new id {object_id}')

    return redirect(reverse('serverdb_history') + '?object_id=' + object_id)
