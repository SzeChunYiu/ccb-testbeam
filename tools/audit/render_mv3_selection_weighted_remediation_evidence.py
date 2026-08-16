#!/usr/bin/env python3
"""Render synthetic MV3 weighting-contract evidence as a standalone SVG."""
from __future__ import annotations

import argparse
import html
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid validation record {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("validation record root must be an object")
    return payload


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def render(payload: dict[str, Any]) -> str:
    control = payload.get("synthetic_control")
    if not isinstance(control, dict):
        raise ValueError("synthetic_control is missing")
    weighted = control.get("weighted_profile")
    unweighted = control.get("unweighted_sensitivity")
    if not isinstance(weighted, dict) or not isinstance(unweighted, dict):
        raise ValueError("weighted and unweighted profiles are required")
    values = {
        "weighted_b2": float(weighted["B2"]),
        "weighted_b8": float(weighted["B8"]),
        "unweighted_b2": float(unweighted["B2"]),
        "unweighted_b8": float(unweighted["B8"]),
    }
    if any(not 0.0 <= value <= 1.0 for value in values.values()):
        raise ValueError("profile values must lie in [0, 1]")
    bars = []
    labels = [
        ("Weighted B2", values["weighted_b2"], 120, "solid"),
        ("Weighted B8", values["weighted_b8"], 240, "solid"),
        ("Unweighted B2", values["unweighted_b2"], 420, "hatched"),
        ("Unweighted B8", values["unweighted_b8"], 540, "hatched"),
    ]
    baseline = 430
    scale = 300
    for label, value, x, fill in labels:
        height = value * scale
        y = baseline - height
        fill_value = "url(#hatch)" if fill == "hatched" else "#4c78a8"
        bars.extend(
            [
                (
                    f'<rect x="{x}" y="{y:.2f}" width="80" height="{height:.2f}" '
                    f'fill="{fill_value}" stroke="#111"/>'
                ),
                (
                    f'<text x="{x + 40}" y="{y - 8:.2f}" text-anchor="middle" '
                    f'font-size="18">{value:.1f}</text>'
                ),
                (
                    f'<text x="{x + 40}" y="458" text-anchor="middle" font-size="15">'
                    f'{html.escape(label)}</text>'
                ),
            ]
        )
    status = html.escape(str(payload.get("status", "UNKNOWN")))
    policy = html.escape(str(payload.get("policy", "")))
    ess = float(control["effective_sample_size"])
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="760" height="590" '
        'viewBox="0 0 760 590">',
        '<defs><pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(45)"><rect width="8" height="8" fill="#f2f2f2"/>'
        '<line x1="0" y1="0" x2="0" y2="8" stroke="#555" stroke-width="2"/>'
        '</pattern></defs>',
        '<rect width="760" height="590" fill="white"/>',
        '<text x="380" y="42" text-anchor="middle" font-size="25" font-weight="bold">'
        'MV3 weighting-contract synthetic control</text>',
        f'<text x="380" y="72" text-anchor="middle" font-size="16">{status}</text>',
        '<line x1="80" y1="430" x2="680" y2="430" stroke="#111"/>',
        '<line x1="80" y1="130" x2="80" y2="430" stroke="#111"/>',
        '<text x="32" y="285" transform="rotate(-90 32 285)" text-anchor="middle" '
        'font-size="17">Profile fraction</text>',
        '<text x="75" y="435" text-anchor="end" font-size="14">0.0</text>',
        '<text x="75" y="285" text-anchor="end" font-size="14">0.5</text>',
        '<text x="75" y="135" text-anchor="end" font-size="14">1.0</text>',
        *bars,
        f'<text x="380" y="510" text-anchor="middle" font-size="15">'
        f'Synthetic weights 1 and 9: ESS = {ess:.6f}</text>',
        f'<text x="380" y="538" text-anchor="middle" font-size="13">'
        f'Policy: {policy}</text>',
        '<text x="380" y="566" text-anchor="middle" font-size="13" font-weight="bold">'
        'Software/provenance validation only — not detector data</text>',
        '</svg>',
        '',
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.validation.resolve(strict=False) == args.out.resolve(strict=False):
        raise ValueError("output aliases validation input")
    _atomic_text(args.out, render(_load(args.validation)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
