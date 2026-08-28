from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase
from django.utils.timezone import now

from adminapi.filters import All, Any, BaseFilter, Regexp
from serveradmin.apps.models import Application
from serveradmin.querylog.models import QueryLoggingRule


class QueryLoggingRuleManagerTest(TransactionTestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice')
        self.bob = User.objects.create_user('bob')
        self.app_a = Application.objects.create(
            name='app-a', owner=self.alice, location='',
        )
        self.app_b = Application.objects.create(
            name='app-b', owner=self.bob, location='',
        )
        self.future = now() + timedelta(hours=1)
        self.past = now() - timedelta(hours=1)

    def test_application_only_rule_matches_any_user_of_that_application(self):
        QueryLoggingRule.objects.create(
            application=self.app_a, enabled_until=self.future,
        )

        self.assertTrue(
            QueryLoggingRule.objects.matching(self.app_a, self.bob).exists()
        )
        self.assertFalse(
            QueryLoggingRule.objects.matching(self.app_b, self.alice).exists()
        )

    def test_user_only_rule_matches_any_application_including_none(self):
        QueryLoggingRule.objects.create(
            user=self.alice, enabled_until=self.future,
        )

        self.assertTrue(
            QueryLoggingRule.objects.matching(self.app_a, self.alice).exists()
        )
        self.assertTrue(
            QueryLoggingRule.objects.matching(None, self.alice).exists()
        )
        self.assertFalse(
            QueryLoggingRule.objects.matching(self.app_a, self.bob).exists()
        )

    def test_rule_with_both_requires_both_to_match(self):
        QueryLoggingRule.objects.create(
            application=self.app_a, user=self.alice,
            enabled_until=self.future,
        )

        self.assertTrue(
            QueryLoggingRule.objects
            .matching(self.app_a, self.alice).exists()
        )
        self.assertFalse(
            QueryLoggingRule.objects.matching(self.app_a, self.bob).exists()
        )
        self.assertFalse(
            QueryLoggingRule.objects.matching(self.app_b, self.alice).exists()
        )

    def test_expired_rule_does_not_match(self):
        QueryLoggingRule.objects.create(
            application=self.app_a, enabled_until=self.past,
        )

        self.assertFalse(
            QueryLoggingRule.objects.matching(self.app_a, self.alice).exists()
        )

    def test_inactive_rule_does_not_match(self):
        QueryLoggingRule.objects.create(
            application=self.app_a, enabled_until=self.future,
            is_active=False,
        )

        self.assertFalse(
            QueryLoggingRule.objects.matching(self.app_a, self.alice).exists()
        )

    def test_clean_requires_application_or_user(self):
        rule = QueryLoggingRule(enabled_until=self.future)
        with self.assertRaises(ValidationError):
            rule.full_clean()

    def test_check_constraint_rejects_bare_insert(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                QueryLoggingRule.objects.create(enabled_until=self.future)


class QueryLoggingRuleMatchesQueryTest(TestCase):
    def setUp(self):
        self.future = now() + timedelta(hours=1)
        self.user = User.objects.create_user('alice')

    def _rule(self, trigger_query):
        return QueryLoggingRule(
            user=self.user, enabled_until=self.future,
            trigger_query=trigger_query,
        )

    def test_blank_trigger_query_always_matches(self):
        rule = self._rule('')
        self.assertTrue(rule.matches_query({}))
        self.assertTrue(rule.matches_query({'hostname': BaseFilter('x')}))

    def test_all_wildcard_matches_presence_regardless_of_value(self):
        rule = self._rule('hostname=All()')

        self.assertTrue(rule.matches_query({'hostname': Regexp('web.*')}))
        self.assertTrue(rule.matches_query({'hostname': Any('a', 'b')}))
        self.assertFalse(
            rule.matches_query({'environment': BaseFilter('prod')})
        )

    def test_any_wildcard_never_matches(self):
        rule = self._rule('hostname=Any()')

        self.assertFalse(rule.matches_query({'hostname': BaseFilter('x')}))
        self.assertFalse(rule.matches_query({}))

    def test_concrete_value_trigger_matches_equal_plain_value(self):
        rule = self._rule('environment=prod')

        self.assertTrue(
            rule.matches_query({'environment': BaseFilter('prod')})
        )

    def test_concrete_value_trigger_rejects_different_plain_value(self):
        rule = self._rule('environment=prod')

        self.assertFalse(
            rule.matches_query({'environment': BaseFilter('staging')})
        )

    def test_concrete_value_trigger_matches_inside_incoming_any(self):
        rule = self._rule('environment=prod')

        self.assertTrue(rule.matches_query({
            'environment': Any('staging', 'prod'),
        }))

    def test_concrete_value_trigger_rejects_incoming_regexp(self):
        rule = self._rule('environment=prod')

        self.assertFalse(rule.matches_query({
            'environment': Regexp('pro.*'),
        }))

    def test_concrete_value_trigger_rejects_incoming_all(self):
        rule = self._rule('environment=prod')

        self.assertFalse(rule.matches_query({'environment': All()}))

    def test_missing_attribute_does_not_match(self):
        rule = self._rule('environment=prod')

        self.assertFalse(rule.matches_query({}))

    def test_multiple_attributes_require_all_to_match(self):
        rule = self._rule('hostname=All() environment=prod')

        self.assertTrue(rule.matches_query({
            'hostname': BaseFilter('web1'),
            'environment': BaseFilter('prod'),
        }))
        self.assertFalse(rule.matches_query({
            'hostname': BaseFilter('web1'),
            'environment': BaseFilter('staging'),
        }))
        self.assertFalse(rule.matches_query({
            'environment': BaseFilter('prod'),
        }))

    def test_invalid_trigger_query_syntax_raises_validation_error(self):
        rule = self._rule("hostname=Regexp('[')")

        with self.assertRaises(ValidationError):
            rule.full_clean()
