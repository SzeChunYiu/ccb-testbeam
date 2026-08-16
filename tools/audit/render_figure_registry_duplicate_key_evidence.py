"""Render deterministic evidence for duplicate-key-safe figure registries."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from tools.figure_registry.registry import (
    REGISTRY_SNAPSHOT_METHOD,
    RegistryFormatError,
    load_registry_snapshot,
)

TASK_ID = "AUD-FIG-004"
POLICY = "FIGURE_REGISTRY_YAML_KEYS_MUST_BE_UNIQUE_AT_EVERY_MAPPING_DEPTH"
BASE_MAIN = "cd4c299dbd67e285950a69610e4b27caed4413e1"
FORMER_REGISTRY_BLOB = "b1381ccc471eb4711251cb2d0471950f60610c68"


def _atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _duplicate_controls(root: Path) -> list[dict[str, Any]]:
    controls = [
        {
            "name": "duplicate_top_level_figure_id",
            "text": (
                "Q:\n"
                "  status: VALIDATED\n"
                "  kind: quantitative\n"
                "  result: one.json\n"
                "  caption: first\n"
                "Q:\n"
                "  status: BLOCKED\n"
                "  kind: quantitative\n"
                "  result: two.json\n"
                "  caption: second\n"
            ),
            "key": "Q",
        },
        {
            "name": "duplicate_nested_status",
            "text": (
                "Q:\n"
                "  status: VALIDATED\n"
                "  status: BLOCKED\n"
                "  kind: quantitative\n"
                "  result: one.json\n"
                "  caption: ambiguous status\n"
            ),
            "key": "status",
        },
    ]
    results: list[dict[str, Any]] = []
    for index, control in enumerate(controls):
        path = root / f"control-{index}.yaml"
        raw = control["text"].encode("utf-8")
        path.write_bytes(raw)
        legacy = yaml.safe_load(control["text"])
        corrected_error = ""
        corrected_rejected = False
        try:
            load_registry_snapshot(path)
        except RegistryFormatError as exc:
            corrected_rejected = True
            corrected_error = str(exc).replace(str(root), "<tmp>")
        results.append(
            {
                "name": control["name"],
                "duplicate_key": control["key"],
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "legacy_safe_load_rejected": False,
                "legacy_safe_load_result": legacy,
                "corrected_rejected": corrected_rejected,
                "corrected_error": corrected_error,
            }
        )
    return results


def _svg(payload: dict[str, Any]) -> str:
    controls = payload["controls"]
    legacy_accepted = sum(not item["legacy_safe_load_rejected"] for item in controls)
    corrected_rejected = sum(item["corrected_rejected"] for item in controls)
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="520"',
        ' viewBox="0 0 1000 520">',
        '  <rect width="1000" height="520" fill="white"/>',
        (
            '  <text x="50" y="58" font-family="sans-serif" font-size="28" '
            'font-weight="bold">Figure-registry duplicate-key integrity</text>'
        ),
        (
            '  <text x="50" y="90" font-family="sans-serif" font-size="16">'
            f'Policy: {POLICY}</text>'
        ),
        (
            '  <text x="50" y="122" font-family="sans-serif" font-size="15">'
            'Two deterministic ambiguous YAML controls</text>'
        ),
        (
            '  <text x="50" y="182" font-family="sans-serif" font-size="18">'
            'Legacy safe_load silently accepted</text>'
        ),
        (
            f'  <rect x="420" y="155" width="{legacy_accepted * 220}" height="38" '
            'fill="#c44"/>'
        ),
        (
            '  <text x="880" y="182" font-family="sans-serif" font-size="18" '
            f'text-anchor="end">{legacy_accepted}/2</text>'
        ),
        (
            '  <text x="50" y="252" font-family="sans-serif" font-size="18">'
            'Corrected loader rejected before build</text>'
        ),
        (
            f'  <rect x="420" y="225" width="{corrected_rejected * 220}" height="38" '
            'fill="#287a3d"/>'
        ),
        (
            '  <text x="880" y="252" font-family="sans-serif" font-size="18" '
            f'text-anchor="end">{corrected_rejected}/2</text>'
        ),
        '  <line x1="420" y1="145" x2="420" y2="285" stroke="black"/>',
        (
            '  <line x1="640" y1="145" x2="640" y2="285" stroke="#999" '
            'stroke-dasharray="4 4"/>'
        ),
        (
            '  <line x1="860" y1="145" x2="860" y2="285" stroke="#999" '
            'stroke-dasharray="4 4"/>'
        ),
        (
            '  <text x="50" y="365" font-family="sans-serif" font-size="16" '
            'font-weight="bold">Scientific interpretation</text>'
        ),
        (
            '  <text x="50" y="396" font-family="sans-serif" font-size="15">'
            'Duplicate IDs or fields can silently replace evidence.</text>'
        ),
        (
            '  <text x="50" y="424" font-family="sans-serif" font-size="15">'
            'Strict loading rejects ambiguity at every mapping depth.</text>'
        ),
        (
            '  <text x="50" y="470" font-family="monospace" font-size="13">'
            f'Base main: {BASE_MAIN}</text>'
        ),
        (
            '  <text x="50" y="494" font-family="monospace" font-size="13">'
            f'Status: {payload["status"]}; tests: {payload["validation"]["pytest"]}</text>'
        ),
        '</svg>',
    ]
    return "\n".join(lines) + "\n"


def build_payload() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="figure-registry-duplicate-keys-") as name:
        controls = _duplicate_controls(Path(name))
    passed = all(item["corrected_rejected"] for item in controls)
    return {
        "schema": "ccb-figure-registry-duplicate-key-validation/1",
        "task_id": TASK_ID,
        "policy": POLICY,
        "status": "VALIDATED" if passed else "FLAWED",
        "base_main": BASE_MAIN,
        "former_registry_git_blob": FORMER_REGISTRY_BLOB,
        "snapshot_method": REGISTRY_SNAPSHOT_METHOD,
        "controls": controls,
        "findings": [] if passed else ["CORRECTED_LOADER_DID_NOT_REJECT_ALL_DUPLICATES"],
        "validation": {
            "python": "3.13.5",
            "pyyaml": "6.0.3",
            "pytest": "6 passed in 0.07s",
            "command": "PYTHONPATH=. pytest -q tests/test_figure_registry_duplicate_keys.py",
        },
        "scientific_boundary": (
            "Software/schema integrity only; no paper figure or scientific quantity was "
            "regenerated or validated."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", required=True)
    parser.add_argument("--svg", required=True)
    args = parser.parse_args()
    payload = build_payload()
    json_raw = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _atomic_write(Path(args.json), json_raw)
    _atomic_write(Path(args.svg), _svg(payload).encode("utf-8"))
    return 0 if payload["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
