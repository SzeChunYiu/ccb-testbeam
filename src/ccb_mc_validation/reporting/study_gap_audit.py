"""Study implementation readiness audit for recursive MC-validation closure."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ccb_mc_validation.io.artifact_store import atomic_write_json

STUDY_GAPS: list[dict[str, Any]] = [
    {
        "study": "MV4",
        "module": "ccb_mc_validation.studies.mv4_timing",
        "status": "BLOCKED",
        "current_state": "timing study placeholder / requires MV0 digitizer readiness and production timing artifacts",
        "required_next_artifact": "reports/mc_validation/systematics/MV4_TIMING_UNCERTAINTIES.json",
    },
    {
        "study": "MV5",
        "module": "ccb_mc_validation.studies.mv5_pileup",
        "status": "BLOCKED",
        "current_state": "pile-up overlay skeleton / requires controlled mixture lineage and recovery diagnostics",
        "required_next_artifact": "reports/mc_validation/pileup/MV5_RECOVERY_DIAGNOSTICS.json",
    },
    {
        "study": "MV6",
        "module": "ccb_mc_validation.studies.mv6_representation",
        "status": "BLOCKED",
        "current_state": "representation comparison skeleton / requires nuisance-leakage-safe waveform comparison",
        "required_next_artifact": "reports/mc_validation/representations/MV6_REPRESENTATION_COMPARISON.json",
    },
    {
        "study": "MV7",
        "module": "ccb_mc_validation.studies.mv7_pedestal",
        "status": "BLOCKED",
        "current_state": "pedestal/noise closure skeleton / requires held-out channel diagnostics",
        "required_next_artifact": "reports/mc_validation/noise/MV7_PEDESTAL_NOISE_CLOSURE.json",
    },
    {
        "study": "MV8",
        "module": "ccb_mc_validation.studies.mv8_saturation",
        "status": "BLOCKED",
        "current_state": "saturation/dynamic-range skeleton / requires failure accounting and dynamic-range scan",
        "required_next_artifact": "reports/mc_validation/saturation/MV8_DYNAMIC_RANGE_SCAN.json",
    },
]


def generate_study_gap_audit(run_root: Path) -> dict[str, Any]:
    """Write a fail-closed MV4-MV8 implementation readiness audit."""
    run_root = Path(run_root)
    out_dir = run_root / "reports" / "mc_validation" / "open_questions"
    out_dir.mkdir(parents=True, exist_ok=True)
    blocked = [gap for gap in STUDY_GAPS if gap["status"] != "READY"]
    payload: dict[str, Any] = {
        "status": "PASS",
        "scope": "study-implementation-gap-audit",
        "all_study_implementations_ready": len(blocked) == 0,
        "blocked_count": len(blocked),
        "studies": STUDY_GAPS,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    atomic_write_json(out_dir / "STUDY_IMPLEMENTATION_GAP_AUDIT.json", payload)
    lines = [
        "# Study implementation gap audit",
        "",
        f"- **All study implementations ready:** `{payload['all_study_implementations_ready']}`",
        f"- **Blocked count:** `{payload['blocked_count']}`",
        "",
        "| Study | Status | Module | Current state | Required next artifact |",
        "|---|---:|---|---|---|",
    ]
    for gap in STUDY_GAPS:
        lines.append(
            f"| {gap['study']} | {gap['status']} | `{gap['module']}` | {gap['current_state']} | `{gap['required_next_artifact']}` |"
        )
    lines.extend([
        "",
        "## Guardrail",
        "",
        "This audit is a readiness map, not physics evidence. A study can move from `BLOCKED` to `READY` only when its production implementation writes the required artifacts and release QA/claim-ledger gates are updated.",
    ])
    (out_dir / "STUDY_IMPLEMENTATION_GAP_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload
