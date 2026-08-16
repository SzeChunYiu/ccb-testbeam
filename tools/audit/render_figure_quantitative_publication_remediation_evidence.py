#!/usr/bin/env python3
"""Render the quantitative figure-publication remediation evidence as SVG."""
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
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _text(
    x: int,
    y: int,
    value: object,
    *,
    size: int = 16,
    weight: str = "normal",
) -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="sans-serif" font-size="{size}" '
        f'font-weight="{weight}">{html.escape(str(value))}</text>'
    )


def render(payload: dict[str, Any]) -> str:
    controls = payload["behavioral_controls"]
    tests = payload["validation"]["focused_tests"]
    rows = [
        (
            "Direct final-path render",
            "DESTROYS PRIOR TARGET",
            controls["former"]["prior_preserved"],
        ),
        (
            "Temporary PNG render failure",
            "PRESERVES PRIOR TARGET",
            controls["render_failure"]["prior_preserved"],
        ),
        (
            "Atomic publication failure",
            "PRESERVES PRIOR TARGET",
            controls["publish_failure"]["prior_preserved"],
        ),
        (
            "Successful publication",
            "HASH-BOUND PNG",
            controls["success"]["digest_matches_metadata"],
        ),
    ]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="650" viewBox="0 0 1100 650">',
        '<rect width="1100" height="650" fill="white"/>',
        _text(
            45,
            55,
            "AUD-FIG-003-R1: quantitative PNG publication remediation",
            size=25,
            weight="bold",
        ),
        _text(45, 88, payload["policy"], size=15),
        _text(
            45,
            120,
            f"status: {payload['status']} | focused tests: {tests['result']}",
            size=17,
            weight="bold",
        ),
    ]
    y = 175
    for label, interpretation, passed in rows:
        parts.append(
            f'<rect x="45" y="{y - 25}" width="1010" height="72" '
            'rx="8" fill="#f5f5f5" stroke="#222"/>'
        )
        parts.append(_text(70, y, label, size=18, weight="bold"))
        parts.append(_text(70, y + 29, interpretation, size=15))
        parts.append(
            _text(
                930,
                y + 10,
                "PASS" if passed else "FAIL",
                size=19,
                weight="bold",
            )
        )
        y += 92
    parts.extend(
        [
            _text(
                45,
                570,
                f"builder blob: {payload['sources']['builder']['git_blob']}",
                size=14,
            ),
            _text(
                45,
                596,
                f"builder sha256: {payload['sources']['builder']['sha256']}",
                size=14,
            ),
            _text(
                45,
                622,
                "Scientific boundary: artifact integrity only; "
                "no plotted physics value was revalidated.",
                size=14,
            ),
            "</svg>",
        ]
    )
    return "\n".join(parts) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    _atomic_write(args.output, render(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
