# -*- coding: utf-8 -*-
import os
import re
import json
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse
from django.core.exceptions import PermissionDenied

@login_required
def index(request):
    return TemplateResponse(request, 'colo/index.html')

@login_required
def plan(request, cololoc):
    colofile = os.path.join(settings.COLO_DATADIR, cololoc + '.html')
    with open(colofile) as f:
        content = f.read() 

    coloname = ''
    if cololoc == 'suderstrasse':
        coloname = 'Süderstrasse - AF'
    elif cololoc == 'wendenstrasse':
        coloname = 'Wendenstrasse - AW'

    return TemplateResponse(request, 'colo/plan.html', {
        'cololoc': cololoc,
        'coloname': coloname,
        'content': content
    })
