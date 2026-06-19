"""Serveradmin - Tests for overridable related-via attributes

Copyright (c) 2026 InnoGames GmbH

These tests build a small schema modelling physical location:

    rack  <--(rack)--  bladecenter  <--(bladecenter)--  hypervisor  <--(hv)--  vm

The ``rack`` attribute is configured as related via ``bladecenter`` on the
hypervisor servertype and related via ``hv`` on the vm servertype.  Overriding
is configured per servertype on the ``ServertypeAttribute``: the hypervisor's
``rack`` is marked ``override_related_via`` so it can also be set directly
(e.g. on a standalone hypervisor that is not installed in a bladecenter), while
the vm's ``rack`` is not overridable and thus stays read-only.
"""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TransactionTestCase

from serveradmin.dataset import Query
from serveradmin.serverdb import query_committer
from serveradmin.serverdb.models import (
    Attribute,
    Servertype,
    ServertypeAttribute,
)


class ValuePresentAfterTestCase(TransactionTestCase):
    """Unit tests for _value_present_after, which decides whether an attribute
    holds a value once a pending change is applied."""

    def _present(self, change, baseline=False):
        return query_committer._value_present_after(
            'attr', {'attr': change}, baseline,
        )

    def test_absent_attribute_uses_baseline(self):
        self.assertTrue(query_committer._value_present_after('attr', {}, True))
        self.assertFalse(query_committer._value_present_after('attr', {}, False))

    def test_delete_is_absent(self):
        self.assertFalse(self._present({'action': 'delete'}, baseline=True))

    def test_update_to_value_is_present(self):
        self.assertTrue(self._present({'action': 'update', 'new': 'rack1'}))

    def test_update_to_empty_is_absent(self):
        self.assertFalse(self._present({'action': 'update', 'new': None}))
        self.assertFalse(self._present({'action': 'update', 'new': ''}))

    def test_boolean_false_is_absent(self):
        # ServerBooleanAttribute stores False as a missing row.
        self.assertFalse(self._present({'action': 'update', 'new': False}))

    def test_number_zero_is_present(self):
        self.assertTrue(self._present({'action': 'update', 'new': 0}))


