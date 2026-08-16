"""Python mirror of single-stave geometry/physics hash recipes (#986).

Kept in sync with ``DetectorConstruction`` GEOMETRY_DIGEST_V2 / physics_v1 /
optical_v1. Used for fail-closed unit tests without requiring a Geant4 rebuild.
"""

from __future__ import annotations

import hashlib
from typing import Mapping

from ccb_mc_validation.provenance.geometry_digest import (
    SCHEMA_VERSION,
    canonical_payload,
    geometry_digest_hex,
)


def _fmt(x: float) -> str:
    # Match C++ CanonFloat / Python geometry_digest (.17g).
    return format(float(x), ".17g")


def _geometry_fields_from_nominal(params: Mapping[str, object]) -> dict[str, object]:
    fr = float(params["kFibreRadius_mm"])
    return {
        "schema_version": SCHEMA_VERSION,
        "stave_half_x_mm": float(params["kStaveHalfX_mm"]),
        "stave_half_y_mm": float(params["kStaveHalfY_mm"]),
        "stave_half_z_mm": float(params["kStaveHalfZ_mm"]),
        "coating_thk_mm": float(params["kCoatingThk_mm"]),
        "hole_radius_mm": float(params["kHoleRadius_mm"]),
        "fibre_radius_mm": fr,
        "fibre_half_x_mm": float(params["kFibreHalfX_mm"]),
        "fibre_sep_mm": float(params["kFibreSep_mm"]),
        "sensor_thk_mm": float(params["kSensorThk_mm"]),
        "fibre_core_radius_mm": fr * 0.94,
        "fibre_inner_clad_radius_mm": fr * 0.97,
        "fibre_outer_clad_radius_mm": fr * 1.00,
        "far_end_mode": str(params["far_end_mode"]),
    }


def geometry_v2_canonical(
    *,
    kStaveHalfX_mm: float,
    kStaveHalfY_mm: float,
    kStaveHalfZ_mm: float,
    kHoleRadius_mm: float,
    kFibreRadius_mm: float,
    kFibreHalfX_mm: float,
    kFibreSep_mm: float,
    rCore_mm: float,
    rInner_mm: float,
    rOuter_mm: float,
    kCoatingThk_mm: float,
    kSensorThk_mm: float,
    far_end_mode: str,
) -> str:
    """Return GEOMETRY_DIGEST_V2 canonical payload (legacy kw names)."""
    return canonical_payload(
        {
            "schema_version": SCHEMA_VERSION,
            "stave_half_x_mm": kStaveHalfX_mm,
            "stave_half_y_mm": kStaveHalfY_mm,
            "stave_half_z_mm": kStaveHalfZ_mm,
            "coating_thk_mm": kCoatingThk_mm,
            "hole_radius_mm": kHoleRadius_mm,
            "fibre_radius_mm": kFibreRadius_mm,
            "fibre_half_x_mm": kFibreHalfX_mm,
            "fibre_sep_mm": kFibreSep_mm,
            "sensor_thk_mm": kSensorThk_mm,
            "fibre_core_radius_mm": rCore_mm,
            "fibre_inner_clad_radius_mm": rInner_mm,
            "fibre_outer_clad_radius_mm": rOuter_mm,
            "far_end_mode": far_end_mode,
        }
    )


def physics_v1_canonical(
    *,
    birks_kB_mm_per_MeV: float,
    optical_interface_model: str,
    scintillator_material: str = "polystyrene_legacy",
    coating_material: str = "air_massless_placeholder",
    wls_mean_number_photons: float = 1.0,
    y11_direct_scint_yield_per_MeV: float = 0.0,
    tio2_finish: str = "ground",
    tio2_specular_lobe: float = 0.0,
    tio2_specular_spike: float = 0.0,
    tio2_backscatter: float = 0.0,
    y11_attenuation_form: str = "long_component_single_exponential",
) -> str:
    return (
        "schema=physics_v1"
        f";birks_kB_mm_per_MeV={_fmt(birks_kB_mm_per_MeV)}"
        f";optical_interface_model={optical_interface_model}"
        f";scintillator_material={scintillator_material}"
        f";coating_material={coating_material}"
        f";wls_mean_number_photons={_fmt(wls_mean_number_photons)}"
        f";y11_direct_scint_yield_per_MeV={_fmt(y11_direct_scint_yield_per_MeV)}"
        f";tio2_finish={tio2_finish}"
        f";tio2_specular_lobe={_fmt(tio2_specular_lobe)}"
        f";tio2_specular_spike={_fmt(tio2_specular_spike)}"
        f";tio2_backscatter={_fmt(tio2_backscatter)}"
        f";y11_attenuation_form={y11_attenuation_form}"
    )


def sha256_hex(canonical: str) -> str:
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def assert_birks_excluded_from_geometry(geo_a: str, geo_b: str) -> None:
    if geo_a != geo_b:
        raise AssertionError("geometry digest must be invariant to Birks-only changes")


def digests_for_nominal(overrides: Mapping[str, object] | None = None) -> dict[str, str]:
    """Nominal single-stave constants (mm) matching DetectorConstruction."""
    params: dict[str, object] = {
        "kStaveHalfX_mm": 250.0,
        "kStaveHalfY_mm": 25.9,
        "kStaveHalfZ_mm": 10.0,
        "kHoleRadius_mm": 1.0,
        "kFibreRadius_mm": 0.90,
        "kFibreHalfX_mm": 260.0,
        "kFibreSep_mm": 20.0,
        "kCoatingThk_mm": 0.25,
        "kSensorThk_mm": 0.10,
        "far_end_mode": "instrumented",
        "birks_kB_mm_per_MeV": 0.126,
        "optical_interface_model": "UNKNOWN_EXTERNAL",
    }
    if overrides:
        params.update(dict(overrides))
    geo_fields = _geometry_fields_from_nominal(params)
    geo = canonical_payload(geo_fields)
    phy = physics_v1_canonical(
        birks_kB_mm_per_MeV=float(params["birks_kB_mm_per_MeV"]),
        optical_interface_model=str(params["optical_interface_model"]),
        scintillator_material=str(params.get("scintillator_material", "polystyrene_legacy")),
        coating_material=str(params.get("coating_material", "air_massless_placeholder")),
        wls_mean_number_photons=float(params.get("wls_mean_number_photons", 1.0)),
        y11_direct_scint_yield_per_MeV=float(
            params.get("y11_direct_scint_yield_per_MeV", 0.0)
        ),
        tio2_finish=str(params.get("tio2_finish", "ground")),
        tio2_specular_lobe=float(params.get("tio2_specular_lobe", 0.0)),
        tio2_specular_spike=float(params.get("tio2_specular_spike", 0.0)),
        tio2_backscatter=float(params.get("tio2_backscatter", 0.0)),
        y11_attenuation_form=str(
            params.get("y11_attenuation_form", "long_component_single_exponential")
        ),
    )
    return {
        "geometry_canonical": geo,
        "physics_canonical": phy,
        "geometry_hash": geometry_digest_hex(geo_fields),
        "physics_hash": sha256_hex(phy),
    }
