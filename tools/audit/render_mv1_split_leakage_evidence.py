#!/usr/bin/env python3
"""Render synthetic visual evidence for the audited MV1 split contract."""

from __future__ import annotations

import argparse
import html
from pathlib import Path

POLICY = "LEGACY_MV1_PID_OUTPUTS_REQUIRE_GROUP_DISJOINT_RERUN_AND_UNCERTAINTY"


def render(path: Path) -> None:
    width = 1040
    height = 650
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Legacy MV1 row-index split versus group-disjoint split</title>',
        '<desc id="desc">Synthetic software-method evidence. Two events each contribute '
        'two tracks. Row-index parity places tracks from each event in both train and test, '
        'whereas a group-disjoint split keeps each event on one side.</desc>',
        '<defs><pattern id="diag" width="8" height="8" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="8" '
        'stroke="#333" stroke-width="2"/></pattern></defs>',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="30" y="38" font-family="sans-serif" font-size="24" '
        'font-weight="bold">MV1 PID split audit</text>',
        '<text x="30" y="66" font-family="sans-serif" font-size="14">'
        'Synthetic regression evidence — not beam data and not a performance estimate.</text>',
        '<text x="30" y="102" font-family="sans-serif" font-size="16" '
        'font-weight="bold">Legacy producer: row index parity</text>',
    ]

    labels = [
        ("Event A / track 0", "TRAIN", 0),
        ("Event A / track 1", "TEST", 1),
        ("Event B / track 0", "TRAIN", 2),
        ("Event B / track 1", "TEST", 3),
    ]
    y0 = 125
    for index, (track, split, row_index) in enumerate(labels):
        y = y0 + index * 48
        fill = "#dddddd" if split == "TRAIN" else "url(#diag)"
        parts.extend(
            [
                f'<text x="45" y="{y + 27}" font-family="monospace" font-size="14">'
                f'row {row_index}: {html.escape(track)}</text>',
                f'<rect x="340" y="{y + 7}" width="180" height="30" fill="{fill}" '
                'stroke="black"/>',
                f'<text x="430" y="{y + 28}" text-anchor="middle" '
                f'font-family="sans-serif" font-size="14">{split}</text>',
            ]
        )
    parts.extend(
        [
            '<text x="560" y="170" font-family="sans-serif" font-size="15" '
            'font-weight="bold">Failure mode</text>',
            '<text x="560" y="198" font-family="sans-serif" font-size="14">'
            'Each event appears in both train and test.</text>',
            '<text x="560" y="224" font-family="sans-serif" font-size="14">'
            'Event-correlated detector or generator features can leak.</text>',
            '<text x="30" y="350" font-family="sans-serif" font-size="16" '
            'font-weight="bold">Required remediation: group-disjoint event split</text>',
        ]
    )
    groups = [
        ("Event A / tracks 0 and 1", "TRAIN", 380),
        ("Event B / tracks 0 and 1", "TEST", 440),
    ]
    for text, split, y in groups:
        fill = "#dddddd" if split == "TRAIN" else "url(#diag)"
        parts.extend(
            [
                f'<text x="45" y="{y + 27}" font-family="monospace" font-size="14">'
                f'{html.escape(text)}</text>',
                f'<rect x="340" y="{y + 7}" width="180" height="30" fill="{fill}" '
                'stroke="black"/>',
                f'<text x="430" y="{y + 28}" text-anchor="middle" '
                f'font-family="sans-serif" font-size="14">{split}</text>',
            ]
        )
    parts.extend(
        [
            '<text x="560" y="414" font-family="sans-serif" font-size="15" '
            'font-weight="bold">Acceptance boundary</text>',
            '<text x="560" y="442" font-family="sans-serif" font-size="14">'
            'Keep every event wholly in train or test.</text>',
            '<text x="560" y="468" font-family="sans-serif" font-size="14">'
            'Rerun the exact 400369-track source and evaluate uncertainty.</text>',
            '<line x1="30" y1="515" x2="1010" y2="515" stroke="black"/>',
            '<text x="30" y="548" font-family="sans-serif" font-size="14">'
            'Legacy fixed outputs: HGB AUC 0.9859658513538254; purity@nominal 90% '
            'efficiency 0.9644090769970706.</text>',
            '<text x="30" y="576" font-family="sans-serif" font-size="14">'
            'These values are GATED: no event-group-disjoint rerun, no uncertainty, '
            'and no beam-data PID closure.</text>',
            f'<text x="30" y="618" font-family="sans-serif" font-size="12">Policy: '
            f'{html.escape(POLICY)}</text>',
            '</svg>',
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    render(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
