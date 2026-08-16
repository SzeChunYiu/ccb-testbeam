#!/usr/bin/env python3
"""Render deterministic SVG evidence for the issue #880 semantics audit."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


def _text(x: int, y: int, value: str, *, size: int = 18, weight: str = "normal") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="DejaVu Sans, sans-serif" '
        f'font-size="{size}" font-weight="{weight}">{html.escape(value)}</text>'
    )


def _bar(x: int, y: int, width: float, height: int, label: str, value: str, fill: str) -> str:
    safe_width = max(0.0, width)
    return "\n".join(
        [
            f'<rect x="{x}" y="{y}" width="{safe_width:.1f}" height="{height}" '
            f'fill="{fill}" stroke="#111" stroke-width="2"/>',
            _text(x, y - 8, label, size=16, weight="bold"),
            _text(x + int(safe_width) + 10, y + height - 8, value, size=16),
        ]
    )


def render(payload: dict[str, Any]) -> str:
    observed = payload["observed"]
    calc = payload["independent_recalculation"]

    mean_u = float(observed["mean_unweighted"])
    mean_w = float(observed["mean_weighted"])
    frac_u = float(observed["fraction_unweighted"])
    frac_w = float(observed["fraction_weighted"])

    mean_scale = 340.0 / max(mean_u, mean_w)
    frac_scale = 340.0 / max(frac_u, frac_w)

    items = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="760" '
        'viewBox="0 0 1200 760">',
        '<rect width="1200" height="760" fill="white"/>',
        _text(50, 55, "Issue #880: directional weight-effect semantics", size=30, weight="bold"),
        _text(
            50,
            88,
            "Independent recalculation from the tracked 1,000,000-event summary; not a ROOT rerun",
            size=17,
        ),
        '<line x1="50" y1="110" x2="1150" y2="110" stroke="#333" stroke-width="2"/>',
        _text(60, 155, "First B-layer mean energy deposit [MeV]", size=22, weight="bold"),
        _bar(80, 205, mean_u * mean_scale, 52, "Legacy unweighted", f"{mean_u:.3f}", "#d9d9d9"),
        _bar(80, 300, mean_w * mean_scale, 52, "PrimaryWeighted", f"{mean_w:.3f}", "#9ecae1"),
        _text(
            60,
            400,
            "Weighted change relative to unweighted: "
            f"{calc['weighted_change_relative_to_unweighted_pct']:+.1f}%",
            size=18,
        ),
        _text(
            60,
            432,
            "Legacy unweighted overstatement relative to weighted: "
            f"{calc['legacy_unweighted_overstatement_relative_to_weighted_pct']:+.1f}%",
            size=18,
            weight="bold",
        ),
        _text(630, 155, "Entering-B deuteron fraction", size=22, weight="bold"),
        _bar(
            650,
            205,
            frac_u * frac_scale,
            52,
            "Legacy unweighted",
            f"{100.0 * frac_u:.2f}%",
            "#d9d9d9",
        ),
        _bar(
            650,
            300,
            frac_w * frac_scale,
            52,
            "PrimaryWeighted",
            f"{100.0 * frac_w:.2f}%",
            "#9ecae1",
        ),
        _text(
            630,
            400,
            "Legacy minus weighted: "
            f"{calc['legacy_unweighted_minus_weighted_pp']:+.2f} percentage points",
            size=18,
        ),
        _text(
            630,
            432,
            "Legacy overstatement relative to weighted: "
            f"{calc['legacy_deuteron_overstatement_relative_to_weighted_pct']:+.1f}%",
            size=18,
            weight="bold",
        ),
        '<line x1="50" y1="485" x2="1150" y2="485" stroke="#333" stroke-width="2"/>',
        _text(60, 530, "Confirmed software/reporting defects", size=22, weight="bold"),
        _text(
            80,
            570,
            "1. Nonfinite weights are converted to unit weight instead of failing closed.",
            size=18,
        ),
        _text(
            80,
            605,
            "2. Invalid weighted estimators fall back to unweighted estimators.",
            size=18,
        ),
        _text(
            80,
            640,
            "3. Signed fields describe weighted − unweighted, while prose calls them legacy bias.",
            size=18,
        ),
        _text(
            80,
            675,
            (
                "4. The retained result omits ROOT SHA-256, producer commit, command, "
                "and weight policy."
            ),
            size=18,
        ),
        _text(
            50,
            730,
            (
                "Acceptance: audit gate validated; retained physics result remains FLAWED "
                "pending strict rerun."
            ),
            size=18,
            weight="bold",
        ),
        "</svg>",
    ]
    return "\n".join(items) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("validation_json", type=Path)
    parser.add_argument("output_svg", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.validation_json.read_text(encoding="utf-8"))
    args.output_svg.parent.mkdir(parents=True, exist_ok=True)
    args.output_svg.write_text(render(payload), encoding="utf-8")


if __name__ == "__main__":
    main()
