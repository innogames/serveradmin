import urllib2
import socket

from django.template.response import TemplateResponse
from django.http import (HttpResponse, HttpResponseRedirect,
        HttpResponseForbidden, HttpResponseServerError)
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm

from serveradmin.serverdb.models import Attribute

def failoverlogin(request):
    if not getattr(settings, 'IS_SECONDARY', False):
        return HttpResponseForbidden()

    try:
        urllib2.urlopen(settings.PRIMARY_CHECK_URL, timeout=1)
    except (socket.timeout, socket.error, urllib2.URLError):
        pass
    else:
        error_msg = "Primary server is up, therefore login isn't allowed here."
        return HttpResponseForbidden(error_msg)

    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user and user.is_active and user.is_superuser:
                login(request, user)
                return HttpResponseRedirect('/')
    else:
        form = AuthenticationForm()

    request.session.set_test_cookie()

    return TemplateResponse(request, 'failoverlogin.html', {
        'form': form,
    })

def check(request):
    # Doing two database query against most important databases
    try:
        Attribute.objects.all()[0]
    except Exception:
        return HttpResponseServerError('FAILURE')
    return HttpResponse('OK')
