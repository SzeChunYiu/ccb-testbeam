"""Python mirror of single-stave geometry/physics hash recipes (#986).

Kept in sync with ``DetectorConstruction`` schema geometry_v2 / physics_v1.
Used for fail-closed unit tests without requiring a Geant4 rebuild.
"""

from __future__ import annotations

import hashlib
from typing import Mapping


def _fmt(x: float) -> str:
    # Match C++ defaultfmt precision(17) stream for finite floats.
    return format(float(x), ".17g")


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
    return (
        "schema=geometry_v2"
        f";kStaveHalfX_mm={_fmt(kStaveHalfX_mm)}"
        f";kStaveHalfY_mm={_fmt(kStaveHalfY_mm)}"
        f";kStaveHalfZ_mm={_fmt(kStaveHalfZ_mm)}"
        f";kHoleRadius_mm={_fmt(kHoleRadius_mm)}"
        f";kFibreRadius_mm={_fmt(kFibreRadius_mm)}"
        f";kFibreHalfX_mm={_fmt(kFibreHalfX_mm)}"
        f";kFibreSep_mm={_fmt(kFibreSep_mm)}"
        f";rCore_mm={_fmt(rCore_mm)}"
        f";rInner_mm={_fmt(rInner_mm)}"
        f";rOuter_mm={_fmt(rOuter_mm)}"
        f";kCoatingThk_mm={_fmt(kCoatingThk_mm)}"
        f";kSensorThk_mm={_fmt(kSensorThk_mm)}"
        f";far_end_mode={far_end_mode}"
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
    fibre_r = 0.5  # mm? actually kFibreRadius is typically 0.5 mm — leave parametric
    # Use the same relative clad radii as C++ (0.94/0.97/1.00 * fibre radius).
    params = {
        "kStaveHalfX_mm": 250.0,   # 25 cm half-length
        "kStaveHalfY_mm": 25.9,    # 2.59 cm
        "kStaveHalfZ_mm": 10.0,    # 1.0 cm
        "kHoleRadius_mm": 1.0,
        "kFibreRadius_mm": 0.90,
        "kFibreHalfX_mm": 260.0,   # 26 cm
        "kFibreSep_mm": 20.0,      # 2 cm
        "kCoatingThk_mm": 0.25,
        "kSensorThk_mm": 0.10,
        "far_end_mode": "instrumented",
        "birks_kB_mm_per_MeV": 0.126,
        "optical_interface_model": "UNKNOWN_EXTERNAL",
    }
    if overrides:
        params.update(dict(overrides))
    fr = float(params["kFibreRadius_mm"])
    geo = geometry_v2_canonical(
        kStaveHalfX_mm=float(params["kStaveHalfX_mm"]),
        kStaveHalfY_mm=float(params["kStaveHalfY_mm"]),
        kStaveHalfZ_mm=float(params["kStaveHalfZ_mm"]),
        kHoleRadius_mm=float(params["kHoleRadius_mm"]),
        kFibreRadius_mm=fr,
        kFibreHalfX_mm=float(params["kFibreHalfX_mm"]),
        kFibreSep_mm=float(params["kFibreSep_mm"]),
        rCore_mm=fr * 0.94,
        rInner_mm=fr * 0.97,
        rOuter_mm=fr * 1.00,
        kCoatingThk_mm=float(params["kCoatingThk_mm"]),
        kSensorThk_mm=float(params["kSensorThk_mm"]),
        far_end_mode=str(params["far_end_mode"]),
    )
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
        "geometry_hash": sha256_hex(geo),
        "physics_hash": sha256_hex(phy),
    }
