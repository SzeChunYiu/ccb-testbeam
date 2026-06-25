"""Artifact-only notebook source and HTML export for MC validation runs."""
from __future__ import annotations

import csv
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ccb_mc_validation.io.artifact_store import atomic_write_json

NOTEBOOK_ID = "00_release_overview"
NOTEBOOK_TITLE = "MC Validation Release Overview"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_metrics_table(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _require(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"missing required {label}: {path}")


def _jupytext_header(run_id: str) -> str:
    return f'''# ---
# jupyter:
#   jupytext:
#     formats: py:percent,ipynb
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#   kernelspec:
#     display_name: ccb-testbeam
#     language: python
#     name: ccb-testbeam
# ---

# %% tags=["parameters"]
RUN_ID = {run_id!r}
RUN_ROOT = None
STUDY_ID = "MV9"
EXECUTION_MODE = "artifact-summary"
ALLOW_FIXTURE = False
'''


def _render_source(run_id: str) -> str:
    return _jupytext_header(run_id) + '''
# %% [markdown] tags=["provenance"]
# # MC Validation Release Overview
#
# This paired-text notebook is an artifact-only reader entry point. It loads the frozen
# validation and summary artifacts for the injected `RUN_ID`; it must not rerun ROOT scans,
# GEANT4, digitization, model training, systematic arrays, or full-data rendering.

# %% tags=["provenance", "integrity"]
from pathlib import Path
import csv
import json

if RUN_ID is None:
    raise RuntimeError("RUN_ID must be injected for production notebook export")

run_root = Path(RUN_ROOT) if RUN_ROOT else Path.cwd()
validation_path = run_root / "VALIDATION.json"
metrics_path = run_root / "reports" / "mc_validation" / "summary" / "metrics_table.csv"
validation = json.loads(validation_path.read_text(encoding="utf-8"))
metrics = list(csv.DictReader(metrics_path.open("r", encoding="utf-8", newline="")))

if any(row.get("status") == "FIXTURE" for row in metrics):
    raise RuntimeError("fixture metrics are not allowed in production notebook export")

# %% [markdown] tags=["scope"]
# ## Scope and guardrail
#
# This notebook summarizes artifact validation and selected MV1-MV3/MV9 metrics only. It is
# intentionally marked partial until MV4-MV8, systematic arrays, the full figure catalog,
# executable notebooks, reports, thesis, and release QA are complete.

# %% tags=["primary-result"]
validation.get("status"), validation.get("job_state", {})

# %% tags=["primary-result"]
metrics

# %% [markdown] tags=["reproduction"]
# ## Reproduction
#
# From the repository root, rebuild this artifact-only export with:
#
# ```bash
# python scripts/mc_validation/run_pipeline.py --run-id "$RUN_ID" notebooks
# ```
'''


def _metric_value(row: dict[str, str]) -> str:
    for key in ("hgb_auc", "proton_ekin_recon_res68", "n_sample_I"):
        value = row.get(key, "")
        if value:
            return value
    return ""


def _render_html(run_id: str, validation: dict[str, Any], rows: list[dict[str, str]]) -> str:
    job = validation.get("job_state", {}) if isinstance(validation.get("job_state"), dict) else {}
    row_html = "\n".join(
        "<tr>"
        f"<td>{html.escape(row.get('study', ''))}</td>"
        f"<td>{html.escape(row.get('status', ''))}</td>"
        f"<td>{html.escape(row.get('n_tracks', ''))}</td>"
        f"<td>{html.escape(_metric_value(row))}</td>"
        "</tr>"
        for row in rows
    )
    generated = datetime.now(tz=timezone.utc).isoformat()
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{NOTEBOOK_TITLE}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:980px;margin:2rem auto;line-height:1.5;color:#17202a}}
.banner{{background:#fff3cd;border:1px solid #ffdf7e;padding:1rem;border-radius:.4rem}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}} th,td{{border:1px solid #d0d7de;padding:.45rem;text-align:left}}
code{{background:#f6f8fa;padding:.1rem .25rem;border-radius:.2rem}}
</style></head>
<body>
<h1>{NOTEBOOK_TITLE}</h1>
<p><b>Run ID:</b> <code>{html.escape(run_id)}</code></p>
<p><b>Artifact validation:</b> <code>{html.escape(str(validation.get('status')))}</code></p>
<p><b>LUNARC job:</b> <code>{html.escape(str(job.get('job_id', 'unknown')))}</code>, state <code>{html.escape(str(job.get('state', 'unknown')))}</code> / <code>{html.escape(str(job.get('exit_code', 'unknown')))}</code></p>
<div class="banner"><b>Partial notebook export.</b> This HTML is generated from frozen artifacts only. It does not execute full-data notebooks and is not a final thesis/release result. MV4-MV8, systematic arrays, full figure catalog, thesis, and release QA remain blockers unless separately validated.</div>
<h2>Selected artifact metrics</h2>
<table><thead><tr><th>Study</th><th>Status</th><th>n tracks</th><th>Key metric</th></tr></thead><tbody>{row_html}</tbody></table>
<h2>Artifact links</h2>
<ul>
<li><code>reports/mc_validation/summary/RUN_SUMMARY.md</code></li>
<li><code>reports/mc_validation/summary/RUN_SUMMARY.html</code></li>
<li><code>reports/mc_validation/summary/metrics_table.csv</code></li>
</ul>
<h2>Reproduction</h2>
<pre>python scripts/mc_validation/run_pipeline.py --run-id {html.escape(run_id)} notebooks</pre>
<p><small>Generated {html.escape(generated)}.</small></p>
</body></html>
"""


def generate_notebook_exports(run_root: Path) -> dict[str, Any]:
    """Generate artifact-only notebook source plus static HTML for a validated run."""
    run_root = Path(run_root)
    validation_path = run_root / "VALIDATION.json"
    metrics_path = run_root / "reports" / "mc_validation" / "summary" / "metrics_table.csv"
    summary_html_path = run_root / "reports" / "mc_validation" / "summary" / "RUN_SUMMARY.html"
    _require(validation_path, "artifact validation")
    _require(metrics_path, "summary metrics table")
    _require(summary_html_path, "run summary html")

    validation = _read_json(validation_path)
    run_id = str(validation.get("run_id") or run_root.name)
    rows = _read_metrics_table(metrics_path)
    if any(row.get("status") == "FIXTURE" for row in rows):
        raise ValueError("fixture metrics cannot be exported as production notebook artifacts")

    source_dir = run_root / "notebooks" / "source"
    executed_dir = run_root / "notebooks" / "executed"
    html_dir = run_root / "notebooks" / "html"
    for directory in (source_dir, executed_dir, html_dir):
        directory.mkdir(parents=True, exist_ok=True)

    source_path = source_dir / f"{NOTEBOOK_ID}.py"
    html_path = html_dir / f"{NOTEBOOK_ID}.html"
    source_path.write_text(_render_source(run_id), encoding="utf-8")
    html_path.write_text(_render_html(run_id, validation, rows), encoding="utf-8")

    manifest = {
        "status": "PASS",
        "scope": "artifact-summary",
        "full_notebook_suite_status": "BLOCKED",
        "reason": "Generated artifact-only source and HTML; clean-kernel full-data notebook execution still requires LUNARC sbatch implementation and complete production artifacts.",
        "run_id": run_id,
        "notebooks": [
            {
                "id": NOTEBOOK_ID,
                "source": str(source_path),
                "html": str(html_path),
                "executed_ipynb": None,
                "execution_status": "NOT_EXECUTED_ARTIFACT_HTML_ONLY",
                "dependencies": [str(validation_path), str(metrics_path), str(summary_html_path)],
            }
        ],
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    atomic_write_json(run_root / "notebooks" / "NOTEBOOKS_MANIFEST.json", manifest)
    return manifest
