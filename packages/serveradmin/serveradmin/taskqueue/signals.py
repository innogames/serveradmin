"""Serveradmin - Task queue post_commit receiver

Copyright (c) 2026 InnoGames GmbH
"""

import logging
from typing import Iterable, List, Union

from serveradmin.taskqueue.queue import build_task, enqueue_many
from serveradmin.taskqueue.registry import REGISTRY, CommitEvent

logger = logging.getLogger(__name__)


def _normalize(payloads: Union[None, dict, Iterable[dict]]) -> List[dict]:
    if payloads is None:
        return []
    if isinstance(payloads, dict):
        return [payloads]
    return list(payloads)


def enqueue_commit_tasks(sender, **kwargs) -> None:
    """Ask every registered task type for tasks and enqueue them

    Connected to serverdb's post_commit signal, which is sent after the
    commit transaction.  A broken producer is logged and skipped so that it
    can neither block other task types nor the commit.
    """
    event = CommitEvent.from_signal(kwargs)
    tasks = []
    for task_type in list(REGISTRY.values()):
        try:
            if not task_type.enabled():
                continue
            payloads = task_type.produce(event)
        except Exception:  # noqa: BLE001 - one producer must not break others
            logger.exception(
                'Task type %s failed to produce tasks for commit %s',
                task_type.name,
                event.commit_id,
            )
            continue

        for payload in _normalize(payloads):
            tasks.append(build_task(task_type, payload, commit_id=event.commit_id))

    if not tasks:
        return

    enqueue_many(tasks)
    logger.info(
        'Enqueued %s task(s) for commit %s: %s',
        len(tasks),
        event.commit_id,
        ', '.join(sorted({t.task_type for t in tasks})),
    )
