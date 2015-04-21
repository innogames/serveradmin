import os
import re
import json
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse
from django.core.exceptions import PermissionDenied

@login_required
def document(request, docname):
    if not re.match('^[a-z0-9-]+$', docname):
        raise PermissionDenied()
    docfile = os.path.join(settings.DOCUMENTATION_DATADIR, docname + '.fjson')
    with open(docfile) as f:
        document = json.load(f)
    return TemplateResponse(request, 'docs/document.html', {
        'document': document
    })
