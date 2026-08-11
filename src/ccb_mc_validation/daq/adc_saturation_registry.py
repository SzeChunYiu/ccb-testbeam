"""ADC saturation-world registry (#1073) — fail-closed until resolved.

Three incompatible "worlds" currently exist in the repository:

* World A (S00 v1): treats stored waveforms as 14-bit codes with full-scale 16383
  and labels that ceiling as "CAEN V1742 hardware saturation".
* World B (CAEN V1742 catalogue): native 12-bit DRS4 digitizer, domain 0..4095.
* World C (MC digitizer / academic chapters): adc_bits=14 with adc_ceiling=7000,
  often described as a SAMPIC or empirical clip.

These cannot all be the same native ADC contract. Until a source-bound transfer
function is recovered (#1014), authorising saturation thresholds MUST NOT be
chosen by preference among {4095, 7000, 16383}.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SCHEMA = "ccb-adc-saturation-world-registry/1"
STATUS_UNRESOLVED = "UNRESOLVED_CROSS_LAYER_CONTRADICTION"
STATUS_BLOCKED = "BLOCKED_HARDWARE_EVIDENCE"


@dataclass(frozen=True)
class SaturationWorld:
    world_id: str
    label: str
    code_domain_max: int | None
    claimed_bits: int | None
    claimed_hardware: str
    sources: tuple[str, ...]
    status: str
    notes: str


WORLDS: tuple[SaturationWorld, ...] = (
    SaturationWorld(
        world_id="A",
        label="S00_v1_14bit_16383",
        code_domain_max=16383,
        claimed_bits=14,
        claimed_hardware="CAEN V1742 (claimed 14-bit in S00 comment)",
        sources=("scripts/01_build_pulse_table_from_root.py",),
        status=STATUS_UNRESOLVED,
        notes=(
            "S00 historically flagged saturation at max(code) >= 16383 and "
            "attributed it to V1742."
        ),
    ),
    SaturationWorld(
        world_id="B",
        label="CAEN_V1742_catalogue_12bit",
        code_domain_max=4095,
        claimed_bits=12,
        claimed_hardware="CAEN V1742 / DRS4 (official catalogue)",
        sources=(
            "https://caen.it/products/v1742/",
            "docs/academic_chapters/02_experimental_setup.md",
        ),
        status=STATUS_UNRESOLVED,
        notes=(
            "Official V1742 is 12-bit; native unsigned domain is 0..4095 "
            "unless a transform exists."
        ),
    ),
    SaturationWorld(
        world_id="C",
        label="MC_digitizer_ceiling_7000",
        code_domain_max=7000,
        claimed_bits=14,
        claimed_hardware="parametric MC / chapter prose (SAMPIC or empirical)",
        sources=(
            "src/ccb_mc_validation/digitizer/electronics.py",
            "docs/academic_chapters/02_experimental_setup.md",
            "docs/academic_chapters/03_data_pipeline.md",
        ),
        status=STATUS_UNRESOLVED,
        notes=(
            "MC clips at min(adc_ceiling=7000, 2**adc_bits-1). Chapter 2 also "
            "cites ~7000 as an observed high-amplitude region."
        ),
    ),
)


class AdcSaturationContractError(RuntimeError):
    """Raised when an authorising consumer asks for an unresolved saturation threshold."""


def registry_snapshot() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "issue": 1073,
        "parent_issue": 1014,
        "status": STATUS_BLOCKED,
        "authorising_threshold": None,
        "reason": (
            "No source-bound analog→code transfer function reconciles Worlds A/B/C. "
            "Do not invent a hardware model; keep saturation-dependent claims "
            "non-authorising."
        ),
        "worlds": [
            {
                "world_id": w.world_id,
                "label": w.label,
                "code_domain_max": w.code_domain_max,
                "claimed_bits": w.claimed_bits,
                "claimed_hardware": w.claimed_hardware,
                "sources": list(w.sources),
                "status": w.status,
                "notes": w.notes,
            }
            for w in WORLDS
        ],
    }


def authorising_saturation_threshold() -> int:
    """Fail-closed: no authorising saturation threshold until the registry is resolved."""
    snap = registry_snapshot()
    raise AdcSaturationContractError(
        f"ADC saturation registry status={snap['status']}: {snap['reason']} "
        f"(issue #{snap['issue']})."
    )


def diagnostic_saturation_flag(peak_code_adc, *, world_id: str = "A"):
    """Non-authorising diagnostic flag under an explicitly named unresolved world.

    Callers must treat the result as a sensitivity/diagnostic column, never as a
    hardware-proven saturation claim.
    """
    import numpy as np

    world = {w.world_id: w for w in WORLDS}.get(world_id)
    if world is None or world.code_domain_max is None:
        raise AdcSaturationContractError(f"unknown saturation world_id={world_id!r}")
    arr = np.asarray(peak_code_adc)
    return arr >= int(world.code_domain_max), {
        "world_id": world.world_id,
        "label": world.label,
        "threshold": world.code_domain_max,
        "authorising": False,
        "registry_status": STATUS_BLOCKED,
        "issue": 1073,
    }
