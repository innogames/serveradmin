# -*- coding: utf-8 -*-
import os
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse

datacenters = {
    'af': 'Süderstraße S108.1',
    'aw.1': 'Wendenstraße W408.1',
    'aw.2': 'Wendenstraße W408.2',
}

@login_required
def index(request):
    content = ''
    for colo in datacenters:
        content += '<h2>' + colo + ' (' + datacenters[colo] + ')</h2>'

        with open(settings.COLO_DATADIR + '/' + colo + '.html') as f:
            content += f.read()

    return TemplateResponse(request, 'colo/index.html', {
        'content': content
    })
