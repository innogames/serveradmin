"""Serveradmin - Access Control for Users and Applications

Copyright (c) 2018 InnoGames GmbH
"""

from django.db import models
from django.contrib.auth.models import User

from adminapi.parse import parse_query
from serveradmin.apps.models import Application
from serveradmin.serverdb.models import Attribute


class AccessControlGroup(models.Model):
    name = models.CharField(max_length=80, unique=True)
    query = models.CharField(max_length=1000)
    members = models.ManyToManyField(
        User,
        blank=True,
        limit_choices_to={'is_superuser': False, 'is_active': True},
        related_name='access_control_groups',
    )
    applications = models.ManyToManyField(
        Application,
        blank=True,
        limit_choices_to={'disabled': False, 'superuser': False},
        related_name='access_control_groups',
    )
    is_whitelist = models.BooleanField(
        null=False,
        default=True,
        help_text=(
            "If checked, the attribute list is treated as a whitelist, "
            "otherwise it is treated as a blacklist."
        ),
    )
    attributes = models.ManyToManyField(
        Attribute,
        blank=True,
        related_name='access_control_groups',
        help_text=(
            "Note that you currently can't select the special attributes "
            "like object_id, hostname, servertype or intern_ip here."
        ),
    )

    class Meta:
        db_table = 'access_control_group'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._filters = None

    def __str__(self):
        return self.name

    def get_filters(self):
        if self._filters is None:
            self._filters = parse_query(self.query)
        return self._filters

    def get_permissible_attribute_ids(self):
        """Gather attribute ids this ACL allows changing

        Return names of self.attributes if self.whitelist, otherwise return
        names of (normal attributes + special attributes) - self.attributes
        """

        if self.is_whitelist is False:
            # Set of all attributes, excluding the blacklisted ones
            return (
                {a.pk for a in Attribute.objects.all()} |
                set(Attribute.specials.keys())
            ).difference(
                {a.pk for a in self.attributes.all()}
            )

        # Set of attributes that this ACL allows to be modified
        # XXX: There is currently no option to whitelist special attributes
        return {a.pk for a in self.attributes.all()}
