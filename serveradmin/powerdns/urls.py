from django.conf.urls import url

from serveradmin.powerdns.views import DomainList, RecordList

urlpatterns = [
    url(r'^domains$', DomainList.as_view(), name='powerdns_domains'),
    url(r'^records$', RecordList.as_view(), name='powerdns_records'),
]
