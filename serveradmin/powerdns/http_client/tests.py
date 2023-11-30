import json
import unittest

from powerdns.http_client.objects import RecordContent, RRSet, RRSetEncoder
from serveradmin.powerdns.http_client.utils import ensure_trailing_dot, quote_string


class Records(unittest.TestCase):
    def test_to_json(self):
        rrsets = []
        rrset = RRSet()
        rrset.type = "A"
        rrset.name = ensure_trailing_dot("foo.example.com")
        rrset.ttl = 3600
        rrset.records = [
            RecordContent("127.0.0.1"),
        ]
        rrsets.append(rrset)

        actual = json.dumps(rrsets, cls=RRSetEncoder)
        expected = """[{"changetype": "REPLACE", "type": "A", "name": "foo.example.com.", "ttl": 3600, "records": [{"content": "127.0.0.1"}]}]"""
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
            self.assertEqual(ensure_trailing_dot(test_case[0]), test_case[1])

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
