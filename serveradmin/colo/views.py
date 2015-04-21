# -*- coding: utf-8 -*-
import os
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse

datacenters = {
    'af': 'Süderstraße',
    'aw': 'Wendenstraße',
}

@login_required
def index(request):
    content = ''
    for file_name in os.listdir(settings.COLO_DATADIR):
        code = file_name[:-5]
        content += '<h2>' + datacenters[code] + ' (' + code + ')</h2>'

        with open(settings.COLO_DATADIR + '/' + file_name) as f:
            content += f.read()

    return TemplateResponse(request, 'colo/index.html', {
        'content': content
    })
