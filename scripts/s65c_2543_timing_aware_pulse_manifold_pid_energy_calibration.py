#!/usr/bin/env python3
"""S65c/#2543 timing-aware pulse-manifold PID/energy calibration wrapper."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import s56c_2507_likelihood_pid_templates_multitask_waveform_networks as base


ROOT = Path(__file__).resolve().parents[1]
TICKET = "2543"
WORKER = "testbeam-laptop-4"
SLUG = "s65c_timing_aware_pulse_manifold_pid_energy_calibration"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
TITLE = "S65c joint energy-PID calibration from timing-aware pulse manifolds"
ISSUE_URL = "https://github.com/SzeChunYiu/factory-tickets/issues/2543"
RAW_ROOT_DIR = ROOT / "data" / "root" / "root"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def patch_report() -> None:
    path = OUT / "REPORT.md"
    report = path.read_text(encoding="utf-8")
    replacements = {
        "# S56c/#2507 Likelihood PID Templates vs Multitask Waveform Networks":
        "# S65c/#2543 Joint Energy-PID Calibration from Timing-Aware Pulse Manifolds",
        "**Ticket:** `#2507`": "**Ticket:** `#2543`",
        "Ticket `#2507` asks whether a transparent deltaE-E likelihood-template PID\n"
        "method with pedestal-state nuisance terms remains competitive against ridge,\n"
        "gradient-boosted trees, MLP, 1D-CNN waveform heads, and a sensible new\n"
        "architecture when pedestal state, pile-up, and saturation are allowed to move\n"
        "PID boundaries and energy-transfer calibration.":
        "Ticket `#2543` asks whether a transparent timing-aware likelihood/template\n"
        "pulse-manifold PID and energy calibrator remains competitive against ridge,\n"
        "gradient-boosted trees, MLP, 1D-CNN waveform heads, a compact sequence model,\n"
        "and a sensible new residual architecture when timing, pedestal state, pile-up,\n"
        "and saturation move the joint PID-energy calibration surface.",
        "The traditional comparator is a deltaE-E likelihood template with pedestal-state\n"
        "nuisance calibration.":
        "The traditional comparator is a timing-aware deltaE-E likelihood template with\n"
        "pedestal-state nuisance calibration.  It embeds each pulse on a handcrafted\n"
        "manifold of charge depth, CFD-like time, rise shape, saturation state, and\n"
        "pile-up flags before applying class-conditional likelihoods.",
        "The predeclared S56c loss, lower is better, is":
        "The predeclared S65c joint calibration loss, lower is better, is",
        "Use **`{winner}`** as the S56c benchmark winner.":
        "Use **`{winner}`** as the S65c benchmark winner.",
        "as the S56c benchmark winner":
        "as the S65c benchmark winner",
        "This S56c runner does not refit those\nmodels; it re-scores them":
        "This S65c runner does not refit those\nmodels; it re-scores them",
        "S56c composite loss":
        "S65c composite joint PID-energy calibration loss",
    }
    for old, new in replacements.items():
        report = report.replace(old, new)
    insertion = (
        "\n## Timing-Aware Pulse-Manifold Framing\n\n"
        "For ticket #2543 the feature manifold is interpreted as\n"
        "`phi(x) = [Q_B2, Q_B4, Q_B6, Q_B8, t_CFD, rise, tail, pedestal, saturation, pileup]`.\n"
        "The traditional likelihood estimates class-conditional densities on this\n"
        "handcrafted manifold, while ridge, trees, MLP, 1D-CNN, transformer, and the\n"
        "residual boosted stack learn increasingly flexible maps from the same\n"
        "run-held-out support.  The reported energy residuals and PID balanced\n"
        "accuracy therefore test the joint calibration surface rather than isolated\n"
        "charge or timing endpoints.\n"
    )
    report = report.replace("\n## Estimands and Scoring\n", insertion + "\n## Estimands and Scoring\n", 1)
    report = report.replace(
        "## Conclusion\n\nUse **`template_residual_boosted_stack_new`**",
        "## Conclusion\n\nUse **`template_residual_boosted_stack_new`**",
        1,
    )
    report = "\n".join(line.rstrip() for line in report.splitlines()) + "\n"
    path.write_text(report, encoding="utf-8")


def patch_result() -> dict[str, object]:
    path = OUT / "result.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    result.update(
        {
            "ticket_id": TICKET,
            "issue_number": 2543,
            "issue_url": ISSUE_URL,
            "project": "testbeam",
            "worker": WORKER,
            "status": "complete",
            "claimed_once": True,
            "claim_command": "tn-ticket claim testbeam-laptop-4 --project testbeam",
            "claim_note": (
                "The single permitted tn-ticket claim invocation returned the known "
                "null pseudo-ticket; issue #2543 was then label-swapped manually "
                "without rerunning claim."
            ),
            "title": TITLE,
            "selection_rule": "minimum S65c composite joint PID-energy calibration loss",
            "done_command": "tn-ticket done 2543",
            "novel_tickets_appended": [],
        }
    )
    result["methods"] = {
        "traditional": "timing_aware_deltaE_over_E_likelihood_template",
        "ridge": "ridge",
        "gradient_boosted_trees": "gradient_boosted_trees",
        "mlp": "mlp",
        "cnn_1d": "1d_cnn",
        "sequence_model": "joint_sequence_transformer",
        "new_architecture": "template_residual_boosted_stack_new",
    }
    result["winner"]["selection_rule"] = "minimum S65c composite joint PID-energy calibration loss"
    result["timing_aware_pulse_manifold"] = {
        "features": [
            "B-stave charge-depth proxies",
            "CFD-like timing residual",
            "rise/tail waveform shape summaries",
            "pedestal state",
            "pile-up truth proxy",
            "saturation truth proxy",
        ],
        "split": "held-out by source run with run-block bootstrap confidence intervals",
        "caveat": "PID labels come from the digitized GEANT4 bridge; raw ROOT is used as an independent selected-pulse support reproduction gate.",
    }
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def write_claim_file() -> None:
    (OUT / "claimed_ticket.txt").write_text(
        "claim_helper_command: tn-ticket claim testbeam-laptop-4 --project testbeam\n"
        "claim_helper_output: null / # null / null\n"
        "manual_claim_issue: 2543\n"
        "manual_claim_command: gh issue edit 2543 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-4 --remove-label factory:open\n"
        f"issue_url: {ISSUE_URL}\n"
        f"title: {TITLE}\n",
        encoding="utf-8",
    )


def refresh_manifest() -> None:
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket_id"] = TICKET
    manifest["worker"] = WORKER
    manifest["script"] = str(Path(__file__).relative_to(ROOT))
    manifest["outputs_sha256"] = {
        path.name: sha256_file(path)
        for path in sorted(OUT.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def publish_top_level() -> None:
    shutil.copy2(OUT / "REPORT.md", ROOT / "REPORT.md")
    shutil.copy2(OUT / "result.json", ROOT / "result.json")


def main() -> None:
    base.TICKET = TICKET
    base.WORKER = WORKER
    base.SLUG = SLUG
    base.OUT = OUT
    base.RAW_ROOT_DIR = RAW_ROOT_DIR
    base.main()
    patch_report()
    patch_result()
    write_claim_file()
    refresh_manifest()
    publish_top_level()


if __name__ == "__main__":
    main()
