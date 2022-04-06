"""Serveradmin - Servershell

Copyright (c) 2021 InnoGames GmbH
"""

import json
from distutils.util import strtobool
from ipaddress import IPv6Address, IPv4Address, ip_interface
from itertools import islice, chain

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import (
    ObjectDoesNotExist,
    PermissionDenied,
    ValidationError
)
from django.http import (
    HttpResponse,
    HttpResponseRedirect,
    Http404,
    JsonResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound, HttpRequest
)
from django.shortcuts import redirect, render, get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import mark_safe, escape as escape_html
from django.views.decorators.http import require_http_methods
from django.views.defaults import bad_request

from adminapi.datatype import DatatypeError
from adminapi.filters import Any, ContainedOnlyBy, filter_classes, Not
from adminapi.parse import parse_query
from adminapi.request import json_encode_extra

from serveradmin.dataset import Query
from serveradmin.serverdb.models import (
    Servertype,
    Attribute,
    ServertypeAttribute,
    Server
)
from serveradmin.serverdb.query_committer import commit_query
from serveradmin.servershell.helper import get_default_shown_attributes
from serveradmin.servershell.helper.autocomplete import (
    attribute_value_startswith,
    attribute_startswith
)

MAX_DISTINGUISHED_VALUES = 50
NUM_SERVERS_DEFAULT = 25
AUTOCOMPLETE_LIMIT = 20
SEARCH_SETTINGS = {
    'autocomplete': True,
    'autocomplete_delay_search': 250,
    'autocomplete_delay_commands': 10,
    'autoselect': True,
    'save_attributes': False,
}


@login_required
def index(request):
    attributes = list(Attribute.objects.all())
    attributes.extend(Attribute.specials.values())
    attributes_json = list()
    for attribute in attributes:
        attributes_json.append({
            'attribute_id': attribute.attribute_id,
            'type': attribute.type,
            'multi': attribute.multi,
            'hovertext': attribute.hovertext,
            'help_link': attribute.help_link,
            'group': attribute.group,
            'regex': (
                # XXX: HTML5 input patterns do not support these
                None if not attribute.regexp else
                attribute.regexp.replace('\\A', '^').replace('\\Z', '$')
            ),
        })
    attributes_json.sort(key=lambda attr: attr['group'])

    # Load user search settings or set default values
    search_settings = dict()
    for setting, default in SEARCH_SETTINGS.items():
        search_settings[setting] = request.session.setdefault(setting, default)

    shown_attributes = request.GET.getlist('shown_attributes[]')
    if not shown_attributes:
        if search_settings['save_attributes']:
            shown_attributes = request.session.setdefault(
                'shown_attributes', get_default_shown_attributes())
        else:
            shown_attributes = get_default_shown_attributes()

    return TemplateResponse(request, 'servershell/index.html', {
        'term': request.GET.get('term', request.session.get('term', '')),
        'shown_attributes': shown_attributes,
        'deep_link': bool(strtobool(request.GET.get('deep_link', 'false'))),
        'attributes': attributes_json,
        'offset': 0,
        'limit': request.session.get('limit', NUM_SERVERS_DEFAULT),
        'order_by': 'hostname',
        'filters': sorted([(f.__name__, f.__doc__) for f in filter_classes]),
        'search_settings': search_settings,
    })


@login_required
def autocomplete(request):
    hostname = request.GET.get('hostname')

    if hostname:
        try:
            query = Server.objects.filter(hostname__startswith=hostname).only(
                'hostname').order_by('hostname')
            autocomplete_list = [server.hostname for server in
                                 query[:AUTOCOMPLETE_LIMIT]]
        except (DatatypeError, ValidationError):
            # If there is no valid query, just don't auto-complete
            autocomplete_list = list()
    else:
        autocomplete_list = list()

    return HttpResponse(json.dumps({'autocomplete': autocomplete_list}),
                        content_type='application/x-json')


