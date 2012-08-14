from django.template.response import TemplateResponse
from django.shortcuts import get_object_or_404
from django.db import connection

from adminapi.utils import IP
from serveradmin.dataset.models import Segment
from serveradmin.dataset.querybuilder import QueryBuilder
from serveradmin.dataset import filters
from serveradmin.iprange.models import IPRange

def index(request):
    try:
        segment = Segment.objects.get(segment=request.GET['segment'])
    except (KeyError, Segment.DoesNotExist):
        segment = Segment.objects.all()[0]
    ip_ranges = IPRange.objects.filter(segment=segment.segment)

    return TemplateResponse(request, 'iprange/index.html', {
        'ip_ranges': ip_ranges,
        'displayed_segment': segment,
        'segments': Segment.objects.all()
    })

def details(request, range_id):
    iprange = get_object_or_404(IPRange, range_id=range_id)
    
    # Query taken IPs
    f_between = filters.Between(iprange.min, iprange.max)
    builder = QueryBuilder()
    builder.add_attribute('all_ips')
    builder.add_filter('all_ips', f_between)
    builder.add_select('intern_ip', 'additional_ips')
    
    # Collect taken IPs in set
    taken_ips = set()
    c = connection.cursor()
    c.execute(builder.build_sql())
    for intern_ip, add_ip in c.fetchall():
        if intern_ip is not None:
            taken_ips.add(intern_ip)
        if add_ip is not None:
            taken_ips.add(int(add_ip))
    
    # Divide IP range into continues blocks
    free_blocks = []
    free_block = []
    usable_ips = 0
    for ip_int in xrange(iprange.min.as_int(), iprange.max.as_int() + 1):
        if ip_int & 0xff in (0, 255):
            continue
        
        usable_ips += 1
        if ip_int in taken_ips:
            if free_block:
                free_blocks.append(free_block)
                free_block = []
        else:
            free_block.append(IP(ip_int))
    if free_block:
        free_blocks.append(free_block)


    return TemplateResponse(request, 'iprange/details.html', {
        'iprange': iprange,
        'free_blocks': free_blocks,
        'num_free_ips': sum([len(block) for block in free_blocks]),
        'num_usable_ips': usable_ips,
        'num_ips': iprange.max.as_int() - iprange.min.as_int() + 1
    })
