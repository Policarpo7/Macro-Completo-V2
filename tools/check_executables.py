"""CI smoke test runs the compiled binaries, not the source entrypoints."""
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as directory:
    env = os.environ.copy()
    env["LOCALAPPDATA"] = directory
    for name in ("MacroCompleto", "GerenciadorLicencas"):
        executable = root / "dist" / (name + ".exe")
        subprocess.run([str(executable), "--smoke-test"], check=True, timeout=90,
                       cwd=directory, env=env)
        print(name + ": compiled GUI smoke test passed")
