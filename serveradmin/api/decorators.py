import hashlib
import hmac
import time
from functools import update_wrapper
try:
    import simplejson as json
except ImportError:
    import json

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.contrib.sites.models import RequestSite

from adminapi.utils.json import json_encode_extra
from serveradmin.apps.models import Application, ApplicationException
from serveradmin.api import AVAILABLE_API_FUNCTIONS

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
                    content_type='text/plain')

        try:
            app = Application.objects.get(app_id=app_id)
        except Application.DoesNotExist:
            return HttpResponseForbidden('Invalid application',
                    content_type='text/plain')

        app = get_object_or_404(Application, app_id=app_id)
        real_security_token = _calc_security_token(app.auth_token.encode(
            'utf-8'), str(timestamp), request.body)
        
        expired = timestamp + 300 < time.time()
        if real_security_token != security_token or expired:
            return HttpResponseForbidden('Invalid or expired security token',
                    content_type='text/plain')
        
        if app.restriction_active():
            has_exception = ApplicationException.objects.filter(application=app,
                    granted=True).count()
            if not has_exception:
                domain = RequestSite(request).domain
                full_url = reverse('apps_request_exception', args=[app.app_id])
                exception_url = 'https://{0}{1}'.format(domain, full_url)
                forbidden_text = ('This token is restricted. To get an '
                        'exception go to ' + exception_url)
                return HttpResponseForbidden(forbidden_text,
                        content_type='text/plain')
        
        readonly_views = ('dataset_query', 'api_call')
        if app.readonly and view.__name__ not in readonly_views:
            return HttpResponseForbidden('This token is readonly')


        return_value = view(request, app, json.loads(request.body))
        if getattr(view, 'encode_json', True):
            return_value = json.dumps(return_value, default=json_encode_extra)
        return HttpResponse(return_value, content_type='application/x-json')

    return update_wrapper(_wrapper, view)

def api_function(group, name=None):
    def inner_decorator(fn):
        group_dict = AVAILABLE_API_FUNCTIONS.setdefault(group, {})
        fn_name = fn.__name__ if name is None else name
        group_dict[fn_name] = fn
        return fn
    return inner_decorator
