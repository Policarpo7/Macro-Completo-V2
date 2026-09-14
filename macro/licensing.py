import base64
import hashlib
import json
import math
import re
import sys
import time
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from macro.storage import write_json

PRODUCT = "macro-completo-v2"
PLAN_DAYS = {"diaria": 1, "semanal": 7, "mensal": 30, "lifetime": None}
PLAN_LABELS = {"diaria": "Diária", "semanal": "Semanal", "mensal": "Mensal", "lifetime": "Vitalícia"}


class LicenseError(ValueError):
    pass


def encode(data):
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def decode(value):
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)


def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def device_id():
    if sys.platform != "win32":
        raise LicenseError("A identificação do computador requer Windows.")
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography",
                        0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
        guid, _ = winreg.QueryValueEx(key, "MachineGuid")
    return hashlib.sha256((PRODUCT + ":" + str(guid)).encode()).hexdigest()


@dataclass(frozen=True)
class License:
    license_id: str
    plan: str
    customer: str
    expires_at: int | None


def verify(token, public_key, device, now=None):
    now = time.time() if now is None else now
    try:
        if not isinstance(token, str) or len(token) > 8192:
            raise LicenseError("Key inválida.")
        prefix, encoded_payload, encoded_signature = token.strip().split(".")
        if prefix != "MCV2":
            raise LicenseError("Formato de key incompatível.")
        body = decode(encoded_payload)
        Ed25519PublicKey.from_public_bytes(public_key).verify(decode(encoded_signature), body)
        payload = json.loads(body)
        if not isinstance(payload, dict) or payload.get("product") != PRODUCT or payload.get("v") != 1:
            raise LicenseError("Key de outro produto ou versão.")
        if payload.get("device") != device:
            raise LicenseError("Esta key pertence a outro computador.")
        plan = payload.get("plan")
        if plan not in PLAN_DAYS:
            raise LicenseError("Plano desconhecido.")
        issued = payload.get("issued_at")
        expires = payload.get("expires_at")
        if type(issued) is not int or issued < 0:
            raise LicenseError("Data de emissão inválida.")
        if issued > now + 300:
            raise LicenseError("Key emitida no futuro. Confira o relógio do Windows.")
        days = PLAN_DAYS[plan]
        if days is None:
            if expires is not None:
                raise LicenseError("Vencimento inválido para lifetime.")
        elif type(expires) is not int or expires != issued + days * 86400:
            raise LicenseError("Prazo incompatível com o plano.")
        if expires is not None and now >= expires:
            raise LicenseError("Licença expirada. Solicite uma nova key ao fornecedor.")
        if not isinstance(payload.get("id"), str) or not payload["id"]:
            raise LicenseError("Identificador da licença inválido.")
        if not isinstance(payload.get("customer"), str) or not payload["customer"].strip():
            raise LicenseError("Cliente da licença inválido.")
        return License(payload["id"], plan, payload["customer"], expires)
    except LicenseError:
        raise
    except (ValueError, TypeError, KeyError, InvalidSignature, UnicodeError) as error:
        raise LicenseError("Key inválida ou assinatura incorreta.") from error


class LicenseSession:
    """Deadline checked by the worker even if the GUI stops processing events."""
    def __init__(self, license, now=None, monotonic=None):
        self.license = license
        now = time.time() if now is None else now
        monotonic = time.monotonic() if monotonic is None else monotonic
        self.anchor = now
        self.started = monotonic
        self.deadline = (None if license.expires_at is None
                         else monotonic + max(0, license.expires_at - now))

    def valid(self, now=None, monotonic=None):
        now = time.time() if now is None else now
        monotonic = time.monotonic() if monotonic is None else monotonic
        expected = self.anchor + monotonic - self.started
        if now < expected - 300:
            return False
        return self.deadline is None or (
            monotonic < self.deadline and now < self.license.expires_at)


class ClockGuard:
    """Best-effort local rollback detection, not a trusted time service."""
    def __init__(self, path):
        self.path = path
        self.last = 0
        if path.exists():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))["last_seen"]
                if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
                    raise ValueError()
                self.last = value
            except (ValueError, KeyError, TypeError) as error:
                raise LicenseError("Registro de horário inválido. Contate o fornecedor.") from error

    def check(self, now=None):
        now = time.time() if now is None else now
        if now < self.last - 300:
            raise LicenseError("Relógio atrasado. Corrija a data/hora do Windows.")
        self.last = max(self.last, now)

    def save(self):
        write_json(self.path, {"last_seen": self.last})
