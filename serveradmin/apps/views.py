from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse
from django import forms

from serveradmin.apps.models import Application, ApplicationException

@login_required
def request_exception(request, app_id):
    app = get_object_or_404(Application, app_id=app_id)

    class ExceptionForm(forms.ModelForm):
        class Meta:
            model = ApplicationException
            fields = ('issue', 'changes', 'tested')
        carefully = forms.BooleanField()
    
    if request.method == 'POST':
        form = ExceptionForm(request.POST)
        if form.is_valid():
            exc = form.save(commit=False)
            exc.application = app
            exc.user = request.user
            exc.save()
            return redirect('apps_exception_filled')
    else:
        form = ExceptionForm()

    return TemplateResponse(request, 'apps/request_exception.html', {
        'app': app,
        'form': form
    })

@login_required
def exception_filled(request):
    return TemplateResponse(request, 'apps/exception_filled.html', {})
