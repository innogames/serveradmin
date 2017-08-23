import json
from ipaddress import ip_network, ip_interface

from django.db import transaction
from django.core.exceptions import ValidationError

from serveradmin.serverdb.models import (
    Servertype,
    Project,
    Attribute,
    Server,
    ChangeCommit,
    ChangeAdd,
    get_unused_ip_addrs,
)
from serveradmin.dataset.typecast import typecast
from serveradmin.dataset.commit import access_control
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
    with transaction.atomic():
        if 'hostname' not in attributes:
            raise CreateError('"hostname" attribute is required.')
        hostname = attributes['hostname']

        servertype = _get_servertype(attributes)
        project = _get_project(attributes)
        intern_ip = _get_ip_addr(servertype, attributes)

        if not user:
            user = app.owner

        real_attributes = dict(_get_real_attributes(attributes))
        _validate_real_attributes(
            servertype,
            real_attributes,
            skip_validation,
            fill_defaults,
            fill_defaults_all,
        )

        server_id = _insert_server(
            hostname,
            intern_ip,
            servertype,
            project,
            real_attributes,
        )

        created_server = {k.pk: v for k, v in real_attributes.items()}
        created_server['hostname'] = hostname
        created_server['servertype'] = servertype.pk
        created_server['project'] = project.pk
        created_server['intern_ip'] = intern_ip

        access_control('create', created_server, user, app)

        commit = ChangeCommit.objects.create(app=app, user=user)
        attributes_json = json.dumps(created_server, default=json_encode_extra)
        ChangeAdd.objects.create(
            commit=commit,
            server_id=server_id,
            attributes_json=attributes_json,
        )

        return server_id


def _get_servertype(attributes):
    if 'servertype' not in attributes:
        raise CreateError('"servertype" attribute is required.')
    try:
        return Servertype.objects.get(pk=attributes['servertype'])
    except Servertype.DoesNotExist:
        raise CreateError('Unknown servertype: ' + attributes['servertype'])


def _get_project(attributes):
    if 'project' not in attributes:
        raise CreateError('"project" attribute is required.')

    return Project.objects.select_for_update().get(pk=attributes['project'])


def _get_ip_addr(servertype, attributes):
    networks = tuple(_get_networks(attributes))
    if servertype.ip_addr_type == 'null':
        return _get_null_ip_addr(attributes, networks)
    if servertype.ip_addr_type in ('host', 'loadbalancer'):
        return _get_host_ip_addr(attributes, networks)
    return _get_network_ip_addr(attributes, networks)


def _get_networks(attributes):
    for attribute in Attribute.objects.all():
        if attribute.type == 'supernet' and attributes.get(attribute.pk):
            attribute_value = attributes[attribute.pk]
            try:
                server = Server.objects.get(hostname=attribute_value)
            except Server.DoesNotExist:
                raise CreateError(
                    'No server named "{0}" for attribute "{1}"'
                    .format(attribute_value, attribute)
                )
            target_servertype = attribute.target_servertype
            if server.servertype != target_servertype:
                raise CreateError(
                    'Matching server "{0}" for attribute "{1}" is not from '
                    'servertype "{2}"'
                    .format(attribute_value, attribute, target_servertype)
                )
            yield server.intern_ip.network


def _get_null_ip_addr(attributes, networks):
    if attributes.get('intern_ip') is not None:
        raise CreateError('"intern_ip" has to be None.')
    if networks:
        raise CreateError('There must not be any networks.')

    return None


def _get_host_ip_addr(attributes, networks):
    if 'intern_ip' not in attributes:
        if not networks:
            raise CreateError(
                '"intern_ip" is not given, and no networks could be found.'
            )
        intern_ip = _choose_ip_addr(networks)
        if intern_ip is None:
            raise CreateError(
                'No IP address could be selected from the given networks.'
            )
        return intern_ip

    try:
        intern_ip = ip_interface(attributes['intern_ip'])
    except ValueError as error:
        raise CreateError(str(error))

    _check_in_networks(networks, intern_ip.network)
    return intern_ip.ip


def _get_network_ip_addr(attributes, networks):
    if 'intern_ip' not in attributes:
        raise CreateError('"intern_ip" attribute is required.')

    try:
        intern_ip = ip_network(attributes['intern_ip'])
    except ValueError as error:
        raise CreateError(str(error))

    _check_in_networks(networks, intern_ip)
    return intern_ip


def _choose_ip_addr(networks):
    smallest_network = None
    for network in networks:
        if smallest_network is not None:
            if not network.overlaps(smallest_network):
                raise CreateError('Networks are not overlapping.')
            if network.prefixlen < smallest_network.prefixlen:
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


def _validate_real_attributes(  # NOQA: C901
    servertype,
    real_attributes,
    skip_validation,
    fill_defaults,
    fill_defaults_all,
):
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
                if sa.default_value is None:
                    real_attributes[attribute] = []
                else:
                    real_attributes[attribute] = _type_cast_default(
                        attribute,
                        sa.default_value,
                    )
            elif sa.required:
                if fill_defaults and sa.default_value is not None:
                    real_attributes[attribute] = _type_cast_default(
                        attribute,
                        sa.default_value,
                    )
                else:
                    violations_required.append(attribute.pk)
                    continue
            else:
                if fill_defaults_all and sa.default_value is not None:
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
                    if not sa.regexp_match(str(val)):
                        violations_regexp.append(attribute.pk)
        elif sa.regexp:
            if not sa.regexp_match(value):
                violations_regexp.append(attribute.pk)

    # Check for attributes that are not defined on this servertype
    violations_attribs = []
    for attr in real_attributes:
        if attr not in servertype_attributes:
            violations_attribs.append(str(attr))

    handle_violations(
        skip_validation,
        violations_regexp,
        violations_required,
        violations_attribs,
    )


def _insert_server(
    hostname,
    intern_ip,
    servertype,
    project,
    attributes,
):

    if Server.objects.filter(hostname=hostname).exists():
        raise CreateError('Server with that hostname already exists')

    server = Server.objects.create(
        hostname=hostname,
        intern_ip=intern_ip,
        _servertype=servertype,
        _project=project,
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
