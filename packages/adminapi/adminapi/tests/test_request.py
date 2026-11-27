"""Serveradmin - adminapi

Copyright (c) 2026 InnoGames GmbH
"""
import os
import unittest
from base64 import b64decode
from tempfile import TemporaryDirectory

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
from paramiko import ECDSAKey, Ed25519Key, RSAKey
from paramiko.agent import AgentKey
from paramiko.message import Message

from adminapi.request import (
    calc_message,
    calc_signature,
    calc_signatures,
    load_private_key_file,
)

SSH2_AGENTC_SIGN_REQUEST = 13
SSH2_AGENT_SIGN_RESPONSE = 14
# Signature flags of the ssh-agent protocol, anything else means ssh-rsa
AGENT_RSA_ALGORITHMS = {2: 'rsa-sha2-256', 4: 'rsa-sha2-512'}

TIMESTAMP = 1700000000
BODY = '{"hostname": "test0"}'


def verify(public_key_base64, signature, timestamp=TIMESTAMP, body=BODY):
    """Verify a signature the way serveradmin does

    This mirrors serveradmin.apps.models.PublicKey.load() and
    serveradmin.api.decorators.authenticate_app_ssh(): The server knows
    nothing but the public key blob and gets the signature base64 encoded.
    """
    public_key_blob = b64decode(public_key_base64)
    key_algorithm = Message(public_key_blob).get_text()
    if key_algorithm.startswith('ssh-ed25519'):
        public_key = Ed25519Key(data=public_key_blob)
    elif key_algorithm.startswith('ecdsa-'):
        public_key = ECDSAKey(data=public_key_blob)
    else:
        public_key = RSAKey(data=public_key_blob)

    return public_key.verify_ssh_sig(
        data=calc_message(timestamp, body).encode(),
        msg=Message(b64decode(signature)),
    )


def signature_algorithm(signature):
    return Message(b64decode(signature)).get_text()


class FakeAgent:
    """Stand-in for a running ssh-agent holding RSA keys

    Like a real agent it signs with the SHA-1 based ssh-rsa unless the
    request flags ask for one of the SHA-2 algorithms.
    """

    def __init__(self, *keys):
        self.keys = {key.asbytes(): key for key in keys}

    def _send_message(self, msg):
        request = Message(msg.asbytes())
        assert ord(request.get_byte()) == SSH2_AGENTC_SIGN_REQUEST
        key = self.keys[request.get_binary()]
        data = request.get_binary()
        algorithm = AGENT_RSA_ALGORITHMS.get(request.get_int(), 'ssh-rsa')

        response = Message()
        response.add_string(key.sign_ssh_data(data, algorithm).asbytes())
        response.rewind()
        return SSH2_AGENT_SIGN_RESPONSE, response


class TestFileKeySignature(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = TemporaryDirectory()
        cls.addClassCleanup(cls.tmp_dir.cleanup)
        cls.keys = {
            'rsa': cls.load(
                rsa.generate_private_key(public_exponent=65537, key_size=2048)
            ),
            'ecdsa': cls.load(ec.generate_private_key(ec.SECP256R1())),
            'ed25519': cls.load(ed25519.Ed25519PrivateKey.generate()),
        }

    @classmethod
    def load(cls, private_key):
        """Write the key like ssh-keygen and load it like adminapi"""
        path = os.path.join(cls.tmp_dir.name, type(private_key).__name__)
        with open(path, 'wb') as key_file:
            key_file.write(private_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.OpenSSH,
                serialization.NoEncryption(),
            ))
        return load_private_key_file(path)

    def test_loaded_key_types(self):
        self.assertIsInstance(self.keys['rsa'], RSAKey)
        self.assertIsInstance(self.keys['ecdsa'], ECDSAKey)
        self.assertIsInstance(self.keys['ed25519'], Ed25519Key)

    def test_round_trip(self):
        for name, key in self.keys.items():
            with self.subTest(key=name):
                signature = calc_signature(key, TIMESTAMP, BODY)
                self.assertTrue(verify(key.get_base64(), signature))

    def test_round_trip_without_body(self):
        for name, key in self.keys.items():
            with self.subTest(key=name):
                signature = calc_signature(key, TIMESTAMP)
                self.assertTrue(
                    verify(key.get_base64(), signature, body=None)
                )

    def test_signature_algorithms(self):
        expected = {
            # Paramiko >= 5 can't verify the SHA-1 based ssh-rsa anymore
            'rsa': 'rsa-sha2-512',
            'ecdsa': 'ecdsa-sha2-nistp256',
            'ed25519': 'ssh-ed25519',
        }
        for name, key in self.keys.items():
            with self.subTest(key=name):
                signature = calc_signature(key, TIMESTAMP, BODY)
                self.assertEqual(
                    expected[name], signature_algorithm(signature)
                )

    def test_changed_body_is_rejected(self):
        for name, key in self.keys.items():
            with self.subTest(key=name):
                signature = calc_signature(key, TIMESTAMP, BODY)
                self.assertFalse(
                    verify(key.get_base64(), signature, body=BODY + ' ')
                )

    def test_changed_timestamp_is_rejected(self):
        for name, key in self.keys.items():
            with self.subTest(key=name):
                signature = calc_signature(key, TIMESTAMP, BODY)
                self.assertFalse(verify(
                    key.get_base64(), signature, timestamp=TIMESTAMP + 1
                ))

    def test_other_key_is_rejected(self):
        other_key = RSAKey.generate(2048)
        signature = calc_signature(other_key, TIMESTAMP, BODY)
        self.assertFalse(verify(self.keys['rsa'].get_base64(), signature))


class TestAgentKeySignature(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = RSAKey.generate(2048)
        agent = FakeAgent(cls.private_key)
        cls.agent_key = AgentKey(agent, cls.private_key.asbytes())

    def test_round_trip(self):
        signature = calc_signature(self.agent_key, TIMESTAMP, BODY)
        self.assertTrue(verify(self.agent_key.get_base64(), signature))

    def test_signature_algorithm(self):
        # The agent signs with ssh-rsa unless we ask for something better
        signature = calc_signature(self.agent_key, TIMESTAMP, BODY)
        self.assertEqual('rsa-sha2-512', signature_algorithm(signature))

    def test_changed_body_is_rejected(self):
        signature = calc_signature(self.agent_key, TIMESTAMP, BODY)
        self.assertFalse(
            verify(self.agent_key.get_base64(), signature, body=BODY + ' ')
        )

    def test_calc_signatures(self):
        signatures = calc_signatures([self.agent_key], TIMESTAMP, BODY)

        self.assertEqual(
            [self.private_key.get_base64()], list(signatures.keys())
        )
        for public_key_base64, signature in signatures.items():
            self.assertTrue(verify(public_key_base64, signature))
