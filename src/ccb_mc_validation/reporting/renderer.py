"""Render MV study reports from structured results."""

from __future__ import annotations

import json
from pathlib import Path
from string import Template

from ccb_mc_validation.studies.common import StudyResult, StudyStatus, write_study_result
from ccb_mc_validation.reporting.tables import metrics_to_markdown_table


def _status_banner(status: StudyStatus) -> str:
    label = status.value
    if status == StudyStatus.PRODUCTION:
        return f"> **STATUS: {label}** — metrics below are from a completed study run."
    if status == StudyStatus.FIXTURE:
        return f"> **STATUS: {label}** — synthetic or partial outputs; not production metrics."
    if status == StudyStatus.NOT_RUN:
        return f"> **STATUS: {label}** — study has not been executed; no metrics are claimed."
    return f"> **STATUS: {label}** — study blocked; see notes for prerequisites."


def _renderable_metrics(result: StudyResult) -> dict:
    """Return metrics safe to tabulate (exclude placeholder-only runs)."""
    if result.status in {StudyStatus.NOT_RUN, StudyStatus.BLOCKED}:
        return {}
    metrics = dict(result.metrics)
    cleaned = {}
    for key, value in metrics.items():
        if key in {"reason", "placeholder"}:
            continue
        if isinstance(value, float) and value != value:  # NaN
            continue
        cleaned[key] = value
    return cleaned


def render_mv_report(study_id: str, result: StudyResult, output_dir: str | Path) -> Path:
    """Generate ``REPORT.md`` for *study_id* without inventing metrics."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    manifest_path = out / "manifest.json"
    result_path = write_study_result(result, out)

    if not manifest_path.is_file():
        manifest_payload = {
            "study_id": study_id,
            "status": result.status.value,
            "study_result": result_path.name,
            "artifacts": sorted(p.name for p in out.iterdir() if p.is_file()),
        }
        manifest_path.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    template_path = Path(__file__).resolve().parents[3] / "templates" / "mc_validation" / "report.md.j2"
    template_text = template_path.read_text(encoding="utf-8")
    template = Template(template_text)

    metrics = _renderable_metrics(result)
    notes_block = "\n".join(f"- {note}" for note in result.notes) if result.notes else "- _none_"
    cutflow_block = (
        metrics_to_markdown_table({f"cutflow.{k}": v for k, v in result.cutflow.items()})
        if result.cutflow
        else "_No cutflow recorded._\n"
    )

    body = template.substitute(
        study_id=study_id,
        status_banner=_status_banner(result.status),
        status=result.status.value,
        metrics_table=metrics_to_markdown_table(metrics),
        cutflow_table=cutflow_block,
        notes_block=notes_block,
        manifest_link=f"[manifest.json](manifest.json)",
        result_link=f"[study_result.json]({result_path.name})",
    )

    report_path = out / "REPORT.md"
    report_path.write_text(body, encoding="utf-8")
    return report_path
