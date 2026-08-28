from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TransactionTestCase
from django.utils.timezone import now

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
