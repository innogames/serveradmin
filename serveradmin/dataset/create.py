import json
from ipaddress import ip_network, ip_interface

from django.core.exceptions import ValidationError

from serveradmin.serverdb.models import (
    Servertype,
    Attribute,
    Server,
    ChangeCommit,
    ChangeAdd,
    get_unused_ip_addrs,
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
        raise CreateError('"hostname" attribute is required.')
    if 'servertype' not in attributes:
        raise CreateError('"servertype" attribute is required.')
    if 'project' not in attributes:
        raise CreateError('"project" attribute is required.')
    if 'segment' not in attributes:
        raise CreateError('"segment" attribute is required.')

    try:
        servertype = Servertype.objects.get(pk=attributes['servertype'])
    except Servertype.DoesNotExists:
        raise CreateError('Unknown servertype: ' + attributes['servertype'])
    intern_ip = _get_ip_addr(servertype, attributes)
    hostname = attributes['hostname']
    servertype_id = servertype.pk
    segment_id = attributes.get('segment')
    project_id = attributes.get('project')

    real_attributes = dict(_get_real_attributes(attributes))

    violations_regexp = []
    violations_required = []
    servertype_attributes = set()
    for sa in servertype.attributes.all():
        attribute = sa.attribute
        servertype_attributes.add(attribute)

        # Ignore the related via attributes
        if sa.related_via_attribute:
            if sa.attribute in real_attributes:
                del real_attributes[attribute]
            continue

        # Handle not existing attributes (fill defaults, validate require)
        if attribute not in real_attributes:
            if attribute.multi:
                if sa.default_value in ('', None):
                    real_attributes[attribute] = []
                else:
                    real_attributes[attribute] = _type_cast_default(
                        attribute,
                        sa.default_value,
                    )
            elif sa.required:
                if fill_defaults and sa.default_value not in ('', None):
                    real_attributes[attribute] = _type_cast_default(
                        attribute,
                        sa.default_value,
                    )
                else:
                    violations_required.append(attribute.pk)
                    continue
            else:
                if fill_defaults_all and sa.default_value not in ('', None):
                    real_attributes[attribute] = _type_cast_default(
                        attribute,
                        sa.default_value,
                    )
                else:
                    continue

        value = real_attributes[attribute]

        if attribute.multi:
            if sa.regexp:
                for val in value:
                    if not sa.regexp_match(unicode(val)):
                        violations_regexp.append(attribute.pk)
        elif sa.regexp:
            if not sa.regexp_match(value):
                violations_regexp.append(attribute.pk)

    # Check for attributes that are not defined on this servertype
    violations_attribs = []
    for attr in real_attributes:
        if attr not in servertype_attributes:
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

    created_server = {k.pk: v for k, v in real_attributes.items()}
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


def _get_ip_addr(servertype, attributes):
    networks = _get_networks(attributes)
    if servertype.ip_addr_type == 'null':
        if attributes.get('intern_ip') is not None:
            raise CreateError('"intern_ip" has to be None.')
        if networks:
            raise CreateError('There must not be any networks.')
        return None

    if 'intern_ip' in attributes:
        intern_ip = attributes['intern_ip']
    elif servertype.ip_addr_type in ('host', 'loadbalancer'):
        if not networks:
            raise CreateError(
                '"intern_ip" is not given, and no networks could be found.'
            )
        inter_ip = _choose_ip_addr(networks)
        if inter_ip is None:
            raise CreateError(
                'No IP address could be selected from the given networks.'
            )
        return inter_ip
    else:
        raise CreateError('"intern_ip" attribute is required.')

    try:
        if servertype.ip_addr_type == 'network':
            intern_ip = ip_network(intern_ip)
        else:
            intern_ip = ip_interface(intern_ip)
    except ValueError as error:
        raise CreateError(str(error))

    if servertype.ip_addr_type == 'network':
        _check_in_networks(networks, intern_ip)
    else:
        _check_in_networks(networks, intern_ip.network)

    return intern_ip


def _get_networks(attributes):
    for attribute in Attribute.objects.all():
        if attribute.type == 'supernet' and attribute.pk in attributes:
            try:
                server = Server.objects.get(hostname=attributes[attribute.pk])
            except Server.DoesNotExist as error:
                raise CreateError(str(error))
            yield server.intern_ip.network


def _choose_ip_addr(networks):
    smallest_network = None
    for network in networks:
        if smallest_network is not None:
            if not network.overlaps(smallest_network):
                raise CreateError('Networks are not overlapping.')
            if network.prefixlen > smallest_network.prefixlen:
                continue
        smallest_network = network
    if smallest_network is not None:
        for ip_addr in get_unused_ip_addrs(smallest_network):
            return ip_addr


def _check_in_networks(networks, intern_ip_network):
    for network in networks:
        if (
            network.prefixlen > intern_ip_network.prefixlen or
            not network.overlaps(intern_ip_network)
        ):
            raise CreateError(
                '"intern_ip" does not belong to the given networks.'
            )


def _get_real_attributes(attributes):
    for attribute_id, value in attributes.items():
        attribute = Attribute.objects.get(pk=attribute_id)
        value_multi = (
            isinstance(value, (list, set)) or
            hasattr(value, '_proxied_set')
        )

        if attribute.multi and not value_multi:
            raise CreateError(
                '{0} is a multi attribute, but {1} of type {2} given.'
                .format(attribute, repr(value), type(value).__name__)
            )
        if not attribute.multi and value_multi:
            raise CreateError(
                '{0} is not a multi attribute, but {1} of type {2} given.'
                .format(attribute, repr(value), type(value).__name__)
            )

        # Ignore special attributes
        if attribute.special:
            continue

        # Ignore nulls
        if not value_multi and value is None:
            continue

        # Ignore the virtual attribute types
        if attribute.type in ('reverse_hostname', 'supernet'):
            continue

        yield attribute, value


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

    for attribute, value in attributes.items():
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
