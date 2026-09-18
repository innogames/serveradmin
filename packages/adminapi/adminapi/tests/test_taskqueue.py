import unittest
from unittest.mock import patch

from adminapi import taskqueue
from adminapi.taskqueue import TaskFailed


def _status(commit_id=42, **states):
    tasks = []
    for state, count in states.items():
        for _ in range(count):
            tasks.append({'id': len(tasks) + 1, 'task_type': 'powerdns.sync', 'state': state,
                          'finished': state in ('done', 'failed', 'cancelled')})
    counts = {s: sum(1 for t in tasks if t['state'] == s)
              for s in ('pending', 'running', 'done', 'failed', 'cancelled')}
    return {
        'commit_id': commit_id,
        'total': len(tasks),
        **counts,
        'finished': all(t['finished'] for t in tasks),
        'succeeded': all(t['state'] == 'done' for t in tasks),
        'tasks': tasks,
    }


class TestWaitForCommit(unittest.TestCase):
    def test_none_commit_returns_immediately(self):
        with patch('adminapi.taskqueue.status') as status:
            result = taskqueue.wait_for_commit(None)
        status.assert_not_called()
        self.assertTrue(result['finished'])
        self.assertEqual(result['tasks'], [])

    def test_returns_when_finished(self):
        responses = [_status(pending=1), _status(running=1), _status(done=1)]
        with patch('adminapi.taskqueue.status', side_effect=responses) as status, \
                patch('adminapi.taskqueue.time.sleep') as sleep:
            result = taskqueue.wait_for_commit(42, timeout=60, interval=3)

        self.assertEqual(status.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        sleep.assert_called_with(3)
        self.assertTrue(result['succeeded'])

    def test_raises_on_failure(self):
        with patch('adminapi.taskqueue.status', return_value=_status(done=1, failed=1)):
            with self.assertRaises(TaskFailed) as ctx:
                taskqueue.wait_for_commit(42)
        self.assertIn('powerdns.sync #2', str(ctx.exception))
        self.assertEqual(ctx.exception.status['failed'], 1)

    def test_failure_returned_when_not_raising(self):
        with patch('adminapi.taskqueue.status', return_value=_status(failed=1)):
            result = taskqueue.wait_for_commit(42, raise_on_failure=False)
        self.assertFalse(result['succeeded'])

    def test_timeout(self):
        clock = iter([0, 1, 2, 100])
        with patch('adminapi.taskqueue.status', return_value=_status(pending=1)), \
                patch('adminapi.taskqueue.time.sleep'), \
                patch('adminapi.taskqueue.time.monotonic', side_effect=clock):
            with self.assertRaises(TimeoutError) as ctx:
                taskqueue.wait_for_commit(42, timeout=10, interval=1)
        self.assertIn('1 of 1 task(s) still unfinished', str(ctx.exception))

    def test_status_calls_api(self):
        with patch('adminapi.taskqueue.FunctionGroup') as group:
            group.return_value.status.return_value = {'finished': True}
            self.assertEqual(taskqueue.status(7), {'finished': True})
        group.assert_called_once_with('taskqueue')
        group.return_value.status.assert_called_once_with(7)
