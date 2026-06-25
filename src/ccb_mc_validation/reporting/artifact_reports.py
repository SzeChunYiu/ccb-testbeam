"""Artifact-backed Markdown/HTML reports for MC validation runs."""
from __future__ import annotations

import csv
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ccb_mc_validation.io.artifact_store import atomic_write_json

REPORT_SCOPE = "artifact-summary"
SUPPORTED_STUDIES = ("MV1", "MV2", "MV3")
BLOCKED_STUDIES = ("MV4", "MV5", "MV6", "MV7", "MV8")


def _require(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"missing required {label}: {path}")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_metrics(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _key_metric(row: dict[str, str]) -> str:
    for key in ("hgb_auc", "proton_ekin_recon_res68", "n_sample_I"):
        value = row.get(key, "")
        if value:
            return f"{key}={value}"
    return "not available"


def _markdown_table(rows: list[dict[str, str]]) -> list[str]:
    lines = ["| Study | Status | n tracks | Key metric |", "|---|---:|---:|---|"]
    for row in rows:
        lines.append(f"| {row.get('study', '')} | {row.get('status', '')} | {row.get('n_tracks', '')} | {_key_metric(row)} |")
    return lines


def _html_table(rows: list[dict[str, str]]) -> str:
    body = "\n".join(
        "<tr>"
        f"<td>{html.escape(row.get('study', ''))}</td>"
        f"<td>{html.escape(row.get('status', ''))}</td>"
        f"<td>{html.escape(row.get('n_tracks', ''))}</td>"
        f"<td>{html.escape(_key_metric(row))}</td>"
        "</tr>"
        for row in rows
    )
    return f"<table><thead><tr><th>Study</th><th>Status</th><th>n tracks</th><th>Key metric</th></tr></thead><tbody>{body}</tbody></table>"


def _write_html(path: Path, title: str, body: str) -> None:
    path.write_text(
        "<!doctype html>\n"
        "<html lang='en'><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:980px;margin:2rem auto;line-height:1.5}"
        "table{border-collapse:collapse;width:100%;margin:1rem 0}td,th{border:1px solid #d0d7de;padding:.45rem;text-align:left}"
        ".guardrail{background:#fff3cd;border:1px solid #ffdf7e;padding:1rem;border-radius:.4rem}</style></head><body>"
        + body
        + "</body></html>\n",
        encoding="utf-8",
    )


def _study_report(study: str, row: dict[str, str], validation: dict[str, Any], out_dir: Path) -> dict[str, str]:
    study_metrics = validation.get("study_metrics", {}).get(study, {}) if isinstance(validation.get("study_metrics"), dict) else {}
    cutflow = study_metrics.get("cutflow", {}) if isinstance(study_metrics, dict) else {}
    metrics = study_metrics.get("metrics", {}) if isinstance(study_metrics, dict) else {}
    md = out_dir / f"{study}_REPORT.md"
    html_path = out_dir / f"{study}_REPORT.html"
    lines = [
        f"# {study} artifact report",
        "",
        f"- **Status:** `{row.get('status', '')}`",
        f"- **Run ID:** `{validation.get('run_id')}`",
        f"- **Scope:** `{REPORT_SCOPE}`",
        f"- **n tracks:** `{row.get('n_tracks', '')}`",
        f"- **Key metric:** `{_key_metric(row)}`",
        "",
        "## Artifact-backed metrics",
        "",
        "```json",
        json.dumps(metrics, indent=2, sort_keys=True),
        "```",
        "",
        "## Cutflow/support",
        "",
        "```json",
        json.dumps(cutflow, indent=2, sort_keys=True),
        "```",
        "",
        "## Guardrail",
        "",
        "This report summarizes validated frozen artifacts only. It does not add uncertainty/systematic arrays or final thesis/release conclusions.",
    ]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _write_html(
        html_path,
        f"{study} artifact report",
        f"<h1>{html.escape(study)} artifact report</h1>"
        f"<p><b>Status:</b> <code>{html.escape(row.get('status', ''))}</code></p>"
        f"<p><b>Run ID:</b> <code>{html.escape(str(validation.get('run_id')))}</code></p>"
        f"<p><b>Key metric:</b> <code>{html.escape(_key_metric(row))}</code></p>"
        f"<h2>Metrics JSON</h2><pre>{html.escape(json.dumps(metrics, indent=2, sort_keys=True))}</pre>"
        f"<h2>Cutflow/support JSON</h2><pre>{html.escape(json.dumps(cutflow, indent=2, sort_keys=True))}</pre>"
        "<div class='guardrail'>Frozen-artifact report only; not a final thesis/release conclusion.</div>",
    )
    return {"study": study, "markdown": str(md), "html": str(html_path), "status": row.get("status", "")}


def generate_artifact_reports(run_root: Path) -> dict[str, Any]:
    """Generate global and per-study reports from frozen validation artifacts."""
    run_root = Path(run_root)
    validation_path = run_root / "VALIDATION.json"
    metrics_path = run_root / "reports" / "mc_validation" / "summary" / "metrics_table.csv"
    notebook_manifest_path = run_root / "notebooks" / "NOTEBOOKS_MANIFEST.json"
    _require(validation_path, "artifact validation")
    _require(metrics_path, "summary metrics table")

    validation = _load_json(validation_path)
    rows = _load_metrics(metrics_path)
    if any(row.get("status") == "FIXTURE" for row in rows):
        raise ValueError("fixture metrics cannot be exported as production reports")
    row_by_study = {row.get("study"): row for row in rows}
    out_dir = run_root / "reports" / "mc_validation" / "artifact_reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    run_id = str(validation.get("run_id") or run_root.name)
    global_md = out_dir / "GLOBAL_REPORT.md"
    global_html = out_dir / "GLOBAL_REPORT.html"
    generated = datetime.now(tz=timezone.utc).isoformat()
    lines = [
        "# MC Validation artifact report",
        "",
        f"- **Run ID:** `{run_id}`",
        f"- **Artifact validation:** `{validation.get('status')}`",
        f"- **Scope:** `{REPORT_SCOPE}`",
        f"- **Generated:** `{generated}`",
        "",
        "## Selected metrics",
        "",
        *_markdown_table(rows),
        "",
        "## Explicit blockers",
        "",
        *(f"- `{study}`: `BLOCKED` pending calibrated digitized MC/systematic production artifacts" for study in BLOCKED_STUDIES),
        "",
        "## Guardrail",
        "",
        "This global report is generated from frozen artifact summaries. It is not the final figure catalog, clean-kernel notebook suite, thesis, or release QA result.",
    ]
    if notebook_manifest_path.is_file():
        lines.extend(["", "## Notebook artifact manifest", "", f"- `{notebook_manifest_path.relative_to(run_root)}`"])
    global_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _write_html(
        global_html,
        "MC Validation artifact report",
        f"<h1>MC Validation artifact report</h1><p><b>Run ID:</b> <code>{html.escape(run_id)}</code></p>"
        f"<p><b>Artifact validation:</b> <code>{html.escape(str(validation.get('status')))}</code></p>"
        + _html_table(rows)
        + "<h2>Explicit blockers</h2><ul>"
        + "".join(f"<li><code>{study}</code>: <code>BLOCKED</code> pending calibrated digitized MC/systematic production artifacts</li>" for study in BLOCKED_STUDIES)
        + "</ul><div class='guardrail'>Frozen-artifact report only; not final thesis/release QA.</div>",
    )

    reports = []
    for study in SUPPORTED_STUDIES:
        if study in row_by_study:
            reports.append(_study_report(study, row_by_study[study], validation, out_dir))

    manifest = {
        "status": "PASS",
        "scope": REPORT_SCOPE,
        "full_report_suite_status": "BLOCKED",
        "reason": "Generated global and MV1-MV3 artifact reports from frozen artifacts; full reports/thesis/release QA require remaining production blockers.",
        "run_id": run_id,
        "global_report": {"markdown": str(global_md), "html": str(global_html)},
        "study_reports": reports,
        "blocked_studies": list(BLOCKED_STUDIES),
        "generated_at": generated,
    }
    atomic_write_json(out_dir / "REPORTS_MANIFEST.json", manifest)
    return manifest
