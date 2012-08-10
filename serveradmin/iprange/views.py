from django.template.response import TemplateResponse
from django.shortcuts import get_object_or_404

from serveradmin.dataset.models import Segment
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

def details(request, iprange_name):
    iprange = get_object_or_404(IPRange, name=iprange_name)

    return TemplateResponse(request, 'iprange/details.html', {
        'iprange': iprange
    })
