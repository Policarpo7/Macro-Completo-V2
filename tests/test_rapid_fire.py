import json
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from macro.engine import Engine
from macro.profiles import Profile, load_profiles, save_profiles
from macro.rapid_fire import LEFT_DOWN, LEFT_UP, RapidFire


class RapidFireTests(unittest.TestCase):
    def engine(self):
        engine = Engine()
        engine.profile = Profile("dmr", "Manual", "DMR", vertical=0, rapid_fire=True, fire_cps=5)
        engine.available = True
        engine.session = SimpleNamespace(valid=lambda: True)
        engine.mouse = SimpleNamespace(Button=SimpleNamespace(left="left", right="right"))
        engine.output = []
        engine.user32 = SimpleNamespace(mouse_event=lambda flags, *args: engine.output.append(flags))
        engine.toggle()
        engine._click(0, 0, "left", True)
        engine._click(0, 0, "right", True)
        return engine

    def test_rate_and_press_duration(self):
        rapid = RapidFire()
        self.assertEqual(rapid.step(0, 5), (LEFT_UP,))
        self.assertEqual(rapid.step(0.199, 5), ())
        self.assertEqual(rapid.step(0.2, 5), (LEFT_DOWN,))
        self.assertEqual(rapid.step(0.21, 5), ())
        self.assertEqual(rapid.step(0.221, 5), (LEFT_UP,))
        self.assertEqual(rapid.step(0.399, 5), ())
        self.assertEqual(rapid.step(0.4, 5), (LEFT_DOWN,))

    def test_slow_tick_never_catches_up_with_burst(self):
        rapid = RapidFire()
        rapid.step(0, 12)
        self.assertEqual(rapid.step(10, 12), (LEFT_DOWN,))
        self.assertEqual(rapid.step(10, 12), ())
        self.assertEqual(rapid.step(11, 12), (LEFT_UP,))
        self.assertEqual(rapid.step(11, 12), (LEFT_DOWN,))
        self.assertEqual(rapid.step(11, 12), ())

    def test_either_physical_button_release_stops(self):
        for button in ("left", "right"):
            with self.subTest(button=button):
                engine = self.engine()
                engine._tick(0)
                engine._tick(0.2)
                self.assertEqual(engine.output[-1], LEFT_DOWN)
                engine._click(0, 0, button, False)
                self.assertEqual(engine.output[-1], LEFT_UP)
                count = len(engine.output)
                engine._tick(0.4)
                self.assertEqual(len(engine.output), count)

    def test_pause_switch_and_close_release_pressed_click(self):
        for operation in ("pause", "switch", "close"):
            engine = self.engine()
            engine._tick(0)
            engine._tick(0.2)
            if operation == "switch":
                engine.set_profile(replace(engine.profile, rapid_fire=False))
            else:
                getattr(engine, operation)()
            self.assertEqual(engine.output[-1], LEFT_UP)
            self.assertFalse(engine.enabled)
            self.assertFalse(engine.rapid.active)

    def test_expiry_releases_before_next_click(self):
        engine = self.engine()
        engine._tick(0)
        engine._tick(0.2)
        engine.session = SimpleNamespace(valid=lambda: False)
        engine.stop_event = SimpleNamespace(is_set=lambda: False,
                                             wait=lambda _: engine.stop_event.__setattr__("is_set", lambda: True))
        engine._loop()
        self.assertEqual(engine.output, [LEFT_UP, LEFT_DOWN, LEFT_UP])
        self.assertFalse(engine.enabled)
        self.assertEqual(engine.events.get_nowait(), "expired")

    def test_rapid_fire_off_keeps_recoil_only(self):
        engine = self.engine()
        engine.profile = replace(engine.profile, rapid_fire=False, vertical=2)
        engine._tick(0)
        engine._tick(0.1)
        self.assertEqual(engine.output, [0x0001, 0x0001])

    def test_synthetic_clicks_do_not_change_physical_hold(self):
        engine = self.engine()
        self.assertFalse(engine._physical_events_only(0, SimpleNamespace(flags=1)))
        self.assertFalse(engine._physical_events_only(0, SimpleNamespace(flags=3)))
        self.assertTrue(engine._physical_events_only(0, SimpleNamespace(flags=0)))
        engine._tick(0)
        engine._tick(0.2)
        self.assertTrue(engine.left and engine.right)

    def test_saved_profile_and_legacy_migration(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "profiles.json"
            legacy = asdict(Profile("old", "Ash", "R4-C"))
            del legacy["rapid_fire"]
            del legacy["fire_cps"]
            path.write_text(json.dumps({"version": 1, "profiles": [legacy]}))
            profile = load_profiles(path)[0]
            self.assertFalse(profile.rapid_fire)
            profile = replace(profile, rapid_fire=True, fire_cps=6.5)
            save_profiles(path, [profile])
            self.assertEqual(load_profiles(path), [profile])

    def test_invalid_rates_and_mode(self):
        profile = Profile("test", "Manual", "DMR")
        for rate in (0, 13, float("nan"), float("inf"), True):
            with self.assertRaises(ValueError):
                replace(profile, fire_cps=rate).validate()
        with self.assertRaises(ValueError):
            replace(profile, rapid_fire="yes").validate()
