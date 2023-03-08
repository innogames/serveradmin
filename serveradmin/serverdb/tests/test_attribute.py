from django.contrib.auth.models import User
from django.test import TransactionTestCase
from django.utils.timezone import now
from faker import Faker
from faker.providers import internet

from serveradmin.dataset import Query
from serveradmin.serverdb.models import Change


class TestAttributeHistory(TransactionTestCase):
    fixtures = ['auth_user.json', 'attribute.json']

    def setUp(self):
        super().setUp()
        self.faker = Faker()
        self.faker.add_provider(internet)

    def test_attribute_history_is_logged(self):
        project = Query().new_object('project')
        project['hostname'] = self.faker.hostname()
        project['owner'] = 'john.doe' # Attribute with history enabled
        project.commit(user=User.objects.first())

        projects = Query({'hostname': project['hostname']}, ['owner'])
        projects.update(owner='max.mustermann')
        projects.commit(user=User.objects.first())
        oid = projects.get()['object_id']

        change = Change.objects.last()
        self.assertEqual(change.change_json, {"owner": {"new": "max.mustermann", "old": "john.doe", "action": "update"}, "object_id": oid})

    def test_attribute_history_is_not_logged(self):
        project = Query().new_object('project')
        project['hostname'] = self.faker.hostname()
        project['last_updated'] = now()  # Attribute with history disabled
        project.commit(user=User.objects.first())

        projects = Query({'hostname': project['hostname']}, ['last_updated'])
        projects.update(last_updated=now())
        projects.commit(user=User.objects.first())
        oid = projects.get()['object_id']

        self.assertEqual(Change.objects.filter(change_type=Change.Type.CHANGE, object_id=oid).count(), 0)

    def test_only_required_attribute_history_is_logged(self):
        project = Query().new_object('project')
        project['hostname'] = self.faker.hostname()
        project['owner'] = 'john.doe'  # Attribute with history enabled
        project['last_updated'] = now()  # Attribute with history disabled
        project.commit(user=User.objects.first())

        projects = Query({'hostname': project['hostname']}, ['owner', 'last_updated'])
        projects.update(owner='max.mustermann', last_updated=now())
        projects.commit(user=User.objects.first())
        oid = projects.get()['object_id']

        change = Change.objects.last()
        self.assertEqual(change.change_json, {"owner": {"new": "max.mustermann", "old": "john.doe", "action": "update"}, "object_id": oid})
