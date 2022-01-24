from django.urls import path

from . import views

urlpatterns = [
    path('settings', views.domains, name='powerdns.domains'),
]
