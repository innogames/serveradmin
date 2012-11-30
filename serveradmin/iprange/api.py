from adminapi.utils import IP
from serveradmin.api.decorators import api_function
from serveradmin.api import ApiError
from serveradmin.dataset import DatasetError
from serveradmin.iprange.models import IPRange

@api_function(group='ip')
def get_free(range_id, reserve_ip=True):
    """Return a free IP address.

    If ``reserve_ip`` is set to ``True`` it will return a different IP
    on the next call unless all other IPs are used. This can be used
    to reserve the IP so other scripts won't get the returned IP if
    you haven't added a server with this IP yet.
    """
    try:
        r = IPRange.objects.get(range_id=range_id)
        return r.get_free(increase_pointer=reserve_ip).as_ip()
    except IPRange.DoesNotExist:
        raise ApiError('No such IP range')
    except DatasetError, e:
        raise ApiError(e.message)

@api_function(group='ip')
def get_multiple_free(range_id, num_free=1):
    """Return ``num_free`` free IP addresses as a list.
    """
    try:
        r = IPRange.objects.get(range_id=range_id)
    except IPRange.DoesNotExist:
        raise ApiError('No such IP range')
    
    try:
        free_ips = set()
        for i in xrange(num_free):
            free_ip = r.get_free(increase_pointer=True).as_ip()
            if free_ip in free_ips:
                raise ApiError('Not enough free IPs available')
            free_ips.add(free_ip)
        return list(free_ips)
    except DatasetError, e:
        raise ApiError(e.message)

@api_function(group='ip')
def get_range(range_id):
    """Return range with given range_id.

    The range is a dictionary with the following keys:

    range_id
       Given range_id
    segment
       Segment of the range (af01 etc.)
    type
       The type of the range (either 'public' or 'private')
    min
       Minimum IP of this range
    max
       Maximum IP of this range
    gateway
       Gateway IP of this range
    """
    try:
        r = IPRange.objects.get(range_id=range_id)
    except IPRange.DoesNotExist:
        raise ApiError('No such IP range')
    
    return _build_range_object(r)

@api_function(group='ip')
def get_ranges(range_ids=None):
    """Return requested ranges. If no range ids are given, return all ranges.
    
    The return value is a list of range objects. See ip.get_range for
    description of a range object.
    """
    if range_ids is None:
        range_objects = IPRange.objects.all()
    else:
        range_objects = IPRange.objects.filter(range_id__in=range_ids)

    return [_build_range_object(r) for r in range_objects]

@api_function(group='ip')
def get_matching_ranges(ip):
    """Return the IP range(s) that belong to the given IP.
    
    See ip.get_range for description of the range object
    """
    ip_int = IP(ip).as_int()
    range_objects =  IPRange.objects.filter(min__lte=ip_int, max__gte=ip_int)
    return [_build_range_object(r) for r in range_objects]

def _build_range_object(r):
    return {
        'range_id': r.range_id,
        'segment': r.segment,
        'type': 'private' if r.ip_type == 'ip' else 'public',
        'min': r.min,
        'max': r.max,
        'gateway': r.gateway
    }
