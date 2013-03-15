from operator import itemgetter

from django import template

from adminapi.utils import IP
from serveradmin.dataset.base import lookups

register = template.Library()

def _to_ip(val):
    if not isinstance(val, IP):
        val = IP(val)
    return val.as_ip()

def _format(attr_type, value, multi=False):
    if multi:
        if attr_type == 'ip':
            return [_to_ip(val) for val in value]
        else:
            return [unicode(val) for val in value]
    else:
        if attr_type == 'ip':
            return _to_ip(value)
        else:
            return unicode(value)

@register.inclusion_tag('dataset/format_server.html')
def format_server(server_obj):
    """Render a serverobject with all attributes as HTML"""
    attr_names = lookups.attr_names
    
    server_items = []
    for attr_name, attr_value in server_obj.iteritems():
        try:
            attr_type = attr_names[attr_name].type
            attr_multi = attr_names[attr_name].multi
            
            value = _format(attr_type, attr_value, multi=attr_multi)
            entry = {
                'attr': attr_name,
                'multi': attr_multi,
                'value': value
            }
        except KeyError:
            entry = {
                'attr': attr_name,
                'multi': False,
                'value': unicode(attr_value)
            }
        server_items.append(entry)
        server_items.sort(key=itemgetter('attr'))

    return {
        'server_items': server_items
    }

@register.inclusion_tag('dataset/format_changes.html')
def format_changes(changes):
    attr_names = lookups.attr_names
    
    for attr_name, change in changes.iteritems():
        attr_type = attr_names[attr_name].type
        change['attr'] = attr_name
        
        if change['action'] == 'multi':
            change['add'] = _format(attr_type, change['add'], multi=True)
            change['remove'] = _format(attr_type, change['remove'], multi=True)
        else:
            if 'new' in change:
                change['new'] = _format(attr_type, change['new'])
            if 'old' in change:
                change['old'] = _format(attr_type, change['old'])

    return {'changes': changes.itervalues()}

