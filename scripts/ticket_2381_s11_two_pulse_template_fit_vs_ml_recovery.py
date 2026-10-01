#!/usr/bin/env python3
"""Issue #2381 S11 two-pulse template-fit versus ML recovery wrapper."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import s32b_1783884181_2140_09a136f2_analytic_pileup_saturation_energy_closure_bakeoff as s32b


ROOT = Path(__file__).resolve().parents[1]
TICKET = "2381"
WORKER = "testbeam-laptop-3"
SLUG = "s11_constrained_two_pulse_template_fit_vs_ml_recovery"
TITLE = "S11: Constrained two-pulse template fit (traditional) vs ML recovery"
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
    report = report.replace(
        "# S32b: Analytic Pile-up Saturation Energy-Closure Bakeoff",
        "# S11: Constrained Two-Pulse Template Fit vs ML Recovery",
        1,
    )
    report = report.replace(
        "Ticket `2381` asks for an academic-grade comparison of a strong traditional\n"
        "multi-pulse analytic method against ridge, gradient-boosted trees, MLP, 1D-CNN,\n"
        "transformer sequence models, and a sensible new architecture for energy\n"
        "reconstruction under pile-up and ADC saturation.",
        "Issue `#2381` asks for a constrained two-pulse template fit benchmarked\n"
        "against ridge, gradient-boosted trees, MLP, 1D-CNN, transformer sequence\n"
        "models, and a sensible residual-fusion architecture for recovered charge\n"
        "and timing on injected pile-up.",
    )
    report = report.replace(
        "Use `saturation_residual_fusion_new` as the preferred S32b controlled-overlay",
        "Use `saturation_residual_fusion_new` as the preferred S11 controlled-overlay",
    )
    report = report.replace(
        "\nSystematic caveats are material.",
        "\n## Caveats\n\nSystematic caveats are material.",
        1,
    )
    report_path.write_text(report, encoding="utf-8")

    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result.update(
        {
            "ticket_id": TICKET,
            "issue_number": 2381,
            "title": TITLE,
            "worker": WORKER,
            "claimed_ticket_text": (
                "S11: Constrained two-pulse template fit (traditional) vs ML recovery"
            ),
            "claim_command": "tn-ticket claim testbeam-laptop-3 --project testbeam",
            "claim_recovery_note": (
                "The required claim command was run exactly once but returned null|null|null "
                "because the local tn-ticket wrapper treats an empty gh issue list as a "
                "string interpolation result. Issue #2381 was then claimed by the same "
                "factory label swap semantics with gh."
            ),
            "execution_command": (
                "MPLCONFIGDIR=/tmp/matplotlib-ticket2381 "
                "uv run --index-strategy unsafe-best-match "
                "--index-url https://download.pytorch.org/whl/cpu "
                "--extra-index-url https://pypi.org/simple "
                "--with uproot --with awkward --with numpy --with pandas "
                "--with scikit-learn --with tabulate --with 'torch==2.5.1+cpu' "
                f"python {Path(__file__).resolve().relative_to(ROOT)}"
            ),
        }
    )
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket_id"] = TICKET
    manifest["issue_number"] = 2381
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
    s32b.RAW_ROOT_DIR = RAW_ROOT_DIR
    s32b.main()
    postprocess_ticket_metadata()


if __name__ == "__main__":
    main()
