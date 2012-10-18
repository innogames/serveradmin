from __future__ import division

from colorsys import hsv_to_rgb

from django import template

register = template.Library()

@register.simple_tag
def format_percent(value, range_start, range_end, range_diff):
    if value is None:
        return u'<div>unknown</div>'
    if value < range_start:
        return u'<div>{0}&nbsp;%</div>'.format(value)

    hue_start = 0
    hue_end = 0.40
    sat = 0.4
    val = 1.0

    part = 1 - ((value - range_start) / range_diff)
    part = min(max(part, 0), 1.0)

    hue = part * (hue_end - hue_start) + hue_start
    r, g, b = hsv_to_rgb(hue, sat, val)
    r, g, b = int(r * 255), int(g * 255), int(b * 255)

    return (u'<div style="background:rgb({r}, {g}, {b});">'
            '{value}&nbsp;%</div>').format(r=r, g=g, b=b, value=value)
