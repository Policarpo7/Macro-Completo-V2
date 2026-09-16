import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from admin.license_tool import issue
from macro.licensing import encode, LicenseError

DEVICE = "a" * 64


@unittest.skipUnless(sys.platform == "win32", "Windows GUI smoke test")
class Gui(unittest.TestCase):
    def test_save_activate_renew_and_preview_without_mouse(self):
        import app
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private = Ed25519PrivateKey.generate()
            public = private.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw)
            (root / "public_key.txt").write_text(encode(public))
            with patch.object(app, "ROOT", root), patch.object(app, "data_dir", return_value=root), \
                 patch.object(app, "device_id", return_value=DEVICE), \
                 patch.object(app.Engine, "start"), \
                 patch.object(app.messagebox, "showerror", side_effect=AssertionError("Unexpected UI error")):
                window = app.App(autostart=False)
                try:
                    window.initialize()
                    window.update()
                    self.assertEqual(len(window.items), 10)
                    window.fields["vertical"].set("5.5")
                    window.fields["lateral"].set("-1")
                    window.save_current()
                    window.update()
                    self.assertEqual(window.items[0].vertical, 5.5)
                    self.assertTrue((root / "profiles.json").exists())
                    window.install_license(issue(private, "diaria", DEVICE, "Teste"), persist=True)
                    self.assertEqual(window.session.license.plan, "diaria")
                    window.engine.available = True
                    window.tabs.select(window.profiles_tab)
                    window.update()
                    window.toggle()
                    self.assertTrue(window.engine.enabled)
                    window.install_license(issue(private, "lifetime", DEVICE, "Teste"), persist=True)
                    self.assertFalse(window.engine.enabled)
                    self.assertIsNone(window.session.license.expires_at)
                    old = (root / "license.json").read_text()
                    with self.assertRaises(LicenseError):
                        window.install_license("invalid", persist=True)
                    self.assertEqual((root / "license.json").read_text(), old)
                    window.copy_profile()
                    window.update()
                    self.assertEqual(len(window.items), 11)
                    window.new_dmr()
                    window.update()
                    self.assertEqual(len(window.items), 12)
                    self.assertTrue(window.rapid_fire.get())
                    window.fire_cps.set("6.5")
                    window.save_current()
                    window.update()
                    self.assertEqual(window.items[-1].fire_cps, 6.5)
                    self.assertTrue(window.items[-1].rapid_fire)
                    self.assertEqual(window.items[-1].vertical, 0)
                    self.assertIsNotNone(window._brand_icon)
                    window.preview()
                    window.update()
                    self.assertFalse(window.engine.enabled)
                finally:
                    window.close()


if __name__ == "__main__":
    unittest.main()
