"""Scoped visual-review record for MC-validation summary figures."""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ccb_mc_validation.io.artifact_store import atomic_write_json


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"missing figure manifest for visual review: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def generate_summary_visual_review(run_root: Path) -> dict[str, Any]:
    """Generate a non-final visual review record for compact summary figures."""
    run_root = Path(run_root)
    figure_dir = run_root / "figures" / "summary"
    manifest = _load_manifest(figure_dir / "FIGURE_MANIFEST.json")
    reviewed_at = datetime.now(tz=timezone.utc).isoformat()
    reviews: list[dict[str, Any]] = []
    for fig in manifest.get("figures", []):
        png = next((fmt for fmt in fig.get("formats", []) if fmt.get("format") == "png"), {})
        svg = next((fmt for fmt in fig.get("formats", []) if fmt.get("format") == "svg"), {})
        status = "PASS" if fig.get("status") == "PASS" and png.get("exists") and svg.get("exists") and fig.get("alt_text") else "BLOCKED"
        reviews.append(
            {
                "figure_id": fig.get("id"),
                "title": fig.get("title"),
                "status": status,
                "reviewer": "codex-automated-visual-qa",
                "reviewed_at": reviewed_at,
                "checks": {
                    "png_present": bool(png.get("exists")),
                    "svg_present": bool(svg.get("exists")),
                    "alt_text_present": bool(fig.get("alt_text")),
                    "data_sidecar_present": bool(fig.get("data_sidecar_exists")),
                    "scope_banner_required": True,
                },
                "notes": "Scoped review of compact summary artifact only; not a substitute for human review of the full thesis/release figure catalog.",
            }
        )
    status = "PASS" if reviews and all(r["status"] == "PASS" for r in reviews) else "BLOCKED"
    payload = {
        "status": status,
        "scope": "summary-figure-visual-review",
        "full_visual_review_status": "BLOCKED",
        "reason": "Reviews compact summary figures only; full catalog visual review remains incomplete.",
        "review_count": len(reviews),
        "reviews": reviews,
        "generated_at": reviewed_at,
    }
    atomic_write_json(figure_dir / "visual_review.json", payload)

    md_lines = [
        "# Summary figure visual review",
        "",
        f"- **Status:** `{status}`",
        "- **Scope:** `summary-figure-visual-review`",
        "- **Full visual review:** `BLOCKED`",
        "",
        "| Figure | Status | Reviewer | Notes |",
        "|---|---:|---|---|",
    ]
    for review in reviews:
        md_lines.append(f"| {review['figure_id']} | {review['status']} | {review['reviewer']} | {review['notes']} |")
    (figure_dir / "visual_review.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    rows = "\n".join(
        f"<tr><td>{html.escape(str(r['figure_id']))}</td><td>{html.escape(r['status'])}</td><td>{html.escape(r['reviewer'])}</td><td>{html.escape(r['notes'])}</td></tr>"
        for r in reviews
    )
    (figure_dir / "visual_review.html").write_text(
        "<!doctype html>\n<html lang='en'><head><meta charset='utf-8'><title>Summary figure visual review</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:980px;margin:2rem auto;line-height:1.5}table{border-collapse:collapse;width:100%}td,th{border:1px solid #d0d7de;padding:.45rem;text-align:left}</style></head><body>"
        f"<h1>Summary figure visual review</h1><p>Status: <code>{html.escape(status)}</code>; full visual review: <code>BLOCKED</code>.</p>"
        f"<table><thead><tr><th>Figure</th><th>Status</th><th>Reviewer</th><th>Notes</th></tr></thead><tbody>{rows}</tbody></table>"
        "</body></html>\n",
        encoding="utf-8",
    )
    return payload
