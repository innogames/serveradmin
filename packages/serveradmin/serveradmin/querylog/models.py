"""Serveradmin - Ad-hoc Query Logging

Copyright (c) 2026 InnoGames GmbH
"""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.timezone import now

from adminapi.exceptions import DatatypeError
from adminapi.filters import Any, BaseFilter
from adminapi.parse import parse_query
from serveradmin.apps.models import Application


def _extract_candidate_values(filter_obj):
    """Best-effort extraction of concrete values from an incoming filter

    Used to evaluate a QueryLoggingRule.trigger_query condition against
    the actual filter object a query used for one attribute. Only two
    incoming filter shapes are considered safely decidable; anything
    else (Regexp, All, Not, GreaterThan, Contains, ...) conservatively
    yields no candidates, meaning the trigger condition for that
    attribute cannot be satisfied. This is a known, intentional
    limitation - comparing two filter expressions isn't well-defined.
    """
    if type(filter_obj) is BaseFilter:
        return [filter_obj.value]
    if type(filter_obj) is Any:
        return [v.value for v in filter_obj.values if type(v) is BaseFilter]
    return []


class QueryLoggingRuleManager(models.Manager):
    def matching(self, application, user):
        """Return the currently active rules that apply

        A rule with only "application" set matches any user of that
        application. A rule with only "user" set matches that user
        regardless of application (this is the only way Servershell
        queries, which have no application, can ever be logged). A rule
        with both set requires both to match.

        "application" may be None (Servershell has no Application).
        """
        clauses = Q(pk__in=[])
        if application is not None and user is not None:
            clauses |= Q(application=application, user=user)
        if application is not None:
            clauses |= Q(application=application, user__isnull=True)
        if user is not None:
            clauses |= Q(user=user, application__isnull=True)

        return self.filter(
            is_active=True, enabled_until__gt=now(),
        ).filter(clauses).order_by('pk')


class QueryLoggingRule(models.Model):
    """Admin-configured rule enabling ad-hoc query logging

    Logging for serveradmin.api.views.dataset_query and
    serveradmin.servershell.views.get_results is off by default. It is
    only turned on for the application and/or user targeted by an active
    rule, and only until "enabled_until".
    """

    application = models.ForeignKey(
        Application, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='query_logging_rules',
    )
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='query_logging_rules',
    )
    is_active = models.BooleanField(
        default=True,
        help_text=(
            'Uncheck to disable this rule immediately without losing its '
            'configured expiry.'
        ),
    )
    enabled_until = models.DateTimeField(
        help_text='Logging stops matching automatically after this time.',
    )
    note = models.TextField(
        blank=True,
        help_text='Reason for enabling logging, e.g. a ticket link.',
    )
    trigger_query = models.CharField(
        max_length=1000,
        blank=True,
        help_text=(
            'Optional. Only log a query if its filters satisfy this '
            'condition, e.g. "hostname=Regexp(\'web.*\') '
            'environment=prod". Leave blank to log every query matched '
            'by application/user above. Use attr=All() to match any '
            'query that references "attr" at all, regardless of its '
            'value.'
        ),
    )
    created_at = models.DateTimeField(default=now, editable=False)
    created_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, editable=False,
        related_name='created_query_logging_rules',
    )

    objects = QueryLoggingRuleManager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(application__isnull=False) | Q(user__isnull=False)
                ),
                name='querylog_rule_application_or_user_required',
            ),
        ]
        indexes = [
            models.Index(fields=['is_active', 'enabled_until']),
        ]

    def clean(self):
        if self.application_id is None and self.user_id is None:
            raise ValidationError(
                'At least one of application or user must be set.'
            )
        if self.trigger_query:
            try:
                parse_query(self.trigger_query)
            except DatatypeError as error:
                raise ValidationError({
                    'trigger_query': 'Invalid query syntax: {}'.format(
                        error
                    ),
                })

    def matches_query(self, filters):
        """Does the actual query's filters dict satisfy trigger_query?

        filters is the {attribute_id: BaseFilter-or-subclass} dict of the
        actual ad-hoc query being considered for logging. Returns True
        unconditionally if trigger_query is blank (unrestricted, the
        default).
        """
        if not self.trigger_query:
            return True

        trigger_filters = parse_query(self.trigger_query)
        for attribute_id, trigger_filter in trigger_filters.items():
            destiny = trigger_filter.destiny()
            if destiny is True:
                # e.g. attr=All(): matches unconditionally, so only the
                # attribute's presence in the query matters.
                if attribute_id not in filters:
                    return False
                continue
            if destiny is False:
                # e.g. the degenerate attr=Any(): never matches.
                return False

            if attribute_id not in filters:
                return False

            candidates = _extract_candidate_values(filters[attribute_id])
            if not any(trigger_filter.matches(v) for v in candidates):
                return False

        return True

    def __str__(self):
        target = self.application or self.user or 'nobody'
        return '{} until {}'.format(target, self.enabled_until)


class QueryLog(models.Model):
    """A single logged ad-hoc query

    Only created when a matching, active QueryLoggingRule exists at the
    time the query ran. See serveradmin.querylog.utils.log_query().
    """

    class Source(models.TextChoices):
        API = 'api', 'API'
        SERVERSHELL = 'servershell', 'Servershell'

    rule = models.ForeignKey(
        QueryLoggingRule, null=True, on_delete=models.SET_NULL,
        related_name='logs',
    )
    application = models.ForeignKey(
        Application, null=True, on_delete=models.SET_NULL,
        related_name='query_logs',
    )
    user = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL,
        related_name='query_logs',
    )
    source = models.CharField(max_length=16, choices=Source.choices)
    query_text = models.TextField()
    filters = models.JSONField(null=True, blank=True)
    restrict = models.JSONField(null=True, blank=True)
    order_by = models.JSONField(null=True, blank=True)
    duration_ms = models.FloatField()
    num_results = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(default=now, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['source', 'created_at']),
        ]

    def __str__(self):
        return '{} query at {}'.format(self.source, self.created_at)
