"""Serveradmin - Task queue worker command tests

Copyright (c) 2026 InnoGames GmbH
"""

from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TransactionTestCase

from serveradmin.taskqueue import queue
from serveradmin.taskqueue.models import Task
from serveradmin.taskqueue.registry import register, unregister
from serveradmin.taskqueue.tests.helpers import (
    DummyTaskType,
    DummyTaskTypeMixin,
    ExternalTaskType,
)


class TestRunTaskqueue(DummyTaskTypeMixin, TransactionTestCase):
    def _run(self, *args):
        out = StringIO()
        call_command('run_taskqueue', '--once', *args, stdout=out, stderr=out)
        return out.getvalue()

    def test_once_processes_all_runnable_tasks(self):
        for i in range(3):
            queue.enqueue(self.dummy, {'i': i})
        Task.objects.create(task_type='not.registered')

        output = self._run()

        self.assertIn('Processed 3 task(s)', output)
        self.assertEqual(
            Task.objects.filter(state=Task.State.DONE).count(), 3
        )
        self.assertEqual(
            Task.objects.get(task_type='not.registered').state, Task.State.PENDING
        )
        self.assertEqual(len(self.dummy.runs), 3)

    def test_failed_task_is_retried_later_not_immediately(self):
        self.dummy.run_exception = RuntimeError('boom')
        task = queue.enqueue(self.dummy, {})

        self._run()

        task.refresh_from_db()
        self.assertEqual(task.state, Task.State.PENDING)
        self.assertEqual(task.attempts, 1)
        self.assertEqual(len(self.dummy.runs), 1)

    def test_task_type_option_restricts(self):
        register(ExternalTaskType)
        self.addCleanup(unregister, ExternalTaskType.name)
        queue.enqueue(self.dummy, {})
        queue.enqueue(ExternalTaskType.name, {})

        self._run('--task-type', DummyTaskType.name)

        self.assertEqual(Task.objects.filter(state=Task.State.DONE).count(), 1)
        self.assertEqual(
            Task.objects.get(task_type=ExternalTaskType.name).state,
            Task.State.PENDING,
        )

    def test_external_types_are_never_claimed(self):
        register(ExternalTaskType)
        self.addCleanup(unregister, ExternalTaskType.name)
        queue.enqueue(ExternalTaskType.name, {})

        self._run()

        self.assertEqual(
            Task.objects.get(task_type=ExternalTaskType.name).state,
            Task.State.PENDING,
        )
        with self.assertRaises(CommandError):
            self._run('--task-type', ExternalTaskType.name)

    def test_unknown_task_type_option_is_error(self):
        with self.assertRaises(CommandError):
            self._run('--task-type', 'nope.nope')

    def test_max_tasks(self):
        for i in range(3):
            queue.enqueue(self.dummy, {'i': i})

        self._run('--max-tasks', '2')

        self.assertEqual(Task.objects.filter(state=Task.State.DONE).count(), 2)
