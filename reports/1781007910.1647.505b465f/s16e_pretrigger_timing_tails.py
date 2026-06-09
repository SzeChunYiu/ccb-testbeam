#!/usr/bin/env python3
"""S16e pre-trigger activity proxy in S02 timing residual tails."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import s02_timing_pickoff as s02


def load_s02b_module():
    path = REPO / "reports" / "1781000705.514762.105c186b__s02b_template_timewalk_closure" / "s02b_template_timewalk_closure.py"
    spec = importlib.util.spec_from_file_location("s02b_template_timewalk_closure", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load S02b helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S02B = load_s02b_module()


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        cfg = json.load(handle)
    cfg["spacing_cm_values"] = [float(cfg["spacing_cm"])]
    return cfg


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def input_hashes(config: dict) -> Dict[str, str]:
    return {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in s02.configured_runs(config)}


def line3_proxy(pre: np.ndarray) -> Dict[str, np.ndarray]:
    xs = np.arange(pre.shape[1], dtype=float)
    loo_residuals = []
    for holdout in range(pre.shape[1]):
        other = [idx for idx in range(pre.shape[1]) if idx != holdout]
        x = xs[other]
        y = pre[:, other].astype(float)
        xbar = float(np.mean(x))
        denom = float(np.sum((x - xbar) ** 2))
        ybar = y.mean(axis=1)
        slope = ((y - ybar[:, None]) * (x[None, :] - xbar)).sum(axis=1) / denom
        pred = ybar + slope * (float(holdout) - xbar)
        loo_residuals.append(pred - pre[:, holdout])
    resid = np.vstack(loo_residuals).T
    full_slope = ((pre - pre.mean(axis=1)[:, None]) * (xs[None, :] - xs.mean())).sum(axis=1) / np.sum((xs - xs.mean()) ** 2)
    return {
        "pre_range_adc": pre.max(axis=1) - pre.min(axis=1),
        "pre_std_adc": pre.std(axis=1),
        "pre_line_absmax_adc": np.max(np.abs(resid), axis=1),
        "pre_line_rms_adc": np.sqrt(np.mean(resid**2, axis=1)),
        "pre_line_slope_adc_per_sample": full_slope,
        "pre_min_adc": pre.min(axis=1),
    }


def load_downstream_pulses_with_proxy(config: dict) -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    pre_idx = [int(i) for i in config["pretrigger_samples"]]
    all_staves = {name: int(ch) for name, ch in config["staves"].items()}
    downstream = list(config["timing"]["downstream_staves"])
    channels = np.asarray([all_staves[name] for name in downstream], dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rows = []
    event_uid_base = 0
    for run in sorted(set(config["timing"]["train_runs"] + config["timing"]["heldout_runs"])):
        path = raw_file(config, run)
        for batch in s02.iter_raw(path, ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            waveforms = events[:, channels, :]
            corrected, amplitude, peak, area = s02.pulse_quantities(waveforms, baseline_idx)
            selected = amplitude > cut
            event_mask = selected.all(axis=1)
            for e in np.where(event_mask)[0]:
                uid = f"{run}:{int(eventno[e])}:{int(evt[e])}:{event_uid_base + int(e)}"
                proxy = line3_proxy(corrected[e, :, :][:, pre_idx])
                for sidx, stave in enumerate(downstream):
                    row = {
                        "event_id": uid,
                        "run": int(run),
                        "eventno": int(eventno[e]),
                        "evt": int(evt[e]),
                        "stave": stave,
                        "waveform": corrected[e, sidx].astype(float),
                        "amplitude_adc": float(amplitude[e, sidx]),
                        "peak_sample": int(peak[e, sidx]),
                        "area_adc_samples": float(area[e, sidx]),
                    }
                    for key, values in proxy.items():
                        row[key] = float(values[sidx])
                    rows.append(row)
            event_uid_base += len(eventno)
    return pd.DataFrame(rows)


def prepare_s02b_baseline(pulses: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    train = pulses[pulses["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train, list(config["timing"]["downstream_staves"]))
    work = pulses.copy()
    methods = s02.add_traditional_times(work, config, templates)
    scan = s02.evaluate_methods(work, methods, config)
    binned_templates, alignment = S02B.build_binned_templates(train, config)
    _, sse, bins = S02B.binned_template_phase_time(work, binned_templates, config)
    work["s02b_template_sse"] = sse
    work["s02b_template_bin"] = bins
    work, tw_cv, tw_cal, tw_coef = S02B.add_conventional_timewalk(
        work,
        config,
        "template_phase",
        "s16e_base_timewalk",
    )
    return work, {
        "traditional_scan_metrics": scan,
        "template_fit_by_run_stave": alignment,
        "base_timewalk_cv": tw_cv,
        "base_timewalk_calibration": tw_cal,
        "base_timewalk_coefficients": tw_coef,
    }


def proxy_feature_frame(pulses: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "pre_range_adc",
        "pre_std_adc",
        "pre_line_absmax_adc",
        "pre_line_rms_adc",
        "pre_line_slope_adc_per_sample",
        "pre_min_adc",
    ]
    out = pulses[cols].copy()
    out["log1p_pre_range"] = np.log1p(np.maximum(out["pre_range_adc"].to_numpy(dtype=float), 0.0))
    out["log1p_line_absmax"] = np.log1p(np.maximum(out["pre_line_absmax_adc"].to_numpy(dtype=float), 0.0))
    out["proxy_x_log_amp"] = out["log1p_line_absmax"].to_numpy(dtype=float) * np.log1p(pulses["amplitude_adc"].to_numpy(dtype=float))
    return out


def fit_proxy_correction(
    pulses: pd.DataFrame,
    config: dict,
    base_method: str,
    output_method: str,
    ml_like: bool,
    shuffled: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, List[str]]:
    spacing = float(config["spacing_cm"])
    targets = s02.event_residual_targets(pulses, base_method, spacing, config)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, config["timing"]["train_runs"]) & np.isfinite(targets)
    if ml_like:
        X = np.hstack(
            [
                s02.feature_matrix(pulses, list(config["timing"]["downstream_staves"])),
                proxy_feature_frame(pulses).to_numpy(dtype=float),
            ]
        )
        feature_names = [f"s02_waveform_feature_{i}" for i in range(s02.feature_matrix(pulses, list(config["timing"]["downstream_staves"])).shape[1])] + list(proxy_feature_frame(pulses).columns)
        alphas = [float(a) for a in config["ml"]["ridge_alphas"]]
    else:
        base_x, base_names = S02B.interaction_features(pulses, config)
        proxy = proxy_feature_frame(pulses)
        X = np.hstack([base_x, proxy.to_numpy(dtype=float)])
        feature_names = base_names + list(proxy.columns)
        alphas = [float(a) for a in config["timewalk"]["proxy_ridge_alphas"]]
    finite = np.all(np.isfinite(X), axis=1)
    train_mask = train_mask & finite
    y_train = targets[train_mask].copy()
    if shuffled:
        rng = np.random.default_rng(int(config["ml"]["permutation_seed"]) + (101 if ml_like else 11))
        y_train = y_train.copy()
        rng.shuffle(y_train)
    groups = runs[train_mask]
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    cv_rows = []
    for alpha in alphas:
        fold_values = []
        if n_splits >= 2:
            gkf = GroupKFold(n_splits=n_splits)
            idx_train = np.flatnonzero(train_mask)
            for fold, (tr, va) in enumerate(gkf.split(X[train_mask], y_train, groups=groups)):
                model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
                model.fit(X[train_mask][tr], y_train[tr])
                pred = np.full(len(pulses), np.nan)
                pred[idx_train[va]] = model.predict(X[train_mask][va])
                tmp = pulses.copy()
                tmp[f"t_{output_method}_ns"] = tmp[f"t_{base_method}_ns"] - pred
                vals = s02.pairwise_residuals(tmp.iloc[idx_train[va]], output_method, spacing, config, list(np.unique(runs[idx_train[va]])))
                score = s02.sigma68(vals)
                fold_values.append(score)
                cv_rows.append({"method": output_method, "alpha": alpha, "fold": int(fold), "sigma68_ns": score, "n_pair_residuals": int(len(vals)), "shuffled_target": bool(shuffled)})
        cv_rows.append({"method": output_method, "alpha": alpha, "fold": -1, "sigma68_ns": float(np.nanmean(fold_values)), "n_pair_residuals": 0, "shuffled_target": bool(shuffled)})
    cv = pd.DataFrame(cv_rows)
    best_alpha = float(cv[cv["fold"] == -1].sort_values("sigma68_ns").iloc[0]["alpha"])
    model = make_pipeline(StandardScaler(), Ridge(alpha=best_alpha))
    model.fit(X[train_mask], y_train)
    pred_all = model.predict(X)
    out = pulses.copy()
    out[f"{output_method}_target_ns"] = targets
    out[f"{output_method}_pred_ns"] = pred_all
    out[f"t_{output_method}_ns"] = out[f"t_{base_method}_ns"] - pred_all
    coef = pd.DataFrame({"feature": feature_names})
    coef["coefficient"] = model.named_steps["ridge"].coef_
    coef["method"] = output_method
    coef["base_method"] = base_method
    coef["best_alpha"] = best_alpha
    coef["train_pulses"] = int(train_mask.sum())
    return out, cv, coef, feature_names


def event_metrics_with_ci(pulses: pd.DataFrame, method: str, config: dict, rng: np.random.Generator) -> dict:
    pairs = S02B.event_pair_table(pulses, method, config, config["timing"]["heldout_runs"])
    grouped = [g["residual_ns"].to_numpy() for _, g in pairs.groupby("event_id")]
    sigma_stats = []
    tail_stats = []
    threshold = float(config["tail_threshold_ns"])
    for _ in range(int(config["ml"]["bootstrap_samples"])):
        chosen = rng.integers(0, len(grouped), size=len(grouped))
        vals = np.concatenate([grouped[i] for i in chosen])
        med = np.median(vals)
        sigma_stats.append(s02.sigma68(vals))
        tail_stats.append(float(np.mean(np.abs(vals - med) > threshold)))
    vals = pairs["residual_ns"].to_numpy(dtype=float)
    med = float(np.median(vals))
    return {
        "value": s02.sigma68(vals),
        "ci_low": float(np.percentile(sigma_stats, 2.5)),
        "ci_high": float(np.percentile(sigma_stats, 97.5)),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(vals - med) > threshold)),
        "tail_ci_low": float(np.percentile(tail_stats, 2.5)),
        "tail_ci_high": float(np.percentile(tail_stats, 97.5)),
        "n_heldout_events": int(len(grouped)),
        **s02.metric_summary(vals),
    }


def benchmark(work: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    methods = [
        ("template_phase", "S02_global_template_phase"),
        ("s16e_base_timewalk", "S02b_global_template_timewalk"),
        ("s16e_proxy_timewalk", "S16e_traditional_proxy_timewalk"),
        ("s16e_ml_proxy", "S16e_ml_proxy_ridge"),
    ]
    rows = []
    for method, label in methods:
        rows.append(
            {
                "method": label,
                "internal_method": method,
                "metric": "heldout_run65_B4_B6_B8_pairwise_sigma68_ns",
                **event_metrics_with_ci(work, method, config, rng),
            }
        )
    return pd.DataFrame(rows)


def tail_by_proxy(work: pd.DataFrame, config: dict, methods: List[Tuple[str, str]]) -> pd.DataFrame:
    event_proxy = (
        work.groupby("event_id")
        .agg(
            run=("run", "first"),
            event_pre_line_absmax_adc=("pre_line_absmax_adc", "max"),
            event_pre_range_adc=("pre_range_adc", "max"),
            event_pre_line_rms_adc=("pre_line_rms_adc", "mean"),
        )
        .reset_index()
    )
    held_proxy = event_proxy[event_proxy["run"].isin(config["timing"]["heldout_runs"])].copy()
    held_proxy["proxy_bin"] = pd.qcut(held_proxy["event_pre_line_absmax_adc"], q=3, labels=["low", "mid", "high"], duplicates="drop")
    rows = []
    threshold = float(config["tail_threshold_ns"])
    for method, label in methods:
        pairs = S02B.event_pair_table(work, method, config, config["timing"]["heldout_runs"]).merge(held_proxy, on="event_id", how="left")
        med = float(np.median(pairs["residual_ns"]))
        pairs["is_tail"] = np.abs(pairs["residual_ns"] - med) > threshold
        for bin_name, sub in pairs.groupby("proxy_bin", dropna=False):
            rows.append(
                {
                    "method": label,
                    "proxy_bin": str(bin_name),
                    "n_pair_residuals": int(len(sub)),
                    "n_events": int(sub["event_id"].nunique()),
                    "event_pre_line_absmax_adc_mean": float(sub["event_pre_line_absmax_adc"].mean()),
                    "sigma68_ns": s02.sigma68(sub["residual_ns"].to_numpy()),
                    "tail_frac_abs_gt5ns": float(sub["is_tail"].mean()),
                }
            )
    return pd.DataFrame(rows)


def normalized_hash_overlap(work: pd.DataFrame, config: dict) -> int:
    train_hash, held_hash = set(), set()
    for mask, dest in [
        (work["run"].isin(config["timing"]["train_runs"]), train_hash),
        (work["run"].isin(config["timing"]["heldout_runs"]), held_hash),
    ]:
        for row in work[mask].itertuples():
            arr = np.round(row.waveform / max(float(row.amplitude_adc), 1.0), 5)
            key = f"{row.stave}|{np.array2string(arr, precision=5, separator=',')}"
            dest.add(hashlib.sha256(key.encode("utf-8")).hexdigest())
    return int(len(train_hash & held_hash))


def leakage_checks(
    work: pd.DataFrame,
    config: dict,
    bench: pd.DataFrame,
    shuffled_trad: pd.DataFrame,
    shuffled_ml: pd.DataFrame,
    feature_names: Dict[str, List[str]],
) -> pd.DataFrame:
    train_runs = set(config["timing"]["train_runs"])
    heldout_runs = set(config["timing"]["heldout_runs"])
    train_events = set(work[work["run"].isin(train_runs)]["event_id"])
    held_events = set(work[work["run"].isin(heldout_runs)]["event_id"])
    actual_trad = float(bench[bench["method"] == "S16e_traditional_proxy_timewalk"]["value"].iloc[0])
    actual_ml = float(bench[bench["method"] == "S16e_ml_proxy_ridge"]["value"].iloc[0])
    shuffled_trad_val = s02.sigma68(s02.pairwise_residuals(shuffled_trad, "s16e_proxy_timewalk_shuffled", float(config["spacing_cm"]), config, config["timing"]["heldout_runs"]))
    shuffled_ml_val = s02.sigma68(s02.pairwise_residuals(shuffled_ml, "s16e_ml_proxy_shuffled", float(config["spacing_cm"]), config, config["timing"]["heldout_runs"]))
    forbidden_tokens = ["run", "event", "target", "residual", "pair"]
    feature_text = " ".join(feature_names["traditional"] + feature_names["ml"]).lower()
    return pd.DataFrame(
        [
            {"check": "train_heldout_run_overlap", "value": int(len(train_runs & heldout_runs)), "pass": len(train_runs & heldout_runs) == 0},
            {"check": "train_heldout_event_id_overlap", "value": int(len(train_events & held_events)), "pass": len(train_events & held_events) == 0},
            {"check": "normalized_waveform_exact_hash_overlap", "value": normalized_hash_overlap(work, config), "pass": normalized_hash_overlap(work, config) == 0},
            {"check": "features_exclude_run_event_target_pair_residual", "value": int(any(tok in feature_text for tok in forbidden_tokens)), "pass": not any(tok in feature_text for tok in forbidden_tokens)},
            {"check": "traditional_shuffled_target_not_better", "value": shuffled_trad_val, "actual": actual_trad, "pass": shuffled_trad_val >= actual_trad},
            {"check": "ml_shuffled_target_not_better", "value": shuffled_ml_val, "actual": actual_ml, "pass": shuffled_ml_val >= actual_ml},
        ]
    )


def write_plots(out_dir: Path, bench: pd.DataFrame, tails: pd.DataFrame, work: pd.DataFrame, config: dict) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ordered = bench.sort_values("value")
    ax.barh(ordered["method"], ordered["value"], xerr=[ordered["value"] - ordered["ci_low"], ordered["ci_high"] - ordered["value"]])
    ax.set_xlabel("held-out sigma68 (ns)")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_sigma68_ci.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.0, 4.4))
    pivot = tails.pivot(index="proxy_bin", columns="method", values="tail_frac_abs_gt5ns")
    pivot.plot(kind="bar", ax=ax)
    ax.set_ylabel("tail fraction |residual - median| > 5 ns")
    ax.set_xlabel("held-out event pre-trigger proxy bin")
    ax.tick_params(axis="x", labelrotation=0)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_tail_fraction_by_proxy.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    for method, label in [("s16e_base_timewalk", "S02b base"), ("s16e_proxy_timewalk", "traditional proxy"), ("s16e_ml_proxy", "ML proxy")]:
        vals = s02.pairwise_residuals(work, method, float(config["spacing_cm"]), config, config["timing"]["heldout_runs"])
        ax.hist(vals, bins=60, histtype="step", density=True, label=f"{label} {s02.sigma68(vals):.2f} ns")
    ax.set_xlabel("held-out pair residual (ns)")
    ax.set_ylabel("density")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_heldout_residuals.png", dpi=140)
    plt.close(fig)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(out_dir: Path, config: dict, match: pd.DataFrame, reference: pd.DataFrame, bench: pd.DataFrame, tails: pd.DataFrame, leakage: pd.DataFrame, result: dict) -> None:
    trad = bench[bench["method"] == "S16e_traditional_proxy_timewalk"].iloc[0]
    base = bench[bench["method"] == "S02b_global_template_timewalk"].iloc[0]
    ml = bench[bench["method"] == "S16e_ml_proxy_ridge"].iloc[0]
    report = f"""# S16e: pre-trigger activity proxy in timing residual tails

