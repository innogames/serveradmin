from django.urls import path

from serveradmin.powerdns.views import DomainList, RecordList

urlpatterns = [
    path('domains', DomainList.as_view(), name='powerdns_domains'),
    path('records', RecordList.as_view(), name='powerdns_records'),
]
