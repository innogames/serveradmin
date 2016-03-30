from ipaddress import IPv4Address

from adminapi.dataset.exceptions import CommitValidationFailed
from serveradmin.dataset.base import lookups
from serveradmin.serverdb.models import ServerObject

def check_attributes(attributes):
    for attr in attributes:
        if attr not in lookups.attr_names:
            raise ValueError(u'Invalid attribute: {0}'.format(attr))

def check_attribute_type(attr, value):
    attr_obj = lookups.attr_names[attr]
    if attr_obj.multi:
        if not (isinstance(value, (list, set)) or hasattr(value,'_proxied_set')):
            raise ValueError((
                    u'{0} is a multi attribute. Require list/set, '
                    u'but {1} of type {2} was given'
                ).format(attr, repr(value), type(value).__name__))

        if attr_obj.type == 'string':
            for val in value:
                _require_string(attr, val)
        elif attr_obj.type == 'integer':
            for val in value:
                _require_integer(attr, val)
        elif attr_obj.type == 'boolean':
            for val in value:
                _require_boolean(attr, val)
        elif attr_obj.type == 'ip':
            for val in value:
                _require_ip(attr, val)
    else:
        if attr_obj.type == 'string':
            _require_string(attr, value)
        elif attr_obj.type == 'integer':
            _require_integer(attr, value)
        elif attr_obj.type == 'boolean':
            _require_boolean(attr, value)
        elif attr_obj.type == 'ip':
            _require_ip(attr, value)

def _require_string(attr, value):
    if not isinstance(value, basestring):
        raise ValueError((
                u'Attribute {0} is of type string, but got {1} of type {2}.'
            ).format(attr, repr(value), type(value).__name__))

def _require_integer(attr, value):
    if not isinstance(value, (int, long)):
        raise ValueError((
                u'Attribute {0} is of type integer, but got {1} of type {2}.'
            ).format(attr, repr(value), type(value).__name__))

def _require_boolean(attr, value):
    if not isinstance(value, bool):
        raise ValueError((
                u'Attribute {0} is of type boolean, but got {1} of type {2}.'
            ).format(attr, repr(value), type(value).__name__))

def _require_ip(attr, value):
    # We will accept IPv4Address objects or everything that can be converted
    if isinstance(value, IPv4Address):
        return

    if isinstance(value, basestring):
        if value.isdigit():
            return

        segs = value.split('.')
        try:
            if len(segs) != 4:
                raise ValueError()
            for seg in segs:
                x = int(seg, 10)
                if not (0 <= x <= 255):
                    raise ValueError()
        except ValueError:
            raise ValueError((
                u'Attribute {0} is of type "ip", but got {1}'
            ).format(attr, repr(value)))

        return

    if isinstance(value, (int, long)):
        return

    raise ValueError((
        'Attribute {0} is of type "ip", but got {1} of type {2}'
    ).format(attr, repr(value), type(value).__name__))

def handle_violations(
        skip_validation,
        violations_regexp,
        violations_required,
        violations_attribs,
    ):

    if not skip_validation:
        if violations_regexp or violations_required:
            if violations_regexp:
                regexp_msg = u'Attributes violating regexp: {0}. '.format(
                        u', '.join(violations_regexp)
                    )
            else:
                regexp_msg = u''
            if violations_required:
                required_msg = u'Attributes violating required: {0}.'.format(
                        u', '.join(violations_required)
                    )
            else:
                required_msg = u''

            raise CommitValidationFailed(u'Validation failed. {0}{1}'.format(
                    regexp_msg,
                    required_msg),
                    violations_regexp + violations_required,
                )
    if violations_attribs:
        raise CommitValidationFailed((
                u'Attributes {0} are not defined on '
                'this servertype. You can\'t skip this validation!'
            ).format(
                    u', '.join(violations_attribs)),
                    violations_regexp + violations_required + violations_attribs,
                )
