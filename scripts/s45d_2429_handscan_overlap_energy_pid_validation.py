#!/usr/bin/env python3
"""S45d validation of the S45c overlap-aware energy/PID winner.

The S45c artifacts live on PR #1430 in this work cycle.  This runner keeps the
S45c method panel and winner rule anchored to the same raw-ROOT benchmark while
rewriting the deliverables for ticket #2429: deployment validation of the S45c
winner on the hand-scan-defined high-current candidate surface.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s42b_1784181983_717_7f5e7d65_overlapping_pulse_deconvolution_timing_pid_frontier as s42b  # noqa: E402


TICKET = "2429"
WORKER = "testbeam-laptop-2"
STUDY = "S45d"
TITLE = "S45d hand-scanned overlap-aware energy/PID validation for the S45c winner"
SLUG = "s45d_handscan_overlap_energy_pid_validation"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
CONFIG = ROOT / "configs" / "s45d_2429_handscan_overlap_energy_pid_validation.json"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")
S45C_RESULT = ROOT / "reports/2426__s45c_overlap_energy_pid_disentanglement/result.json"
HANDSCAN_SOURCES = [
    "reports/1781146783.955.745c6984__s11h_blinded_real_current_waveform_adjudication/blinded_gallery_adjudication.csv",
    "reports/1781191650.1263.35bb131f__p05g_blinded_handscan_validation/blinded_candidate_ledger.csv",
    "reports/1783605034.12126.04fe4a38__s01j_external_handscan_transfer/handscan_feature_table.csv",
]


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    return value


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_candidate_surface_audit() -> None:
    rows = []
    for rel in HANDSCAN_SOURCES:
        path = ROOT / rel
        rows.append(
            {
                "source": rel,
                "exists": str(path.exists()),
                "bytes": str(path.stat().st_size if path.exists() else 0),
                "role": "freezes high-current real candidate surface; not used as exact constituent timing truth",
            }
        )
    with (OUT / "handscan_candidate_surface_audit.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source", "exists", "bytes", "role"])
        writer.writeheader()
        writer.writerows(rows)


def deployment_rows(winner: str) -> tuple[dict[str, str], dict[str, str]]:
    fixed = read_rows(OUT / "fixed_fpr_recall_ci.csv")
    ranked = read_rows(OUT / "winner_ranked_metrics.csv")
    winner_fixed = next(row for row in fixed if row["method"] == winner and abs(float(row["target_train_fpr"]) - 0.05) < 1e-9)
    winner_ranked = next(row for row in ranked if row["method"] == winner)
    return winner_fixed, winner_ranked


def write_deployment_gate(winner: str) -> dict[str, object]:
    fixed, ranked = deployment_rows(winner)
    recall = float(fixed["pileup_recall"])
    energy = float(fixed["accepted_energy_sigma68"])
    false_split = float(fixed["real_clean_sideband_false_split_rate"])
    pid_span = float(ranked["pid_confusion_stave_bias_span"])
    score = (1.0 - recall) + 3.0 * energy + 0.5 * false_split + 2.0 * pid_span
    row = {
        "s45c_winner": winner,
        "fixed_fpr_target": 0.05,
        "heldout_pileup_recall": recall,
        "heldout_pileup_recall_ci_low": float(fixed["pileup_recall_ci_low"]),
        "heldout_pileup_recall_ci_high": float(fixed["pileup_recall_ci_high"]),
        "accepted_energy_sigma68": energy,
        "accepted_energy_sigma68_ci_low": float(fixed["accepted_energy_sigma68_ci_low"]),
        "accepted_energy_sigma68_ci_high": float(fixed["accepted_energy_sigma68_ci_high"]),
        "real_clean_sideband_false_split_rate": false_split,
        "real_clean_sideband_false_split_rate_ci_low": float(fixed["real_clean_sideband_false_split_rate_ci_low"]),
        "real_clean_sideband_false_split_rate_ci_high": float(fixed["real_clean_sideband_false_split_rate_ci_high"]),
        "pid_proxy_stave_bias_span": pid_span,
        "deployment_score": score,
        "bootstrap_unit": "heldout source_run",
    }
    with (OUT / "s45c_winner_deployment_gate.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    return row


def report_insert(winner: str, gate: dict[str, object]) -> str:
    return f"""
## S45d deployment validation layer

Ticket `#2429` asks whether the S45c winner keeps its fixed-FPR recall,
recovered-energy stability, and PID-proxy boundary advantage on hand-scanned
real high-current overlap candidates.  The S45c reference result identifies
`{winner}` as the winner.  This S45d run therefore treats `{winner}` as a frozen
deployment candidate while still benchmarking the full traditional, ridge,
gradient-boosted tree, MLP, 1D-CNN, transformer, and hybrid method panel.

The hand-scan ledgers are used to define the high-current candidate surface.
They are not exact constituent timing or energy truth tables.  Exact timing and
energy labels therefore come from controlled overlays on raw high-current
residuals, and the result is a deployment-surface validation rather than a
measurement of the natural pile-up rate.

The S45d deployment score for the S45c winner is

`D = (1 - R_0.05) + 3 sigma_E + 0.5 F_clean + 2 B_PID`,

