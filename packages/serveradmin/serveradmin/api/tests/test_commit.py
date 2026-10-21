"""Serveradmin - Query API commit tests

Copyright (c) 2026 InnoGames GmbH
"""

from django.contrib.auth.models import User
from django.test import TransactionTestCase

from serveradmin.api.views import dataset_commit
from serveradmin.apps.models import Application
from serveradmin.dataset import Query
from serveradmin.serverdb.models import Attribute, Change, ChangeCommit
from serveradmin.serverdb.query_committer import _normalize_values


class DatasetCommitChangelogTestCase(TransactionTestCase):
    """The changelog must only contain changes that actually changed a value

    The adminapi client filters unchanged attributes before sending a commit,
    but the API accepts hand-built payloads (raw HTTP clients, the servershell
    commit view, direct commit_query callers).  The server therefore has to
    make sure that a commit like ``memory: 8192 => 8192`` neither creates a
    ChangeCommit nor a Change entry.
    """

    fixtures = ['test_dataset.json']

    def setUp(self):
        super().setUp()
        user = User.objects.create_user('alice')
        # Superuser app: ACLs are out of scope for these tests.
        self.app = Application.objects.create(
            name='app', owner=user, location='', superuser=True,
        )

    def _commit(self, changed):
        # Call the view without the auth decorator, like the other API tests.
        response = dataset_commit.__wrapped__(
            None, self.app, {'changed': changed},
        )
        self.assertEqual(response['status'], 'success', response)
        return response['commit_id']

    def _assert_nothing_logged(self, commit_id):
        self.assertIsNone(commit_id)
        self.assertEqual(ChangeCommit.objects.count(), 0)
        self.assertEqual(Change.objects.count(), 0)

    def test_unchanged_update_is_not_logged(self):
        """An update with old == new must not end up in the changelog"""
        commit_id = self._commit([{
            'object_id': 2,
            'game_world': {'action': 'update', 'old': 1, 'new': 1},
        }])

        self._assert_nothing_logged(commit_id)
        server = Query({'hostname': 'test1'}, ['game_world']).get()
        self.assertEqual(server['game_world'], 1)

    def test_unchanged_multi_is_not_logged(self):
        """A multi change without add/remove must not be logged"""
        commit_id = self._commit([{
            'object_id': 1,
            'database': {'action': 'multi', 'add': [], 'remove': []},
        }])

        self._assert_nothing_logged(commit_id)

    def test_delete_of_unset_attribute_is_not_logged(self):
        """Clearing an attribute that has no value, as the servershell does"""
        commit_id = self._commit([{
            'object_id': 1,
            'mac_address': {'action': 'delete', 'old': None},
        }])

        self._assert_nothing_logged(commit_id)

    def test_delete_of_set_attribute_is_logged(self):
        """Control: deleting a real value is a change"""
        commit_id = self._commit([{
            'object_id': 2,
            'game_world': {'action': 'delete', 'old': 1},
        }])

        self.assertIsNotNone(commit_id)
        change = Change.objects.get()
        self.assertEqual(change.object_id, 2)
        self.assertEqual(
            change.change_json['game_world'], {'action': 'delete', 'old': 1},
        )
        server = Query({'hostname': 'test1'}, ['game_world']).get()
        self.assertIsNone(server['game_world'])

    def test_mixed_commit_logs_only_real_changes(self):
        """Unchanged attributes are dropped from an otherwise real change"""
        commit_id = self._commit([{
            'object_id': 2,
            'os': {'action': 'update', 'old': 'squeeze', 'new': 'wheezy'},
            'game_world': {'action': 'update', 'old': 1, 'new': 1},
        }])

        self.assertIsNotNone(commit_id)
        self.assertEqual(ChangeCommit.objects.count(), 1)
        change = Change.objects.get()
        self.assertEqual(change.object_id, 2)
        self.assertEqual(change.change_type, Change.Type.CHANGE)
        self.assertIn('os', change.change_json)
        self.assertNotIn('game_world', change.change_json)

    def test_real_change_is_logged(self):
        """Control: a real change creates exactly one commit and one change"""
        commit_id = self._commit([{
            'object_id': 2,
            'os': {'action': 'update', 'old': 'squeeze', 'new': 'wheezy'},
        }])

        self.assertIsNotNone(commit_id)
        commit = ChangeCommit.objects.get()
        self.assertEqual(commit.id, commit_id)
        self.assertEqual(commit.app, self.app)
        change = Change.objects.get()
        self.assertEqual(change.commit, commit)
        self.assertEqual(change.object_id, 2)
        self.assertEqual(change.change_type, Change.Type.CHANGE)
        self.assertEqual(
            change.change_json['os'],
            {'action': 'update', 'old': 'squeeze', 'new': 'wheezy'},
        )
        server = Query({'hostname': 'test1'}, ['os']).get()
        self.assertEqual(server['os'], 'wheezy')


