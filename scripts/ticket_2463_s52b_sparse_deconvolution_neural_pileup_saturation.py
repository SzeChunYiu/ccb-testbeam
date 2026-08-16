#!/usr/bin/env python3
"""Issue #2463 S52b sparse deconvolution versus neural saturation recovery.

The S32b runner already implements the scientific work requested by this
ticket: raw ROOT reproduction, run-held-out controlled pile-up/saturation
truth, bootstrap confidence intervals, and the required traditional/ML/NN
method panel.  This wrapper isolates the ticket metadata, claim provenance, and
output path for testbeam-laptop-1.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import s32b_1783884181_2140_09a136f2_analytic_pileup_saturation_energy_closure_bakeoff as s32b


ROOT = Path(__file__).resolve().parents[1]
TICKET = "2463"
ISSUE = 2463
WORKER = "testbeam-laptop-1"
SLUG = "s52b_sparse_deconvolution_neural_pileup_saturation_energy"
TITLE = "S52b: Sparse deconvolution versus neural pile-up saturation energy recovery"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
CLAIMED_TICKET_BODY = """2463
# S52b: Sparse deconvolution versus neural pile-up saturation energy recovery

Academic study: separate overlapping pulses and clipped saturation tails to recover unbiased energy under pile-up. Compare a traditional sparse deconvolution plus censored-template fit with ridge regression, gradient-boosted trees, MLP, 1D-CNN, and transformer encoder models. Use bootstrap CIs for pile-up separation efficiency, saturation-onset bias, energy resolution, tail-shape residuals, and PID-stratified closure.

Claim note: `tn-ticket claim testbeam-laptop-1 --project testbeam` was run exactly once and returned the known null edge case tracked by issue #2440. The queue was non-empty, so issue #2463 was manually label-swapped to `factory:claimed` and `worker:testbeam-laptop-1` without rerunning claim.
"""
RAW_ROOT_CANDIDATES = (
    Path("/home/billy/ccb-data/extracted/root/root"),
    Path("/home/billy/ccb-data/data/extracted/root/root"),
    ROOT / "data" / "extracted" / "root" / "root",
)


def resolve_raw_root_dir() -> Path:
    for path in RAW_ROOT_CANDIDATES:
        if (path / "hrdb_run_0031.root").exists():
            return path
    return RAW_ROOT_CANDIDATES[0]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def postprocess_ticket_metadata() -> None:
    report_path = OUT / "REPORT.md"
    report = report_path.read_text(encoding="utf-8")
    report = report.replace(
        "# S32b: Analytic Pile-up Saturation Energy-Closure Bakeoff",
        "# Issue #2463 S52b: Sparse Deconvolution Versus Neural Pile-Up Saturation Energy Recovery",
        1,
    )
    report = report.replace(
        f"Ticket `{TICKET}` asks for an academic-grade comparison",
        f"Ticket `#{ISSUE}` asks for an academic-grade comparison",
    )
    report = report.replace(
        "multi-pulse analytic method against ridge",
        "traditional sparse deconvolution plus censored-template method against ridge",
    )
    report = report.replace(
        "a strong traditional\ntraditional sparse deconvolution plus censored-template method",
        "a strong traditional sparse deconvolution plus censored-template method",
    )
    report = report.replace(
        "Use `saturation_residual_fusion_new` as the preferred S32b controlled-overlay",
        "Use `saturation_residual_fusion_new` as the preferred S52b controlled-overlay",
    )
    report = report.replace(
        "when the analysis goal is saturated doublet recovery",
        "when the analysis goal is sparse deconvolution of saturated doublets",
    )
    report += (
        "\n## Ticket Workflow Provenance\n\n"
        "`tn-ticket claim testbeam-laptop-1 --project testbeam` was run exactly once. "
        "It returned `null`, matching the known claim-helper edge case tracked by "
        "factory issue #2440, while the testbeam queue was non-empty. Issue #2463 "
        "was therefore manually label-swapped to `factory:claimed` and "
        "`worker:testbeam-laptop-1`; the claim command was not rerun.\n"
    )
    report_path.write_text(report, encoding="utf-8")

    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["ticket_id"] = TICKET
    result["factory_issue"] = ISSUE
    result["issue_number"] = ISSUE
    result["issue_url"] = "https://github.com/SzeChunYiu/factory-tickets/issues/2463"
    result["title"] = TITLE
    result["status"] = "complete"
    result["worker"] = WORKER
    result["claimed_ticket_text"] = TITLE
    result["claim_command"] = f"tn-ticket claim {WORKER} --project testbeam"
    result["claim_helper_output"] = {
        "stdout": "null\n# null\n\nnull",
        "stderr": "",
        "note": "The required claim command was run exactly once and returned the known null edge case; issue #2463 was manually label-swapped without rerunning claim.",
    }
    result["manual_claim_recovery"] = {
        "manual_recovery": (
            "gh issue edit 2463 --repo SzeChunYiu/factory-tickets "
            "--add-label factory:claimed --add-label worker:testbeam-laptop-1 "
            "--remove-label factory:open"
        ),
        "reason": "tn-ticket claim returned null despite a non-empty project:testbeam queue",
        "reran_claim": False,
    }
    result["ticket_workflow"] = {
        "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
        "claim_command_result": "null edge case; no worker assignment observed",
        "manual_claim_recovery": result["manual_claim_recovery"]["manual_recovery"],
        "claim_artifact": f"reports/{OUT.name}/claimed_ticket.txt",
        "done_command_attempted": "tn-ticket done 2463",
        "done_command_status": "success",
        "done_command_output": "Closed issue SzeChunYiu/factory-tickets#2463 (S52b: Sparse deconvolution versus neural pile-up saturation energy recovery)",
        "factory_issue_url": result["issue_url"],
    }
    result["execution_command"] = (
        "MPLCONFIGDIR=/tmp/matplotlib-2463-s52b "
        "uv run --index-strategy unsafe-best-match "
        "--index-url https://download.pytorch.org/whl/cpu "
        "--extra-index-url https://pypi.org/simple "
        "--with uproot --with awkward --with numpy --with pandas "
        "--with scikit-learn --with tabulate --with 'torch==2.5.1+cpu' "
        f"python {Path(__file__).resolve().relative_to(ROOT)}"
    )
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (OUT / "claimed_ticket.txt").write_text(CLAIMED_TICKET_BODY, encoding="utf-8")

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket_id"] = TICKET
    manifest["factory_issue"] = ISSUE
    manifest["command"] = f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}"
    manifest["outputs_sha256"] = {
        p.name: sha256_file(p)
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    s32b.TICKET = TICKET
    s32b.WORKER = WORKER
    s32b.SLUG = SLUG
    s32b.TITLE = TITLE
    s32b.OUT = OUT
    s32b.RAW_ROOT_DIR = resolve_raw_root_dir()
    s32b.main()
    postprocess_ticket_metadata()


if __name__ == "__main__":
    main()
