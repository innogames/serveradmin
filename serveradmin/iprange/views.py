from django.template.response import TemplateResponse
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.contrib.auth.decorators import login_required

from serveradmin.serverdb.models import Segment
from serveradmin.iprange.models import IPRange
from serveradmin.iprange.forms import IPRangeForm

@login_required
def index(request):
    order_field = request.GET.get('order_field',
            request.session.get('iprange_order_field', 'name'))
    order_dir = request.GET.get('order_dir',
            request.session.get('iprange_order_dir', 'asc'))

    if order_field in ('range_id', 'ip_type', 'gateway',
                       'internal_gateway', 'vlan', 'belongs_to__range_id',
                       'gateway6', 'internal_gateway6'):
        request.session['iprange_order_field'] = order_field
        request.session['iprange_order_dir'] = order_dir

        if order_dir == 'desc':
            ordering = '-' + order_field
        else:
            ordering = order_field
    else:
        ordering = 'range_id'

    try:
        segment = Segment.objects.get(segment_id=request.GET['segment'])
    except (KeyError, Segment.DoesNotExist):
        segment = Segment.objects.all()[0]
    ip_ranges = IPRange.objects.filter(segment=segment.segment_id).order_by(
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

    taken_ips = iprange.get_taken_set()
    # Divide IP range into continues blocks
    free_blocks = []
    free_block = []
    if not (iprange.min is None or iprange.max is None):
        for host in iprange.get_network().hosts():
            if host in taken_ips:
                if free_block:
                    free_blocks.append(free_block)
                    free_block = []
            else:
                free_block.append(host)

        if free_block:
            free_blocks.append(free_block)
        num_ips = int(iprange.max) - int(iprange.min) + 1
        num_usable = num_ips - 2
    else:
        num_ips = 0
        num_usable = 0

    return TemplateResponse(request, 'iprange/details.html', {
        'iprange': iprange,
        'free_blocks': free_blocks,
        'num_free_ips': sum([len(block) for block in free_blocks]),
        'num_usable_ips': num_usable,
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
                                   vlan=data['vlan'],
                                   belongs_to=data['belongs_to'],
                                   min=data['start'],
                                   max=data['end'],
                                   gateway=data['gateway'],
                                   internal_gateway=data['internal_gateway'],
                                   min6=data['start6'],
                                   max6=data['end6'],
                                   gateway6=data['gateway6'],
                                   internal_gateway6=data['internal_gateway6'])
            messages.success(request, u'Added IP range "{0}"'.format(
                    data['range_id']))
            return HttpResponseRedirect('{0}?segment={1}'.format(
                    reverse('iprange_index'), data['segment'].segment_id))
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
                    vlan=data['vlan'],
                    belongs_to=data['belongs_to'],
                    min=data['start'],
                    max=data['end'],
                    gateway=data['gateway'],
                    internal_gateway=data['internal_gateway'],
                    min6=data['start6'],
                    max6=data['end6'],
                    gateway6=data['gateway6'],
                    internal_gateway6=data['internal_gateway6'])

            messages.success(request, u'Edited IP range "{0}"'.format(
                    iprange.range_id))

            return HttpResponseRedirect('{0}?segment={1}'.format(
                    reverse('iprange_index'), data['segment'].segment_id))
    else:
        initial = {
                'range_id': iprange.range_id,
                'segment': iprange.segment,
                'ip_type': iprange.ip_type,
                'gateway': iprange.gateway,
                'internal_gateway': iprange.internal_gateway,
                'vlan': iprange.vlan,
                'gateway6': iprange.gateway6,
                'internal_gateway6': iprange.internal_gateway6,
                'belongs_to': iprange.belongs_to,
        }
        cidr = iprange.cidr
        if cidr:
            initial['cidr'] = cidr
        cidr6 = iprange.cidr6
        if cidr6:
            initial['cidr6'] = cidr6
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

@login_required
def chooseip(request):
    if 'range_id' in request.GET:
        iprange = get_object_or_404(IPRange, range_id=request.GET['range_id'])
        return TemplateResponse(request, 'iprange/chooseip_ips.html', {
            'ip_list': sorted(iprange.get_free_set()),
        })
    else:
        return TemplateResponse(request, 'iprange/chooseip_ranges.html', {
            'iprange_list': IPRange.objects.all()
        })

    return TemplateResponse(request, 'iprange/chooseip_ranges.html', {
        'iprange_list': IPRange.objects.all(),
    })
