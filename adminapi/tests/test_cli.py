import unittest
from argparse import ArgumentParser
from typing import NoReturn, Text

from adminapi.cli import parse_args


# ArgumentParser exists on error, we cannot capture this so we override it
class ArgumentParserMock(ArgumentParser):
    def error(self, message: Text) -> NoReturn:
        raise Exception(message)


class TestCommandlineInterface(unittest.TestCase):
    def test_no_argument(self, *args):
        with self.assertRaises(SystemExit):
            parse_args([])

    def test_unknown_argument(self, *args):
        with self.assertRaises(SystemExit):
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
