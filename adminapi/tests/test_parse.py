import unittest

from adminapi.parse import parse_query, build_query
from adminapi.filters import (
    BaseFilter, Regexp, Any, All, Not, Empty,
    GreaterThan, GreaterThanOrEquals, LessThan, LessThanOrEquals,
    Contains, StartsWith,
)


class TestBuildQuery(unittest.TestCase):
    """Tests for the build_query function."""

    def test_simple_filter(self):
        """Test building a query with a simple attribute filter."""
        query = 'servertype=vm'
        parsed = parse_query(query)
        rebuilt = build_query(parsed)
        self.assertEqual(rebuilt, 'servertype=vm')

    def test_multiple_attributes(self):
        """Test building a query with multiple attributes."""
        query = 'servertype=vm state=online'
        parsed = parse_query(query)
        rebuilt = build_query(parsed)
        # Order may vary due to dict iteration, check both attributes present
        self.assertIn('servertype=vm', rebuilt)
        self.assertIn('state=online', rebuilt)

    def test_regexp_filter_explicit(self):
        """Test building a query with explicit Regexp filter."""
        query = 'hostname=Regexp(web.*)'
        parsed = parse_query(query)
        rebuilt = build_query(parsed)
        self.assertEqual(rebuilt, 'hostname=Regexp(web.*)')

    def test_any_filter(self):
        """Test building a query with Any filter."""
        query = 'state=Any(online offline)'
        parsed = parse_query(query)
        rebuilt = build_query(parsed)
        self.assertEqual(rebuilt, 'state=Any(online offline)')

    def test_all_filter(self):
        """Test building a query with All filter."""
        query = 'tags=All(production web)'
        parsed = parse_query(query)
        rebuilt = build_query(parsed)
        self.assertEqual(rebuilt, 'tags=All(production web)')

    def test_not_filter(self):
        """Test building a query with Not filter."""
        query = 'state=Not(offline)'
        parsed = parse_query(query)
        rebuilt = build_query(parsed)
        self.assertEqual(rebuilt, 'state=Not(offline)')

    def test_empty_filter(self):
        """Test building a query with Empty filter."""
        query = 'comment=Empty()'
        parsed = parse_query(query)
        rebuilt = build_query(parsed)
        self.assertEqual(rebuilt, 'comment=Empty()')

    def test_numeric_value(self):
        """Test building a query with numeric value."""
        query = 'cpu_cores=4'
        parsed = parse_query(query)
        rebuilt = build_query(parsed)
        self.assertEqual(rebuilt, 'cpu_cores=4')

    def test_boolean_true(self):
        """Test building a query with boolean true value."""
        query = 'active=true'
        parsed = parse_query(query)
        rebuilt = build_query(parsed)
        self.assertEqual(rebuilt, 'active=true')

    def test_boolean_false(self):
        """Test building a query with boolean false value."""
        query = 'active=false'
        parsed = parse_query(query)
        rebuilt = build_query(parsed)
        self.assertEqual(rebuilt, 'active=false')

    def test_hostname_only_plain(self):
        """Test building a query with plain hostname."""
        query = 'webserver01'
        parsed = parse_query(query)
        rebuilt = build_query(parsed)
        self.assertEqual(rebuilt, 'hostname=webserver01')

    def test_hostname_only_with_regex(self):
        """Test building a query with hostname containing regex chars."""
        query = 'web.*'
        parsed = parse_query(query)
        rebuilt = build_query(parsed)
        self.assertEqual(rebuilt, 'hostname=Regexp(web.*)')

    def test_greater_than_filter(self):
        """Test building a query with GreaterThan filter."""
        query = 'cpu_cores=GreaterThan(4)'
        parsed = parse_query(query)
        rebuilt = build_query(parsed)
        self.assertEqual(rebuilt, 'cpu_cores=GreaterThan(4)')

    def test_less_than_filter(self):
        """Test building a query with LessThan filter."""
        query = 'memory=LessThan(8192)'
        parsed = parse_query(query)
        rebuilt = build_query(parsed)
        self.assertEqual(rebuilt, 'memory=LessThan(8192)')

    def test_nested_not_any(self):
        """Test building a query with nested Not(Any(...))."""
        query = 'state=Not(Any(offline maintenance))'
        parsed = parse_query(query)
        rebuilt = build_query(parsed)
        self.assertEqual(rebuilt, 'state=Not(Any(offline maintenance))')

    def test_nested_any_not(self):
        """Test building a query with nested Any containing Not."""
        query = 'state=Any(online Not(offline))'
        parsed = parse_query(query)
        rebuilt = build_query(parsed)
        self.assertEqual(rebuilt, 'state=Any(online Not(offline))')

    def test_empty_query(self):
        """Test building an empty query."""
        parsed = {}
        rebuilt = build_query(parsed)
        self.assertEqual(rebuilt, '')

    def test_contains_filter(self):
        """Test building a query with Contains filter."""
        query = 'hostname=Contains(web)'
        parsed = parse_query(query)
        rebuilt = build_query(parsed)
        self.assertEqual(rebuilt, 'hostname=Contains(web)')

    def test_startswith_filter(self):
        """Test building a query with StartsWith filter."""
        query = 'hostname=StartsWith(web)'
        parsed = parse_query(query)
        rebuilt = build_query(parsed)
        self.assertEqual(rebuilt, 'hostname=StartsWith(web)')


