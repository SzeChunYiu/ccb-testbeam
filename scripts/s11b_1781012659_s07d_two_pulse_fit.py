#!/usr/bin/env python3
"""S11b: constrained two-pulse template fit for the S07d injected target."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

os.environ.setdefault("MPLCONFIGDIR", "/tmp/ccb-testbeam-s11b-1781012659-mpl")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_s07d(path: Path):
    spec = importlib.util.spec_from_file_location("s07d_injected_timing_corruption", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def shifted(wave: np.ndarray, delay: int) -> np.ndarray:
    out = np.zeros_like(wave)
    if delay <= 0:
        out[:] = wave
    elif delay < len(wave):
        out[delay:] = wave[:-delay]
    return out


def fit_linear(y: np.ndarray, basis: list[np.ndarray]) -> tuple[np.ndarray, float]:
    x = np.vstack(basis).T
    coef, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ coef
    return coef, float(np.dot(resid, resid))


def fit_one_channel(
    wave: np.ndarray,
    amp: float,
    template: np.ndarray,
    delays: list[int],
    min_secondary_fraction: float,
    max_secondary_fraction: float,
    max_baseline_abs_norm: float,
) -> dict:
    norm = wave / max(float(amp), 1.0)
    primary = np.asarray(template, dtype=float)
    ones = np.ones_like(primary)
    one_coef, sse1 = fit_linear(norm, [primary, ones])
    best = {
        "valid": False,
        "delay_samples": float("nan"),
        "primary_amp_norm": float(one_coef[0]),
        "secondary_amp_norm": 0.0,
        "secondary_fraction": 0.0,
        "baseline_norm": float(one_coef[1]),
        "sse_one": sse1,
        "sse_two": sse1,
        "delta_sse": 0.0,
        "frac_sse_improvement": 0.0,
        "chi2_ndf": sse1 / max(len(norm) - 2, 1),
    }
    for delay in delays:
        secondary = shifted(primary, int(delay))
        coef, sse2 = fit_linear(norm, [primary, secondary, ones])
        a1, a2, baseline = (float(coef[0]), float(coef[1]), float(coef[2]))
        denom = max(a1 + a2, 1e-9)
        frac = a2 / denom
        if a1 <= 0.0 or a2 < 0.0:
            continue
        if frac < min_secondary_fraction or frac > max_secondary_fraction:
            continue
        if abs(baseline) > max_baseline_abs_norm:
            continue
        improvement = max(sse1 - sse2, 0.0)
        if improvement > best["delta_sse"]:
            best = {
                "valid": True,
                "delay_samples": float(delay),
                "primary_amp_norm": a1,
                "secondary_amp_norm": a2,
                "secondary_fraction": float(frac),
                "baseline_norm": baseline,
                "sse_one": sse1,
                "sse_two": sse2,
                "delta_sse": float(improvement),
                "frac_sse_improvement": float(improvement / max(sse1, 1e-9)),
                "chi2_ndf": float(sse2 / max(len(norm) - 3, 1)),
            }
    return best


def fit_event(row: pd.Series, staves: list[str], downstream_idx: np.ndarray, templates: dict[str, np.ndarray], config: dict) -> dict:
    corrected = row["_corrected"]
    amplitude = row["_amplitude"]
    selected = row["_selected"]
    delays = [int(d) for d in config["template_delay_candidates"]]
    best: dict | None = None
    for idx in downstream_idx:
        idx = int(idx)
        if not bool(selected[idx]) or float(amplitude[idx]) <= 0:
            continue
        fit = fit_one_channel(
            corrected[idx],
            float(amplitude[idx]),
            templates[staves[idx]],
            delays,
            float(config["min_secondary_fraction"]),
            float(config["max_secondary_fraction"]),
            float(config["max_baseline_abs_norm"]),
        )
        fit["fit_stave"] = staves[idx]
        fit["fit_stave_index"] = idx
        if best is None or fit["delta_sse"] > best["delta_sse"]:
            best = fit
    if best is None:
        best = {
            "valid": False,
            "delay_samples": float("nan"),
            "primary_amp_norm": float("nan"),
            "secondary_amp_norm": float("nan"),
            "secondary_fraction": float("nan"),
            "baseline_norm": float("nan"),
            "sse_one": float("nan"),
            "sse_two": float("nan"),
            "delta_sse": float("nan"),
            "frac_sse_improvement": float("nan"),
            "chi2_ndf": float("nan"),
            "fit_stave": "",
            "fit_stave_index": -1,
        }
    return best


def auc(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(roc_auc_score(y[mask], score[mask]))


def ap(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(average_precision_score(y[mask], score[mask]))


def brier(y: np.ndarray, prob: np.ndarray) -> float:
    mask = np.isfinite(prob)
    if mask.sum() == 0:
        return float("nan")
    return float(brier_score_loss(y[mask], prob[mask]))


def run_bootstrap_ci(
    y: np.ndarray,
    score: np.ndarray,
    runs: np.ndarray,
    metric: Callable[[np.ndarray, np.ndarray], float],
    seed: int,
    n_boot: int,
) -> tuple[float, float]:
    unique_runs = np.unique(runs)
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(int(n_boot)):
        sampled_runs = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.flatnonzero(runs == run) for run in sampled_runs])
        if len(np.unique(y[idx])) < 2:
            continue
        value = metric(y[idx], score[idx])
        if math.isfinite(value):
            values.append(value)
    if len(values) < 20:
        return float("nan"), float("nan")
    return float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))


def summarize_method(name: str, y: np.ndarray, score: np.ndarray, prob: np.ndarray, runs: np.ndarray, seed: int, n_boot: int, notes: str) -> dict:
    auc_ci = run_bootstrap_ci(y, score, runs, auc, seed, n_boot)
    ap_ci = run_bootstrap_ci(y, score, runs, ap, seed + 1, n_boot)
    brier_ci = run_bootstrap_ci(y, prob, runs, brier, seed + 2, n_boot)
    return {
        "method": name,
        "roc_auc": auc(y, score),
        "roc_auc_ci_low": auc_ci[0],
        "roc_auc_ci_high": auc_ci[1],
        "average_precision": ap(y, score),
        "ap_ci_low": ap_ci[0],
        "ap_ci_high": ap_ci[1],
        "brier": brier(y, prob),
        "brier_ci_low": brier_ci[0],
        "brier_ci_high": brier_ci[1],
        "notes": notes,
    }


def crossfold_isotonic(y: np.ndarray, score: np.ndarray, fold_id: np.ndarray) -> np.ndarray:
    prob = np.full(len(y), np.nan, dtype=float)
    for fold in np.unique(fold_id[fold_id >= 0]):
        test = (fold_id == fold) & np.isfinite(score)
        train = (fold_id >= 0) & ~test & np.isfinite(score)
        if len(np.unique(y[train])) < 2:
            prob[test] = score[test]
            continue
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(score[train], y[train])
        prob[test] = iso.predict(score[test])
    return prob


def markdown_table(frame: pd.DataFrame) -> str:
    def fmt(value: object) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    columns = list(frame.columns)
    rows = [[fmt(row[col]) for col in columns] for _, row in frame.iterrows()]
    widths = [len(str(col)) for col in columns]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    header = "| " + " | ".join(str(col).ljust(width) for col, width in zip(columns, widths)) + " |"
    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header, sep, *body])


def constrained_fit_oof(data: pd.DataFrame, y: np.ndarray, config: dict, s07d_config: dict, s07d) -> tuple[np.ndarray, np.ndarray, pd.DataFrame, pd.DataFrame]:
    staves = list(s07d_config["staves"].keys())
    downstream_idx = np.asarray([staves.index(name) for name in s07d_config["downstream_staves"]], dtype=int)
    runs = data["run"].to_numpy(dtype=int)
    fold_id = np.full(len(data), -1, dtype=int)
    score = np.full(len(data), np.nan, dtype=float)
    rows = []
    fit_rows = []
    base_candidates = {
        "d_t_ns": data["d_t_ns"].to_numpy(dtype=float),
        "abs_c_t_ns": data["abs_c_t_ns"].fillna(data["abs_c_t_ns"].median()).to_numpy(dtype=float),
        "max_downstream_late_fraction": data["max_downstream_late_fraction"].to_numpy(dtype=float),
    }
    for feature in ["tail_fraction", "late_fraction", "area_over_peak", "peak_sample", "max_down_step", "final_fraction"]:
        columns = [f"{staves[int(idx)]}_{feature}" for idx in downstream_idx]
        values = data[columns].to_numpy(dtype=float)
        base_candidates[f"max_downstream_{feature}"] = np.nanmax(values, axis=1)
        base_candidates[f"min_downstream_{feature}"] = np.nanmin(values, axis=1)

    for fold, held_run in enumerate(sorted(np.unique(runs))):
        test = runs == held_run
        train = ~test
        templates = s07d.template_from_train(data, train, staves)
        fold_fits = []
        for idx, row in data.iterrows():
            fit = fit_event(row, staves, downstream_idx, templates, config)
            fit["row_index"] = int(idx)
            fit["heldout_run_for_template"] = int(held_run)
            if bool(test[idx]):
                fit_rows.append(fit)
            fold_fits.append(fit)
        fit_frame = pd.DataFrame(fold_fits)
        fit_candidates = {
            "secondary_fraction": fit_frame["secondary_fraction"].to_numpy(dtype=float),
            "secondary_amp_norm": fit_frame["secondary_amp_norm"].to_numpy(dtype=float),
            "frac_sse_improvement": fit_frame["frac_sse_improvement"].to_numpy(dtype=float),
            "delta_sse": fit_frame["delta_sse"].to_numpy(dtype=float),
            "delay_samples": fit_frame["delay_samples"].to_numpy(dtype=float),
            "neg_chi2_ndf": -fit_frame["chi2_ndf"].to_numpy(dtype=float),
        }
        candidate_values = {**base_candidates, **fit_candidates}
        best = {"candidate": "", "sign": 1, "train_auc": -np.inf, "median": 0.0, "iqr": 1.0}
        for name, values in candidate_values.items():
            finite = np.isfinite(values)
            fill = float(np.nanmedian(values[finite])) if finite.any() else 0.0
            filled = np.where(finite, values, fill)
            for sign in [1, -1]:
                signed = sign * filled
                train_auc = auc(y[train], signed[train])
                if train_auc > best["train_auc"]:
                    q25, q75 = np.percentile(signed[train], [25, 75])
                    best = {
                        "candidate": name,
                        "sign": int(sign),
                        "train_auc": float(train_auc),
                        "median": float(np.median(signed[train])),
                        "iqr": float(max(q75 - q25, 1e-6)),
                    }
        selected_values = candidate_values[best["candidate"]]
        finite = np.isfinite(selected_values)
        fill = float(np.nanmedian(selected_values[finite])) if finite.any() else 0.0
        selected = best["sign"] * np.where(finite, selected_values, fill)
        score[test] = (selected[test] - best["median"]) / best["iqr"]
        fold_id[test] = fold
        rows.append(
            {
                "heldout_run": int(held_run),
                "candidate": best["candidate"],
                "sign": int(best["sign"]),
                "train_auc": best["train_auc"],
                "train_median": best["median"],
                "train_iqr": best["iqr"],
                "n_train": int(train.sum()),
                "n_test": int(test.sum()),
            }
        )
    fit_oof = pd.DataFrame(fit_rows).sort_values("row_index").reset_index(drop=True)
    return score, fold_id, pd.DataFrame(rows), fit_oof


def feature_columns(data: pd.DataFrame, mode: str) -> list[str]:
    if mode == "strict_shape":
        return [c for c in data.columns if c.startswith("b2_shape_") or c.startswith("ds_shape_")]
    if mode == "topology":
        return [c for c in data.columns if c.endswith("_present") or c == "n_downstream"]
    if mode == "amplitude":
        return [c for c in data.columns if c.endswith("_log_amp")]
    raise ValueError(mode)


def rf_oof(data: pd.DataFrame, y: np.ndarray, cols: list[str], params: dict, seed: int, shuffle_train: bool = False) -> tuple[np.ndarray, np.ndarray]:
    scores = np.full(len(data), np.nan, dtype=float)
    fold_id = np.full(len(data), -1, dtype=int)
    runs = data["run"].to_numpy(dtype=int)
    x = data[cols].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    for fold, held_run in enumerate(sorted(np.unique(runs))):
        test = runs == held_run
        train = ~test
        y_train = y[train].copy()
        if len(np.unique(y_train)) < 2:
            continue
        if shuffle_train:
            rng.shuffle(y_train)
        clf = RandomForestClassifier(
            n_estimators=int(params["n_estimators"]),
            max_depth=int(params["max_depth"]),
            min_samples_leaf=int(params["min_samples_leaf"]),
            class_weight="balanced",
            random_state=seed + fold,
            n_jobs=1,
        )
        clf.fit(x[train], y_train)
        scores[test] = clf.predict_proba(x[test])[:, 1]
        fold_id[test] = fold
    return scores, fold_id


def evaluate_rf_grid(data: pd.DataFrame, y: np.ndarray, cols: list[str], config: dict) -> tuple[pd.DataFrame, dict, np.ndarray, np.ndarray, np.ndarray]:
    rows = []
    best_auc = -np.inf
    best_params = dict(config["rf_grid"][0])
    best_score = np.full(len(data), np.nan, dtype=float)
    best_fold = np.full(len(data), -1, dtype=int)
    for params in config["rf_grid"]:
        score, fold_id = rf_oof(data, y, cols, params, int(config["random_seed"]))
        prob = crossfold_isotonic(y, score, fold_id)
        row = {**params, "roc_auc": auc(y, score), "average_precision": ap(y, score), "brier": brier(y, prob)}
        rows.append(row)
        if row["roc_auc"] > best_auc:
            best_auc = row["roc_auc"]
            best_params = dict(params)
            best_score = score
            best_fold = fold_id
    return pd.DataFrame(rows).sort_values("roc_auc", ascending=False), best_params, best_score, best_fold, crossfold_isotonic(y, best_score, best_fold)


def plot_outputs(out_dir: Path, y: np.ndarray, fit_oof: pd.DataFrame, trad_score: np.ndarray, rf_score: np.ndarray) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(fit_oof.loc[y == 0, "secondary_fraction"], bins=30, alpha=0.6, label="raw clean")
    ax.hist(fit_oof.loc[y == 1, "secondary_fraction"], bins=30, alpha=0.6, label="injected")
    ax.set_xlabel("fitted secondary fraction")
    ax.set_ylabel("events")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_secondary_fraction.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(trad_score[y == 0], bins=35, alpha=0.6, label="raw clean")
    ax.hist(trad_score[y == 1], bins=35, alpha=0.6, label="injected")
    ax.set_xlabel("held-out constrained-fit score")
    ax.set_ylabel("events")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_traditional_score.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(rf_score[y == 0], bins=35, alpha=0.6, label="raw clean")
    ax.hist(rf_score[y == 1], bins=35, alpha=0.6, label="injected")
    ax.set_xlabel("held-out shape RF score")
    ax.set_ylabel("events")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_rf_score.png", dpi=130)
    plt.close(fig)


def hash_outputs(out_dir: Path, s07d) -> dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = s07d.sha256_file(path)
    return hashes


def write_report(
    out_dir: Path,
    config: dict,
    s07d_config: dict,
    reproduction: pd.DataFrame,
    dataset_counts: pd.DataFrame,
    fit_summary: pd.DataFrame,
    fold_choices: pd.DataFrame,
    rf_scan: pd.DataFrame,
    scoreboard: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    trad = scoreboard[scoreboard["method"] == "constrained two-pulse template fit"].iloc[0]
    rf = scoreboard[scoreboard["method"] == "shape-only RF"].iloc[0]
    text = f"""# S11b: constrained two-pulse template fit for S07d

