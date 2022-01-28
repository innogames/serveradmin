from django.urls import path

from . import views

urlpatterns = [
    path('settings/domains', views.domains, name='powerdns.domains'),
    path('settings/records', views.records, name='powerdns.records'),
]
