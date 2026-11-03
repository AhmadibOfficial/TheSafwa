"""Regression tests using synthetic values only."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from ai_security_preflight import blocked_path, inspect_content

class ConfidentialityGateTests(unittest.TestCase):
    def test_private_files_are_blocked(self):
        for path in (
            ".env", ".env.local", "apps/site/.env.production", "secrets/keys.txt",
            "apps/admin/private/config.json", "foo/credentials.json",
            "certs/signing.pem", "app/id_rsa", "backup/service-account.json",
        ):
            with self.subTest(path=path):
                self.assertTrue(blocked_path(path))

    def test_synthetic_environment_examples_are_allowed(self):
        for path in (".env.example", ".env.sample", "packages/web/.env.example"):
            self.assertFalse(blocked_path(path))

    def test_private_key_detected_without_printing_contents(self):
        result = inspect_content("demo.py", b"value = '-----BEGIN " + b"PRIVATE KEY-----'")
        self.assertIn("private-key-header", result)

    def test_high_confidence_token_detected(self):
        token = b"ghp_" + b"Z" * 36
        self.assertIn("github-access-token", inspect_content("demo.py", token))

    def test_literal_password_blocked(self):
        self.assertIn("hardcoded-credential", inspect_content("config.py", b"password" + b' = "somelonghardcodedvalue"'))

    def test_placeholder_not_flagged(self):
        self.assertEqual([], inspect_content("config.py", b'password = "example-only-placeholder"'))
        self.assertEqual([], inspect_content("config.py", b'token = process.env.SECRET'))

    def test_binary_skipped(self):
        self.assertEqual([], inspect_content("logo.jpg", b"\x00-----BEGIN " + b"PRIVATE KEY-----"))

if __name__ == "__main__":
    unittest.main()
