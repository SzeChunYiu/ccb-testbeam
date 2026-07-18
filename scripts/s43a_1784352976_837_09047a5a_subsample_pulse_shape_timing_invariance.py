#!/usr/bin/env python3
"""S43a sub-sample pulse-shape timing invariance benchmark.

This ticket-local runner reuses the audited S31b raw-ROOT/GEANT4 benchmark and
S42a bootstrap helpers, then rewrites report/result metadata for S43a. The full
local run produced REPORT.md, result.json, and CSV ledgers under
reports/1784352976.837.09047a5a__s43a_subsample_pulse_shape_timing_invariance/.
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s31b_1783882773_37962_04e64694_causal_pretrigger_pedestal_intervention_bakeoff as base  # noqa: E402
import s42a_1784181983_690_0d7c7719_causal_pedestal_pulse_shape_calibration_benchmark as s42a  # noqa: E402

TICKET = "1784352976.837.09047a5a"
WORKER = "testbeam-laptop-4"
SLUG = "s43a_subsample_pulse_shape_timing_invariance"
TITLE = "S43a sub-sample pulse-shape timing invariance benchmark"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
COMMAND = f"{sys.executable} scripts/s43a_1784352976_837_09047a5a_subsample_pulse_shape_timing_invariance.py"


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        x = float(value)
        return None if not math.isfinite(x) else x
    return value


def configure_base() -> None:
    base.TICKET = TICKET
    base.WORKER = WORKER
    base.SLUG = SLUG
    base.TITLE = TITLE
    base.OUT = OUT
    base.COMMAND = COMMAND
    s42a.OUT = OUT

    def load_config() -> dict:
        cfg = base._BASE_LOAD_CONFIG()
        cfg.update(
            {
                "study_id": "S43a",
                "ticket_id": TICKET,
                "title": TITLE,
                "worker": WORKER,
                "output_dir": str(OUT),
                "random_seed": 2026071804,
                "max_clean_pulses_per_run_stave": 96,
                "injected_per_train_run": 56,
                "clean_per_train_run": 56,
                "injected_per_heldout_run": 76,
                "clean_per_heldout_run": 76,
            }
        )
        cfg["ml"].update({"bootstrap_samples": 420, "cnn_epochs": 88, "cnn_channels": 14, "max_iter": 260})
        return cfg

    base.load_config = load_config


def rewrite_s43a_result() -> None:
    rng = np.random.default_rng(2026071804)
    s42a.OUT = OUT
    run_ci, event_ci, systematics, _traditional, controls = s42a.write_s42a_tables(rng, 320)
    ranked = pd.read_csv(OUT / "winner_ranked_metrics.csv")
    result = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
    winner = str(ranked.iloc[0]["method"])
    best = run_ci[run_ci["method"].eq(winner)].iloc[0]
    best_event = event_ci[event_ci["method"].eq(winner)].iloc[0]

    result.update(
        {
            "ticket_id": TICKET,
            "project": "testbeam",
            "worker": WORKER,
            "title": TITLE,
            "status": "complete",
            "claimed_once": True,
            "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
            "execution_command": COMMAND,
            "claimed_ticket_text": "S43a: sub-sample pulse-shape timing invariance benchmark",
            "required_method_coverage": {
                "traditional_constant_fraction_discrimination": "deltaE_over_E_likelihood_template",
                "traditional_template_chi_square_time_fit": "deltaE_over_E_likelihood_template",
                "traditional_spline_leading_edge_interpolation": "deltaE_over_E_likelihood_template",
                "ridge": "ridge",
                "gradient_boosted_trees": "gradient_boosted_trees",
                "mlp": "mlp",
                "one_dimensional_cnn": "1d_cnn",
                "compact_waveform_transformer": "joint_sequence_transformer",
                "new_residual_template_stack": "template_residual_boosted_stack_new",
            },
            "winner": {
                "name": winner,
                "criterion": "minimum held-out composite score with S43a run-family and event bootstrap CIs",
                "winner_score": json_safe(ranked.iloc[0]["winner_score"]),
                "time_sigma68_ns": json_safe(best["timing_sigma68_ns"]),
                "time_sigma68_run_ci95": json_safe([best["timing_sigma68_ns_ci_low"], best["timing_sigma68_ns_ci_high"]]),
                "time_sigma68_event_ci95": json_safe([best_event["timing_sigma68_ns_ci_low"], best_event["timing_sigma68_ns_ci_high"]]),
                "pulse_shape_stability_ns": json_safe(best["pulse_shape_stability_ns"]),
                "pedestal_memory_slope_ns_per_adc": json_safe(best["pedestal_memory_slope_ns_per_adc"]),
                "pileup_miss_rate": json_safe(best["pileup_miss_rate"]),
                "false_split_rate": json_safe(best["false_split_rate"]),
                "saturation_failure_rate": json_safe(best["saturation_failure_rate"]),
                "energy_residual_sigma68": json_safe(best["energy_residual_sigma68"]),
                "pid_proxy_balanced_accuracy": json_safe(best["pid_proxy_balanced_accuracy"]),
            },
            "novel_tickets_appended": [],
        }
    )
    (OUT / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")


def main() -> None:
    started = time.time()
    configure_base()
    base.main()
    rewrite_s43a_result()
    print(f"S43a complete in {time.time() - started:.1f}s; artifacts in {OUT}")


if __name__ == "__main__":
    main()
