import os
import time
import unittest

os.environ.setdefault("WZ_JWT_SECRET", "test-secret-for-unit-tests-only")

from apps.api.auth import create_access_token, decode_access_token, TokenError


class TestJWT(unittest.TestCase):
    def test_round_trip(self):
        token = create_access_token(1, "nurse1@wardzero.local", "caregiver")
        payload = decode_access_token(token)
        self.assertEqual(payload["email"], "nurse1@wardzero.local")
        self.assertEqual(payload["role"], "caregiver")
        self.assertEqual(payload["sub"], "1")

    def test_tampered_token_rejected(self):
        token = create_access_token(1, "a@b.com", "caregiver")
        tampered = token[:-2] + ("aa" if token[-2:] != "aa" else "bb")
        with self.assertRaises(TokenError):
            decode_access_token(tampered)

    def test_wrong_secret_rejected(self):
        token = create_access_token(1, "a@b.com", "administrator")
        old = os.environ["WZ_JWT_SECRET"]
        os.environ["WZ_JWT_SECRET"] = "different-secret"
        try:
            with self.assertRaises(TokenError):
                decode_access_token(token)
        finally:
            os.environ["WZ_JWT_SECRET"] = old

    def test_missing_secret_raises(self):
        old = os.environ.pop("WZ_JWT_SECRET")
        old_env = os.environ.get("WZ_ENV")
        os.environ["WZ_ENV"] = "production"
        try:
            with self.assertRaises(RuntimeError):
                create_access_token(1, "a@b.com", "caregiver")
        finally:
            os.environ["WZ_JWT_SECRET"] = old
            if old_env is None:
                os.environ.pop("WZ_ENV", None)
            else:
                os.environ["WZ_ENV"] = old_env

    def test_dev_mode_without_secret_uses_random_secret(self):
        old = os.environ.pop("WZ_JWT_SECRET")
        old_env = os.environ.pop("WZ_ENV", None)
        try:
            tok = create_access_token(1, "a@b.com", "caregiver")
            self.assertEqual(decode_access_token(tok)["email"], "a@b.com")
        finally:
            os.environ["WZ_JWT_SECRET"] = old
            if old_env is not None:
                os.environ["WZ_ENV"] = old_env


if __name__ == "__main__":
    unittest.main()
