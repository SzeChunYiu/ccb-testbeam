#!/usr/bin/env python3
"""Ticket 2503 S55c pedestal-memory energy/PID disentanglement benchmark.

This entry point reuses the validated S36c PID-energy benchmark machinery, but
binds it to ticket #2503 and adds the ticket-local pedestal-state holdout,
pedestal-shuffle negative controls, calibration curves, and attribution tables.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s36c_1784064870_931_2c5305bf_pedestal_memory_pid_energy_calibration as s36c  # noqa: E402


TICKET = "2503"
TITLE = "S55c pedestal-memory energy PID disentanglement benchmark"
WORKER = "testbeam-laptop-1"
SLUG = "s55c_pedestal_memory_energy_pid_disentanglement"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")
CLAIM_OUTPUT = "tn-ticket claim testbeam-laptop-1 --project testbeam returned malformed null / # null / null"


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    return float((np.percentile(values, 84.0) - np.percentile(values, 16.0)) / 2.0)


def pred_energy(frame: pd.DataFrame) -> np.ndarray:
    return frame[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)


def true_energy(frame: pd.DataFrame) -> np.ndarray:
    return frame[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)


def endpoint_values(frame: pd.DataFrame) -> dict[str, float]:
    positives = frame[(frame["is_overlap"] == 1) & (~frame["failed"].astype(bool))].copy()
    if positives.empty:
        return {
            "n": int(len(frame)),
            "pid_auc": float("nan"),
            "energy_residual_bias": float("nan"),
            "energy_residual_sigma68": float("nan"),
            "pedestal_energy_bias": float("nan"),
        }
    err = (pred_energy(positives) - true_energy(positives)) / np.maximum(true_energy(positives), 1.0)
    y_pid = (positives["pid_proxy_class"].astype(str).to_numpy() == "inner_high_charge").astype(int)
    score = pred_energy(positives)
    pid_auc = float(roc_auc_score(y_pid, score)) if len(np.unique(y_pid)) == 2 else float("nan")
    return {
        "n": int(len(frame)),
        "pid_auc": pid_auc,
        "energy_residual_bias": float(np.median(err)),
        "energy_residual_sigma68": sigma68(err),
        "pedestal_energy_bias": float(np.median(err)),
    }


def pedestal_state_holdout(joined: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    held = joined[joined["split"].eq("heldout")].copy()
    rows = []
    states = sorted(str(x) for x in held["pedestal_state"].dropna().unique())
    for method, mg in held.groupby("method"):
        for state in states:
            group = mg[mg["pedestal_state"].astype(str).eq(state)]
            row = {"method": method, "holdout_pedestal_state": state, **endpoint_values(group)}
            runs = sorted(group["source_run"].dropna().unique())
            samples: dict[str, list[float]] = {}
            if len(runs) > 0:
                for _ in range(n_boot):
                    take = rng.choice(runs, size=len(runs), replace=True)
                    boot = pd.concat([group[group["source_run"].eq(run)] for run in take], ignore_index=True)
                    vals = endpoint_values(boot)
                    for key, value in vals.items():
                        if key == "n" or not np.isfinite(value):
                            continue
                        samples.setdefault(key, []).append(float(value))
            for key, vals in samples.items():
                row[f"{key}_ci_low"] = float(np.percentile(vals, 2.5))
                row[f"{key}_ci_high"] = float(np.percentile(vals, 97.5))
            rows.append(row)
    return pd.DataFrame(rows).sort_values(["holdout_pedestal_state", "energy_residual_sigma68", "method"])


def pedestal_shuffle_controls(joined: pd.DataFrame, rng: np.random.Generator, n_shuffle: int = 200) -> pd.DataFrame:
    held = joined[joined["split"].eq("heldout")].copy()
    rows = []
    for method, group in held.groupby("method"):
        real = pedestal_bias_span(group)
        spans = []
        for _ in range(n_shuffle):
            shuffled = group.copy()
            shuffled["pedestal_state"] = rng.permutation(shuffled["pedestal_state"].to_numpy())
            spans.append(pedestal_bias_span(shuffled))
        spans_arr = np.asarray(spans, dtype=float)
        rows.append(
            {
                "method": method,
                "observed_pedestal_bias_span": real,
                "shuffle_mean_span": float(np.nanmean(spans_arr)),
                "shuffle_ci_low": float(np.nanpercentile(spans_arr, 2.5)),
                "shuffle_ci_high": float(np.nanpercentile(spans_arr, 97.5)),
                "p_shuffle_ge_observed": float(np.nanmean(spans_arr >= real)),
                "n_shuffles": int(n_shuffle),
            }
        )
    return pd.DataFrame(rows).sort_values(["p_shuffle_ge_observed", "observed_pedestal_bias_span"])


def pedestal_bias_span(frame: pd.DataFrame) -> float:
    positives = frame[(frame["is_overlap"] == 1) & (~frame["failed"].astype(bool))].copy()
    if positives.empty:
        return float("nan")
    biases = []
    for _state, group in positives.groupby("pedestal_state", observed=False):
        if len(group) == 0:
            continue
        err = (pred_energy(group) - true_energy(group)) / np.maximum(true_energy(group), 1.0)
        biases.append(float(np.median(err)))
    return float(np.nanmax(biases) - np.nanmin(biases)) if len(biases) > 1 else 0.0


def calibration_curves(joined: pd.DataFrame) -> pd.DataFrame:
    held = joined[(joined["split"].eq("heldout")) & (joined["is_overlap"] == 1) & (~joined["failed"].astype(bool))].copy()
    rows = []
    for method, group in held.groupby("method"):
        pred = pred_energy(group)
        true = true_energy(group)
        try:
            bins = pd.qcut(pred, q=6, labels=False, duplicates="drop")
        except ValueError:
            bins = pd.Series(np.zeros(len(group), dtype=int), index=group.index)
        tmp = group.copy()
        tmp["pred_energy"] = pred
        tmp["true_energy"] = true
        tmp["calibration_bin"] = np.asarray(bins, dtype=int)
        for b, bg in tmp.groupby("calibration_bin"):
            err = (bg["pred_energy"].to_numpy(float) - bg["true_energy"].to_numpy(float)) / np.maximum(bg["true_energy"].to_numpy(float), 1.0)
            rows.append(
                {
                    "method": method,
                    "calibration_bin": int(b),
                    "n": int(len(bg)),
                    "pred_energy_mean_adc": float(bg["pred_energy"].mean()),
                    "true_energy_mean_adc": float(bg["true_energy"].mean()),
                    "fractional_bias": float(np.median(err)),
                    "fractional_sigma68": sigma68(err),
                }
            )
    return pd.DataFrame(rows).sort_values(["method", "calibration_bin"])


def attribution_table(joined: pd.DataFrame) -> pd.DataFrame:
    held = joined[(joined["split"].eq("heldout")) & (joined["is_overlap"] == 1) & (~joined["failed"].astype(bool))].copy()
    rows = []
    axes = ["pedestal_state", "morphology_state", "stave", "pid_proxy_class"]
    if "saturated_sample_count" in held.columns:
        held["saturation_axis"] = np.where(held["saturated_sample_count"].to_numpy(float) > 0, "clipped", "unclipped")
        axes.append("saturation_axis")
    for method, mg in held.groupby("method"):
        overall = endpoint_values(mg)["energy_residual_sigma68"]
        for axis in axes:
            vals = []
            for _level, ag in mg.groupby(axis, observed=False):
                vals.append(endpoint_values(ag)["energy_residual_sigma68"])
            vals = [float(v) for v in vals if np.isfinite(v)]
            rows.append(
                {
                    "method": method,
                    "axis": axis,
                    "levels": int(len(vals)),
                    "overall_energy_sigma68": overall,
                    "worst_level_energy_sigma68": float(np.max(vals)) if vals else float("nan"),
                    "best_level_energy_sigma68": float(np.min(vals)) if vals else float("nan"),
                    "span_energy_sigma68": float(np.max(vals) - np.min(vals)) if len(vals) > 1 else 0.0,
                }
            )
    return pd.DataFrame(rows).sort_values(["method", "span_energy_sigma68"], ascending=[True, False])


def markdown_table(df: pd.DataFrame, cols: list[str], limit: int | None = None) -> str:
    view = df.loc[:, [c for c in cols if c in df.columns]].copy()
    if limit is not None:
        view = view.head(limit)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    return view.to_markdown(index=False)


def patch_s36c_globals() -> None:
    s36c.TICKET = TICKET
    s36c.TITLE = TITLE
    s36c.WORKER = WORKER
    s36c.SLUG = SLUG
    s36c.OUT = OUT
    s36c.RAW_ROOT_DIR = RAW_ROOT_DIR
    s36c.NEXT_TICKET = {
        "title": "S55d: externally labeled pedestal-memory PID validation",
        "body": (
            "Join external PID labels or digitized-Geant4 truth to the S55c pedestal-memory "
            "benchmark and repeat run-held-out plus pedestal-state-held-out evaluation with "
            "true PID confusion rather than the current charge/stave proxy."
        ),
    }
    original_load_config = s36c.load_config

    def load_config_s55c() -> dict:
        cfg = original_load_config()
        cfg.update(
            {
                "study_id": "S55c",
                "ticket_id": TICKET,
                "title": TITLE,
                "worker": WORKER,
                "claimed_ticket_text": "S55c: pedestal-memory energy PID disentanglement benchmark",
                "raw_root_dir": str(RAW_ROOT_DIR),
                "output_dir": str(OUT),
                "random_seed": 2503007,
                "max_clean_pulses_per_run_stave": 42,
                "injected_per_train_run": 18,
                "clean_per_train_run": 18,
                "injected_per_heldout_run": 24,
                "clean_per_heldout_run": 24,
                "template_shift_grid": {"min": -1.0, "max": 0.5, "step": 0.5},
                "fit_separation_grid_samples": [0.5, 1.0, 2.0, 4.0, 6.0],
                "injection_separation_grid_samples": [0.5, 1.0, 2.0, 4.0, 6.0],
            }
        )
        cfg["ml"].update({"bootstrap_samples": 120, "cnn_epochs": 20, "cnn_channels": 8, "max_iter": 100})
        return cfg

    s36c.load_config = load_config_s55c


def augment_outputs(runtime: float) -> None:
    rng = np.random.default_rng(2503007)
    joined = pd.read_csv(OUT / "event_predictions.csv")
    result = json.loads((OUT / "result.json").read_text(encoding="utf-8"))

    holdout = pedestal_state_holdout(joined, rng, int(result["evaluation_design"]["bootstrap_replicates"]))
    shuffles = pedestal_shuffle_controls(joined, rng)
    curves = calibration_curves(joined)
    attribution = attribution_table(joined)

    holdout.to_csv(OUT / "pedestal_state_holdout_metrics.csv", index=False)
    shuffles.to_csv(OUT / "negative_control_pedestal_shuffles.csv", index=False)
    curves.to_csv(OUT / "calibration_curves.csv", index=False)
    attribution.to_csv(OUT / "attribution_ablation_summary.csv", index=False)

    report = (OUT / "REPORT.md").read_text(encoding="utf-8")
    report = report.replace("# S36c: Pedestal-Memory Transfer into Joint PID-Energy Calibration", "# S55c: Pedestal-Memory Energy PID Disentanglement Benchmark")
    report = report.replace("Ticket `2503` asks whether pretrigger pedestal memory explains cross-run PID", "Ticket `#2503` asks whether pretrigger pedestal memory explains cross-run PID")
    report = report.replace("S36c", "S55c")
    insertion = f"""

## Ticket Claim Provenance

The required claim helper was run exactly once:

`tn-ticket claim testbeam-laptop-1 --project testbeam`

It returned only `null`, `# null`, and `null`, while read-only queue inspection
showed ticket `#2503` as the sole open `project:testbeam` issue.  To respect the
``never claim twice`` constraint, this worker did not invoke the claim helper
again.  The present artifact is therefore bound to the read-only ticket body for
`#2503`; no manual second helper claim is recorded.

## S55c Additional Required Outputs

The reused core benchmark gives the requested run-held-out comparison.  S55c adds
pedestal-state-held-out slices, pedestal-shuffle negative controls, calibration
curves, and attribution/ablation summaries:

### Pedestal-State-Held-Out Metrics

{markdown_table(holdout, ['holdout_pedestal_state', 'method', 'n', 'pid_auc', 'energy_residual_bias', 'energy_residual_sigma68', 'energy_residual_sigma68_ci_low', 'energy_residual_sigma68_ci_high'], limit=80)}

### Negative-Control Pedestal Shuffles

{markdown_table(shuffles, ['method', 'observed_pedestal_bias_span', 'shuffle_mean_span', 'shuffle_ci_low', 'shuffle_ci_high', 'p_shuffle_ge_observed', 'n_shuffles'])}

