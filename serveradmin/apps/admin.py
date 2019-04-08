from django.contrib import admin

from serveradmin.apps.models import Application, PublicKey


class PublicKeyInline(admin.TabularInline):
    model = PublicKey


class ApplicationAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'owner',
        'auth_token',
        'get_public_keys',
        'superuser',
        'disabled',
    ]

    inlines = [
        PublicKeyInline
    ]

    def get_public_keys(self, obj):
        return list(obj.public_keys.all())
    get_public_keys.short_description = 'Public Keys'

    def has_delete_permission(self, request, obj=None):
        # We don't want the applications to be deleted but disabled.
        # Deleting cause the history related with them to go away.
        return False

    def get_actions(self, request):
        actions = super(ApplicationAdmin, self).get_actions(request)
        del actions['delete_selected']
        return actions


admin.site.register(Application, ApplicationAdmin)
