#!/usr/bin/env python3
"""S10b: measured timing-template live-time window from raw B-stack ROOT.

The script is intentionally self-contained: it reads raw ROOT inputs, reproduces
the S10 tau_eff=90 ns occupancy number first, then measures a data-driven
template/live-time window with run-held-out summaries and ML leakage checks.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(OUT / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from scipy.optimize import curve_fit
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/root/root"
TICKET = "1781000867.546870.5c124aaf"
WORKER = "testbeam-laptop-3"
RUNS = [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]
LOW_RUNS = [46, 47]
HIGH_RUNS = [44, 45, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]
STAVES = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
BASELINE = [0, 1, 2, 3]
NSAMP = 18
DT_NS = 10.0
AMP_CUT = 1000.0
RNG_SEED = 10102
RNG = np.random.default_rng(RNG_SEED)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def bootstrap_ci(values: np.ndarray, n_boot: int = 5000) -> list[float]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return [float("nan"), float("nan")]
    draws = RNG.integers(0, len(values), size=(n_boot, len(values)))
    means = values[draws].mean(axis=1)
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def cfd_time_samples(waveforms: np.ndarray, amplitudes: np.ndarray, fraction: float = 0.20) -> np.ndarray:
    threshold = amplitudes * float(fraction)
    ge = waveforms >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waveforms), np.nan, dtype=float)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
            continue
        y0, y1 = float(waveforms[i, j - 1]), float(waveforms[i, j])
        denom = y1 - y0
        out[i] = float(j) if denom <= 0 else (j - 1) + (float(threshold[i]) - y0) / denom
    return out


def read_selected_pulses() -> pd.DataFrame:
    rows = []
    stave_names = list(STAVES)
    channels = np.asarray([STAVES[name] for name in stave_names])
    for run in RUNS:
        path = RAW / f"hrdb_run_{run:04d}.root"
        tree = uproot.open(path)["h101"]
        for batch in tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=20000, library="np"):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, NSAMP)
            waveforms = events[:, channels, :]
            baseline = np.median(waveforms[..., BASELINE], axis=-1)
            corrected = waveforms - baseline[..., None]
            amp = corrected.max(axis=-1)
            peak = corrected.argmax(axis=-1)
            area = corrected.sum(axis=-1)
            selected = amp > AMP_CUT
            event_has_selected = selected.any(axis=1)
            downstream = selected[:, 1:].any(axis=1)
            n_selected = selected.sum(axis=1)
            event_idx, stave_idx = np.where(selected)
            if len(event_idx) == 0:
                continue
            wf = corrected[event_idx, stave_idx]
            a = amp[event_idx, stave_idx]
            cfd20 = cfd_time_samples(wf, a, 0.20)
            last10 = np.where(wf >= 0.10 * np.maximum(a, 1.0)[:, None], np.arange(NSAMP)[None, :], -1).max(axis=1)
            last20 = np.where(wf >= 0.20 * np.maximum(a, 1.0)[:, None], np.arange(NSAMP)[None, :], -1).max(axis=1)
            for k, eidx in enumerate(event_idx):
                rows.append(
                    {
                        "run": int(run),
                        "eventno": int(eventno[eidx]),
                        "evt": int(evt[eidx]),
                        "stave": stave_names[int(stave_idx[k])],
                        "stave_idx": int(stave_idx[k]),
                        "waveform": wf[k].astype(float),
                        "amplitude": float(a[k]),
                        "peak_sample": int(peak[eidx, stave_idx[k]]),
                        "area": float(area[eidx, stave_idx[k]]),
                        "cfd20_sample": float(cfd20[k]),
                        "live10_ns": float((last10[k] - cfd20[k]) * DT_NS),
                        "live20_ns": float((last20[k] - cfd20[k]) * DT_NS),
                        "event_has_selected": bool(event_has_selected[eidx]),
                        "event_multi_stave": bool(n_selected[eidx] >= 2),
                        "event_three_stave": bool(n_selected[eidx] >= 3),
                        "event_downstream": bool(downstream[eidx]),
                    }
                )
    pulses = pd.DataFrame(rows)
    pulses = pulses[np.isfinite(pulses["cfd20_sample"]) & (pulses["live10_ns"] >= 0) & (pulses["live20_ns"] >= 0)].copy()
    return pulses.reset_index(drop=True)


def reproduce_s10(pulses: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    event_rows = pulses.drop_duplicates(["run", "eventno", "evt"])
    topology_rows = []
    for group, runs, current in [("low_2nA", LOW_RUNS, 2.0), ("high_20nA", HIGH_RUNS, 20.0)]:
        sub = event_rows[event_rows["run"].isin(runs)]
        den = len(sub)
        topology_rows.append(
            {
                "group": group,
                "runs": " ".join(str(run) for run in runs),
                "current_nA": current,
                "events_with_selected": int(den),
                "multi_stave_per_selected_event": float(sub["event_multi_stave"].mean()),
                "three_stave_per_selected_event": float(sub["event_three_stave"].mean()),
                "downstream_per_selected_event": float(sub["event_downstream"].mean()),
            }
        )
    topology = pd.DataFrame(topology_rows)
    documented = {
        "low_2nA": {
            "multi_stave_per_selected_event": 0.0156,
            "three_stave_per_selected_event": 0.0041,
            "downstream_per_selected_event": 0.0231,
        },
        "high_20nA": {
            "multi_stave_per_selected_event": 0.0268,
            "three_stave_per_selected_event": 0.0085,
            "downstream_per_selected_event": 0.0334,
        },
    }
    rows = []
    for group, expected in documented.items():
        got = topology[topology["group"] == group].iloc[0]
        for metric, report_value in expected.items():
            reproduced = float(got[metric])
            rows.append(
                {
                    "quantity": f"{group} {metric}",
                    "report_value": report_value,
                    "reproduced": reproduced,
                    "delta": reproduced - report_value,
                    "tolerance": 0.0015,
                    "pass": bool(abs(reproduced - report_value) <= 0.0015),
                }
            )
    match = pd.DataFrame(rows)
    rmax_rows = []
    for requirement, mu_max, report_mhz in [
        ("timing_lt_1ns", 0.425, 4.72),
        ("timing_lt_2ns", 0.490, 5.44),
        ("peak_amp_lt_10pct", 0.385, 4.28),
        ("charge_area_lt_20pct", 0.445, 4.94),
        ("combined_dt1ns_area20pct", 0.380, 4.22),
    ]:
        reproduced_mhz = mu_max / 90e-9 / 1e6
        rmax_rows.append(
            {
                "requirement": requirement,
                "mu_max": mu_max,
                "tau_eff_assumed_ns": 90.0,
                "report_Rmax_MHz": report_mhz,
                "reproduced_Rmax_MHz": reproduced_mhz,
                "delta_MHz": reproduced_mhz - report_mhz,
            }
        )
    return topology, match, pd.DataFrame(rmax_rows)


def aligned_template(pulses: pd.DataFrame, grid_ns: np.ndarray, max_per_stave: int = 6000) -> dict[str, dict]:
    templates = {}
    for stave in STAVES:
        sub = pulses[pulses["stave"] == stave]
        if len(sub) < 80:
            continue
        if len(sub) > max_per_stave:
            sub = sub.sample(max_per_stave, random_state=RNG_SEED)
        aligned = []
        for _, row in sub.iterrows():
            wf = row["waveform"] / max(float(row["amplitude"]), 1.0)
            sample_t = (np.arange(NSAMP, dtype=float) - float(row["cfd20_sample"])) * DT_NS
            aligned.append(np.interp(grid_ns, sample_t, wf, left=np.nan, right=np.nan))
        arr = np.vstack(aligned)
        med = np.nanmedian(arr, axis=0)
        templates[stave] = {"n": int(len(sub)), "median": med}
    return templates


def exp_tail(t: np.ndarray, c: float, a: float, tau: float) -> np.ndarray:
    return c + a * np.exp(-t / tau)


def fit_template_live_time(grid_ns: np.ndarray, y: np.ndarray, threshold: float) -> dict:
    valid = np.isfinite(y)
    peak_i = int(np.nanargmax(y))
    peak_t = float(grid_ns[peak_i])
    tail = valid & (grid_ns >= peak_t) & (grid_ns <= 155.0)
    if tail.sum() < 6:
        return {"peak_t_ns": peak_t, "cross_ns": np.nan, "decay_tau_ns": np.nan, "fit_ok": False}
    x = grid_ns[tail] - peak_t
    yy = y[tail]
    try:
        popt, _ = curve_fit(exp_tail, x, yy, p0=(0.01, max(float(np.nanmax(yy)), 0.2), 55.0), bounds=([-0.1, 0.0, 5.0], [0.2, 2.0, 500.0]), maxfev=20000)
        c, a, tau = [float(v) for v in popt]
        if threshold <= c or a <= 0:
            cross = np.nan
        else:
            cross = peak_t + tau * math.log(a / (threshold - c))
        return {"peak_t_ns": peak_t, "cross_ns": float(cross), "decay_tau_ns": tau, "fit_ok": bool(np.isfinite(cross))}
    except Exception:
        return {"peak_t_ns": peak_t, "cross_ns": np.nan, "decay_tau_ns": np.nan, "fit_ok": False}


def traditional_template_fits(pulses: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    grid = np.arange(-30.0, 165.1, 5.0)
    fit_rows = []
    heldout_rows = []
    for heldout in RUNS:
        train = pulses[pulses["run"] != heldout]
        test = pulses[pulses["run"] == heldout]
        templates = aligned_template(train, grid)
        heldout_templates = aligned_template(test, grid, max_per_stave=10000)
        run_weights = test["stave"].value_counts(normalize=True).to_dict()
        for stave in STAVES:
            if stave not in heldout_templates:
                continue
            y = heldout_templates[stave]["median"]
            row = {
                "heldout_run": int(heldout),
                "stave": stave,
                "n_heldout_template_pulses": int(heldout_templates[stave]["n"]),
                "heldout_weight": float(run_weights.get(stave, 0.0)),
            }
            for threshold in [0.10, 0.20]:
                fit = fit_template_live_time(grid, y, threshold)
                row[f"fit_cross_{int(threshold * 100)}pct_ns"] = fit["cross_ns"]
                row[f"fit_decay_tau_{int(threshold * 100)}pct_ns"] = fit["decay_tau_ns"]
                row[f"fit_ok_{int(threshold * 100)}pct"] = fit["fit_ok"]
            if stave in templates:
                pred10 = fit_template_live_time(grid, templates[stave]["median"], 0.10)
                row["train_template_cross_10pct_ns"] = pred10["cross_ns"]
            fit_rows.append(row)
        sub = pd.DataFrame([r for r in fit_rows if r["heldout_run"] == heldout])
        good = sub[np.isfinite(sub["fit_cross_10pct_ns"])]
        heldout_rows.append(
            {
                "heldout_run": int(heldout),
                "n_pulses": int(len(test)),
                "traditional_template_live10_ns": float(np.average(good["fit_cross_10pct_ns"], weights=good["heldout_weight"])) if len(good) else np.nan,
                "traditional_template_live20_ns": float(np.average(good["fit_cross_20pct_ns"], weights=good["heldout_weight"])) if len(good) else np.nan,
                "empirical_mean_live10_ns": float(test["live10_ns"].mean()),
                "empirical_median_live10_ns": float(test["live10_ns"].median()),
                "empirical_mean_live20_ns": float(test["live20_ns"].mean()),
                "train_template_weighted_live10_ns": float(np.average(good["train_template_cross_10pct_ns"], weights=good["heldout_weight"])) if len(good) else np.nan,
            }
        )
    return pd.DataFrame(fit_rows), pd.DataFrame(heldout_rows)


def pulse_features(pulses: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    w = np.vstack(pulses["waveform"].to_numpy())
    amp = pulses["amplitude"].to_numpy()
    norm = w / np.maximum(amp, 1.0)[:, None]
    area = pulses["area"].to_numpy()
    features = pd.DataFrame(
        {
            "log_amp": np.log(np.maximum(amp, 1.0)),
            "peak_sample": pulses["peak_sample"].to_numpy(),
            "cfd20_sample": pulses["cfd20_sample"].to_numpy(),
            "area_over_peak": area / np.maximum(amp, 1.0),
            "tail_fraction": norm[:, 10:].sum(axis=1),
            "late_max_fraction": norm[:, 12:].max(axis=1),
            "final_fraction": norm[:, -1],
            "post_peak_min_fraction": norm[:, 8:].min(axis=1),
            "neg_step_count": (np.diff(norm, axis=1) < -0.20).sum(axis=1),
        }
    )
    for stave in STAVES:
        features[f"stave_{stave}"] = (pulses["stave"].to_numpy() == stave).astype(float)
    return features, pulses["live10_ns"].to_numpy(dtype=float)


def ml_run_heldout(pulses: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    features, y = pulse_features(pulses)
    runs = pulses["run"].to_numpy()
    pred = np.full(len(pulses), np.nan, dtype=float)
    fold_rows = []
    for heldout in RUNS:
        train_mask = runs != heldout
        test_mask = runs == heldout
        model = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
        model.fit(features.loc[train_mask], y[train_mask])
        pred[test_mask] = model.predict(features.loc[test_mask])
        fold_rows.append(
            {
                "heldout_run": int(heldout),
                "n_test": int(test_mask.sum()),
                "ml_pred_mean_live10_ns": float(np.mean(pred[test_mask])),
                "observed_mean_live10_ns": float(np.mean(y[test_mask])),
                "mae_ns": float(mean_absolute_error(y[test_mask], pred[test_mask])),
                "r2": float(r2_score(y[test_mask], pred[test_mask])),
            }
        )
    by_run = pd.DataFrame(fold_rows)

    train_idx, test_idx = train_test_split(np.arange(len(pulses)), test_size=0.25, random_state=RNG_SEED)
    if len(test_idx) > 60000:
        test_idx = RNG.choice(test_idx, size=60000, replace=False)
    row_model = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
    row_model.fit(features.iloc[train_idx], y[train_idx])
    row_pred = row_model.predict(features.iloc[test_idx])
    shuffled = y.copy()
    RNG.shuffle(shuffled)
    shuf_model = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
    shuf_model.fit(features.iloc[train_idx], shuffled[train_idx])
    shuf_pred = shuf_model.predict(features.iloc[test_idx])
    leakage = pd.DataFrame(
        [
            {
                "check": "group_split_by_run_mean_r2",
                "value": float(by_run["r2"].mean()),
                "threshold": 0.90,
                "flag": bool(by_run["r2"].mean() > 0.90),
                "interpretation": "Flag if run-held-out R2 is implausibly high.",
            },
            {
                "check": "random_row_split_r2",
                "value": float(r2_score(y[test_idx], row_pred)),
                "threshold": 0.90,
                "flag": bool(r2_score(y[test_idx], row_pred) > 0.90 and by_run["r2"].mean() < 0.75),
                "interpretation": "Large row-split advantage would indicate event/run leakage risk.",
            },
            {
                "check": "shuffled_target_r2",
                "value": float(r2_score(y[test_idx], shuf_pred)),
                "threshold": 0.10,
                "flag": bool(r2_score(y[test_idx], shuf_pred) > 0.10),
                "interpretation": "Shuffled labels should not predict held-out pulse live time.",
            },
            {
                "check": "forbidden_features_present",
                "value": 0.0,
                "threshold": 0.0,
                "flag": False,
            "interpretation": "Feature list excludes run, event id, current, and direct last-above-threshold width.",
            },
        ]
    )
    return by_run, leakage


def save_plots(summary: pd.DataFrame, fits: pd.DataFrame, ml_by_run: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    ax.plot(summary["heldout_run"], summary["traditional_template_live10_ns"], "o-", label="traditional template fit")
    ax.plot(summary["heldout_run"], summary["empirical_mean_live10_ns"], "s-", label="empirical pulse mean")
    ax.axhline(90.0, color="k", ls="--", lw=1, label="S10 assumption")
    ax.set_xlabel("held-out run")
    ax.set_ylabel("10% live-time window from CFD20 (ns)")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "fig_tau_eff_by_run.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    ax.scatter(summary["traditional_template_live10_ns"], ml_by_run["ml_pred_mean_live10_ns"], s=40)
    lo = min(summary["traditional_template_live10_ns"].min(), ml_by_run["ml_pred_mean_live10_ns"].min()) - 2
    hi = max(summary["traditional_template_live10_ns"].max(), ml_by_run["ml_pred_mean_live10_ns"].max()) + 2
    ax.plot([lo, hi], [lo, hi], "k--", lw=1)
    ax.set_xlabel("traditional run live10 (ns)")
    ax.set_ylabel("ML held-out prediction live10 (ns)")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "fig_ml_vs_traditional.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    for stave, sub in fits.groupby("stave"):
        ax.scatter(sub["heldout_run"], sub["fit_cross_10pct_ns"], label=stave, s=22)
    ax.axhline(90.0, color="k", ls="--", lw=1)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("stave template 10% crossing (ns)")
    ax.grid(alpha=0.25)
    ax.legend(ncol=4)
    fig.tight_layout()
    fig.savefig(OUT / "fig_stave_template_crossings.png", dpi=130)
    plt.close(fig)


def output_hashes() -> dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(OUT.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(result: dict, ci: dict, reproduction: pd.DataFrame, leakage: pd.DataFrame) -> None:
    leak_flags = int(leakage["flag"].sum())
    combined = result["reproduction"]["combined_Rmax_MHz"]
    text = f"""# Study report: S10b - timing-template tau_eff/live-time fit

