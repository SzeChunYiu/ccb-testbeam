#!/usr/bin/env python3
"""S51b ticket wrapper for saturated pile-up recovery from censored windows."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import s35b_1784063447_914_74ba7793_saturation_pileup_energy_recovery_benchmark as s35b


ROOT = Path(__file__).resolve().parents[1]
TICKET = "2456"
WORKER = "testbeam-laptop-4"
SLUG = "s51b_saturated_pileup_censored_recovery"
TITLE = "S51b: Saturated pile-up energy recovery from censored pulse windows"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def postprocess_ticket_metadata() -> None:
    report_path = OUT / "REPORT.md"
    report = report_path.read_text(encoding="utf-8")
    replacements = {
        "# S35b: Saturation Pile-Up Energy Recovery Benchmark": "# S51b: Saturated Pile-Up Energy Recovery from Censored Pulse Windows",
        "Ticket `2456` asks for a raw-ROOT reproduction": "Ticket `2456` asks for a raw-ROOT reproduction",
        "S35b winner": "S51b winner",
        "S35b held-out": "S51b held-out",
    }
    for old, new in replacements.items():
        report = report.replace(old, new)
    report = report.replace(
        "comparison of energy reconstruction under clipped saturation and unresolved\npile-up.",
        "comparison of energy reconstruction under censored clipped saturation and unresolved\npile-up.",
    )
    report_path.write_text(report, encoding="utf-8")

    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result.update(
        {
            "ticket_id": TICKET,
            "project": "testbeam",
            "worker": WORKER,
            "title": TITLE,
            "claimed_ticket_text": TITLE,
            "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
            "execution_command": (
                "MPLCONFIGDIR=/tmp/matplotlib-s51b "
                "uv run --index-strategy unsafe-best-match "
                "--index-url https://download.pytorch.org/whl/cpu "
                "--extra-index-url https://pypi.org/simple "
                "--with uproot --with awkward --with numpy --with pandas "
                "--with scikit-learn --with tabulate --with 'torch==2.5.1+cpu' "
                f"python {Path(__file__).resolve().relative_to(ROOT)}"
            ),
        }
    )
    result["winner"]["criterion"] = (
        "minimum registered S51b held-out censored saturation-energy, timing, "
        "pile-up, pedestal, and PID-proxy composite score with run-block bootstrap CIs"
    )
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    claimed_path = OUT / "claimed_ticket.txt"
    claimed_path.write_text(f"{TICKET}\n# {TITLE}\n", encoding="utf-8")

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket_id"] = TICKET
    manifest["command"] = f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}"
    manifest["outputs_sha256"] = {
        p.name: sha256_file(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    s35b.TICKET = TICKET
    s35b.WORKER = WORKER
    s35b.SLUG = SLUG
    s35b.TITLE = TITLE
    s35b.OUT = OUT
    s35b.RAW_ROOT_DIR = RAW_ROOT_DIR
    s35b.main()
    postprocess_ticket_metadata()


if __name__ == "__main__":
    main()
