"""Artifact-backed thesis draft generation for MC validation."""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ccb_mc_validation.io.artifact_store import atomic_write_json


def _require(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"missing required {label}: {path}")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_html(path: Path, title: str, markdown_text: str) -> None:
    # Deliberately simple static HTML; full PDF/site rendering remains blocked.
    escaped = html.escape(markdown_text)
    body = escaped.replace("\n", "<br>\n")
    path.write_text(
        "<!doctype html>\n<html lang='en'><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:980px;margin:2rem auto;line-height:1.55}"
        ".banner{background:#fff3cd;border:1px solid #ffdf7e;padding:1rem;border-radius:.4rem}</style></head><body>"
        "<div class='banner'><b>Draft only.</b> This artifact is assembled from frozen validation/report artifacts and is not a final thesis, PDF, or release package.</div>"
        f"<pre style='white-space:pre-wrap'>{body}</pre>"
        "</body></html>\n",
        encoding="utf-8",
    )


def generate_thesis_draft(run_root: Path) -> dict[str, Any]:
    """Generate a blocked thesis draft skeleton from available artifact reports."""
    run_root = Path(run_root)
    validation_path = run_root / "VALIDATION.json"
    audit_path = run_root / "QA_RELEASE_AUDIT.json"
    reports_manifest_path = run_root / "reports" / "mc_validation" / "artifact_reports" / "REPORTS_MANIFEST.json"
    notebook_manifest_path = run_root / "notebooks" / "NOTEBOOKS_MANIFEST.json"
    for label, path in (
        ("validation", validation_path),
        ("release audit", audit_path),
        ("artifact report manifest", reports_manifest_path),
        ("notebook manifest", notebook_manifest_path),
    ):
        _require(path, label)

    validation = _load_json(validation_path)
    audit = _load_json(audit_path)
    reports = _load_json(reports_manifest_path)
    notebooks = _load_json(notebook_manifest_path)
    run_id = str(validation.get("run_id") or run_root.name)
    out_dir = run_root / "reports" / "mc_validation" / "thesis_draft"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "THESIS_DRAFT.md"
    html_path = out_dir / "THESIS_DRAFT.html"
    generated = datetime.now(tz=timezone.utc).isoformat()
    blocked = [c for c in audit.get("checks", []) if c.get("status") != "PASS"]

    lines = [
        "# CCB testbeam MC validation thesis draft",
        "",
        f"- **Run ID:** `{run_id}`",
        f"- **Generated:** `{generated}`",
        f"- **Validation status:** `{validation.get('status')}`",
        f"- **Release audit:** `{audit.get('status')}`, release_ready=`{audit.get('release_ready')}`",
        f"- **Report scope:** `{reports.get('scope')}` with full_report_suite_status=`{reports.get('full_report_suite_status')}`",
        f"- **Notebook scope:** `{notebooks.get('scope')}` with full_notebook_suite_status=`{notebooks.get('full_notebook_suite_status')}`",
        "",
        "## Abstract draft",
        "",
        "This draft records the current frozen-artifact MC validation state for MV1-MV3 and MV9. It is a writing scaffold and provenance index, not a final scientific thesis conclusion.",
        "",
        "## Artifact-backed chapters",
        "",
        "1. Inputs, provenance, and execution status: see `VALIDATION_SUMMARY.md` and `QA_RELEASE_AUDIT.md`.",
        "2. MV1 particle identification: see `reports/mc_validation/artifact_reports/MV1_REPORT.md`.",
        "3. MV2 energy/range response: see `reports/mc_validation/artifact_reports/MV2_REPORT.md`.",
        "4. MV3 stopping profile: see `reports/mc_validation/artifact_reports/MV3_REPORT.md`.",
        "5. MV9 synthesis and global status: see `reports/mc_validation/artifact_reports/GLOBAL_REPORT.md`.",
        "",
        "## Release blockers to resolve before final thesis",
        "",
    ]
    lines.extend(f"- `{c.get('name')}`: {c.get('reason') or c.get('status')}" for c in blocked)
    lines.extend(
        [
            "",
            "## Reproduction",
            "",
            f"```bash\npython scripts/mc_validation/run_pipeline.py --run-id {run_id} thesis\n```",
            "",
            "## Guardrail",
            "",
            "This draft must not be cited as the final thesis/static-site/PDF release. It intentionally preserves blocker visibility.",
        ]
    )
    markdown = "\n".join(lines) + "\n"
    md_path.write_text(markdown, encoding="utf-8")
    _write_html(html_path, "CCB testbeam MC validation thesis draft", markdown)
    manifest = {
        "status": "PASS",
        "scope": "artifact-thesis-draft",
        "final_thesis_status": "BLOCKED",
        "reason": "Generated a draft scaffold from frozen artifacts; final thesis/PDF/site remains blocked by release audit gaps.",
        "run_id": run_id,
        "markdown": str(md_path),
        "html": str(html_path),
        "blocked_count": len(blocked),
        "generated_at": generated,
    }
    atomic_write_json(out_dir / "THESIS_DRAFT_MANIFEST.json", manifest)
    return manifest
