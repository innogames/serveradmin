"""Serveradmin - Filters on inherited attributes

Copyright (c) 2026 InnoGames GmbH
"""

from django.contrib.auth.models import User
from django.test import TransactionTestCase

from adminapi.filters import Not
from serveradmin.dataset import Query
from serveradmin.serverdb.models import ServertypeAttribute


class InheritedFilterTest(TransactionTestCase):
    """Filter on an attribute that some servertypes inherit

    The fixture has vm-1 pointing at hv-1 through the "hypervisor" relation
    attribute, with "vms" as its reverse, and neither servertype carrying
    "os".  Each test wires "os" onto one of them directly and onto the other
    through a relation path, then filters on it without narrowing the
    servertype, so the SQL generator has to render both the direct and the
    inherited path (see sql_generator._inherited_server_ids_sql).  The
    supernet path is covered in test_ip_addr_type.
    """

    fixtures = ['auth_user.json', 'test_dataset.json']

    def _set_os(self, hostname, value):
        query = Query({'hostname': hostname}, ['os'])
        query.update(os=value)
        query.commit(user=User.objects.first())

    def _hostnames(self, os_filter):
        return {s['hostname'] for s in Query({'os': os_filter}, ['hostname'])}

    def test_inherited_via_relation(self):
        # hypervisor carries "os", vm inherits it from its hypervisor.
        ServertypeAttribute.objects.create(
            servertype_id='hypervisor', attribute_id='os',
        )
        ServertypeAttribute.objects.create(
            servertype_id='vm', attribute_id='os',
            related_via_attribute_id='hypervisor',
        )
        self._set_os('hv-1', 'buster')

        self.assertEqual(self._hostnames('buster'), {'hv-1', 'vm-1'})

        # The inheriting server must drop out under negation too: the
        # subquery selects a NOT NULL column, so NOT IN keeps set semantics.
        excluded = self._hostnames(Not('buster'))
        self.assertNotIn('hv-1', excluded)
        self.assertNotIn('vm-1', excluded)
        self.assertIn('test0', excluded)

    def test_inherited_via_reverse(self):
        # vm carries "os", hypervisor inherits it from its vms.
        ServertypeAttribute.objects.create(
            servertype_id='vm', attribute_id='os',
        )
        ServertypeAttribute.objects.create(
            servertype_id='hypervisor', attribute_id='os',
            related_via_attribute_id='vms',
        )
        self._set_os('vm-1', 'buster')

        self.assertEqual(self._hostnames('buster'), {'vm-1', 'hv-1'})
