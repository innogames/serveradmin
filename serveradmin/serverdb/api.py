from serveradmin.api.decorators import api_function
from serveradmin.serverdb.models import ServerType, Segment

@api_function(group='dataset')
def get_servertypes():
    """Returns a list of available servertypes"""
    return [stype.name for stype in ServerType.objects.all()]

@api_function(group='dataset')
def get_segments():
    """Returns a list of available segments"""
    return [seg.segment for seg in Segment.objects.all()]
