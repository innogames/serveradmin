"""Serveradmin - Task queue registry

Copyright (c) 2026 InnoGames GmbH

Apps define a subclass of ``TaskType`` and register it, usually from their
``AppConfig.ready()``::

    from serveradmin.taskqueue.registry import TaskType, register

    @register
    class HelloTask(TaskType):
        name = 'example.hello'

        def produce(self, event):
            hostnames = [obj['hostname'] for obj in event.created_objects]
            if hostnames:
                return {'hostnames': hostnames}

        def run(self, task):
            say_hello(task.payload['hostnames'])
            return {'greeted': len(task.payload['hostnames'])}

Payloads must be JSON serializable and self-contained.  ``run()`` must be
idempotent and derive the desired state from the database at run time,
because tasks may be retried and several workers may run concurrently.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Set, Union

if TYPE_CHECKING:
    from serveradmin.taskqueue.models import Task


@dataclass
class CommitEvent:
    """Everything the post_commit signal knows about a commit

    ``created``, ``changed`` and ``deleted`` are the raw commit payloads as
    sent by the client (``deleted`` is a list of object ids).  The
    ``*_objects`` lists contain the materialized objects: ``created_objects``
    and ``changed_objects`` after the commit, ``unchanged_objects`` (the
    changed objects before the commit) and ``deleted_objects`` before it.
    """

    commit_id: Optional[int] = None
    created: List[dict] = field(default_factory=list)
    changed: List[dict] = field(default_factory=list)
    deleted: List[int] = field(default_factory=list)
    created_objects: List[dict] = field(default_factory=list)
    changed_objects: List[dict] = field(default_factory=list)
    unchanged_objects: List[dict] = field(default_factory=list)
    deleted_objects: List[dict] = field(default_factory=list)
    user: Any = None
    app: Any = None

    @classmethod
    def from_signal(cls, kwargs: dict) -> 'CommitEvent':
        return cls(
            commit_id=kwargs.get('commit_id'),
            created=list(kwargs.get('created') or []),
            changed=list(kwargs.get('changed') or []),
            deleted=list(kwargs.get('deleted') or []),
            created_objects=list(kwargs.get('created_objects') or []),
            changed_objects=list(kwargs.get('changed_objects') or []),
            unchanged_objects=list(kwargs.get('unchanged_objects') or []),
            deleted_objects=list(kwargs.get('deleted_objects') or []),
            user=kwargs.get('user'),
            app=kwargs.get('app'),
        )

    @property
    def is_empty(self) -> bool:
        return not (self.created or self.changed or self.deleted)

    def changed_object_ids(self) -> Set[int]:
        return {c['object_id'] for c in self.changed if 'object_id' in c}

    def changed_attribute_ids(self) -> Set[str]:
        return {a for c in self.changed for a in c if a != 'object_id'}


class TaskType:
    """Base class for task types, see the module docstring"""

    # Unique registry key, by convention "<app>.<verb>"
    name: str = ''
    # None means: use the TASKQUEUE_* default
    max_attempts: Optional[int] = None
    lease_seconds: Optional[int] = None
    retry_backoff_seconds: Optional[int] = None
    retry_backoff_max_seconds: Optional[int] = None
    # External task types are never claimed by run_taskqueue.  They are
    # processed by external workers which report back through the API.
    external: bool = False

    def enabled(self) -> bool:
        """Whether tasks should be produced, e.g. required settings exist"""
        return True

    def produce(
        self, event: CommitEvent
    ) -> Union[None, dict, Iterable[dict]]:
        """Return payload(s) for tasks to enqueue for this commit, or None"""
        return None

    def run(self, task: 'Task') -> Optional[dict]:
        """Do the work; return a small JSON serializable result or None"""
        raise NotImplementedError(
            'Task type {} does not implement run()'.format(self.name)
        )

    def is_retryable(self, exc: BaseException) -> bool:
        """Whether a failure with this exception should be retried"""
        return True

    def get_status(self, task: 'Task') -> dict:
        """Extra or overriding keys for the taskqueue.status API

        The returned dict is merged over ``Task.as_status_dict()``.  Keep
        ``state`` and ``finished`` consistent if you override them.
        """
        return {}

    def __repr__(self) -> str:
        return '<{} {}>'.format(type(self).__name__, self.name)


REGISTRY: Dict[str, TaskType] = {}


def register(task_type: Union[TaskType, type]) -> Union[TaskType, type]:
    """Register a TaskType class or instance, usable as a class decorator"""
    instance = task_type() if isinstance(task_type, type) else task_type
    if not isinstance(instance, TaskType):
        raise TypeError('{!r} is not a TaskType'.format(task_type))
    if not instance.name:
        raise ValueError('{!r} has no name'.format(task_type))

    existing = REGISTRY.get(instance.name)
    if existing is not None and type(existing) is not type(instance):
        raise ValueError(
            'Task type {!r} is already registered by {!r}'.format(
                instance.name, type(existing)
            )
        )

    REGISTRY[instance.name] = instance
    return task_type


def unregister(name: str) -> None:
    REGISTRY.pop(name, None)


def get_task_type(name: str) -> Optional[TaskType]:
    return REGISTRY.get(name)


def claimable_type_names() -> List[str]:
    """Names of registered task types the run_taskqueue worker may run"""
    return sorted(n for n, t in REGISTRY.items() if not t.external)
