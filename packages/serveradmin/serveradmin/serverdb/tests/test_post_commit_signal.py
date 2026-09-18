"""Serveradmin - post_commit signal payload tests

Copyright (c) 2026 InnoGames GmbH
"""

from django.contrib.auth.models import User
from django.test import TransactionTestCase

from serveradmin.dataset import Query
from serveradmin.serverdb.models import Attribute
from serveradmin.serverdb.signals import post_commit


class TestPostCommitSignal(TransactionTestCase):
    fixtures = ['test_dataset.json', 'auth_user.json']

    def setUp(self):
        self.received = []
        post_commit.connect(self._receiver, dispatch_uid='test_post_commit_signal')
        self.addCleanup(post_commit.disconnect, dispatch_uid='test_post_commit_signal')

    def _receiver(self, sender, **kwargs):
        self.received.append(kwargs)

    def test_change_passes_materialized_objects_user_and_app(self):
        user = User.objects.first()
        q = Query({'hostname': 'test1'}, ['os'])
        server = q.get()
        server['os'] = 'jessie'
        commit_id = q.commit(user=user)

        kwargs = self.received[-1]
        self.assertEqual(kwargs['commit_id'], commit_id)
        self.assertEqual(kwargs['changed'][0]['object_id'], server['object_id'])
        self.assertEqual(kwargs['created'], [])
        self.assertEqual(kwargs['deleted'], [])
        self.assertEqual(kwargs['created_objects'], [])
        self.assertEqual(kwargs['deleted_objects'], [])
        self.assertEqual(kwargs['changed_objects'][0]['os'], 'jessie')
        self.assertEqual(kwargs['unchanged_objects'][0]['os'], 'squeeze')
        self.assertEqual(kwargs['user'], user)
        self.assertIsNone(kwargs['app'])

    def test_delete_passes_deleted_objects(self):
        q = Query({'hostname': 'test2'}, ['hostname', 'os'])
        obj = q.get()
        q.delete()
        q.commit(user=User.objects.first())

        kwargs = self.received[-1]
        self.assertEqual(kwargs['deleted'], [obj['object_id']])
        self.assertEqual(len(kwargs['deleted_objects']), 1)
        self.assertEqual(kwargs['deleted_objects'][0]['hostname'], 'test2')
        self.assertEqual(kwargs['deleted_objects'][0]['object_id'], obj['object_id'])
        self.assertEqual(kwargs['deleted_objects'][0]['servertype'], 'test2')

    def test_create_passes_created_objects(self):
        new = Query().new_object('test0')
        new['hostname'] = 'test-new'
        new['intern_ip'] = '10.16.0.99'
        commit_id = new.commit(user=User.objects.first())

        kwargs = self.received[-1]
        self.assertEqual(kwargs['commit_id'], commit_id)
        self.assertEqual(kwargs['created'][0]['hostname'], 'test-new')
        self.assertEqual(kwargs['created_objects'][0]['hostname'], 'test-new')
        self.assertIsNotNone(kwargs['created_objects'][0]['object_id'])

    def test_commit_id_is_none_without_history(self):
        Attribute.objects.filter(pk='os').update(history=False)
        q = Query({'hostname': 'test1'}, ['os'])
        q.get()['os'] = 'jessie'
        commit_id = q.commit(user=User.objects.first())

        self.assertIsNone(commit_id)
        self.assertIsNone(self.received[-1]['commit_id'])
