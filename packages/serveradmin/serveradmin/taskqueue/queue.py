"""Serveradmin - Task queue operations

Copyright (c) 2026 InnoGames GmbH

All functions use short transactions only.  The database is accessed through
PgBouncer in transaction pooling mode, so nothing here may rely on session
state (no session level advisory locks, no connection local settings).
"""

import logging
import os
import platform
import traceback
from datetime import datetime, timedelta
from typing import Iterable, List, Optional, Sequence, Union

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils.timezone import now

from serveradmin.taskqueue import conf
from serveradmin.taskqueue.models import Task
from serveradmin.taskqueue.registry import TaskType, get_task_type

logger = logging.getLogger(__name__)

# Keep tracebacks in last_error reasonably small
MAX_ERROR_LENGTH = 10000


def worker_id() -> str:
    return '{}:{}'.format(platform.node(), os.getpid())


def resolve_task_type(task_type: Union[str, TaskType, type]) -> TaskType:
    if isinstance(task_type, TaskType):
        return task_type
    if isinstance(task_type, type) and issubclass(task_type, TaskType):
        name = task_type.name
    else:
        name = task_type
    instance = get_task_type(name)
    if instance is None:
        raise ValueError('Unknown task type {!r}'.format(name))
    return instance


def build_task(
    task_type: Union[str, TaskType, type],
    payload: dict,
    commit_id: Optional[int] = None,
    run_after: Optional[datetime] = None,
    max_attempts: Optional[int] = None,
) -> Task:
    """Create an unsaved Task for the given type"""
    task_type = resolve_task_type(task_type)
    if max_attempts is None:
        max_attempts = task_type.max_attempts or conf.default_max_attempts()
    return Task(
        task_type=task_type.name,
        commit_id=commit_id,
        payload=payload or {},
        max_attempts=max_attempts,
        run_after=run_after or now(),
    )


def enqueue(
    task_type: Union[str, TaskType, type],
    payload: dict,
    commit_id: Optional[int] = None,
    run_after: Optional[datetime] = None,
    max_attempts: Optional[int] = None,
) -> Task:
    """Enqueue a single task"""
    task = build_task(task_type, payload, commit_id, run_after, max_attempts)
    task.save()
    logger.info(
        'Enqueued task %s (%s) for commit %s', task.pk, task.task_type, commit_id
    )
    if conf.run_inline():
        run_inline([task])
    return task


def enqueue_many(tasks: Sequence[Task]) -> List[Task]:
    """Save tasks built with build_task() in one transaction"""
    tasks = list(tasks)
    if not tasks:
        return tasks
    with transaction.atomic():
        Task.objects.bulk_create(tasks)
    if conf.run_inline():
        run_inline(tasks)
    return tasks


def run_inline(tasks: Iterable[Task]) -> None:
    """Process tasks synchronously, oldest first (TASKQUEUE_RUN_INLINE)

    This goes through the normal claim path so that state transitions are
    the same as in the worker.
    """
    for task in tasks:
        task_type = get_task_type(task.task_type)
        if task_type is None or task_type.external:
            continue
        claimed = claim_next(worker_id(), [task.task_type])
        if claimed is not None:
            run_task(claimed)


def claim_next(
    worker: str,
    task_types: Sequence[str],
    lease_seconds: Optional[int] = None,
) -> Optional[Task]:
    """Claim the oldest runnable task of the given types

    Runnable means pending with ``run_after`` in the past, or running with an
    expired lease (the worker died).  Rows are locked with SKIP LOCKED so
    that several workers never claim the same task.  The task is returned in
    state running; do the work outside of any transaction and then call
    complete() or fail().
    """
    if not task_types:
        return None

    current = now()
    pending = Q(state=Task.State.PENDING, run_after__lte=current)
    lease_expired = Q(state=Task.State.RUNNING, locked_until__lt=current)
    with transaction.atomic():
        task = (
            Task.objects.select_for_update(skip_locked=True)
            .filter(task_type__in=task_types)
            .filter(pending | lease_expired)
            .order_by('id')
            .first()
        )
        if task is None:
            return None

        if task.state == Task.State.RUNNING:
            logger.warning(
                'Task %s: lease of worker %s expired, re-claiming',
                task.pk,
                task.locked_by,
            )

        if lease_seconds is None:
            task_type = get_task_type(task.task_type)
            lease_seconds = (
                task_type.lease_seconds if task_type else None
            ) or conf.lease_seconds()

        task.state = Task.State.RUNNING
        task.attempts += 1
        task.locked_by = worker
        task.locked_at = current
        task.locked_until = current + timedelta(seconds=lease_seconds)
        task.save(
            update_fields=[
                'state', 'attempts', 'locked_by', 'locked_at', 'locked_until'
            ]
        )

    logger.debug('Task %s claimed by %s', task.pk, worker)
    return task


