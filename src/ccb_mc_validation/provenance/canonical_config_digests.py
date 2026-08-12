"""Canonical separated config digests (issue #986).

Geometry, optical, physics/response and digitizer configuration are distinct
provenance atoms. A single overloaded geometry hash that mixes Birks into
solid dimensions is not an authorising geometry identity.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

GEOMETRY_DIGEST_SCHEMA = "ccb-geometry-config-digest/v1"
OPTICAL_DIGEST_SCHEMA = "ccb-optical-config-digest/v1"
PHYSICS_DIGEST_SCHEMA = "ccb-physics-config-digest/v1"
DIGITIZER_DIGEST_SCHEMA = "ccb-digitizer-config-digest/v1"


def _canon_float(value: float) -> str:
    """Deterministic float text (17 significant digits, no locale)."""
    x = float(value)
    if x != x:  # NaN
        raise ValueError("NaN is not allowed in canonical digests")
    if x == float("inf") or x == float("-inf"):
        raise ValueError("non-finite float is not allowed in canonical digests")
    return format(x, ".17g")


def canonical_digest_bytes(payload: Mapping[str, Any]) -> bytes:
    """Serialize sorted field names with explicit typed values to UTF-8 bytes."""
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode(
        "utf-8"
    )


def sha256_hex(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_digest_bytes(payload)).hexdigest()


def geometry_config_payload(
    *,
    stave_half_x_mm: float,
    stave_half_y_mm: float,
    stave_half_z_mm: float,
    hole_radius_mm: float,
    fibre_radius_mm: float,
    fibre_half_x_mm: float,
    fibre_sep_mm: float,
    fibre_core_radius_mm: float,
    fibre_inner_clad_radius_mm: float,
    fibre_outer_radius_mm: float,
    coating_thickness_mm: float,
    sensor_thickness_mm: float,
    far_end_mode: str,
    schema_version: str = GEOMETRY_DIGEST_SCHEMA,
) -> dict[str, Any]:
    mode = str(far_end_mode)
    if not mode:
        raise ValueError("far_end_mode must be a non-empty string")
    return {
        "schema_version": schema_version,
        "coating_thickness_mm": _canon_float(coating_thickness_mm),
        "far_end_mode": mode,
        "fibre_core_radius_mm": _canon_float(fibre_core_radius_mm),
        "fibre_half_x_mm": _canon_float(fibre_half_x_mm),
        "fibre_inner_clad_radius_mm": _canon_float(fibre_inner_clad_radius_mm),
        "fibre_outer_radius_mm": _canon_float(fibre_outer_radius_mm),
        "fibre_radius_mm": _canon_float(fibre_radius_mm),
        "fibre_sep_mm": _canon_float(fibre_sep_mm),
        "hole_radius_mm": _canon_float(hole_radius_mm),
        "sensor_thickness_mm": _canon_float(sensor_thickness_mm),
        "stave_half_x_mm": _canon_float(stave_half_x_mm),
        "stave_half_y_mm": _canon_float(stave_half_y_mm),
        "stave_half_z_mm": _canon_float(stave_half_z_mm),
    }


def geometry_config_sha256(**kwargs: Any) -> str:
    return sha256_hex(geometry_config_payload(**kwargs))


def physics_config_payload(
    *,
    birks_kB_mm_per_MeV: float,
    production_cut_mm: float,
    optical_interface_model: str,
    schema_version: str = PHYSICS_DIGEST_SCHEMA,
) -> dict[str, Any]:
    model = str(optical_interface_model)
    if not model:
        raise ValueError("optical_interface_model must be a non-empty string")
    return {
        "schema_version": schema_version,
        "birks_kB_mm_per_MeV": _canon_float(birks_kB_mm_per_MeV),
        "optical_interface_model": model,
        "production_cut_mm": _canon_float(production_cut_mm),
    }


def physics_config_sha256(**kwargs: Any) -> str:
    return sha256_hex(physics_config_payload(**kwargs))


def optical_config_payload(
    *,
    table_sha256_by_name: Mapping[str, str],
    schema_version: str = OPTICAL_DIGEST_SCHEMA,
) -> dict[str, Any]:
    tables = {str(k): str(v) for k, v in sorted(table_sha256_by_name.items())}
    if any(not v for v in tables.values()):
        raise ValueError("optical table digests must be non-empty")
    return {"schema_version": schema_version, "tables": tables}


def optical_config_sha256(**kwargs: Any) -> str:
    return sha256_hex(optical_config_payload(**kwargs))


def digitizer_config_payload(
    *,
    resolved_stages: list[str],
    apply_birks: bool,
    birks_kB_mm_per_MeV: float | None,
    n_samples: int,
    sample_spacing_ns: float,
    gain_adc_per_mev: float,
    noise_adc_rms: float,
    pedestal_adc: float,
    schema_version: str = DIGITIZER_DIGEST_SCHEMA,
) -> dict[str, Any]:
    if not resolved_stages:
        raise ValueError("resolved_stages must be non-empty")
    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "apply_birks": bool(apply_birks),
        "gain_adc_per_mev": _canon_float(gain_adc_per_mev),
        "n_samples": int(n_samples),
        "noise_adc_rms": _canon_float(noise_adc_rms),
        "pedestal_adc": _canon_float(pedestal_adc),
        "resolved_stages": list(resolved_stages),
        "sample_spacing_ns": _canon_float(sample_spacing_ns),
    }
    if apply_birks:
        if birks_kB_mm_per_MeV is None:
            raise ValueError("birks_kB_mm_per_MeV required when apply_birks is true")
        payload["birks_kB_mm_per_MeV"] = _canon_float(birks_kB_mm_per_MeV)
    else:
        payload["birks_kB_mm_per_MeV"] = None
    return payload


def digitizer_config_sha256(**kwargs: Any) -> str:
    return sha256_hex(digitizer_config_payload(**kwargs))