Ticket `{config['ticket_id']}`. Worker `{config['worker']}`.

## Reproduction first

Raw ROOT was read from `h101/HRDv` before timing fits. The S00 selected B-stave gate uses median samples 0-3 and `A > 1000 ADC`.

{match.to_markdown(index=False)}

S02/S02b timing references were then rebuilt on the same raw run split:

{reference.to_markdown(index=False)}

## Method

The S16b proxy is computed per pulse from baseline-subtracted pre-trigger samples 0-3. The primary proxy is the maximum absolute leave-one-sample `line3_predict` closure residual; supporting proxy terms are the pre-trigger range, RMS line residual, early-sample standard deviation, slope, and minimum. Timing uses B4/B6/B8 events, train runs `{config['timing']['train_runs']}`, and held-out run `{config['timing']['heldout_runs']}`.

The traditional extension is a train-only linear Ridge residual correction on top of the S02b global-template/timewalk method using only hand-built timewalk and pre-trigger proxy features. The ML extension is a Ridge residual corrector on S02 normalized waveform features plus the same proxy terms. Both are evaluated only on held-out run 65 with event bootstrap CIs.

## Held-out benchmark

{bench[['method', 'value', 'ci_low', 'ci_high', 'tail_frac_abs_gt5ns', 'tail_ci_low', 'tail_ci_high', 'n_heldout_events', 'n_pair_residuals']].to_markdown(index=False)}