def _cas(task: Task, **values) -> bool:
    """Update the task only if it is still running with our attempt number

    ``attempts`` is the fencing token: a worker whose lease expired and whose
    task was re-claimed has a stale attempt number and its update is ignored.
    """
    updated = Task.objects.filter(
        pk=task.pk, state=Task.State.RUNNING, attempts=task.attempts
    ).update(**values)
    if not updated:
        logger.warning('Task %s: lost lease, ignoring state update', task.pk)
        return False
    for key, value in values.items():
        setattr(task, key, value)
    return True


def complete(task: Task, result: Optional[dict] = None) -> bool:
    return _cas(
        task,
        state=Task.State.DONE,
        finished_at=now(),
        result=result,
        locked_until=None,
        locked_by='',
    )


def fail(task: Task, exc: BaseException) -> bool:
    """Record a failure; re-queue with backoff if attempts are left"""
    task_type = get_task_type(task.task_type)
    error = ''.join(traceback.format_exception(exc))[-MAX_ERROR_LENGTH:]

    attempts_left = task.attempts < task.max_attempts
    retryable = attempts_left and (task_type is None or task_type.is_retryable(exc))
    if retryable:
        base = (
            task_type.retry_backoff_seconds if task_type else None
        ) or conf.retry_backoff_seconds()
        cap = (
            task_type.retry_backoff_max_seconds if task_type else None
        ) or conf.retry_backoff_max_seconds()
        delay = min(base * 2 ** (task.attempts - 1), cap)
        logger.info(
            'Task %s: attempt %s/%s failed, retrying in %ss',
            task.pk, task.attempts, task.max_attempts, delay,
        )
        return _cas(
            task,
            state=Task.State.PENDING,
            run_after=now() + timedelta(seconds=delay),
            last_error=error,
            locked_until=None,
            locked_by='',
        )

    logger.error(
        'Task %s: attempt %s/%s failed, giving up',
        task.pk, task.attempts, task.max_attempts,
    )
    return _cas(
        task,
        state=Task.State.FAILED,
        finished_at=now(),
        last_error=error,
        locked_until=None,
        locked_by='',
    )


def extend_lease(task: Task, seconds: int) -> bool:
    """Extend the lease of a long running task"""
    return _cas(task, locked_until=now() + timedelta(seconds=seconds))


def run_task(task: Task) -> bool:
    """Run a claimed task and record the outcome; never raises"""
    task_type = get_task_type(task.task_type)
    if task_type is None:
        fail(task, RuntimeError('Unknown task type {}'.format(task.task_type)))
        return False

    try:
        result = task_type.run(task)
    except Exception as exc:  # noqa: BLE001 - the worker must survive anything
        logger.exception('Task %s (%s) failed', task.pk, task.task_type)
        fail(task, exc)
        return False

    return complete(task, result)


def retry(tasks: Union[QuerySet, Iterable[Task]]) -> int:
    """Re-queue finished tasks, resetting their attempts"""
    if not isinstance(tasks, QuerySet):
        tasks = Task.objects.filter(pk__in=[t.pk for t in tasks])
    return tasks.filter(state__in=Task.TERMINAL_STATES).update(
        state=Task.State.PENDING,
        attempts=0,
        run_after=now(),
        last_error='',
        finished_at=None,
        locked_by='',
        locked_at=None,
        locked_until=None,
        result=None,
    )


def cancel(tasks: Union[QuerySet, Iterable[Task]]) -> int:
    """Cancel pending tasks"""
    if not isinstance(tasks, QuerySet):
        tasks = Task.objects.filter(pk__in=[t.pk for t in tasks])
    return tasks.filter(state=Task.State.PENDING).update(
        state=Task.State.CANCELLED, finished_at=now()
    )


def prune(retention_days: Optional[int] = None, batch_size: int = 1000) -> int:
    """Delete finished tasks older than the retention period, in batches"""
    if retention_days is None:
        retention_days = conf.retention_days()
    cutoff = now() - timedelta(days=retention_days)
    total = 0
    while True:
        ids = list(
            Task.objects.filter(
                state__in=Task.TERMINAL_STATES, finished_at__lt=cutoff
            )
            .order_by('id')
            .values_list('pk', flat=True)[:batch_size]
        )
        if not ids:
            break
        deleted, _ = Task.objects.filter(pk__in=ids).delete()
        total += deleted
        if len(ids) < batch_size:
            break
    if total:
        logger.info('Pruned %s finished task(s) older than %s days', total, retention_days)
    return total


def pending_unregistered_types() -> List[str]:
    """Task types with pending work that no installed app has registered"""
    pending = (
        Task.objects.filter(state=Task.State.PENDING)
        .values_list('task_type', flat=True)
        .distinct()
    )
    return sorted(t for t in pending if get_task_type(t) is None)
