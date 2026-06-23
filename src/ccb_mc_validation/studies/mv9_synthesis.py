"""MV9: synthesis report from registry of MV study results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


VERDICT_ORDER = ("PRODUCTION", "FIXTURE", "NOT_RUN", "BLOCKED")


def _load_registry(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _verdict_line(study_id: str, entry: Mapping[str, Any]) -> str:
    status = entry.get("status", "NOT_RUN")
    metrics = entry.get("metrics", {})
    reason = metrics.get("reason", "")
    if status == "PRODUCTION":
        return f"- **{study_id}**: PRODUCTION — metrics recorded."
    if status == "FIXTURE":
        return f"- **{study_id}**: FIXTURE — synthetic or reduced-statistics run."
    if status == "BLOCKED":
        return f"- **{study_id}**: BLOCKED — {reason}"
    return f"- **{study_id}**: NOT_RUN — {reason}"


def synthesize(registry_path: str | Path, out_path: str | Path | None = None) -> str:
    """
    Read MV study registry JSON and generate MV9_SYNTHESIS markdown report.

    Registry format::

        {
          "studies": {
            "MV1": { "status": "PRODUCTION", "metrics": {...}, ... },
            ...
          }
        }
    """
    registry = _load_registry(registry_path)
    studies: dict[str, Any] = registry.get("studies", registry)

    lines = [
        "# MV9 — MC Validation Synthesis",
        "",
        "Auto-generated verdict column for the MC validation program.",
        "",
        "## Study verdicts",
        "",
    ]
    for study_id in sorted(studies.keys()):
        lines.append(_verdict_line(study_id, studies[study_id]))

    lines.extend(["", "## Summary table", "", "| Study | Status | Key metric |", "| --- | --- | --- |"])
    for study_id in sorted(studies.keys()):
        entry = studies[study_id]
        status = entry.get("status", "NOT_RUN")
        metrics = entry.get("metrics", {})
        key_metric = ""
        for candidate in ("logreg_auc", "hgb_auc", "proton_ekin_recon_res68", "reason"):
            if candidate in metrics:
                key_metric = f"{candidate}={metrics[candidate]}"
                break
        lines.append(f"| {study_id} | {status} | {key_metric} |")

    lines.append("")
    markdown = "\n".join(lines)
    if out_path is not None:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")
    return markdown
