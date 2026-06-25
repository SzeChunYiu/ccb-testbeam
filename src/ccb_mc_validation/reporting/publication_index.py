"""Static publication index draft for MC validation artifacts."""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ccb_mc_validation.io.artifact_store import atomic_write_json

REQUIRED_LINKS = {
    "validation_summary": "VALIDATION_SUMMARY.md",
    "release_audit": "QA_RELEASE_AUDIT.md",
    "claim_ledger": "reports/mc_validation/claims/CLAIM_LEDGER.md",
    "reference_registry": "reports/mc_validation/references/REFERENCE_REGISTRY.md",
    "notation_registry": "reports/mc_validation/notation/NOTATION_REGISTRY.md",
    "open_questions": "reports/mc_validation/open_questions/OPEN_QUESTIONS.md",
    "open_question_closure_plan": "reports/mc_validation/open_questions/OPEN_QUESTION_CLOSURE_PLAN.md",
    "run_summary_html": "reports/mc_validation/summary/RUN_SUMMARY.html",
    "notebook_overview": "notebooks/html/00_release_overview.html",
    "figure_contact_sheet": "figures/summary/FIGURE_CONTACT_SHEET.html",
    "summary_visual_review": "figures/summary/visual_review.html",
    "global_report": "reports/mc_validation/artifact_reports/GLOBAL_REPORT.html",
    "mv1_report": "reports/mc_validation/artifact_reports/MV1_REPORT.html",
    "mv2_report": "reports/mc_validation/artifact_reports/MV2_REPORT.html",
    "mv3_report": "reports/mc_validation/artifact_reports/MV3_REPORT.html",
    "thesis_draft": "reports/mc_validation/thesis_draft/THESIS_DRAFT.html",
}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"missing required JSON artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _rel_status(run_root: Path, rel: str) -> dict[str, Any]:
    path = run_root / rel
    return {"relative_path": rel, "exists": path.is_file(), "size_bytes": path.stat().st_size if path.is_file() else None}


def generate_publication_index(run_root: Path) -> dict[str, Any]:
    """Generate a static index page and manifest for existing publication artifacts."""
    run_root = Path(run_root)
    validation = _load_json(run_root / "VALIDATION.json")
    audit = _load_json(run_root / "QA_RELEASE_AUDIT.json")
    thesis_manifest = _load_json(run_root / "reports" / "mc_validation" / "thesis_draft" / "THESIS_DRAFT_MANIFEST.json")
    report_manifest = _load_json(run_root / "reports" / "mc_validation" / "artifact_reports" / "REPORTS_MANIFEST.json")
    notebook_manifest = _load_json(run_root / "notebooks" / "NOTEBOOKS_MANIFEST.json")

    links = {name: _rel_status(run_root, rel) for name, rel in REQUIRED_LINKS.items()}
    missing = [name for name, rec in links.items() if not rec["exists"]]
    release_ready = bool(audit.get("release_ready")) and not missing
    status = "PASS" if release_ready else "BLOCKED"
    run_id = str(validation.get("run_id") or run_root.name)
    out_dir = run_root / "publication"
    out_dir.mkdir(parents=True, exist_ok=True)
    index_html = out_dir / "index.html"
    index_md = out_dir / "INDEX.md"
    generated = datetime.now(tz=timezone.utc).isoformat()
    blocked_checks = [c for c in audit.get("checks", []) if c.get("status") != "PASS"]

    md_lines = [
        "# MC validation publication index",
        "",
        f"- **Run ID:** `{run_id}`",
        f"- **Validation status:** `{validation.get('status')}`",
        f"- **Release audit status:** `{audit.get('status')}`",
        f"- **Release ready:** `{release_ready}`",
        f"- **Generated:** `{generated}`",
        "",
        "## Artifact links",
        "",
    ]
    for name, rec in links.items():
        md_lines.append(f"- `{name}`: `{rec['relative_path']}` ({'present' if rec['exists'] else 'missing'})")
    md_lines.extend(["", "## Remaining release blockers", ""])
    if blocked_checks:
        md_lines.extend(f"- `{c.get('name')}`: {c.get('reason') or c.get('status')}" for c in blocked_checks)
    else:
        md_lines.append("- None recorded by QA release audit.")
    md_lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "This index is a draft navigation page over frozen artifacts. It is not a final signed release unless `release_ready` is true and all required artifacts are present.",
        ]
    )
    index_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    link_items = "\n".join(
        f"<li><a href='../{html.escape(rec['relative_path'])}'>{html.escape(name)}</a> "
        f"<code>{'present' if rec['exists'] else 'missing'}</code></li>"
        for name, rec in links.items()
    )
    blocker_items = "\n".join(
        f"<li><code>{html.escape(str(c.get('name')))}</code>: {html.escape(str(c.get('reason') or c.get('status')))}</li>"
        for c in blocked_checks
    ) or "<li>None recorded by QA release audit.</li>"
    banner = "Release-ready" if release_ready else "Draft / blocked"
    index_html.write_text(
        "<!doctype html>\n<html lang='en'><head><meta charset='utf-8'>"
        "<title>MC validation publication index</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:980px;margin:2rem auto;line-height:1.5}"
        ".banner{background:#fff3cd;border:1px solid #ffdf7e;padding:1rem;border-radius:.4rem}"
        "code{background:#f6f8fa;padding:.1rem .25rem;border-radius:.2rem}</style></head><body>"
        f"<h1>MC validation publication index</h1><div class='banner'><b>{html.escape(banner)}</b>: release_ready=<code>{str(release_ready).lower()}</code>; audit=<code>{html.escape(str(audit.get('status')))}</code>.</div>"
        f"<p><b>Run ID:</b> <code>{html.escape(run_id)}</code></p>"
        f"<p><b>Validation:</b> <code>{html.escape(str(validation.get('status')))}</code></p>"
        f"<p><b>Report scope:</b> <code>{html.escape(str(report_manifest.get('scope')))}</code>; notebook scope: <code>{html.escape(str(notebook_manifest.get('scope')))}</code>; thesis scope: <code>{html.escape(str(thesis_manifest.get('scope')))}</code></p>"
        f"<h2>Artifact links</h2><ul>{link_items}</ul>"
        f"<h2>Remaining release blockers</h2><ul>{blocker_items}</ul>"
        "<p>This page is generated from frozen artifacts and does not run analysis.</p>"
        "</body></html>\n",
        encoding="utf-8",
    )
    manifest = {
        "status": status,
        "scope": "publication-index-draft",
        "release_ready": release_ready,
        "reason": "Release remains blocked by QA audit or missing publication artifacts." if status != "PASS" else "All publication index requirements passed.",
        "run_id": run_id,
        "index_html": str(index_html),
        "index_markdown": str(index_md),
        "links": links,
        "missing": missing,
        "blocked_count": len(blocked_checks),
        "generated_at": generated,
    }
    atomic_write_json(out_dir / "PUBLICATION_MANIFEST.json", manifest)
    return manifest
