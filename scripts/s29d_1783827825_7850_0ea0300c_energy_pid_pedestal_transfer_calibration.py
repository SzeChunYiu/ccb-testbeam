#!/usr/bin/env python3
"""S29d energy-PID pedestal transfer calibration study.

This ticket-local runner reuses the audited S26c raw-ROOT reproduction and
joint PID/energy/timing benchmark, then adds S29d transfer tables for pedestal
regimes, saturation bands, pile-up load, pulse-shape families, and run-family
leave-out behavior.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BASE_SCRIPT = ROOT / "scripts/s26c_1783800116_3081_430d48e6_pulse_pid_energy_timing_joint_inference_bakeoff.py"
TICKET = "1783827825.7850.0ea0300c"
WORKER = "testbeam-laptop-4"
SLUG = "s29d_energy_pid_pedestal_transfer_calibration"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
TITLE = "S29d energy-PID pedestal transfer calibration study"


def load_base():
    spec = importlib.util.spec_from_file_location("s29d_base_s26c", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["s29d_base_s26c"] = module
    spec.loader.exec_module(module)
    return module


BASE = load_base()


def configure_base() -> None:
    original_load_config = BASE.load_config

    def load_config() -> dict:
        cfg = original_load_config()
        cfg.update(
            {
                "study_id": "S29d",
                "ticket_id": TICKET,
                "title": TITLE,
                "worker": WORKER,
                "output_dir": str(OUT),
                "random_seed": 2026071217,
                "max_clean_pulses_per_run_stave": 32,
                "injected_per_train_run": 16,
                "clean_per_train_run": 16,
                "injected_per_heldout_run": 22,
                "clean_per_heldout_run": 22,
            }
        )
        cfg["ml"].update({"bootstrap_samples": 180, "cnn_epochs": 24, "cnn_channels": 8, "max_iter": 90})
        return cfg

    BASE.TICKET = TICKET
    BASE.WORKER = WORKER
    BASE.SLUG = SLUG
    BASE.OUT = OUT
    BASE.load_config = load_config
    BASE.transformer_prediction = fast_transformer_prediction


def fast_transformer_prediction(events: pd.DataFrame, waveforms: np.ndarray, cfg: dict) -> pd.DataFrame:
    if BASE.torch is None:
        raise RuntimeError("torch is required for transformer benchmark")
    seed = int(cfg["random_seed"]) + 300
    BASE.torch.manual_seed(seed)
    BASE.torch.set_num_threads(1)
    x_np = waveforms.astype(np.float32)
    x_np = x_np - np.median(x_np[:, :4], axis=1, keepdims=True)
    scale = np.maximum(np.percentile(np.abs(x_np), 95, axis=1, keepdims=True), 1.0)
    x_np = np.clip(x_np / scale, -4.0, 4.0).astype(np.float32)
    y_overlap = events["is_overlap"].to_numpy(dtype=np.float32)
    y_pid = events["pid_label"].to_numpy(dtype=np.float32)
    y_reg, max_amp = BASE.base.regression_targets(events, waveforms)
    y_reg = y_reg.astype(np.float32)
    train = events["split"].to_numpy() == "train"
    ds = BASE.TensorDataset(
        BASE.torch.from_numpy(x_np[train]),
        BASE.torch.from_numpy(y_overlap[train]),
        BASE.torch.from_numpy(y_pid[train]),
        BASE.torch.from_numpy(y_reg[train]),
    )
    loader = BASE.DataLoader(ds, batch_size=48, shuffle=True, generator=BASE.torch.Generator().manual_seed(seed))
    model = BASE.JointSequenceTransformer(waveforms.shape[1])
    opt = BASE.torch.optim.AdamW(model.parameters(), lr=1.4e-3, weight_decay=2e-3)
    bce = BASE.nn.BCEWithLogitsLoss()
    mse = BASE.nn.SmoothL1Loss()
    for _epoch in range(22):
        model.train()
        for xb, yo, yp, yr in loader:
            opt.zero_grad(set_to_none=True)
            ologit, plogit, reg = model(xb)
            pos = yo > 0.5
            loss = bce(ologit, yo) + 0.8 * bce(plogit, yp)
            if bool(pos.any()):
                loss = loss + 1.8 * mse(reg[pos], yr[pos])
            loss.backward()
            opt.step()
    model.eval()
    scores = []
    pid_scores = []
    regs = []
    with BASE.torch.no_grad():
        for start in range(0, len(x_np), 512):
            xb = BASE.torch.from_numpy(x_np[start : start + 512])
            ologit, plogit, reg = model(xb)
            scores.append(BASE.torch.sigmoid(ologit).cpu().numpy())
            pid_scores.append(BASE.torch.sigmoid(plogit).cpu().numpy())
            regs.append(reg.cpu().numpy())
    return BASE.attach_pid(
        BASE.base.as_prediction(events, np.concatenate(scores), np.vstack(regs), max_amp, "joint_sequence_transformer"),
        np.concatenate(pid_scores),
    )


def _fmt(x: object) -> str:
    try:
        y = float(x)
    except Exception:
        return str(x)
    return f"{y:.5g}" if np.isfinite(y) else "nan"


def md_table(df: pd.DataFrame, cols: list[str]) -> str:
    view = df.loc[:, cols].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(_fmt)
    return view.to_markdown(index=False)


def _metric(frame: pd.DataFrame) -> dict:
    vals = BASE.metric_values(frame)
    keep = [
        "pid_balanced_accuracy",
        "pid_efficiency",
        "pid_purity",
        "energy_fractional_bias",
        "energy_fractional_sigma68",
        "time_sigma68_ns",
        "pileup_miss_rate",
        "false_split_rate",
        "n_events",
        "n_positive",
    ]
    return {k: vals[k] for k in keep}


def _bootstrap_ci(group: pd.DataFrame, field: str, rng: np.random.Generator, n_boot: int) -> tuple[float, float]:
    runs = sorted(group["source_run"].unique())
    if len(runs) < 2:
        return float("nan"), float("nan")
    vals = []
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="y_pred contains classes not in y_true")
        for _ in range(n_boot):
            take = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["source_run"] == run] for run in take], ignore_index=True)
            val = _metric(boot).get(field, float("nan"))
            if np.isfinite(val):
                vals.append(float(val))
    if not vals:
        return float("nan"), float("nan")
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def s29d_transfer_tables(rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    joined = pd.read_csv(OUT / "event_predictions.csv")
    held = joined[joined["split"] == "heldout"].copy()
    held["pedestal_regime"] = pd.qcut(held["shape_area_over_amp"], 3, labels=["low_area_over_peak", "mid_area_over_peak", "high_area_over_peak"], duplicates="drop")
    held["saturation_band"] = pd.qcut(held["true_energy_proxy_adc"], 3, labels=["low_energy", "mid_energy", "high_energy"], duplicates="drop")
    held["pileup_load"] = pd.cut(held["true_sep_sample"] * 10.0, bins=[0, 15, 35, 80], labels=["high_overlap", "mid_overlap", "low_overlap"], include_lowest=True)
    held["shape_family"] = np.select(
        [
            held["shape_area_over_amp"] <= held["shape_area_over_amp"].quantile(0.33),
            held["shape_area_over_amp"] >= held["shape_area_over_amp"].quantile(0.67),
        ],
        ["narrow_high_peak", "broad_tail"],
        default="nominal_shape",
    )
    family_map = {int(run): f"heldout_run_family_{i+1}" for i, run in enumerate(sorted(held["source_run"].unique()))}
    held["run_family"] = held["source_run"].map(family_map)

    rows = []
    for field in ["run_family", "pedestal_regime", "saturation_band", "pileup_load", "shape_family", "stave"]:
        for (method, value), group in held.groupby(["method", field], observed=False):
            if len(group) < 5:
                continue
            row = {"transfer_axis": field, "stratum": str(value), "method": method, **_metric(group)}
            for metric in ["pid_balanced_accuracy", "energy_fractional_sigma68", "time_sigma68_ns"]:
                lo, hi = _bootstrap_ci(group, metric, rng, 25)
                row[f"{metric}_ci_low"] = lo
                row[f"{metric}_ci_high"] = hi
            rows.append(row)
    transfer = pd.DataFrame(rows).sort_values(["transfer_axis", "stratum", "method"])

    worst_rows = []
    for method, group in transfer.groupby("method"):
        worst_rows.append(
            {
                "method": method,
                "worst_pid_balanced_accuracy": float(group["pid_balanced_accuracy"].min()),
                "worst_energy_fractional_sigma68": float(group["energy_fractional_sigma68"].max()),
                "max_abs_energy_bias": float(group["energy_fractional_bias"].abs().max()),
                "worst_time_sigma68_ns": float(group["time_sigma68_ns"].max()),
                "worst_pileup_miss_rate": float(group["pileup_miss_rate"].max()),
                "n_transfer_cells": int(len(group)),
            }
        )
    stress = pd.DataFrame(worst_rows)
    stress["transfer_score"] = (
        stress["worst_energy_fractional_sigma68"]
        + 0.01 * stress["worst_time_sigma68_ns"]
        + 0.25 * (1.0 - stress["worst_pid_balanced_accuracy"])
        + 0.05 * stress["worst_pileup_miss_rate"]
        + 0.10 * stress["max_abs_energy_bias"]
    )
    stress = stress.sort_values("transfer_score").reset_index(drop=True)

    rank = pd.read_csv(OUT / "winner_ranked_metrics.csv")
    merged = rank.merge(stress, on="method", how="left", suffixes=("_overall", "_stress"))

    method_specs = pd.DataFrame(
        [
            {
                "method": "deltaE_over_E_likelihood_template",
                "family": "strong traditional",
                "role": "charge-integration, template timing, and deltaE/E Gaussian PID likelihood",
            },
            {"method": "ridge", "family": "linear ML", "role": "regularized linear accessibility test"},
            {"method": "gradient_boosted_trees", "family": "tree ML", "role": "nonlinear threshold and saturation interactions"},
            {"method": "mlp", "family": "tabular neural network", "role": "dense nonlinear pulse-summary model"},
            {"method": "1d_cnn", "family": "waveform neural network", "role": "local 18-sample convolutional waveform model"},
            {"method": "joint_sequence_transformer", "family": "new architecture", "role": "compact full-context waveform transformer with PID and energy heads"},
            {"method": "template_residual_boosted_stack_new", "family": "new architecture", "role": "physics residual stack using traditional estimates as residual features"},
        ]
    )
    return transfer, stress, merged, method_specs


def append_report_and_result() -> None:
    rng = np.random.default_rng(2026071217)
    transfer, stress, merged, specs = s29d_transfer_tables(rng)
    transfer.to_csv(OUT / "s29d_transfer_axis_metrics.csv", index=False)
    stress.to_csv(OUT / "s29d_stress_worst_case_metrics.csv", index=False)
    merged.to_csv(OUT / "s29d_overall_vs_transfer_ranking.csv", index=False)
    specs.to_csv(OUT / "s29d_method_panel.csv", index=False)

    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    primary_winner = result["winner"]["name"]
    transfer_winner = str(stress.iloc[0]["method"])
    result.update(
        {
            "ticket_id": TICKET,
            "worker": WORKER,
            "title": TITLE,
            "status": "complete",
            "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
            "s29d_transfer_winner": {
                "name": transfer_winner,
                "criterion": "minimum worst-case transfer score across run family, pedestal regime, saturation band, pile-up load, pulse-shape family, and stave strata",
                "transfer_score": float(stress.iloc[0]["transfer_score"]),
                "worst_energy_fractional_sigma68": float(stress.iloc[0]["worst_energy_fractional_sigma68"]),
                "worst_pid_balanced_accuracy": float(stress.iloc[0]["worst_pid_balanced_accuracy"]),
                "max_abs_energy_bias": float(stress.iloc[0]["max_abs_energy_bias"]),
            },
            "winner": {
                **result["winner"],
                "name": primary_winner,
                "s29d_transfer_check": transfer_winner,
                "interpretation": "primary winner is the overall held-out composite-score winner; transfer winner is reported as a robustness cross-check",
            },
        }
    )
    result["artifacts"].update(
        {
            "s29d_method_panel": "s29d_method_panel.csv",
            "s29d_transfer_axis_metrics": "s29d_transfer_axis_metrics.csv",
            "s29d_stress_worst_case_metrics": "s29d_stress_worst_case_metrics.csv",
            "s29d_overall_vs_transfer_ranking": "s29d_overall_vs_transfer_ranking.csv",
        }
    )
    result["caveats"].extend(
        [
            "Pedestal regimes are waveform-derived area-over-peak strata rather than dedicated pedestal-run labels.",
            "Saturation bands use controlled-injection energy proxy strata because hardware saturation metadata are not present in the waveform tree.",
            "Run-family transfer is implemented as complete held-out source-run families with run-block bootstrap CIs.",
        ]
    )
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    report_path = OUT / "REPORT.md"
    report = report_path.read_text(encoding="utf-8")
    report = report.replace("# S26c: pulse PID, energy, and timing joint inference bakeoff", f"# {TITLE}", 1)
    appendix = f"""

