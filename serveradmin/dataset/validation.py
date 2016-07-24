from ipaddress import ip_interface

from django.core.exceptions import ValidationError

from serveradmin.dataset.commit import CommitValidationFailed
from serveradmin.serverdb.models import Attribute


def check_attributes(attributes):
    for attr in attributes:
        try:
            Attribute.objects.get(pk=attr)
        except Attribute.DoesNotExist:
            raise ValidationError('Invalid attribute: {0}'.format(attr))


def check_attribute_type(attr, value):
    attribute = Attribute.objects.get(pk=attr)
    if attribute.multi:
        if not (isinstance(value, (list, set)) or
                hasattr(value, '_proxied_set')):
            raise ValidationError(
                '{0} is a multi attribute. Require list/set, '
                'but {1} of type {2} was given'
                .format(attr, repr(value), type(value).__name__)
            )

        if attribute.type == 'string':
            for val in value:
                _require_string(attr, val)
        elif attribute.type == 'integer':
            for val in value:
                _require_integer(attr, val)
        elif attribute.type == 'boolean':
            for val in value:
                _require_boolean(attr, val)
        elif attribute.type == 'ip':
            for val in value:
                _require_ip(attr, val)
    else:
        if attribute.type == 'string':
            _require_string(attr, value)
        elif attribute.type == 'integer':
            _require_integer(attr, value)
        elif attribute.type == 'boolean':
            _require_boolean(attr, value)
        elif attribute.type == 'ip':
            _require_ip(attr, value)


def _require_string(attr, value):
    if not isinstance(value, basestring):
        raise ValidationError(
            'Attribute {0} is of type string, but got {1} of type {2}.'
            .format(attr, repr(value), type(value).__name__)
        )


def _require_integer(attr, value):
    if not isinstance(value, (int, long)):
        raise ValidationError(
            'Attribute {0} is of type integer, but got {1} of type {2}.'
            .format(attr, repr(value), type(value).__name__)
        )


def _require_boolean(attr, value):
    if not isinstance(value, bool):
        raise ValidationError(
            'Attribute {0} is of type boolean, but got {1} of type {2}.'
            .format(attr, repr(value), type(value).__name__)
        )


def _require_ip(attr, value):
    try:
        ip_interface(value)
    except ValueError as error:
        raise ValidationError(str(error))


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

            raise CommitValidationFailed(
                'Validation failed. {0}{1}'.format(regexp_msg, required_msg),
                violations_regexp + violations_required,
            )
    if violations_attribs:
        raise CommitValidationFailed(
            'Attributes {0} are not defined on '
            'this servertype. You can\'t skip this validation!'
            .format(', '.join(violations_attribs)),
            violations_regexp + violations_required + violations_attribs,
        )
