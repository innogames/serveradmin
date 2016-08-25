try:
    import simplejson as json
except ImportError:
    import json
from operator import attrgetter

from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.utils.html import mark_safe, escape as escape_html

from adminapi.utils.json import json_encode_extra
from adminapi.utils.parse import ParseQueryError, parse_query
from serveradmin.dataset import query, filters
from serveradmin.dataset.filters import filter_classes
from serveradmin.dataset.commit import (
    commit_changes,
    CommitValidationFailed,
    CommitIncomplete,
)
from serveradmin.dataset.typecast import typecast, displaycast
from serveradmin.dataset.create import create_server
from serveradmin.serverdb.forms import ServerForm
from serveradmin.serverdb.models import (
    Servertype,
    Attribute,
    ServertypeAttribute,
    ServerStringAttribute,
)

MAX_DISTINGUISHED_VALUES = 50
NUM_SERVERS_DEFAULT = 100


@login_required
@ensure_csrf_cookie
def index(request):
    attributes = Attribute.objects.all()
    attribute_groups = {}
    for attribute in attributes:
        attribute_groups.setdefault(attribute.group, []).append(attribute)
    for attributes in attribute_groups.itervalues():
        attributes.sort(key=attrgetter('pk'))
    attribute_groups = sorted(attribute_groups.iteritems(), key=lambda x: x[0])

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
    })


@login_required
def autocomplete(request):
    autocomplete_list = []
    if 'hostname' in request.GET:
        hostname = request.GET['hostname']
        try:
            queryset = query(hostname=filters.Startswith(hostname))
            queryset.restrict('hostname')
            queryset.limit(10)
            autocomplete_list += (h['hostname'] for h in queryset)
        except ValidationError:
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

    order_by = request.GET.get('order_by')
    order_dir = request.GET.get('order_dir', 'asc')

    try:
        query_kwargs = parse_query(term, filter_classes)
        queryset = query(**query_kwargs)
        queryset.restrict(*shown_attributes)
        if order_by:
            queryset.order_by(order_by, order_dir)
        queryset.limit(limit)
        if offset:
            queryset.offset(offset)

        results = queryset.get_results()
        num_servers = queryset.get_num_rows()
    except (ParseQueryError, ValidationError) as error:
        return HttpResponse(json.dumps({
            'status': 'error',
            'message': str(error)
        }))

    request.session['term'] = term
    request.session['per_page'] = limit

    # Add information about available attributes on servertypes
    # It will be encoded as map avail[servertype][attr] = stypeattr
    servertype_ids = {s['servertype'] for s in results.values()}
    specials = tuple(
        (a.pk, {
            'regexp': None,
            'default': None,
        })
        for a in Attribute.specials
    )
    avail_attributes = {s: dict(specials) for s in servertype_ids}
    for sa in ServertypeAttribute.objects.all():
        if sa.servertype.pk in servertype_ids and not sa.related_via_attribute:
            avail_attributes[sa.servertype.pk][sa.attribute.pk] = {
                'regexp': sa.regexp,
                'default': sa.default_value,
            }

    return HttpResponse(json.dumps({
        'status': 'success',
        'understood': queryset.get_representation().as_code(hide_extra=True),
        'servers': results,
        'num_servers': num_servers,
        'avail_attributes': avail_attributes
    }, default=json_encode_extra), content_type='application/x-json')


@login_required
def export(request):
    term = request.GET.get('term', '')
    try:
        query_args = parse_query(term, filter_classes)
        q = query(**query_args).restrict('hostname')
    except (ParseQueryError, ValidationError) as error:
        return HttpResponse(str(error), status=400)

    hostnames = u' '.join(server['hostname'] for server in q)
    return HttpResponse(hostnames, content_type='text/plain')


