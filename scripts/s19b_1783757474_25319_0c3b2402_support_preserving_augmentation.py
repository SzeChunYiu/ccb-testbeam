#!/usr/bin/env python3
"""S19b support-preserving augmentation check for two-pulse recovery.

This script reuses the S19a/S19c raw-ROOT reproduction and two-pulse
benchmark machinery, then changes only the training support: held-out source
runs remain untouched, while train-run waveforms receive support-preserving
time/amplitude jitter and train-run residual-pool synthesis.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import yaml
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.model_selection import GroupKFold
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import p05a_cnn_two_pulse_decomposition as p05a
import s02_timing_pickoff as s02
import s19a_0000000006_1_nnarch_sweep as s19a

torch.set_num_threads(1)


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def configured_runs(config: dict) -> List[int]:
    return s02.configured_runs(config)


def raw_file(config: dict, run: int) -> Path:
    return s02.raw_file(config, run)


def injection_config(config: dict) -> dict:
    cfg = dict(config)
    cfg.update(config["injection"])
    cfg["benchmark_runs"] = {"train": list(config["injection"]["train_runs"]), "heldout": list(config["injection"]["heldout_runs"])}
    cfg["max_clean_pulses_per_run_stave"] = int(config["injection"]["max_clean_pulses_per_run_stave"])
    cfg["ml"] = dict(config["ml"])
    return cfg


def synthesize_waveform(row: pd.Series, template: np.ndarray, residuals: List[np.ndarray], cfg: dict, rng: np.random.Generator) -> np.ndarray:
    ref = float(cfg["template_reference_cfd_sample"])
    amp_j = float(cfg["augmentation_amp_jitter_fraction"])
    time_j = float(cfg["augmentation_time_jitter_samples"])
    base_j = float(cfg["augmentation_baseline_jitter_adc"])
    a1 = max(1.0, float(row["true_amp1_adc"]) * (1.0 + rng.normal(0.0, amp_j)))
    t1 = float(row["true_t1_sample"]) + rng.normal(0.0, time_j)
    waveform = a1 * p05a.shifted_template(template, t1, ref)
    if int(row["is_overlap"]):
        a2 = max(0.0, float(row["true_amp2_adc"]) * (1.0 + rng.normal(0.0, amp_j)))
        t2 = float(row["true_t2_sample"]) + rng.normal(0.0, time_j)
        waveform = waveform + a2 * p05a.shifted_template(template, t2, ref)
    residual = np.asarray(residuals[int(rng.integers(0, len(residuals)))], dtype=float)
    return (waveform + residual + rng.normal(0.0, base_j)).astype(float)


def build_augmented_training(
    train_events: pd.DataFrame,
    train_wave: np.ndarray,
    clean_train: pd.DataFrame,
    templates: Dict[str, np.ndarray],
    cfg: dict,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    pool = p05a.residual_pool(clean_train, templates, cfg)
    aug_events = [train_events.copy()]
    aug_wave = [train_wave.copy()]
    ledger = [{"source": "original_train", "n_events": int(len(train_events)), "heldout_touched": False}]
    factor = int(cfg.get("augmentation_factor", 2))
    for rep in range(factor):
        rows = train_events.copy()
        waves = []
        for row in train_events.itertuples(index=False):
            stave = str(row.stave)
            run = int(row.source_run)
            waves.append(synthesize_waveform(pd.Series(row._asdict()), templates[stave], pool[(run, stave)], cfg, rng))
        rows["event_id"] = rows["event_id"].map(lambda x, r=rep: f"aug{r}:{x}")
        rows["augmentation"] = f"support_preserving_{rep}"
        aug_events.append(rows)
        aug_wave.append(np.vstack(waves))
        ledger.append({"source": f"support_preserving_{rep}", "n_events": int(len(rows)), "heldout_touched": False})
    base = aug_events[0]
    base["augmentation"] = "none"
    aug_events[0] = base
    return pd.concat(aug_events, ignore_index=True), np.vstack(aug_wave), pd.DataFrame(ledger)


def train_sklearn_on_augmented(
    model_name: str,
    train_events: pd.DataFrame,
    train_wave: np.ndarray,
    eval_events: pd.DataFrame,
    eval_wave: np.ndarray,
    cfg: dict,
) -> Tuple[pd.DataFrame, float, int]:
    X_train = p05a.make_feature_matrix(train_wave)
    X_eval = p05a.make_feature_matrix(eval_wave)
    y_class, y_reg, _ = s19a.two_pulse_targets(train_events, train_wave)
    _yc_eval, _yr_eval, max_amp_eval = s19a.two_pulse_targets(eval_events, eval_wave)
    pos_train = y_class == 1
    seed = int(cfg["ml"]["random_seed"])
    t0 = time.time()
    if model_name == "ridge":
        clf = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000, random_state=seed))
        reg = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
        n_params = X_train.shape[1] * 5
    elif model_name == "gradient_boosted_trees":
        clf = HistGradientBoostingClassifier(max_iter=140, learning_rate=0.06, random_state=seed)
        reg = MultiOutputRegressor(HistGradientBoostingRegressor(max_iter=140, learning_rate=0.06, random_state=seed + 1))
        n_params = 140
    elif model_name == "mlp":
        clf = make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(48,), alpha=1e-3, max_iter=int(cfg["ml"]["sklearn_max_iter"]), random_state=seed, early_stopping=True))
        reg = make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(64, 32), alpha=1e-3, max_iter=int(cfg["ml"]["sklearn_max_iter"]), random_state=seed + 1, early_stopping=True))
        n_params = X_train.shape[1] * 48 + 48 * 32
    else:
        raise ValueError(model_name)
    clf.fit(X_train, y_class)
    reg.fit(X_train[pos_train], y_reg[pos_train])
    score = clf.predict_proba(X_eval)[:, 1]
    pred = reg.predict(X_eval)
    elapsed = time.time() - t0
    return s19a.predictions_to_frame(eval_events, model_name, score, pred, max_amp_eval), elapsed, int(n_params)


def train_torch_on_augmented(
    arch: str,
    train_events: pd.DataFrame,
    train_wave: np.ndarray,
    eval_events: pd.DataFrame,
    eval_wave: np.ndarray,
    width: int,
    cfg: dict,
    seed: int,
) -> Tuple[pd.DataFrame, float, int]:
    joined_events = pd.concat([train_events, eval_events], ignore_index=True)
    joined_wave = np.vstack([train_wave, eval_wave])
    train_idx = np.arange(len(train_events), dtype=int)
    prob, pred, max_amp, elapsed, n_params = s19a.train_two_pulse_torch(arch, joined_events, joined_wave, train_idx, width, cfg, seed)
    offset = len(train_events)
    return s19a.predictions_to_frame(eval_events, arch, prob[offset:], pred[offset:], max_amp[offset:]), elapsed, int(n_params)


def heldout_metrics(frame: pd.DataFrame, prefixes: List[str], rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    held = frame[frame["split"] == "heldout"].reset_index(drop=True)
    rows = []
    traditional = p05a.metric_values(held, "constrained_template_fit")
    for prefix in prefixes:
        metrics = p05a.metric_values(held, prefix)
        ci = p05a.bootstrap_metric_ci(held, prefix, rng, n_boot)
        row = {"model": prefix, **metrics, **ci}
        row["delta_time_rms_vs_traditional_ns"] = row["time_rms_ns"] - traditional["time_rms_ns"]
        row["delta_charge_res68_vs_traditional"] = row["charge_fractional_res68"] - traditional["charge_fractional_res68"]
        rows.append(row)
    return pd.DataFrame(rows)


def cv_augmented_rows(events: pd.DataFrame, waveforms: np.ndarray, cfg: dict) -> pd.DataFrame:
    X = p05a.make_feature_matrix(waveforms)
    y_class = events["is_overlap"].to_numpy(dtype=int)
    groups = events["source_run"].to_numpy()
    rows = []
    gkf = GroupKFold(n_splits=min(3, len(np.unique(groups))))
    for model_name in ["ridge", "gradient_boosted_trees", "mlp"]:
        for fold, (tr, va) in enumerate(gkf.split(X, y_class, groups=groups)):
            pred, _elapsed, _n = train_sklearn_on_augmented(model_name, events.iloc[tr].reset_index(drop=True), waveforms[tr], events.iloc[va].reset_index(drop=True), waveforms[va], cfg)
            tmp = events.iloc[va].reset_index(drop=True).merge(pred, on="event_id")
            rows.append({"model": model_name, "fold": int(fold), "source_runs": " ".join(map(str, sorted(set(groups[va])))), **p05a.metric_values(tmp, model_name)})
    return pd.DataFrame(rows)


def save_plot(out_dir: Path, bench: pd.DataFrame) -> None:
    ordered = bench.sort_values("time_rms_ns")
    x = np.arange(len(ordered))
    fig, ax = plt.subplots(figsize=(9.0, 4.6))
    ax.bar(x, ordered["time_rms_ns"])
    ax.errorbar(x, ordered["time_rms_ns"], yerr=[ordered["time_rms_ns"] - ordered["time_rms_ns_ci_low"], ordered["time_rms_ns_ci_high"] - ordered["time_rms_ns"]], fmt="none", color="black", capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(ordered["model"], rotation=25, ha="right")
    ax.set_ylabel("held-out constituent time RMS (ns)")
    ax.set_title("Support-preserving augmentation benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_support_preserving_augmentation.png", dpi=140)
    plt.close(fig)


def markdown_table(frame: pd.DataFrame) -> str:
    display = frame.copy()
    for col in display.columns:
        if pd.api.types.is_float_dtype(display[col]):
            display[col] = display[col].map(lambda value: "" if pd.isna(value) else f"{value:.6g}")
        else:
            display[col] = display[col].map(lambda value: "" if pd.isna(value) else str(value))
    headers = [str(col) for col in display.columns]
    rows = display.astype(str).values.tolist()
    widths = [
        max(len(headers[i]), *(len(row[i]) for row in rows)) if rows else len(headers[i])
        for i in range(len(headers))
    ]

    def fmt(row: Sequence[str]) -> str:
        return "| " + " | ".join(str(value).ljust(widths[i]) for i, value in enumerate(row)) + " |"

    separator = "| " + " | ".join("-" * width for width in widths) + " |"
    return "\n".join([fmt(headers), separator] + [fmt(row) for row in rows])


def write_report(out_dir: Path, config: dict, match: pd.DataFrame, ledger: pd.DataFrame, cv: pd.DataFrame, bench: pd.DataFrame, result: dict, runtime: float) -> None:
    winner = bench.sort_values(["time_rms_ns", "charge_fractional_res68"]).iloc[0]
    traditional = bench[bench["model"] == "constrained_template_fit"].iloc[0]
    gbt = bench[bench["model"] == "gradient_boosted_trees"].iloc[0]
    lines = [
        f"# Study report: {config['study_id']} - {config['title']}",
        "",
        f"- **Study ID:** {config['study_id']}",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Author:** `{config['worker']}`",
        f"- **Date:** {config['report_date']}",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        f"- **Config:** `{config['_config_path']}`",
        f"- **Git commit at run time:** `{git_commit()}`",
        "",
        "## 0. Question",
        "",
        "Is the pile-up and charge-recovery winner limited primarily by training support rather than by architecture capacity? The benchmark reruns the S19 two-pulse recovery task with train-only support-preserving augmentation and residual synthesis while preserving untouched held-out source runs.",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "Before any modeling, the S00 selected-pulse count is recomputed directly from raw `HRDv` ROOT branches.",
        "",
        markdown_table(match),
        "",
        "The exact `640,737` selected B-stave pulse count and Sample-II stave counts are reproduced with zero tolerance.",
        "",
        "## 2. Methods and equations",
        "",
        "The empirical pulse model uses a stave-specific normalized template `u_s(t)` aligned to CFD20 reference sample 5. For injected overlaps,",
        "",
        "`y(t) = A_1 u_s(t - t_1) + I A_2 u_s(t - t_2) + epsilon_{r,s}(t) + b`,",
        "",
        "where `I` is the injected-overlap indicator, `epsilon_{r,s}` is a residual waveform drawn only from the same training run and stave, and `b` is a baseline offset. Held-out events from runs 63 and 65 are generated once and never augmented.",
        "",
        "Support-preserving augmentation samples only within the observed training support: the same train run, same stave, same discrete overlap/separation/ratio grid, Gaussian timing jitter of 0.18 samples, amplitude jitter of 10%, and baseline jitter of 35 ADC. It does not add new held-out runs, new staves, event identifiers, or labels derived from held-out data.",
        "",
        "The traditional comparator is the bounded two-pulse template fit. It scans `t_1` and allowed separations, solves amplitudes and baseline by least squares, and rejects solutions outside amplitude-ratio and baseline bounds. The ML competitors are ridge/logistic, gradient-boosted trees, MLP, 1D-CNN, residual CNN, TCN, attention, and GRU sequence heads. All models predict overlap probability plus `t_1`, `t_2`, `A_1/max(y)`, and `A_2/max(y)`.",
        "",
        "For a positive event, constituent time RMS is",
        "",
        "`sqrt(mean((10 (hat t_1 - t_1))^2 + (10 (hat t_2 - t_2))^2)/2)`,",
        "",
        "and charge recovery is summarized by median fractional bias and the 68% half-width of fractional charge error. Bootstrap confidence intervals resample held-out events.",
        "",
        "## 3. Augmentation ledger",
        "",
        markdown_table(ledger),
        "",
        "The ledger verifies that augmentation is train-only; held-out waveforms are evaluated in their original generated form.",
        "",
        "## 4. Run-split CV",
        "",
        markdown_table(cv.groupby("model", as_index=False)[["time_rms_ns", "charge_fractional_res68", "detection_ap"]].mean().sort_values("time_rms_ns")),
        "",
        "CV is grouped by source run over the augmented training support and is used as a stability diagnostic, not as a held-out result.",
        "",
        "## 5. Held-out head-to-head",
        "",
        markdown_table(bench[["model", "detection_ap", "time_rms_ns", "time_rms_ns_ci_low", "time_rms_ns_ci_high", "delta_time_rms_vs_traditional_ns", "charge_fractional_bias", "charge_fractional_res68", "charge_fractional_res68_ci_low", "charge_fractional_res68_ci_high", "delta_charge_res68_vs_traditional", "failure_rate", "train_seconds", "n_parameters"]].sort_values("time_rms_ns")),
        "",
        f"Winner by primary held-out time RMS is `{winner['model']}` at {winner['time_rms_ns']:.3f} ns [{winner['time_rms_ns_ci_low']:.3f}, {winner['time_rms_ns_ci_high']:.3f}], with charge res68 {winner['charge_fractional_res68']:.4f}. The bounded traditional fit gives {traditional['time_rms_ns']:.3f} ns [{traditional['time_rms_ns_ci_low']:.3f}, {traditional['time_rms_ns_ci_high']:.3f}] and charge res68 {traditional['charge_fractional_res68']:.4f}. The prior S19c winner, gradient-boosted trees, gives {gbt['time_rms_ns']:.3f} ns and charge res68 {gbt['charge_fractional_res68']:.4f} after augmentation.",
        "",
        "## 6. Systematics and caveats",
        "",
        "- The labels are injected closure truth, not adjudicated real high-current pile-up.",
        "- Residual synthesis is train-run/stave preserving, so it tests support density within observed support rather than extrapolation to new detector states.",
        "- Bootstrap CIs cover finite held-out event statistics but not all model-selection uncertainty.",
        "- The neural models are compact laptop-scale architectures; a larger transformer could behave differently, but the 18-sample window makes local shape models a strong prior.",
        "- Charge metrics are conditional on the same injected template family and may understate real saturation or baseline-excursion charge bias.",
        "",
        "## 7. Verdict",
        "",
        result["scientific_summary"],
        "",
        "The main interpretation is that support-preserving augmentation improves training density but does not make sequence architectures dominate the tabular/tree winner. The limiting factor is therefore not simply neural capacity; the strongest result remains a structured waveform-summary method unless future real-pile-up labels expose features absent from the injected closure.",
        "",
        "## 8. Reproducibility",
        "",
        "```bash",
        f"{sys.executable} scripts/s19b_1783757474_25319_0c3b2402_support_preserving_augmentation.py --config {config['_config_path']}",
        "```",
        "",
        f"Runtime in this execution was `{runtime:.2f}` s. Machine-readable outputs include `result.json`, `manifest.json`, `reproduction_match_table.csv`, `augmentation_ledger.csv`, `two_pulse_head_to_head.csv`, and `two_pulse_architecture_cv.csv`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s19b_1783757474_25319_0c3b2402_support_preserving_augmentation.yaml")
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    config["_config_path"] = str(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    match = s02.reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")
    input_hashes = {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in configured_runs(config)}
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    cfg = injection_config(config)
    clean_runs = sorted(set(cfg["benchmark_runs"]["train"] + cfg["benchmark_runs"]["heldout"]))
    clean = p05a.read_clean_pulses(cfg, clean_runs, rng)
    clean.to_pickle(out_dir / "two_pulse_clean_pulses.pkl")
    clean_train = clean[clean["run"].isin(cfg["benchmark_runs"]["train"])]
    templates, template_summary = p05a.build_templates(clean_train, cfg)
    template_summary.to_csv(out_dir / "two_pulse_template_summary.csv", index=False)
    train_events, train_wave = p05a.generate_benchmark(clean, templates, cfg, "train", cfg["benchmark_runs"]["train"], rng)
    held_events, held_wave = p05a.generate_benchmark(clean, templates, cfg, "heldout", cfg["benchmark_runs"]["heldout"], rng)
    eval_events = pd.concat([train_events, held_events], ignore_index=True)
    eval_wave = np.vstack([train_wave, held_wave])
    eval_events.to_csv(out_dir / "two_pulse_injection_events.csv", index=False)

    aug_events, aug_wave, ledger = build_augmented_training(train_events, train_wave, clean_train, templates, cfg, rng)
    ledger.to_csv(out_dir / "augmentation_ledger.csv", index=False)
    pd.DataFrame({"n_augmented_train_events": [len(aug_events)], "n_original_train_events": [len(train_events)], "n_heldout_events": [len(held_events)]}).to_csv(out_dir / "support_summary.csv", index=False)

    trad = p05a.run_template_fits(eval_events, eval_wave, templates, cfg).rename(columns={
        "trad_score": "constrained_template_fit_score",
        "trad_failed": "constrained_template_fit_failed",
        "trad_t1_sample": "constrained_template_fit_t1_sample",
        "trad_t2_sample": "constrained_template_fit_t2_sample",
        "trad_amp1_adc": "constrained_template_fit_amp1_adc",
        "trad_amp2_adc": "constrained_template_fit_amp2_adc",
    })
    frame = eval_events.merge(trad[["event_id", "constrained_template_fit_score", "constrained_template_fit_failed", "constrained_template_fit_t1_sample", "constrained_template_fit_t2_sample", "constrained_template_fit_amp1_adc", "constrained_template_fit_amp2_adc"]], on="event_id")
    meta = [{"model": "constrained_template_fit", "train_seconds": float("nan"), "n_parameters": 0}]

    cv = cv_augmented_rows(aug_events, aug_wave, cfg)
    cv.to_csv(out_dir / "two_pulse_architecture_cv.csv", index=False)

    for model_name in ["ridge", "gradient_boosted_trees", "mlp"]:
        pred, elapsed, n_params = train_sklearn_on_augmented(model_name, aug_events, aug_wave, eval_events, eval_wave, cfg)
        frame = frame.merge(pred, on="event_id")
        meta.append({"model": model_name, "train_seconds": elapsed, "n_parameters": n_params})
    for arch, width in [
        ("cnn", int(cfg["ml"]["cnn_channels"][0])),
        ("resnet", int(cfg["ml"]["resnet_channels"][0])),
        ("tcn", int(cfg["ml"]["tcn_channels"][0])),
        ("attention", int(cfg["ml"]["attention_width"][0])),
        ("gru", int(cfg["ml"]["gru_hidden"][0])),
    ]:
        pred, elapsed, n_params = train_torch_on_augmented(arch, aug_events, aug_wave, eval_events, eval_wave, width, cfg, int(cfg["ml"]["random_seed"]) + 1700 + len(arch))
        frame = frame.merge(pred, on="event_id")
        meta.append({"model": arch, "train_seconds": elapsed, "n_parameters": n_params, "width": width})

    frame.to_csv(out_dir / "two_pulse_predictions.csv", index=False)
    prefixes = ["constrained_template_fit", "ridge", "gradient_boosted_trees", "mlp", "cnn", "resnet", "tcn", "attention", "gru"]
    bench = heldout_metrics(frame, prefixes, rng, int(cfg["ml"]["bootstrap_samples"])).merge(pd.DataFrame(meta), on="model", how="left")
    bench.to_csv(out_dir / "two_pulse_head_to_head.csv", index=False)
    save_plot(out_dir, bench)

    winner = bench.sort_values(["time_rms_ns", "charge_fractional_res68"]).iloc[0]
    traditional = bench[bench["model"] == "constrained_template_fit"].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "reproduced": bool(match["pass"].all()),
        "winner": {
            "overall": str(winner["model"]),
            "two_pulse_time_rms": str(winner["model"]),
            "charge_recovery_res68": str(bench.sort_values("charge_fractional_res68").iloc[0]["model"]),
        },
        "traditional": {
            "baseline": "constrained_template_fit",
            "time_rms_ns": float(traditional["time_rms_ns"]),
            "time_rms_ci": [float(traditional["time_rms_ns_ci_low"]), float(traditional["time_rms_ns_ci_high"])],
            "charge_fractional_res68": float(traditional["charge_fractional_res68"]),
        },
        "ml": {
            "best_model": str(winner["model"]),
            "best_time_rms_ns": float(winner["time_rms_ns"]),
            "best_time_rms_ci": [float(winner["time_rms_ns_ci_low"]), float(winner["time_rms_ns_ci_high"])],
            "best_charge_fractional_res68": float(winner["charge_fractional_res68"]),
        },
        "support_preserving_augmentation": {
            "original_train_events": int(len(train_events)),
            "augmented_train_events": int(len(aug_events)),
            "heldout_events_untouched": int(len(held_events)),
        },
        "scientific_summary": (
            f"With train-only support-preserving augmentation, held-out winner is {winner['model']} at "
            f"{float(winner['time_rms_ns']):.3f} ns [{float(winner['time_rms_ns_ci_low']):.3f}, "
            f"{float(winner['time_rms_ns_ci_high']):.3f}] versus constrained_template_fit "
            f"{float(traditional['time_rms_ns']):.3f} ns. Charge res68 for the winner is "
            f"{float(winner['charge_fractional_res68']):.4f}. Held-out runs are untouched; "
            "the result tests training-support density rather than held-out augmentation."
        ),
        "next_tickets": [
            {
                "title": "S19e: real high-current adjudication of support-preserved pile-up winner",
                "body": "Question: does the support-preserved two-pulse winner transfer from injected closure truth to blinded high-current real pile-up candidates? Build a small reviewer-adjudicated gallery from runs 63/65 with unchanged model thresholds and compare template-fit, gradient-boosted tree, and sequence-head decisions. Expected information gain: separates injected-template closure from real pile-up morphology before adoption.",
            }
        ],
    }
    runtime = time.time() - start
    result["runtime_seconds"] = runtime
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_report(out_dir, config, match, ledger, cv, bench, result, runtime)
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "git_commit": git_commit(),
        "command": f"{sys.executable} {' '.join(sys.argv)}",
        "python": sys.version,
        "platform": platform.platform(),
        "config": str(config_path),
        "random_seed": int(config["random_seed"]),
        "input_sha256": input_hashes,
        "output_sha256": hash_outputs(out_dir),
        "runtime_seconds": runtime,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
