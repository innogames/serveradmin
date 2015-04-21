from django.conf.urls import patterns, url

urlpatterns = patterns(
    'serveradmin.docs.views',
    url(r'^([a-z0-9-]+)$', 'document', name='docs_document'),
)
