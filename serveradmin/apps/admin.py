from django.contrib import admin

from serveradmin.apps.models import Application

class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'author', 'location', 'auth_token')

admin.site.register(Application, ApplicationAdmin)