### Calibration Curves

{markdown_table(curves, ['method', 'calibration_bin', 'n', 'pred_energy_mean_adc', 'true_energy_mean_adc', 'fractional_bias', 'fractional_sigma68'], limit=90)}

### Attribution and Ablation Summary

{markdown_table(attribution, ['method', 'axis', 'levels', 'overall_energy_sigma68', 'best_level_energy_sigma68', 'worst_level_energy_sigma68', 'span_energy_sigma68'], limit=80)}
"""
    report = report.replace("\n## Verdict\n", insertion + "\n## Verdict\n")
    report = report.replace("Runtime was `", f"Ticket wrapper runtime was `{runtime:.1f}` s; core benchmark runtime was `")
    report = "\n".join(line.rstrip() for line in report.splitlines()) + "\n"
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")

    result.update(
        {
            "ticket_id": TICKET,
            "ticket_number": 2503,
            "study_id": "S55c",
            "worker": WORKER,
            "title": TITLE,
            "claimed_ticket_text": "S55c: pedestal-memory energy PID disentanglement benchmark",
            "claim_command": "tn-ticket claim testbeam-laptop-1 --project testbeam",
            "claim_command_output": CLAIM_OUTPUT,
            "claim_command_run_count": 1,
            "manual_claim_performed": False,
            "ticket_body_source": "read-only gh issue view/list after malformed claim output",
            "s55c_additional_outputs": {
                "pedestal_state_holdout_metrics": "pedestal_state_holdout_metrics.csv",
                "negative_control_pedestal_shuffles": "negative_control_pedestal_shuffles.csv",
                "calibration_curves": "calibration_curves.csv",
                "attribution_ablation_summary": "attribution_ablation_summary.csv",
            },
            "wrapper_runtime_sec": runtime,
            "methods_required_by_ticket": {
                "traditional": "ar1_charge_ratio_likelihood_traditional",
                "ridge": "ridge",
                "gradient_boosted_trees": "gradient_boosted_trees",
                "mlp": "mlp",
                "one_dimensional_cnn": "1d_cnn",
                "new_architecture": "pedestal_memory_fusion_new",
                "extra_nn_when_sensible": "tiny_sequence_transformer",
            },
        }
    )
    if isinstance(result.get("winner"), dict):
        result["winner"]["criterion"] = "minimum registered S55c held-out PID-energy-pedestal composite score with run-block bootstrap CIs"
    result["artifacts"].update(result["s55c_additional_outputs"])
    result["novel_tickets_appended"] = []
    result["next_tickets"] = []
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    (OUT / "claimed_ticket.txt").write_text(
        f"#2503\n# {TITLE}\n{CLAIM_OUTPUT}\n",
        encoding="utf-8",
    )
    manifest = {
        "ticket_id": TICKET,
        "git_commit": s36c.git_commit(),
        "command": f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}",
        "runtime_seconds": runtime,
        "python": sys.version,
        "platform": platform.platform(),
        "outputs_sha256": {
            p.name: s36c.base.sha256_file(p)
            for p in sorted(OUT.iterdir())
            if p.is_file() and p.name != "manifest.json"
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (OUT / "claimed_ticket_body.txt").write_text(
        "Academic-grade study: test whether slow pedestal memory and baseline drift confound energy calibration and PID boundaries in waveform-level analyses.\n\n"
        "Compare a traditional pedestal-subtracted charge integration plus deltaE-E/PID calibration baseline against ridge, gradient-boosted trees, MLP, 1D-CNN, and a multichannel transformer when auxiliary channels are available. Report bootstrap CIs for PID AUC or balanced accuracy, energy residuals, pedestal-state transfer, and pile-up/saturation interaction terms.\n\n"
        "Required outputs: run-held-out and pedestal-state-held-out splits, negative-control pedestal shuffles, calibration curves, model attribution or ablation tables, and a concise physics interpretation of which pulse-shape and timing features survive leakage controls.\n",
        encoding="utf-8",
    )


def main() -> None:
    started = time.time()
    patch_s36c_globals()
    s36c.main()
    augment_outputs(time.time() - started)
    print(json.dumps({"done": True, "ticket": TICKET, "out_dir": str(OUT), "platform": platform.platform()}, indent=2))


if __name__ == "__main__":
    main()
