import unittest

from adminapi.dataset import strtobool


class TestStrtobool(unittest.TestCase):
    def test_true_values(self):
        true_values = ['y', 'yes', 't', 'true', 'on', '1']
        for value in true_values:
            with self.subTest(value=value):
                self.assertTrue(strtobool(value))

    def test_false_values(self):
        false_values = ['n', 'no', 'f', 'false', 'off', '0']
        for value in false_values:
            with self.subTest(value=value):
                self.assertFalse(strtobool(value))

    def test_invalid_values(self):
        invalid_values = ['maybe', '2', 'none', '', 'Yess']
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    strtobool(value)