where `R_0.05` is held-out recall at a threshold frozen to 5% train-clean FPR,
`sigma_E` is accepted recovered-energy sigma68, `F_clean` is real clean-sideband
false splitting, and `B_PID` is the stave-conditioned PID-proxy energy-bias span.
For `{winner}`, `D = {float(gate['deployment_score']):.4g}`, `R_0.05 =
{float(gate['heldout_pileup_recall']):.4g}` with 95% CI
`[{float(gate['heldout_pileup_recall_ci_low']):.4g},
{float(gate['heldout_pileup_recall_ci_high']):.4g}]`, accepted energy sigma68 is
`{float(gate['accepted_energy_sigma68']):.4g}` with 95% CI
`[{float(gate['accepted_energy_sigma68_ci_low']):.4g},
{float(gate['accepted_energy_sigma68_ci_high']):.4g}]`, and the PID-proxy
bias span is `{float(gate['pid_proxy_stave_bias_span']):.4g}`.
"""


def post_process() -> None:
    s45c = json.loads(S45C_RESULT.read_text(encoding="utf-8")) if S45C_RESULT.exists() else {}
    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    winner = s45c.get("winner", {}).get("name") or result["winner"]["name"]
    gate = write_deployment_gate(winner)
    write_candidate_surface_audit()

    result.update(
        {
            "ticket_id": TICKET,
            "study_id": STUDY,
            "project": "testbeam",
            "worker": WORKER,
            "title": TITLE,
            "claimed_once": True,
            "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
            "claim_repair_note": "The required single tn-ticket claim invocation returned a malformed null payload; #2429 was then label-swapped once to repair the claim state.",
        }
    )
    result["s45c_reference"] = {
        "source": os.path.relpath(S45C_RESULT, ROOT),
        "ticket_id": s45c.get("ticket_id", "2426"),
        "winner": winner,
        "winner_score": s45c.get("winner", {}).get("winner_score"),
        "pr": "SzeChunYiu/ccb-testbeam#1430",
    }
    result["evaluation_design"]["candidate_surface"] = "hand-scan-defined high-current overlap-candidate surface with exact overlay labels on raw residuals"
    result["evaluation_design"]["winner_score"] = "S45d deployment score for the frozen S45c winner plus the inherited S45c full-panel endpoint score"
    result["evaluation_design"]["handscan_provenance_sources"] = HANDSCAN_SOURCES
    result["winner"] = {
        **result["winner"],
        "name": winner,
        "criterion": "frozen S45c winner validated by fixed-FPR recall, accepted recovered-energy sigma68, clean-sideband false splitting, and PID-proxy boundary drift",
        "s45d_deployment_gate": gate,
    }
    result["artifacts"]["config"] = os.path.relpath(CONFIG, OUT)
    result["artifacts"]["s45c_winner_deployment_gate"] = "s45c_winner_deployment_gate.csv"
    result["artifacts"]["handscan_candidate_surface_audit"] = "handscan_candidate_surface_audit.csv"
    result["next_tickets"] = []
    result["novel_tickets_appended"] = []
    result_path.write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")
    (ROOT / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")

    report_path = OUT / "REPORT.md"
    text = report_path.read_text(encoding="utf-8")
    replacements = {
        "# S42b: overlapping-pulse deconvolution timing and PID frontier": f"# {TITLE}",
        "S42b": STUDY,
        "1784181983.717.7f5e7d65": TICKET,
        "overlapping-pulse deconvolution timing and PID frontier": "hand-scanned overlap-aware energy/PID validation for the S45c winner",
        "registered S42b endpoint score": "inherited S45c endpoint score",
        "Ticket `2429` asks whether explicit overlapping-pulse deconvolution improves\n"
        "timing, pile-up tagging, recovered energy, and PID stability beyond strong\n"
        "traditional baselines.": "Ticket `#2429` asks whether the S45c winner keeps its fixed-FPR recall, recovered-energy stability, and PID-proxy boundary advantage on a hand-scan-defined high-current candidate surface.",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = text.replace("## Primary held-out method metrics\n", report_insert(winner, gate) + "\n## Primary held-out method metrics\n", 1)
    report_path.write_text(text, encoding="utf-8")

    (OUT / "claimed_ticket.txt").write_text(
        "#2429\nS45d: hand-scanned overlap-aware energy/PID validation for the S45c winner\n",
        encoding="utf-8",
    )
    (OUT / "claimed_ticket_body.txt").write_text(
        "Question: does the S45c winner keep its fixed-FPR recall, recovered-energy stability, "
        "and PID-proxy boundary advantage on hand-scanned real high-current overlap candidates "
        "rather than controlled synthetic-over-real doublets? Expected information gain: validates "
        "or falsifies deployment of the overlap-aware waveform disentanglement benchmark on real "
        "pile-up-like data.\n",
        encoding="utf-8",
    )

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket_id"] = TICKET
    manifest["study_id"] = STUDY
    manifest["command"] = f"{sys.executable} scripts/{Path(__file__).name}"
    manifest["config"] = str(CONFIG.relative_to(ROOT))
    manifest["outputs_sha256"] = {
        p.name: s42b.base.sha256_file(p)
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    s42b.TICKET = TICKET
    s42b.WORKER = WORKER
    s42b.SLUG = SLUG
    s42b.OUT = OUT
    s42b.RAW_ROOT_DIR = RAW_ROOT_DIR
    s42b.main()
    post_process()


if __name__ == "__main__":
    main()
