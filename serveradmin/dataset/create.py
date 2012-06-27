from django.db import connection

from serveradmin.dataset.base import lookups
from serveradmin.dataset.cache import invalidate_cache
from adminapi.dataset.exceptions import CommitValidationFailed, CommitError
from adminapi.utils import IP

def create_server(attributes, skip_validation, fill_defaults, fill_defaults_all):
    if u'hostname' not in attributes:
        raise CommitError(u'Hostname is required')
    if u'servertype' not in attributes:
        raise CommitError(u'Servertype is required')
    if u'intern_ip' not in attributes:
        raise CommitError(u'Internal IP (intern_ip) is required')

    try:
        stype = lookups.stype_names[attributes[u'servertype']]
    except KeyError:
        raise CommitError(u'Unknown servertype')

    hostname = attributes[u'hostname']
    intern_ip = IP(attributes[u'intern_ip'])
    servertype_id = stype.pk
    segment = attributes.get(u'segment')

    real_attributes = attributes.copy()
    for key in (u'hostname', u'intern_ip', u'comment', u'servertype', u'segment'):
        try:
            del real_attributes[key]
        except KeyError:
            pass
    
    violations_regexp = []
    violations_required = []
    for attr in stype.attributes:
        stype_attr = lookups.stype_attrs[(stype.name, attr.name)]
        attr_obj = lookups.attr_names[attr.name]
        
        # Handle not existing attributes (fill defaults, validate require)
        if attr.name not in real_attributes:
            if attr_obj.multi:
                if stype_attr.default is None:
                    real_attributes[attr.name] = []
                else:
                    real_attributes[attr.name] = stype_attr.default.split(',')
            elif stype_attr.required:
                if fill_defaults and stype_attr.default is not None:
                    real_attributes[attr.name] = stype_attr.default
                else:
                    violations_required.append(attr.name)
                    continue
            else:
                if fill_defaults_all and stype_attr.default is not None:
                        real_attributes[attr.name] = stype_attr.default

        # Validate regular expression
        regexp = stype_attr.regexp
        value = real_attributes[attr.name]
        if attr_obj.multi:
            if not (isinstance(value, (list, set)) or hasattr(value,
                    '_proxied_set')):
                error = ('{0} is a multi attribute and requires list/set. '
                         'Got {1} of type {2}')
                raise ValueError(error.format(attr.name, repr(value),
                    type(value).__name__))
            if regexp:
                for val in value:
                    if not regexp.match(unicode(val)):
                        violations_regexp.append(attr.name)
        else:
            if regexp and not regexp.match(value):
                violations_regexp.append(attr.name)
    
    # Check for attributes that are not defined on this servertype
    violations_attribs = []
    attribute_set = set([attr.name for attr in stype.attributes])
    for attr in real_attributes:
        if attr not in attribute_set:
            violations_attribs.append(attr)

    if not skip_validation:
        if violations_regexp or violations_required:
            raise CommitValidationFailed(u'Validation failed',
                    violations_regexp + violations_required)
    if violations_attribs:
        raise CommitValidationFailed(u'Unskippable validation failed',
                violations_regexp + violations_required + violations_attribs)
    

    c = connection.cursor()
    c.execute(u"SELECT GET_LOCK('serverobject_commit', 10)")
    if not c.fetchone()[0]:
        raise CommitError(u'Could not get lock')
    try:
        server_id = _insert_server(hostname, intern_ip, segment,
                servertype_id, real_attributes)
    finally:
        c.execute(u'COMMIT')
        c.execute(u"SELECT RELEASE_LOCK('serverobject_commit')")

    # Invalidate caches
    invalidate_cache()

    return server_id

def _insert_server(hostname, intern_ip, segment, servertype_id, attributes):
    c = connection.cursor()
    
    c.execute(u'SELECT COUNT(*) FROM admin_server WHERE hostname = %s',
            (hostname, ))
    if c.fetchone()[0] != 0:
        raise CommitError(u'Server with that hostname already exists')

    # Get segment
    c.execute(u'SELECT segment_id FROM ip_range '
              u'WHERE %s BETWEEN `min` AND `max` LIMIT 1',
              (intern_ip.as_int(), ))
    result = c.fetchone()
    segment_id = result[0] if result else segment
    
    # Insert into admin_server table
    c.execute(u'INSERT INTO admin_server (hostname, intern_ip, servertype_id, '
            u' segment) VALUES (%s, %s, %s, %s)', (hostname, intern_ip.as_int(),
            servertype_id, segment_id))
    server_id = c.lastrowid

    # Insert additional attributes
    attr_query = (u'INSERT INTO attrib_values (server_id, attrib_id, value) '
                  u'VALUES (%s, %s, %s)')
    for attr_name, value in attributes.iteritems():
        attr_obj = lookups.attr_names[attr_name]
        if attr_obj.multi:
            for single_value in value:
                if attr_obj.type == u'ip':
                    single_value = IP(single_value).as_int()
                c.execute(attr_query, (server_id, attr_obj.pk, single_value))
        else:
            if attr_obj.type == u'ip':
                value = IP(value).as_int()
            c.execute(attr_query, (server_id, attr_obj.pk, value))

    return server_id
