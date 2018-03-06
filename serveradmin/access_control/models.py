from django.db.models import Model, CharField, ManyToManyField
from django.contrib.auth.models import User

from adminapi.parse import parse_query
from serveradmin.apps.models import Application


class AccessControlGroup(Model):
    name = CharField(max_length=80, unique=True)
    query = CharField(max_length=1000)
    members = ManyToManyField(
        User,
        blank=True,
        limit_choices_to={'is_superuser': False, 'is_active': True},
        related_name='access_control_groups',
    )
    applications = ManyToManyField(
        Application,
        blank=True,
        limit_choices_to={'disabled': False, 'superuser': False},
        related_name='access_control_groups',
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

    def match_server(self, server):
        return all(f.matches(server[a]) for a, f in self.get_filters().items())
