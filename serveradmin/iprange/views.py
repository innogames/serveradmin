from django.template.response import TemplateResponse
from django.shortcuts import get_object_or_404, redirect
from django.db import connection
from django.contrib import messages

from adminapi.utils import IP
from serveradmin.dataset.models import Segment
from serveradmin.dataset.querybuilder import QueryBuilder
from serveradmin.dataset import filters
from serveradmin.iprange.models import IPRange
from serveradmin.iprange.forms import IPRangeForm

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

def add(request):
    if request.method == 'POST':
        form = IPRangeForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            IPRange.objects.create(range_id=data['range_id'],
                                   segment=data['segment'],
                                   ip_type=data['ip_type'],
                                   min=data['start'],
                                   max=data['end'],
                                   next_free=data['start'],
                                   gateway=data['gateway'])
            messages.success(request, u'Added IP range "{0}"'.format(
                    data['range_id']))
            return redirect('iprange_index')
    else:
        form = IPRangeForm()

    return TemplateResponse(request, 'iprange/add_edit.html', {
        'form': form
    })

def edit(request, range_id):
    iprange = get_object_or_404(IPRange, range_id=range_id)

    if request.method == 'POST':
        form = IPRangeForm(request.POST, iprange=iprange)
        if form.is_valid():
            iprange.range_id = form.cleaned_data['range_id']
            iprange.segment = form.cleaned_data['segment']
            iprange.ip_type = form.cleaned_data['ip_type']
            iprange.min = form.cleaned_data['start']
            iprange.max = form.cleaned_data['end']
            iprange.gateway = form.cleaned_data['gateway']
            iprange.save()
            messages.success(request, u'Edited IP range "{0}"'.format(
                    iprange.range_id))
            return redirect('iprange_index')
    else:
        initial = {'range_id': iprange.range_id, 'segment': iprange.segment,
                   'ip_type': iprange.ip_type, 'gateway': iprange.gateway}
        cidr = iprange.cidr
        if cidr:
            initial['cidr'] = cidr
        else:
            initial['start'] = iprange.min
            initial['end'] = iprange.max
        form = IPRangeForm(initial=initial)

    return TemplateResponse(request, 'iprange/add_edit.html', {
        'form': form,
        'edit': True
    })

def delete(request, range_id):
    iprange = get_object_or_404(IPRange, range_id=range_id)
    if request.method == 'POST':
        iprange.delete()
        return redirect('iprange_index')
    
    return TemplateResponse(request, 'iprange/delete.html', {
        'iprange': iprange
    })
