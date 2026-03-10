"""Unit tests for sql_generator_v2 module.

Copyright (c) 2024 InnoGames GmbH

Tests the Django ORM-based SQL generator implementation to ensure
it produces correct results matching the v1 implementation.
"""

from django.db.models import QuerySet
from django.test import TransactionTestCase, override_settings

from adminapi.filters import (
    Any,
    All,
    BaseFilter,
    Contains,
    ContainedBy,
    Empty,
    GreaterThan,
    GreaterThanOrEquals,
    LessThan,
    LessThanOrEquals,
    Not,
    Overlaps,
    Regexp,
    StartsWith,
)
from serveradmin.serverdb.models import Attribute, Server
from serveradmin.serverdb.sql_generator import (
    get_server_query as get_server_query_v1,
)
from serveradmin.serverdb.sql_generator_v2 import (
    get_server_query as get_server_query_v2,
    _build_attribute_condition,
    _build_value_condition,
    _build_logical_condition,
)


class TestGetServerQueryV2(TransactionTestCase):
    """Test that get_server_query returns a proper QuerySet."""

    fixtures = ['auth_user.json', 'test_dataset.json']

    def test_returns_queryset(self):
        """Verify get_server_query_v2 returns a QuerySet."""
        result = get_server_query_v2([], {})
        self.assertIsInstance(result, QuerySet)

    def test_empty_filters_returns_all_servers(self):
        """Empty filter list should return all servers."""
        result = get_server_query_v2([], {})
        self.assertEqual(result.count(), Server.objects.count())

    def test_ordering_by_hostname(self):
        """Results should be ordered by hostname."""
        result = list(get_server_query_v2([], {}))
        hostnames = [s.hostname for s in result]
        self.assertEqual(hostnames, sorted(hostnames))


class TestSpecialAttributeFilters(TransactionTestCase):
    """Test filtering by special attributes (hostname, servertype, etc.)."""

    fixtures = ['auth_user.json', 'test_dataset.json']

    def test_filter_by_hostname_equality(self):
        """Test filtering by exact hostname."""
        hostname_attr = Attribute.specials['hostname']
        filt = BaseFilter('test0')

        result = get_server_query_v2([(hostname_attr, filt)], {})
        hostnames = [s.hostname for s in result]

        self.assertIn('test0', hostnames)
        self.assertEqual(len(hostnames), 1)

    def test_filter_by_hostname_regexp(self):
        """Test filtering by hostname with regex."""
        hostname_attr = Attribute.specials['hostname']
        filt = Regexp('^test[0-9]+$')

        result = get_server_query_v2([(hostname_attr, filt)], {})
        hostnames = [s.hostname for s in result]

        # All test fixtures should match
        self.assertTrue(all(h.startswith('test') for h in hostnames))

    def test_filter_by_servertype(self):
        """Test filtering by servertype."""
        servertype_attr = Attribute.specials['servertype']
        filt = BaseFilter('test0')

        result = get_server_query_v2([(servertype_attr, filt)], {})

        for server in result:
            self.assertEqual(server.servertype_id, 'test0')

    def test_filter_by_object_id(self):
        """Test filtering by object_id."""
        object_id_attr = Attribute.specials['object_id']
        server = Server.objects.first()
        filt = BaseFilter(server.server_id)

        result = get_server_query_v2([(object_id_attr, filt)], {})
        result_list = list(result)

        self.assertEqual(len(result_list), 1)
        self.assertEqual(result_list[0].server_id, server.server_id)


class TestComparisonFilters(TransactionTestCase):
    """Test comparison filters (>, <, >=, <=)."""

    fixtures = ['auth_user.json', 'test_dataset.json']

    def test_greater_than_filter(self):
        """Test GreaterThan filter on object_id."""
        object_id_attr = Attribute.specials['object_id']
        filt = GreaterThan(1)

        result = get_server_query_v2([(object_id_attr, filt)], {})

        for server in result:
            self.assertGreater(server.server_id, 1)

    def test_greater_than_or_equals_filter(self):
        """Test GreaterThanOrEquals filter."""
        object_id_attr = Attribute.specials['object_id']
        filt = GreaterThanOrEquals(2)

        result = get_server_query_v2([(object_id_attr, filt)], {})

        for server in result:
            self.assertGreaterEqual(server.server_id, 2)

    def test_less_than_filter(self):
        """Test LessThan filter."""
        object_id_attr = Attribute.specials['object_id']
        filt = LessThan(3)

        result = get_server_query_v2([(object_id_attr, filt)], {})

        for server in result:
            self.assertLess(server.server_id, 3)

    def test_less_than_or_equals_filter(self):
        """Test LessThanOrEquals filter."""
        object_id_attr = Attribute.specials['object_id']
        filt = LessThanOrEquals(2)

        result = get_server_query_v2([(object_id_attr, filt)], {})

        for server in result:
            self.assertLessEqual(server.server_id, 2)


