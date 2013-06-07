from django.template.response import TemplateResponse
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm

def failoverlogin(request):
    if not getattr(settings, 'IS_SECONDARY', False):
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            print user
            if user and user.is_active and user.is_superuser:
                login(request, user)
                return HttpResponseRedirect('/')
    else:
        form = AuthenticationForm()
    
    request.session.set_test_cookie()
    
    return TemplateResponse(request, 'failoverlogin.html', {
        'form': form,
    })
