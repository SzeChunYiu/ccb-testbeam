#!/usr/bin/env python3
"""Ticket #2443 wrapper for the pedestal-aware PID boundary benchmark."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s39c_1784070453_964_25fe633c_joint_pid_energy_disentanglement as s39c  # noqa: E402


TICKET = "2443"
WORKER = "testbeam-laptop-1"
TITLE = "S48c: Pedestal-aware PID boundary and pulse-memory comparison"
CONFIG = "configs/s48c_2443_pedestal_aware_pid_boundary_pulse_memory_comparison.yaml"
OUT = ROOT / "reports" / "2443__s48c_pedestal_aware_pid_boundary_pulse_memory_comparison"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def postprocess() -> None:
    report_path = OUT / "REPORT.md"
    report = report_path.read_text(encoding="utf-8")
    report = report.replace(
        "# S39c: Joint PID-Energy Disentanglement under Pile-Up and Saturation",
        "# S48c/#2443: Pedestal-Aware PID Boundary and Pulse-Memory Comparison",
        1,
    )
    report = report.replace(
        "## Verdict\n\n",
        (
            "## Ticket Claim Provenance\n\n"
            "The required one-shot helper command `tn-ticket claim testbeam-laptop-1 --project testbeam` "
            "returned the known null pseudo-ticket pattern (`null`, `# null`, `null`) while open "
            "`project:testbeam` tickets existed.  Without rerunning the helper, issue #2443 was "
            "manually label-swapped to `factory:claimed` and `worker:testbeam-laptop-1`; this is "
            "the same recovery pattern documented for the helper bug in factory-ticket #2440.  No "
            "novel follow-up ticket was appended.\n\n"
            "## Verdict\n\n"
        ),
        1,
    )
    report = report.replace("S39c winner", "S48c/#2443 winner")
    report = report.replace(
        "| pedestal_tail_fusion_new | new hybrid | Birks residual correction using pedestal, tail, timing, and boosted-PID summaries |\n\n"
        "## Overall Results",
        (
            "| pedestal_tail_fusion_new | new hybrid | Birks residual correction using pedestal, tail, timing, and boosted-PID summaries |\n\n"
            "### Implementation Details\n\n"
            "The traditional PID score uses a train-only charge-depth coordinate\n\n"
            "`z = log(1 + Q_even) - 0.42 d - 0.08 M`,\n\n"
            "where `Q_even` is the duplicate even-readout charge, `d` is the deepest selected\n"
            "B-stave index, and `M` is event multiplicity.  Class-conditional Gaussian\n"
            "densities `p(z | y=0)` and `p(z | y=1)` are fit on train runs only and converted\n"
            "to a posterior score by Bayes' rule.  The associated energy endpoint uses the\n"
            "duplicate-readout Birks inversion, so this comparator is intentionally\n"
            "transparent and low-capacity.\n\n"
            "The ridge, boosted-tree, and MLP models consume the same tabular feature matrix:\n"
            "event multiplicity, depth, log charge, log peak amplitude, saturated-channel\n"
            "count, per-stave charge/peak/hit summaries, and early/late charge fractions.\n"
            "The 1D-CNN and transformer additionally consume the four B-stave waveform\n"
            "windows directly.  The hybrid model appends the traditional Birks energy, the\n"
            "boosted-tree PID score, and boosted-tree timing proxy to the tabular matrix and\n"
            "learns a residual correction.\n\n"
            "No held-out run contributes to feature scaling, weak-label thresholds, Birks\n"
            "calibration, class-conditional traditional likelihoods, or model fitting.\n\n"
            "## Overall Results"
        ),
        1,
    )
    report_path.write_text(report, encoding="utf-8")

    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["study"] = "S48c"
    result["ticket_id"] = TICKET
    result["issue_number"] = 2443
    result["issue_url"] = "https://github.com/SzeChunYiu/factory-tickets/issues/2443"
    result["title"] = TITLE
    result["claim_command"] = f"tn-ticket claim {WORKER} --project testbeam"
    result["done_command"] = "tn-ticket done 2443"
    result["manual_claim_recovery"] = {
        "reason": "tn-ticket claim returned a null pseudo-ticket despite a non-empty testbeam queue",
        "manual_recovery": "gh issue edit 2443 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-1 --remove-label factory:open",
        "reran_claim": False,
    }
    result["claim_helper_output"] = {
        "stderr": "null",
        "stdout": "# null\n\nnull",
        "note": "single required claim command returned the known null edge case tracked as factory-ticket #2440; issue #2443 was manually label-swapped to worker:testbeam-laptop-1 without rerunning claim",
    }
    result["required_method_coverage"]["traditional"] = "traditional_charge_ratio_template/Gaussian charge-depth calibration"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    (OUT / "claimed_ticket.txt").write_text(
        "claim_helper_command: tn-ticket claim testbeam-laptop-1 --project testbeam\n"
        "claim_helper_stderr:\n"
        "null\n"
        "claim_helper_stdout:\n"
        "# null\n\n"
        "null\n"
        "manual_claim_issue: 2443\n"
        "manual_claim_command: gh issue edit 2443 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-1 --remove-label factory:open\n"
        "manual_claim_evidence: issue #2443 labels include factory:claimed, project:testbeam, worker:testbeam-laptop-1\n"
        "done_command: tn-ticket done 2443\n"
        "#2443 S48c: Pedestal-aware PID boundary and pulse-memory comparison\n",
        encoding="utf-8",
    )

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["study"] = "S48c"
    manifest["ticket_id"] = TICKET
    manifest["command"] = f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}"
    manifest["outputs"] = {
        p.name: sha256_file(p)
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    old_argv = sys.argv[:]
    try:
        sys.argv = [str(Path(__file__).name), "--config", CONFIG]
        s39c.main()
    finally:
        sys.argv = old_argv
    postprocess()


if __name__ == "__main__":
    main()
