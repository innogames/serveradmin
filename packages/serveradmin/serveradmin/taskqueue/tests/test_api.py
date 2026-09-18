"""Serveradmin - Task queue API tests

Copyright (c) 2026 InnoGames GmbH
"""

from django.contrib.auth.models import User
from django.test import TransactionTestCase
from django.utils.timezone import now

from adminapi.exceptions import ApiError
from serveradmin.api import AVAILABLE_API_FUNCTIONS
from serveradmin.serverdb.models import ChangeCommit
from serveradmin.taskqueue import queue
from serveradmin.taskqueue.api import status
from serveradmin.taskqueue.models import Task
from serveradmin.taskqueue.tests.helpers import DummyTaskType, DummyTaskTypeMixin


class TestStatusApi(DummyTaskTypeMixin, TransactionTestCase):
    fixtures = ['auth_user.json']

    def setUp(self):
        super().setUp()
        self.commit = ChangeCommit.objects.create(user=User.objects.first())

    def test_registered_as_api_function(self):
        self.assertIs(AVAILABLE_API_FUNCTIONS['taskqueue']['status'], status)

    def test_commit_without_tasks_is_finished(self):
        result = status(self.commit.pk)
        self.assertEqual(result['total'], 0)
        self.assertTrue(result['finished'])
        self.assertTrue(result['succeeded'])
        self.assertEqual(result['tasks'], [])

    def test_unknown_commit_raises(self):
        with self.assertRaises(ApiError):
            status(self.commit.pk + 1000)

    def test_rejects_non_integer(self):
        for value in ('1', None, True, 1.5):
            with self.assertRaises(ApiError):
                status(value)

    def test_aggregates_states(self):
        pending = queue.enqueue(self.dummy, {'n': 1}, commit_id=self.commit.pk)
        done = queue.enqueue(self.dummy, {'n': 2}, commit_id=self.commit.pk)
        Task.objects.filter(pk=done.pk).update(
            state=Task.State.DONE, finished_at=now(), result={'changed': 1}
        )
        queue.enqueue(self.dummy, {'n': 3})  # other commit

        result = status(self.commit.pk)

        self.assertEqual(result['commit_id'], self.commit.pk)
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['pending'], 1)
        self.assertEqual(result['done'], 1)
        self.assertFalse(result['finished'])
        self.assertFalse(result['succeeded'])
        self.assertEqual([t['id'] for t in result['tasks']], [pending.pk, done.pk])
        self.assertEqual(result['tasks'][1]['result'], {'changed': 1})
        self.assertEqual(result['tasks'][0]['task_type'], DummyTaskType.name)
        self.assertIsInstance(result['tasks'][0]['created_at'], str)

        Task.objects.filter(pk=pending.pk).update(
            state=Task.State.FAILED, finished_at=now()
        )
        result = status(self.commit.pk)
        self.assertTrue(result['finished'])
        self.assertFalse(result['succeeded'])
        self.assertEqual(result['failed'], 1)

    def test_type_may_override_status(self):
        self.dummy.get_status = lambda task: {'extra': 42, 'state': 'custom'}
        queue.enqueue(self.dummy, {}, commit_id=self.commit.pk)

        result = status(self.commit.pk)

        self.assertEqual(result['tasks'][0]['extra'], 42)
        self.assertEqual(result['tasks'][0]['state'], 'custom')

    def test_unregistered_type_uses_default_status(self):
        Task.objects.create(task_type='gone.away', commit=self.commit)
        result = status(self.commit.pk)
        self.assertEqual(result['tasks'][0]['state'], 'pending')
        self.assertFalse(result['finished'])
