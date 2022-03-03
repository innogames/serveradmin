from django.contrib import admin

from serveradmin.apps.models import Application, PublicKey


class PublicKeyInline(admin.TabularInline):
    """Inline Form for Public Keys

    PublicKey are always bundled to an application. It makes little sense to
    create them separately and then chose the application from a dropdown
    inside the PublicKey form. This allows us to edit PublicKeys inside the
    Applications admin form.
    """
    model = PublicKey


class ApplicationAdmin(admin.ModelAdmin):
    readonly_fields = [
        'auth_token',
        'last_login',
    ]

    list_display = [
        'name',
        'owner',
        'auth_token',
        'get_public_keys',
        'superuser',
        'disabled',
        'last_login',
    ]

    inlines = [
        PublicKeyInline
    ]

    @admin.display(description='Public Keys')
    def get_public_keys(self, obj):
        return list(obj.public_keys.all())

    def has_delete_permission(self, request, obj=None):
        # We don't want the applications to be deleted but disabled.
        # Deleting cause the history related with them to go away.
        return False

    def get_actions(self, request):
        actions = super(ApplicationAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('public_keys')


admin.site.register(Application, ApplicationAdmin)
