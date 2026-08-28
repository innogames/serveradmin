from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.test import TransactionTestCase
from django.utils.timezone import now

from adminapi.filters import Any, BaseFilter, Regexp
from serveradmin.api.views import dataset_query
from serveradmin.apps.models import Application
from serveradmin.querylog.models import QueryLog, QueryLoggingRule
from serveradmin.querylog.utils import log_query


class LogQueryTest(TransactionTestCase):
    fixtures = ['test_dataset.json']

    def setUp(self):
        self.user = User.objects.create_user('alice')
        self.app = Application.objects.create(
            name='app-a', owner=self.user, location='',
        )

    def _log(self, **overrides):
        kwargs = dict(
            application=self.app,
            user=self.user,
            source=QueryLog.Source.API,
            filters={'hostname': BaseFilter('test0')},
            restrict=['hostname'],
            order_by=None,
            duration_seconds=0.05,
            query_text="Query({'hostname': BaseFilter('test0')})",
            num_results=1,
        )
        kwargs.update(overrides)
        return log_query(**kwargs)

    def test_no_rule_no_log(self):
        self.assertFalse(self._log())
        self.assertEqual(0, QueryLog.objects.count())

    def test_matching_rule_creates_log_row(self):
        QueryLoggingRule.objects.create(
            application=self.app, enabled_until=now() + timedelta(hours=1),
        )

        self.assertTrue(self._log())

        log = QueryLog.objects.get()
        self.assertEqual(self.app, log.application)
        self.assertEqual(self.user, log.user)
        self.assertEqual(QueryLog.Source.API, log.source)
        self.assertEqual(50.0, log.duration_ms)
        self.assertEqual(1, log.num_results)
        self.assertEqual({'hostname': 'test0'}, log.filters)

    def test_filters_round_trip_regexp_and_any(self):
        QueryLoggingRule.objects.create(
            application=self.app, enabled_until=now() + timedelta(hours=1),
        )

        self._log(filters={
            'hostname': Regexp('test.*'),
            'servertype': Any('test0', 'test1'),
        })

        log = QueryLog.objects.get()
        self.assertEqual(
            Regexp('test.*').serialize(), log.filters['hostname'],
        )
        reconstructed = BaseFilter.deserialize(log.filters['servertype'])
        self.assertIsInstance(reconstructed, Any)

    def test_log_query_never_raises_on_internal_error(self):
        QueryLoggingRule.objects.create(
            application=self.app, enabled_until=now() + timedelta(hours=1),
        )

        with patch.object(
            QueryLog.objects, 'create', side_effect=Exception('boom'),
        ):
            with self.assertLogs('serveradmin', level='WARNING'):
                result = self._log()

        self.assertFalse(result)
        self.assertEqual(0, QueryLog.objects.count())


class DatasetQueryLoggingTest(TransactionTestCase):
    fixtures = ['test_dataset.json']

    def setUp(self):
        self.alice = User.objects.create_user('alice')
        self.app_a = Application.objects.create(
            name='app-a', owner=self.alice, location='',
        )
        self.bob = User.objects.create_user('bob')
        self.app_b = Application.objects.create(
            name='app-b', owner=self.bob, location='',
        )

    def _call(self, app):
        data = {
            'filters': {'hostname': 'test0'},
            'restrict': ['hostname'],
        }
        return dataset_query.__wrapped__(None, app, data)

    def test_logs_when_app_rule_active(self):
        QueryLoggingRule.objects.create(
            application=self.app_a, enabled_until=now() + timedelta(hours=1),
        )

        result = self._call(self.app_a)

        self.assertEqual('success', result['status'])
        log = QueryLog.objects.get()
        self.assertEqual('api', log.source)
        self.assertEqual(self.app_a, log.application)
        self.assertEqual(self.alice, log.user)
        self.assertGreaterEqual(log.duration_ms, 0)
        self.assertEqual(1, log.num_results)

    def test_no_log_for_unrelated_app(self):
        QueryLoggingRule.objects.create(
            application=self.app_a, enabled_until=now() + timedelta(hours=1),
        )

        self._call(self.app_b)

        self.assertEqual(0, QueryLog.objects.count())

    def test_no_log_on_error(self):
        QueryLoggingRule.objects.create(
            application=self.app_a, enabled_until=now() + timedelta(hours=1),
        )

        with self.assertRaises(ObjectDoesNotExist):
            dataset_query.__wrapped__(None, self.app_a, {
                'filters': {'no_such_attribute': 'test0'},
            })

        self.assertEqual(0, QueryLog.objects.count())


class ServershellQueryLoggingTest(TransactionTestCase):
    fixtures = ['test_dataset.json']

    def setUp(self):
        self.user = User.objects.create_user('alice', password='alice')
        self.client.force_login(self.user)

    def test_logs_when_user_rule_active(self):
        QueryLoggingRule.objects.create(
            user=self.user, enabled_until=now() + timedelta(hours=1),
        )

        response = self.client.get(
            '/servershell/results', {'term': 'hostname=test0'},
        )

        self.assertEqual(200, response.status_code)
        log = QueryLog.objects.get()
        self.assertEqual('servershell', log.source)
        self.assertIsNone(log.application)
        self.assertEqual(self.user, log.user)
        self.assertEqual(1, log.num_results)

    def test_no_log_without_rule(self):
        response = self.client.get(
            '/servershell/results', {'term': 'hostname=test0'},
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(0, QueryLog.objects.count())

    def test_no_log_on_parse_error(self):
        QueryLoggingRule.objects.create(
            user=self.user, enabled_until=now() + timedelta(hours=1),
        )

        response = self.client.get(
            '/servershell/results', {'term': "hostname=Regexp('[')"},
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(0, QueryLog.objects.count())
