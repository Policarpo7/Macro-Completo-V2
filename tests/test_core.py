import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from admin.license_tool import issue
from macro.engine import Engine, FractionalMotion
from macro.licensing import (ClockGuard, License, LicenseError, LicenseSession, PLAN_DAYS,
                             canonical, decode, encode, verify)
from macro.profiles import Profile, defaults, duplicate, load_profiles, save_profiles

DEVICE = "a" * 64
NOW = 1800000000


class Licenses(unittest.TestCase):
    def setUp(self):
        self.key = Ed25519PrivateKey.generate()
        self.public = self.key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    def token(self, plan="diaria", now=NOW):
        return issue(self.key, plan, DEVICE, "Cliente Teste", now=now)

    def test_all_plans_and_exact_expiry(self):
        for plan, days in PLAN_DAYS.items():
            with self.subTest(plan=plan):
                token = self.token(plan)
                result = verify(token, self.public, DEVICE, now=NOW)
                if days is None:
                    self.assertIsNone(result.expires_at)
                    verify(token, self.public, DEVICE, now=NOW + 100 * 365 * 86400)
                else:
                    end = NOW + days * 86400
                    self.assertEqual(result.expires_at, end)
                    verify(token, self.public, DEVICE, now=end - 1)
                    with self.assertRaises(LicenseError):
                        verify(token, self.public, DEVICE, now=end)

    def test_wrong_machine(self):
        with self.assertRaisesRegex(LicenseError, "outro computador"):
            verify(self.token(), self.public, "b" * 64, now=NOW)

    def test_forged_payload_rejected(self):
        prefix, body, signature = self.token().split(".")
        data = json.loads(decode(body))
        data["plan"], data["expires_at"] = "lifetime", None
        token = prefix + "." + encode(canonical(data)) + "." + signature
        with self.assertRaises(LicenseError):
            verify(token, self.public, DEVICE, now=NOW)

    def test_wrong_signing_key(self):
        token = issue(Ed25519PrivateKey.generate(), "mensal", DEVICE, "Outro", now=NOW)
        with self.assertRaises(LicenseError):
            verify(token, self.public, DEVICE, now=NOW)

    def test_invalid_tokens(self):
        for value in ("", "MCV2.foo.bar", "MCV2.!.$", "x" * 9000, None):
            with self.subTest(value=str(value)[:20]), self.assertRaises(LicenseError):
                verify(value, self.public, DEVICE, now=NOW)

    def test_invalid_signed_payloads(self):
        _, body, _ = self.token().split(".")
        original = json.loads(decode(body))
        for update in ({"plan": "anual"}, {"issued_at": True}, {"expires_at": NOW + 1},
                       {"product": "outro"}, {"customer": ""}, {"id": ""}):
            data = {**original, **update}
            payload = canonical(data)
            token = "MCV2." + encode(payload) + "." + encode(self.key.sign(payload))
            with self.subTest(update=update), self.assertRaises(LicenseError):
                verify(token, self.public, DEVICE, now=NOW)

    def test_future_issue(self):
        with self.assertRaises(LicenseError):
            verify(self.token(now=NOW + 301), self.public, DEVICE, now=NOW)

    def test_reactivation_does_not_renew(self):
        token = self.token()
        self.assertEqual(verify(token, self.public, DEVICE, now=NOW + 4000).expires_at, NOW + 86400)
        with self.assertRaises(LicenseError):
            verify(token, self.public, DEVICE, now=NOW + 86401)
        new = self.token("semanal", now=NOW + 86401)
        self.assertEqual(verify(new, self.public, DEVICE, now=NOW + 86401).plan, "semanal")

    def test_bad_device_and_customer_on_issue(self):
        for device, customer in (("abc", "User"), (DEVICE, ""), (DEVICE, "x" * 201)):
            with self.assertRaises(ValueError):
                issue(self.key, "diaria", device, customer, NOW)

    def test_session_expiry_without_gui(self):
        session = LicenseSession(License("id", "diaria", "Test", NOW + 10), now=NOW, monotonic=100)
        self.assertTrue(session.valid(now=NOW + 9, monotonic=109))
        self.assertFalse(session.valid(now=NOW + 10, monotonic=110))
        self.assertFalse(session.valid(now=NOW, monotonic=111))

    def test_lifetime_session_clock_rollback(self):
        session = LicenseSession(License("id", "lifetime", "Test", None), now=NOW, monotonic=100)
        self.assertTrue(session.valid(now=NOW + 10000, monotonic=10100))
        self.assertFalse(session.valid(now=NOW - 400, monotonic=101))

    def test_persisted_clock_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clock.json"
            guard = ClockGuard(path)
            guard.check(now=NOW)
            guard.save()
            second = ClockGuard(path)
            with self.assertRaises(LicenseError):
                second.check(now=NOW - 301)
            second.check(now=NOW + 10)

    def test_corrupt_clock_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clock.json"
            for content in ('oops', '{"last_seen": NaN}', '{"last_seen": true}'):
                path.write_text(content)
                with self.assertRaises(LicenseError):
                    ClockGuard(path)


