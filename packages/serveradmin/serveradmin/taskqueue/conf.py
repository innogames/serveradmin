"""Serveradmin - Task queue settings

Copyright (c) 2026 InnoGames GmbH

All settings are read at call time so that they can be overridden in tests
with ``override_settings``.
"""

from django.conf import settings


def _get(name, default):
    return getattr(settings, name, default)


def run_inline() -> bool:
    """Run tasks synchronously right after enqueueing them

    This is a fallback for development and test setups without a
    ``run_taskqueue`` worker.  Failures are recorded on the task and never
    raised into the commit request.
    """
    return bool(_get('TASKQUEUE_RUN_INLINE', False))


def lease_seconds() -> int:
    """How long a claimed task stays locked before it may be re-claimed"""
    return int(_get('TASKQUEUE_LEASE_SECONDS', 300))


def retention_days() -> int:
    """How long finished tasks are kept before they are pruned"""
    return int(_get('TASKQUEUE_RETENTION_DAYS', 30))


def poll_interval() -> float:
    """Seconds the worker sleeps when there is nothing to do"""
    return float(_get('TASKQUEUE_POLL_INTERVAL', 1.0))


def default_max_attempts() -> int:
    return int(_get('TASKQUEUE_DEFAULT_MAX_ATTEMPTS', 5))


def retry_backoff_seconds() -> int:
    """Base delay for the exponential retry backoff"""
    return int(_get('TASKQUEUE_RETRY_BACKOFF_SECONDS', 30))


def retry_backoff_max_seconds() -> int:
    """Upper bound for the retry backoff"""
    return int(_get('TASKQUEUE_RETRY_BACKOFF_MAX_SECONDS', 900))
