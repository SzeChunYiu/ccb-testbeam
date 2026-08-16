#!/usr/bin/env python3
"""Render the issue #880 strict-producer validation record as deterministic SVG."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape


def text(x: int, y: int, value: str, *, size: int = 18, weight: str = "normal") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="sans-serif" font-size="{size}" '
        f'font-weight="{weight}">{escape(value)}</text>'
    )


def rect(x: int, y: int, width: int, height: int, *, fill: str, stroke: str = "#222") -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="12" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
    )


def render(record: dict) -> str:
    retained = record["independent_retained_arithmetic"]
    test_result = record["validation"]["pytest"]
    elements = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="900" '
        'viewBox="0 0 1400 900">',
        '<rect width="1400" height="900" fill="#fafafa"/>',
        text(55, 65, "Issue #880 strict event-weight producer remediation", size=30, weight="bold"),
        text(55, 100, "Synthetic software/provenance evidence — not detector data", size=18),
        rect(55, 145, 610, 270, fill="#ffe8e8"),
        text(85, 190, "Retained producer (blocked)", size=24, weight="bold"),
        text(85, 230, "• nonfinite PrimaryWeight → 1.0", size=19),
        text(85, 265, "• weighted helpers may fall back to unweighted", size=19),
        text(85, 300, "• relative-bias direction/denominator ambiguous", size=19),
        text(85, 335, "• ROOT digest and producer commit absent", size=19),
        text(
            85,
            380,
            f"historical blob: {record['repository_inputs']['historical_producer_blob']}",
            size=15,
        ),
        rect(735, 145, 610, 270, fill="#e7f7ea"),
        text(765, 190, "Strict replacement (validated code)", size=24, weight="bold"),
        text(765, 230, "• exactly one finite nonnegative weight per event", size=19),
        text(765, 265, "• no epsilon or unweighted estimator fallback", size=19),
        text(765, 300, "• both comparison directions name denominators", size=19),
        text(765, 335, "• ROOT SHA-256 checked before and after read", size=19),
        text(765, 370, "• clean git commit + script hashes + atomic JSON", size=19),
        text(765, 400, f"focused tests: {test_result}", size=17, weight="bold"),
        rect(55, 465, 1290, 235, fill="#eef3ff"),
        text(
            85,
            510,
            "Independent reconstruction of retained directional semantics",
            size=23,
            weight="bold",
        ),
        text(
            85,
            555,
            "First-B mean: weighted change vs unweighted = "
            f"{retained['first_B_weighted_minus_unweighted_pct_of_abs_unweighted']:+.6f}%",
            size=19,
        ),
        text(
            85,
            595,
            "First-B mean: legacy unweighted overstatement vs weighted = "
            f"{retained['first_B_legacy_overstatement_pct_of_abs_weighted']:+.6f}%",
            size=19,
        ),
        text(
            85,
            635,
            "Deuteron fraction: legacy-minus-weighted = "
            f"{retained['deuteron_legacy_minus_weighted_percentage_points']:+.6f} "
            "percentage points",
            size=19,
        ),
        text(
            85,
            675,
            "Deuteron fraction: legacy overstatement vs weighted = "
            f"{retained['deuteron_legacy_overstatement_pct_of_abs_weighted']:+.6f}%",
            size=19,
        ),
        rect(55, 745, 1290, 105, fill="#fff6d8"),
        text(85, 790, "Acceptance boundary", size=22, weight="bold"),
        text(
            85,
            825,
            "Code and synthetic regressions are validated; exact 1M-event ROOT rerun, "
            "weighted uncertainty, tail stability, and data/MC closure remain required.",
            size=17,
        ),
        "</svg>",
    ]
    return "\n".join(elements) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    record = json.loads(args.record.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(record), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