class OverrideRelatedViaTestCase(TransactionTestCase):
    fixtures = ['auth_user.json']

    def setUp(self):
        super().setUp()
        self.user = User.objects.first()

        for servertype_id in ('rack', 'bladecenter', 'hypervisor', 'vm'):
            Servertype.objects.create(
                servertype_id=servertype_id,
                description=servertype_id,
                ip_addr_type='null',
            )

        regexp = r'\A.*\Z'
        Attribute.objects.create(
            attribute_id='rack', type='relation', regexp=regexp,
        )
        Attribute.objects.create(
            attribute_id='bladecenter', type='relation', regexp=regexp,
        )
        Attribute.objects.create(
            attribute_id='hv', type='relation', regexp=regexp,
        )

        # bladecenter: rack stored directly.
        ServertypeAttribute.objects.create(
            servertype_id='bladecenter', attribute_id='rack',
        )
        # hypervisor: bladecenter stored directly, rack related via bladecenter
        # and overridable so it can also be set directly on a standalone host.
        ServertypeAttribute.objects.create(
            servertype_id='hypervisor', attribute_id='bladecenter',
        )
        ServertypeAttribute.objects.create(
            servertype_id='hypervisor', attribute_id='rack',
            related_via_attribute_id='bladecenter',
            override_related_via=True,
        )
        # vm: hv stored directly, rack related via hv.  Not overridable here,
        # so a vm's rack is always inherited and can never be set directly.
        ServertypeAttribute.objects.create(
            servertype_id='vm', attribute_id='hv',
        )
        ServertypeAttribute.objects.create(
            servertype_id='vm', attribute_id='rack',
            related_via_attribute_id='hv',
        )

    def _create(self, servertype, hostname, **attributes):
        obj = Query().new_object(servertype)
        obj['hostname'] = hostname
        for key, value in attributes.items():
            obj[key] = value
        obj.commit(user=self.user)
        return obj

    def _rack_of(self, hostname):
        return Query({'hostname': hostname}, ['rack']).get()['rack']

    # -- Materialization ---------------------------------------------------

    def test_standalone_hypervisor_direct_rack(self):
        self._create('rack', 'rack2')
        self._create('hypervisor', 'hv-standalone', rack='rack2')

        self.assertEqual(self._rack_of('hv-standalone'), 'rack2')

    def test_blade_hypervisor_inherits_rack_single_hop(self):
        self._create('rack', 'rack1')
        self._create('bladecenter', 'bc1', rack='rack1')
        self._create('hypervisor', 'hv-blade', bladecenter='bc1')

        self.assertEqual(self._rack_of('hv-blade'), 'rack1')

    def test_vm_inherits_rack_two_hops_via_bladecenter(self):
        self._create('rack', 'rack1')
        self._create('bladecenter', 'bc1', rack='rack1')
        self._create('hypervisor', 'hv-blade', bladecenter='bc1')
        self._create('vm', 'vm-on-blade', hv='hv-blade')

        # rack <- bladecenter <- hypervisor <- vm (two related-via hops)
        self.assertEqual(self._rack_of('vm-on-blade'), 'rack1')

    def test_vm_inherits_rack_from_standalone_hypervisor(self):
        self._create('rack', 'rack2')
        self._create('hypervisor', 'hv-standalone', rack='rack2')
        self._create('vm', 'vm-on-standalone', hv='hv-standalone')

        self.assertEqual(self._rack_of('vm-on-standalone'), 'rack2')

    # -- Commit consistency ------------------------------------------------

    def test_cannot_set_direct_rack_when_bladecenter_present(self):
        self._create('rack', 'rack1')
        self._create('rack', 'rack2')
        self._create('bladecenter', 'bc1', rack='rack1')
        self._create('hypervisor', 'hv-blade', bladecenter='bc1')

        query = Query({'hostname': 'hv-blade'}, ['rack'])
        query.update(rack='rack2')
        with self.assertRaises(ValidationError) as error:
            query.commit(user=self.user)
        self.assertIn('rack', str(error.exception))

    def test_cannot_set_bladecenter_when_direct_rack_present(self):
        self._create('rack', 'rack2')
        self._create('rack', 'rack1')
        self._create('bladecenter', 'bc1', rack='rack1')
        self._create('hypervisor', 'hv-standalone', rack='rack2')

        query = Query({'hostname': 'hv-standalone'}, ['bladecenter'])
        query.update(bladecenter='bc1')
        with self.assertRaises(ValidationError) as error:
            query.commit(user=self.user)
        # The violation is reported against the directly-set override attribute.
        self.assertIn('rack', str(error.exception))

    def test_cannot_create_with_both_direct_rack_and_bladecenter(self):
        self._create('rack', 'rack1')
        self._create('rack', 'rack2')
        self._create('bladecenter', 'bc1', rack='rack1')

        with self.assertRaises(ValidationError) as error:
            self._create(
                'hypervisor', 'hv-both', bladecenter='bc1', rack='rack2',
            )
        self.assertIn('rack', str(error.exception))

    def test_can_set_direct_rack_when_no_bladecenter(self):
        self._create('rack', 'rack2')
        self._create('hypervisor', 'hv-standalone')

        query = Query({'hostname': 'hv-standalone'}, ['rack'])
        query.update(rack='rack2')
        query.commit(user=self.user)

        self.assertEqual(self._rack_of('hv-standalone'), 'rack2')

    def test_cannot_set_direct_rack_on_vm_without_override(self):
        # ``rack`` is related via ``hv`` on the vm servertype but, unlike on the
        # hypervisor, it is not overridable there.  Setting it directly must be
        # rejected even though the very same attribute is overridable elsewhere.
        # The vm inherits rack1 from its hypervisor; we try to override it with
        # rack2 so the commit actually stages a change rather than a no-op.
        self._create('rack', 'rack1')
        self._create('rack', 'rack2')
        self._create('hypervisor', 'hv-standalone', rack='rack1')
        self._create('vm', 'vm1', hv='hv-standalone')

        query = Query({'hostname': 'vm1'}, ['rack'])
        query.update(rack='rack2')
        with self.assertRaises(ValidationError) as error:
            query.commit(user=self.user)
        self.assertIn('rack', str(error.exception))

    # -- Model validation --------------------------------------------------

    def test_clean_rejects_override_without_related_via(self):
        # override_related_via only makes sense on a related-via row; the
        # bladecenter stores rack directly, so marking it overridable is a
        # misconfiguration that clean() must reject.
        sa = ServertypeAttribute(
            servertype_id='bladecenter', attribute_id='rack',
            override_related_via=True,
        )
        with self.assertRaises(ValidationError):
            sa.clean()

    def test_clean_allows_override_with_related_via(self):
        # The hypervisor's rack is related via bladecenter, so it may be
        # marked overridable.
        sa = ServertypeAttribute(
            servertype_id='hypervisor', attribute_id='rack',
            related_via_attribute_id='bladecenter',
            override_related_via=True,
        )
        sa.clean()

    def test_creating_vm_with_direct_rack_ignores_it_without_override(self):
        # On the create path a non-overridable related-via value is dropped
        # rather than stored, so the vm's rack stays inherited from its
        # hypervisor regardless of the directly supplied value.
        self._create('rack', 'rack1')
        self._create('rack', 'rack2')
        self._create('hypervisor', 'hv-standalone', rack='rack1')

        self._create('vm', 'vm1', hv='hv-standalone', rack='rack2')

        self.assertEqual(self._rack_of('vm1'), 'rack1')
