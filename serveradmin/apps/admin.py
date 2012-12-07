from django.contrib import admin

from serveradmin.apps.models import Application, ApplicationException

class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'author', 'location', 'auth_token', 'restricted')

admin.site.register(Application, ApplicationAdmin)
admin.site.register(ApplicationException)