@login_required
def get_results(request):
    term = request.GET.get('term', '')
    shown_attributes = request.GET.getlist('shown_attributes[]')
    deep_link = bool(strtobool(request.GET.get('deep_link', 'false')))

    if request.session.get('save_attributes') and not deep_link:
        request.session['shown_attributes'] = shown_attributes

    try:
        offset = int(request.GET.get('offset', '0'))
        limit = int(request.GET.get('limit', '0'))
        request.session['limit'] = limit
    except ValueError:
        offset = 0
        limit = NUM_SERVERS_DEFAULT

    if 'order_by' in request.GET:
        order_by = [request.GET['order_by']]
    else:
        order_by = None

    try:
        # Query manipulates shown_attributes by adding object_id we want to
        # keep the original value to save settings ...
        restrict = shown_attributes.copy()
        if 'servertype' not in restrict:
            restrict.append('servertype')
        query = Query(parse_query(term), restrict, order_by)

        # TODO: Using len is terribly slow for large datasets because it has
        #  to query all objects but we cannot use count which is available on
        #  Django QuerySet
        num_servers = len(query)
    except (DatatypeError, ObjectDoesNotExist, ValidationError) as error:
        return HttpResponse(json.dumps({
            'status': 'error',
            'message': str(error)
        }))

    # Query successful term must be valid here, so we can save it safely now.
    request.session['term'] = term

    servers = list(islice(query, offset, offset + limit))

    # Add information about available, editable attributes on servertypes
    servertype_ids = {s['servertype'] for s in servers}

    # We do not support editing of all attributes
    default_editable = list(Attribute.specials)
    default_editable.remove('object_id')
    default_editable.remove('servertype')

    editable_attributes = dict()
    for servertype_id in servertype_ids:
        editable_attributes[servertype_id] = default_editable.copy()
    for sa in ServertypeAttribute.objects.filter(
            servertype_id__in=servertype_ids,
            attribute_id__in=shown_attributes,
            related_via_attribute_id__isnull=True,
            attribute__readonly=False,
    ):
        editable_attributes[sa.servertype_id].append(sa.attribute_id)

    return HttpResponse(json.dumps({
        'status': 'success',
        'understood': repr(query),
        'servers': servers,
        'num_servers': num_servers,
        'editable_attributes': editable_attributes,
    }, default=json_encode_extra), content_type='application/x-json')


@login_required
@require_http_methods(['GET'])
def inspect(request):
    if 'object_id' in request.GET:
        query = Query({'object_id': request.GET['object_id']}, None)
    elif 'hostname' in request.GET:
        query = Query({'hostname': request.GET['hostname']}, None)
    else:
        return HttpResponseBadRequest(
            'object_id or hostname parameter is mandatory')

    if not query:
        return HttpResponseNotFound('No such object exists')

    return _edit(request, query.get(), template='inspect')


@login_required
def edit(request):
    if 'object_id' in request.GET:
        server = Query({'object_id': request.GET['object_id']}, None).get()
    else:
        servertype = request.POST.get('attr_servertype')
        if not Servertype.objects.filter(pk=servertype).exists():
            raise Http404('Servertype {} does not exist'.format(servertype))
        server = Query().new_object(servertype)

    return _edit(request, server, True)


