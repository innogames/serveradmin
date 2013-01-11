from django.template.response import TemplateResponse
from django.shortcuts import get_object_or_404
from django.db import connection
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.contrib.auth.decorators import login_required

from adminapi.utils import IP
from serveradmin.dataset.base import lookups
from serveradmin.dataset.models import Segment
from serveradmin.dataset.querybuilder import QueryBuilder
from serveradmin.dataset import filters
from serveradmin.iprange.models import IPRange
from serveradmin.iprange.forms import IPRangeForm

@login_required
def index(request):
    order_field = request.GET.get('order_field',
            request.session.get('iprange_order_field', 'name'))
    order_dir = request.GET.get('order_dir',
            request.session.get('iprange_order_dir', 'asc'))

    if order_field in ('range_id', 'ip_type', 'min', 'max', 'gateway'):
        request.session['iprange_order_field'] = order_field
        request.session['iprange_order_dir'] = order_dir

        if order_dir == 'desc':
            ordering = '-' + order_field
        else:
            ordering = order_field
    else:
        ordering = 'range_id'

    try:
        segment = Segment.objects.get(segment=request.GET['segment'])
    except (KeyError, Segment.DoesNotExist):
        segment = Segment.objects.all()[0]
    ip_ranges = IPRange.objects.filter(segment=segment.segment).order_by(
            ordering)

    return TemplateResponse(request, 'iprange/index.html', {
        'order_field': order_field,
        'order_dir': order_dir,
        'ip_ranges': ip_ranges,
        'displayed_segment': segment,
        'segments': Segment.objects.all()
    })

@login_required
def details(request, range_id):
    iprange = get_object_or_404(IPRange, range_id=range_id)
    
    # Query taken IPs
    f_between = filters.Between(iprange.min, iprange.max)
    builder = QueryBuilder()
    builder.add_attribute('all_ips')
    builder.add_filter('all_ips', f_between)
    fields = lookups.attr_names['all_ips'].special.attrs
    builder.add_select(*fields)
    
    # Collect taken IPs in set
    taken_ips = set()
    c = connection.cursor()
    c.execute(builder.build_sql())
    for ip_tuple in c.fetchall():
        for ip in ip_tuple:
            if ip is not None:
                taken_ips.add(int(ip))
    
    # Divide IP range into continues blocks
    free_blocks = []
    free_block = []
    for ip_int in xrange(iprange.min.as_int() + 1, iprange.max.as_int()):
        if ip_int in taken_ips:
            if free_block:
                free_blocks.append(free_block)
                free_block = []
        else:
            free_block.append(IP(ip_int))
    if free_block:
        free_blocks.append(free_block)

    num_ips = iprange.max.as_int() - iprange.min.as_int() + 1
    return TemplateResponse(request, 'iprange/details.html', {
        'iprange': iprange,
        'free_blocks': free_blocks,
        'num_free_ips': sum([len(block) for block in free_blocks]),
        'num_usable_ips': num_ips - 2,
        'num_ips': num_ips
    })

@login_required
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
            return HttpResponseRedirect('{0}?segment={1}'.format(
                    reverse('iprange_index'), data['segment'].segment))
    else:
        form = IPRangeForm()

    return TemplateResponse(request, 'iprange/add_edit.html', {
        'form': form
    })

@login_required
def edit(request, range_id):
    iprange = get_object_or_404(IPRange, range_id=range_id)

    if request.method == 'POST':
        form = IPRangeForm(request.POST, iprange=iprange)
        if form.is_valid():
            data = form.cleaned_data
            IPRange.objects.filter(range_id=iprange.range_id).update(
                    range_id=data['range_id'],
                    segment=data['segment'],
                    ip_type=data['ip_type'],
                    min=data['start'],
                    max=data['end'],
                    gateway=data['gateway'])
            messages.success(request, u'Edited IP range "{0}"'.format(
                    iprange.range_id))
            return HttpResponseRedirect('{0}?segment={1}'.format(
                    reverse('iprange_index'), data['segment'].segment))
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

@login_required
def delete(request, range_id):
    iprange = get_object_or_404(IPRange, range_id=range_id)
    if request.method == 'POST':
        iprange.delete()
        return HttpResponseRedirect('{0}?segment={1}'.format(
                reverse('iprange_index'), iprange.segment))
    
    return TemplateResponse(request, 'iprange/delete.html', {
        'iprange': iprange
    })
