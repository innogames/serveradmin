"""Serveradmin - Task queue worker

Copyright (c) 2026 InnoGames GmbH
"""

import logging
import signal
import time
from typing import List

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, close_old_connections, connection

from serveradmin.taskqueue import conf
from serveradmin.taskqueue.queue import (
    claim_next,
    pending_unregistered_types,
    prune,
    run_task,
    worker_id,
)
from serveradmin.taskqueue.registry import claimable_type_names, get_task_type

logger = logging.getLogger(__name__)

running = True


def _shutdown_handler(signum: int, frame) -> None:
    global running
    running = False
    logger.info('Received signal %s, shutting down after current task', signum)


class Command(BaseCommand):
    help = (
        'Process tasks from the task queue until terminated.  Several '
        'instances may run at the same time.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--once',
            action='store_true',
            help='Process all runnable tasks and exit',
        )
        parser.add_argument(
            '--task-type',
            action='append',
            default=[],
            metavar='NAME',
            help='Only process this task type (repeatable, default: all)',
        )
        parser.add_argument(
            '--poll-interval',
            type=float,
            default=None,
            help='Seconds to sleep when idle (default: TASKQUEUE_POLL_INTERVAL)',
        )
        parser.add_argument(
            '--lease-seconds',
            type=int,
            default=None,
            help='Lease duration for claimed tasks (default: TASKQUEUE_LEASE_SECONDS)',
        )
        parser.add_argument(
            '--worker-id',
            default=None,
            help='Identifier stored in locked_by (default: hostname:pid)',
        )
        parser.add_argument(
            '--max-tasks',
            type=int,
            default=0,
            help='Exit after processing this many tasks (default: unlimited)',
        )
        parser.add_argument(
            '--prune-interval',
            type=int,
            default=3600,
            help='Seconds between pruning runs, 0 disables pruning',
        )

    def handle(self, *args, **options) -> None:
        task_types = self._task_types(options['task_type'])
        worker = options['worker_id'] or worker_id()
        poll_interval = options['poll_interval']
        if poll_interval is None:
            poll_interval = conf.poll_interval()
        prune_interval = options['prune_interval']
        max_tasks = options['max_tasks']

        signal.signal(signal.SIGTERM, _shutdown_handler)
        signal.signal(signal.SIGINT, _shutdown_handler)

        self.stdout.write(
            'Worker {} serving task types: {}'.format(worker, ', '.join(task_types))
        )
        if not task_types:
            self.stderr.write('No task types registered, nothing to do')

        processed = 0
        last_housekeeping = 0.0
        while running:
            try:
                task = claim_next(worker, task_types, options['lease_seconds'])
            except DatabaseError:
                logger.exception('Database error while claiming, retrying')
                connection.close()
                time.sleep(poll_interval)
                continue

            if task is None:
                if options['once']:
                    break
                if prune_interval and time.monotonic() - last_housekeeping > prune_interval:
                    self._housekeeping()
                    last_housekeeping = time.monotonic()
                close_old_connections()
                time.sleep(poll_interval)
                continue

            run_task(task)
            processed += 1
            if max_tasks and processed >= max_tasks:
                logger.info('Processed %s tasks, exiting', processed)
                break

        self.stdout.write('Processed {} task(s), shutting down'.format(processed))

    def _task_types(self, requested: List[str]) -> List[str]:
        available = claimable_type_names()
        if not requested:
            return available
        for name in requested:
            task_type = get_task_type(name)
            if task_type is None:
                raise CommandError('Unknown task type {!r}'.format(name))
            if task_type.external:
                raise CommandError(
                    'Task type {!r} is processed by external workers'.format(name)
                )
        return sorted(set(requested))

    def _housekeeping(self) -> None:
        try:
            prune()
            unregistered = pending_unregistered_types()
            if unregistered:
                logger.warning(
                    'Pending tasks of unregistered task types: %s',
                    ', '.join(unregistered),
                )
        except DatabaseError:
            logger.exception('Database error during housekeeping')
            connection.close()
