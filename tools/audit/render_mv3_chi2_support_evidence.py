#!/usr/bin/env python3
"""Render text-first SVG evidence for the MV3 chi-square support audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape


def render(record: dict, output: Path) -> None:
    outside = record["controls"]["positive_observed_zero_expected"]
    nonunit = record["controls"]["nonunit_model_profile"]
    lines = [
        "MV3 Pearson chi-square support audit",
        f"Status: {record['status']} | findings: {record['finding_count']}",
        "Synthetic control A: model fractions [0.50, 0.50, 0, 0]",
        "Observed counts [45, 45, 10, 0] include B6=10 where expected B6=0.",
        (
            f"Current behavior: {outside['outcome']} chi2={outside.get('chi2')} "
            f"ndf={outside.get('ndf')}"
        ),
        "Required behavior: reject as CHI2_OBSERVED_OUTSIDE_MODEL_SUPPORT.",
        "Synthetic control B: model fractions sum to 0.95.",
        f"Current behavior: {nonunit['outcome']} chi2={nonunit.get('chi2')}",
        "Required behavior: reject as CHI2_PROFILE_NOT_NORMALIZED.",
        "Evidence class: synthetic software/statistical validation, not detector data.",
    ]
    height = 90 + 34 * len(lines)
    text = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" '
        'viewBox="0 0 1200 {0}">'.format(height),
        '<rect x="1" y="1" width="1198" height="{0}" fill="white" stroke="black"/>'.format(
            height - 2
        ),
    ]
    for index, line in enumerate(lines):
        size = 26 if index == 0 else 19
        weight = "bold" if index in (0, 1, 5, 8) else "normal"
        text.append(
            f'<text x="38" y="{55 + index * 34}" font-family="sans-serif" '
            f'font-size="{size}" font-weight="{weight}" fill="black">{escape(str(line))}</text>'
        )
    text.append("</svg>\n")
    output.write_text("\n".join(text), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    record = json.loads(args.input.read_text(encoding="utf-8"))
    render(record, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
