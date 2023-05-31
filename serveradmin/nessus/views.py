"""Serveradmin - Nessus Integration

Copyright (c) 2023 InnoGames GmbH
"""
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import (
    HttpResponseBadRequest, HttpResponseServerError
)
from django.template.response import TemplateResponse
from django.views.decorators.csrf import ensure_csrf_cookie

from adminapi.filters import Any
from serveradmin.dataset import Query
from serveradmin.nessus.models import NessusAPI

@login_required
@ensure_csrf_cookie
def nessus_config(request):
    """Generate nessus scan configuration page

    :param request:
    :return:
    """

    hostnames = [h for h in request.GET.get('hosts', '').split(', ')]
    object_ids = [o.strip() for o in request.GET.getlist('object_id', []) if o]

    if len(hostnames) == 0 and len(object_ids) == 0:
        return HttpResponseBadRequest('No hostname or object_id provided')

    servers = {s['hostname']: s for s in
               Query({'hostname': Any(*hostnames)}, None)}
    servers.update({s['hostname']: s for s in
                    Query({'object_id': Any(*object_ids)}, None)})

    if request.GET.get('action') == 'Submit':
        user_email = request.GET['email']
        scan_type = request.GET['type']
        try:
            nessus = NessusAPI(username=settings.NESSUS_USER, password=settings.NESSUS_PASSWORD, url=settings.NESSUS_URL)
            policy_id = settings.NESSUS_POLICIES[scan_type]
            uuid = settings.NESSUS_UUID
            folder_id = settings.NESSUS_FOLDER
            ips = [ s['intern_ip'] for s in Query({'hostname': Any(*hostnames)}, None) ]
            scan_ids = nessus.check_if_running(ips)
            if not scan_ids:
                try:
                    nessus.create_scan(scan_name=', '.join(hostnames), uuid=uuid, folder_id=folder_id, target=ips, policy_id=policy_id, receiver=user_email)
                    messages.info(request, str('Scan started.'))
                except Exception as error:
                    messages.error(request, str('Scan could not be started. {}'.format(error)))
            else:
                messages.error(request, str('Scan for at least one of the targets is already running with scan id: {}.'.format(', '.join(scan_ids))))
        except IOError as error:
            return HttpResponseServerError("Communication with nessus failed.")

    return TemplateResponse(request, 'nessus/nessus.html', {
        'hostnames': servers.keys(),
    })
