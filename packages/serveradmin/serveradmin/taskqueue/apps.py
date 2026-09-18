"""Serveradmin - Task queue

Copyright (c) 2026 InnoGames GmbH
"""

from django.apps import AppConfig


class TaskqueueConfig(AppConfig):
    name = 'serveradmin.taskqueue'
    verbose_name = 'Task queue'

    def ready(self):
        import serveradmin.taskqueue.api  # noqa: F401

        from serveradmin.serverdb.signals import post_commit
        from serveradmin.taskqueue.signals import enqueue_commit_tasks

        post_commit.connect(
            enqueue_commit_tasks, dispatch_uid='taskqueue_enqueue_commit_tasks'
        )
