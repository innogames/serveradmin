"""Serveradmin - adminapi task queue helpers

Copyright (c) 2026 InnoGames GmbH

Commits return immediately; asynchronous work like DNS pushes is queued on
the server and processed later.  Use ``wait_for_commit()`` when you need to
know that this work is done::

    commit_id = query.commit()
    adminapi.taskqueue.wait_for_commit(commit_id, timeout=120)
"""

import time
from typing import Optional

from adminapi.api import FunctionGroup
from adminapi.exceptions import ApiError

API_GROUP = 'taskqueue'


class TaskFailed(ApiError):
    """At least one task of the commit failed or was cancelled"""

    def __init__(self, status: dict):
        self.status = status
        failed = [
            t for t in status.get('tasks', []) if t.get('state') in ('failed', 'cancelled')
        ]
        message = 'Commit {}: {} task(s) failed: {}'.format(
            status.get('commit_id'),
            len(failed),
            ', '.join(
                '{} #{}'.format(t.get('task_type'), t.get('id')) for t in failed
            ),
        )
        super().__init__(message, status_code=None)


def status(commit_id: int) -> dict:
    """Return the task queue status of a commit, see taskqueue.status"""
    return FunctionGroup(API_GROUP).status(commit_id)


def wait_for_commit(
    commit_id: Optional[int],
    timeout: float = 300.0,
    interval: float = 2.0,
    raise_on_failure: bool = True,
) -> dict:
    """Poll until all tasks of a commit are finished

    :param commit_id: as returned by Query.commit(); None returns immediately
    :param timeout: seconds to wait before raising TimeoutError
    :param interval: seconds between polls
    :param raise_on_failure: raise TaskFailed if not all tasks succeeded

    :return: the final status dict
    """
    if commit_id is None:
        return {
            'commit_id': None,
            'total': 0,
            'finished': True,
            'succeeded': True,
            'tasks': [],
        }

    deadline = time.monotonic() + timeout
    while True:
        result = status(commit_id)
        if result['finished']:
            if raise_on_failure and not result['succeeded']:
                raise TaskFailed(result)
            return result
        if time.monotonic() >= deadline:
            finished = sum(result.get(s, 0) for s in ('done', 'failed', 'cancelled'))
            raise TimeoutError(
                'Commit {}: {} of {} task(s) still unfinished after {}s'.format(
                    commit_id, result['total'] - finished, result['total'], timeout
                )
            )
        time.sleep(interval)
