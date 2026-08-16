"""Canonical geometry vs physics provenance digests (issue #986)."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

GEOMETRY_SCHEMA = "geometry_config_v1"
PHYSICS_SCHEMA = "physics_config_v1"


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_hex(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def geometry_config_payload(
    *,
    stave_half_x_mm: float,
    stave_half_y_mm: float,
    stave_half_z_mm: float,
    hole_radius_mm: float,
    fibre_radius_mm: float,
    fibre_half_x_mm: float,
    fibre_sep_mm: float,
    coating_thk_mm: float,
    sensor_thk_mm: float,
    far_end_mode: str,
    fibre_core_frac: float = 0.94,
    fibre_inner_frac: float = 0.97,
    fibre_outer_frac: float = 1.00,
) -> dict[str, Any]:
    r_core = fibre_radius_mm * fibre_core_frac
    r_inner = fibre_radius_mm * fibre_inner_frac
    r_outer = fibre_radius_mm * fibre_outer_frac
    return {
        "schema": GEOMETRY_SCHEMA,
        "units": {"length": "mm"},
        "stave_half_x_mm": float(stave_half_x_mm),
        "stave_half_y_mm": float(stave_half_y_mm),
        "stave_half_z_mm": float(stave_half_z_mm),
        "hole_radius_mm": float(hole_radius_mm),
        "fibre_radius_mm": float(fibre_radius_mm),
        "fibre_half_x_mm": float(fibre_half_x_mm),
        "fibre_sep_mm": float(fibre_sep_mm),
        "fibre_core_radius_mm": float(r_core),
        "fibre_inner_clad_radius_mm": float(r_inner),
        "fibre_outer_radius_mm": float(r_outer),
        "coating_thk_mm": float(coating_thk_mm),
        "sensor_thk_mm": float(sensor_thk_mm),
        "far_end_mode": str(far_end_mode),
    }


def physics_config_payload(
    *,
    birks_kB_mm_per_MeV: float,
    optical_interface_model: str,
    production_cut_mm: float | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "schema": PHYSICS_SCHEMA,
        "units": {"birks_kB": "mm/MeV", "production_cut": "mm"},
        "birks_kB_mm_per_MeV": float(birks_kB_mm_per_MeV),
        "optical_interface_model": str(optical_interface_model),
    }
    if production_cut_mm is not None:
        out["production_cut_mm"] = float(production_cut_mm)
    return out


def geometry_config_sha256(**kwargs: Any) -> str:
    return sha256_hex(geometry_config_payload(**kwargs))


def physics_config_sha256(**kwargs: Any) -> str:
    return sha256_hex(physics_config_payload(**kwargs))