Traditional proxy delta versus S02b timewalk: `{result['traditional']['delta_vs_s02b_ns']:+.3f} ns`; tail-fraction delta `{result['traditional']['tail_delta_vs_s02b']:+.4f}`. ML proxy delta versus S02b timewalk: `{result['ml']['delta_vs_s02b_ns']:+.3f} ns`; tail-fraction delta `{result['ml']['tail_delta_vs_s02b']:+.4f}`.

## Tail study

Held-out event residual tails by pre-trigger proxy bin:

{tails.to_markdown(index=False)}

The held-out tail count is small, so the proxy-bin table should be read as a diagnostic stratification rather than a discovery test. The high-proxy bin has a distinct residual-width pattern, but the `>5 ns` tail fraction is not consistently higher. Adding the proxy as a correction feature does not decisively erase timing tails: the traditional proxy sigma68 is `{trad['value']:.3f} [{trad['ci_low']:.3f}, {trad['ci_high']:.3f}] ns` versus the S02b baseline `{base['value']:.3f} [{base['ci_low']:.3f}, {base['ci_high']:.3f}] ns`, with overlapping CIs.

## Leakage checks

{leakage.to_markdown(index=False)}

The split is by run and the proxy features exclude run id, event id, pair residuals, target residuals, and other-stave timing values. Shuffled-target controls were rerun for both proxy corrections.

