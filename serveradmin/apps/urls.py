from django.conf.urls import patterns, url

urlpatterns = patterns(
    'serveradmin.apps.views',
    url(r'^exc/(\w+)$', 'request_exception', name='apps_request_exception'),
    url(r'^exc_filled$', 'exception_filled', name='apps_exception_filled'),
)
