"""Truth-type-specific ADC/MeV quantity dictionary (#994)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from ccb_mc_validation.exceptions import ConfigurationError, DataContractError

DICTIONARY_VERSION: str = "2026.0-waveB-lane05"
_DICT_REL = Path("configs/response/quantities/adc_mev_quantity_dictionary.yaml")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class AdcMevQuantity:
    quantity_id: str
    short_label: str
    domain: str
    input_energy_type: str
    output_adc_definition: str
    estimator: str
    nominal_value: float | None
    unit: str
    claims_authorized: bool
    raw: dict[str, Any]

    @property
    def truth_type_key(self) -> tuple[str, str, str]:
        return (self.domain, self.input_energy_type, self.estimator)


def load_adc_mev_dictionary(repo_root: Path | None = None) -> dict[str, AdcMevQuantity]:
    root = repo_root if repo_root is not None else _repo_root()
    path = (root / _DICT_REL).resolve()
    if not path.is_file():
        raise ConfigurationError(f"ADC/MeV quantity dictionary missing: {path}")
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ConfigurationError(f"ADC/MeV dictionary is not a mapping: {path}")
    if data.get("schema") != "ccb-adc-mev-quantity-dictionary/1":
        raise ConfigurationError(
            f"unsupported ADC/MeV dictionary schema: {data.get('schema')!r}"
        )
    if data.get("dictionary_version") != DICTIONARY_VERSION:
        raise ConfigurationError(
            f"ADC/MeV dictionary_version mismatch: file has "
            f"{data.get('dictionary_version')!r}, code expects {DICTIONARY_VERSION!r}"
        )
    out: dict[str, AdcMevQuantity] = {}
    for entry in data.get("quantities", []):
        qid = str(entry["quantity_id"])
        out[qid] = AdcMevQuantity(
            quantity_id=qid,
            short_label=str(entry["short_label"]),
            domain=str(entry["domain"]),
            input_energy_type=str(entry["input_energy_type"]),
            output_adc_definition=str(entry["output_adc_definition"]),
            estimator=str(entry["estimator"]),
            nominal_value=(
                float(entry["nominal_value"])
                if entry.get("nominal_value") is not None
                else None
            ),
            unit=str(entry.get("unit", "ADC/MeV")),
            claims_authorized=bool(entry.get("claims_authorized", False)),
            raw=dict(entry),
        )
    return out


def require_quantity(
    quantity_id: str, *, repo_root: Path | None = None
) -> AdcMevQuantity:
    if not quantity_id:
        raise ConfigurationError(
            "adc_mev quantity_id is unset. Ambiguous 'gain'/'ADC/MeV' labels are "
            "forbidden (#994). Choose a registered quantity_id from "
            "configs/response/quantities/adc_mev_quantity_dictionary.yaml."
        )
    table = load_adc_mev_dictionary(repo_root)
    if quantity_id not in table:
        known = ", ".join(sorted(table)) or "(none)"
        raise ConfigurationError(
            f"unknown adc_mev quantity_id {quantity_id!r}; registered: {known}"
        )
    return table[quantity_id]


def assert_public_short_labels_compatible(
    quantity_ids: Iterable[str], *, repo_root: Path | None = None
) -> None:
    """Fail if distinct truth types share one public short_label (#994)."""
    table = load_adc_mev_dictionary(repo_root)
    by_label: dict[str, list[AdcMevQuantity]] = {}
    for qid in quantity_ids:
        if qid not in table:
            raise ConfigurationError(f"unknown adc_mev quantity_id {qid!r}")
        q = table[qid]
        by_label.setdefault(q.short_label, []).append(q)
    for label, qs in by_label.items():
        truth_keys = {q.truth_type_key for q in qs}
        if len(truth_keys) > 1:
            ids = [q.quantity_id for q in qs]
            raise DataContractError(
                f"public short_label {label!r} is shared by incompatible truth "
                f"types ({ids}); attach distinct labels or quantity_ids (#994)"
            )
