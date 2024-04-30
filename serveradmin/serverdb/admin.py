"""Serveradmin - Django Admin Setup

Copyright (c) 2019 InnoGames GmbH
"""

from django.contrib import admin
from django.utils.html import format_html

from serveradmin.serverdb.forms import (
    ServertypeAdminForm,
    ServertypeAttributeAdminForm,
)
from serveradmin.serverdb.models import (
    Attribute,
    Server,
    ServerRelationAttribute,
    ServerStringAttribute,
    Servertype,
    ServertypeAttribute,
)


class ServertypeAttributeInline(admin.TabularInline):
    form = ServertypeAttributeAdminForm
    model = ServertypeAttribute


class ServertypeAdmin(admin.ModelAdmin):
    form = ServertypeAdminForm
    inlines = (ServertypeAttributeInline,)

    list_display = [
        'servertype_id',
        'description',
    ]
    search_fields = [
        'servertype_id',
        'description',
    ]

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)

        if obj:
            # Because of the complexity when changing servertypes of existing
            # objects and the little use-cases we have right now we don't
            # support it.
            fields += ('ip_addr_type',)

        return fields


class ServerRelationAttributeInline(admin.TabularInline):
    model = ServerRelationAttribute
    fk_name = 'server'


class ServerStringAttributeInline(admin.TabularInline):
    model = ServerStringAttribute


class ServerAdmin(admin.ModelAdmin):
    inlines = (
        ServerRelationAttributeInline,
        ServerStringAttributeInline,
    )

    list_display = [
        'server_id',
        'hostname',
        'servertype',
    ]
    list_display_links = [
        'hostname',
    ]
    search_fields = [
        'server_id',
        'hostname',
    ]
    list_filter = [
        'servertype__servertype_id',
    ]


class AttributeAdmin(admin.ModelAdmin):
    list_display = [
        'attribute_id',
        'type',
        'group',
        'get_hovertext',
        'multi',
        'readonly',
        'clone',
        'history',
    ]
    search_fields = [
        'attribute_id',
    ]
    list_filter = [
        'type',
        'group',
        'multi',
        'readonly',
        'clone',
        'history',
    ]

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)

        # Because of the complexity when changing attribute types of existing
        # objects and the little use-cases we have right now we don't
        # support it.
        if obj:
            fields += ('type', 'attribute_id', 'target_servertype', 'reversed_attribute')

        return fields

    @admin.display(description='hovertext')
    def get_hovertext(self, obj):
        return format_html(
            '<span title="{}">{}</span>',
            obj.hovertext,
            obj.hovertext[:50],
        )


admin.site.register(Servertype, ServertypeAdmin)
admin.site.register(Attribute, AttributeAdmin)
admin.site.register(Server, ServerAdmin)
