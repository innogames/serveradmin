"""Serveradmin - Task queue tests

Copyright (c) 2026 InnoGames GmbH
"""

import threading
from datetime import timedelta

from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.utils.timezone import now

from serveradmin.taskqueue import queue
from serveradmin.taskqueue.models import Task
from serveradmin.taskqueue.registry import register, unregister
from serveradmin.taskqueue.tests.helpers import (
    DummyTaskType,
    DummyTaskTypeMixin,
    ExternalTaskType,
)

WORKER = 'test:1'
TYPES = [DummyTaskType.name]


class TestEnqueue(DummyTaskTypeMixin, TransactionTestCase):
    def test_enqueue_creates_pending_task_with_type_defaults(self):
        task = queue.enqueue(DummyTaskType.name, {'a': 1}, commit_id=None)

        task.refresh_from_db()
        self.assertEqual(task.state, Task.State.PENDING)
        self.assertEqual(task.payload, {'a': 1})
        self.assertEqual(task.max_attempts, DummyTaskType.max_attempts)
        self.assertEqual(task.attempts, 0)
        self.assertIsNone(task.commit)
        self.assertLessEqual(task.run_after, now())

    def test_enqueue_accepts_class_and_instance(self):
        queue.enqueue(DummyTaskType, {})
        queue.enqueue(self.dummy, {})
        self.assertEqual(Task.objects.count(), 2)

    def test_enqueue_unknown_type_raises(self):
        with self.assertRaises(ValueError):
            queue.enqueue('nope.nope', {})

    def test_enqueue_many_saves_all(self):
        tasks = [queue.build_task(self.dummy, {'i': i}) for i in range(3)]
        queue.enqueue_many(tasks)
        self.assertEqual(Task.objects.count(), 3)

    @override_settings(TASKQUEUE_RUN_INLINE=True)
    def test_inline_mode_runs_task_synchronously(self):
        task = queue.enqueue(self.dummy, {})

        task.refresh_from_db()
        self.assertEqual(task.state, Task.State.DONE)
        self.assertEqual(task.result, {'ok': True})
        self.assertEqual(self.dummy.runs, [task.pk])

    @override_settings(TASKQUEUE_RUN_INLINE=True)
    def test_inline_mode_records_failure_instead_of_raising(self):
        self.dummy.run_exception = ValueError('nope')
        task = queue.enqueue(self.dummy, {}, max_attempts=1)

        task.refresh_from_db()
        self.assertEqual(task.state, Task.State.FAILED)
        self.assertIn('ValueError: nope', task.last_error)


class TestClaim(DummyTaskTypeMixin, TransactionTestCase):
    def test_claim_returns_oldest_pending_first(self):
        first = queue.enqueue(self.dummy, {'n': 1})
        queue.enqueue(self.dummy, {'n': 2})

        task = queue.claim_next(WORKER, TYPES)

        self.assertEqual(task.pk, first.pk)
        self.assertEqual(task.state, Task.State.RUNNING)
        self.assertEqual(task.attempts, 1)
        self.assertEqual(task.locked_by, WORKER)
        self.assertIsNotNone(task.locked_at)
        self.assertGreater(task.locked_until, now())

    def test_claim_returns_none_when_empty(self):
        self.assertIsNone(queue.claim_next(WORKER, TYPES))
        self.assertIsNone(queue.claim_next(WORKER, []))

    def test_claim_only_given_types(self):
        register(ExternalTaskType)
        self.addCleanup(unregister, ExternalTaskType.name)
        queue.enqueue(ExternalTaskType.name, {})
        Task.objects.create(task_type='not.registered', payload={})

        self.assertIsNone(queue.claim_next(WORKER, TYPES))
        self.assertEqual(
            Task.objects.filter(state=Task.State.PENDING).count(), 2
        )

    def test_claim_skips_future_run_after(self):
        queue.enqueue(self.dummy, {}, run_after=now() + timedelta(minutes=5))
        self.assertIsNone(queue.claim_next(WORKER, TYPES))

    def test_claim_ignores_running_task_with_valid_lease(self):
        queue.enqueue(self.dummy, {})
        queue.claim_next(WORKER, TYPES)

        self.assertIsNone(queue.claim_next('test:2', TYPES))

    def test_claim_reclaims_expired_lease_and_increments_attempts(self):
        queue.enqueue(self.dummy, {})
        task = queue.claim_next(WORKER, TYPES)
        Task.objects.filter(pk=task.pk).update(
            locked_until=now() - timedelta(seconds=1)
        )

        reclaimed = queue.claim_next('test:2', TYPES)

        self.assertEqual(reclaimed.pk, task.pk)
        self.assertEqual(reclaimed.attempts, 2)
        self.assertEqual(reclaimed.locked_by, 'test:2')

    def test_claim_uses_type_lease_seconds(self):
        self.dummy.lease_seconds = 7
        queue.enqueue(self.dummy, {})
        task = queue.claim_next(WORKER, TYPES)
        self.assertAlmostEqual(
            (task.locked_until - task.locked_at).total_seconds(), 7, delta=0.01
        )

    def test_concurrent_claims_return_distinct_tasks(self):
        for i in range(2):
            queue.enqueue(self.dummy, {'i': i})
        claimed = []
        barrier = threading.Barrier(2)

        def worker(name):
            try:
                barrier.wait(timeout=5)
                task = queue.claim_next(name, TYPES)
                claimed.append(task.pk if task else None)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker, args=(f'w{i}',)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(len(claimed), 2)
        self.assertNotIn(None, claimed)
        self.assertNotEqual(claimed[0], claimed[1])


