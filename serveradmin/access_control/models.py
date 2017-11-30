from django.db.models import Model, CharField, ManyToManyField
from django.contrib.auth.models import User

from adminapi.parse import parse_query
from serveradmin.apps.models import Application
from serveradmin.dataset.filters import filter_classes


class AccessControlGroup(Model):
    name = CharField(max_length=80, unique=True)
    create_server_query = CharField(max_length=1000)
    edit_server_query = CharField(max_length=1000)
    commit_server_query = CharField(max_length=1000)
    delete_server_query = CharField(max_length=1000)
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
        self._filters = {}

    def __str__(self):
        return self.name

    def get_filters(self, action):
        if action not in self._filters:
            query = getattr(self, action + '_server_query')
            self._filters[action] = parse_query(query, filter_classes)
        return self._filters[action]

    def match_server(self, action, server):
        return all(
            f.matches(server[a]) for a, f in self.get_filters(action).items()
        )
