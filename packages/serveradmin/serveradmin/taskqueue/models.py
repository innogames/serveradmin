"""Serveradmin - Task queue

Copyright (c) 2026 InnoGames GmbH
"""

from datetime import datetime
from typing import Optional

from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from serveradmin.serverdb.models import Change, ChangeCommit


def _isoformat(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


class Task(models.Model):
    """One unit of asynchronous work, usually produced by a commit

    The state machine is driven by ``serveradmin.taskqueue.queue``:

        pending --claim--> running --complete--> done
                              |  \\--fail (attempts left)--> pending (run_after in the future)
                              \\--fail (no attempts left)--> failed
        pending --cancel--> cancelled

    A running task whose lease (``locked_until``) expired is re-claimed by
    the next worker; ``attempts`` acts as a fencing token so that a worker
    which lost its lease cannot overwrite the newer state.
    """

    class State(models.TextChoices):
        PENDING = 'pending', _('pending')
        RUNNING = 'running', _('running')
        DONE = 'done', _('done')
        FAILED = 'failed', _('failed')
        CANCELLED = 'cancelled', _('cancelled')

    TERMINAL_STATES = (State.DONE, State.FAILED, State.CANCELLED)

    id = models.BigAutoField(primary_key=True)
    # Registry key of the TaskType, e.g. "powerdns.sync"
    task_type = models.CharField(max_length=64)
    # Null for commits which did not log any change (no ChangeCommit row) and
    # for tasks enqueued outside of a commit.  SET_NULL: pruning the change
    # log must never drop pending work.
    commit = models.ForeignKey(
        ChangeCommit,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='tasks',
    )
    payload = models.JSONField(
        default=dict, blank=True, encoder=Change.ChangeJSONEncoder
    )
    state = models.CharField(
        max_length=10, choices=State.choices, default=State.PENDING
    )
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)
    # Earliest time the task may be claimed, used for retry backoff
    run_after = models.DateTimeField(default=now)
    locked_by = models.CharField(max_length=128, blank=True, default='')
    locked_at = models.DateTimeField(null=True, blank=True)
    # Lease expiry, only set while running
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=now)
    finished_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default='')
    result = models.JSONField(
        null=True, blank=True, encoder=Change.ChangeJSONEncoder
    )

    class Meta:
        ordering = ('id',)
        indexes = [
            # Claim query
            models.Index(
                fields=['state', 'task_type', 'run_after', 'id'],
                name='taskqueue_task_claim_idx',
            ),
            # Lease expiry scan
            models.Index(
                fields=['state', 'locked_until'],
                name='taskqueue_task_lease_idx',
            ),
            # Prune
            models.Index(
                fields=['state', 'finished_at'],
                name='taskqueue_task_prune_idx',
            ),
        ]

    def __str__(self) -> str:
        return '#{} {} [{}]'.format(self.id, self.task_type, self.state)

    @property
    def finished(self) -> bool:
        return self.state in self.TERMINAL_STATES

    def as_status_dict(self) -> dict:
        """Default status representation used by the taskqueue.status API"""
        return {
            'id': self.id,
            'task_type': self.task_type,
            'state': self.state,
            'finished': self.finished,
            'attempts': self.attempts,
            'max_attempts': self.max_attempts,
            'created_at': _isoformat(self.created_at),
            'run_after': _isoformat(self.run_after),
            'locked_by': self.locked_by,
            'locked_until': _isoformat(self.locked_until),
            'finished_at': _isoformat(self.finished_at),
            'last_error': self.last_error,
            'result': self.result,
        }
