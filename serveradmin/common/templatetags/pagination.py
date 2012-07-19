from django import template
from urlparse import parse_qsl
from urllib import urlencode

register = template.Library()

@register.inclusion_tag('pagination.html', takes_context=True)
def pagination(context, page, pagination_id=None):
    request = context['request']
    url = request.path
    qs = parse_qsl(request.META['QUERY_STRING'])
    new_qs = [(key, value) for key, value in qs if key != 'page']
    if new_qs:
        sep = '&amp;'
        url += urlencode(new_qs)
    else:
        sep = '?'

    return {
        'page': page,
        'paginator': page.paginator,
        'pagination_id': pagination_id,
        'url': url,
        'sep': sep
    }
