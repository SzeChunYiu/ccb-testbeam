#!/usr/bin/env python3
"""Render synthetic visual evidence for the DeltaE Parquet snapshot contract."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def render(payload: dict, output: Path) -> None:
    controls = payload["controls"]
    status = payload["status"]
    source = payload["source"]
    former_sha = controls["former_post_read_manifest_sha256"][:12]
    parsed_sha = controls["parsed_sha256"][:12]
    current_sha = controls["single_snapshot_manifest_sha256"][:12]
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="720" '
        'viewBox="0 0 1200 720">',
        '<rect width="1200" height="720" fill="white"/>',
        '<style>text{font-family:DejaVu Sans,Arial,sans-serif;fill:#111}'
        '.title{font-size:28px;font-weight:700}.head{font-size:21px;font-weight:700}'
        '.body{font-size:17px}.small{font-size:14px}.box{fill:#f5f5f5;stroke:#111;stroke-width:2}'
        '.bad{fill:none;stroke:#111;stroke-width:4;stroke-dasharray:10 7}'
        '.good{fill:none;stroke:#111;stroke-width:4}.cross{stroke:#111;stroke-width:5}'
        '</style>',
        '<text x="45" y="50" class="title">DeltaE Parquet input provenance</text>',
        '<text x="45" y="82" class="body">Synthetic software/provenance evidence'
        ' — not detector data</text>',
        '<rect x="45" y="115" width="525" height="440" class="box"/>',
        '<rect x="630" y="115" width="525" height="440" class="box"/>',
        '<text x="75" y="155" class="head">Former split-read path</text>',
        '<text x="660" y="155" class="head">Current one-snapshot path</text>',
        '<text x="75" y="205" class="body">1. pandas reads mutable path A</text>',
        '<text x="75" y="245" class="body">2. path is replaced by bytes B</text>',
        '<text x="75" y="285" class="body">3. manifest hashes current path B</text>',
        f'<text x="75" y="335" class="body">parsed SHA: {parsed_sha}</text>',
        f'<text x="75" y="375" class="body">manifest SHA: {former_sha}</text>',
        '<text x="75" y="425" class="head">ROWS ≠ MANIFEST BYTES</text>',
        '<line x1="70" y1="185" x2="540" y2="450" class="cross"/>',
        '<line x1="540" y1="185" x2="70" y2="450" class="cross"/>',
        '<text x="660" y="205" class="body">1. read exact bytes A once</text>',
        '<text x="660" y="245" class="body">2. parse io.BytesIO(A)</text>',
        '<text x="660" y="285" class="body">3. manifest reuses retained A</text>',
        f'<text x="660" y="335" class="body">parsed SHA: {parsed_sha}</text>',
        f'<text x="660" y="375" class="body">manifest SHA: {current_sha}</text>',
        '<text x="660" y="425" class="head">ROWS = MANIFEST BYTES</text>',
        '<rect x="655" y="180" width="470" height="285" class="good"/>',
        f'<text x="45" y="600" class="head">Audit status: {html.escape(status)}</text>',
        f'<text x="45" y="635" class="body">Source bytes: {source["bytes"]}; '
        f'SHA-256: {html.escape(source["sha256"])}</text>',
        '<text x="45" y="670" class="small">Policy: '
        'DELTAE_PARQUET_ROWS_AND_PROVENANCE_MUST_SHARE_ONE_BYTE_SNAPSHOT</text>',
        '<text x="45" y="698" class="small">Success means parser/provenance identity only; '
        'A-002 physics remains blocked.</text>',
        '</svg>',
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    render(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