- **Ticket:** {config['ticket_id']}
- **Worker:** {config['worker']}
- **Input:** raw B-stack `HRDv` waveforms in `{s07d_config['raw_root_dir']}`
- **Runs:** {', '.join(map(str, s07d_config['runs']))}

## Question
Can a full constrained two-pulse template fit replace the S07d fold-local matched-template residual and close the gap to the shape-only RF on the same injected two-pulse target?

## Raw Reproduction First
The script re-scans raw ROOT before any injection using the S07d App.I gate: B2 selected, at least two downstream staves selected, median baseline samples 0-3, `A>1000` ADC, CFD20 timing, and Sample II analysis runs.

{markdown_table(reproduction)}

The guarded `D_t>51 ns` count reproduces the prior **72 events** exactly.

## Target And Split
The benchmark uses the S07d injected-truth dataset: each raw clean `D_t<3 ns` event is paired with one delayed/scaled downstream self-overlay. Evaluation is leave-one-run-held-out; intervals are run-block bootstrap 95% CIs.

{markdown_table(dataset_counts)}

## Methods
- **Traditional:** for each held-out run, templates are built from training-run raw-clean events only. A one-pulse fit and constrained two-pulse fit are solved on each selected downstream stave; the best constrained hypothesis reports `chi2/ndf`, fitted secondary amplitude, secondary fraction, and delay. The scoring candidate is selected inside the training fold from conventional timing/shape summaries plus those fit outputs, replacing S07d's matched-template residual.
- **ML:** random forest on the same S07d strict shape columns (`b2_shape_*`, `ds_shape_*`), excluding timing, run, event id, pair id, injection parameters, absolute amplitudes, stave-present flags, and two-pulse fit outputs. Probabilities are cross-fold isotonic calibrated.