## S29d transfer calibration synthesis

The S29d ticket asks whether waveform-derived energy and PID calibration remains
stable across pedestal regimes, saturation bands, pile-up load, and pulse-shape
families.  The primary winner retained in `result.json` is the overall
held-out composite-score winner `{primary_winner}`.  A stricter transfer-only
stress score, computed from worst-case strata, selects `{transfer_winner}`.

The stress score is

`T_m = R68_E,worst + 0.01 sigma_t,worst + 0.25(1-BAcc_PID,worst) + 0.05 r_miss,worst + 0.10 |bias_E|_max`.

This stress score is not a replacement for the primary winner rule; it is the
ticket-specific systematic guard for calibration transfer.

### Method panel

{md_table(specs, ['method', 'family', 'role'])}

### Overall versus transfer ranking

{md_table(merged, ['method', 'winner_score', 'pid_balanced_accuracy', 'energy_fractional_sigma68', 'time_sigma68_ns', 'transfer_score', 'worst_pid_balanced_accuracy', 'worst_energy_fractional_sigma68', 'max_abs_energy_bias'])}

### Worst-case transfer summary

{md_table(stress, ['method', 'transfer_score', 'worst_pid_balanced_accuracy', 'worst_energy_fractional_sigma68', 'max_abs_energy_bias', 'worst_time_sigma68_ns', 'worst_pileup_miss_rate', 'n_transfer_cells'])}

