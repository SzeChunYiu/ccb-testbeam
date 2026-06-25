"""Per-open-question evidence packet templates for recursive closure."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ccb_mc_validation.io.artifact_store import atomic_write_json
from ccb_mc_validation.reporting.open_questions import QUESTION_RECORDS
from ccb_mc_validation.reporting.question_closure import ACTION_BY_ID


ARTIFACT_REQUIREMENTS: dict[str, list[str]] = {
    "OQ-MV4": [
        "reports/mc_validation/artifact_reports/MV4_REPORT.html",
        "reports/mc_validation/systematics/MV4_TIMING_UNCERTAINTIES.json",
        "reports/mc_validation/leakage/MV4_TRUTH_BOUNDARY_AUDIT.json",
    ],
    "OQ-MV5": [
        "reports/mc_validation/artifact_reports/MV5_REPORT.html",
        "reports/mc_validation/pileup/MV5_MIXTURE_LINEAGE.json",
        "reports/mc_validation/pileup/MV5_RECOVERY_DIAGNOSTICS.json",
    ],
    "OQ-MV6": [
        "reports/mc_validation/artifact_reports/MV6_REPORT.html",
        "reports/mc_validation/representations/MV6_REPRESENTATION_COMPARISON.json",
        "reports/mc_validation/leakage/MV6_NUISANCE_LEAKAGE_AUDIT.json",
    ],
    "OQ-MV7": [
        "reports/mc_validation/artifact_reports/MV7_REPORT.html",
        "reports/mc_validation/noise/MV7_PEDESTAL_NOISE_CLOSURE.json",
        "reports/mc_validation/noise/MV7_CHANNEL_DIAGNOSTICS.json",
    ],
    "OQ-MV8": [
        "reports/mc_validation/artifact_reports/MV8_REPORT.html",
        "reports/mc_validation/saturation/MV8_DYNAMIC_RANGE_SCAN.json",
        "reports/mc_validation/saturation/MV8_FAILURE_ACCOUNTING.json",
    ],
    "OQ-SYS": [
        "reports/mc_validation/systematics/SYSTEMATIC_ARRAY_MANIFEST.json",
        "reports/mc_validation/systematics/BOOTSTRAP_INTERVALS.json",
        "reports/mc_validation/systematics/UNCERTAINTY_DECOMPOSITION.json",
    ],
    "OQ-WIKI": [
        "wiki/WIKI_MANIFEST.json",
        "reports/mc_validation/references/REFERENCE_REGISTRY.json",
        "publication/PUBLICATION_MANIFEST.json",
        "QA_RELEASE_AUDIT.json",
    ],
}


SLURM_HINTS: dict[str, str] = {
    "OQ-MV4": "sbatch geant4/jobs/mc_validation_pipeline.sbatch --studies MV4",
    "OQ-MV5": "sbatch geant4/jobs/mc_validation_pipeline.sbatch --studies MV5",
    "OQ-MV6": "sbatch geant4/jobs/mc_validation_pipeline.sbatch --studies MV6",
    "OQ-MV7": "sbatch geant4/jobs/mc_validation_pipeline.sbatch --studies MV7",
    "OQ-MV8": "sbatch geant4/jobs/mc_validation_pipeline.sbatch --studies MV8",
    "OQ-SYS": "sbatch geant4/jobs/mc_validation_pipeline.sbatch --studies systematics",
    "OQ-WIKI": "python scripts/mc_validation/run_pipeline.py --run-id <run_id> release && python scripts/mc_validation/run_pipeline.py --run-id <run_id> qa",
}


VALIDATION_GATES = [
    "required artifacts exist and are non-empty",
    "artifact statuses are PASS or PRODUCTION as appropriate",
    "claim ledger updated with evidence links before claim promotion",
    "QA release audit rerun after artifact generation",
]


def _packet(record: dict[str, Any]) -> dict[str, Any]:
    question_id = str(record["id"])
    action, dependencies = ACTION_BY_ID.get(question_id, ("define_action", []))
    return {
        "question_id": question_id,
        "status": "OPEN",
        "packet_status": "BLOCKED",
        "priority": record["priority"],
        "question": record["question"],
        "required_evidence": record["needed_evidence"],
        "closure_action": action,
        "dependencies": dependencies,
        "required_artifacts": ARTIFACT_REQUIREMENTS.get(question_id, []),
        "execution_hint": SLURM_HINTS.get(question_id, "define LUNARC execution command before closure"),
        "validation_gates": VALIDATION_GATES,
        "documentation_updates": [
            "reports/mc_validation/open_questions/OPEN_QUESTIONS.md",
            "reports/mc_validation/open_questions/OPEN_QUESTION_CLOSURE_PLAN.md",
            "reports/mc_validation/claims/CLAIM_LEDGER.md",
            "publication/PUBLICATION_MANIFEST.json",
            "wiki/Open-Questions.md",
        ],
        "terminal_condition": "packet may close only after required artifacts validate, corresponding claim-ledger rows are evidence-backed, and release audit gates pass",
    }


def generate_evidence_packets(run_root: Path) -> dict[str, Any]:
    """Write per-question evidence packet templates without closing claims."""
    run_root = Path(run_root)
    out_dir = run_root / "reports" / "mc_validation" / "open_questions"
    out_dir.mkdir(parents=True, exist_ok=True)
    packets = [_packet(record) for record in QUESTION_RECORDS]
    open_packets = [packet for packet in packets if packet["packet_status"] != "CLOSED"]
    payload: dict[str, Any] = {
        "status": "PASS",
        "scope": "open-question-evidence-packets",
        "all_packets_closed": len(open_packets) == 0,
        "packet_count": len(packets),
        "open_packet_count": len(open_packets),
        "packets": packets,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    atomic_write_json(out_dir / "EVIDENCE_PACKETS.json", payload)

    lines = [
        "# Open-question evidence packets",
        "",
        f"- **All packets closed:** `{payload['all_packets_closed']}`",
        f"- **Packet count:** `{payload['packet_count']}`",
        f"- **Open packet count:** `{payload['open_packet_count']}`",
        "",
        "| Question | Packet status | Closure action | Required artifacts | Execution hint |",
        "|---|---:|---|---|---|",
    ]
    for packet in packets:
        artifacts = "<br>".join(f"`{artifact}`" for artifact in packet["required_artifacts"])
        lines.append(
            f"| {packet['question_id']} | {packet['packet_status']} | {packet['closure_action']} | {artifacts} | `{packet['execution_hint']}` |"
        )
    lines.extend(
        [
            "",
            "## Closure rule",
            "",
            "These packets are templates for recursive study closure. A packet remaining `BLOCKED` is not a failure of generation; it means the production evidence has not yet been produced and checked.",
        ]
    )
    (out_dir / "EVIDENCE_PACKETS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload
