"""Birks kB hypothesis registry (issue #1079)."""
from __future__ import annotations

from typing import Any, Mapping, Optional

HYPOTHESES: dict[str, dict[str, Any]] = {
    "H1_NO_QUENCHING": {
        "k_b_mm_per_MeV": 0.0,
        "k_b_cm_per_mev": 0.0,
        "status": "HISTORICAL_PROSE_HYPOTHESIS",
        "source": "chapter10_mv0_operational_scan_endpoint",
    },
    "H2_PYTHON_DIGITIZER_LEGACY_DEFAULT": {
        "k_b_mm_per_MeV": 0.08,
        "k_b_cm_per_mev": 0.008,
        "status": "PYTHON_FUNCTION_DEFAULT_WHEN_UNSPECIFIED",
        "source": "src/ccb_mc_validation/digitizer/birks.py::birks_quench default",
    },
    "H3_GEANT4_SINGLE_STAVE_DEFAULT": {
        "k_b_mm_per_MeV": 0.126,
        "k_b_cm_per_mev": 0.0126,
        "status": "GEANT4_APPCONFIG_DEFAULT",
        "source": "geant4/single_stave/include/AppConfig.hh",
    },
}


class BirksContractError(ValueError):
    """Fail-closed Birks parameter contract violation."""


def hypothesis_for_k_b_cm_per_mev(k_b_cm_per_mev: float, *, rtol: float = 1e-9) -> Optional[str]:
    kb = float(k_b_cm_per_mev)
    for hid, meta in HYPOTHESES.items():
        ref = float(meta["k_b_cm_per_mev"])
        if abs(kb - ref) <= rtol * max(1.0, abs(ref)):
            return hid
    return None


def require_explicit_k_b(
    *,
    apply_birks: bool,
    k_b_cm_per_mev: Optional[float],
    hypothesis_id: Optional[str] = None,
) -> dict[str, Any]:
    if not apply_birks:
        return {
            "apply_birks": False,
            "k_b_cm_per_mev": 0.0,
            "hypothesis_id": "H1_NO_QUENCHING",
            "status": "BIRKS_DISABLED",
        }
    kb: Optional[float] = None
    hid = hypothesis_id
    if hid is not None:
        if hid not in HYPOTHESES:
            raise BirksContractError(
                f"unknown Birks hypothesis_id {hid!r}; known={sorted(HYPOTHESES)}"
            )
        kb = float(HYPOTHESES[hid]["k_b_cm_per_mev"])
        if k_b_cm_per_mev is not None and abs(float(k_b_cm_per_mev) - kb) > 1e-12:
            raise BirksContractError(
                f"k_b_cm_per_mev={k_b_cm_per_mev!r} disagrees with hypothesis {hid} value {kb}"
            )
    elif k_b_cm_per_mev is not None:
        kb = float(k_b_cm_per_mev)
        if kb != kb or kb < 0.0:
            raise BirksContractError(
                f"k_b_cm_per_mev must be finite and >=0, got {k_b_cm_per_mev!r}"
            )
        hid = hypothesis_for_k_b_cm_per_mev(kb) or "H_CUSTOM_EXPLICIT"
    else:
        raise BirksContractError(
            "apply_birks=True requires explicit birks_k_b_cm_per_mev or "
            "birks_hypothesis_id; silent use of the Python 0.008 cm/MeV default "
            "is forbidden (issue #1079)"
        )
    assert kb is not None
    return {
        "apply_birks": True,
        "k_b_cm_per_mev": float(kb),
        "k_b_mm_per_MeV": float(kb) * 10.0,
        "hypothesis_id": hid,
        "status": "EXPLICIT_PARAMETER",
        "canonical_default": False,
        "note": (
            "H1/H2/H3 remain distinct hypotheses; none is promoted to a single "
            "production truth by this contract"
        ),
    }


def assert_worlds_remain_distinct(registry: Mapping[str, Mapping[str, Any]] = HYPOTHESES) -> None:
    vals = [
        float(registry[k]["k_b_cm_per_mev"])
        for k in (
            "H1_NO_QUENCHING",
            "H2_PYTHON_DIGITIZER_LEGACY_DEFAULT",
            "H3_GEANT4_SINGLE_STAVE_DEFAULT",
        )
    ]
    if len(set(vals)) != 3:
        raise BirksContractError("Birks hypothesis kB values collapsed")