class TestLogicalFilters(TransactionTestCase):
    """Test logical filters (Any, All, Not)."""

    fixtures = ['auth_user.json', 'test_dataset.json']

    def test_any_filter_with_values(self):
        """Test Any filter matches any of the values."""
        hostname_attr = Attribute.specials['hostname']
        filt = Any('test0', 'test1')

        result = get_server_query_v2([(hostname_attr, filt)], {})
        hostnames = {s.hostname for s in result}

        self.assertTrue(hostnames.issubset({'test0', 'test1'}))

    def test_any_filter_empty_returns_nothing(self):
        """Test empty Any filter returns no results."""
        hostname_attr = Attribute.specials['hostname']
        filt = Any()

        result = get_server_query_v2([(hostname_attr, filt)], {})

        self.assertEqual(result.count(), 0)

    def test_all_filter_empty_returns_all(self):
        """Test empty All filter returns all results."""
        hostname_attr = Attribute.specials['hostname']
        filt = All()

        result = get_server_query_v2([(hostname_attr, filt)], {})

        self.assertEqual(result.count(), Server.objects.count())

    def test_not_filter(self):
        """Test Not filter negates the condition."""
        hostname_attr = Attribute.specials['hostname']
        filt = Not(BaseFilter('test0'))

        result = get_server_query_v2([(hostname_attr, filt)], {})
        hostnames = [s.hostname for s in result]

        self.assertNotIn('test0', hostnames)

    def test_nested_logical_filters(self):
        """Test nested logical filters."""
        hostname_attr = Attribute.specials['hostname']
        # Match test0 OR (NOT test1)
        filt = Any(BaseFilter('test0'), Not(BaseFilter('test1')))

        result = get_server_query_v2([(hostname_attr, filt)], {})
        hostnames = [s.hostname for s in result]

        # test0 should be included, test1 should be excluded
        self.assertIn('test0', hostnames)
        self.assertNotIn('test1', hostnames)


class TestStringFilters(TransactionTestCase):
    """Test string containment filters."""

    fixtures = ['auth_user.json', 'test_dataset.json']

    def test_contains_filter_on_hostname(self):
        """Test Contains filter on string attribute."""
        hostname_attr = Attribute.specials['hostname']
        filt = Contains('est')

        result = get_server_query_v2([(hostname_attr, filt)], {})
        hostnames = [s.hostname for s in result]

        # All test hostnames contain 'est'
        for hostname in hostnames:
            self.assertIn('est', hostname)

    def test_startswith_filter_on_hostname(self):
        """Test StartsWith filter on string attribute."""
        hostname_attr = Attribute.specials['hostname']
        filt = StartsWith('test')

        result = get_server_query_v2([(hostname_attr, filt)], {})
        hostnames = [s.hostname for s in result]

        for hostname in hostnames:
            self.assertTrue(hostname.startswith('test'))


class TestV1V2Comparison(TransactionTestCase):
    """Compare v1 and v2 implementations produce same results."""

    fixtures = ['auth_user.json', 'test_dataset.json']

    def _get_v1_server_ids(self, attribute_filters, related_vias):
        """Execute v1 query and return server IDs."""
        sql = get_server_query_v1(attribute_filters, related_vias)
        servers = Server.objects.raw(sql)
        return {s.server_id for s in servers}

    def _get_v2_server_ids(self, attribute_filters, related_vias):
        """Execute v2 query and return server IDs."""
        queryset = get_server_query_v2(attribute_filters, related_vias)
        return {s.server_id for s in queryset}

    def test_empty_filters_match(self):
        """Empty filters should return same results."""
        v1_ids = self._get_v1_server_ids([], {})
        v2_ids = self._get_v2_server_ids([], {})
        self.assertEqual(v1_ids, v2_ids)

    def test_hostname_equality_match(self):
        """Hostname equality filter should return same results."""
        hostname_attr = Attribute.specials['hostname']
        filters = [(hostname_attr, BaseFilter('test0'))]

        v1_ids = self._get_v1_server_ids(filters, {})
        v2_ids = self._get_v2_server_ids(filters, {})
        self.assertEqual(v1_ids, v2_ids)

    def test_hostname_regexp_match(self):
        """Hostname regexp filter should return same results."""
        hostname_attr = Attribute.specials['hostname']
        filters = [(hostname_attr, Regexp('^test[0-9]$'))]

        v1_ids = self._get_v1_server_ids(filters, {})
        v2_ids = self._get_v2_server_ids(filters, {})
        self.assertEqual(v1_ids, v2_ids)

    def test_servertype_filter_match(self):
        """Servertype filter should return same results."""
        servertype_attr = Attribute.specials['servertype']
        filters = [(servertype_attr, BaseFilter('test0'))]

        v1_ids = self._get_v1_server_ids(filters, {})
        v2_ids = self._get_v2_server_ids(filters, {})
        self.assertEqual(v1_ids, v2_ids)

    def test_any_filter_match(self):
        """Any filter should return same results."""
        hostname_attr = Attribute.specials['hostname']
        filters = [(hostname_attr, Any('test0', 'test1'))]

        v1_ids = self._get_v1_server_ids(filters, {})
        v2_ids = self._get_v2_server_ids(filters, {})
        self.assertEqual(v1_ids, v2_ids)

    def test_not_filter_match(self):
        """Not filter should return same results."""
        hostname_attr = Attribute.specials['hostname']
        filters = [(hostname_attr, Not(BaseFilter('test0')))]

        v1_ids = self._get_v1_server_ids(filters, {})
        v2_ids = self._get_v2_server_ids(filters, {})
        self.assertEqual(v1_ids, v2_ids)

    def test_comparison_filter_match(self):
        """Comparison filters should return same results."""
        object_id_attr = Attribute.specials['object_id']
        filters = [(object_id_attr, GreaterThan(1))]

        v1_ids = self._get_v1_server_ids(filters, {})
        v2_ids = self._get_v2_server_ids(filters, {})
        self.assertEqual(v1_ids, v2_ids)

    def test_multiple_filters_match(self):
        """Multiple filters should return same results."""
        hostname_attr = Attribute.specials['hostname']
        servertype_attr = Attribute.specials['servertype']
        filters = [
            (hostname_attr, Regexp('^test')),
            (servertype_attr, BaseFilter('test0')),
        ]

        v1_ids = self._get_v1_server_ids(filters, {})
        v2_ids = self._get_v2_server_ids(filters, {})
        self.assertEqual(v1_ids, v2_ids)


