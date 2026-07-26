"""Render deterministic SVG evidence for AUD-FIG-005."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

POLICY = "FIGURE_BUILD_REPORT_MUST_BIND_TO_EXACT_REGISTRY_SNAPSHOT"


def _load(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid validation JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("validation payload must be an object")
    if payload.get("policy") != POLICY or payload.get("status") != "VALIDATED":
        raise ValueError("validation payload is not the accepted AUD-FIG-005 contract")
    return payload


def _svg(payload: dict[str, Any]) -> str:
    checks = payload["validation"]["checks"]
    metrics = [
        ("Registry identity fields", 0, 5),
        ("Controlled format failures", 0, 2),
        ("Focused tests", 0, int(checks["tests_passed"])),
    ]
    width, height = 1040, 560
    left, bar_x, bar_w = 48, 360, 560
    rows: list[str] = []
    y = 190
    for label, before, after in metrics:
        maximum = max(after, 1)
        before_w = int(bar_w * before / maximum)
        after_w = int(bar_w * after / maximum)
        rows.extend(
            [
                f'<text x="{left}" y="{y + 18}" font-size="20">{html.escape(label)}</text>',
                (
                    f'<rect x="{bar_x}" y="{y}" width="{bar_w}" height="28" '
                    'fill="none" stroke="black"/>'
                ),
                f'<rect x="{bar_x}" y="{y}" width="{before_w}" height="12" fill="black"/>',
                (
                    f'<rect x="{bar_x}" y="{y + 16}" width="{after_w}" '
                    'height="12" fill="none" stroke="black" stroke-width="3"/>'
                ),
                (
                    f'<text x="{bar_x + bar_w + 18}" y="{y + 11}" '
                    f'font-size="16">before {before}</text>'
                ),
                f'<text x="{bar_x + bar_w + 18}" y="{y + 29}" font-size="16">after {after}</text>',
            ]
        )
        y += 92
    base = html.escape(payload["base_main"][:12])
    validated = html.escape(payload["validated_main"][:12])
    return "\n".join(
        [
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
                f'height="{height}" viewBox="0 0 {width} {height}">'
            ),
            '<rect width="100%" height="100%" fill="white" stroke="black"/>',
            (
                '<text x="48" y="58" font-size="30" font-weight="bold">'
                'AUD-FIG-005 registry snapshot provenance</text>'
            ),
            (
                '<text x="48" y="94" font-size="18">build_report.json now '
                'identifies the exact duplicate-key-safe registry bytes</text>'
            ),
            (
                f'<text x="48" y="126" font-size="16">main {base} → '
                f'{validated} | status VALIDATED</text>'
            ),
            (
                '<text x="48" y="154" font-size="15">solid = former '
                'contract; outlined = corrected contract</text>'
            ),
            *rows,
            (
                '<text x="48" y="510" font-size="15">Scientific boundary: '
                'software/provenance only; no figure value or detector result was '
                'revalidated.</text>'
            ),
            '</svg>',
            '',
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = _load(args.validation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(_svg(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
