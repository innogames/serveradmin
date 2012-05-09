import hashlib
import hmac
import json
import time
from functools import update_wrapper

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from adminapi.utils import json_encode_extra
from serveradmin.apps.models import Application

def _calc_security_token(auth_token, timestamp, content):
    message = ':'.join((str(timestamp), content))
    return hmac.new(auth_token, message, hashlib.sha1).hexdigest()

def api_view(view):
    @csrf_exempt
    def _wrapper(request):
        try:
            app_id = request.META['HTTP_X_APPLICATION']
            timestamp = int(request.META['HTTP_X_TIMESTAMP'])
            security_token = request.META['HTTP_X_SECURITYTOKEN']
        except (KeyError, ValueError):
            return HttpResponseBadRequest('Invalid API request',
                    mimetype='text/plain')

        app = get_object_or_404(Application, app_id=app_id)
        real_security_token = _calc_security_token(app.auth_token.encode(
            'utf-8'), str(timestamp), request.body)
        
        expired = timestamp + 300 < time.time()
        if real_security_token != security_token or expired:
            return HttpResponseForbidden('Invalid or expired security token',
                    mimetype='text/plain')
        return_value = view(request, app, json.loads(request.body))
        return HttpResponse(json.dumps(return_value, default=json_encode_extra),
                mimetype='application/x-json')

    return update_wrapper(_wrapper, view)