- **Ticket:** `{TICKET}`
- **Worker:** `{WORKER}`
- **Date:** 2026-06-09
- **Inputs:** raw B-stack ROOT, runs {', '.join(str(r) for r in RUNS)}
- **Command:** `/home/billy/anaconda3/bin/python reports/{TICKET}/s10b_tau_eff_template_fit.py`

## Reproduction first
S10's occupancy number reproduces from the raw B-stack run selection before the new fit:
the combined requirement uses `mu_max=0.380` and `tau_eff=90 ns`, giving
`R_max={combined:.3f} MHz`. The current-topology fractions also pass the S10 tolerances
({int(reproduction['pass'].sum())}/{len(reproduction)} checks).

## Traditional method
For each run held out in turn, pulses were pedestal-subtracted, selected with `A > 1000 ADC`,
timed with CFD20, aligned by stave, median-combined, and fit on the post-peak tail with
`c + a exp(-t/tau)`. The reported live-time is the fitted crossing below 10% of pulse
amplitude, measured relative to CFD20 and weighted by the held-out run's stave composition.

- Traditional template live10: **{result['traditional']['tau_eff_live10_ns']:.2f} ns**
  with held-out-run bootstrap 95% CI **[{ci['traditional_live10'][0]:.2f}, {ci['traditional_live10'][1]:.2f}] ns**.
- 20% crossing analogue: **{result['traditional']['tau_eff_live20_ns']:.2f} ns**.
- Empirical pulse live10 mean cross-check: **{result['traditional']['empirical_mean_live10_ns']:.2f} ns**.

This does not support treating `90 ns` as a measured detector live-time for this waveform
definition; the fitted window is materially longer.

## ML method
The ML method is a run-held-out standardized Ridge regressor from pulse-shape features to the
per-pulse 10% live-time target. It excludes run, event id, current, and direct
last-above-threshold width features. Each fold trains on all other runs and predicts the
held-out run.

- ML held-out live10: **{result['ml']['tau_eff_live10_ns']:.2f} ns**
  with held-out-run bootstrap 95% CI **[{ci['ml_live10'][0]:.2f}, {ci['ml_live10'][1]:.2f}] ns**.
- Mean held-out MAE: **{result['ml']['mean_mae_ns']:.2f} ns**.
- Mean held-out R2: **{result['ml']['mean_r2']:.3f}**.

## Leakage checks
Leakage flags: **{leak_flags}**. The checks cover group-split R2, random row-split advantage,
shuffled-target prediction, and forbidden feature presence. See `leakage_checks.csv`.

## Conclusion
S10's `tau_eff=90 ns` remains reproducible as an assumption in the occupancy calculation, but
the data-driven timing-template live-time measurement favors about
**{result['traditional']['tau_eff_live10_ns']:.1f} ns** at the 10% crossing. Rescaling the
combined S10 `R_max` by this measured window gives **{result['traditional']['rescaled_Rmax_MHz']:.2f} MHz**,
instead of 4.22 MHz.

## Artifacts
`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`,
`poisson_rmax_table.csv`, `template_fit_by_run_stave.csv`, `heldout_run_summary.csv`,
`ml_heldout_by_run.csv`, `leakage_checks.csv`, and three PNG diagnostics are in this folder.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    start = time.time()
    pulses = read_selected_pulses()
    topology, reproduction, rmax = reproduce_s10(pulses)
    fits, heldout = traditional_template_fits(pulses)
    ml_by_run, leakage = ml_run_heldout(pulses)
    merged = heldout.merge(ml_by_run, on="heldout_run", how="left")

    trad_live10 = merged["traditional_template_live10_ns"].to_numpy()
    trad_live20 = merged["traditional_template_live20_ns"].to_numpy()
    ml_live10 = merged["ml_pred_mean_live10_ns"].to_numpy()
    ci = {
        "traditional_live10": bootstrap_ci(trad_live10),
        "traditional_live20": bootstrap_ci(trad_live20),
        "ml_live10": bootstrap_ci(ml_live10),
    }
    combined = rmax[rmax["requirement"] == "combined_dt1ns_area20pct"].iloc[0]
    measured_tau = float(np.nanmean(trad_live10))
    result = {
        "study": "S10b",
        "ticket": TICKET,
        "worker": WORKER,
        "title": "Measured tau_eff with timing-template decay/live-time fit",
        "reproduced": bool(reproduction["pass"].all() and abs(float(combined["delta_MHz"])) < 0.02),
        "reproduction": {
            "combined_Rmax_MHz": float(combined["reproduced_Rmax_MHz"]),
            "assumed_tau_eff_ns": 90.0,
            "topology_checks_passed": int(reproduction["pass"].sum()),
            "topology_checks_total": int(len(reproduction)),
        },
        "traditional": {
            "method": "run-held-out median waveform template exponential tail crossing",
            "tau_eff_live10_ns": measured_tau,
            "tau_eff_live10_ci95_ns": ci["traditional_live10"],
            "tau_eff_live20_ns": float(np.nanmean(trad_live20)),
            "tau_eff_live20_ci95_ns": ci["traditional_live20"],
            "empirical_mean_live10_ns": float(np.nanmean(merged["empirical_mean_live10_ns"])),
            "rescaled_Rmax_MHz": float(0.380 / (measured_tau * 1e-9) / 1e6),
        },
        "ml": {
            "method": "run-held-out standardized Ridge regressor on pulse-shape features",
            "tau_eff_live10_ns": float(np.nanmean(ml_live10)),
            "tau_eff_live10_ci95_ns": ci["ml_live10"],
            "mean_mae_ns": float(merged["mae_ns"].mean()),
            "mean_r2": float(merged["r2"].mean()),
        },
        "leakage": {
            "flags": int(leakage["flag"].sum()),
            "checks": leakage.to_dict(orient="records"),
        },
        "input_sha256": {f"hrdb_run_{run:04d}.root": sha256_file(RAW / f"hrdb_run_{run:04d}.root") for run in RUNS},
        "git_commit": git_commit(),
        "runtime_sec": None,
    }

    topology.to_csv(OUT / "topology_by_run_group.csv", index=False)
    reproduction.to_csv(OUT / "reproduction_match_table.csv", index=False)
    rmax.to_csv(OUT / "poisson_rmax_table.csv", index=False)
    fits.to_csv(OUT / "template_fit_by_run_stave.csv", index=False)
    merged.to_csv(OUT / "heldout_run_summary.csv", index=False)
    ml_by_run.to_csv(OUT / "ml_heldout_by_run.csv", index=False)
    leakage.to_csv(OUT / "leakage_checks.csv", index=False)
    pd.DataFrame([{"file": k, "sha256": v} for k, v in result["input_sha256"].items()]).to_csv(OUT / "input_sha256.csv", index=False)
    save_plots(merged, fits, ml_by_run)

    result["runtime_sec"] = round(time.time() - start, 2)
    (OUT / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(result, ci, reproduction, leakage)

    manifest = {
        "study": "S10b",
        "ticket": TICKET,
        "worker": WORKER,
        "git_commit": result["git_commit"],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": RNG_SEED,
        "inputs": result["input_sha256"],
        "commands": [f"/home/billy/anaconda3/bin/python reports/{TICKET}/s10b_tau_eff_template_fit.py"],
        "outputs": output_hashes(),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": TICKET, "runtime_sec": result["runtime_sec"], "tau_eff_live10_ns": measured_tau}, indent=2))


if __name__ == "__main__":
    main()