class TestCompleteAndFail(DummyTaskTypeMixin, TransactionTestCase):
    def _claimed(self, **kwargs):
        queue.enqueue(self.dummy, {}, **kwargs)
        return queue.claim_next(WORKER, TYPES)

    def test_complete_sets_done_result_and_clears_lease(self):
        task = self._claimed()

        self.assertTrue(queue.complete(task, {'changed': 3}))

        task.refresh_from_db()
        self.assertEqual(task.state, Task.State.DONE)
        self.assertEqual(task.result, {'changed': 3})
        self.assertIsNotNone(task.finished_at)
        self.assertIsNone(task.locked_until)
        self.assertEqual(task.locked_by, '')
        self.assertTrue(task.finished)

    def test_fail_requeues_with_exponential_backoff(self):
        task = self._claimed()

        self.assertTrue(queue.fail(task, RuntimeError('first')))
        task.refresh_from_db()
        self.assertEqual(task.state, Task.State.PENDING)
        self.assertIn('RuntimeError: first', task.last_error)
        delay = (task.run_after - now()).total_seconds()
        self.assertAlmostEqual(delay, 10, delta=2)

        Task.objects.filter(pk=task.pk).update(run_after=now())
        task = queue.claim_next(WORKER, TYPES)
        queue.fail(task, RuntimeError('second'))
        task.refresh_from_db()
        delay = (task.run_after - now()).total_seconds()
        self.assertAlmostEqual(delay, 20, delta=2)

    def test_fail_after_max_attempts_is_terminal(self):
        task = self._claimed(max_attempts=1)

        queue.fail(task, RuntimeError('boom'))

        task.refresh_from_db()
        self.assertEqual(task.state, Task.State.FAILED)
        self.assertIsNotNone(task.finished_at)
        self.assertIsNone(queue.claim_next(WORKER, TYPES))

    def test_fail_non_retryable_is_terminal_immediately(self):
        self.dummy.is_retryable = lambda exc: False
        task = self._claimed()

        queue.fail(task, RuntimeError('boom'))

        task.refresh_from_db()
        self.assertEqual(task.state, Task.State.FAILED)

    def test_state_update_after_lost_lease_is_ignored(self):
        task = self._claimed()
        # Another worker re-claimed the task: attempts moved on
        Task.objects.filter(pk=task.pk).update(attempts=task.attempts + 1)

        self.assertFalse(queue.complete(task, {}))
        self.assertFalse(queue.fail(task, RuntimeError()))

        task.refresh_from_db()
        self.assertEqual(task.state, Task.State.RUNNING)

    def test_extend_lease(self):
        task = self._claimed()
        old = task.locked_until
        self.assertTrue(queue.extend_lease(task, 3600))
        task.refresh_from_db()
        self.assertGreater(task.locked_until, old)

    def test_run_task_completes(self):
        task = self._claimed()
        self.assertTrue(queue.run_task(task))
        task.refresh_from_db()
        self.assertEqual(task.state, Task.State.DONE)
        self.assertEqual(task.result, {'ok': True})

    def test_run_task_catches_exception(self):
        self.dummy.run_exception = KeyError('missing')
        task = self._claimed()
        self.assertFalse(queue.run_task(task))
        task.refresh_from_db()
        self.assertEqual(task.state, Task.State.PENDING)
        self.assertIn('KeyError', task.last_error)

    def test_run_task_unknown_type_fails(self):
        task = Task.objects.create(
            task_type='gone.away', payload={}, state=Task.State.RUNNING,
            attempts=1, max_attempts=1, locked_until=now(),
        )
        self.assertFalse(queue.run_task(task))
        task.refresh_from_db()
        self.assertEqual(task.state, Task.State.FAILED)


class TestHousekeeping(DummyTaskTypeMixin, TransactionTestCase):
    def test_retry_requeues_finished_tasks_only(self):
        failed = Task.objects.create(
            task_type=DummyTaskType.name, state=Task.State.FAILED, attempts=3,
            finished_at=now(), last_error='x',
        )
        pending = queue.enqueue(self.dummy, {})

        self.assertEqual(queue.retry(Task.objects.all()), 1)

        failed.refresh_from_db()
        pending.refresh_from_db()
        self.assertEqual(failed.state, Task.State.PENDING)
        self.assertEqual(failed.attempts, 0)
        self.assertEqual(failed.last_error, '')
        self.assertEqual(pending.attempts, 0)

    def test_cancel_pending_only(self):
        pending = queue.enqueue(self.dummy, {})
        queue.enqueue(self.dummy, {})
        running = queue.claim_next(WORKER, TYPES)

        self.assertEqual(queue.cancel([pending, running]), 0)
        self.assertEqual(queue.cancel(Task.objects.all()), 1)

        running.refresh_from_db()
        self.assertEqual(running.state, Task.State.RUNNING)
        self.assertIsNone(queue.claim_next(WORKER, TYPES))

    def test_prune_removes_only_old_terminal_tasks(self):
        old = now() - timedelta(days=40)
        Task.objects.create(task_type='x', state=Task.State.DONE, finished_at=old)
        Task.objects.create(task_type='x', state=Task.State.FAILED, finished_at=old)
        Task.objects.create(task_type='x', state=Task.State.DONE, finished_at=now())
        Task.objects.create(task_type='x', state=Task.State.PENDING, created_at=old)

        self.assertEqual(queue.prune(retention_days=30, batch_size=1), 2)
        self.assertEqual(Task.objects.count(), 2)

    def test_pending_unregistered_types(self):
        queue.enqueue(self.dummy, {})
        Task.objects.create(task_type='gone.away', payload={})
        Task.objects.create(task_type='gone.done', state=Task.State.DONE)

        self.assertEqual(queue.pending_unregistered_types(), ['gone.away'])
