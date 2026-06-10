#!/usr/bin/env python3
"""S02d follow-up: propagate P07e retained-window saturation uncertainty.

The raw-root reproduction gate is intentionally first: Sample-II B2 selected
pulses and the natural high-amplitude proxy are rebuilt before any timing-tail
fit, correction, or prior P07e reference is consumed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import p07e_leading_edge_sample_ablation as p07e


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def raw_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def run_block_ci(values_by_run: pd.Series, rng: np.random.Generator, reps: int) -> List[float]:
    vals = values_by_run.to_numpy(dtype=float)
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return [float("nan"), float("nan")]
    draws = [float(np.mean(rng.choice(vals, size=len(vals), replace=True))) for _ in range(int(reps))]
    return [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))]


def summarize_by_run(rows: pd.DataFrame, group_cols: List[str], metrics: List[str], rng: np.random.Generator, reps: int) -> pd.DataFrame:
    out = []
    for keys, group in rows.groupby(group_cols, sort=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = {k: v for k, v in zip(group_cols, keys)}
        row["n_runs"] = int(group["run"].nunique())
        for metric in metrics:
            by_run = group.groupby("run")[metric].mean()
            if metric == "n_events":
                row["n_events_total"] = int(round(float(by_run.sum())))
                row["n_events_mean_per_run"] = float(by_run.mean())
                row["n_events_mean_per_run_ci95"] = run_block_ci(by_run, rng, reps)
                continue
            row[metric] = float(by_run.mean())
            row[f"{metric}_ci95"] = run_block_ci(by_run, rng, reps)
        out.append(row)
    return pd.DataFrame(out)


def reproduction_gate(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    meta, waves = p07e.load_sample_ii()
    b2 = meta["stave"].to_numpy() == "B2"
    high = b2 & (meta["amplitude_adc"].to_numpy(dtype=float) >= float(config["saturation_proxy_adc"]))
    rows = pd.DataFrame(
        [
            {
                "quantity": "sample_ii_analysis B2 selected pulses",
                "expected": int(config["expected_sample_ii_b2"]),
                "reproduced": int(b2.sum()),
                "delta": int(b2.sum()) - int(config["expected_sample_ii_b2"]),
                "pass": int(b2.sum()) == int(config["expected_sample_ii_b2"]),
            },
            {
                "quantity": "B2 pulses >= 7000 ADC",
                "expected": int(config["expected_b2_ge7000"]),
                "reproduced": int(high.sum()),
                "delta": int(high.sum()) - int(config["expected_b2_ge7000"]),
                "pass": int(high.sum()) == int(config["expected_b2_ge7000"]),
            },
        ]
    )
    if not bool(rows["pass"].all()):
        raise RuntimeError("raw-root reproduction gate failed")
    return rows, meta, waves


def fit_w2_8_gbr(x: np.ndarray, y: np.ndarray, observed: np.ndarray, window: List[int], seed: int) -> GradientBoostingRegressor:
    model = GradientBoostingRegressor(
        n_estimators=120,
        max_depth=3,
        learning_rate=0.055,
        subsample=0.75,
        random_state=seed,
    )
    model.fit(p07e.masked_features(x, observed, window), np.log(y / observed))
    return model


def real_saturated_event_ids(meta: pd.DataFrame, config: dict) -> pd.Index:
    wide = meta.pivot_table(index="event_uid", columns="stave", values="amplitude_adc", aggfunc="first")
    has_b2_sat = wide.get("B2", pd.Series(index=wide.index, dtype=float)) >= float(config["saturation_proxy_adc"])
    downstream = [s for s in ["B4", "B6", "B8"] if s in wide]
    ds_count = (wide[downstream] > float(config["amplitude_cut_adc"])).sum(axis=1)
    return wide.index[has_b2_sat & (ds_count >= int(config["natural_selection"]["min_downstream_selected"]))]


def event_metrics(rows: pd.DataFrame, waves: np.ndarray, corrected_b2_amp: np.ndarray, template: np.ndarray, config: dict) -> pd.DataFrame:
    spacing = float(config["spacing_cm"])
    positions = {"B2": 0.0, "B4": spacing, "B6": 2.0 * spacing, "B8": 3.0 * spacing}
    out = rows.copy()
    amp = out["amplitude_adc"].to_numpy(dtype=float).copy()
    b2 = out["stave"].to_numpy() == "B2"
    amp[b2] = corrected_b2_amp
    out["amp_used_adc"] = amp
    out["time_ns"] = float(config["sample_period_ns"]) * p07e.cfd_time_samples(waves, amp)
    out["tcorr_ns"] = out["time_ns"] - out["stave"].map(positions).astype(float) * float(config["tof_per_cm_ns"])
    q = np.full(len(out), np.nan, dtype=float)
    q[b2] = np.sqrt(np.mean((waves[b2] / np.maximum(corrected_b2_amp[:, None], 1.0) - template[None, :]) ** 2, axis=1))
    out["q_template_rmse"] = q

    wide = out.pivot(index="event_uid", columns="stave", values="tcorr_ns")
    ds_cols = [c for c in ["B4", "B6", "B8"] if c in wide]
    ds_median = wide[ds_cols].median(axis=1)
    residual = wide["B2"] - ds_median
    b2_rows = out[out["stave"] == "B2"][["event_uid", "run", "amplitude_adc", "amp_used_adc", "q_template_rmse"]]
    return pd.DataFrame({"event_uid": residual.index, "timing_residual_ns": residual.to_numpy()}).merge(
        b2_rows, on="event_uid", how="left"
    )


def timing_summary(values: pd.DataFrame, config: dict) -> dict:
    resid = values["timing_residual_ns"].to_numpy(dtype=float)
    q = values["q_template_rmse"].to_numpy(dtype=float)
    ratio = values["amp_used_adc"].to_numpy(dtype=float) / np.maximum(values["amplitude_adc"].to_numpy(dtype=float), 1.0)
    finite = np.isfinite(resid) & np.isfinite(q) & np.isfinite(ratio)
    resid, q, ratio = resid[finite], q[finite], ratio[finite]
    if len(resid) == 0:
        return {
            "n_events": 0,
            "timing_tail_frac_abs_gt5ns": float("nan"),
            "timing_sigma68_ns": float("nan"),
            "timing_q95_abs_ns": float("nan"),
            "timing_median_ns": float("nan"),
            "q_template_median": float("nan"),
            "q_template_p95": float("nan"),
            "amp_ratio_median": float("nan"),
        }
    centered = resid - np.median(resid)
    q16, q84 = np.percentile(centered, [16, 84])
    return {
        "n_events": int(len(resid)),
        "timing_tail_frac_abs_gt5ns": float(np.mean(np.abs(centered) > float(config["timing_tail_abs_ns"]))),
        "timing_sigma68_ns": float((q84 - q16) / 2.0),
        "timing_q95_abs_ns": float(np.percentile(np.abs(centered), 95)),
        "timing_median_ns": float(np.median(resid)),
        "q_template_median": float(np.median(q)),
        "q_template_p95": float(np.percentile(q, 95)),
        "amp_ratio_median": float(np.median(ratio)),
    }


def artificial_reproduction_and_models(
    config: dict,
    meta: pd.DataFrame,
    waves: np.ndarray,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, Dict[int, dict]]:
    window = list(config["retained_window"]["samples"])
    clean = p07e.clean_b2_mask(meta)
    clean_idx_all = np.flatnonzero(clean)
    rows = []
    fold = {}
    for run in config["runs"]:
        train_idx = clean_idx_all[meta.loc[clean_idx_all, "run"].to_numpy() != int(run)]
        held_idx = clean_idx_all[meta.loc[clean_idx_all, "run"].to_numpy() == int(run)]
        if len(train_idx) > int(config["max_train_clean_per_split"]):
            train_idx = rng.choice(train_idx, size=int(config["max_train_clean_per_split"]), replace=False)
        if len(held_idx) > int(config["max_held_artificial_per_run"]):
            held_idx = rng.choice(held_idx, size=int(config["max_held_artificial_per_run"]), replace=False)
        train_wave = waves[train_idx]
        train_amp = meta.loc[train_idx, "amplitude_adc"].to_numpy(dtype=float)
        held_wave = waves[held_idx]
        held_amp = meta.loc[held_idx, "amplitude_adc"].to_numpy(dtype=float)
        template = p07e.build_template(train_wave, train_amp)
        x_train, y_train, obs_train = p07e.fixed_ceiling_samples(
            train_wave,
            train_amp,
            list(config["train_ceilings_adc"]),
            rng,
            max_rows=int(config["max_train_clean_per_split"]),
        )
        x_held, y_held, obs_held = p07e.fixed_ceiling_samples(
            held_wave,
            held_amp,
            [float(config["artificial_fixed_ceiling_adc"])],
            rng,
            max_rows=int(config["max_held_artificial_per_run"]),
        )
        trad_pred = p07e.template_recover(x_held, obs_held, template, window)
        model = fit_w2_8_gbr(x_train, y_train, obs_train, window, int(config["random_seed"]) + int(run) + len(window))
        ml_pred = obs_held * np.exp(model.predict(p07e.masked_features(x_held, obs_held, window)))
        observed_pred = obs_held.copy()
        for method, pred in [
            ("observed_ceiling", observed_pred),
            ("traditional_template", trad_pred),
            ("ml_gbr_masked", ml_pred),
        ]:
            rows.append({"run": int(run), "method": method, **p07e.recovery_metrics(y_held, pred)})
        fold[int(run)] = {
            "template": template,
            "model": model,
            "train_event_ids": set(meta.loc[train_idx, "event_uid"].astype(str)),
            "held_event_ids": set(meta.loc[held_idx, "event_uid"].astype(str)),
            "x_train": x_train,
            "y_train": y_train,
            "obs_train": obs_train,
            "x_held": x_held,
            "y_held": y_held,
            "obs_held": obs_held,
        }
    return pd.DataFrame(rows), fold


def timing_branches(
    config: dict,
    meta: pd.DataFrame,
    waves: np.ndarray,
    artificial_summary: pd.DataFrame,
    fold: Dict[int, dict],
) -> pd.DataFrame:
    window = list(config["retained_window"]["samples"])
    bias_ci = artificial_summary.loc[artificial_summary["method"] == "ml_gbr_masked", "bias_median_frac_ci95"].iloc[0]
    res68_ci = artificial_summary.loc[artificial_summary["method"] == "ml_gbr_masked", "res68_abs_frac_ci95"].iloc[0]
    nuisance_low = float(bias_ci[0]) - float(res68_ci[1])
    nuisance_high = float(bias_ci[1]) + float(res68_ci[1])
    event_ids = real_saturated_event_ids(meta, config)
    real_rows_all = meta[meta["event_uid"].isin(event_ids)].copy()
    real_waves_all = waves[real_rows_all.index.to_numpy()]
    rows = []
    for run in config["runs"]:
        run_rows = real_rows_all[real_rows_all["run"] == int(run)].copy()
        if run_rows.empty:
            continue
        run_waves = real_waves_all[real_rows_all["run"].to_numpy() == int(run)]
        b2 = run_rows["stave"].to_numpy() == "B2"
        b2_wave = run_waves[b2]
        b2_obs = run_rows.loc[b2, "amplitude_adc"].to_numpy(dtype=float)
        template = fold[int(run)]["template"]
        model = fold[int(run)]["model"]
        trad = np.maximum(b2_obs, p07e.template_recover(b2_wave, b2_obs, template, window))
        ml = np.maximum(b2_obs, b2_obs * np.exp(model.predict(p07e.masked_features(b2_wave, b2_obs, window))))
        ml_low = np.maximum(b2_obs, ml * (1.0 + nuisance_low))
        ml_high = np.maximum(b2_obs, ml * (1.0 + nuisance_high))
        for method, amp, family in [
            ("observed_saturated", b2_obs, "observed"),
            ("traditional_template", trad, "traditional"),
            ("ml_corrected", ml, "ml"),
            ("ml_p07e_nuisance_low", ml_low, "ml_nuisance"),
            ("ml_p07e_nuisance_high", ml_high, "ml_nuisance"),
        ]:
            values = event_metrics(run_rows, run_waves, amp, template, config)
            rows.append({"run": int(run), "method": method, "family": family, **timing_summary(values, config)})
    out = pd.DataFrame(rows)
    observed = out[out["method"] == "observed_saturated"][["run", "timing_tail_frac_abs_gt5ns", "timing_sigma68_ns"]].rename(
        columns={
            "timing_tail_frac_abs_gt5ns": "observed_tail_frac",
            "timing_sigma68_ns": "observed_sigma68_ns",
        }
    )
    out = out.merge(observed, on="run", how="left")
    out["tail_delta_vs_observed"] = out["timing_tail_frac_abs_gt5ns"] - out["observed_tail_frac"]
    out["sigma68_delta_vs_observed_ns"] = out["timing_sigma68_ns"] - out["observed_sigma68_ns"]
    return out


def leakage_checks(config: dict, artificial: pd.DataFrame, fold: Dict[int, dict], rng: np.random.Generator) -> pd.DataFrame:
    window = list(config["retained_window"]["samples"])
    rows = []
    for run, payload in fold.items():
        train_ids = payload["train_event_ids"]
        held_ids = payload["held_event_ids"]
        overlap = len(train_ids.intersection(held_ids))
        rows.append(
            {
                "run": run,
                "check": "train_heldout_event_overlap",
                "value": overlap,
                "pass": overlap == 0,
                "interpretation": "hard run split should imply no event overlap",
            }
        )
        x_train = payload["x_train"]
        y_train = payload["y_train"]
        obs_train = payload["obs_train"]
        x_held = payload["x_held"]
        y_held = payload["y_held"]
        obs_held = payload["obs_held"]
        y_shuffle = rng.permutation(y_train)
        shuffled = fit_w2_8_gbr(x_train, y_shuffle, obs_train, window, int(config["random_seed"]) + 7000 + run)
        pred = obs_held * np.exp(shuffled.predict(p07e.masked_features(x_held, obs_held, window)))
        shuffled_res68 = p07e.recovery_metrics(y_held, pred)["res68_abs_frac"]
        real_res68 = float(
            artificial[(artificial["run"] == run) & (artificial["method"] == "ml_gbr_masked")]["res68_abs_frac"].iloc[0]
        )
        rows.append(
            {
                "run": run,
                "check": "shuffled_target_res68",
                "value": shuffled_res68,
                "pass": shuffled_res68 > real_res68 * 1.5,
                "interpretation": "shuffled target should be much worse than the real ML model",
            }
        )
        rows.append(
            {
                "run": run,
                "check": "ml_too_good_to_be_true",
                "value": real_res68,
                "pass": real_res68 > 0.005,
                "interpretation": "near-zero amplitude recovery would trigger leakage suspicion",
            }
        )
    return pd.DataFrame(rows)


def write_manifest(out_dir: Path, config_path: Path, config: dict, runtime_sec: float) -> None:
    input_rows = []
    input_hashes = {}
    for run in config["runs"]:
        path = raw_path(config, int(run))
        digest = sha256_file(path)
        input_rows.append({"path": str(path), "sha256": digest, "bytes": path.stat().st_size})
        input_hashes[str(path)] = digest
    config_digest = sha256_file(config_path)
    input_rows.append({"path": str(config_path), "sha256": config_digest, "bytes": config_path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)
    outputs = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs[path.name] = sha256_file(path)
    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "command": " ".join([sys.executable] + sys.argv),
        "config": str(config_path),
        "random_seed": int(config["random_seed"]),
        "inputs_sha256": input_hashes,
        "config_sha256": config_digest,
        "outputs_sha256": outputs,
        "runtime_sec": runtime_sec,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def write_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    p07e_repro: pd.DataFrame,
    p07e_summary: pd.DataFrame,
    timing_summary_frame: pd.DataFrame,
    nuisance: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    display_timing = timing_summary_frame[
        timing_summary_frame["method"].isin(["observed_saturated", "traditional_template", "ml_corrected"])
    ][
        [
            "method",
            "n_runs",
            "n_events_total",
            "n_events_mean_per_run",
            "timing_tail_frac_abs_gt5ns",
            "timing_tail_frac_abs_gt5ns_ci95",
            "tail_delta_vs_observed",
            "tail_delta_vs_observed_ci95",
            "timing_sigma68_ns",
            "timing_sigma68_ns_ci95",
            "amp_ratio_median",
        ]
    ]
    lines = [
        "# S02d/P07e: saturation nuisance in timing tails",
        "",
        f"Ticket `{config['ticket_id']}`. Raw B-stack ROOT was read from `{config['raw_root_dir']}`; no Monte Carlo was used.",
        "",
        "## Reproduction Gate",
        "",
        reproduction.to_markdown(index=False),
        "",
        "The raw-root gate ran before the retained-window timing analysis. The P07e retained-window headline was then recomputed on the same raw ROOT for the `w2_8` GBR branch:",
        "",
        p07e_repro.to_markdown(index=False),
        "",
        "## Method",
        "",
        "Each Sample-II analysis run was held out in turn. Train runs built the B2 template and the P07e `w2_8` gradient-boosted retained-window model; the held-out run supplied both the artificial fixed-ceiling check and the natural high-amplitude B2 timing rows.",
        "",
        "- `observed_saturated`: observed B2 amplitude, no correction.",
        "- `traditional_template`: train-run median B2 template scaled on retained non-plateau samples.",
        "- `ml_corrected`: P07e-style GBR on retained-window normalized B2 samples.",
        "- `ml_p07e_nuisance_low/high`: ML amplitude shifted by the reproduced P07e bias/res68 95% envelope before timing recomputation.",
        "",
        "## Timing Tails",
        "",
        display_timing.to_markdown(index=False),
        "",
        "## P07e Nuisance Envelope",
        "",
        nuisance.to_markdown(index=False),
        "",
        "The adoption screen remains failed: the reproduced P07e best branch has an artificial res68 upper CI above 8%, so the ML timing correction is treated as a nuisance envelope rather than an adopted correction.",
        "",
        "## Leakage Checks",
        "",
        leakage.to_markdown(index=False),
        "",
        "## Headline",
        "",
        result["headline_text"],
        "",
        "## Follow-up",
        "",
        result["follow_up_text"],
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s02d_1781019500_1834_77b10e02_p07e_saturation_tails.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    print("raw-root reproduction gate", flush=True)
    reproduction, meta, waves = reproduction_gate(config)

    print("reproducing P07e w2_8 branch and fitting held-out models", flush=True)
    artificial, fold = artificial_reproduction_and_models(config, meta, waves, rng)
    p07e_summary = summarize_by_run(
        artificial,
        ["method"],
        ["res68_abs_frac", "bias_median_frac", "frac_within10"],
        rng,
        int(config["bootstrap_reps"]),
    )
    ml_row = p07e_summary[p07e_summary["method"] == "ml_gbr_masked"].iloc[0]
    p07e_repro = pd.DataFrame(
        [
            {
                "quantity": "P07e w2_8 GBR res68_abs_frac",
                "expected": "0.0812 from P07e headline",
                "reproduced": float(ml_row["res68_abs_frac"]),
                "ci95": ml_row["res68_abs_frac_ci95"],
                "pass": abs(float(ml_row["res68_abs_frac"]) - 0.08120972878215624) < 0.003,
            },
            {
                "quantity": "P07e w2_8 GBR bias_median_frac",
                "expected": "0.0292 from P07e headline",
                "reproduced": float(ml_row["bias_median_frac"]),
                "ci95": ml_row["bias_median_frac_ci95"],
                "pass": abs(float(ml_row["bias_median_frac"]) - 0.029168391594658696) < 0.01,
            },
            {
                "quantity": "P07e adoption screen",
                "expected": "not adoptable",
                "reproduced": "not adoptable",
                "ci95": ml_row["res68_abs_frac_ci95"],
                "pass": float(ml_row["res68_abs_frac_ci95"][1]) >= 0.08,
            },
        ]
    )
    if not bool(p07e_repro["pass"].all()):
        raise RuntimeError("P07e retained-window reproduction failed")

    print("propagating observed/template/ML corrections into natural high-amplitude timing tails", flush=True)
    timing = timing_branches(config, meta, waves, p07e_summary, fold)
    timing_summary_frame = summarize_by_run(
        timing,
        ["method", "family"],
        [
            "n_events",
            "timing_tail_frac_abs_gt5ns",
            "tail_delta_vs_observed",
            "timing_sigma68_ns",
            "sigma68_delta_vs_observed_ns",
            "timing_q95_abs_ns",
            "q_template_median",
            "amp_ratio_median",
        ],
        rng,
        int(config["bootstrap_reps"]),
    )
    ml_bounds = timing_summary_frame[timing_summary_frame["family"] == "ml_nuisance"]
    nuisance = pd.DataFrame(
        [
            {
                "quantity": "ML timing-tail nuisance span",
                "low": float(ml_bounds["timing_tail_frac_abs_gt5ns"].min()),
                "high": float(ml_bounds["timing_tail_frac_abs_gt5ns"].max()),
                "span": float(ml_bounds["timing_tail_frac_abs_gt5ns"].max() - ml_bounds["timing_tail_frac_abs_gt5ns"].min()),
            },
            {
                "quantity": "ML sigma68 nuisance span ns",
                "low": float(ml_bounds["timing_sigma68_ns"].min()),
                "high": float(ml_bounds["timing_sigma68_ns"].max()),
                "span": float(ml_bounds["timing_sigma68_ns"].max() - ml_bounds["timing_sigma68_ns"].min()),
            },
            {
                "quantity": "P07e artificial res68 CI used",
                "low": float(ml_row["res68_abs_frac_ci95"][0]),
                "high": float(ml_row["res68_abs_frac_ci95"][1]),
                "span": float(ml_row["res68_abs_frac_ci95"][1] - ml_row["res68_abs_frac_ci95"][0]),
            },
        ]
    )

    print("running leakage probes", flush=True)
    leakage = leakage_checks(config, artificial, fold, rng)
    leakage_pass = bool(leakage["pass"].all())

    reproduction.to_csv(out_dir / "reproduction_gate.csv", index=False)
    p07e_repro.to_csv(out_dir / "p07e_w2_8_reproduction.csv", index=False)
    artificial.to_csv(out_dir / "artificial_recovery_by_run.csv", index=False)
    p07e_summary.to_csv(out_dir / "artificial_recovery_summary.csv", index=False)
    timing.to_csv(out_dir / "natural_timing_by_run.csv", index=False)
    timing_summary_frame.to_csv(out_dir / "natural_timing_summary.csv", index=False)
    nuisance.to_csv(out_dir / "p07e_nuisance_envelope.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    main_rows = timing_summary_frame.set_index("method")
    observed = main_rows.loc["observed_saturated"]
    trad = main_rows.loc["traditional_template"]
    ml = main_rows.loc["ml_corrected"]
    headline_text = (
        f"Observed saturated B2 events have tail fraction {observed['timing_tail_frac_abs_gt5ns']:.4f}; "
        f"the train-run retained-window template branch gives {trad['timing_tail_frac_abs_gt5ns']:.4f} "
        f"(delta {trad['tail_delta_vs_observed']:+.4f}), and the P07e-style ML correction gives "
        f"{ml['timing_tail_frac_abs_gt5ns']:.4f} (delta {ml['tail_delta_vs_observed']:+.4f}). "
        f"The explicit P07e ML nuisance span is {float(nuisance.iloc[0]['span']):.4f} in tail fraction, "
        "and the failed P07e adoption screen prevents treating the ML correction as production timing."
    )
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].all() and p07e_repro["pass"].all()),
        "raw_root_dir": config["raw_root_dir"],
        "split": "leave-one-run-out by run over Sample-II analysis runs",
        "methods": ["observed_saturated", "traditional_template", "ml_corrected"],
        "p07e_nuisance": {
            "retained_window": config["retained_window"],
            "artificial_res68_abs_frac": float(ml_row["res68_abs_frac"]),
            "artificial_res68_abs_frac_ci95": [float(x) for x in ml_row["res68_abs_frac_ci95"]],
            "bias_median_frac": float(ml_row["bias_median_frac"]),
            "bias_median_frac_ci95": [float(x) for x in ml_row["bias_median_frac_ci95"]],
            "adoptable": False,
        },
        "timing_summary": timing_summary_frame.to_dict(orient="records"),
        "nuisance_envelope": nuisance.to_dict(orient="records"),
        "leakage_audit": {
            "pass": leakage_pass,
            "split_by_run": bool((leakage[leakage["check"] == "train_heldout_event_overlap"]["value"] == 0).all()),
            "features_excluded": ["run_id", "event_id", "downstream_timing", "true_amplitude", "heldout_labels"],
            "too_good_to_be_true": bool((leakage[leakage["check"] == "ml_too_good_to_be_true"]["pass"] == False).any()),
        },
        "headline_text": headline_text,
        "follow_up_text": "No follow-up ticket appended: existing done reports and the study registry already cover P07e duplicate-channel validation and P07g-style saturation acceptance rules, so a new ticket would duplicate existing work.",
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, reproduction, p07e_repro, p07e_summary, timing_summary_frame, nuisance, leakage, result)
    write_manifest(out_dir, config_path, config, result["runtime_sec"])
    print(json.dumps({"out_dir": str(out_dir), "headline": headline_text, "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