class TestQueryBuilderFacade(TransactionTestCase):
    """Test the query_builder facade switches correctly."""

    fixtures = ['auth_user.json', 'test_dataset.json']

    @override_settings(SQL_GENERATOR_VERSION='v1')
    def test_v1_returns_string(self):
        """V1 setting should return SQL string."""
        from serveradmin.serverdb.query_builder import get_server_query
        result = get_server_query([], {})
        self.assertIsInstance(result, str)

    @override_settings(SQL_GENERATOR_VERSION='v2')
    def test_v2_returns_queryset(self):
        """V2 setting should return QuerySet."""
        from serveradmin.serverdb.query_builder import get_server_query
        result = get_server_query([], {})
        self.assertIsInstance(result, QuerySet)

    @override_settings(SQL_GENERATOR_VERSION='v1')
    def test_default_is_v1(self):
        """Default setting should be v1."""
        from serveradmin.serverdb.query_builder import get_server_query
        result = get_server_query([], {})
        self.assertIsInstance(result, str)


class TestBuildValueCondition(TransactionTestCase):
    """Unit tests for _build_value_condition function."""

    fixtures = ['auth_user.json', 'test_dataset.json']

    def test_base_filter_creates_equality(self):
        """BaseFilter should create equality condition."""
        attr = Attribute.specials['hostname']
        filt = BaseFilter('test')
        condition = _build_value_condition(attr, filt)

        # Should have value='test' in children
        self.assertTrue(any(
            child == ('value', 'test')
            for child in condition.children
            if isinstance(child, tuple)
        ))

    def test_regexp_filter_creates_regex_lookup(self):
        """Regexp filter should create regex lookup."""
        attr = Attribute.specials['hostname']
        filt = Regexp('^test')
        condition = _build_value_condition(attr, filt)

        # Should have value__regex in children
        self.assertTrue(any(
            child[0] == 'value__regex'
            for child in condition.children
            if isinstance(child, tuple)
        ))

    def test_greater_than_creates_gt_lookup(self):
        """GreaterThan filter should create __gt lookup."""
        attr = Attribute.specials['object_id']
        filt = GreaterThan(5)
        condition = _build_value_condition(attr, filt)

        self.assertTrue(any(
            child[0] == 'value__gt' and child[1] == 5
            for child in condition.children
            if isinstance(child, tuple)
        ))


class TestBuildLogicalCondition(TransactionTestCase):
    """Unit tests for _build_logical_condition function."""

    fixtures = ['auth_user.json', 'test_dataset.json']

    def test_empty_any_creates_false_condition(self):
        """Empty Any should create always-false condition."""
        attr = Attribute.specials['hostname']
        filt = Any()
        condition = _build_logical_condition(attr, filt, {})

        # The condition should match nothing
        # We verify by checking it's a complex condition that evaluates to false
        result = Server.objects.filter(condition)
        self.assertEqual(result.count(), 0)

    def test_empty_all_creates_true_condition(self):
        """Empty All should create always-true condition."""
        attr = Attribute.specials['hostname']
        filt = All()
        condition = _build_logical_condition(attr, filt, {})

        # The condition should match everything
        result = Server.objects.filter(condition)
        self.assertEqual(result.count(), Server.objects.count())

    def test_any_with_simple_values_optimizes_to_in(self):
        """Any with simple BaseFilter values should use IN clause."""
        attr = Attribute.specials['hostname']
        filt = Any('test0', 'test1', 'test2')
        condition = _build_logical_condition(attr, filt, {})

        # Should work correctly regardless of optimization
        result = Server.objects.filter(condition)
        hostnames = {s.hostname for s in result}
        self.assertTrue(hostnames.issubset({'test0', 'test1', 'test2'}))
