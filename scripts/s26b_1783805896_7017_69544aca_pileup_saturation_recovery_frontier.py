#!/usr/bin/env python3
"""S26b pile-up saturation recovery frontier for testbeam-laptop-3.

This ticket-specific runner reuses the validated raw-ROOT reproduction,
controlled-injection, and model bakeoff machinery from the earlier S26b runner,
but writes a new artifact directory for the claimed ticket and adds an
injection-source bootstrap CI table.
"""

from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402
import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as base  # noqa: E402
import s26b_1783798536_2368_2ce12433_saturation_energy_recovery_architecture_bakeoff as prior  # noqa: E402


TICKET = "1783805896.7017.69544aca"
SLUG = "s26b_pileup_saturation_recovery_frontier"
WORKER = "testbeam-laptop-3"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/extracted/root/root")


def load_config() -> dict:
    cfg = prior.load_config()
    cfg.update(
        {
            "ticket_id": TICKET,
            "title": "Pile-up saturation recovery frontier",
            "worker": WORKER,
            "output_dir": str(OUT),
            "random_seed": 2026071203,
        }
    )
    cfg["raw_root_dir"] = str(RAW_ROOT_DIR)
    return cfg


def source_unit_bootstrap(joined: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    """Bootstrap held-out metrics over run/stave/injection-source cells.

    The controlled benchmark does not preserve the integer index of the residual
    waveform sampled from the pool.  The finest auditable injection-source unit
    retained in the event table is therefore the run, stave, pulse-label, spacing
    bin, and ratio bin cell.  This is stricter than event bootstrap and
    complementary to the run-block intervals in method_metrics.csv.
    """

    held = joined[joined["split"] == "heldout"].copy()
    held["source_spacing_bin"] = pd.cut(
        held["true_sep_sample"].fillna(-1.0),
        bins=[-2.0, 0.0, 1.5, 3.5, 6.5],
        include_lowest=True,
    ).astype(str)
    held["source_ratio_bin"] = pd.cut(
        held["true_ratio"].fillna(0.0),
        bins=[-0.01, 0.01, 0.35, 0.625, 0.875, 1.05],
        include_lowest=True,
    ).astype(str)
    held["injection_source_unit"] = (
        held["source_run"].astype(str)
        + ":"
        + held["stave"].astype(str)
        + ":"
        + held["is_overlap"].astype(str)
        + ":"
        + held["source_spacing_bin"]
        + ":"
        + held["source_ratio_bin"]
    )

    rows: List[Dict[str, object]] = []
    metric_names = [
        "detection_ap",
        "time_sigma68_ns",
        "pileup_miss_rate",
        "false_split_rate",
        "energy_fractional_sigma68",
    ]
    for method, group in held.groupby("method"):
        units = np.asarray(sorted(group["injection_source_unit"].unique()), dtype=object)
        samples: Dict[str, List[float]] = {name: [] for name in metric_names}
        for _ in range(n_boot):
            take = rng.choice(units, size=len(units), replace=True)
            boot = pd.concat([group[group["injection_source_unit"] == unit] for unit in take], ignore_index=True)
            vals = base.metric_values(boot)
            for name in metric_names:
                value = float(vals[name])
                if np.isfinite(value):
                    samples[name].append(value)
        row: Dict[str, object] = {
            "method": method,
            "bootstrap_unit": "source_run:stave:is_overlap:spacing_bin:ratio_bin",
            "n_source_units": int(len(units)),
            "bootstrap_replicates": int(n_boot),
        }
        for name, values in samples.items():
            row[name] = float(base.metric_values(group)[name])
            row[f"{name}_ci_low"] = float(np.percentile(values, 2.5)) if values else float("nan")
            row[f"{name}_ci_high"] = float(np.percentile(values, 97.5)) if values else float("nan")
        rows.append(row)
    return pd.DataFrame(rows).sort_values("energy_fractional_sigma68").reset_index(drop=True)


def append_source_bootstrap_report(source_ci: pd.DataFrame) -> None:
    cols = [
        "method",
        "n_source_units",
        "energy_fractional_sigma68",
        "energy_fractional_sigma68_ci_low",
        "energy_fractional_sigma68_ci_high",
        "time_sigma68_ns",
        "time_sigma68_ns_ci_low",
        "time_sigma68_ns_ci_high",
        "detection_ap",
        "detection_ap_ci_low",
        "detection_ap_ci_high",
    ]
    section = f"""

## Injection-source bootstrap

The run-block intervals above answer whether the ranking transfers across held-out
runs.  As a complementary stress test, `injection_source_bootstrap_ci.csv`
resamples retained source cells defined by
`source_run:stave:is_overlap:spacing_bin:ratio_bin`.  This unit preserves the
run-local residual source, detector stave/PID proxy, pile-up label, separation
family, and amplitude-ratio family rather than treating individual synthetic
events as independent draws.

{prior.md_table(source_ci, cols)}
"""
    report = OUT / "REPORT.md"
    report.write_text(report.read_text(encoding="utf-8") + section, encoding="utf-8")


def main() -> None:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "claimed_ticket.txt").write_text(TICKET + "\n", encoding="utf-8")
    cfg = load_config()
    rng = np.random.default_rng(int(cfg["random_seed"]))

    match = p05a.reproduce_counts(cfg)
    match.to_csv(OUT / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    runs = cfg["benchmark_runs"]["train"] + cfg["benchmark_runs"]["heldout"]
    clean = p05a.read_clean_pulses(cfg, runs, rng)
    templates, template_summary = p05a.build_templates(clean[clean["run"].isin(cfg["benchmark_runs"]["train"])], cfg)
    template_summary.to_csv(OUT / "template_summary.csv", index=False)

    train_events, train_waves = p05a.generate_benchmark(clean, templates, cfg, "train", cfg["benchmark_runs"]["train"], rng)
    held_events, held_waves = p05a.generate_benchmark(clean, templates, cfg, "heldout", cfg["benchmark_runs"]["heldout"], rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waves = np.vstack([train_waves, held_waves])

    trad_raw = p05a.run_template_fits(events, waves, templates, cfg)
    preds = [base.template_prediction(trad_raw)]
    preds.extend(base.run_sklearn_methods(events, waves, int(cfg["random_seed"])))
    preds.append(base.cnn_prediction(events, waves, cfg))
    preds.append(prior.transformer_prediction(events, waves, cfg))
    preds.append(base.add_residual_stack(events, waves, trad_raw, int(cfg["random_seed"])))

    all_pred = pd.concat(preds, ignore_index=True)
    base_cols = [
        "event_id",
        "split",
        "source_run",
        "stave",
        "is_overlap",
        "true_t1_sample",
        "true_t2_sample",
        "true_amp1_adc",
        "true_amp2_adc",
        "true_sep_sample",
        "true_ratio",
    ]
    joined = all_pred.merge(events[base_cols], on="event_id", how="left")
    joined.to_csv(OUT / "event_predictions.csv", index=False)

    overall = base.summarize(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    ranked = prior.winner_table(overall)
    by_run = base.by_run_summary(joined)
    strata = base.strata_summary(joined)
    source_ci = source_unit_bootstrap(joined, rng, int(cfg["ml"]["bootstrap_samples"]))

    overall.to_csv(OUT / "method_metrics.csv", index=False)
    ranked.to_csv(OUT / "winner_ranked_metrics.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)
    source_ci.to_csv(OUT / "injection_source_bootstrap_ci.csv", index=False)

    winner = str(ranked.iloc[0]["method"])
    runtime = time.time() - started
    prior.TICKET = TICKET
    prior.WORKER = WORKER
    prior.OUT = OUT
    prior.write_report(cfg, match, overall, ranked, by_run, strata, template_summary, winner, runtime)
    append_source_bootstrap_report(source_ci)

    input_rows = [
        {"path": str(path), "sha256": base.sha256_file(path), "size": path.stat().st_size}
        for path in sorted(RAW_ROOT_DIR.glob("hrdb_run_*.root"))
    ]
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

    result = {
        "ticket_id": TICKET,
        "project": "testbeam",
        "worker": WORKER,
        "title": cfg["title"],
        "status": "complete",
        "claimed_once": True,
        "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
        "raw_root_reproduction": {
            "passed": bool(match["pass"].all()),
            "raw_root_glob": str(RAW_ROOT_DIR / "hrdb_run_*.root"),
            "expected_selected_pulses": int(match.iloc[0]["report_value"]),
            "reproduced_selected_pulses": int(match.iloc[0]["reproduced"]),
            "delta": int(match.iloc[0]["delta"]),
            "evidence_table": "reproduction_match_table.csv",
        },
        "evaluation_design": {
            "split": "train and held-out sets are disjoint by source run",
            "train_runs": cfg["benchmark_runs"]["train"],
            "heldout_runs": cfg["benchmark_runs"]["heldout"],
            "run_block_bootstrap": "held-out source_run percentile 95% CI",
            "injection_source_bootstrap": "held-out source_run:stave:is_overlap:spacing_bin:ratio_bin percentile 95% CI",
            "bootstrap_replicates": int(cfg["ml"]["bootstrap_samples"]),
            "negative_control": "clean single-pulse controls with matched source-run distribution",
            "winner_score": "energy_fractional_sigma68 + 0.01*time_sigma68_ns + 0.05*pileup_miss_rate + 0.05*false_split_rate",
        },
        "required_method_coverage": {
            "traditional": "two_pulse_template_cfd_baseline",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "transformer_sequence_head": "tiny_sequence_transformer",
            "new_architecture": "template_residual_boosted_stack_new",
        },
        "winner": {
            "name": winner,
            "criterion": "minimum held-out composite saturation-energy/timing score with run-block and injection-source bootstrap CIs reported",
            "winner_score": float(ranked.iloc[0]["winner_score"]),
            "energy_fractional_sigma68": float(ranked.iloc[0]["energy_fractional_sigma68"]),
            "energy_fractional_sigma68_run_block_ci95": [
                float(ranked.iloc[0]["energy_fractional_sigma68_ci_low"]),
                float(ranked.iloc[0]["energy_fractional_sigma68_ci_high"]),
            ],
            "energy_fractional_sigma68_injection_source_ci95": [
                float(source_ci[source_ci["method"] == winner].iloc[0]["energy_fractional_sigma68_ci_low"]),
                float(source_ci[source_ci["method"] == winner].iloc[0]["energy_fractional_sigma68_ci_high"]),
            ],
            "time_sigma68_ns": float(ranked.iloc[0]["time_sigma68_ns"]),
            "time_sigma68_run_block_ci95": [
                float(ranked.iloc[0]["time_sigma68_ns_ci_low"]),
                float(ranked.iloc[0]["time_sigma68_ns_ci_high"]),
            ],
            "time_sigma68_injection_source_ci95": [
                float(source_ci[source_ci["method"] == winner].iloc[0]["time_sigma68_ns_ci_low"]),
                float(source_ci[source_ci["method"] == winner].iloc[0]["time_sigma68_ns_ci_high"]),
            ],
            "pileup_miss_rate": float(ranked.iloc[0]["pileup_miss_rate"]),
            "false_split_rate": float(ranked.iloc[0]["false_split_rate"]),
        },
        "artifacts": {
            "report": "REPORT.md",
            "manifest": "manifest.json",
            "claimed_ticket": "claimed_ticket.txt",
            "raw_reproduction": "reproduction_match_table.csv",
            "method_metrics": "method_metrics.csv",
            "winner_ranked_metrics": "winner_ranked_metrics.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "injection_source_bootstrap_ci": "injection_source_bootstrap_ci.csv",
            "strata_metrics": "strata_metrics.csv",
            "event_predictions": "event_predictions.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "caveats": [
            "Truth comes from controlled injections into raw-ROOT-derived clean pulses.",
            "Saturation is represented by an amplitude-ceiling proxy rather than electronics saturation flags.",
            "Injection-source cells are retained provenance units, not exact residual waveform indices.",
        ],
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "ticket_id": TICKET,
        "git_commit": base.git_commit(),
        "command": f"{sys.executable} scripts/{Path(__file__).name}",
        "runtime_seconds": runtime,
        "python": sys.version,
        "platform": platform.platform(),
        "outputs_sha256": {
            p.name: base.sha256_file(p)
            for p in sorted(OUT.iterdir())
            if p.is_file() and p.name != "manifest.json"
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
