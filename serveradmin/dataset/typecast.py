from netaddr import EUI

from django.core.exceptions import ValidationError


_typecast_fns = {
    'boolean': lambda x: x in ('1', 'True', 'true', 1, True),
    'string': str,
    'hostname': str,
    'reverse_hostname': str,
    'number': lambda x: float(x) if '.' in str(x) else int(x),
    'inet': str,
    'macaddr': EUI,
    'date': str,
    'supernet': str,
}


def typecast(attribute, value, force_single=False):
    if value is None:
        return value

    multi = attribute.multi and not force_single
    if multi and not isinstance(value, (list, set)):
        raise ValidationError('Attr is multi, but value is not a list/set')

    typecast_fn = _typecast_fns[attribute.type]
    try:
        if multi:
            return set(typecast_fn(x) for x in value)
        return typecast_fn(value)
    except ValueError as error:
        raise ValidationError(str(error))
