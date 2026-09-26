from django.contrib import admin, messages

from serveradmin.apps.models import Application, PublicKey
from serveradmin.common.utils import random_alnum_string


class PublicKeyInline(admin.TabularInline):
    """Inline Form for Public Keys

    PublicKey are always bundled to an application. It makes little sense to
    create them separately and then chose the application from a dropdown
    inside the PublicKey form. This allows us to edit PublicKeys inside the
    Applications admin form.
    """
    model = PublicKey


class ApplicationAdmin(admin.ModelAdmin):

    list_display = [
        'name',
        'owner',
        'auth_token',
        'get_public_keys',
        'superuser',
        'disabled',
        'last_login',
    ]
    search_fields = ['name', 'owner__username', ]
    list_filter = ['superuser', 'disabled', ]
    list_select_related = ['owner', ]

    readonly_fields = [
        'auth_token',
        'last_login',
    ]
    autocomplete_fields = ['owner']
    inlines = [
        PublicKeyInline
    ]
    actions = [
        'generate_auth_token',
        'revoke_auth_token',
    ]

    @admin.action(
        description='Generate auth token for applications without one',
        permissions=['change'],
    )
    def generate_auth_token(self, request, queryset):
        """Give a random auth token to every selected application without one

        Applications that already have a token are left untouched so the
        action never rotates a credential that is in use. Revoke first if you
        want a fresh token.
        """
        generated = 0
        skipped = 0
        for app in queryset:
            if app.auth_token:
                skipped += 1
                continue
            app.auth_token = random_alnum_string(24)
            # save() triggers the pre_save signal which derives app_id
            app.save()
            generated += 1

        if generated:
            self.message_user(
                request, f'Generated auth token for {generated} application(s).',
                messages.SUCCESS,
            )
        if skipped:
            self.message_user(
                request,
                f'Skipped {skipped} application(s) that already have a token.',
                messages.WARNING,
            )

    @admin.action(
        description='Revoke auth token (public keys keep working)',
        permissions=['change'],
    )
    def revoke_auth_token(self, request, queryset):
        """Remove the auth token from the selected applications

        Clients using the token get "Application has no auth token" from
        the API afterwards. Public key authentication is unaffected.
        """
        revoked = 0
        for app in queryset:
            if not app.auth_token:
                continue
            app.auth_token = None
            # save() triggers the pre_save signal which clears app_id
            app.save()
            revoked += 1

        self.message_user(
            request, f'Revoked auth token of {revoked} application(s).',
            messages.SUCCESS,
        )

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