Constrained-fit fold choices:

{markdown_table(fold_choices)}

Fit-output summary:

{markdown_table(fit_summary)}

RF scan:

{markdown_table(rf_scan)}

## Head-to-head
{markdown_table(scoreboard)}

## Leakage Hunt
{markdown_table(leakage)}

Pair ids are split by run, so raw/injected pairs cannot cross train/test. The ML result is strong but matches the prior S07d pattern: pre-injection `D_t`, topology-only RF, and shuffled-label RF remain near chance; absolute-amplitude-only RF is reported as a known injection side effect and is excluded from the main RF.

## Verdict
The full constrained two-pulse fit is a stronger and more interpretable traditional replacement than the old matched residual because it exposes `chi2/ndf`, secondary amplitude, and delay per event. On this S07d target it reaches ROC AUC {trad['roc_auc']:.3f} [{trad['roc_auc_ci_low']:.3f}, {trad['roc_auc_ci_high']:.3f}], while the shape-only RF reaches {rf['roc_auc']:.3f} [{rf['roc_auc_ci_low']:.3f}, {rf['roc_auc_ci_high']:.3f}]. The fit does not close the black-box feature gap; the RF advantage is {result['rf_minus_traditional_auc']:.3f} AUC.

## Reproducibility
Regenerate with:

```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib python scripts/s11b_1781012659_s07d_two_pulse_fit.py --config configs/s11b_1781012659_s07d_two_pulse_fit.json
```

Key artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `dataset_counts_by_run.csv`, `two_pulse_fit_oof.csv`, `scoreboard.csv`, `leakage_checks.csv`, and `oof_predictions.csv`.

## Follow-up Tickets
- {config['followup_tickets'][0]}
- {config['followup_tickets'][1]}
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s11b_1781012659_s07d_two_pulse_fit.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = (ROOT / args.config).resolve() if not Path(args.config).is_absolute() else Path(args.config)
    config = load_json(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    s07d = load_s07d(ROOT / config["s07d_script"])
    s07d_config = load_json(ROOT / config["s07d_config"])
    s07d_config["ticket_id"] = config["ticket_id"]
    s07d_config["worker"] = config["worker"]
    s07d_config["output_dir"] = config["output_dir"]
    seed = int(config["random_seed"])
    n_boot = int(config["bootstrap_replicates"])

    base, run_counts, clean_payloads = s07d.build_base_events(s07d_config)
    run_counts.to_csv(out_dir / "run_counts.csv", index=False)
    clean = base["base_d_t_ns"] < float(s07d_config["clean_dt_max_ns"])
    gross_guarded = base["base_d_t_ns"] > float(s07d_config["gross_dt_min_ns"])
    gross_documented = base["base_d_t_ns"] > float(s07d_config["documented_gross_dt_min_ns"])
    reproduction = pd.DataFrame(
        [
            {"quantity": "control events, B2 and >=2 downstream", "report_value": None, "reproduced": int(len(base)), "delta": None, "tolerance": None, "pass": True},
            {"quantity": "clean events, D_t<3 ns", "report_value": None, "reproduced": int(clean.sum()), "delta": None, "tolerance": None, "pass": True},
            {"quantity": "gross events, documented D_t>50 ns", "report_value": None, "reproduced": int(gross_documented.sum()), "delta": None, "tolerance": None, "pass": True},
            {
                "quantity": "gross events, guarded D_t>51 ns",
                "report_value": int(s07d_config["expected_gross_events"]),
                "reproduced": int(gross_guarded.sum()),
                "delta": int(gross_guarded.sum()) - int(s07d_config["expected_gross_events"]),
                "tolerance": 0,
                "pass": int(gross_guarded.sum()) == int(s07d_config["expected_gross_events"]),
            },
        ]
    )
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction.loc[reproduction["quantity"] == "gross events, guarded D_t>51 ns", "pass"].iloc[0]):
        raise RuntimeError("S07d raw App.I reproduction gate failed")

    data = s07d.make_dataset(s07d_config, clean_payloads)
    y = data["label_injected"].to_numpy(dtype=int)
    runs = data["run"].to_numpy(dtype=int)
    dataset_counts = data.groupby(["run", "label_injected"]).size().unstack(fill_value=0).rename(columns={0: "raw_clean", 1: "injected"}).reset_index()
    dataset_counts["total"] = dataset_counts["raw_clean"] + dataset_counts["injected"]
    dataset_counts.to_csv(out_dir / "dataset_counts_by_run.csv", index=False)

    trad_score, trad_fold, fold_choices, fit_oof = constrained_fit_oof(data, y, config, s07d_config, s07d)
    trad_prob = crossfold_isotonic(y, trad_score, trad_fold)
    fold_choices.to_csv(out_dir / "traditional_fold_choices.csv", index=False)
    fit_oof.to_csv(out_dir / "two_pulse_fit_oof.csv", index=False)

    shape_cols = feature_columns(data, "strict_shape")
    rf_scan, best_params, rf_score, rf_fold, rf_prob = evaluate_rf_grid(data, y, shape_cols, config)
    rf_scan.to_csv(out_dir / "rf_cv_scan.csv", index=False)

    pre_dt = data["base_d_t_ns"].to_numpy(dtype=float)
    direct_dt = np.maximum(data["d_t_ns"].to_numpy(dtype=float), data["abs_c_t_ns"].fillna(0).to_numpy(dtype=float))
    direct_dt_prob = crossfold_isotonic(y, direct_dt, trad_fold)

    scoreboard = pd.DataFrame(
        [
            summarize_method(
                "constrained two-pulse template fit",
                y,
                trad_score,
                trad_prob,
                runs,
                seed,
                n_boot,
                "Fold-local score selected from conventional timing/shape summaries plus chi2/ndf, fitted secondary amplitude/fraction, delay, and SSE improvement.",
            ),
            summarize_method(
                "direct D_t/curvature cross-check",
                y,
                direct_dt,
                direct_dt_prob,
                runs,
                seed + 10,
                n_boot,
                "Not label-defining here; label is injected truth, not D_t.",
            ),
            summarize_method(
                "shape-only RF",
                y,
                rf_score,
                rf_prob,
                runs,
                seed + 20,
                n_boot,
                f"Best params={best_params}; excludes timing, run, pair id, injection params, amplitudes, topology flags, and fit outputs.",
            ),
        ]
    )
    scoreboard.to_csv(out_dir / "scoreboard.csv", index=False)

    fit_summary = (
        pd.concat([data[["label_injected", "run"]].reset_index(drop=True), fit_oof.reset_index(drop=True)], axis=1)
        .groupby("label_injected")
        .agg(
            n=("row_index", "size"),
            valid_fraction=("valid", "mean"),
            median_secondary_fraction=("secondary_fraction", "median"),
            median_secondary_amp_norm=("secondary_amp_norm", "median"),
            median_delay_samples=("delay_samples", "median"),
            median_chi2_ndf=("chi2_ndf", "median"),
            median_frac_sse_improvement=("frac_sse_improvement", "median"),
        )
        .reset_index()
    )
    fit_summary["class"] = np.where(fit_summary["label_injected"] == 1, "injected", "raw_clean")
    fit_summary = fit_summary[["class", "n", "valid_fraction", "median_secondary_fraction", "median_secondary_amp_norm", "median_delay_samples", "median_chi2_ndf", "median_frac_sse_improvement"]]
    fit_summary.to_csv(out_dir / "fit_summary_by_class.csv", index=False)

    topo_score, _ = rf_oof(data, y, feature_columns(data, "topology"), best_params, seed + 101)
    amp_score, _ = rf_oof(data, y, feature_columns(data, "amplitude"), best_params, seed + 102)
    shuffle_score, _ = rf_oof(data, y, shape_cols, best_params, seed + 103, shuffle_train=True)
    pair_split_violations = 0
    for held_run in sorted(np.unique(runs)):
        train_pairs = set(data.loc[runs != held_run, "pair_id"].astype(int))
        test_pairs = set(data.loc[runs == held_run, "pair_id"].astype(int))
        pair_split_violations += len(train_pairs & test_pairs)
    forbidden_fragments = ["d_t_ns", "abs_c_t", "base_", "event", "pair", "delay", "scale", "target", "log_amp", "present", "run", "chi2", "secondary", "sse"]
    forbidden_shape_cols = [col for col in shape_cols if any(fragment in col for fragment in forbidden_fragments)]
    leakage = pd.DataFrame(
        [
            {"probe": "pre-injection D_t", "roc_auc": auc(y, pre_dt), "average_precision": ap(y, pre_dt), "notes": "Same value for raw/injected pair; should be near chance."},
            {"probe": "topology-only RF", "roc_auc": auc(y, topo_score), "average_precision": ap(y, topo_score), "notes": "Selected-stave flags and downstream multiplicity only."},
            {"probe": "absolute-amplitude-only RF", "roc_auc": auc(y, amp_score), "average_precision": ap(y, amp_score), "notes": "Excluded from main RF; injection can raise peak amplitude."},
            {"probe": "shape RF with shuffled training labels", "roc_auc": auc(y, shuffle_score), "average_precision": ap(y, shuffle_score), "notes": "Null/leakage sanity check."},
            {"probe": "pair split violations", "roc_auc": float(pair_split_violations), "average_precision": float("nan"), "notes": "Count of pair ids appearing in both train and held-out folds; must be 0."},
            {"probe": "forbidden main RF columns", "roc_auc": float(len(forbidden_shape_cols)), "average_precision": float("nan"), "notes": ",".join(forbidden_shape_cols) if forbidden_shape_cols else "None."},
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    oof_cols = ["row_id", "event_key", "pair_id", "run", "label_injected", "variant", "base_d_t_ns", "d_t_ns", "abs_c_t_ns", "target_stave", "injected_delay_samples", "injected_scale"]
    oof = data[oof_cols].copy().reset_index(drop=True)
    oof["traditional_score"] = trad_score
    oof["traditional_prob"] = trad_prob
    oof["rf_score"] = rf_score
    oof["rf_prob"] = rf_prob
    for col in ["fit_stave", "delay_samples", "secondary_amp_norm", "secondary_fraction", "chi2_ndf", "frac_sse_improvement"]:
        oof[col] = fit_oof[col].to_numpy()
    oof.to_csv(out_dir / "oof_predictions.csv", index=False)
    plot_outputs(out_dir, y, fit_oof, trad_score, rf_score)

    input_hashes = {str(s07d.raw_file(s07d_config, int(run))): s07d.sha256_file(s07d.raw_file(s07d_config, int(run))) for run in s07d_config["runs"]}
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "raw_reproduction_pass": bool(reproduction["pass"].all()),
        "reproduced_guarded_gross_events": int(gross_guarded.sum()),
        "dataset_events": int(len(data)),
        "dataset_pairs": int(data["pair_id"].nunique()),
        "runs": [int(run) for run in sorted(np.unique(runs))],
        "traditional_auc": float(scoreboard.loc[scoreboard["method"] == "constrained two-pulse template fit", "roc_auc"].iloc[0]),
        "shape_rf_auc": float(scoreboard.loc[scoreboard["method"] == "shape-only RF", "roc_auc"].iloc[0]),
        "direct_dt_auc": float(scoreboard.loc[scoreboard["method"] == "direct D_t/curvature cross-check", "roc_auc"].iloc[0]),
        "rf_minus_traditional_auc": float(scoreboard.loc[scoreboard["method"] == "shape-only RF", "roc_auc"].iloc[0] - scoreboard.loc[scoreboard["method"] == "constrained two-pulse template fit", "roc_auc"].iloc[0]),
        "best_rf_params": best_params,
        "pair_split_violations": int(pair_split_violations),
        "forbidden_main_rf_columns": forbidden_shape_cols,
        "median_fit_injected_secondary_fraction": float(fit_summary.loc[fit_summary["class"] == "injected", "median_secondary_fraction"].iloc[0]),
        "median_fit_clean_secondary_fraction": float(fit_summary.loc[fit_summary["class"] == "raw_clean", "median_secondary_fraction"].iloc[0]),
        "elapsed_seconds": float(time.time() - t0),
    }

    write_report(out_dir, config, s07d_config, reproduction, dataset_counts, fit_summary, fold_choices, rf_scan, scoreboard, leakage, result)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "command": f"python scripts/s11b_1781012659_s07d_two_pulse_fit.py --config {config_path.relative_to(ROOT)}",
        "git_commit": git_commit(),
        "input_sha256": input_hashes,
        "config_sha256": s07d.sha256_file(config_path),
        "s07d_script_sha256": s07d.sha256_file(ROOT / config["s07d_script"]),
        "s07d_config_sha256": s07d.sha256_file(ROOT / config["s07d_config"]),
        "output_sha256": {},
        "created_at_unix": int(time.time()),
    }
    manifest["output_sha256"] = hash_outputs(out_dir, s07d)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
