"""Serveradmin - Ad-hoc Query Logging

Copyright (c) 2026 InnoGames GmbH
"""

from logging import getLogger

from serveradmin.querylog.models import QueryLog, QueryLoggingRule

logger = getLogger('serveradmin')


def log_query(
    *,
    application,
    user,
    source,
    filters,
    restrict,
    order_by,
    duration_seconds,
    query_text,
    num_results=None,
):
    """Persist a QueryLog row if an active QueryLoggingRule matches

    This is a no-op (no DB write) when nothing is configured to log the
    given application/user, which is the default and common case. Also
    skips rules whose trigger_query does not match the query's actual
    filters.

    Must never raise: a bug or outage in logging must not break the
    actual query response. Returns True if a row was written, else False.
    """
    try:
        rule = None
        for candidate in QueryLoggingRule.objects.matching(application, user):
            if candidate.matches_query(filters):
                rule = candidate
                break
        if rule is None:
            return False

        QueryLog.objects.create(
            rule=rule,
            application=application,
            user=user,
            source=source,
            query_text=query_text,
            filters=_serialize_filters(filters),
            restrict=restrict,
            order_by=order_by,
            duration_ms=duration_seconds * 1000.0,
            num_results=num_results,
        )
        return True
    except Exception:
        logger.warning(
            'querylog: Failed to record query log for source=%s '
            'application=%s user=%s', source, application, user,
            exc_info=True,
        )
        return False


def _serialize_filters(filters):
    if not filters:
        return None
    return {
        attribute_id: filt.serialize()
        for attribute_id, filt in filters.items()
    }
