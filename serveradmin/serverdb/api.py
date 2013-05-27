from serveradmin.api.decorators import api_function
from serveradmin.serverdb.models import ServerType, Segment
from serveradmin.dataset.base import lookups

@api_function(group='dataset')
def get_servertypes():
    """Returns a list of available servertypes"""
    return [stype.name for stype in ServerType.objects.all()]

@api_function(group='dataset')
def get_segments():
    """Returns a list of available segments"""
    return [seg.segment for seg in Segment.objects.all()]

@api_function(group='dataset')
def get_attribute_info(servertype_name, attr_name):
    """Returns default value for an attribute"""
    try:
        return _get_stype_attr_dict(servertype_name, attr_name)
    except KeyError:
        raise ValueError('Invalid servertype/attr combination: {0}/{1}'.format(
                servertype_name, attr_name))

@api_function(group='dataset')
def get_servertype_attributes_info(servertype_name):
    """Returns the attribute info for each attribute on a servertype"""
    result = {}

    try:
        stype =  lookups.stype_names[servertype_name]
    except KeyError:
        raise ValueError('Invalid servertype: {0}'.format(servertype_name))

    for attribute in stype.attributes:
        result[attribute.name] = _get_stype_attr_dict(
                servertype_name, attribute.name)

    return result

def _get_stype_attr_dict(servertype_name, attr_name):
    index = (servertype_name, attr_name)
    stype = lookups.stype_attrs[index]
    return {
        'default': stype.default,
        'required': stype.required,
        'regexp': stype.regexp.pattern if stype.regexp else None
    }
