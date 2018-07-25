"""Serveradmin - Servershell

Copyright (c) 2018 InnoGames GmbH
"""

try:
    import simplejson as json
except ImportError:
    import json
from operator import attrgetter
from itertools import islice

from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import (
    ObjectDoesNotExist, PermissionDenied, ValidationError
)
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.utils.html import mark_safe, escape as escape_html

from adminapi.datatype import DatatypeError
from adminapi.filters import Any, ContainedOnlyBy, StartsWith, filter_classes
from adminapi.parse import parse_query
from adminapi.request import json_encode_extra
from serveradmin.dataset import Query
from serveradmin.serverdb.models import (
    Servertype,
    Attribute,
    ServertypeAttribute,
    ServerStringAttribute,
)
from serveradmin.serverdb.query_committer import commit_query

MAX_DISTINGUISHED_VALUES = 50
NUM_SERVERS_DEFAULT = 100


@login_required
def index(request):
    attributes = list(Attribute.objects.all())
    attributes.extend(Attribute.specials.values())
    attribute_groups = {}
    for attribute in attributes:
        attribute_groups.setdefault(attribute.group, []).append(attribute)
    for attributes in attribute_groups.values():
        attributes.sort(key=attrgetter('attribute_id'))
    attribute_groups = sorted(attribute_groups.items(), key=lambda x: x[0])

    return TemplateResponse(request, 'servershell/index.html', {
        'checked_attributes': set(request.GET.get('attrs', '').split(',')),
        'attribute_groups': attribute_groups,
        'search_term': request.GET.get(
            'term', request.session.get('term', '')
        ),
        'per_page': request.session.get('per_page', NUM_SERVERS_DEFAULT),
        'command_history': json.dumps(
            request.session.get('command_history', [])
        ),
        'filters': [(f.__name__, f.__doc__) for f in filter_classes],
    })


@login_required
def autocomplete(request):
    autocomplete_list = []
    if 'hostname' in request.GET:
        hostname = request.GET['hostname']
        try:
            query = Query({'hostname': StartsWith(hostname)}, ['hostname'])
            autocomplete_list += islice((h['hostname'] for h in query), 100)
        except (DatatypeError, ValidationError):
            pass    # If there is no valid query, just don't auto-complete

    return HttpResponse(
        json.dumps({'autocomplete': autocomplete_list}),
        content_type='application/x-json',
    )


@login_required
def get_results(request):
    term = request.GET.get('term', '')
    shown_attributes = request.GET.get('shown_attributes').split(',')

    # We need servertypes to return the attribute properties.
    if 'servertype' not in shown_attributes:
        shown_attributes.append('servertype')

    try:
        offset = int(request.GET.get('offset', '0'))
        limit = int(request.GET.get('limit', '0'))
    except ValueError:
        offset = 0
        limit = NUM_SERVERS_DEFAULT

    if 'order_by' in request.GET:
        order_by = [request.GET['order_by']]
    else:
        order_by = None

    try:
        query = Query(parse_query(term), shown_attributes, order_by)
        num_servers = len(query)
    except (DatatypeError, ObjectDoesNotExist, ValidationError) as error:
        return HttpResponse(json.dumps({
            'status': 'error',
            'message': str(error)
        }))

    servers = list(islice(query, offset, offset + limit))

    request.session['term'] = term
    request.session['per_page'] = limit

    # Add information about available attributes on servertypes
    # It will be encoded as map avail[servertype][attr] = stypeattr
    specials = tuple(
        (a, {
            'regexp': None,
            'default': None,
        })
        for a in Attribute.specials.keys()
    )
    servertype_ids = {s['servertype'] for s in servers}
    editable_attributes = dict()
    for servertype_id in servertype_ids:
        editable_attributes[servertype_id] = dict(specials)
    for sa in ServertypeAttribute.objects.filter(
        servertype_id__in=servertype_ids,
        attribute_id__in=shown_attributes,
        related_via_attribute_id__isnull=True,
        attribute__readonly=False,
    ):
        editable_attributes[sa.servertype_id][sa.attribute_id] = {
            'regexp': sa.attribute.regexp,
            'default': sa.default_value,
        }

    return HttpResponse(json.dumps({
        'status': 'success',
        'understood': repr(query),
        'servers': servers,
        'num_servers': num_servers,
        'editable_attributes': editable_attributes,
    }, default=json_encode_extra), content_type='application/x-json')


