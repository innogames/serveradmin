import unittest
from argparse import ArgumentParser
from typing import Text, NoReturn

from adminapi.cli import parse_args, _resolve_value
from adminapi.dataset import DatasetObject, MultiAttr


# ArgumentParser exists on error, we cannot capture this so we override it
class ArgumentParserMock(ArgumentParser):
    def error(self, message: Text) -> NoReturn:
        raise Exception(message)


class TestCommandlineInterface(unittest.TestCase):
    def test_no_argument(self, *args):
        with self.assertRaises(SystemExit) as e:
            parse_args([])

    def test_unknown_argument(self, *args):
        with self.assertRaises(SystemExit) as e:
            parse_args(['project=adminapi', '--attr', 'state', 'spaceship'])

    def test_one_argument(self, *args):
        args = parse_args(['project=adminapi', '--one'])
        self.assertTrue(args.one)

        args = parse_args(['project=adminapi', '-1'])
        self.assertTrue(args.one)

    def test_attr_argument(self, *args):
        args = parse_args(['project=adminapi', '--attr', 'hostname'])
        self.assertEqual(args.attr, ['hostname'])

        args = parse_args(['project=adminapi', '-a', 'hostname'])
        self.assertEqual(args.attr, ['hostname'])

        args = parse_args(['project=adminapi', '--attr', 'hostname', '-a', 'state'])
        self.assertEqual(args.attr, ['hostname', 'state'])

    def test_order_argument(self, *args):
        args = parse_args(['project=adminapi', '--order', 'hostname'])
        self.assertEqual(args.order, ['hostname'])

        args = parse_args(['project=adminapi', '-o', 'hostname'])
        self.assertEqual(args.order, ['hostname'])

        args = parse_args(['project=adminapi', '--order', 'hostname', '-o', 'state'])
        self.assertEqual(args.order, ['hostname', 'state'])

    def test_reset_argument(self, *args):
        args = parse_args(['project=adminapi', '--reset', 'responsible_admins'])
        self.assertEqual(args.reset, ['responsible_admins'])

        args = parse_args(['project=adminapi', '-r', 'responsible_admins'])
        self.assertEqual(args.reset, ['responsible_admins'])

        args = parse_args(['project=adminapi', '--reset', 'responsible_admins', '-r', 'service_groups'])
        self.assertEqual(args.reset, ['responsible_admins', 'service_groups'])

    def test_update_argument(self, *args):
        args = parse_args(['project=adminapi', '--update', 'hostname=SomeNewHostname'])
        self.assertEqual(args.update, [('hostname', 'SomeNewHostname')])

        args = parse_args(['project=adminapi', '-u', 'hostname=SomeNewHostname'])
        self.assertEqual(args.update, [('hostname', 'SomeNewHostname')])

        args = parse_args(['project=adminapi', '--update', 'hostname=SomeNewHostname', '-u', 'state=maintenance'])
        self.assertEqual(args.update, [('hostname', 'SomeNewHostname'), ('state', 'maintenance')])


class TestResolveValue(unittest.TestCase):
    def test_resolve_dotted_multi_attr(self):
        vm1 = DatasetObject({'hostname': 'vm-1'}, object_id=1)
        vm2 = DatasetObject({'hostname': 'vm-2'}, object_id=2)
        server = DatasetObject({'hostname': 'hv-1', 'vms': [vm1, vm2]})

        result = _resolve_value(server, 'vms.hostname')

        self.assertIsInstance(result, MultiAttr)
        self.assertEqual(sorted(result), ['vm-1', 'vm-2'])

    def test_resolve_dotted_single_relation(self):
        related = DatasetObject({'hostname': 'lb-1'}, object_id=1)
        server = DatasetObject({'loadbalancer': related})

        result = _resolve_value(server, 'loadbalancer.hostname')

        self.assertEqual(result, 'lb-1')