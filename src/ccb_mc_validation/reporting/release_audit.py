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


def generate_release_audit(run_root: Path) -> dict[str, Any]:
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
    ]

    validation = _load_json(run_root / "VALIDATION.json")
    studies = validation.get("study_metrics", {}) if isinstance(validation.get("study_metrics"), dict) else {}
    for study in ("MV1", "MV2", "MV3"):
        rec = studies.get(study, {}) if isinstance(studies, dict) else {}
        checks.append(
            {
                "name": f"{study}_production_artifact",
                "status": PASS if rec.get("status") == "PRODUCTION" else BLOCKED,
                "observed_status": rec.get("status"),
                "reason": None if rec.get("status") == "PRODUCTION" else "missing production study artifact",
            }
        )
    for study in ("MV4", "MV5", "MV6", "MV7", "MV8"):
        checks.append(
            {
                "name": f"{study}_production_artifact",
                "status": BLOCKED,
                "observed_status": "BLOCKED",
                "reason": "requires calibrated digitized MC/systematics production artifacts",
            }
        )
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
