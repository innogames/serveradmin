from django.test import SimpleTestCase

from adminapi.filters import Regexp
from serveradmin.serverdb.models import _apply_aliases


class ApplyAliasesTestCase(SimpleTestCase):
    mapping = {'old_name': 'new_name', 'old_code': 'short_code'}

    def test_none(self):
        self.assertIsNone(_apply_aliases(self.mapping, None))

    def test_string(self):
        self.assertEqual(_apply_aliases(self.mapping, 'old_name'), 'new_name')
        self.assertEqual(_apply_aliases(self.mapping, 'hostname'), 'hostname')

    def test_flat_restrict(self):
        self.assertEqual(
            _apply_aliases(self.mapping, ['hostname', 'old_name']),
            ['hostname', 'new_name'],
        )

    def test_restrict_with_joins(self):
        restrict = [{'old_name': ['old_code', 'object_id']}, 'hostname']
        self.assertEqual(
            _apply_aliases(self.mapping, restrict),
            [{'new_name': ['short_code', 'object_id']}, 'hostname'],
        )

    def test_restrict_with_nested_joins(self):
        restrict = [{'project': [{'old_name': ['old_code']}, 'hostname']}]
        self.assertEqual(
            _apply_aliases(self.mapping, restrict),
            [{'project': [{'new_name': ['short_code']}, 'hostname']}],
        )

    def test_filters_keep_filter_objects(self):
        regexp = Regexp('^foo')
        # A plain string value is a filter value, not an attribute name,
        # so it must not be rewritten even if it matches an alias.
        filters = {'old_name': regexp, 'hostname': 'old_code'}
        result = _apply_aliases(self.mapping, filters)
        self.assertEqual(set(result), {'new_name', 'hostname'})
        self.assertIs(result['new_name'], regexp)
        self.assertEqual(result['hostname'], 'old_code')

    def test_unsupported_type(self):
        with self.assertRaises(TypeError):
            _apply_aliases(self.mapping, 42)
