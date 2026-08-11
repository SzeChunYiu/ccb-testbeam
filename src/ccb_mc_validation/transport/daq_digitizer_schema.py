"""Production DAQ digitizer schema gate (issue #1009 / AF-058).

Production data/MC waveform comparison requires a measured HRD transfer
function and the exact real DAQ clock/schema. Invented sample counts, clocks,
or CR-RC priors must not authorize production claims. See
``docs/adr/ADR-0004-daq-digitizer-measured-transfer.md``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ccb_mc_validation.exceptions import StudyBlockedError

SCHEMA_VERSION = "2026.0-waveB-lane06"
_REGISTRY = (
    Path(__file__).resolve().parents[3]
    / "configs"
    / "transport"
    / "daq_digitizer_registry.json"
)


def load_daq_digitizer_registry(path: Path | None = None) -> dict[str, Any]:
    p = path or _REGISTRY
    with p.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise StudyBlockedError("daq_digitizer_registry must be a mapping")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise StudyBlockedError(
            "daq_digitizer_registry schema_version mismatch: "
            f"got {data.get('schema_version')!r}, expected {SCHEMA_VERSION!r}"
        )
    return data


def authorize_production_daq_digitizer(
    config: Mapping[str, Any] | None,
    *,
    registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail closed unless a measured transfer-function binding is present.

    Returns a machine-readable authorization record. Production claims are
    never authorized when ``measured_transfer_function`` evidence is missing.
    """
    reg = dict(registry) if registry is not None else load_daq_digitizer_registry()
    cfg = dict(config or {})

    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "issue": 1009,
        "status": "BLOCKED",
        "claims_authorized": False,
        "reason": None,
        "legacy_parametric_bridges": list(reg.get("legacy_parametric_bridges", [])),
        "required_evidence": list(reg.get("required_evidence", [])),
    }

    schema_id = cfg.get("daq_digitizer_schema_id")
    if not schema_id:
        record["reason"] = (
            "daq_digitizer_schema_id unset; production waveform persistence "
            "and DAQ observation-grid sampling are BLOCKED pending measured "
            "HRD transfer function + resolved waveform contract (#952/#993)"
        )
        raise StudyBlockedError(record["reason"])

    schemas = reg.get("schemas") or {}
    if schema_id not in schemas:
        record["reason"] = f"unknown daq_digitizer_schema_id {schema_id!r}"
        raise StudyBlockedError(record["reason"])

    schema = dict(schemas[schema_id])
    record["schema_id"] = schema_id
    record["schema"] = schema

    if schema.get("status") != "APPROVED":
        record["status"] = str(schema.get("status", "BLOCKED"))
        record["reason"] = (
            f"schema {schema_id!r} status={schema.get('status')!r}; "
            "production authorization requires APPROVED measured transfer "
            "function evidence (ADR-0004)"
        )
        raise StudyBlockedError(record["reason"])

    tf = schema.get("measured_transfer_function") or {}
    digest = tf.get("evidence_digest")
    if not digest:
        record["reason"] = (
            f"schema {schema_id!r} lacks measured_transfer_function.evidence_digest"
        )
        raise StudyBlockedError(record["reason"])

    for key in ("n_channels", "samples_per_channel", "sample_interval_ns"):
        if key not in schema:
            record["reason"] = f"approved schema missing required field {key!r}"
            raise StudyBlockedError(record["reason"])
        if key in cfg and cfg[key] != schema[key]:
            record["reason"] = (
                f"caller override of {key}={cfg[key]!r} disagrees with measured "
                f"schema value {schema[key]!r}; invented clocks/grids are forbidden"
            )
            raise StudyBlockedError(record["reason"])

    record["status"] = "AUTHORIZED"
    record["claims_authorized"] = True
    record["reason"] = "measured transfer function bound"
    record["measured_transfer_function"] = tf
    return record
