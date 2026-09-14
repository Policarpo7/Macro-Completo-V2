import json
import os
import tempfile
from pathlib import Path


def data_dir():
    root = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    path = root / "PolicarpoMacroV2"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path, value):
    """Replace atomically; a failed write must not destroy the previous file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