### Transfer-axis table with bootstrap intervals

{md_table(transfer, ['transfer_axis', 'stratum', 'method', 'pid_balanced_accuracy', 'pid_balanced_accuracy_ci_low', 'pid_balanced_accuracy_ci_high', 'energy_fractional_sigma68', 'energy_fractional_sigma68_ci_low', 'energy_fractional_sigma68_ci_high', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high'])}

## S29d systematics and caveats

The pedestal axis is derived from held-out pulse area-over-peak quantiles after
raw pedestal subtraction; it therefore tests transfer across waveform pedestal
and shape regimes, not a dedicated electronics pedestal scan.  The saturation
axis is a controlled-injection energy-proxy band.  Pile-up load is the injected
two-pulse separation, with high-overlap events forming the hardest recovery
cell.  Pulse-shape families are narrow, nominal, and broad-tail quantiles of the
same held-out waveform-shape observable.  The run-family split uses complete
held-out source runs, and all quoted intervals in the transfer table are
percentile run-block bootstrap intervals.

The PID endpoint remains a deterministic raw-waveform high-dE/dx-depth proxy.
This makes the benchmark appropriate for architecture ranking and calibration
stress testing, but not a final external particle-ID measurement.  The strong
traditional method is retained as an interpretable calibration baseline even
where neural or hybrid methods win the composite objective.
"""
    report_path.write_text(report + appendix, encoding="utf-8")

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket_id"] = TICKET
    manifest["command"] = f"{sys.executable} scripts/s29d_1783827825_7850_0ea0300c_energy_pid_pedestal_transfer_calibration.py"
    manifest["outputs_sha256"] = {
        p.name: BASE.base.sha256_file(p) if hasattr(BASE, "base") else BASE.s26b.sha256_file(p)
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    started = time.time()
    configure_base()
    BASE.main()
    append_report_and_result()
    print(json.dumps({"done": True, "ticket": TICKET, "out_dir": str(OUT.relative_to(ROOT)), "runtime_sec": time.time() - started}, indent=2))


if __name__ == "__main__":
    main()