def list_and_edit(request, mode='list'):
    try:
        object_id = request.GET['object_id']
        server = query(object_id=object_id).get()
    except (KeyError, ValidationError):
        raise Http404

    if not request.user.has_perm('dataset.change_serverobject'):
        mode = 'list'

    stype = Servertype.objects.get(pk=server['servertype'])

    invalid_attrs = set()
    if mode == 'edit' and request.POST:
        attrs = set(request.POST.getlist('attr'))
        for attr in attrs:
            attribute = Attribute.objects.get(pk=attr)

            if attribute.multi:
                values = [raw_value.strip() for raw_value in
                          request.POST.get('attr_' + attr, '').splitlines()]
                try:
                    value = typecast(attribute, values)
                except ValueError:
                    invalid_attrs.add(attr)
                    value = set(values)
            else:
                value = request.POST.get('attr_' + attr, '')
                try:
                    value = typecast(attribute, value)
                except ValueError:
                    invalid_attrs.add(attr)
            server[attr] = value

        if not invalid_attrs:
            try:
                server.commit(user=request.user)
                messages.success(request, 'Edited server successfully')
                url = '{0}?object_id={1}'.format(
                        reverse('servershell_list'),
                        server.object_id,
                    )
                return HttpResponseRedirect(url)
            except CommitValidationFailed as e:
                invalid_attrs.update([attr for obj_id, attr in e.violations])
            except ValidationError as error:
                messages.error(request, str(error))

        if invalid_attrs:
            messages.error(request, 'Attributes contain invalid values')

    servertype_attributes = {
        sa.attribute.pk: sa
        for sa in ServertypeAttribute.objects.all()
        if sa.servertype == stype
    }

    fields = []
    fields_set = set()
    for key, value in server.iteritems():
        if key not in servertype_attributes:
            continue
        servertype_attribute = servertype_attributes[key]
        if servertype_attribute.related_via_attribute:
            continue

        fields_set.add(key)
        fields.append({
            'key': key,
            'value': displaycast(servertype_attribute.attribute, value),
            'has_value': True,
            'editable': True,
            'type': servertype_attribute.attribute.type,
            'multi': servertype_attribute.attribute.multi,
            'required': servertype_attribute.required,
            'regexp': _prepare_regexp_html(servertype_attribute.regexp),
            'default': servertype_attribute.default_value,
            'readonly': servertype_attribute.attribute.readonly,
            'error': key in invalid_attrs,
        })

    if mode == 'edit':
        for servertype_attribute in servertype_attributes.values():
            if servertype_attribute.attribute.pk in fields_set:
                continue
            fields.append({
                'key': servertype_attribute.attribute.pk,
                'value': [] if servertype_attribute.attribute.multi else '',
                'has_value': False,
                'editable': True,
                'type': servertype_attribute.attribute.type,
                'multi': servertype_attribute.attribute.multi,
                'required': False,
                'regexp': _prepare_regexp_html(servertype_attribute.regexp),
                'default': servertype_attribute.default_value,
                'readonly': servertype_attribute.attribute.readonly,
                'error': servertype_attribute.attribute.pk in invalid_attrs,
            })

    return TemplateResponse(request, 'servershell/{0}.html'.format(mode), {
        'object_id': server.object_id,
        'fields': fields,
        'is_ajax': request.is_ajax(),
        'base_template': 'empty.html' if request.is_ajax() else 'base.html',
        'link': request.get_full_path(),
    })


@login_required
@permission_required('dataset.change_serverobject')
def commit(request):
    try:
        commit = json.loads(request.POST['commit'])
    except (KeyError, ValueError) as error:
        result = {
            'status': 'error',
            'message': unicode(error),
        }
    else:
        if 'changes' in commit:
            changes = {}
            for key, value in commit['changes'].iteritems():
                if not key.isdigit():
                    continue
                changes[int(key)] = value
            commit['changes'] = changes

        try:
            commit_changes(commit, user=request.user)
        except (
            ValueError,
            ValidationError,
        ) as error:
            result = {
                'status': 'error',
                'message': unicode(error),
            }
        except CommitIncomplete as error:
            result = {
                'status': 'success',
                'message': unicode(error)
            }
        else:
            result = {'status': 'success'}

    return HttpResponse(json.dumps(result), content_type='application/x-json')


@login_required
def get_values(request):
    try:
        attribute = Attribute.objects.get(pk=request.GET['attribute'])
    except Attribute.DoesNotExist:
        raise Http404

    queryset = ServerStringAttribute.objects.filter(_attribute=attribute)
    value_queryset = queryset.values('value').distinct().order_by('value')

    return TemplateResponse(request, 'servershell/values.html', {
        'attribute': attribute,
        'values': (
            v['value'] for v in value_queryset[:MAX_DISTINGUISHED_VALUES]
        ),
        'num_values': MAX_DISTINGUISHED_VALUES
    })


@login_required
@permission_required('dataset.create_serverobject')
def new_server(request):

    if 'clone_from' in request.REQUEST:
        try:
            clone_from = query(hostname=request.REQUEST['clone_from']).get()
        except ValidationError:
            raise Http404
    else:
        clone_from = None

    if request.method == 'POST':
        form = ServerForm(request.POST)

        if form.is_valid():
            if clone_from:
                attributes = dict(clone_from)
            else:
                attributes = {
                    'servertype': form.cleaned_data['_servertype'].pk,
                }

            attributes['hostname'] = form.cleaned_data['hostname']
            attributes['intern_ip'] = form.cleaned_data['intern_ip']
            attributes['project'] = form.cleaned_data['_project'].pk
            attributes['segment'] = form.cleaned_data['_segment'].pk
            attributes['responsible_admin'] = [
                form.cleaned_data['_project'].responsible_admin.username
            ]
            if 'ssh_pubkey' in attributes:
                del attributes['ssh_pubkey']

            server_id = create_server(
                attributes,
                skip_validation=True,
                fill_defaults=True,
                fill_defaults_all=True,
                user=request.user,
            )
            url = '{0}?object_id={1}'.format(
                reverse('servershell_edit'), server_id
            )
            return HttpResponseRedirect(url)
    else:
        if clone_from:
            form = ServerForm(initial={
                '_servertype': clone_from['servertype'],
                '_project': clone_from['project'],
                '_segment': clone_from['segment'],
                'hostname': clone_from['hostname'],
                'intern_ip': clone_from['intern_ip'],
            })
        else:
            form = ServerForm()

    return TemplateResponse(request, 'servershell/new_server.html', {
        'form': form,
        'is_ajax': request.is_ajax(),
        'base_template': 'empty.html' if request.is_ajax() else 'base.html',
        'clone_from': clone_from,
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