@login_required
def export(request):
    term = request.GET.get('term', '')
    try:
        query = Query(parse_query(term), ['hostname'])
    except (DatatypeError, ObjectDoesNotExist, ValidationError) as error:
        return HttpResponse(str(error), status=400)

    hostnames = ' '.join(server['hostname'] for server in query)
    return HttpResponse(hostnames, content_type='text/plain')


@login_required
def inspect(request):
    server = Query({'object_id': request.GET['object_id']}, None).get()
    return _edit(request, server, template='inspect')


@login_required
def edit(request):
    if 'object_id' in request.GET:
        server = Query({'object_id': request.GET['object_id']}, None).get()
    else:
        server = Query().new_object(request.POST['attr_servertype'])

    return _edit(request, server, True)


def _edit(request, server, edit_mode=False, template='edit'):   # NOQA: C901
    invalid_attrs = set()
    if edit_mode and request.POST:
        attribute_lookup = {a.pk: a for a in Attribute.objects.filter(
            attribute_id__in=(k[len('attr_'):] for k in request.POST.keys())
        )}
        attribute_lookup.update(Attribute.specials)
        for key, value in request.POST.items():
            if not key.startswith('attr_'):
                continue
            attribute_id = key[len('attr_'):]
            attribute = attribute_lookup[attribute_id]
            value = value.strip()
            if attribute.multi:
                values = [v.strip() for v in value.splitlines()]
                try:
                    value = attribute.from_str(values)
                except ValidationError:
                    invalid_attrs.add(attribute_id)
                    value = set(values)
            elif value == '':
                value = None
            else:
                try:
                    value = attribute.from_str(value)
                except ValidationError:
                    invalid_attrs.add(attribute_id)

            server[attribute_id] = value

        if not invalid_attrs:
            if server.object_id:
                action = 'edited'
                created = []
                changed = [server._serialize_changes()]
            else:
                action = 'created'
                created = [server]
                changed = []

            try:
                commit_obj = commit_query(created, changed, user=request.user)
            except (PermissionDenied, ValidationError) as err:
                messages.error(request, str(err))
            else:
                messages.success(request, 'Server successfully ' + action)
                if action == 'created':
                    server = commit_obj.created[0]

                url = '{0}?object_id={1}'.format(
                    reverse('servershell_inspect'),
                    server.object_id,
                )
                return HttpResponseRedirect(url)

        if invalid_attrs:
            messages.error(request, 'Attributes contain invalid values')

    servertype = Servertype.objects.get(pk=server['servertype'])
    attribute_lookup = {a.pk: a for a in Attribute.objects.filter(
        attribute_id__in=(server.keys())
    )}
    attribute_lookup.update(Attribute.specials)
    servertype_attributes = {sa.attribute_id: sa for sa in (
        ServertypeAttribute.objects.filter(servertype_id=server['servertype'])
    )}

    fields = []
    fields_set = set()
    for key, value in server.items():
        if (
            key == 'object_id' or
            key == 'intern_ip' and servertype.ip_addr_type == 'null'
        ):
            continue

        attribute = attribute_lookup[key]
        servertype_attribute = servertype_attributes.get(key)
        if servertype_attribute and servertype_attribute.related_via_attribute:
            continue

        fields_set.add(key)
        fields.append({
            'key': key,
            'value': value,
            'type': attribute.type,
            'multi': attribute.multi,
            'required': (
                servertype_attribute and servertype_attribute.required or
                key in Attribute.specials.keys()
            ),
            'regexp_display': _prepare_regexp_html(
                attribute.regexp and '^' + attribute.regexp + '$'
            ),
            'regexp': (
                attribute.regexp and '^' + attribute.regexp + '$'
            ),
            'default': (
                servertype_attribute and servertype_attribute.default_value
            ),
            'readonly': attribute.readonly,
            'error': key in invalid_attrs,
        })

    fields.sort(key=lambda k: (not k['required'], k['key']))
    return TemplateResponse(request, 'servershell/{}.html'.format(template), {
        'object_id': server.object_id,
        'fields': fields,
        'is_ajax': request.is_ajax(),
        'base_template': 'empty.html' if request.is_ajax() else 'base.html',
        'link': request.get_full_path(),
    })