class TestBuildQueryRoundTrip(unittest.TestCase):
    """Tests to verify parse_query and build_query are inverses."""

    def assert_filters_equal(self, filter1, filter2):
        """Recursively compare two filter objects for equality."""
        self.assertEqual(type(filter1), type(filter2))

        if hasattr(filter1, 'values'):
            # Any/All filters have multiple values
            self.assertEqual(len(filter1.values), len(filter2.values))
            for v1, v2 in zip(filter1.values, filter2.values):
                self.assert_filters_equal(v1, v2)
        elif hasattr(filter1, 'value'):
            # Single value filters (BaseFilter, Not, Regexp, etc.)
            if isinstance(filter1.value, BaseFilter):
                self.assert_filters_equal(filter1.value, filter2.value)
            else:
                self.assertEqual(filter1.value, filter2.value)

    def assert_round_trip(self, query):
        """Assert that parsing and rebuilding produces equivalent result."""
        parsed = parse_query(query)
        rebuilt = build_query(parsed)
        reparsed = parse_query(rebuilt)

        # Compare keys
        self.assertEqual(set(parsed.keys()), set(reparsed.keys()))

        # Compare filter types and values recursively
        for key in parsed:
            self.assert_filters_equal(parsed[key], reparsed[key])

    def test_round_trip_simple(self):
        """Test round-trip for simple query."""
        self.assert_round_trip('servertype=vm')

    def test_round_trip_any(self):
        """Test round-trip for Any filter."""
        self.assert_round_trip('state=Any(online offline)')

    def test_round_trip_not(self):
        """Test round-trip for Not filter."""
        self.assert_round_trip('state=Not(offline)')

    def test_round_trip_nested(self):
        """Test round-trip for nested filters."""
        self.assert_round_trip('state=Not(Any(offline maintenance))')

    def test_round_trip_numeric(self):
        """Test round-trip for numeric value."""
        self.assert_round_trip('cpu_cores=4')

    def test_round_trip_boolean(self):
        """Test round-trip for boolean value."""
        self.assert_round_trip('active=true')


class TestBuildQueryDirectConstruction(unittest.TestCase):
    """Tests for build_query with directly constructed filter objects."""

    def test_direct_base_filter(self):
        """Test building query from directly constructed BaseFilter."""
        query_args = {'servertype': BaseFilter('vm')}
        rebuilt = build_query(query_args)
        self.assertEqual(rebuilt, 'servertype=vm')

    def test_direct_regexp(self):
        """Test building query from directly constructed Regexp."""
        query_args = {'hostname': Regexp('web.*')}
        rebuilt = build_query(query_args)
        self.assertEqual(rebuilt, 'hostname=Regexp(web.*)')

    def test_direct_any(self):
        """Test building query from directly constructed Any."""
        query_args = {'state': Any('online', 'offline')}
        rebuilt = build_query(query_args)
        self.assertEqual(rebuilt, 'state=Any(online offline)')

    def test_direct_not(self):
        """Test building query from directly constructed Not."""
        query_args = {'state': Not('offline')}
        rebuilt = build_query(query_args)
        self.assertEqual(rebuilt, 'state=Not(offline)')

    def test_direct_empty(self):
        """Test building query from directly constructed Empty."""
        query_args = {'comment': Empty()}
        rebuilt = build_query(query_args)
        self.assertEqual(rebuilt, 'comment=Empty()')

    def test_direct_nested(self):
        """Test building query from nested filter construction."""
        query_args = {'state': Not(Any('offline', 'maintenance'))}
        rebuilt = build_query(query_args)
        self.assertEqual(rebuilt, 'state=Not(Any(offline maintenance))')

    def test_direct_all(self):
        """Test building query from directly constructed All."""
        query_args = {'tags': All('production', 'web')}
        rebuilt = build_query(query_args)
        self.assertEqual(rebuilt, 'tags=All(production web)')


if __name__ == '__main__':
    unittest.main()
