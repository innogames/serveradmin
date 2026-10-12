from django.contrib.auth.models import User
from django.test import SimpleTestCase, TransactionTestCase

from adminapi.dataset import DatasetObject
from adminapi.filters import Regexp
from serveradmin.api.views import dataset_query
from serveradmin.apps.models import Application
from serveradmin.serverdb.models import (
    Attribute,
    AttributeRedirect,
    _apply_aliases,
    _restore_aliases,
)


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


class RestoreAliasesTestCase(SimpleTestCase):
    mapping = {'operating_system': 'os', 'hv': 'hypervisor', 'name': 'hostname'}

    def test_flat_alias_is_renamed(self):
        results = [{'hostname': 'test0', 'os': 'wheezy'}]
        _restore_aliases(self.mapping, ['hostname', 'operating_system'], results)
        self.assertEqual(results, [{'hostname': 'test0', 'operating_system': 'wheezy'}])

    def test_real_name_is_untouched(self):
        results = [{'hostname': 'test0', 'os': 'wheezy'}]
        _restore_aliases(self.mapping, ['hostname', 'os'], results)
        self.assertEqual(results, [{'hostname': 'test0', 'os': 'wheezy'}])

    def test_alias_and_real_name_both_requested(self):
        results = [{'os': 'wheezy'}]
        _restore_aliases(self.mapping, ['os', 'operating_system'], results)
        self.assertEqual(results, [{'os': 'wheezy', 'operating_system': 'wheezy'}])

    def test_missing_attribute_is_not_added(self):
        results = [{'hostname': 'test0'}]
        _restore_aliases(self.mapping, ['hostname', 'operating_system'], results)
        self.assertEqual(results, [{'hostname': 'test0'}])

    def test_join_single_relation(self):
        results = [{'hostname': 'vm-1', 'hypervisor': {'hostname': 'hv-1', 'os': 'wheezy'}}]
        _restore_aliases(self.mapping, ['hostname', {'hv': ['name', 'operating_system']}], results)
        self.assertEqual(results, [
            {'hostname': 'vm-1', 'hv': {'name': 'hv-1', 'operating_system': 'wheezy'}},
        ])

    def test_join_with_none_value(self):
        results = [{'hostname': 'vm-1', 'hypervisor': None}]
        _restore_aliases(self.mapping, [{'hv': ['name']}], results)
        self.assertEqual(results, [{'hostname': 'vm-1', 'hv': None}])

    def test_join_multi_relation(self):
        vm1 = DatasetObject({'hostname': 'vm-1', 'os': 'wheezy'}, 7)
        vm2 = DatasetObject({'hostname': 'vm-2', 'os': 'squeeze'}, 8)
        results = [DatasetObject({'hostname': 'hv-1', 'vms': [vm1, vm2]}, 6)]
        _restore_aliases(self.mapping, [{'vms': ['name', 'operating_system']}], results)

        self.assertEqual(set(results[0]), {'hostname', 'vms'})
        self.assertEqual(
            sorted(sorted(vm.items()) for vm in results[0]['vms']),
            [
                [('name', 'vm-1'), ('operating_system', 'wheezy')],
                [('name', 'vm-2'), ('operating_system', 'squeeze')],
            ],
        )

    def test_join_real_name_with_nested_alias(self):
        results = [{'hypervisor': {'os': 'wheezy'}}]
        _restore_aliases(self.mapping, [{'hypervisor': ['operating_system']}], results)
        self.assertEqual(results, [{'hypervisor': {'operating_system': 'wheezy'}}])

    def test_dataset_objects_stay_clean(self):
        nested = DatasetObject({'hostname': 'hv-1', 'os': 'wheezy'}, 6)
        obj = DatasetObject({'hostname': 'vm-1', 'os': 'squeeze', 'hypervisor': nested}, 7)
        _restore_aliases(
            self.mapping,
            ['operating_system', {'hv': ['operating_system']}],
            [obj],
        )
        self.assertEqual(
            obj, {'hostname': 'vm-1', 'operating_system': 'squeeze', 'hv': nested},
        )
        self.assertEqual(nested, {'hostname': 'hv-1', 'operating_system': 'wheezy'})
        self.assertFalse(obj.is_dirty())
        self.assertFalse(nested.is_dirty())


class DatasetQueryAliasTestCase(TransactionTestCase):
    fixtures = ['test_dataset.json']

    def setUp(self):
        super().setUp()
        user = User.objects.create_user('alice')
        self.app = Application.objects.create(name='app', owner=user, location='')
        AttributeRedirect.objects.create(
            alias='operating_system', target=Attribute.objects.get(pk='os'),
        )
        AttributeRedirect.objects.create(
            alias='hv', target=Attribute.objects.get(pk='hypervisor'),
        )

    def _query(self, filters, restrict):
        response = dataset_query.__wrapped__(
            None, self.app, {'filters': filters, 'restrict': restrict},
        )
        self.assertEqual(response['status'], 'success')
        return response['result']

    def test_restrict_alias_is_returned_as_alias(self):
        result = self._query({'hostname': 'test0'}, ['hostname', 'operating_system'])
        self.assertEqual(result, [{'hostname': 'test0', 'operating_system': 'wheezy'}])

    def test_restrict_alias_and_real_name(self):
        result = self._query({'hostname': 'test0'}, ['os', 'operating_system'])
        self.assertEqual(result, [{'os': 'wheezy', 'operating_system': 'wheezy'}])

    def test_restrict_join_alias(self):
        result = self._query({'hostname': 'vm-1'}, ['hostname', {'hv': ['hostname']}])
        self.assertEqual(result, [{'hostname': 'vm-1', 'hv': {'hostname': 'hv-1'}}])

    def test_filter_alias_resolves_objects(self):
        result = self._query({'operating_system': 'wheezy'}, ['hostname'])
        self.assertEqual(result, [{'hostname': 'test0'}])

    def test_no_restrict_returns_real_names(self):
        result = self._query({'hostname': 'test0'}, [])
        self.assertEqual(len(result), 1)
        self.assertIn('os', result[0])
        self.assertNotIn('operating_system', result[0])