## Conclusion

The S16b pre-trigger proxy is useful as a diagnostic tail tag but is not adopted as a timing correction. On held-out run 65, the proxy traditional fit changes sigma68 by `{result['traditional']['delta_vs_s02b_ns']:+.3f} ns` relative to S02b and the ML proxy changes it by `{result['ml']['delta_vs_s02b_ns']:+.3f} ns`; neither provides a clean leakage-aware improvement.

## Follow-up tickets

- S16f: build a per-event pre-trigger contamination veto using B2/B4/B6/B8 and test efficiency versus S02 timing tails with leave-one-run-out Sample-II splits.
- S02d: leave-one-run-out S02b timing plus S16e proxy terms over all Sample-II analysis runs, not only held-out run 65.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(SCRIPT_DIR / "s16e_config.json"))
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    match = s02.reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT selected-pulse reproduction gate failed")

    pulses = load_downstream_pulses_with_proxy(config)
    pulses.to_csv(out_dir / "timing_pulse_proxy_table.csv.gz", index=False, compression="gzip")
    proxy_summary = pulses.groupby(["run", "stave"]).agg(
        n=("event_id", "count"),
        pre_line_absmax_median_adc=("pre_line_absmax_adc", "median"),
        pre_line_absmax_q90_adc=("pre_line_absmax_adc", lambda x: float(np.quantile(x, 0.9))),
        pre_range_median_adc=("pre_range_adc", "median"),
    ).reset_index()
    proxy_summary.to_csv(out_dir / "pretrigger_proxy_by_run_stave.csv", index=False)

    work, tables = prepare_s02b_baseline(pulses, config)
    for name, table in tables.items():
        table.to_csv(out_dir / f"{name}.csv", index=False)

    ref_rows = []
    for method, label, expected in [
        ("template_phase", "S02 global-template traditional template_phase", float(config["s02_reference"]["traditional_template_phase_sigma68_ns"])),
        ("s16e_base_timewalk", "S02b global-template timewalk", float(config["s02b_reference"]["global_template_timewalk_sigma68_ns"])),
    ]:
        vals = s02.pairwise_residuals(work, method, float(config["spacing_cm"]), config, config["timing"]["heldout_runs"])
        value = s02.sigma68(vals)
        ref_rows.append({"quantity": label, "reproduced_sigma68_ns": value, "reference_sigma68_ns": expected, "delta_ns": value - expected, "pass": abs(value - expected) < 1e-6})
    reference = pd.DataFrame(ref_rows)
    reference.to_csv(out_dir / "reproduction_reference_numbers.csv", index=False)
    if not bool(reference["pass"].all()):
        raise RuntimeError("S02/S02b timing reference reproduction failed")

    trad_work, trad_cv, trad_coef, trad_features = fit_proxy_correction(work, config, "s16e_base_timewalk", "s16e_proxy_timewalk", ml_like=False)
    trad_cv.to_csv(out_dir / "traditional_proxy_cv.csv", index=False)
    trad_coef.to_csv(out_dir / "traditional_proxy_coefficients.csv", index=False)
    ml_work, ml_cv, ml_coef, ml_features = fit_proxy_correction(trad_work, config, "template_phase", "s16e_ml_proxy", ml_like=True)
    ml_cv.to_csv(out_dir / "ml_proxy_cv.csv", index=False)
    ml_coef.to_csv(out_dir / "ml_proxy_coefficients.csv", index=False)

    shuffled_trad, shuffled_trad_cv, _, _ = fit_proxy_correction(work, config, "s16e_base_timewalk", "s16e_proxy_timewalk_shuffled", ml_like=False, shuffled=True)
    shuffled_trad_cv.to_csv(out_dir / "traditional_shuffled_target_cv.csv", index=False)
    shuffled_ml, shuffled_ml_cv, _, _ = fit_proxy_correction(work, config, "template_phase", "s16e_ml_proxy_shuffled", ml_like=True, shuffled=True)
    shuffled_ml_cv.to_csv(out_dir / "ml_shuffled_target_cv.csv", index=False)

    combined = ml_work.copy()
    bench = benchmark(combined, config, rng)
    bench.to_csv(out_dir / "heldout_benchmark.csv", index=False)
    tails = tail_by_proxy(combined, config, [("s16e_base_timewalk", "S02b_global_template_timewalk"), ("s16e_proxy_timewalk", "S16e_traditional_proxy_timewalk"), ("s16e_ml_proxy", "S16e_ml_proxy_ridge")])
    tails.to_csv(out_dir / "proxy_tail_table.csv", index=False)
    leakage = leakage_checks(combined, config, bench, shuffled_trad, shuffled_ml, {"traditional": trad_features, "ml": ml_features})
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    write_plots(out_dir, bench, tails, combined, config)

    hashes = input_hashes(config)
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)
    b = bench.set_index("method")
    base = b.loc["S02b_global_template_timewalk"]
    trad = b.loc["S16e_traditional_proxy_timewalk"]
    ml = b.loc["S16e_ml_proxy_ridge"]
    result = {
        "study": "S16e",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_first": bool(match["pass"].all()),
        "reference_numbers_reproduced": bool(reference["pass"].all()),
        "split_by_run": {"train_runs": config["timing"]["train_runs"], "heldout_runs": config["timing"]["heldout_runs"]},
        "traditional": {
            "method": "linear_ridge_proxy_residual_correction_on_s02b_timewalk",
            "metric": "heldout_run65_B4_B6_B8_pairwise_sigma68_ns",
            "value": float(trad["value"]),
            "ci": [float(trad["ci_low"]), float(trad["ci_high"])],
            "tail_frac_abs_gt5ns": float(trad["tail_frac_abs_gt5ns"]),
            "tail_ci": [float(trad["tail_ci_low"]), float(trad["tail_ci_high"])],
            "delta_vs_s02b_ns": float(trad["value"] - base["value"]),
            "tail_delta_vs_s02b": float(trad["tail_frac_abs_gt5ns"] - base["tail_frac_abs_gt5ns"]),
        },
        "ml": {
            "method": "ridge_residual_corrector_on_waveform_plus_pretrigger_proxy",
            "metric": "heldout_run65_B4_B6_B8_pairwise_sigma68_ns",
            "value": float(ml["value"]),
            "ci": [float(ml["ci_low"]), float(ml["ci_high"])],
            "tail_frac_abs_gt5ns": float(ml["tail_frac_abs_gt5ns"]),
            "tail_ci": [float(ml["tail_ci_low"]), float(ml["tail_ci_high"])],
            "delta_vs_s02b_ns": float(ml["value"] - base["value"]),
            "tail_delta_vs_s02b": float(ml["tail_frac_abs_gt5ns"] - base["tail_frac_abs_gt5ns"]),
        },
        "s02b_baseline": {"value": float(base["value"]), "ci": [float(base["ci_low"]), float(base["ci_high"])], "tail_frac_abs_gt5ns": float(base["tail_frac_abs_gt5ns"])},
        "leakage_checks_pass": bool(leakage["pass"].all()),
        "input_sha256": hashlib.sha256("".join(hashes.values()).encode("ascii")).hexdigest(),
        "next_tickets": [
            "S16f: per-event pre-trigger contamination veto versus S02 timing tails with leave-one-run-out splits",
            "S02d: leave-one-run-out S02b timing plus S16e proxy terms over all Sample-II analysis runs",
        ],
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, match, reference, bench, tails, leakage, result)
    manifest = {
        "ticket": config["ticket_id"],
        "study": "S16e",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["ml"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "traditional_delta_vs_s02b_ns": result["traditional"]["delta_vs_s02b_ns"], "ml_delta_vs_s02b_ns": result["ml"]["delta_vs_s02b_ns"], "leakage_checks_pass": result["leakage_checks_pass"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
