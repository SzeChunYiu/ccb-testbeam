"""Notation and equation registry for MC-validation publication/wiki drafts."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ccb_mc_validation.io.artifact_store import atomic_write_json

NOTATION_RECORDS = [
    {
        "id": "EQ-PID-EFF",
        "symbol": r"\\epsilon(t)",
        "latex": r"\\epsilon(t)=N_{\\mathrm{true\\,signal}}(s(x)\\ge t)/N_{\\mathrm{true\\,signal}}",
        "meaning": "Signal efficiency at score threshold t.",
        "scope": "MV1 artifact-summary interpretation",
    },
    {
        "id": "EQ-PID-PURITY",
        "symbol": "P(t)",
        "latex": r"P(t)=N_{\\mathrm{true\\,signal}}(s(x)\\ge t)/N_{\\mathrm{selected}}(s(x)\\ge t)",
        "meaning": "Purity among selected candidates at score threshold t.",
        "scope": "MV1 artifact-summary interpretation",
    },
    {
        "id": "EQ-R68",
        "symbol": "R_68",
        "latex": r"R_{68}=\\frac{1}{2}(Q_{84}[r]-Q_{16}[r])",
        "meaning": "Robust central 68% residual scale.",
        "scope": "MV2 artifact-summary interpretation",
    },
    {
        "id": "EQ-ERESID",
        "symbol": "r",
        "latex": r"r=(E_{\\mathrm{reco}}-E_{\\mathrm{truth}})/E_{\\mathrm{truth}}",
        "meaning": "Relative reconstructed-energy residual.",
        "scope": "MV2 artifact-summary interpretation",
    },
    {
        "id": "EQ-STOP-SUPPORT",
        "symbol": r"N_{\\mathrm{Sample\\,I}}, N_{\\mathrm{Sample\\,II}}",
        "latex": r"N_{\\mathrm{Sample\\,I}},\\;N_{\\mathrm{Sample\\,II}}",
        "meaning": "Frozen support counts for stopping-depth samples.",
        "scope": "MV3 artifact-summary interpretation",
    },
]


def generate_notation_registry(run_root: Path) -> dict[str, Any]:
    """Write notation/equation registry artifacts."""
    run_root = Path(run_root)
    out_dir = run_root / "reports" / "mc_validation" / "notation"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "status": "PASS",
        "scope": "notation-registry",
        "final_notation_status": "DRAFT",
        "records": NOTATION_RECORDS,
        "record_count": len(NOTATION_RECORDS),
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    atomic_write_json(out_dir / "NOTATION_REGISTRY.json", payload)
    lines = [
        "# MC validation notation and equation registry",
        "",
        f"- **Status:** `{payload['status']}`",
        f"- **Final notation status:** `{payload['final_notation_status']}`",
        f"- **Record count:** `{payload['record_count']}`",
        "",
        "| ID | Symbol | Equation | Meaning | Scope |",
        "|---|---|---|---|---|",
    ]
    for record in NOTATION_RECORDS:
        lines.append(
            f"| {record['id']} | `{record['symbol']}` | `${record['latex']}$ | {record['meaning']} | {record['scope']} |"
        )
    (out_dir / "NOTATION_REGISTRY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload
