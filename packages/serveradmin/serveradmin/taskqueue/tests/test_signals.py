"""Serveradmin - Task queue post_commit dispatch tests

Copyright (c) 2026 InnoGames GmbH
"""

from django.contrib.auth.models import User
from django.test import TransactionTestCase, override_settings

from serveradmin.dataset import Query
from serveradmin.serverdb.models import ChangeCommit
from serveradmin.taskqueue.models import Task
from serveradmin.taskqueue.registry import register, unregister
from serveradmin.taskqueue.tests.helpers import (
    DummyTaskType,
    DummyTaskTypeMixin,
    RaisingProducer,
)


class TestCommitDispatch(DummyTaskTypeMixin, TransactionTestCase):
    fixtures = ['test_dataset.json', 'auth_user.json']

    def _user(self):
        return User.objects.first()

    def test_change_creates_task_with_commit_and_payload(self):
        q = Query({'hostname': 'test1'}, ['os'])
        server = q.get()
        server['os'] = 'jessie'
        commit_id = q.commit(user=self._user())

        task = Task.objects.get()
        self.assertEqual(task.task_type, DummyTaskType.name)
        self.assertEqual(task.commit_id, commit_id)
        self.assertEqual(task.state, Task.State.PENDING)
        self.assertEqual(task.payload['changed'], [server['object_id']])
        self.assertEqual(task.payload['created'], [])
        self.assertEqual(task.payload['deleted'], [])

        event = self.dummy.events[-1]
        self.assertEqual(event.commit_id, commit_id)
        self.assertEqual(event.changed_object_ids(), {server['object_id']})
        self.assertEqual(event.changed_attribute_ids(), {'os'})
        self.assertEqual(event.changed_objects[0]['os'], 'jessie')
        self.assertEqual(event.unchanged_objects[0]['os'], 'squeeze')
        self.assertEqual(event.user, self._user())
        self.assertIsNone(event.app)

    def test_create_and_delete_carry_materialized_objects(self):
        q = Query({'hostname': 'test2'}, ['hostname'])
        q.get()
        q.delete()
        new = Query().new_object('test0')
        new['hostname'] = 'test-new'
        new['intern_ip'] = '10.16.0.99'
        # Both in one commit is not possible via Query, so two commits
        commit_delete = q.commit(user=self._user())
        commit_create = new.commit(user=self._user())

        delete_task = Task.objects.get(commit_id=commit_delete)
        create_task = Task.objects.get(commit_id=commit_create)
        self.assertEqual(delete_task.payload['deleted'], ['test2'])
        self.assertEqual(create_task.payload['created'], ['test-new'])

        delete_event = self.dummy.events[0]
        self.assertEqual(delete_event.deleted_objects[0]['hostname'], 'test2')
        self.assertEqual(delete_event.deleted_objects[0]['servertype'], 'test2')
        self.assertEqual(delete_event.deleted, [delete_event.deleted_objects[0]['object_id']])

    def test_disabled_type_produces_nothing(self):
        self.dummy.is_enabled = False
        self._change_os()
        self.assertEqual(Task.objects.count(), 0)
        self.assertEqual(self.dummy.events, [])

    def test_producer_returning_none_creates_no_task(self):
        self.dummy.produce_payload = []
        self._change_os()
        self.assertEqual(Task.objects.count(), 0)

    def test_producer_may_return_several_payloads(self):
        self.dummy.produce_payload = [{'n': 1}, {'n': 2}]
        commit_id = self._change_os()
        self.assertEqual(
            sorted(t.payload['n'] for t in Task.objects.filter(commit_id=commit_id)),
            [1, 2],
        )

    def test_raising_producer_does_not_block_others(self):
        register(RaisingProducer)
        self.addCleanup(unregister, RaisingProducer.name)

        with self.assertLogs('serveradmin.taskqueue.signals', level='ERROR'):
            self._change_os()

        self.assertEqual(Task.objects.count(), 1)
        self.assertEqual(Task.objects.get().task_type, DummyTaskType.name)

    def test_commit_without_history_creates_task_without_commit(self):
        # Nothing to log -> no ChangeCommit row -> commit_id is None
        from serveradmin.serverdb.models import Attribute
        Attribute.objects.filter(pk='os').update(history=False)

        commit_id = self._change_os()

        self.assertIsNone(commit_id)
        task = Task.objects.get()
        self.assertIsNone(task.commit)
        event = self.dummy.events[-1]
        self.assertEqual(task.payload['changed'], sorted(event.changed_object_ids()))

    @override_settings(TASKQUEUE_RUN_INLINE=True)
    def test_inline_mode_runs_after_commit(self):
        commit_id = self._change_os()
        task = Task.objects.get(commit_id=commit_id)
        self.assertEqual(task.state, Task.State.DONE)
        self.assertEqual(self.dummy.runs, [task.pk])

    def test_commit_fk(self):
        commit_id = self._change_os()
        commit = ChangeCommit.objects.get(pk=commit_id)
        self.assertEqual(commit.tasks.count(), 1)

    def _change_os(self):
        q = Query({'hostname': 'test1'}, ['os'])
        q.get()['os'] = 'buster'
        return q.commit(user=self._user())
