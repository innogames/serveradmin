import json
import unittest

from serveradmin.powerdns.sync.objects import RecordContent, RRSet, RRSetEncoder
from serveradmin.powerdns.sync.utils import ensure_canonical, quote_string, get_dns_zone


class Records(unittest.TestCase):
    def test_to_json(self):
        rrsets = []
        rrset = RRSet("foo.example.com", "A", 3600)
        rrset.records = (
            RecordContent("127.0.0.1"),
        )
        rrsets.append(rrset)

        actual = json.dumps(rrsets, cls=RRSetEncoder)
        expected = """[{"changetype": "REPLACE", "type": "A", "name": "foo.example.com.",
         "ttl": 3600, "records": [{"content": "127.0.0.1"}]}]"""
        self.assertEqual(actual, expected)


class TestUtils(unittest.TestCase):
    def test_ensure_trailing_dot(self):
        test_cases = [
            ('', '.'),
            ('test', 'test.'),
            ('test.', 'test.'),
            ('test.de.', 'test.de.'),
            ('test.de', 'test.de.'),
        ]
        for test_case in test_cases:
            self.assertEqual(ensure_canonical(test_case[0]), test_case[1])

    def test_quote_string(self):
        test_cases = [
            ('', '""'),
            ('test', '"test"'),
            ('"test"', '"test"'),
            ('t"est', '"t\"est"'),
            ('t\'est', '"t\'est"'),
        ]
        for test_case in test_cases:
            self.assertEqual(quote_string(test_case[0]), test_case[1])


class TestGetDNSZone(unittest.TestCase):
    def test_get_dns_zone(self):
        test_cases = [
            ("foo.example.com", "example.com"),
            ("foo.ig.local", "ig.local"),
            ("foo.bar.co.uk", "bar.co.uk"),
            ("www.example.net", "example.net"),
            ("test.gov.uk", "test.gov.uk"),
            ("subdomain.example.org", "example.org"),
            ("ae19.tribalwars.ae", "tribalwars.ae"),
        ]
        for domain, expected in test_cases:
            with self.subTest(domain=domain, expected=expected):
                self.assertEqual(get_dns_zone(domain), expected)
