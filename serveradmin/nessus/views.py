"""Serveradmin - Nessus Integration

Copyright (c) 2023 InnoGames GmbH
"""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseServerError
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

    object_ids = request.GET.getlist("object_id", [])
    email = request.user.email

    if request.GET.get("action") == "Start Scan":
        email = request.GET["email"]
        scan_type = request.GET["type"]
        hostnames = request.GET["hosts"].replace(", ", " ").replace(",", " ").split(" ")
        try:
            nessus = NessusAPI(
                username=settings.NESSUS_USER,
                password=settings.NESSUS_PASSWORD,
                url=settings.NESSUS_URL,
            )
            policy_id = settings.NESSUS_POLICIES[scan_type]
            uuid = settings.NESSUS_UUID
            folder_id = settings.NESSUS_FOLDER
            ips = [
                s["intern_ip"]
                for s in Query({"hostname": Any(*hostnames)}, ["intern_ip"])
            ]
            scan_ids = nessus.check_if_running(ips)
            if not scan_ids:
                try:
                    nessus.create_scan(
                        scan_name=", ".join(hostnames),
                        uuid=uuid,
                        folder_id=folder_id,
                        target=ips,
                        policy_id=policy_id,
                        receiver=email,
                    )
                    messages.info(request, "Scan started.")
                except Exception as error:
                    messages.error(request, "Scan could not be started. %s" % (error))
            else:
                messages.error(
                    request,
                    "Scan for at least one of the targets is already running with scan id: %s."
                    % (", ".join(scan_ids)),
                )
        except IOError as error:
            return HttpResponseServerError("Communication with nessus failed.")
    else:
        if len(object_ids) == 0:
            return HttpResponseBadRequest("No hostname or object_id provided")

        servers = Query({"object_id": Any(*object_ids)}, ["hostname", "intern_ip"])
        hostnames = [s["hostname"] for s in servers]
        for server in servers:
            if not server["intern_ip"]:
                return HttpResponseBadRequest(
                    "Submitted object does not have intern_ip"
                )

    return TemplateResponse(
        request, "nessus/nessus.html", {"hostnames": hostnames, "email": email}
    )