class DatasetCommitValueTypesTestCase(TransactionTestCase):
    """Values sent as strings are cast to the attribute type

    Otherwise a commit of memory: 8192 => "8192" is logged as a change and
    the string "false" ends up as a true boolean.
    """

    fixtures = ['test_dataset.json']

    def setUp(self):
        super().setUp()
        user = User.objects.create_user('alice')
        self.app = Application.objects.create(
            name='app', owner=user, location='', superuser=True,
        )

    def _commit(self, changed):
        return dataset_commit.__wrapped__(
            None, self.app, {'changed': changed},
        )

    def test_string_number_equal_to_stored_value_is_not_logged(self):
        response = self._commit([{
            'object_id': 2,
            'game_world': {'action': 'update', 'old': 1, 'new': '1'},
        }])

        self.assertEqual(response['status'], 'success', response)
        self.assertIsNone(response['commit_id'])
        self.assertFalse(Change.objects.exists())
        self.assertEqual(
            Query({'hostname': 'test1'}, ['game_world']).get()['game_world'],
            1,
        )

    def test_string_number_is_stored_and_logged_typed(self):
        response = self._commit([{
            'object_id': 2,
            'game_world': {'action': 'update', 'old': 1, 'new': '2'},
        }])

        self.assertEqual(response['status'], 'success', response)
        change = Change.objects.get()
        self.assertEqual(change.change_json['game_world']['new'], 2)
        self.assertEqual(
            Query({'hostname': 'test1'}, ['game_world']).get()['game_world'],
            2,
        )

    def test_boolean_string_false_is_stored_as_false(self):
        response = self._commit([{
            'object_id': 2,
            'has_monitoring': {
                'action': 'update', 'old': False, 'new': 'false',
            },
        }])

        self.assertEqual(response['status'], 'success', response)
        server = Query({'hostname': 'test1'}, ['has_monitoring']).get()
        self.assertIs(server['has_monitoring'], False)
        self.assertFalse(Change.objects.exists())

    def test_boolean_string_true_is_stored_as_true(self):
        response = self._commit([{
            'object_id': 2,
            'has_monitoring': {
                'action': 'update', 'old': False, 'new': 'true',
            },
        }])

        self.assertEqual(response['status'], 'success', response)
        server = Query({'hostname': 'test1'}, ['has_monitoring']).get()
        self.assertIs(server['has_monitoring'], True)
        change = Change.objects.get()
        self.assertIs(change.change_json['has_monitoring']['new'], True)

    def test_invalid_boolean_string_is_rejected(self):
        response = self._commit([{
            'object_id': 2,
            'has_monitoring': {
                'action': 'update', 'old': False, 'new': 'maybe',
            },
        }])

        self.assertEqual(response['status'], 'error')
        self.assertEqual(response['type'], 'ValidationError')
        self.assertIn('has_monitoring', response['message'])
        self.assertFalse(Change.objects.exists())

    def test_multi_values_are_cast(self):
        # The fixture has no multi number attribute, so test the helper.
        attribute = Attribute(attribute_id='ports', type='number', multi=True)
        changed = [{
            'object_id': 1,
            'ports': {'action': 'multi', 'add': ['80', 443], 'remove': ['22']},
        }]

        normalized = _normalize_values({'ports': attribute}, changed)

        self.assertEqual(
            normalized[0]['ports'], {'action': 'multi', 'add': [80, 443],
                                     'remove': [22]},
        )
        # The input must not be modified.
        self.assertEqual(changed[0]['ports']['add'], ['80', 443])