def _edit(request, server, edit_mode=False, template='edit'):  # NOQA: C901
    # @TODO work with ServerAttribute models here and use Django forms
    invalid_attrs = set()
    if edit_mode and request.POST:
        attribute_lookup = {a.pk: a for a in Attribute.objects.filter(
            attribute_id__in=(k[len('attr_'):] for k in request.POST.keys()))}
        attribute_lookup.update(Attribute.specials)

        # Get current values to be able to submit only changes
        current = None
        if server['object_id']:
            current = Query({'object_id': server['object_id']},
                            list(attribute_lookup.keys())).get()

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

            if attribute_id not in server.keys():
                messages.error(request,
                               'Unknown attribute {}'.format(attribute_id))
                continue

            if current:
                # TODO: Remove when PR153 is merged
                if type(current[attribute_id]) in (IPv4Address, IPv6Address):
                    current[attribute_id] = ip_interface(current[attribute_id])

                # Submit only changes
                if current[attribute_id] != value:
                    server[attribute_id] = value
            else:
                server[attribute_id] = value

        if not invalid_attrs:
            if server.object_id:
                action = 'edited'
                created = []

                changes = server._serialize_changes()
                if len(changes.keys()) > 1:
                    changed = [changes]
                else:
                    # Only object_id has been passed and we do not support
                    # changing it (yet).
                    changed = []
            else:
                action = 'created'
                created = [server]
                changed = []

            if not created and not changed:
                messages.info(request, str('Nothing has changed.'))
            else:
                try:
                    commit_obj = commit_query(created, changed,
                                              user=request.user)
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
            messages.error(request, 'Attributes contains invalid values')

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
            'regexp_display': _prepare_regexp_html(attribute.regexp),
            'regexp': (
                # XXX: HTML5 input patterns do not support these
                None if not attribute.regexp else
                attribute.regexp.replace('\\A', '^').replace('\\Z', '$')
            ),
            'default': (
                    servertype_attribute and servertype_attribute.default_value
            ),
            'readonly': attribute.readonly,
            'error': key in invalid_attrs,
            'hovertext': attribute.hovertext,
        })

    fields.sort(key=lambda k: (not k['required'], k['key']))
    return TemplateResponse(request, 'servershell/{}.html'.format(template), {
        'object_id': server.object_id,
        'hostname': server['hostname'],
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
def new_object(request):
    servertype = request.GET.get('servertype')

    try:
        new_object = Query().new_object(servertype)
    except Servertype.DoesNotExist:
        messages.error(request,
                       'The servertype {} does not exist!'.format(servertype))
        return redirect('servershell_index')

    return _edit(request, new_object)


@login_required
def clone_object(request):
    try:
        cloned_attributes = list(Attribute.specials)
        # intern_ip is usually unique (except for loadbalancers) therefore it
        # makes sense to not clone it.
        cloned_attributes.remove('intern_ip')
        cloned_attributes.extend(
            list(Attribute.objects.filter(clone=True).values_list(
                'attribute_id', flat=True)))

        old_object = Query(
            {'object_id': request.GET.get('object_id')}, cloned_attributes
        ).get()
    except ValidationError as e:
        messages.error(request, e.message)
        return redirect('servershell_index')

    new_object = Query().new_object(old_object['servertype'])
    for attribute_id, value in old_object.items():
        new_object[attribute_id] = value

    return _edit(request, new_object)


@login_required
def choose_ip_addr(request):
    if 'network' not in request.GET:
        servers = list(
            Query({'servertype': 'route_network'}, ['hostname', 'intern_ip'],
                  ['hostname']))

        return TemplateResponse(request, 'servershell/choose_ip_addr.html',
                                {'servers': servers})

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
        return TemplateResponse(request, 'servershell/choose_ip_addr.html',
                                {'servers': servers})

    # TODO: This is specific to our data model, we should get it independent
    network_query = Query(
        {'intern_ip': network, 'servertype': Not('provider_network')},
        ['intern_ip', 'servertype'])

    return TemplateResponse(request, 'servershell/choose_ip_addr.html', {
        'ip_addrs': islice(network_query.get_free_ip_addrs(), 1000)})


@login_required
def settings(request):
    """Synchronize search settings

    Save desired search settings to user session

    :param request:
    :return:
    """

    for setting in SEARCH_SETTINGS.keys():
        value = request.GET.get(setting)
        if value in ('true', 'false'):
            request.session[setting] = bool(strtobool(value))
        else:
            request.session[setting] = int(value)

    return JsonResponse(
        {key: request.session.get(key) for key in SEARCH_SETTINGS})


def _prepare_regexp_html(regexp):
    """Return HTML for a given regexp. Includes wordbreaks."""
    if not regexp:
        return ''
    else:
        regexp_html = (escape_html(regexp).replace('|', '|&#8203;')
                       .replace(']', ']&#8203;').replace(')', ')&#8203;'))
        return mark_safe(regexp_html)


@login_required
def diff(request: HttpRequest) -> HttpResponse:
    attrs = request.GET.getlist('attr')
    objects = request.GET.getlist('object')

    if not objects or not all([o.isnumeric() for o in objects]):
        return bad_request(request, HttpResponseBadRequest)

    # Can raise ApiError for unknown attributes - let it flow ...
    qs = Query({'object_id': Any(*objects)}, attrs if attrs else None)

    diff_data = []
    for attribute in sorted(set(chain(*[o.keys() for o in qs]))):
        # object_id is always different and special
        if attribute == 'object_id':
            continue

        # Show hostname only if request by user
        if attribute == 'hostname' and attrs != [] and attribute not in attrs:
            continue

        values = []
        for obj in qs:
            values.append(obj[attribute])

        diff_data.append([attribute, values])

    # Fetch hostnames if not requested by user to display as header in result.
    if 'hostname' in attrs:
        hosts = qs
    else:
        hosts = Query({'object_id': Any(*objects)}, ['hostname'])

    context = {
        'hosts': hosts,
        'diff_data': diff_data,
    }
    return render(request, 'servershell/diff.html', context)
