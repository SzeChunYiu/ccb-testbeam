"""Reference registry for MC-validation publication/wiki drafts."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ccb_mc_validation.io.artifact_store import atomic_write_json

REFERENCE_RECORDS = [
    {
        "id": "REF-RUNBOOK",
        "type": "project-specification",
        "title": "CCB testbeam Codex MC validation completion thesis runbook",
        "citation": "Project runbook supplied with this repository session; governs execution, reporting, thesis, and release requirements.",
        "status": "AVAILABLE",
        "note": "Local operator-provided specification, not an external literature source.",
    },
    {
        "id": "REF-VALIDATION-ARTIFACTS",
        "type": "frozen-artifact",
        "title": "Selected LUNARC MC validation artifacted run",
        "citation": "Run 20260625T064500Z_full_input_artifacted, job 3316536, frozen validation artifacts under the configured LUNARC artifact root.",
        "status": "AVAILABLE",
        "note": "Primary evidence for current MV1-MV3/MV9 artifact-summary claims.",
    },
    {
        "id": "REF-FINAL-LITERATURE-CURATION",
        "type": "literature-placeholder",
        "title": "Final detector/MC/statistical-method references",
        "citation": "To be curated before final publication-grade wiki/thesis release.",
        "status": "BLOCKED",
        "note": "Do not invent references; final bibliography remains a release blocker.",
    },
]


def generate_reference_registry(run_root: Path) -> dict[str, Any]:
    """Write JSON and Markdown reference registry artifacts."""
    run_root = Path(run_root)
    out_dir = run_root / "reports" / "mc_validation" / "references"
    out_dir.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(tz=timezone.utc).isoformat()
    blocked = [record for record in REFERENCE_RECORDS if record["status"] != "AVAILABLE"]
    payload: dict[str, Any] = {
        "status": "PASS",
        "scope": "reference-registry",
        "final_bibliography_status": "BLOCKED" if blocked else "PASS",
        "records": REFERENCE_RECORDS,
        "blocked_count": len(blocked),
        "generated_at": generated,
    }
    atomic_write_json(out_dir / "REFERENCE_REGISTRY.json", payload)
    lines = [
        "# MC validation reference registry",
        "",
        f"- **Status:** `{payload['status']}`",
        f"- **Final bibliography:** `{payload['final_bibliography_status']}`",
        f"- **Blocked reference count:** `{payload['blocked_count']}`",
        "",
        "| ID | Type | Status | Citation | Note |",
        "|---|---|---:|---|---|",
    ]
    for record in REFERENCE_RECORDS:
        lines.append(
            f"| {record['id']} | {record['type']} | {record['status']} | {record['citation']} | {record['note']} |"
        )
    (out_dir / "REFERENCE_REGISTRY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload
