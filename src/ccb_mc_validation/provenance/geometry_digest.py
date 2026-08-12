"""Canonical GEOMETRY_DIGEST_V2 helper (#986)."""
from __future__ import annotations

import hashlib
from typing import Mapping

SCHEMA_VERSION = "2.0.0"
FIELD_ORDER = (
    "schema_version",
    "stave_half_x_mm",
    "stave_half_y_mm",
    "stave_half_z_mm",
    "coating_thk_mm",
    "hole_radius_mm",
    "fibre_radius_mm",
    "fibre_half_x_mm",
    "fibre_sep_mm",
    "sensor_thk_mm",
    "fibre_core_radius_mm",
    "fibre_inner_clad_radius_mm",
    "fibre_outer_clad_radius_mm",
    "far_end_mode",
)


def format_float(value: float) -> str:
    return format(float(value), ".17g")


def canonical_payload(fields: Mapping[str, object]) -> str:
    missing = [k for k in FIELD_ORDER if k not in fields]
    if missing:
        raise ValueError(f"geometry digest missing fields: {missing}")
    parts: list[str] = []
    for key in FIELD_ORDER:
        val = fields[key]
        if key == "schema_version" or key == "far_end_mode":
            parts.append(f"{key}={val}")
        else:
            parts.append(f"{key}={format_float(float(val))}")
    return ";".join(parts)


def geometry_digest_hex(fields: Mapping[str, object]) -> str:
    payload = canonical_payload(fields)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def default_single_stave_fields(*, far_end_mode: str = "instrumented") -> dict[str, object]:
    """Mirror DetectorConstruction constants (mm)."""
    fibre_radius_mm = 0.90
    return {
        "schema_version": SCHEMA_VERSION,
        "stave_half_x_mm": 250.0,
        "stave_half_y_mm": 25.9,
        "stave_half_z_mm": 10.0,
        "coating_thk_mm": 0.25,
        "hole_radius_mm": 1.0,
        "fibre_radius_mm": fibre_radius_mm,
        "fibre_half_x_mm": 260.0,
        "fibre_sep_mm": 20.0,
        "sensor_thk_mm": 0.10,
        "fibre_core_radius_mm": fibre_radius_mm * 0.94,
        "fibre_inner_clad_radius_mm": fibre_radius_mm * 0.97,
        "fibre_outer_clad_radius_mm": fibre_radius_mm * 1.00,
        "far_end_mode": far_end_mode,
    }
