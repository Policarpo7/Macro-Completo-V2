import json
import math
import uuid
from dataclasses import asdict, dataclass, replace

from macro.storage import write_json

# Catalog examples, not calibrated recoil measurements.
CATALOG = {"Ash": ["R4-C", "G36C"], "Sledge": ["L85A2"],
           "Thermite": ["556xi"], "Twitch": ["F2"],
           "Jäger": ["416-C CARBINE"], "Bandit": ["MP7"],
           "Doc": ["MP5"], "Smoke": ["FMG-9", "SMG-11"]}


@dataclass(frozen=True)
class Profile:
    id: str
    operator: str
    weapon: str
    loadout: str = "Padrão"
    vertical: float = 8.0
    lateral: float = 0.0
    interval_ms: float = 9.0
    dpi: int = 800
    sensitivity: str = "Preencher H / V / ADS"
    calibrated: bool = False
    rapid_fire: bool = False
    fire_cps: float = 5.0

    def validate(self):
        for field in ("id", "operator", "weapon", "loadout", "sensitivity"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip() or len(value) > 200:
                raise ValueError("Preencha " + field + " (até 200 caracteres).")
        for field, minimum, maximum in (("vertical", 0, 30), ("lateral", -5, 5),
                                        ("interval_ms", 5, 100), ("fire_cps", 1, 12)):
            value = getattr(self, field)
            if type(value) not in (float, int) or not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError(f"{field}: informe um valor entre {minimum} e {maximum}.")
        if type(self.dpi) is not int or not 100 <= self.dpi <= 50000:
            raise ValueError("DPI deve ser um inteiro de 100 a 50000.")
        if type(self.calibrated) is not bool:
            raise ValueError("Estado de calibração inválido.")
        if type(self.rapid_fire) is not bool:
            raise ValueError("Estado de Rapid Fire inválido.")
        return self

    @property
    def label(self):
        mark = "✓" if self.calibrated else "○"
        mode = " [RF]" if self.rapid_fire else ""
        return f"{mark} {self.operator} / {self.weapon} / {self.loadout}{mode}"


def defaults():
    return [Profile(f"seed-{operator}-{weapon}", operator, weapon)
            for operator, weapons in CATALOG.items() for weapon in weapons]


def load_profiles(path):
    if not path.exists():
        return defaults()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("version") != 1 or not isinstance(raw.get("profiles"), list):
        raise ValueError("Arquivo de perfis incompatível.")
    if not 1 <= len(raw["profiles"]) <= 1000:
        raise ValueError("A lista deve conter de 1 a 1000 perfis.")
    items = [Profile(**row).validate() for row in raw["profiles"]]
    if len({p.id for p in items}) != len(items):
        raise ValueError("Há identificadores de perfis duplicados.")
    return items


def save_profiles(path, profiles):
    if not 1 <= len(profiles) <= 1000:
        raise ValueError("A lista deve conter de 1 a 1000 perfis.")
    if len({p.id for p in profiles}) != len(profiles):
        raise ValueError("Há identificadores de perfis duplicados.")
    write_json(path, {"version": 1, "profiles": [asdict(p.validate()) for p in profiles]})


def duplicate(profile):
    return replace(profile, id=str(uuid.uuid4()), loadout=profile.loadout[:190] + " (cópia)")