class ProfilesAndMotion(unittest.TestCase):
    def test_roundtrip_custom_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.json"
            items = defaults()
            items[0] = replace(items[0], vertical=4.5, lateral=-0.8, calibrated=True,
                               dpi=1600, sensitivity="H 10 / V 10 / ADS 35", loadout="Mira teste")
            save_profiles(path, items)
            self.assertEqual(load_profiles(path), items)

    def test_invalid_profile_values(self):
        profile = defaults()[0]
        for update in ({"vertical": float("nan")}, {"lateral": 6}, {"interval_ms": 0},
                       {"dpi": True}, {"operator": ""}, {"vertical": float("inf")},
                       {"calibrated": "yes"}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                replace(profile, **update).validate()

    def test_corruption_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.json"
            path.write_text("corrupt")
            with self.assertRaises(ValueError):
                load_profiles(path)
            self.assertEqual(path.read_text(), "corrupt")

    def test_duplicate_ids_and_empty_list_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.json"
            for items in ([], [defaults()[0], defaults()[0]]):
                with self.assertRaises(ValueError):
                    save_profiles(path, items)

    def test_duplicate_preserves_settings(self):
        source = replace(defaults()[0], lateral=1.5)
        copy = duplicate(source)
        self.assertNotEqual(copy.id, source.id)
        self.assertEqual(copy.lateral, source.lateral)

    def test_small_horizontal_motion_both_directions(self):
        for force, expected in ((1, 30), (-1, -30), (0.5, 15), (-0.5, -15)):
            motion = FractionalMotion()
            results = [motion.step(force, 0.5) for _ in range(100)]
            self.assertEqual(sum(x for x, y in results), expected)
            self.assertEqual(sum(y for x, y in results), 50)

    def test_reset_clears_fraction(self):
        motion = FractionalMotion()
        motion.step(1, 0.5)
        motion.reset()
        self.assertEqual(motion.step(1, 0.5), (0, 0))

    def test_engine_cannot_enable_without_license(self):
        engine = Engine()
        engine.available = True
        with self.assertRaises(ValueError):
            engine.toggle()
        self.assertFalse(engine.enabled)

    def test_profile_change_and_pause_reset_buttons(self):
        engine = Engine()
        engine.enabled = engine.left = engine.right = True
        engine.set_profile(defaults()[0])
        self.assertFalse(engine.enabled or engine.left or engine.right)

    def test_worker_stops_expired_session_before_moving(self):
        class Expired:
            def valid(self):
                return False
        engine = Engine()
        engine.session = Expired()
        engine.enabled = engine.left = engine.right = True
        class OneIteration:
            def is_set(self):
                return False
            def wait(self, interval):
                raise RuntimeError("End deterministic test loop")
        engine.stop_event = OneIteration()
        engine._loop()
        self.assertFalse(engine.enabled)
        self.assertEqual(engine.events.get_nowait(), "expired")


if __name__ == "__main__":
    unittest.main()
