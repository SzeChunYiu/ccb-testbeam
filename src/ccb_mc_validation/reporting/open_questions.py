"""Open-question registry for recursive MC-validation study closure."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ccb_mc_validation.io.artifact_store import atomic_write_json

QUESTION_RECORDS = [
    {"id": "OQ-MV4", "status": "OPEN", "priority": "high", "question": "Can calibrated digitized MC validate timing observables without truth leakage?", "needed_evidence": "MV4 production artifact, uncertainty intervals, and acceptance decision."},
    {"id": "OQ-MV5", "status": "OPEN", "priority": "high", "question": "How robust is pile-up detection/reconstruction under controlled mixture lineage?", "needed_evidence": "MV5 production artifact and pile-up recovery diagnostics."},
    {"id": "OQ-MV6", "status": "OPEN", "priority": "medium", "question": "Which waveform representations preserve physics information without nuisance leakage?", "needed_evidence": "MV6 representation comparison and probe results."},
    {"id": "OQ-MV7", "status": "OPEN", "priority": "high", "question": "Do pedestal/noise models match held-out data sufficiently for MC validation?", "needed_evidence": "MV7 pedestal/noise closure with per-channel diagnostics."},
    {"id": "OQ-MV8", "status": "OPEN", "priority": "high", "question": "Where do saturation and dynamic-range effects invalidate reconstruction claims?", "needed_evidence": "MV8 saturation/dynamic-range study and failure accounting."},
    {"id": "OQ-SYS", "status": "OPEN", "priority": "high", "question": "How large are generator, detector, and electronics systematic envelopes?", "needed_evidence": "LUNARC systematic arrays with paired shifts and uncertainty decomposition."},
    {"id": "OQ-WIKI", "status": "OPEN", "priority": "medium", "question": "Are final citations, references, plots, and discussion complete enough for a publication-grade GitHub wiki?", "needed_evidence": "Release-ready wiki publication with curated bibliography and all QA gates passing."},
]


def generate_open_question_registry(run_root: Path) -> dict[str, Any]:
    """Write open-question registry artifacts."""
    run_root = Path(run_root)
    out_dir = run_root / "reports" / "mc_validation" / "open_questions"
    out_dir.mkdir(parents=True, exist_ok=True)
    open_records = [record for record in QUESTION_RECORDS if record["status"] != "CLOSED"]
    payload: dict[str, Any] = {
        "status": "PASS",
        "scope": "open-question-registry",
        "all_questions_closed": len(open_records) == 0,
        "open_count": len(open_records),
        "records": QUESTION_RECORDS,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    atomic_write_json(out_dir / "OPEN_QUESTIONS.json", payload)
    lines = [
        "# MC validation open-question registry",
        "",
        f"- **All questions closed:** `{payload['all_questions_closed']}`",
        f"- **Open count:** `{payload['open_count']}`",
        "",
        "| ID | Status | Priority | Question | Needed evidence |",
        "|---|---:|---:|---|---|",
    ]
    for record in QUESTION_RECORDS:
        lines.append(f"| {record['id']} | {record['status']} | {record['priority']} | {record['question']} | {record['needed_evidence']} |")
    (out_dir / "OPEN_QUESTIONS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload
