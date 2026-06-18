from datetime import timezone

from django import template
from django.utils.safestring import mark_safe
from django.utils.html import escape

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
def link_to_object(value, field_type) -> str:
    """If the given object is a reference to another object,
    create a link to the inspection page


    :param value:
    :param field_type:
    :return:
    """
    if field_type not in ['relation', 'reverse']:
        return value

    hostname = escape(value)

    return mark_safe(f'<a href="/servershell/inspect?hostname={hostname}">{hostname}</a>')


@register.filter
def value_to_str(value, field_type) -> str:
    """Get value string representation

    Similar to field_to_str but returns the string representation directly
    for a value.

    :param value:
    :param field_type:
    :return:
    """

    # @TODO Maybe we can use ServerAttribute models and __str__ method here
    def conversion_datetime(value):
        if value.tzinfo is None:
            value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S%z')

    conversions = {
        'datetime': conversion_datetime,
        'boolean': lambda v: str(v).lower(),
    }

    conv = conversions.get(field_type)
    if conv is None:
        return str(value)

    return conv(value)
