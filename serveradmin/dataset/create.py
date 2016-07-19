import json
from ipaddress import (
    ip_address,
    IPv4Address,
    IPv6Address,
    IPv4Network,
    IPv6Network,
)

from serveradmin.serverdb.models import (
    Attribute,
    ServertypeAttribute,
    Server,
    ChangeCommit,
    ChangeAdd,
)
from serveradmin.dataset.base import lookups
from serveradmin.dataset.validation import (
    handle_violations,
    check_attribute_type,
)
from serveradmin.dataset.typecast import typecast
from serveradmin.dataset.commit import CommitError
from adminapi.utils.json import json_encode_extra


def create_server(
    attributes,
    skip_validation,
    fill_defaults,
    fill_defaults_all,
    user=None,
    app=None,
):

    # Import here to break cyclic imports.
    from serveradmin.iprange.models import IPRange

    if 'hostname' not in attributes:
        raise CommitError('Hostname is required')
    if 'servertype' not in attributes:
        raise CommitError('Servertype is required')
    if 'project' not in attributes:
        raise CommitError('Project is required')
    if 'intern_ip' not in attributes:
        raise CommitError('Internal IP (intern_ip) is required')

    for attr in ('hostname', 'servertype', 'project', 'intern_ip'):
        check_attribute_type(attr, attributes[attr])

    if attributes['servertype'] in lookups.servertypes:
        servertype = lookups.servertypes[attributes['servertype']]
    else:
        raise CommitError('Unknown servertype: ' + attributes['servertype'])

    hostname = attributes['hostname']
    if isinstance(attributes['intern_ip'], (
        IPv4Address,
        IPv6Address,
        IPv4Network,
        IPv6Network,
    )):
        intern_ip = attributes['intern_ip']
    else:
        intern_ip = ip_address(attributes['intern_ip'])
    servertype_id = servertype.pk
    segment_id = attributes.get('segment')

    if segment_id:
        check_attribute_type('segment', segment_id)
    else:
        try:
            segment_id = IPRange.objects.filter(
                min__lte=intern_ip,
                max__gte=intern_ip,
            )[0].segment
        except IndexError:
            raise CommitError('Could not determine segment')

    project_id = attributes.get('project')

    real_attributes = attributes.copy()
    for key in (
        'hostname',
        'intern_ip',
        'comment',
        'servertype',
        'segment',
        'project',
    ):
        if key in real_attributes:
            del real_attributes[key]

    # Ignore the reverse attributes
    for attribute in Attribute.objects.all():
        if attribute.reversed_attribute and attribute.pk in real_attributes:
            del real_attributes[attribute.pk]

    violations_regexp = []
    violations_required = []
    for sa in ServertypeAttribute.objects.all():
        if sa.servertype != servertype:
            continue

        # Ignore the related via attributes
        if sa.related_via_attribute:
            if sa.attribute.pk in real_attributes:
                del real_attributes[sa.attribute.pk]
            continue

        # Handle not existing attributes (fill defaults, validate require)
        if sa.attribute.pk not in real_attributes:
            if sa.attribute.multi:
                if sa.default_value in ('', None):
                    real_attributes[sa.attribute.pk] = []
                else:
                    real_attributes[sa.attribute.pk] = _type_cast_default(
                        sa.attribute,
                        sa.default_value,
                    )
            elif sa.required:
                if fill_defaults and sa.default_value not in ('', None):
                    real_attributes[sa.attribute.pk] = _type_cast_default(
                        sa.attribute,
                        sa.default_value,
                    )
                else:
                    violations_required.append(sa.attribute.pk)
                    continue
            else:
                if fill_defaults_all and sa.default_value not in ('', None):
                    real_attributes[sa.attribute.pk] = _type_cast_default(
                        sa.attribute,
                        sa.default_value,
                    )
                else:
                    continue

        value = real_attributes[sa.attribute.pk]
        check_attribute_type(sa.attribute.pk, value)

        # Validate regular expression
        if sa.regexp:
            if sa.attribute.multi:
                for val in value:
                    if not sa.regexp_match(unicode(val)):
                        violations_regexp.append(sa.attribute.pk)
            else:
                if not sa.regexp_match(value):
                    violations_regexp.append(sa.attribute.pk)

    # Check for attributes that are not defined on this servertype
    violations_attribs = []
    servertype_attribute_ids = {
        sa.attribute.pk
        for sa in ServertypeAttribute.objects.all()
        if sa.servertype == servertype
    }
    for attr in real_attributes:
        if attr not in servertype_attribute_ids:
            violations_attribs.append(attr)

    handle_violations(
        skip_validation,
        violations_regexp,
        violations_required,
        violations_attribs,
    )

    server_id = _insert_server(
        hostname,
        intern_ip,
        segment_id,
        servertype_id,
        project_id,
        real_attributes,
    )

    created_server = real_attributes.copy()
    created_server['hostname'] = hostname
    created_server['intern_ip'] = intern_ip

    commit = ChangeCommit.objects.create(app=app, user=user)
    attributes_json = json.dumps(created_server, default=json_encode_extra)
    ChangeAdd.objects.create(
        commit=commit,
        hostname=created_server['hostname'],
        attributes_json=attributes_json,
    )

    return server_id


def _insert_server(
    hostname,
    intern_ip,
    segment_id,
    servertype_id,
    project_id,
    attributes,
):

    if Server.objects.filter(hostname=hostname).exists():
        raise CommitError(u'Server with that hostname already exists')

    server = Server.objects.create(
        hostname=hostname,
        intern_ip=intern_ip,
        _project_id=project_id,
        _servertype_id=servertype_id,
        _segment_id=segment_id,
    )
    server.full_clean()
    server.save()

    for attr_name, value in attributes.iteritems():
        attribute = lookups.attributes[attr_name]

        if attribute.multi:
            for single_value in value:
                server.add_attribute(attribute, single_value)
        else:
            server.add_attribute(attribute, value)

    return server.server_id


def _type_cast_default(attribute, value):
    if attribute.multi:
        return [
            typecast(attribute, val, force_single=True)
            for val in value.split(',')
        ]
    else:
        return typecast(attribute, value, force_single=True)
