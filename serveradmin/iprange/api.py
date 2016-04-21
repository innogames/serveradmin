from ipaddress import IPv4Address, IPv6Address

from serveradmin.api.decorators import api_function
from serveradmin.api import ApiError
from serveradmin.dataset import DatasetError
from serveradmin.iprange.models import IPRange, get_gateways, get_gateways6, _get_network_settings, _get_network_settings6, _get_iprange_settings

@api_function(group='ip')
def get_free(range_id, reserve_ip=True):
    """Return a free IP address

    XXX reserve_ip argument is not used anymore.
    """
    free_addresses = get_free_set(range_id)
    if not free_addresses:
        raise ApiError('No more free addresses')

    for address in free_addresses:
        return address

@api_function(group='ip')
def get_free_set(range_id):
    """Return all free IPs"""
    try:
        iprange = IPRange.objects.get(range_id=range_id)
    except IPRange.DoesNotExist:
        raise ApiError('No such IP range')

    return iprange.get_free_set()

@api_function(group='ip')
def get_taken_set(range_id):
    """Return all taken IPs"""
    try:
        iprange = IPRange.objects.get(range_id=range_id)
    except IPRange.DoesNotExist:
        raise ApiError('No such IP range')

    return iprange.get_taken_set()

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
       Default Gateway IP of this range
    internal_gateway
       Internal (10.0.0.0/8) gateway of this range
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
def get_ranges_by_type(segment, type):
    """Return ranges by segment and type. Possible types: 'private', 'public'.

    The return value is a list of range objects. See ip.get_range for
    description of a range object.
    """

    type = {'private': 'ip', 'public': 'public_ip'}.get(type, type)
    range_objects = IPRange.objects.filter(segment=segment, ip_type=type)
    return [_build_range_object(r) for r in range_objects]

@api_function(group='ip')
def get_matching_ranges(ip_string):
    """Return the IP range(s) that belong to the given IP.

    See ip.get_range for description of the range object
    """

    ip_addr = IPv4Address(ip_string)
    range_objects = IPRange.objects.filter(min__lte=ip_addr, max__gte=ip_addr)
    return [_build_range_object(r) for r in range_objects]

@api_function(group='ip')
def get_matching_ranges6(ipv6):
    """Return the IP range(s) that belong to the given IP.

    See ip.get_range for description of the range object
    """

    ip = IPv6Address(ipv6)
    range_objects =  IPRange.objects.filter(min6__lte=ip, max6__gte=ip)
    return [_build_range_object(r) for r in range_objects]

def _build_range_object(r):
    belongs_to = r.belongs_to.range_id if r.belongs_to else None
    return {
        'range_id': r.range_id,
        'segment': str(r.segment),
        'type': 'private' if r.ip_type == 'ip' else 'public',
        'min': r.min,
        'max': r.max,
        'gateway': r.gateway,
        'internal_gateway': r.internal_gateway,
        'min6': r.min6,
        'max6': r.max6,
        'gateway6': r.gateway6,
        'internal_gateway6': r.internal_gateway6,
        'belongs_to': belongs_to,
        'vlan': r.vlan
    }

@api_function(group='ip')
def get_gateway(ip):
    return get_gateways(IPv4Address(ip))

@api_function(group='ip')
def get_gateway6(ip):
    return get_gateways6(IPv6Address(ip))

@api_function(group='ip')
def get_network_settings(ip):
    return _get_network_settings(IPv4Address(ip))

@api_function(group='ip')
def get_network_settings6(ip):
    return _get_network_settings6(IPv6Address(ip))

@api_function(group='ip')
def get_iprange_settings(name):
    return _get_iprange_settings(name)
