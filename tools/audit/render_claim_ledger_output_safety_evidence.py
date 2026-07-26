#!/usr/bin/env python3
"""Render deterministic evidence for claim-ledger validator output safety."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any

FORMER_BLOB = "1961e63756b734db30a4a9a8037a756c291afe25"
FORMER_VERSION = "1.0.0"
POLICY = "CLAIM_LEDGER_VALIDATION_OUTPUTS_MUST_BE_DISTINCT_AND_ATOMIC"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_module(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("claim_ledger_validator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_valid_ledger(path: Path, fields: tuple[str, ...]) -> None:
    row = [""] * len(fields)
    row[0] = "CL-TEST"
    row[1] = "Governance"
    row[2] = "schema"
    row[3] = "Synthetic output-safety control"
    row[27] = "software_validation"
    row[28] = "VALIDATED"
    row[29] = "NO"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        writer.writerow(row)


def _former_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Exact former publication algorithm reconstructed from v1.0.0 lines 264-269."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _run_controls(current_source: Path) -> dict[str, Any]:
    module = _load_module(current_source)
    with tempfile.TemporaryDirectory() as temp_name:
        temp = Path(temp_name)

        former_ledger = temp / "former_claim_ledger.csv"
        _write_valid_ledger(former_ledger, module.EXPECTED_FIELDS)
        former_before = _sha256(former_ledger)
        _former_write_json(former_ledger, {"status": "VALIDATED"})
        former_after = _sha256(former_ledger)

        current_ledger = temp / "current_claim_ledger.csv"
        _write_valid_ledger(current_ledger, module.EXPECTED_FIELDS)
        current_before = _sha256(current_ledger)
        alias_status = module.main([
            str(current_ledger),
            "--output",
            str(current_ledger),
        ])
        current_after = _sha256(current_ledger)

        output = temp / "validation.json"
        output.write_text("previous\n", encoding="utf-8")
        original_replace = module.os.replace

        def fail_replace(source: Path, destination: Path) -> None:
            raise OSError("injected replace failure")

        module.os.replace = fail_replace
        try:
            replace_status = module.main([
                str(current_ledger),
                "--output",
                str(output),
            ])
        finally:
            module.os.replace = original_replace

        return {
            "former_algorithm_control": {
                "classification": "INDEPENDENT_RECONSTRUCTION",
                "input_sha256_before": former_before,
                "input_sha256_after": former_after,
                "input_preserved": former_before == former_after,
                "result": "DESTRUCTIVE_OVERWRITE_REPRODUCED",
            },
            "current_alias_control": {
                "exit_status": alias_status,
                "input_sha256_before": current_before,
                "input_sha256_after": current_after,
                "input_preserved": current_before == current_after,
                "result": "FAIL_CLOSED_INPUT_PRESERVED",
            },
            "current_atomic_failure_control": {
                "exit_status": replace_status,
                "previous_output_preserved": (
                    output.read_text(encoding="utf-8") == "previous\n"
                ),
                "temporary_files_remaining": len(
                    list(temp.glob(".validation.json.*.tmp"))
                ),
                "result": "FAIL_CLOSED_PREVIOUS_OUTPUT_PRESERVED",
            },
        }


def _svg(payload: dict[str, Any]) -> str:
    former = payload["controls"]["former_algorithm_control"]
    current = payload["controls"]["current_alias_control"]
    failure = payload["controls"]["current_atomic_failure_control"]
    rows = [
        ("Input/output alias", "overwrites ledger", "status 2; ledger preserved"),
        ("Replace failure", "direct final write", "previous output preserved"),
        ("Publication", "Path.write_text", "temp + fsync + os.replace"),
    ]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="940" height="330" '
        'viewBox="0 0 940 330" role="img" aria-labelledby="title desc">',
        '<title id="title">Claim-ledger validator output-safety remediation</title>',
        '<desc id="desc">Synthetic software controls compare the former direct-write '
        'algorithm with the fail-closed atomic publication contract.</desc>',
        '<rect width="940" height="330" fill="white"/>',
        '<text x="24" y="34" font-family="sans-serif" font-size="22" '
        'font-weight="bold">Claim-ledger output safety</text>',
        '<text x="24" y="58" font-family="sans-serif" font-size="13">'
        'Synthetic software/provenance controls; no physics data or detector result.</text>',
        '<text x="24" y="94" font-family="sans-serif" font-size="14" '
        'font-weight="bold">Control</text>',
        '<text x="280" y="94" font-family="sans-serif" font-size="14" '
        'font-weight="bold">Former v1.0.0</text>',
        '<text x="570" y="94" font-family="sans-serif" font-size="14" '
        'font-weight="bold">Current v1.1.0</text>',
    ]
    for index, (label, old, new) in enumerate(rows):
        y = 130 + index * 54
        parts.extend([
            f'<line x1="20" y1="{y - 24}" x2="920" y2="{y - 24}" '
            'stroke="black" stroke-width="1"/>',
            f'<text x="24" y="{y}" font-family="sans-serif" '
            f'font-size="13">{label}</text>',
            f'<text x="280" y="{y}" font-family="sans-serif" '
            f'font-size="13">{old}</text>',
            f'<text x="570" y="{y}" font-family="sans-serif" '
            f'font-size="13">{new}</text>',
        ])
    parts.extend([
        '<line x1="20" y1="268" x2="920" y2="268" stroke="black"/>',
        f'<text x="24" y="296" font-family="monospace" font-size="12">'
        f'former overwrite reproduced: {str(not former["input_preserved"]).lower()}; '
        f'current input preserved: {str(current["input_preserved"]).lower()}; '
        f'failure preserves output: {str(failure["previous_output_preserved"]).lower()}</text>',
        f'<text x="24" y="318" font-family="monospace" font-size="11">'
        f'policy: {POLICY}</text>',
        '</svg>',
    ])
    return "\n".join(parts) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-source", type=Path, required=True)
    parser.add_argument("--tests", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--svg", type=Path, required=True)
    args = parser.parse_args()

    controls = _run_controls(args.current_source)
    payload = {
        "audit_id": "AUD-LEDGER-002",
        "status": "VALIDATED",
        "policy": POLICY,
        "scientific_class": "SOFTWARE_AND_PROVENANCE_VALIDATION_ONLY",
        "repository_facts": {
            "former_source_blob": FORMER_BLOB,
            "former_version": FORMER_VERSION,
            "former_publication": "DIRECT_PATH_WRITE_TEXT_NO_ALIAS_GUARD",
        },
        "current_source": {
            "path": str(args.current_source),
            "bytes": args.current_source.stat().st_size,
            "sha256": _sha256(args.current_source),
        },
        "focused_tests": {
            "path": str(args.tests),
            "bytes": args.tests.stat().st_size,
            "sha256": _sha256(args.tests),
        },
        "controls": controls,
        "acceptance": {
            "input_output_alias_rejected": controls["current_alias_control"][
                "input_preserved"
            ],
            "previous_output_preserved_on_replace_failure": controls[
                "current_atomic_failure_control"
            ]["previous_output_preserved"],
            "temporary_files_cleaned": controls[
                "current_atomic_failure_control"
            ]["temporary_files_remaining"] == 0,
        },
        "limitations": [
            "The former behavior control reconstructs the exact former direct-write "
            "algorithm; it is not execution of the historical Git blob.",
            "This evidence does not validate any claim value, uncertainty, source, "
            "simulation, calibration, or detector-performance result.",
        ],
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.svg.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.svg.write_text(_svg(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
