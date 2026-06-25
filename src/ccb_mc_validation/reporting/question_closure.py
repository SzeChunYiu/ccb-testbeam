"""Open-question recursive closure plan artifacts."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ccb_mc_validation.io.artifact_store import atomic_write_json
from ccb_mc_validation.reporting.open_questions import QUESTION_RECORDS

ACTION_BY_ID = {
    "OQ-MV4": ("produce_mv4_timing_artifact", ["calibrated_digitized_mc", "timing_truth_boundary_audit"]),
    "OQ-MV5": ("produce_mv5_pileup_artifact", ["calibrated_digitized_mc", "controlled_mixture_manifest"]),
    "OQ-MV6": ("produce_mv6_representation_artifact", ["calibrated_digitized_mc", "fit_split_registry"]),
    "OQ-MV7": ("produce_mv7_pedestal_noise_artifact", ["real_pedestal_splits", "calibrated_digitized_mc"]),
    "OQ-MV8": ("produce_mv8_saturation_artifact", ["calibrated_digitized_mc", "dynamic_range_scan"]),
    "OQ-SYS": ("submit_systematic_arrays", ["MV4", "MV5", "MV6", "MV7", "MV8"]),
    "OQ-WIKI": ("publish_final_wiki", ["release_audit_PASS", "curated_bibliography", "full_figure_catalog"]),
}


def generate_question_closure_plan(run_root: Path) -> dict[str, Any]:
    run_root = Path(run_root)
    out_dir = run_root / "reports" / "mc_validation" / "open_questions"
    out_dir.mkdir(parents=True, exist_ok=True)
    steps = []
    for index, record in enumerate(QUESTION_RECORDS, start=1):
        action, deps = ACTION_BY_ID[record["id"]]
        steps.append(
            {
                "order": index,
                "question_id": record["id"],
                "status": "OPEN",
                "priority": record["priority"],
                "action": action,
                "dependencies": deps,
                "required_evidence": record["needed_evidence"],
                "terminal_condition": "close only after required evidence artifact exists, validates, and claim ledger is updated",
            }
        )
    mermaid = ["flowchart TD"]
    for step in steps:
        node = step["question_id"].replace("-", "_")
        mermaid.append(f"  {node}[\"{step['question_id']}: {step['action']}\"]")
        for dep in step["dependencies"]:
            dep_node = dep.replace("-", "_").replace(" ", "_")
            mermaid.append(f"  {dep_node}[\"{dep}\"] --> {node}")
    payload: dict[str, Any] = {
        "status": "PASS",
        "scope": "open-question-closure-plan",
        "all_steps_closed": False,
        "step_count": len(steps),
        "steps": steps,
        "dag_mermaid": "\n".join(mermaid),
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    atomic_write_json(out_dir / "OPEN_QUESTION_CLOSURE_PLAN.json", payload)
    lines = [
        "# Recursive open-question closure plan",
        "",
        f"- **All steps closed:** `{payload['all_steps_closed']}`",
        f"- **Step count:** `{payload['step_count']}`",
        "",
        "```mermaid",
        payload["dag_mermaid"],
        "```",
        "",
        "| Order | Question | Priority | Action | Dependencies | Required evidence | Terminal condition |",
        "|---:|---|---:|---|---|---|---|",
    ]
    for step in steps:
        lines.append(
            f"| {step['order']} | {step['question_id']} | {step['priority']} | {step['action']} | {', '.join(step['dependencies'])} | {step['required_evidence']} | {step['terminal_condition']} |"
        )
    (out_dir / "OPEN_QUESTION_CLOSURE_PLAN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload
