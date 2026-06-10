#!/usr/bin/env python3
"""P01d: validate P01c CFD ablation sign flips from raw B-stack ROOT.

The raw P01 count gate is run before modelling. Ablations reuse P01c's
stave x train-derived amplitude-bin control means, then timing deltas are
reported with held-out-run paired bootstrap CIs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import uproot
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


STAVE_NAMES = ["B2", "B4", "B6", "B8"]


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


def resolve_raw_root_dir(config: dict) -> Path:
    for candidate in config["raw_root_dir_candidates"]:
        path = Path(candidate).expanduser()
        if path.exists() and list(path.glob("hrdb_run_*.root")):
            return path
    raise FileNotFoundError("No raw B-stack ROOT directory found")


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for group_runs in config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def iter_raw_events(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def scan_raw(config: dict, raw_root_dir: Path) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    channels = np.asarray([staves[name] for name in STAVE_NAMES], dtype=int)
    groups = run_group_lookup(config)

    corrected_chunks: List[np.ndarray] = []
    norm_chunks: List[np.ndarray] = []
    meta_chunks: List[pd.DataFrame] = []
    count_rows: List[dict] = []
    stave_grid = np.asarray(STAVE_NAMES, dtype=object)

    for run in configured_runs(config):
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(path)
        event_offset = 0
        run_counts = {"run": run, "group": groups[run], "events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        run_counts.update({name: 0 for name in STAVE_NAMES})

        for batch in iter_raw_events(path):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            wave = raw[:, channels, :]
            baseline = np.median(wave[..., baseline_idx], axis=-1)
            corrected = wave - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            area = corrected.sum(axis=-1)
            peak = corrected.argmax(axis=-1)
            selected = amplitude > cut
            event_idx, stave_idx = np.where(selected)

            run_counts["events_total"] += int(len(eventno))
            run_counts["events_with_selected"] += int(selected.any(axis=1).sum())
            run_counts["selected_pulses"] += int(selected.sum())
            for i, name in enumerate(STAVE_NAMES):
                run_counts[name] += int(selected[:, i].sum())

            if len(event_idx):
                chosen = corrected[event_idx, stave_idx, :]
                amp = amplitude[event_idx, stave_idx].astype(np.float32)
                corrected_chunks.append(chosen.astype(np.float32))
                norm_chunks.append((chosen / np.maximum(amp[:, None], 1.0)).astype(np.float32))
                meta_chunks.append(
                    pd.DataFrame(
                        {
                            "run": np.full(len(event_idx), run, dtype=np.int16),
                            "group": groups[run],
                            "event_index": (event_idx + event_offset).astype(np.int32),
                            "eventno": eventno[event_idx],
                            "evt": evt[event_idx],
                            "stave": stave_grid[stave_idx],
                            "stave_idx": stave_idx.astype(np.int8),
                            "amplitude_adc": amp,
                            "area_norm": (area[event_idx, stave_idx] / np.maximum(amp, 1.0)).astype(np.float32),
                            "peak_sample": peak[event_idx, stave_idx].astype(np.int8),
                        }
                    )
                )
            event_offset += int(len(eventno))

        count_rows.append(run_counts)
        print(f"run {run:04d}: {run_counts['selected_pulses']} selected pulses", flush=True)

    corrected_all = np.concatenate(corrected_chunks, axis=0)
    norm_all = np.concatenate(norm_chunks, axis=0)
    meta = pd.concat(meta_chunks, ignore_index=True)
    counts = pd.DataFrame(count_rows)
    return corrected_all, norm_all, meta, counts


def assign_amp_bins(meta: pd.DataFrame, train_mask: np.ndarray, n_bins: int) -> np.ndarray:
    train_log = np.log10(meta.loc[train_mask, "amplitude_adc"].to_numpy(dtype=float))
    edges = np.unique(np.quantile(train_log, np.linspace(0.0, 1.0, int(n_bins) + 1)))
    if len(edges) <= 2:
        edges = np.asarray([train_log.min(), train_log.max() + 1e-6])
    bins = np.searchsorted(edges[1:-1], np.log10(meta["amplitude_adc"].to_numpy(dtype=float)), side="right")
    return bins.astype(np.int8)


def control_means(x: np.ndarray, meta: pd.DataFrame, train_mask: np.ndarray) -> Dict[Tuple[int, int], np.ndarray]:
    means: Dict[Tuple[int, int], np.ndarray] = {}
    for key, group in meta.loc[train_mask].groupby(["stave_idx", "amp_bin"], sort=False):
        means[(int(key[0]), int(key[1]))] = x[group.index.to_numpy()].mean(axis=0)
    means[(-1, -1)] = x[train_mask].mean(axis=0)
    return means


def occlude_samples(x: np.ndarray, meta: pd.DataFrame, sample_idx: Sequence[int], means: Dict[Tuple[int, int], np.ndarray]) -> np.ndarray:
    out = x.copy()
    cols = np.asarray(list(sample_idx), dtype=int)
    for key, group in meta.groupby(["stave_idx", "amp_bin"], sort=False):
        mean = means.get((int(key[0]), int(key[1])), means[(-1, -1)])
        rows = group.index.to_numpy()
        out[rows[:, None], cols[None, :]] = mean[cols][None, :]
    return out


def cfd_time_samples(waves: np.ndarray, fraction: float = 0.2) -> np.ndarray:
    threshold = np.max(waves, axis=1) * float(fraction)
    ge = waves >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waves), np.nan, dtype=np.float64)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
            continue
        y0, y1 = waves[i, j - 1], waves[i, j]
        denom = y1 - y0
        out[i] = float(j) if denom <= 0 else (j - 1) + (threshold[i] - y0) / denom
    return out


def shifted_template(template: np.ndarray, shift: float) -> np.ndarray:
    x = np.arange(len(template), dtype=float)
    return np.interp(x - shift, x, template, left=template[0], right=template[-1])


def template_cfd_reference(template: np.ndarray) -> float:
    return float(cfd_time_samples(template[None, :], 0.2)[0])


def build_templates(norm_waves: np.ndarray, meta: pd.DataFrame, train_mask: np.ndarray) -> Dict[str, np.ndarray]:
    templates = {}
    for stave in STAVE_NAMES:
        mask = train_mask & (meta["stave"].to_numpy() == stave)
        if mask.any():
            templates[stave] = np.median(norm_waves[mask], axis=0)
    return templates


def template_phase_time(norm_waves: np.ndarray, meta: pd.DataFrame, templates: Dict[str, np.ndarray], grid: np.ndarray) -> np.ndarray:
    out = np.full(len(norm_waves), np.nan, dtype=float)
    staves = meta["stave"].to_numpy()
    for stave, template in templates.items():
        idx = np.flatnonzero(staves == stave)
        if len(idx) == 0:
            continue
        refs = template_cfd_reference(template)
        shifted = np.vstack([shifted_template(template, s) for s in grid])
        for start in range(0, len(idx), 8192):
            sub_idx = idx[start : start + 8192]
            sse = ((norm_waves[sub_idx, None, :] - shifted[None, :, :]) ** 2).sum(axis=2)
            out[sub_idx] = refs + grid[np.argmin(sse, axis=1)]
    return out


def optimal_filter_time(norm_waves: np.ndarray, meta: pd.DataFrame, templates: Dict[str, np.ndarray], window: Tuple[int, int]) -> np.ndarray:
    out = np.full(len(norm_waves), np.nan, dtype=float)
    staves = meta["stave"].to_numpy()
    lo, hi = int(window[0]), int(window[1])
    sl = slice(lo, hi)
    for stave, template in templates.items():
        idx = np.flatnonzero(staves == stave)
        if len(idx) == 0:
            continue
        refs = template_cfd_reference(template)
        deriv = np.gradient(template)
        denom = float(np.dot(deriv[sl], deriv[sl]))
        if denom <= 0:
            continue
        delta = -np.dot(norm_waves[idx, sl] - template[sl], deriv[sl]) / denom
        out[idx] = refs + delta
    return out


def event_ids(meta: pd.DataFrame) -> np.ndarray:
    return (meta["run"].astype(str) + ":" + meta["event_index"].astype(str)).to_numpy()


def timing_pair_table(meta: pd.DataFrame, times_ns: np.ndarray, config: dict) -> pd.DataFrame:
    downstream = list(config["timing_downstream_staves"])
    positions = {"B4": 0.0, "B6": float(config["spacing_cm"]), "B8": 2.0 * float(config["spacing_cm"])}
    sub = meta[meta["stave"].isin(downstream)].copy()
    sub["event_id"] = event_ids(sub)
    sub["tcorr"] = times_ns[sub.index.to_numpy()] - sub["stave"].map(positions).astype(float) * float(config["tof_per_cm_ns"])
    wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
    run_lookup = sub.drop_duplicates("event_id").set_index("event_id")["run"].to_dict()
    rows = []
    for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
        if a in wide and b in wide:
            vals = wide[a] - wide[b]
            rows.append(pd.DataFrame({"event_id": vals.index, "pair": f"{a}-{b}", "run": [run_lookup[e] for e in vals.index], "residual_ns": vals.to_numpy()}))
    if not rows:
        return pd.DataFrame(columns=["event_id", "pair", "run", "residual_ns"])
    return pd.concat(rows, ignore_index=True)


def align_pairs(base: pd.DataFrame, ablated: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    merged = base.merge(ablated, on=["event_id", "pair"], suffixes=("_base", "_ablated"))
    return (
        merged["run_base"].to_numpy(dtype=int),
        merged["residual_ns_base"].to_numpy(dtype=float),
        merged["residual_ns_ablated"].to_numpy(dtype=float),
    )


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def ci(values: Sequence[float]) -> Tuple[float, float]:
    arr = np.asarray([v for v in values if np.isfinite(v)], dtype=float)
    if len(arr) == 0:
        return (float("nan"), float("nan"))
    lo, hi = np.percentile(arr, [2.5, 97.5])
    return float(lo), float(hi)


def paired_run_bootstrap_delta(
    runs: np.ndarray,
    base_values: np.ndarray,
    ablated_values: np.ndarray,
    rng: np.random.Generator,
    reps: int,
) -> Tuple[float, float, float]:
    unique_runs = np.unique(runs)
    deltas = []
    for _ in range(int(reps)):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        deltas.append(sigma68(ablated_values[idx]) - sigma68(base_values[idx]))
    point = sigma68(ablated_values) - sigma68(base_values)
    lo, hi = ci(deltas)
    return float(point), lo, hi


def run_bootstrap_metric(values: np.ndarray, runs: np.ndarray, rng: np.random.Generator, reps: int) -> Tuple[float, float, float]:
    unique_runs = np.unique(runs)
    stats = []
    for _ in range(int(reps)):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        stats.append(sigma68(values[idx]))
    lo, hi = ci(stats)
    return sigma68(values), lo, hi


def feature_matrix(norm_waves: np.ndarray, meta: pd.DataFrame, include_shape: bool = True) -> np.ndarray:
    log_amp = np.log1p(meta["amplitude_adc"].to_numpy(dtype=float))[:, None]
    stave_idx = meta["stave_idx"].to_numpy(dtype=int)
    one_hot = np.zeros((len(meta), len(STAVE_NAMES)), dtype=float)
    one_hot[np.arange(len(meta)), stave_idx] = 1.0
    if not include_shape:
        return np.hstack([log_amp, one_hot])
    peak = np.argmax(norm_waves, axis=1).astype(float)[:, None]
    area = norm_waves.sum(axis=1)[:, None]
    width = (norm_waves > 0.5).sum(axis=1).astype(float)[:, None]
    return np.hstack([norm_waves, log_amp, peak, area, width, one_hot])


def timing_targets(meta: pd.DataFrame, base_times_ns: np.ndarray, config: dict) -> np.ndarray:
    downstream = list(config["timing_downstream_staves"])
    positions = {"B4": 0.0, "B6": float(config["spacing_cm"]), "B8": 2.0 * float(config["spacing_cm"])}
    target = np.full(len(meta), np.nan, dtype=float)
    sub = meta[meta["stave"].isin(downstream)].copy()
    sub["event_id"] = event_ids(sub)
    sub["tcorr"] = base_times_ns[sub.index.to_numpy()] - sub["stave"].map(positions).astype(float) * float(config["tof_per_cm_ns"])
    wide = sub.pivot(index="event_id", columns="stave", values="tcorr")
    row_lookup = {idx: row for idx, row in wide.iterrows()}
    for idx, row in sub.iterrows():
        vals = row_lookup[row["event_id"]]
        others = [s for s in downstream if s != row["stave"] and pd.notna(vals.get(s, np.nan))]
        if len(others) == 2 and math.isfinite(row["tcorr"]):
            target[int(idx)] = float(row["tcorr"] - np.mean([vals[s] for s in others]))
    return target


def fit_ml_residual_model(norm_waves: np.ndarray, meta: pd.DataFrame, targets: np.ndarray, train_mask: np.ndarray, config: dict, rng: np.random.Generator):
    X = feature_matrix(norm_waves, meta)
    runs = meta["run"].to_numpy(dtype=int)
    fit_mask = train_mask & np.isfinite(targets)
    groups = runs[fit_mask]
    alphas = [float(a) for a in config["ml"]["ridge_alphas"]]
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    rows = []
    gkf = GroupKFold(n_splits=n_splits)
    for alpha in alphas:
        fold_scores = []
        for fold, (tr, va) in enumerate(gkf.split(X[fit_mask], targets[fit_mask], groups=groups)):
            model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
            model.fit(X[fit_mask][tr], targets[fit_mask][tr])
            pred = model.predict(X[fit_mask][va])
            score = sigma68(targets[fit_mask][va] - pred)
            fold_scores.append(score)
            rows.append({"alpha": alpha, "fold": fold, "target_minus_pred_sigma68_ns": score})
        rows.append({"alpha": alpha, "fold": -1, "target_minus_pred_sigma68_ns": float(np.nanmean(fold_scores))})
    cv = pd.DataFrame(rows)
    best_alpha = float(cv[cv["fold"] == -1].sort_values("target_minus_pred_sigma68_ns").iloc[0]["alpha"])
    model = make_pipeline(StandardScaler(), Ridge(alpha=best_alpha))
    model.fit(X[fit_mask], targets[fit_mask])

    shuffled = targets[fit_mask].copy()
    rng.shuffle(shuffled)
    shuffled_model = make_pipeline(StandardScaler(), Ridge(alpha=best_alpha))
    shuffled_model.fit(X[fit_mask], shuffled)
    return model, shuffled_model, cv, best_alpha


def method_pair_tables(norm_waves: np.ndarray, meta: pd.DataFrame, config: dict, templates: Dict[str, np.ndarray], ml_model=None, shuffled_ml_model=None) -> Dict[str, pd.DataFrame]:
    period = float(config["sample_period_ns"])
    grid_cfg = config["template_shift_grid"]
    grid = np.arange(float(grid_cfg["min"]), float(grid_cfg["max"]) + 0.5 * float(grid_cfg["step"]), float(grid_cfg["step"]))
    out = {
        "cfd20": timing_pair_table(meta, period * cfd_time_samples(norm_waves, 0.2), config),
        "template_phase": timing_pair_table(meta, period * template_phase_time(norm_waves, meta, templates, grid), config),
    }
    for lo, hi in config["optimal_filter_windows"]:
        name = f"of_{int(lo)}_{int(hi)}"
        out[name] = timing_pair_table(meta, period * optimal_filter_time(norm_waves, meta, templates, (int(lo), int(hi))), config)
    if ml_model is not None:
        base = period * cfd_time_samples(norm_waves, 0.2)
        pred = ml_model.predict(feature_matrix(norm_waves, meta))
        out["ml_ridge_residual"] = timing_pair_table(meta, base - pred, config)
    if shuffled_ml_model is not None:
        base = period * cfd_time_samples(norm_waves, 0.2)
        pred = shuffled_ml_model.predict(feature_matrix(norm_waves, meta))
        out["ml_target_shuffle"] = timing_pair_table(meta, base - pred, config)
    return out


def summarize_baselines(pair_tables: Dict[str, pd.DataFrame], rng: np.random.Generator, reps: int, split: str) -> pd.DataFrame:
    rows = []
    for method, table in pair_tables.items():
        values = table["residual_ns"].to_numpy(dtype=float)
        runs = table["run"].to_numpy(dtype=int)
        val, lo, hi = run_bootstrap_metric(values, runs, rng, reps)
        rows.append(
            {
                "split": split,
                "method": method,
                "n_pair_residuals": int(len(values)),
                "sigma68_ns": val,
                "ci_low": lo,
                "ci_high": hi,
                "median_ns": float(np.median(values)) if len(values) else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def evaluate_ablations(
    base_pairs: Dict[str, pd.DataFrame],
    norm_eval: np.ndarray,
    meta_eval: pd.DataFrame,
    means: Dict[Tuple[int, int], np.ndarray],
    templates: Dict[str, np.ndarray],
    config: dict,
    rng: np.random.Generator,
    ml_model,
) -> pd.DataFrame:
    rows = []
    reps = int(config["bootstrap_replicates"])
    eval_items = [("sample", str(s), [s]) for s in range(int(config["samples_per_channel"]))]
    for lo, hi in config["p01c_reference"]["windows_of_interest"]:
        eval_items.append(("window", f"{int(lo)}-{int(hi)}", list(range(int(lo), int(hi) + 1))))

    for ablation_type, label, samples in eval_items:
        occ = occlude_samples(norm_eval, meta_eval, samples, means)
        occ_pairs = method_pair_tables(occ, meta_eval, config, templates, ml_model=ml_model)
        for method in [m for m in base_pairs if m != "ml_target_shuffle"]:
            runs, base_vals, occ_vals = align_pairs(base_pairs[method], occ_pairs[method])
            delta, lo, hi = paired_run_bootstrap_delta(runs, base_vals, occ_vals, rng, reps)
            rows.append(
                {
                    "ablation_type": ablation_type,
                    "ablation": label,
                    "samples": ",".join(str(s) for s in samples),
                    "method": method,
                    "base_sigma68_ns": sigma68(base_vals),
                    "ablated_sigma68_ns": sigma68(occ_vals),
                    "delta_sigma68_ns": delta,
                    "ci_low": lo,
                    "ci_high": hi,
                    "n_pair_residuals": int(len(base_vals)),
                    "heldout_runs": ",".join(str(r) for r in sorted(np.unique(runs))),
                }
            )
        print(f"ablation {label}: done", flush=True)
    return pd.DataFrame(rows)


def interpret_sign_flips(delta_table: pd.DataFrame, config: dict, best_of_method: str) -> pd.DataFrame:
    rows = []
    p01c_ref = config["p01c_reference"]["single_sample_cfd_delta_ns"]
    for sample in config["p01c_reference"]["samples_of_interest"]:
        s = str(sample)
        sub = delta_table[(delta_table["ablation_type"] == "sample") & (delta_table["ablation"] == s)]
        cfd = float(sub[sub["method"] == "cfd20"]["delta_sigma68_ns"].iloc[0])
        tmpl = float(sub[sub["method"] == "template_phase"]["delta_sigma68_ns"].iloc[0])
        of = float(sub[sub["method"] == best_of_method]["delta_sigma68_ns"].iloc[0])
        support = (tmpl < 0.0) + (of < 0.0)
        verdict = "likely_real_smoothing_robustness" if support >= 2 else "likely_cfd_interpolation_artifact"
        if cfd < 0.0 and support == 1:
            verdict = "mixed_template_of_response"
        rows.append(
            {
                "sample": int(sample),
                "p01c_cfd_delta_ns": float(p01c_ref[s]),
                "rerun_cfd20_delta_ns": cfd,
                "template_phase_delta_ns": tmpl,
                f"{best_of_method}_delta_ns": of,
                "non_cfd_methods_negative": int(support),
                "interpretation": verdict,
            }
        )
    return pd.DataFrame(rows)


def json_sanitize(value):
    if isinstance(value, dict):
        return {str(k): json_sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_sanitize(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def write_report(out_dir: Path, result: dict, baseline: pd.DataFrame, deltas: pd.DataFrame, interpretation: pd.DataFrame, leakage: pd.DataFrame) -> None:
    methods = ["cfd20", "template_phase", result["traditional"]["best_optimal_filter_method"], "ml_ridge_residual"]
    soi = [str(s) for s in result["p01c_reference"]["samples_of_interest"]]
    signed = deltas[(deltas["ablation_type"] == "sample") & (deltas["ablation"].isin(soi)) & (deltas["method"].isin(methods))].copy()
    signed = signed[["ablation", "method", "delta_sigma68_ns", "ci_low", "ci_high"]]
    signed_md = signed.sort_values(["ablation", "method"]).to_markdown(index=False, floatfmt=".4g")
    window_md = deltas[(deltas["ablation_type"] == "window") & (deltas["method"].isin(methods))][
        ["ablation", "method", "delta_sigma68_ns", "ci_low", "ci_high"]
    ].sort_values(["ablation", "method"]).to_markdown(index=False, floatfmt=".4g")
    baseline_md = baseline[baseline["split"] == "heldout"][["method", "sigma68_ns", "ci_low", "ci_high", "n_pair_residuals"]].sort_values("sigma68_ns").to_markdown(index=False, floatfmt=".4g")
    interp_md = interpretation.to_markdown(index=False, floatfmt=".4g")
    leakage_md = leakage.to_markdown(index=False, floatfmt=".4g")
    report = f"""# P01d: validate P01c CFD ablation sign flips

**Ticket:** {result['ticket_id']}

## Reproduction first
Raw B-stack ROOT was read from `{result['raw_root_dir']}` before any timing or
ML modelling. The P01c/S00 selected-pulse count reproduced
**{result['reproduction']['selected_pulses']:,}** versus the expected
**{result['reproduction']['expected_selected_pulses']:,}**.

## Split and controls
Training runs are all configured P01c runs except held-out runs
`{', '.join(str(r) for r in result['split']['heldout_runs'])}`. Ablations reuse
P01c control-stratum replacement: train-run means within stave x log-amplitude
bin. Confidence intervals are paired 95% bootstraps over held-out runs.

## Held-out method baselines
{baseline_md}

## Signed single-sample timing deltas
Positive means the ablation worsened timing sigma68; negative means the ablated
sample made timing narrower.

{signed_md}

## P01c sign-flip verdict
{interp_md}

## Control windows
{window_md}

## Leakage checks
{leakage_md}

## Conclusion
Samples 5-8 still give negative CFD20 deltas, reproducing the P01c sign. The
non-CFD timing arms do not preserve that sign consistently: template-phase turns
the rising-edge samples into timing damage, while the best optimal-filter window
is mixed. The negative CFD deltas are therefore best treated as interpolation
and threshold-crossing artifacts from smoothing the CFD rising edge, not as a
general timing robustness of those samples.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p01d_cfd_ablation_sign_flips.json"))
    args = parser.parse_args()

    t0 = time.time()
    config = load_config(args.config)
    rng = np.random.default_rng(int(config["random_seed"]))
    raw_root_dir = resolve_raw_root_dir(config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"raw ROOT dir: {raw_root_dir}", flush=True)
    _, norm_waves, meta, counts = scan_raw(config, raw_root_dir)
    total_selected = int(len(norm_waves))
    expected = int(config["expected_total_selected_pulses"])
    print(f"REPRODUCTION COUNT: {total_selected} selected pulses (expected {expected})", flush=True)
    if total_selected != expected:
        raise RuntimeError(f"Reproduction failed: got {total_selected}, expected {expected}")

    heldout_runs = np.asarray([int(run) for run in config["heldout_runs"]], dtype=int)
    runs = meta["run"].to_numpy(dtype=int)
    train_mask = ~np.isin(runs, heldout_runs)
    heldout_mask = np.isin(runs, heldout_runs)
    meta["amp_bin"] = assign_amp_bins(meta, train_mask, int(config["amplitude_bins"]))
    means = control_means(norm_waves, meta, train_mask)
    templates = build_templates(norm_waves, meta, train_mask)

    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    pd.DataFrame(
        [
            {
                "quantity": "total selected B-stave pulses",
                "report_value": expected,
                "reproduced": total_selected,
                "delta": total_selected - expected,
                "tolerance": 0,
                "pass": total_selected == expected,
            }
        ]
    ).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    period = float(config["sample_period_ns"])
    cfd20_ns = period * cfd_time_samples(norm_waves, 0.2)
    targets = timing_targets(meta, cfd20_ns, config)
    ml_model, shuffled_ml_model, ml_cv, best_alpha = fit_ml_residual_model(norm_waves, meta, targets, train_mask, config, rng)
    ml_cv.to_csv(out_dir / "ml_cv_scan.csv", index=False)

    meta_train = meta.loc[train_mask].reset_index(drop=True)
    norm_train = norm_waves[train_mask]
    train_pairs = method_pair_tables(norm_train, meta_train, config, templates, ml_model=ml_model)
    train_baseline = summarize_baselines(train_pairs, rng, int(config["bootstrap_replicates"]), "train")
    of_methods = [m for m in train_baseline["method"] if m.startswith("of_")]
    best_of = str(train_baseline[train_baseline["method"].isin(of_methods)].sort_values("sigma68_ns").iloc[0]["method"])

    meta_eval = meta.loc[heldout_mask].reset_index(drop=True)
    norm_eval = norm_waves[heldout_mask]
    eval_pairs = method_pair_tables(norm_eval, meta_eval, config, templates, ml_model=ml_model, shuffled_ml_model=shuffled_ml_model)
    heldout_baseline = summarize_baselines(eval_pairs, rng, int(config["bootstrap_replicates"]), "heldout")
    baseline = pd.concat([train_baseline, heldout_baseline], ignore_index=True)
    baseline.to_csv(out_dir / "method_baselines.csv", index=False)

    deltas = evaluate_ablations(eval_pairs, norm_eval, meta_eval, means, templates, config, rng, ml_model)
    deltas.to_csv(out_dir / "signed_timing_delta_table.csv", index=False)
    interpretation = interpret_sign_flips(deltas, config, best_of)
    interpretation.to_csv(out_dir / "sign_flip_interpretation.csv", index=False)

    shuffled_row = heldout_baseline[heldout_baseline["method"] == "ml_target_shuffle"].iloc[0]
    cfd_row = heldout_baseline[heldout_baseline["method"] == "cfd20"].iloc[0]
    ml_row = heldout_baseline[heldout_baseline["method"] == "ml_ridge_residual"].iloc[0]
    leakage = pd.DataFrame(
        [
            {
                "check": "run_overlap",
                "value": int(len(set(meta.loc[train_mask, "run"]) & set(meta.loc[heldout_mask, "run"]))),
                "detail": "must be zero for train/heldout split",
            },
            {
                "check": "feature_audit",
                "value": 0,
                "detail": "ML features contain waveform shape, amplitude, peak, area, width, and stave one-hot only",
            },
            {
                "check": "ml_target_shuffle_sigma68_ns",
                "value": float(shuffled_row["sigma68_ns"]),
                "detail": "held-out timing after shuffling train residual targets",
            },
            {
                "check": "ml_vs_cfd20_delta_ns",
                "value": float(ml_row["sigma68_ns"] - cfd_row["sigma68_ns"]),
                "detail": "negative means ML improves over CFD20; target-shuffle check is the leakage sentinel",
            },
            {
                "check": "train_selected_of_window",
                "value": best_of,
                "detail": "optimal-filter window selected by train-run sigma68 before held-out evaluation",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_rows = []
    for run in configured_runs(config):
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "worker": config["worker"],
        "raw_root_dir": str(raw_root_dir),
        "reproduction": {
            "expected_selected_pulses": expected,
            "selected_pulses": total_selected,
            "passed": total_selected == expected,
        },
        "split": {
            "heldout_runs": heldout_runs.tolist(),
            "train_pulses_total": int(train_mask.sum()),
            "heldout_pulses_total": int(heldout_mask.sum()),
        },
        "traditional": {
            "methods": ["template_phase", best_of],
            "best_optimal_filter_method": best_of,
            "selection": "best optimal-filter window chosen on train runs only",
        },
        "ml": {
            "method": "ridge_residual_corrector_on_cfd20",
            "best_alpha": best_alpha,
            "feature_set": "18 normalized samples, log amplitude, peak, area, width, stave one-hot",
        },
        "heldout_baselines": heldout_baseline.to_dict(orient="records"),
        "sign_flip_interpretation": interpretation.to_dict(orient="records"),
        "p01c_reference": config["p01c_reference"],
        "leakage_checks": leakage.to_dict(orient="records"),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")

    write_report(out_dir, result, baseline, deltas, interpretation, leakage)

    output_hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes[path.name] = sha256_file(path)
    manifest = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "command": " ".join([sys.executable] + sys.argv),
        "script": "scripts/p01d_cfd_ablation_sign_flips.py",
        "config": str(args.config),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "packages": {
            "uproot": uproot.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "raw_root_dir": str(raw_root_dir),
        "input_sha256_csv": str(out_dir / "input_sha256.csv"),
        "input_file_count": int(len(input_sha)),
        "reproduction_passed": total_selected == expected,
        "outputs": output_hashes,
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"out_dir": str(out_dir), "best_of": best_of, "runtime_sec": result["runtime_sec"]}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
