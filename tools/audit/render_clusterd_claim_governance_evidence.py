#!/usr/bin/env python3
"""Render Cluster D claim-governance validation evidence as a standalone SVG."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

VERSION = "1.0.0"


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("validation input must be a JSON object")
    return payload


def _text(x: int, y: int, value: str, size: int = 18, weight: str = "normal") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="sans-serif" font-size="{size}" '
        f'font-weight="{weight}">{html.escape(value)}</text>'
    )


def render(payload: dict[str, Any]) -> str:
    status = str(payload.get("status", "UNKNOWN"))
    findings = int(payload.get("n_issues", -1))
    initial = str(payload.get("initial_main_sha", "unknown"))[:12]
    delivered = str(payload.get("delivery_main_sha", "pending"))[:12]
    rows = [
        ("MV0", "PASS / production", "KS=0.1077; chi2/ndf=2928; stave mismatch", "GATED proxy"),
        ("MV5", "Rmax=3.04 MHz", "duty-factor product; recovery ceiling null", "BLOCKED"),
        (
            "MV6",
            "data species identified",
            "25/38 truth-MC; cluster purity 46.4%",
            "TRUTH MC ONLY",
        ),
        (
            "VIS-MC",
            "proves simulation",
            "internal/toy closure and embedded PSTAR table",
            "DIAGNOSTIC",
        ),
    ]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="720" '
        'viewBox="0 0 1200 720">',
        '<rect width="1200" height="720" fill="white"/>',
        '<rect x="30" y="25" width="1140" height="80" rx="12" fill="#eef3f8"/>',
        _text(55, 62, "Cluster D scientific-claim governance", 28, "bold"),
        _text(
            55,
            91,
            f"status={status}  findings={findings}  main {initial} → {delivered}",
            16,
        ),
    ]
    headers = [
        (45, "Area"),
        (180, "Merged wording"),
        (465, "Tracked evidence"),
        (940, "Corrected state"),
    ]
    for x, label in headers:
        parts.append(_text(x, 145, label, 17, "bold"))
    y = 175
    for index, (area, old, evidence, state) in enumerate(rows):
        fill = "#f8fafc" if index % 2 == 0 else "#eef3f8"
        parts.append(f'<rect x="30" y="{y}" width="1140" height="92" rx="8" fill="{fill}"/>')
        parts.append(_text(45, y + 35, area, 20, "bold"))
        parts.append(_text(180, y + 35, old, 17))
        parts.append(_text(465, y + 35, evidence, 16))
        parts.append(_text(940, y + 35, state, 18, "bold"))
        y += 102
    parts.extend([
        '<rect x="30" y="600" width="1140" height="82" rx="10" fill="#fff5e6"/>',
        _text(50, 632, "Boundary", 18, "bold"),
        _text(
            150,
            632,
            "Documentation and source-binding validation; no raw data or simulation rerun.",
            17,
        ),
        _text(50, 660, "Policy", 18, "bold"),
        _text(150, 660, str(payload.get("policy", "unknown")), 15),
        (
            '<metadata>renderer=render_clusterd_claim_governance_evidence.py;'
            f'version={VERSION}</metadata>'
        ),
        '</svg>',
    ])
    return "\n".join(parts) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("validation_json", type=Path)
    parser.add_argument("output_svg", type=Path)
    args = parser.parse_args()
    payload = _load(args.validation_json)
    args.output_svg.parent.mkdir(parents=True, exist_ok=True)
    args.output_svg.write_text(render(payload), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
