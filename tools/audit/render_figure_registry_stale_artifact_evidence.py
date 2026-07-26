#!/usr/bin/env python3
"""Render SVG evidence for the figure-registry stale-artifact audit."""

from __future__ import annotations

import argparse
import html
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _bar(x: int, y: int, value: int, label: str) -> str:
    width = 120 * value
    safe = html.escape(label)
    return (
        f'<text x="{x}" y="{y - 8}" font-size="16">{safe}</text>'
        f'<rect x="{x}" y="{y}" width="{width}" height="30" '
        'fill="#9a9a9a" stroke="#222"/>'
        f'<text x="{x + width + 12}" y="{y + 22}" font-size="18">{value}</text>'
    )


def render(payload: dict[str, Any]) -> str:
    current = payload["controls"]["current_no_cleanup_model"]
    corrected = payload["controls"]["corrected_cleanup_model"]
    scenarios = ["blocked", "failed", "removed"]
    pieces = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="680" '
        'viewBox="0 0 1100 680">',
        '<rect width="1100" height="680" fill="white"/>',
        '<text x="50" y="55" font-size="28" font-weight="bold">'
        'Figure-registry stale managed artifacts</text>',
        '<text x="50" y="90" font-size="17">'
        'Deterministic control: two prior managed files per entry scenario</text>',
        '<text x="50" y="135" font-size="20" font-weight="bold">'
        'Current no-cleanup contract</text>',
    ]
    y = 175
    for scenario in scenarios:
        pieces.append(
            _bar(80, y, int(current[scenario]["stale_count"]), scenario.upper())
        )
        y += 75
    pieces.extend(
        [
            '<text x="570" y="135" font-size="20" font-weight="bold">'
            'Required fail-closed cleanup</text>',
        ]
    )
    y = 175
    for scenario in scenarios:
        pieces.append(
            _bar(600, y, int(corrected[scenario]["stale_count"]), scenario.upper())
        )
        y += 75
    findings = len(payload["findings"])
    pieces.extend(
        [
            '<line x1="50" y1="430" x2="1050" y2="430" stroke="#444"/>',
            f'<text x="50" y="475" font-size="22">Audit status: '
            f'{html.escape(payload["status"])}</text>',
            f'<text x="50" y="510" font-size="18">Finding families: {findings}</text>',
            '<text x="50" y="550" font-size="17">A BLOCKED, QUARANTINED, '
            'failed, or removed entry must not leave an older paper artifact.</text>',
            '<text x="50" y="585" font-size="17">This is software/provenance '
            'evidence; no scientific central value is evaluated.</text>',
            '<text x="50" y="635" font-size="14">Policy: '
            f'{html.escape(payload["policy"])}</text>',
            '</svg>',
        ]
    )
    return "".join(pieces)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--output-svg", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    _atomic_write(Path(args.output_svg), render(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
