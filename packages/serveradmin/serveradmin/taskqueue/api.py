"""Serveradmin - Task queue remote API

Copyright (c) 2026 InnoGames GmbH
"""

from collections import Counter

from serveradmin.api import ApiError
from serveradmin.api.decorators import api_function
from serveradmin.serverdb.models import ChangeCommit
from serveradmin.taskqueue.models import Task
from serveradmin.taskqueue.registry import get_task_type


def task_status(task: Task) -> dict:
    """Status dict of one task, letting the task type override keys"""
    status = task.as_status_dict()
    task_type = get_task_type(task.task_type)
    if task_type is not None:
        status.update(task_type.get_status(task))
    return status


@api_function(group='taskqueue')
def status(commit_id: int) -> dict:
    """Return the task queue status for a commit

    :param commit_id: The commit id as returned by Query.commit()

    :return: dict with ``finished`` (no task will change anymore),
             ``succeeded`` (finished and every task is done), per state
             counts and the list of ``tasks``.  A commit without tasks is
             finished and succeeded.
    """
    if isinstance(commit_id, bool) or not isinstance(commit_id, int):
        raise ApiError('commit_id must be an integer')

    tasks = list(Task.objects.filter(commit_id=commit_id).order_by('id'))
    if not tasks and not ChangeCommit.objects.filter(pk=commit_id).exists():
        raise ApiError('Unknown commit id {}'.format(commit_id))

    items = [task_status(task) for task in tasks]
    counts = Counter(item['state'] for item in items)

    return {
        'commit_id': commit_id,
        'total': len(items),
        'pending': counts[Task.State.PENDING],
        'running': counts[Task.State.RUNNING],
        'done': counts[Task.State.DONE],
        'failed': counts[Task.State.FAILED],
        'cancelled': counts[Task.State.CANCELLED],
        'finished': all(item['finished'] for item in items),
        'succeeded': all(item['state'] == Task.State.DONE for item in items),
        'tasks': items,
    }
