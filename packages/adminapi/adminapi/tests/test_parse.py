import unittest

from adminapi.datatype import DatatypeError
from adminapi.filters import (
    BaseFilter,
    Regexp,
    Any,
    GreaterThan,
)
from adminapi.parse import parse_query, parse_function_string


def assert_filters_equal(test_case, result, expected):
    """Compare filter dictionaries by their repr, which includes structure and values."""
    test_case.assertEqual(sorted(result.keys()), sorted(expected.keys()))
    for key in expected:
        test_case.assertEqual(repr(result[key]), repr(expected[key]))


class TestParseQuery(unittest.TestCase):
    def test_simple_attribute(self):
        result = parse_query("hostname=web01")
        expected = {"hostname": BaseFilter("web01")}
        assert_filters_equal(self, result, expected)

    def test_whitespace_handling(self):
        result = parse_query("  hostname=test  ")
        expected = {"hostname": BaseFilter("test")}
        assert_filters_equal(self, result, expected)

    def test_multiple_attributes(self):
        result = parse_query("hostname=web01 state=online")
        expected = {
            "hostname": BaseFilter("web01"),
            "state": BaseFilter("online"),
        }
        assert_filters_equal(self, result, expected)

    def test_hostname_shorthand(self):
        result = parse_query("web01 state=online")
        expected = {
            "hostname": BaseFilter("web01"),
            "state": BaseFilter("online"),
        }
        assert_filters_equal(self, result, expected)

    def test_hostname_shorthand_with_regexp(self):
        # Hostname shortcuts automatically detect regex patterns
        result = parse_query("web.*")
        expected = {"hostname": Regexp("web.*")}
        assert_filters_equal(self, result, expected)

    def test_regexp_pattern_as_literal(self):
        # Regex patterns in attribute values are treated as literals
        # Use Regexp() function for actual regex filtering
        result = parse_query("hostname=web.*")
        expected = {"hostname": BaseFilter("web.*")}
        assert_filters_equal(self, result, expected)

    def test_explicit_regexp_function(self):
        # Use explicit Regexp() function for regex filtering
        result = parse_query("hostname=Regexp(web.*)")
        expected = {"hostname": Regexp("web.*")}
        assert_filters_equal(self, result, expected)

    def test_function_filter(self):
        result = parse_query("num_cores=GreaterThan(4)")
        expected = {"num_cores": GreaterThan(4)}
        assert_filters_equal(self, result, expected)

    def test_function_with_multiple_args(self):
        result = parse_query("hostname=Any(web01 web02)")
        expected = {"hostname": Any("web01", "web02")}
        assert_filters_equal(self, result, expected)

    def test_empty_query(self):
        result = parse_query("")
        self.assertEqual(result, {})

    def test_whitespace_only_query(self):
        result = parse_query("   ")
        self.assertEqual(result, {})

    def test_newline_in_query(self):
        result = parse_query("hostname=web01\nstate=online")
        expected = {
            "hostname": BaseFilter("web01"),
            "state": BaseFilter("online"),
        }
        assert_filters_equal(self, result, expected)

    def test_any_filter_with_duplicate_hostname(self):
        # Hostname shorthand triggers regex, but explicit attribute assignment doesn't
        result = parse_query("web.* hostname=db.*")
        expected = {"hostname": Any(BaseFilter("db.*"), Regexp("web.*"))}
        assert_filters_equal(self, result, expected)

    def test_invalid_function(self):
        with self.assertRaisesRegex(DatatypeError, r"Invalid function InvalidFunc"):
            parse_query("hostname=InvalidFunc(test)")

    def test_top_level_literal_error(self):
        with self.assertRaisesRegex(
            DatatypeError, r"Invalid term: Top level literals are not allowed"
        ):
            parse_query("hostname=test value")

    def test_top_level_function_as_hostname(self):
        # Function syntax without key is treated as hostname shorthand
        result = parse_query("GreaterThan(4)")
        expected = {"hostname": BaseFilter("GreaterThan(4)")}
        assert_filters_equal(self, result, expected)

    def test_garbled_hostname_error(self):
        with self.assertRaisesRegex(DatatypeError, r"Garbled hostname: db01"):
            parse_query("web01", hostname="db01")


class TestParseFunctionString(unittest.TestCase):
    def test_simple_key_value(self):
        result = parse_function_string("hostname=web01")
        self.assertEqual(result, [("key", "hostname"), ("literal", "web01")])

    def test_quoted_string(self):
        result = parse_function_string('hostname="web 01"')
        self.assertEqual(result, [("key", "hostname"), ("literal", "web 01")])

        result = parse_function_string("hostname='web 01'")
        self.assertEqual(result, [("key", "hostname"), ("literal", "web 01")])

        result = parse_function_string('hostname="web\\"01"')
        self.assertEqual(result[1], ("literal", 'web\\"01'))

    def test_function_call(self):
        result = parse_function_string("num_cores=GreaterThan(4)")
        expected = [
            ("key", "num_cores"),
            ("func", "GreaterThan"),
            ("literal", 4),
            ("endfunc", ""),
        ]
        self.assertEqual(result, expected)

    def test_nested_function(self):
        result = parse_function_string("attr=Func1(Func2(value))")
        self.assertEqual(result[0], ("key", "attr"))
        self.assertEqual(result[1], ("func", "Func1"))
        self.assertEqual(result[2], ("func", "Func2"))

    def test_multiple_values(self):
        result = parse_function_string("host1 host2 host3")
        expected = [
            ("literal", "host1"),
            ("literal", "host2"),
            ("literal", "host3"),
        ]
        self.assertEqual(result, expected)

    def test_datatype_conversion(self):
        result = parse_function_string("count=42")
        self.assertEqual(result, [("key", "count"), ("literal", 42)])

    def test_unterminated_string(self):
        with self.assertRaisesRegex(DatatypeError, r"Unterminated string"):
            parse_function_string('hostname="web01', strict=True)

    def test_invalid_escape(self):
        with self.assertRaisesRegex(DatatypeError, r"Invalid escape"):
            parse_function_string('hostname="web\\01"', strict=True)

    def test_empty_string(self):
        result = parse_function_string("")
        self.assertEqual(result, [])

    def test_whitespace_only(self):
        result = parse_function_string("   ")
        self.assertEqual(result, [])

    def test_parentheses_handling(self):
        result = parse_function_string("func(a b)")
        expected = [
            ("func", "func"),
            ("literal", "a"),
            ("literal", "b"),
            ("endfunc", ""),
        ]
        self.assertEqual(result, expected)
