from serveradmin.api.decorators import api_function
from serveradmin.graphite.models import NumericCache


@api_function(group='graphite')
def get_numeric_cache(hostname):
    """Get all the numeric cache entries we have for an hostname
    """

    return [{
        'collection': str(n.template.collection),
        'template': str(n.template),
        'value': n.value,
        'last_modified': n.last_modified,
    } for n in NumericCache.objects.filter(hostname=hostname)]
