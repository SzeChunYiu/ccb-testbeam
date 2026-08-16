#!/usr/bin/env python3
"""Render deterministic SVG evidence for stale figure-artifact remediation."""
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


def render(payload: dict[str, Any]) -> str:
    scenarios = payload["controls"]
    rows = []
    y = 190
    for label in ("blocked", "failed", "removed", "kind_change"):
        values = scenarios[label]
        rows.append(
            f'<text x="70" y="{y}" font-size="18">{html.escape(label)}</text>'
            f'<rect x="280" y="{y - 22}" width="{values["before"] * 90}" '
            'height="28" fill="#aaa" stroke="#222"/>'
            f'<text x="480" y="{y}" font-size="18">{values["before"]}</text>'
            f'<rect x="610" y="{y - 22}" width="{values["after"] * 90}" '
            'height="28" fill="#ddd" stroke="#222"/>'
            f'<text x="810" y="{y}" font-size="18">{values["after"]}</text>'
        )
        y += 70
    return "".join(
        [
            '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="600" '
            'viewBox="0 0 1000 600">',
            '<rect width="1000" height="600" fill="white"/>',
            '<text x="50" y="55" font-size="28" font-weight="bold">'
            'Figure-registry managed-artifact lifecycle</text>',
            '<text x="50" y="90" font-size="17">'
            'Prior canonical files before and after the corrected build contract</text>',
            '<text x="280" y="135" font-size="19" font-weight="bold">before</text>',
            '<text x="610" y="135" font-size="19" font-weight="bold">after</text>',
            *rows,
            '<line x1="50" y1="485" x2="950" y2="485" stroke="#444"/>',
            f'<text x="50" y="525" font-size="20">status: '
            f'{html.escape(payload["status"])}</text>',
            '<text x="50" y="560" font-size="14">policy: '
            f'{html.escape(payload["policy"])}</text>',
            '</svg>',
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--output-svg", required=True)
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    _atomic_write(Path(args.output_svg), render(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
