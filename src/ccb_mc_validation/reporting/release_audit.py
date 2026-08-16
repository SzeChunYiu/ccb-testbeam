"""Fail-closed release audit matrix for MC validation artifacts."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ccb_mc_validation.io.artifact_store import atomic_write_json

PASS = "PASS"
BLOCKED = "BLOCKED"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _check_file(name: str, path: Path, *, required_status: str | None = None, json_key: str = "status") -> dict[str, Any]:
    rec: dict[str, Any] = {"name": name, "path": str(path), "exists": path.is_file()}
    if not path.is_file():
        rec.update({"status": BLOCKED, "reason": "missing artifact"})
        return rec
    rec["size_bytes"] = path.stat().st_size
    if required_status is not None:
        payload = _load_json(path)
        observed = payload.get(json_key)
        rec["observed_status"] = observed
        rec["status"] = PASS if observed == required_status else BLOCKED
        if rec["status"] != PASS:
            rec["reason"] = f"expected {json_key}={required_status}, observed {observed}"
    else:
        rec["status"] = PASS
    return rec


def _check_json_bool(name: str, path: Path, key: str, expected: bool) -> dict[str, Any]:
    rec: dict[str, Any] = {"name": name, "path": str(path), "exists": path.is_file(), "expected": expected}
    if not path.is_file():
        rec.update({"status": BLOCKED, "reason": "missing artifact"})
        return rec
    payload = _load_json(path)
    observed = payload.get(key)
    rec.update({"observed": observed, "size_bytes": path.stat().st_size})
    rec["status"] = PASS if observed is expected else BLOCKED
    if rec["status"] != PASS:
        rec["reason"] = f"expected {key}={expected}, observed {observed}"
    return rec



def _check_wiki_page(name: str, run_root: Path, page_name: str) -> dict[str, Any]:
    """Fail-closed check that a wiki manifest lists a concrete non-empty page."""

    manifest_path = run_root / "wiki" / "WIKI_MANIFEST.json"
    page_path = run_root / "wiki" / page_name
    rec: dict[str, Any] = {
        "name": name,
        "manifest_path": str(manifest_path),
        "page_path": str(page_path),
        "manifest_exists": manifest_path.is_file(),
        "page_exists": page_path.is_file(),
    }
    if not manifest_path.is_file():
        rec.update({"status": BLOCKED, "reason": "missing wiki manifest"})
        return rec
    if not page_path.is_file():
        rec.update({"status": BLOCKED, "reason": "missing wiki page"})
        return rec
    manifest = _load_json(manifest_path)
    pages = manifest.get("pages", [])
    listed = page_name in pages if isinstance(pages, list) else False
    size = page_path.stat().st_size
    rec.update({"listed_in_manifest": listed, "size_bytes": size})
    rec["status"] = PASS if listed and size > 0 else BLOCKED
    if rec["status"] != PASS:
        rec["reason"] = f"expected {page_name} listed in WIKI_MANIFEST.json and non-empty"
    return rec


def study_release_check(name: str, rec: dict) -> dict:
    """VAL-002 defense-in-depth: a study passes the release gate only if it is
    PRODUCTION with no blocker/error marker -- not merely status == PRODUCTION."""
    ok = isinstance(rec, dict) and rec.get("status") == "PRODUCTION"
    reason = None if ok else "missing/non-production study artifact"
    if ok and rec.get("blocked_by"):
        ok = False
        reason = f"study blocked_by {rec.get('blocked_by')!r}"
    if ok and rec.get("_ml_error"):
        ok = False
        reason = "study recorded an ML error (_ml_error)"
    return {
        "name": f"{name}_production_artifact",
        "status": PASS if ok else BLOCKED,
        "observed_status": rec.get("status") if isinstance(rec, dict) else None,
        "reason": reason,
    }


def generate_release_audit(run_root: Path, *, include_claim_ledger: bool = False) -> dict[str, Any]:
    """Write a machine-readable release audit and Markdown summary.

    This audit intentionally fails closed for the current partial production state.
    It distinguishes validated artifact-summary deliverables from full release
    requirements that remain blocked.
    """
    run_root = Path(run_root)
    checks = [
        _check_file("artifact_validation", run_root / "VALIDATION.json", required_status=PASS),
        _check_file("run_summary_html", run_root / "reports" / "mc_validation" / "summary" / "RUN_SUMMARY.html"),
        _check_file("run_summary_metrics", run_root / "reports" / "mc_validation" / "summary" / "metrics_table.csv"),
        _check_file("artifact_notebook_manifest", run_root / "notebooks" / "NOTEBOOKS_MANIFEST.json", required_status=PASS),
        _check_file("artifact_report_manifest", run_root / "reports" / "mc_validation" / "artifact_reports" / "REPORTS_MANIFEST.json", required_status=PASS),
        _check_file("summary_figure_manifest", run_root / "figures" / "summary" / "FIGURE_MANIFEST.json", required_status=PASS),
        _check_file("summary_visual_review", run_root / "figures" / "summary" / "visual_review.json", required_status=PASS),
        _check_file("open_question_registry", run_root / "reports" / "mc_validation" / "open_questions" / "OPEN_QUESTIONS.json", required_status=PASS),
        _check_file("open_question_closure_plan", run_root / "reports" / "mc_validation" / "open_questions" / "OPEN_QUESTION_CLOSURE_PLAN.json", required_status=PASS),
        _check_file("open_question_evidence_packets", run_root / "reports" / "mc_validation" / "open_questions" / "EVIDENCE_PACKETS.json", required_status=PASS),
        _check_file("study_implementation_gap_audit", run_root / "reports" / "mc_validation" / "open_questions" / "STUDY_IMPLEMENTATION_GAP_AUDIT.json", required_status=PASS),
    ]
    if include_claim_ledger:
        checks.append(_check_file("claim_ledger", run_root / "reports" / "mc_validation" / "claims" / "CLAIM_LEDGER.json", required_status=PASS))
    checks.append(_check_wiki_page("wiki_claim_evidence_matrix", run_root, "Claim-Evidence-Matrix.md"))
    checks.append(_check_wiki_page("wiki_claim_dependency_tree", run_root, "Claim-Dependency-Tree.md"))
    checks.append(_check_wiki_page("wiki_study_coverage_gaps", run_root, "Study-Coverage-and-Remaining-Gaps.md"))

    validation = _load_json(run_root / "VALIDATION.json")
    studies = validation.get("study_metrics", {}) if isinstance(validation.get("study_metrics"), dict) else {}
    for study in ("MV1", "MV2", "MV3"):
        rec = studies.get(study, {}) if isinstance(studies, dict) else {}
        checks.append(study_release_check(study, rec))
    for study in ("MV4", "MV5", "MV6", "MV7", "MV8"):
        checks.append(
            {
                "name": f"{study}_production_artifact",
                "status": BLOCKED,
                "observed_status": "BLOCKED",
                "reason": "requires calibrated digitized MC/systematics production artifacts",
            }
        )
    checks.append(_check_json_bool("all_questions_closed", run_root / "reports" / "mc_validation" / "open_questions" / "OPEN_QUESTIONS.json", "all_questions_closed", True))
    checks.append(_check_json_bool("all_question_steps_closed", run_root / "reports" / "mc_validation" / "open_questions" / "OPEN_QUESTION_CLOSURE_PLAN.json", "all_steps_closed", True))
    checks.append(_check_json_bool("all_evidence_packets_closed", run_root / "reports" / "mc_validation" / "open_questions" / "EVIDENCE_PACKETS.json", "all_packets_closed", True))
    checks.append(_check_json_bool("all_study_implementations_ready", run_root / "reports" / "mc_validation" / "open_questions" / "STUDY_IMPLEMENTATION_GAP_AUDIT.json", "all_study_implementations_ready", True))

    for name, reason in (
        ("systematic_arrays", "required systematic/bootstrap arrays are not complete"),
        ("full_figure_catalog", "required 300-entry figure catalog/contact sheets are not complete"),
        ("clean_kernel_notebooks", "full-data notebooks have not been executed via LUNARC sbatch"),
        ("thesis_pdf_html", "thesis/static site PDF/HTML package is not built"),
        ("release_bundle", "final release bundle/signoff is not complete"),
    ):
        checks.append({"name": name, "status": BLOCKED, "reason": reason})

    status = PASS if all(c.get("status") == PASS for c in checks) else BLOCKED
    payload = {
        "status": status,
        "run_id": validation.get("run_id", run_root.name),
        "release_ready": status == PASS,
        "checks": checks,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    atomic_write_json(run_root / "QA_RELEASE_AUDIT.json", payload)

    lines = [
        "# MC Validation release QA audit",
        "",
        f"- **Run ID:** `{payload['run_id']}`",
        f"- **Status:** **{status}**",
        f"- **Release ready:** `{payload['release_ready']}`",
        "",
        "| Check | Status | Reason |",
        "|---|---:|---|",
    ]
    for check in checks:
        lines.append(f"| {check['name']} | {check['status']} | {check.get('reason') or ''} |")
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "A `BLOCKED` release audit is expected until MV4-MV8, systematic arrays, the full figure catalog, clean-kernel notebooks, thesis/static site, and release bundle are completed and validated.",
        ]
    )
    (run_root / "QA_RELEASE_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload
