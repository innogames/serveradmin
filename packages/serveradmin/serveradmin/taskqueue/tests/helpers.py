"""Serveradmin - Task queue test helpers

Copyright (c) 2026 InnoGames GmbH
"""

from typing import Optional

from serveradmin.taskqueue.registry import TaskType, register, unregister


class DummyTaskType(TaskType):
    """Records produce() events and run() calls; behaviour is configurable"""

    name = 'test.dummy'
    max_attempts = 3
    retry_backoff_seconds = 10
    retry_backoff_max_seconds = 100

    is_enabled = True
    produce_payload = None  # None -> derive from event, dict/list -> as is
    run_exception = None
    run_result = {'ok': True}
    events = []
    runs = []

    def enabled(self) -> bool:
        return self.is_enabled

    def produce(self, event) -> Optional[dict]:
        self.events.append(event)
        if self.produce_payload is not None:
            return self.produce_payload
        if event.is_empty:
            return None
        return {
            'created': [obj['hostname'] for obj in event.created_objects],
            'changed': sorted(event.changed_object_ids()),
            'deleted': [obj['hostname'] for obj in event.deleted_objects],
        }

    def run(self, task) -> dict:
        self.runs.append(task.pk)
        if self.run_exception is not None:
            raise self.run_exception
        return self.run_result


class RaisingProducer(TaskType):
    name = 'test.raising'

    def produce(self, event) -> None:
        raise RuntimeError('boom')


class ExternalTaskType(TaskType):
    name = 'test.external'
    external = True


class DummyTaskTypeMixin:
    """Register a fresh DummyTaskType for every test"""

    def setUp(self) -> None:
        super().setUp()
        self.dummy = DummyTaskType()
        self.dummy.events = []
        self.dummy.runs = []
        register(self.dummy)
        self.addCleanup(unregister, DummyTaskType.name)
