from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def logo():
    if getattr(settings, 'IS_SECONDARY', False):
        return settings.STATIC_URL + 'logo_innogames_bigbulb_120_warn.png'
    else:
        return settings.STATIC_URL + 'logo_innogames_bigbulb_120.png'
