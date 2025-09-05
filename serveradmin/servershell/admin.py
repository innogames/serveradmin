from django.contrib import admin

from serveradmin.servershell.models import AttributeSelection


class AttributeSelectionAdmin(admin.ModelAdmin):
    pass


admin.site.register(AttributeSelection, AttributeSelectionAdmin)
