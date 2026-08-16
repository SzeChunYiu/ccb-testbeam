#!/usr/bin/env python3
"""Render the Chapter 8 MV1 source-binding validation record as an SVG."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape

WIDTH = 1120
HEIGHT = 720


def line(x: int, y: int, text: str, *, size: int = 18, weight: str = "normal") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="DejaVu Sans, sans-serif" '
        f'font-size="{size}" font-weight="{weight}">{escape(text)}</text>'
    )


def render(record: dict, output: Path) -> None:
    source = record["source_contract"]
    tests = record["validation"]
    old = record["former_chapter_findings"]
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<rect width="1120" height="720" fill="white"/>',
        (
            '<rect x="28" y="28" width="1064" height="664" fill="none" '
            'stroke="black" stroke-width="2"/>'
        ),
        line(54, 70, "Chapter 8 MV1 claim remediation", size=28, weight="bold"),
        line(54, 102, "Software/documentation evidence — not beam-data PID performance", size=17),
        '<line x1="54" y1="122" x2="1066" y2="122" stroke="black"/>',
        line(54, 160, "Former chapter: source-contract violations", size=21, weight="bold"),
    ]
    y = 192
    for item in old[:7]:
        elements.append(line(72, y, f"• {item}", size=16))
        y += 29
    elements.extend(
        [
            '<line x1="54" y1="410" x2="1066" y2="410" stroke="black"/>',
            line(54, 448, "Tracked MV1 fixed outputs", size=21, weight="bold"),
            line(
                72,
                482,
                f"p/d tracks: {source['n_pd']:,} of {source['n_tracks']:,} charged B-arm tracks",
                size=17,
            ),
            line(
                72,
                512,
                f"Logistic regression: AUC {source['logreg_auc']}; "
                f"purity {source['logreg_purity_at_90eff']}",
                size=17,
            ),
            line(
                72,
                542,
                f"HGB: AUC {source['hgb_auc']}; "
                f"purity {source['hgb_purity_at_90eff']}",
                size=17,
            ),
            line(
                72,
                572,
                f"Traditional cut: purity {source['cut_purity']}; "
                f"efficiency {source['cut_efficiency']}",
                size=17,
            ),
            line(54, 616, "Acceptance boundary", size=21, weight="bold"),
            line(
                72,
                646,
                "GATED / truth-labelled MC / row-index parity split / no CI / "
                "BLK-MV1-001",
                size=17,
            ),
            line(
                72,
                676,
                f"Focused regression: {tests['pytest_result']}; accepted issues: 0; "
                f"stale issues: {tests['stale_fixture_issue_count']}",
                size=17,
            ),
        ]
    )
    elements.append("</svg>")
    output.write_text("\n".join(elements) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-json", type=Path, required=True)
    parser.add_argument("--output-svg", type=Path, required=True)
    args = parser.parse_args()
    record = json.loads(args.validation_json.read_text(encoding="utf-8"))
    render(record, args.output_svg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
