from datetime import timezone

from django import template

register = template.Library()


@register.filter
def field_to_str(field: dict) -> str:
    """Get field value string representation

    We have a custom string representation for some types that should be
    uniform in all views edit, inspect, servershell as well as in the command
    line interface.

    :param field:
    :return:
    """

    if field['multi']:
        values = list()
        for value in field['value']:
            values.append(value_to_str(value, field['type']))

        return '\n'.join(values)

    return value_to_str(field['value'], field['type'])


@register.filter
def value_to_str(value, field_type) -> str:
    """Get value string representation

    Similar to field_to_str but returns the string representation directly
    for a value.

    :param value:
    :param field_type:
    :return:
    """

    if field_type == 'datetime':
        if value.tzinfo is None:
            value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S%z')
    elif field_type == 'boolean':
        return str(value).lower()

    return str(value)
