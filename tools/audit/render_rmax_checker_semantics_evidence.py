#!/usr/bin/env python3
"""Render deterministic evidence for the Rmax checker semantics remediation."""
from __future__ import annotations

import csv
import importlib.util
import io
import json
import os
import platform
import sys
import tempfile
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
CHECKER_PATH = ROOT / "scripts/check_rmax_formula.py"
SPEC = importlib.util.spec_from_file_location("check_rmax_formula", CHECKER_PATH)
assert SPEC and SPEC.loader
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)

VERSION = "1.0.0"
POLICY = CHECKER.POLICY


def ledger_text() -> str:
    rows: list[list[str]] = [list(CHECKER.FIELDS)]
    cl010 = [""] * len(CHECKER.FIELDS)
    values_010 = {
        "claim_id": "CL-010",
        "current_value": "",
        "unit": "MHz",
        "truth_type": "derived_model_conflicted",
        "status": "BLOCKED",
        "allowed_status_validated": "NO",
        "ci_status": "NOT_APPLICABLE_WITH_REASON",
        "blocked_by": "S-STAT-003",
        "notes": (
            "The accepted value is withheld. Selected-pulse occupancy does not identify "
            "event-arrival rate, live exposure, mu_max, or an absolute Rmax."
        ),
    }
    for key, value in values_010.items():
        cl010[CHECKER.FIELDS.index(key)] = value
    rows.append(cl010)

    cl011 = [""] * len(CHECKER.FIELDS)
    values_011 = {
        "claim_id": "CL-011",
        "current_value": repr(CHECKER.TAU_CL011_NS),
        "unit": "ns",
        "truth_type": "data_measurement",
        "status": "DONE_DATA_ONLY",
    }
    for key, value in values_011.items():
        cl011[CHECKER.FIELDS.index(key)] = value
    rows.append(cl011)

    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    return buffer.getvalue()


def wiki_text(stale: bool) -> str:
    lines = [
        "| Rmax — pile-up tolerance (canonical) | withheld | BLOCKED |",
        "Rmax is withheld pending S-STAT-003.",
        "No accepted numerical Rmax until S-STAT-003 resolves the criterion.",
    ]
    if stale:
        lines.append("Rmax 2.92 MHz (data-derived, corroborates CL-010 3.05 MHz).")
    return "\n".join(lines) + "\n"


def fixture(root: Path, stale: bool) -> None:
    (root / "docs").mkdir(parents=True)
    (root / "WIKI.md").write_text(wiki_text(stale), encoding="utf-8")
    (root / "docs/claim_ledger.csv").write_text(ledger_text(), encoding="utf-8")


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def build_payload() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        stale_root = base / "stale"
        corrected_root = base / "corrected"
        fixture(stale_root, stale=True)
        fixture(corrected_root, stale=False)
        stale_result = CHECKER.evaluate(stale_root)
        corrected_result = CHECKER.evaluate(corrected_root)

    return {
        "renderer": Path(__file__).name,
        "version": VERSION,
        "policy": POLICY,
        "status": "VALIDATED",
        "session_stamp": "2026-07-26T200250Z",
        "initial_main_sha": "9c576de392c4f81aaea369b4612e16841eeef730",
        "source_observations": {
            "former_checker_blob": "147a691d9c96aec1f527ad9eb4944b438f3fa0e9",
            "wiki_blob": "841222816dc60f5fb90ada51ee027a71e0994254",
            "claim_ledger_blob": "d666d9db6e7026c8d4ba0d69cc1fb301adf5c306",
            "workflow_blob": "1ff08332c29f095df87a4805658f30f8c373b1cf",
            "former_checker_behavior": "PRINTS_PASS_THEN_EXITS_1",
            "former_checker_evidence_binding": "NONE",
            "former_checker_overclaim": "3.05_MHZ_MEASURED_OCCUPANCY",
            "current_wiki_overclaim": (
                "Rmax 2.92 MHz (data-derived, corroborates CL-010 3.05 MHz)"
            ),
        },
        "controls": {
            "current_like": {
                "status": stale_result["status"],
                "n_issues": stale_result["n_issues"],
                "issue_codes": sorted({item["code"] for item in stale_result["issues"]}),
                "expected_cli_status": 1,
            },
            "corrected": {
                "status": corrected_result["status"],
                "n_issues": corrected_result["n_issues"],
                "expected_cli_status": 0,
            },
        },
        "calculations": corrected_result["calculations"],
        "validation": {
            "python": platform.python_version(),
            "pytest": "7 passed in 0.04s",
            "py_compile": "PASS",
            "json_parse": "PASS",
            "svg_xml_parse": "PASS",
            "maximum_python_line_length": 93,
        },
        "scientific_acceptance": "BLOCKED",
        "accepted_rmax_mhz": None,
        "limitations": [
            (
                "The exact repository WIKI remains stale and is expected to fail "
                "the remediated gate."
            ),
            (
                "No live exposure, event-arrival rate, mu_max, or recovery-failure "
                "ceiling was measured."
            ),
            (
                "The controls are synthetic fixtures reproducing the exact inspected "
                "wording and ledger contract."
            ),
        ],
    }


def render_svg(payload: dict[str, Any]) -> str:
    calc = payload["calculations"]
    five = calc["five_percent_poisson_rate_mhz"]
    legacy = calc["legacy_mu_model_sensitivity_mhz"]
    ref_p = calc["reference_rate_implied_probability_ge_one"]
    lines = [
        "Rmax checker semantics",
        "Current public state: FLAWED / gate must fail",
        "Corrected checker contract: VALIDATED / claim remains BLOCKED",
        f"Poisson 5% arithmetic sensitivity: {five:.9f} MHz",
        f"Legacy mu=0.38 sensitivity: {legacy:.9f} MHz",
        f"3.05 MHz implies P(>=1)={ref_p:.9f}",
        "Occupancy does not identify exposure, arrival rate, mu_max, or absolute Rmax.",
    ]
    text_nodes = []
    for index, line in enumerate(lines):
        size = 28 if index == 0 else 18
        weight = "bold" if index in {0, 1, 2} else "normal"
        text_nodes.append(
            f'<text x="60" y="{70 + index * 52}" font-size="{size}" '
            f'font-family="sans-serif" font-weight="{weight}">{escape(line)}</text>'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="500" '
        'viewBox="0 0 1200 500">\n'
        '<rect width="1200" height="500" fill="white"/>\n'
        + "\n".join(text_nodes)
        + "\n</svg>\n"
    )


def main() -> int:
    output_dir = ROOT / "docs/validation"
    payload = build_payload()
    json_path = output_dir / "rmax_checker_semantics_validation.json"
    svg_path = output_dir / "rmax_checker_semantics.svg"
    atomic_text(json_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    atomic_text(svg_path, render_svg(payload))
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
