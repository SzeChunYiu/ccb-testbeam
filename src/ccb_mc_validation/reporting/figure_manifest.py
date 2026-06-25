"""Manifest and contact sheet for generated MC-validation summary figures."""
from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ccb_mc_validation.io.artifact_store import atomic_write_json

FIGURES = [
    {
        "id": "SUMMARY-F001",
        "stem": "study_support",
        "title": "Study support overview",
        "alt_text": "Bar chart summarizing available support for MV1, MV2, and MV3 artifact studies.",
    },
    {
        "id": "SUMMARY-F002",
        "stem": "selected_metrics",
        "title": "Selected validated metrics",
        "alt_text": "Bar chart of selected artifact metrics for MV1, MV2, and MV3.",
    },
]


def generate_summary_figure_manifest(run_root: Path) -> dict[str, Any]:
    """Write metadata sidecars and a contact sheet for compact summary figures."""
    run_root = Path(run_root)
    figure_dir = run_root / "figures" / "summary"
    summary_table = run_root / "reports" / "mc_validation" / "summary" / "metrics_table.csv"
    records: list[dict[str, Any]] = []
    for spec in FIGURES:
        formats = []
        for ext in ("svg", "png"):
            path = figure_dir / f"{spec['stem']}.{ext}"
            formats.append(
                {
                    "format": ext,
                    "relative_path": str(path.relative_to(run_root)),
                    "exists": path.is_file(),
                    "size_bytes": path.stat().st_size if path.is_file() else None,
                }
            )
        status = "PASS" if all(item["exists"] for item in formats) else "BLOCKED"
        records.append(
            {
                "id": spec["id"],
                "title": spec["title"],
                "status": status,
                "scope": "summary-artifact",
                "alt_text": spec["alt_text"],
                "data_sidecar": str(summary_table.relative_to(run_root)),
                "data_sidecar_exists": summary_table.is_file(),
                "formats": formats,
            }
        )
    status = "PASS" if all(r["status"] == "PASS" and r["data_sidecar_exists"] for r in records) else "BLOCKED"
    manifest = {
        "status": status,
        "scope": "summary-figure-manifest",
        "full_figure_catalog_status": "BLOCKED",
        "reason": "Catalogs compact summary figures only; full required figure catalog/contact sheets remain incomplete.",
        "figures": records,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    figure_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(figure_dir / "FIGURE_MANIFEST.json", manifest)

    md_lines = [
        "# Summary figure contact sheet",
        "",
        f"- **Status:** `{status}`",
        "- **Scope:** `summary-figure-manifest`",
        "- **Full figure catalog:** `BLOCKED`",
        "",
    ]
    for record in records:
        png = next(item for item in record["formats"] if item["format"] == "png")
        md_lines.extend(
            [
                f"## {record['id']} — {record['title']}",
                "",
                f"- Status: `{record['status']}`",
                f"- Alt text: {record['alt_text']}",
                f"- Data sidecar: `{record['data_sidecar']}`",
                f"- PNG: `{png['relative_path']}`",
                "",
            ]
        )
    (figure_dir / "FIGURE_CONTACT_SHEET.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    cards = "\n".join(
        f"<section><h2>{html.escape(record['id'])}: {html.escape(record['title'])}</h2>"
        f"<p>Status: <code>{html.escape(record['status'])}</code></p>"
        f"<p>{html.escape(record['alt_text'])}</p>"
        f"<img src='{html.escape(next(item for item in record['formats'] if item['format']=='png')['relative_path'].split('/')[-1])}' alt='{html.escape(record['alt_text'])}' style='max-width:100%;border:1px solid #d0d7de'>"
        f"<p>Data sidecar: <code>{html.escape(record['data_sidecar'])}</code></p></section>"
        for record in records
    )
    (figure_dir / "FIGURE_CONTACT_SHEET.html").write_text(
        "<!doctype html>\n<html lang='en'><head><meta charset='utf-8'><title>Summary figure contact sheet</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:980px;margin:2rem auto;line-height:1.5}section{margin:2rem 0}</style></head><body>"
        f"<h1>Summary figure contact sheet</h1><p>Status: <code>{html.escape(status)}</code>; full figure catalog: <code>BLOCKED</code>.</p>{cards}</body></html>\n",
        encoding="utf-8",
    )
    return manifest
