import json
from ipaddress import ip_interface

from django.core.exceptions import ValidationError

from serveradmin.serverdb.models import (
    Servertype,
    Attribute,
    ServertypeAttribute,
    Server,
    ChangeCommit,
    ChangeAdd,
)
from serveradmin.dataset.typecast import typecast
from adminapi.utils.json import json_encode_extra


class CreateError(ValidationError):
    pass


def create_server(
    attributes,
    skip_validation,
    fill_defaults,
    fill_defaults_all,
    user=None,
    app=None,
):
    if 'hostname' not in attributes:
        raise CreateError('Hostname is required')
    if 'servertype' not in attributes:
        raise CreateError('Servertype is required')
    if 'project' not in attributes:
        raise CreateError('Project is required')
    if 'intern_ip' not in attributes:
        raise CreateError('Internal IP (intern_ip) is required')
    if 'segment' not in attributes:
        raise CreateError('Segment is required')
    try:
        servertype = Servertype.objects.get(pk=attributes['servertype'])
    except Servertype.DoesNotExists:
        raise CreateError('Unknown servertype: ' + attributes['servertype'])

    hostname = attributes['hostname']
    intern_ip = (
        ip_interface(attributes['intern_ip'])
        if attributes['intern_ip'] is not None
        else None
    )
    servertype_id = servertype.pk
    segment_id = attributes.get('segment')
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

        if sa.attribute.multi:
            if not (isinstance(value, (list, set)) or
                    hasattr(value, '_proxied_set')):
                raise CreateError(
                    '{0} is a multi attribute. Require list/set, '
                    'but {1} of type {2} was given'
                    .format(sa.attribute, repr(value), type(value).__name__)
                )
            if sa.regexp:
                for val in value:
                    if not sa.regexp_match(unicode(val)):
                        violations_regexp.append(sa.attribute.pk)
        elif sa.regexp:
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
        raise CreateError(u'Server with that hostname already exists')

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
        attribute = Attribute.objects.get(pk=attr_name)

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


def handle_violations(
    skip_validation,
    violations_regexp,
    violations_required,
    violations_attribs,
):
    if not skip_validation:
        if violations_regexp or violations_required:
            if violations_regexp:
                regexp_msg = 'Attributes violating regexp: {0}. '.format(
                    ', '.join(violations_regexp)
                )
            else:
                regexp_msg = ''
            if violations_required:
                required_msg = 'Attributes violating required: {0}.'.format(
                    ', '.join(violations_required)
                )
            else:
                required_msg = ''

            raise CreateError(
                'Validation failed. {0}{1}'.format(regexp_msg, required_msg),
                violations_regexp + violations_required,
            )
    if violations_attribs:
        raise CreateError(
            'Attributes {0} are not defined on '
            'this servertype. You can\'t skip this validation!'
            .format(', '.join(violations_attribs)),
            violations_regexp + violations_required + violations_attribs,
        )
