import tempfile
import unittest
import zipfile
from pathlib import Path

from admin.distribution import provision, load_issuer, package_client
from admin.license_tool import issue
from macro.licensing import decode, verify


class Distribution(unittest.TestCase):
    def test_owner_setup_and_client_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            password = "test-password-123"
            provision(folder, password)
            key = load_issuer(folder, password)
            device = "a" * 64
            token = issue(key, "mensal", device, "Teste")
            public = decode((folder / "public_key.txt").read_text().strip())
            self.assertEqual(verify(token, public, device).plan, "mensal")
            with self.assertRaises(ValueError):
                provision(folder, password)
            with self.assertRaises(ValueError):
                load_issuer(folder, "wrong-password")
            executable = folder / "MacroCompleto.exe"
            executable.write_bytes(b"test-placeholder")
            package = folder / "client.zip"
            package_client(executable, folder, package)
            with zipfile.ZipFile(package) as archive:
                self.assertEqual(set(archive.namelist()), {"MacroCompleto.exe", "public_key.txt", "LEIA-ME.txt"})
                self.assertEqual(decode(archive.read("public_key.txt").decode().strip()), public)
            original = package.read_bytes()
            with self.assertRaises(ValueError):
                package_client(executable, folder, package)
            self.assertEqual(package.read_bytes(), original)

    def test_short_password_creates_no_private_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            with self.assertRaises(ValueError):
                provision(folder, "short")
            self.assertFalse((folder / "issuer-private.pem").exists())