@login_required
def commit(request):
    try:
        commit_obj = json.loads(request.POST['commit'])
    except (KeyError, ValueError) as error:
        result = {
            'status': 'error',
            'message': str(error),
        }
    else:
        changed = []
        if 'changes' in commit_obj:
            for key, value in commit_obj['changes'].items():
                value['object_id'] = int(key)
                changed.append(value)

        deleted = commit_obj.get('deleted', [])
        user = request.user

        try:
            commit_query(changed=changed, deleted=deleted, user=user)
        except (PermissionDenied, ValidationError) as error:
            result = {
                'status': 'error',
                'message': str(error),
            }
        else:
            result = {'status': 'success'}

    return HttpResponse(json.dumps(result), content_type='application/x-json')


@login_required
def get_values(request):
    attribute = get_object_or_404(
        Attribute, attribute_id=request.GET['attribute']
    )
    queryset = ServerStringAttribute.objects.filter(attribute=attribute)
    value_queryset = queryset.values('value').distinct().order_by('value')

    return TemplateResponse(request, 'servershell/values.html', {
        'attribute': attribute,
        'values': (
            v['value'] for v in value_queryset[:MAX_DISTINGUISHED_VALUES]
        ),
        'num_values': MAX_DISTINGUISHED_VALUES
    })


@login_required
def new_object(request):
    try:
        servertype = request.GET.get('servertype')
        new_object = Query().new_object(servertype)
    except Servertype.DoesNotExist:
        raise Http404

    return _edit(request, new_object)


@login_required
def clone_object(request):
    try:
        old_object = Query(
            {'hostname': request.GET.get('hostname')},
            Attribute.objects.filter(clone=True)
        ).get()
    except ValidationError:
        raise Http404

    new_object = Query().new_object(old_object['servertype'])
    for attribute_id, value in old_object.items():
        new_object[attribute_id] = value

    return _edit(request, new_object)


@login_required
def choose_ip_addr(request):
    if 'network' not in request.GET:
        servers = list(Query(
            {'servertype': 'route_network'},
            ['hostname', 'intern_ip'],
            ['hostname'],
        ))

        return TemplateResponse(request, 'servershell/choose_ip_addr.html', {
            'servers': servers
        })

    network = request.GET['network']
    servers = list(Query(
        {
            'servertype': Any(*(
                s.servertype_id
                for s in Servertype.objects.filter(ip_addr_type='network')
            )),
            'intern_ip': ContainedOnlyBy(network),
        },
        ['hostname', 'intern_ip'],
        ['hostname'],
    ))

    if servers:
        return TemplateResponse(request, 'servershell/choose_ip_addr.html', {
            'servers': servers
        })

    network_query = Query({'intern_ip': network}, ['intern_ip'])

    return TemplateResponse(request, 'servershell/choose_ip_addr.html', {
        'ip_addrs': islice(network_query.get_free_ip_addrs(), 1000)
    })


@login_required
def store_command(request):
    command = request.POST.get('command')
    if command:
        command_history = request.session.setdefault('command_history', [])
        if command not in command_history:
            command_history.append(command)
            request.session.modified = True
    return HttpResponse('{"status": "OK"}', content_type='application/x-json')


def _prepare_regexp_html(regexp):
    """Return HTML for a given regexp. Includes wordbreaks."""
    if not regexp:
        return ''
    else:
        regexp_html = (escape_html(regexp).replace('|', '|&#8203;')
                       .replace(']', ']&#8203;').replace(')', ')&#8203;'))
        return mark_safe(regexp_html)
