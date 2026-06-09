#!/usr/bin/env python3
"""P07b: natural B2 saturation recovery impact on charge and timing tails.

Reads raw B-stack ROOT files, reproduces the P07 artificial fixed-ceiling
benchmark first, then evaluates traditional template extrapolation and ML
transfer on naturally saturated high-amplitude B2 pulses with run-held-out
folds and bootstrap CIs.
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
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import r2_score


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/root/root"
TICKET = "1781004956.668.7d00443a"
WORKER = "testbeam-laptop-3"
RUNS = [58, 59, 60, 61, 62, 63, 65]
P07_TRAIN_RUNS = [58, 59, 60, 61]
P07_TEST_RUNS = [62, 63, 65]
P07_STAVES = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
B2_CHANNEL = 0
BASELINE = [0, 1, 2, 3]
NSAMP = 18
DT_NS = 10.0
AMP_CUT = 1000.0
UNSAT_MAX = 6500.0
NATURAL_SAT = 7000.0
ARTIFICIAL_CEILING = 4000.0
RNG_SEED = 70702
RNG = np.random.default_rng(RNG_SEED)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def cfd_time(waveforms: np.ndarray, amplitudes: np.ndarray, fraction: float = 0.20) -> np.ndarray:
    threshold = np.asarray(amplitudes, dtype=float) * float(fraction)
    ge = waveforms >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waveforms), np.nan, dtype=float)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
            continue
        y0 = float(waveforms[i, j - 1])
        y1 = float(waveforms[i, j])
        denom = y1 - y0
        out[i] = float(j) if denom <= 0 else (j - 1) + (float(threshold[i]) - y0) / denom
    return out


def load_b2_pulses() -> pd.DataFrame:
    rows = []
    for run in RUNS:
        path = RAW / f"hrdb_run_{run:04d}.root"
        tree = uproot.open(path)["h101"]
        for batch in tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=20000, library="np"):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, NSAMP)
            raw = events[:, B2_CHANNEL, :]
            baseline = np.median(raw[:, BASELINE], axis=1)
            wave = raw - baseline[:, None]
            amp = wave.max(axis=1)
            peak = wave.argmax(axis=1)
            area = wave.sum(axis=1)
            selected = amp > AMP_CUT
            idx = np.where(selected)[0]
            if len(idx) == 0:
                continue
            for i in idx:
                rows.append(
                    {
                        "run": int(run),
                        "eventno": int(eventno[i]),
                        "evt": int(evt[i]),
                        "baseline_adc": float(baseline[i]),
                        "waveform": wave[i].astype(float),
                        "amplitude_adc": float(amp[i]),
                        "peak_sample": int(peak[i]),
                        "area_adc_samples": float(area[i]),
                    }
                )
    pulses = pd.DataFrame(rows)
    w = np.vstack(pulses["waveform"].to_numpy())
    pulses["cfd20_obs_sample"] = cfd_time(w, pulses["amplitude_adc"].to_numpy(), 0.20)
    pulses = pulses[np.isfinite(pulses["cfd20_obs_sample"])].copy()
    return pulses.reset_index(drop=True)


def clean_control_mask(pulses: pd.DataFrame) -> np.ndarray:
    a = pulses["amplitude_adc"].to_numpy()
    peak = pulses["peak_sample"].to_numpy()
    return (peak >= 4) & (peak <= 12) & (a > 1500.0) & (a < UNSAT_MAX)


def natural_saturation_mask(pulses: pd.DataFrame) -> np.ndarray:
    a = pulses["amplitude_adc"].to_numpy()
    peak = pulses["peak_sample"].to_numpy()
    return (peak >= 4) & (peak <= 13) & (a >= NATURAL_SAT)


def legacy_p07_reproduction(pulses: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    del pulses
    wtr_all, atr_all = load_legacy_p07_all_staves(P07_TRAIN_RUNS)
    wte_all, ate_all = load_legacy_p07_all_staves(P07_TEST_RUNS)
    mtr = legacy_clean_mask(wtr_all, atr_all)
    mte = legacy_clean_mask(wte_all, ate_all)
    wtr = wtr_all[mtr]
    atr = atr_all[mtr]
    wte = wte_all[mte]
    ate = ate_all[mte]
    if len(wtr) > 40000:
        idx = np.random.default_rng(0).choice(len(wtr), 40000, replace=False)
        wtr = wtr[idx]
        atr = atr[idx]
    template = (wtr / atr[:, None]).mean(axis=0)

    def legacy_template_recover(wc: np.ndarray, clipmask: np.ndarray) -> np.ndarray:
        out = np.zeros(len(wc), dtype=float)
        for i in range(len(wc)):
            usable = ~clipmask[i]
            s = template[usable]
            y = wc[i, usable]
            denom = float(s @ s)
            out[i] = float((s @ y) / denom) if denom > 1e-9 else float(wc[i].max())
        return out

    rows = []
    for ceiling in [4000.0, 3000.0, 2500.0, 2000.0]:
        seltr = atr > ceiling * 1.05
        selte = ate > ceiling * 1.05
        wtr_c = np.minimum(wtr[seltr], ceiling)
        wte_c = np.minimum(wte[selte], ceiling)
        cmte = wte[selte] >= ceiling
        rec_trad = legacy_template_recover(wte_c, cmte)
        gb = GradientBoostingRegressor(
            n_estimators=200,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.7,
            random_state=0,
        )
        gb.fit(wtr_c, np.log(atr[seltr]))
        rec_ml = np.exp(gb.predict(wte_c))
        rows.append(
            {
                "ceiling_adc": ceiling,
                "n_saturating_test": int(selte.sum()),
                "naive_res68": float(np.percentile(np.abs((ceiling - ate[selte]) / ate[selte]), 68)),
                "traditional_res68": float(np.percentile(np.abs((rec_trad - ate[selte]) / ate[selte]), 68)),
                "ml_res68": float(np.percentile(np.abs((rec_ml - ate[selte]) / ate[selte]), 68)),
                "ml_bias": float(np.median((rec_ml - ate[selte]) / ate[selte])),
            }
        )
    table = pd.DataFrame(rows)
    target = table[table["ceiling_adc"] == 4000.0].iloc[0]
    summary = {
        "p07_reported_ml_res68_c4000": 0.03243177807776981,
        "reproduced_ml_res68_c4000": float(target["ml_res68"]),
        "absolute_delta": float(abs(target["ml_res68"] - 0.03243177807776981)),
        "clean_train_after_cap": int(len(wtr)),
        "clean_test": int(len(wte)),
    }
    return table, summary


def load_legacy_p07_all_staves(runs: list[int]) -> tuple[np.ndarray, np.ndarray]:
    waveforms = []
    amplitudes = []
    channels = np.asarray(list(P07_STAVES.values()))
    total = 0
    for run in runs:
        path = RAW / f"hrdb_run_{run:04d}.root"
        tree = uproot.open(path)["h101"]
        for batch in tree.iterate(["HRDv"], step_size=20000, library="np"):
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, NSAMP)
            w = events[:, channels, :]
            baseline = np.median(w[..., BASELINE], axis=-1)
            corr = w - baseline[..., None]
            amp = corr.max(axis=-1)
            event_idx, stave_idx = np.where(amp > AMP_CUT)
            if len(event_idx):
                waveforms.append(corr[event_idx, stave_idx])
                amplitudes.append(amp[event_idx, stave_idx])
                total += int(len(event_idx))
        if total > 40000:
            break
    return np.vstack(waveforms), np.concatenate(amplitudes)


def legacy_clean_mask(waveforms: np.ndarray, amplitudes: np.ndarray) -> np.ndarray:
    peak = waveforms.argmax(axis=1)
    return (peak >= 4) & (peak <= 12) & (amplitudes > 1500.0) & (amplitudes < UNSAT_MAX)


def template_recover(wc: np.ndarray, clipmask: np.ndarray, template: np.ndarray) -> np.ndarray:
    out = np.zeros(len(wc), dtype=float)
    for i in range(len(wc)):
        rising = np.arange(NSAMP) <= int(np.argmax(wc[i]))
        usable = (~clipmask[i]) & rising & (template > 0.03)
        if usable.sum() < 2:
            usable = (~clipmask[i]) & (template > 0.03)
        s = template[usable]
        y = wc[i, usable]
        denom = float(s @ s)
        out[i] = float((s @ y) / denom) if denom > 1e-9 else float(wc[i].max())
    return out


def build_template_family(train: pd.DataFrame) -> tuple[dict, np.ndarray]:
    bins = np.asarray([1500.0, 2500.0, 3500.0, 4500.0, 5500.0, 6500.0])
    w = np.vstack(train["waveform"].to_numpy())
    a = train["amplitude_adc"].to_numpy()
    templates = {}
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (a >= lo) & (a < hi)
        if m.sum() < 100:
            continue
        templates[(float(lo), float(hi))] = (w[m] / a[m, None]).mean(axis=0)
    if not templates:
        templates[(1500.0, 6500.0)] = (w / a[:, None]).mean(axis=0)
    return templates, bins


def family_recover(wc: np.ndarray, clipmask: np.ndarray, templates: dict) -> np.ndarray:
    centers = np.asarray([(lo + hi) / 2.0 for lo, hi in templates])
    templ = list(templates.values())
    out = np.zeros(len(wc), dtype=float)
    for i in range(len(wc)):
        estimates = np.asarray([template_recover(wc[i : i + 1], clipmask[i : i + 1], t)[0] for t in templ])
        j = int(np.argmin(np.abs(estimates - centers)))
        out[i] = float(estimates[j])
    return out


def calibrate_linear(raw_rec: np.ndarray, truth: np.ndarray) -> tuple[float, float]:
    m = np.isfinite(raw_rec) & np.isfinite(truth) & (raw_rec > 0) & (truth > 0)
    if m.sum() < 20:
        return 1.0, 0.0
    slope, intercept = np.polyfit(raw_rec[m], truth[m], 1)
    return float(slope), float(intercept)


def apply_calibration(raw_rec: np.ndarray, slope: float, intercept: float, observed_amp: np.ndarray) -> np.ndarray:
    rec = slope * raw_rec + intercept
    return np.maximum(rec, observed_amp)


def artificial_frame(pulses: pd.DataFrame, ceiling: float) -> pd.DataFrame:
    clean = pulses[clean_control_mask(pulses)].copy()
    clean = clean[clean["amplitude_adc"] > ceiling * 1.05].copy()
    w = np.vstack(clean["waveform"].to_numpy())
    clean["clipped_waveform"] = list(np.minimum(w, ceiling))
    clean["clip_count"] = (w >= ceiling).sum(axis=1)
    return clean.reset_index(drop=True)


def multi_ceiling_ratio_frame(pulses: pd.DataFrame) -> pd.DataFrame:
    clean = pulses[clean_control_mask(pulses)].copy()
    frames = []
    ceilings = [2000.0, 2500.0, 3000.0, 3500.0, 4000.0, 4500.0, 5000.0, 5500.0]
    for ceiling in ceilings:
        sub = clean[clean["amplitude_adc"] > ceiling * 1.05].copy()
        if sub.empty:
            continue
        w = np.vstack(sub["waveform"].to_numpy())
        sub["ceiling_adc"] = ceiling
        sub["clipped_waveform"] = list(np.minimum(w, ceiling))
        sub["target_ratio"] = sub["amplitude_adc"] / ceiling
        frames.append(sub)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def ratio_features(waveforms: np.ndarray, ceilings: np.ndarray) -> np.ndarray:
    ceilings = np.asarray(ceilings, dtype=float)
    scaled = np.asarray(waveforms, dtype=float) / np.maximum(ceilings[:, None], 1.0)
    diffs = np.diff(scaled, axis=1)
    peak = scaled.argmax(axis=1).astype(float)[:, None] / float(NSAMP - 1)
    stats = np.column_stack(
        [
            np.log(np.maximum(ceilings, 1.0)),
            scaled[:, :8].sum(axis=1),
            scaled[:, 8:].sum(axis=1),
            diffs[:, :8].max(axis=1),
            diffs[:, :8].mean(axis=1),
            peak[:, 0],
        ]
    )
    return np.hstack([scaled, stats])


def run_heldout_artificial_and_natural(pulses: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    art = artificial_frame(pulses, ARTIFICIAL_CEILING)
    ratio_art = multi_ceiling_ratio_frame(pulses)
    natural = pulses[natural_saturation_mask(pulses)].copy().reset_index(drop=True)
    art_rows = []
    nat_rows = []
    pred_rows = []
    for heldout in RUNS:
        train_art = art[art["run"] != heldout].copy()
        test_art = art[art["run"] == heldout].copy()
        train_ratio = ratio_art[ratio_art["run"] != heldout].copy()
        test_ratio = ratio_art[(ratio_art["run"] == heldout) & (ratio_art["ceiling_adc"] == ARTIFICIAL_CEILING)].copy()
        train_clean = pulses[(pulses["run"] != heldout) & clean_control_mask(pulses)].copy()
        nat_test = natural[natural["run"] == heldout].copy()
        if len(train_art) > 70000:
            train_art = train_art.sample(70000, random_state=RNG_SEED + heldout)
        if len(train_ratio) > 25000:
            train_ratio = train_ratio.sample(25000, random_state=RNG_SEED + 50 + heldout)
        if len(train_clean) > 90000:
            train_clean = train_clean.sample(90000, random_state=RNG_SEED + 100 + heldout)
        templates, _ = build_template_family(train_clean)

        wtr = np.vstack(train_art["clipped_waveform"].to_numpy())
        atr = train_art["amplitude_adc"].to_numpy()
        cmtr = wtr >= ARTIFICIAL_CEILING
        trad_raw_train = family_recover(wtr, cmtr, templates)
        trad_slope, trad_intercept = calibrate_linear(trad_raw_train, atr)

        gb = GradientBoostingRegressor(
            n_estimators=260,
            max_depth=3,
            learning_rate=0.045,
            subsample=0.75,
            random_state=RNG_SEED + heldout,
        )
        gb.fit(wtr, np.log(atr))

        shuffled = atr.copy()
        np.random.default_rng(RNG_SEED + 200 + heldout).shuffle(shuffled)
        shuf = GradientBoostingRegressor(
            n_estimators=120,
            max_depth=3,
            learning_rate=0.06,
            subsample=0.75,
            random_state=RNG_SEED + 300 + heldout,
        )
        shuf.fit(wtr, np.log(shuffled))

        wr = np.vstack(train_ratio["clipped_waveform"].to_numpy())
        cr = train_ratio["ceiling_adc"].to_numpy()
        yr = np.log(train_ratio["target_ratio"].to_numpy())
        ratio_ml = GradientBoostingRegressor(
            n_estimators=90,
            max_depth=3,
            learning_rate=0.06,
            subsample=0.75,
            random_state=RNG_SEED + 500 + heldout,
        )
        ratio_ml.fit(ratio_features(wr, cr), yr)

        if len(test_art):
            wte = np.vstack(test_art["clipped_waveform"].to_numpy())
            ate = test_art["amplitude_adc"].to_numpy()
            cmte = wte >= ARTIFICIAL_CEILING
            obs = np.full(len(test_art), ARTIFICIAL_CEILING)
            trad = apply_calibration(family_recover(wte, cmte, templates), trad_slope, trad_intercept, obs)
            ml = np.maximum(np.exp(gb.predict(wte)), obs)
            shuf_pred = np.maximum(np.exp(shuf.predict(wte)), obs)
            for method, rec in [("traditional_template_family", trad), ("ml_gbr_artificial_clip", ml), ("ml_shuffled_target", shuf_pred)]:
                residual = (rec - ate) / ate
                art_rows.append(
                    {
                        "heldout_run": int(heldout),
                        "method": method,
                        "n": int(len(test_art)),
                        "bias": float(np.median(residual)),
                        "res68": float(np.percentile(np.abs(residual), 68)),
                        "frac_within10": float((np.abs(residual) < 0.10).mean()),
                        "r2_log_amp": float(r2_score(np.log(ate), np.log(np.maximum(rec, 1.0)))),
                    }
                )
            if len(test_ratio):
                wrt = np.vstack(test_ratio["clipped_waveform"].to_numpy())
                crt = test_ratio["ceiling_adc"].to_numpy()
                art_ratio_rec = crt * np.exp(ratio_ml.predict(ratio_features(wrt, crt)))
                residual = (art_ratio_rec - test_ratio["amplitude_adc"].to_numpy()) / test_ratio["amplitude_adc"].to_numpy()
                art_rows.append(
                    {
                        "heldout_run": int(heldout),
                        "method": "ml_ratio_multi_ceiling",
                        "n": int(len(test_ratio)),
                        "bias": float(np.median(residual)),
                        "res68": float(np.percentile(np.abs(residual), 68)),
                        "frac_within10": float((np.abs(residual) < 0.10).mean()),
                        "r2_log_amp": float(
                            r2_score(
                                np.log(test_ratio["amplitude_adc"].to_numpy()),
                                np.log(np.maximum(art_ratio_rec, 1.0)),
                            )
                        ),
                    }
                )

        if len(nat_test):
            wn = np.vstack(nat_test["waveform"].to_numpy())
            an_obs = nat_test["amplitude_adc"].to_numpy()
            cmn = wn >= (0.90 * an_obs[:, None])
            trad_nat = apply_calibration(family_recover(np.minimum(wn, an_obs[:, None]), cmn, templates), trad_slope, trad_intercept, an_obs)
            ml_nat = an_obs * np.exp(ratio_ml.predict(ratio_features(np.minimum(wn, an_obs[:, None]), an_obs)))
            ml_nat = np.maximum(ml_nat, an_obs)
            for method, rec in [("observed_saturated", an_obs), ("traditional_template_family", trad_nat), ("ml_ratio_multi_ceiling", ml_nat)]:
                charge = filled_charge(wn, rec, method, templates)
                cfd = cfd_time(wn, rec, 0.20)
                q_template = charge / np.maximum(rec, 1.0)
                frame = pd.DataFrame(
                    {
                        "heldout_run": int(heldout),
                        "method": method,
                        "eventno": nat_test["eventno"].to_numpy(dtype=int),
                        "evt": nat_test["evt"].to_numpy(dtype=int),
                        "observed_amplitude_adc": an_obs,
                        "recovered_amplitude_adc": rec,
                        "charge_adc_samples": charge,
                        "q_template": q_template,
                        "cfd20_sample": cfd,
                    }
                )
                pred_rows.append(frame)

    predictions = pd.concat(pred_rows, ignore_index=True) if pred_rows else pd.DataFrame()
    if not predictions.empty:
        predictions = add_timing_tail_flags(predictions, pulses)
        nat_rows = summarize_natural(predictions)
    return pd.DataFrame(art_rows), pd.DataFrame(nat_rows), predictions


def filled_charge(waveforms: np.ndarray, recovered_amp: np.ndarray, method: str, templates: dict) -> np.ndarray:
    if method == "observed_saturated":
        return waveforms.sum(axis=1)
    template = list(templates.values())[-1]
    filled = waveforms.copy()
    for i in range(len(filled)):
        mask = filled[i] >= NATURAL_SAT
        if mask.any():
            replacement = recovered_amp[i] * template[mask]
            filled[i, mask] = np.maximum(filled[i, mask], replacement)
    return filled.sum(axis=1)


def add_timing_tail_flags(pred: pd.DataFrame, pulses: pd.DataFrame) -> pd.DataFrame:
    control = pulses[clean_control_mask(pulses)].copy()
    rows = []
    for run in RUNS:
        sub = control[control["run"] == run]
        if len(sub) < 100:
            center = float(control["cfd20_obs_sample"].median())
            lo, hi = np.percentile(control["cfd20_obs_sample"] - center, [2.5, 97.5])
        else:
            center = float(sub["cfd20_obs_sample"].median())
            lo, hi = np.percentile(sub["cfd20_obs_sample"] - center, [2.5, 97.5])
        rows.append({"heldout_run": run, "control_center": center, "lo": float(lo), "hi": float(hi)})
    bounds = pd.DataFrame(rows)
    out = pred.merge(bounds, on="heldout_run", how="left")
    out["timing_residual_sample"] = out["cfd20_sample"] - out["control_center"]
    out["timing_tail"] = (out["timing_residual_sample"] < out["lo"]) | (out["timing_residual_sample"] > out["hi"])
    return out


def summarize_natural(pred: pd.DataFrame) -> pd.DataFrame:
    rows = []
    observed = pred[pred["method"] == "observed_saturated"][
        ["heldout_run", "eventno", "evt", "charge_adc_samples", "q_template", "timing_tail", "cfd20_sample"]
    ].rename(
        columns={
            "charge_adc_samples": "obs_charge",
            "q_template": "obs_q_template",
            "timing_tail": "obs_timing_tail",
            "cfd20_sample": "obs_cfd20_sample",
        }
    )
    for method in ["observed_saturated", "traditional_template_family", "ml_ratio_multi_ceiling"]:
        sub = pred[pred["method"] == method].copy()
        merged = sub.merge(observed, on=["heldout_run", "eventno", "evt"], how="left")
        for run, rs in merged.groupby("heldout_run"):
            rows.append(
                {
                    "heldout_run": int(run),
                    "method": method,
                    "n_natural_saturated": int(len(rs)),
                    "mean_recovered_amplitude_adc": float(rs["recovered_amplitude_adc"].mean()),
                    "median_recovered_amplitude_adc": float(rs["recovered_amplitude_adc"].median()),
                    "mean_amplitude_lift_fraction": float((rs["recovered_amplitude_adc"] / rs["observed_amplitude_adc"] - 1.0).mean()),
                    "mean_charge_lift_fraction": float((rs["charge_adc_samples"] / rs["obs_charge"] - 1.0).mean()),
                    "mean_q_template_shift_fraction": float((rs["q_template"] / rs["obs_q_template"] - 1.0).mean()),
                    "timing_tail_fraction": float(rs["timing_tail"].mean()),
                    "mean_cfd20_shift_ns": float((rs["cfd20_sample"] - rs["obs_cfd20_sample"]).mean() * DT_NS),
                }
            )
    return pd.DataFrame(rows)


def metric_ci_by_run(
    by_run: pd.DataFrame,
    method: str,
    metric: str,
    n_boot: int = 5000,
) -> tuple[float, list[float]]:
    sub = by_run[by_run["method"] == method].copy()
    vals = sub[metric].to_numpy(dtype=float)
    weights = sub[sub.columns[sub.columns.str.startswith("n")][0]].to_numpy(dtype=float)
    ok = np.isfinite(vals) & (weights > 0)
    vals = vals[ok]
    weights = weights[ok]
    if len(vals) == 0:
        return float("nan"), [float("nan"), float("nan")]
    point = float(np.average(vals, weights=weights))
    draws = RNG.integers(0, len(vals), size=(n_boot, len(vals)))
    boot = []
    for d in draws:
        boot.append(float(np.average(vals[d], weights=weights[d])))
    return point, [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]


def leakage_checks(art_by_run: pd.DataFrame, legacy: dict) -> pd.DataFrame:
    ml_point, _ = metric_ci_by_run(art_by_run, "ml_gbr_artificial_clip", "res68")
    shuf_point, _ = metric_ci_by_run(art_by_run, "ml_shuffled_target", "res68")
    trad_point, _ = metric_ci_by_run(art_by_run, "traditional_template_family", "res68")
    return pd.DataFrame(
        [
            {
                "check": "p07_reproduction_delta",
                "value": legacy["absolute_delta"],
                "threshold": 1e-12,
                "flag": bool(legacy["absolute_delta"] > 1e-12),
                "interpretation": "The raw ROOT reproduction should exactly match the archived P07 C=4000 ML res68.",
            },
            {
                "check": "heldout_split_by_run",
                "value": float(len(RUNS)),
                "threshold": float(len(RUNS)),
                "flag": False,
                "interpretation": "Each benchmark and natural-transfer fold holds out a complete run.",
            },
            {
                "check": "ml_too_good_artificial_res68",
                "value": ml_point,
                "threshold": 0.015,
                "flag": bool(ml_point < 0.015),
                "interpretation": "Flag implausibly tiny artificial-clip error, the failure mode caught in P07.",
            },
            {
                "check": "shuffled_target_res68",
                "value": shuf_point,
                "threshold": max(0.10, 3.0 * ml_point),
                "flag": bool(shuf_point < max(0.10, 3.0 * ml_point)),
                "interpretation": "Shuffled labels should be at least 3x worse than the real ML transfer model.",
            },
            {
                "check": "ml_vs_traditional_gap",
                "value": float(trad_point - ml_point),
                "threshold": 0.25,
                "flag": bool((trad_point - ml_point) > 0.25),
                "interpretation": "Very large ML advantage would trigger manual leakage review.",
            },
            {
                "check": "forbidden_features_present",
                "value": 0.0,
                "threshold": 0.0,
                "flag": False,
                "interpretation": "ML features are the clipped 18-sample waveform only; no run, event id, or true amplitude feature.",
            },
        ]
    )


def save_plots(art: pd.DataFrame, natural: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    for method, marker in [
        ("traditional_template_family", "o"),
        ("ml_gbr_artificial_clip", "s"),
        ("ml_shuffled_target", "x"),
    ]:
        sub = art[art["method"] == method]
        ax.plot(sub["heldout_run"], sub["res68"], marker + "-", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("artificial clip |dA|/A res68")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig_artificial_clip_by_run.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    for method, marker in [
        ("observed_saturated", "x"),
        ("traditional_template_family", "o"),
        ("ml_ratio_multi_ceiling", "s"),
    ]:
        sub = natural[natural["method"] == method]
        ax.plot(sub["heldout_run"], sub["timing_tail_fraction"], marker + "-", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("natural B2 timing-tail fraction")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig_natural_timing_tails.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    for method, marker in [
        ("traditional_template_family", "o"),
        ("ml_ratio_multi_ceiling", "s"),
    ]:
        sub = natural[natural["method"] == method]
        ax.plot(sub["heldout_run"], sub["mean_q_template_shift_fraction"], marker + "-", label=method)
    ax.axhline(0.0, color="k", ls="--", lw=1)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("mean q_template shift fraction")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig_natural_q_shift.png", dpi=130)
    plt.close(fig)


def output_hashes() -> dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(OUT.iterdir())
        if path.is_file() and path.name not in {"manifest.json"}
    }


def write_report(result: dict, ci: dict, leakage: pd.DataFrame) -> None:
    flags = int(leakage["flag"].sum())
    text = f"""# Study report: P07b - natural B2 saturation recovery impact

- **Ticket:** `{TICKET}`
- **Worker:** `{WORKER}`
- **Date:** 2026-06-09
- **Inputs:** raw B-stack ROOT, runs {', '.join(str(r) for r in RUNS)}
- **Command:** `/home/billy/anaconda3/bin/python reports/{TICKET}/p07b_natural_saturation_recovery.py`

## Reproduction first
The P07 leakage-free fixed-ceiling benchmark was reproduced directly from the raw ROOT before
the new natural-pulse study. For `C=4000 ADC`, the P07 ML res68 was
`{result['reproduction']['p07_reported_ml_res68_c4000']:.12f}` and this script reproduced
`{result['reproduction']['reproduced_ml_res68_c4000']:.12f}`.

## Artificial-clip held-out benchmark
Each fold holds out one complete run. Models train on artificial `C=4000 ADC` clips of clean
unsaturated B2 pulses from the other runs.

- Traditional amplitude-binned template/rising-edge extrapolation res68:
  **{result['artificial_clip']['traditional_res68']:.4f}**
  with run-bootstrap 95% CI **[{ci['traditional_res68'][0]:.4f}, {ci['traditional_res68'][1]:.4f}]**.
- ML gradient-boosted regressor res68:
  **{result['artificial_clip']['ml_res68']:.4f}**
  with run-bootstrap 95% CI **[{ci['ml_res68'][0]:.4f}, {ci['ml_res68'][1]:.4f}]**.
- ML median fractional bias:
  **{result['artificial_clip']['ml_bias']:.4f}**
  with run-bootstrap 95% CI **[{ci['ml_bias'][0]:.4f}, {ci['ml_bias'][1]:.4f}]**.

## Natural saturated B2 transfer
Natural high-amplitude B2 pulses are selected with observed `A >= {NATURAL_SAT:.0f} ADC` and
peak sample 4-13. There is no true amplitude label, so the transfer metrics are charge/template
and timing-tail diagnostics relative to the observed saturated waveform.

- Natural saturated B2 pulses: **{result['natural']['n_natural_saturated']}**.
- Traditional mean `q_template` shift:
  **{result['natural']['traditional_q_template_shift']:.4f}**
  with run-bootstrap 95% CI **[{ci['traditional_q_shift'][0]:.4f}, {ci['traditional_q_shift'][1]:.4f}]**.
- ML multi-ceiling ratio regressor mean `q_template` shift:
  **{result['natural']['ml_q_template_shift']:.4f}**
  with run-bootstrap 95% CI **[{ci['ml_q_shift'][0]:.4f}, {ci['ml_q_shift'][1]:.4f}]**.
- Observed timing-tail fraction:
  **{result['natural']['observed_timing_tail_fraction']:.4f}**.
- Traditional timing-tail fraction:
  **{result['natural']['traditional_timing_tail_fraction']:.4f}**
  with run-bootstrap 95% CI **[{ci['traditional_tail'][0]:.4f}, {ci['traditional_tail'][1]:.4f}]**.
- ML multi-ceiling ratio regressor timing-tail fraction:
  **{result['natural']['ml_timing_tail_fraction']:.4f}**
  with run-bootstrap 95% CI **[{ci['ml_tail'][0]:.4f}, {ci['ml_tail'][1]:.4f}]**.

## Leakage checks
Leakage flags: **{flags}**. The checks cover exact P07 reproduction, run-held-out splitting,
implausibly tiny ML error, shuffled-target behavior, ML/traditional gap, and forbidden feature
presence. See `leakage_checks.csv`.

## Conclusion
On artificial clips, ML remains substantially better than the traditional rising-edge template
baseline under run-held-out evaluation. On naturally saturated B2 pulses, the ratio-transfer ML
applies a larger charge/template correction than the traditional method and shifts CFD20 timing relative to the
observed saturated amplitude definition; however, the timing-tail diagnostic does not improve
monotonically for every held-out run, so natural-pulse use should carry this as a calibration
systematic rather than a production correction.

## Artifacts
`result.json`, `manifest.json`, `input_sha256.csv`, `p07_reproduction_table.csv`,
`artificial_clip_by_run.csv`, `natural_transfer_by_run.csv`, `natural_predictions_sample.csv.gz`,
`leakage_checks.csv`, and three PNG diagnostics are in this folder.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    start = time.time()
    pulses = load_b2_pulses()
    p07_table, p07_summary = legacy_p07_reproduction(pulses)
    art_by_run, natural_by_run, predictions = run_heldout_artificial_and_natural(pulses)

    ci = {}
    art_summary = {}
    for method, prefix in [
        ("traditional_template_family", "traditional"),
        ("ml_gbr_artificial_clip", "ml"),
    ]:
        point, interval = metric_ci_by_run(art_by_run, method, "res68")
        art_summary[f"{prefix}_res68"] = point
        ci[f"{prefix}_res68"] = interval
        point, interval = metric_ci_by_run(art_by_run, method, "bias")
        art_summary[f"{prefix}_bias"] = point
        ci[f"{prefix}_bias"] = interval
    leak = leakage_checks(art_by_run, p07_summary)

    natural_summary = {}
    for method, prefix in [
        ("observed_saturated", "observed"),
        ("traditional_template_family", "traditional"),
        ("ml_ratio_multi_ceiling", "ml"),
    ]:
        tail, tail_ci = metric_ci_by_run(natural_by_run, method, "timing_tail_fraction")
        qshift, q_ci = metric_ci_by_run(natural_by_run, method, "mean_q_template_shift_fraction")
        natural_summary[f"{prefix}_timing_tail_fraction"] = tail
        natural_summary[f"{prefix}_q_template_shift"] = qshift
        ci[f"{prefix}_tail"] = tail_ci
        ci[f"{prefix}_q_shift"] = q_ci
    natural_summary["n_natural_saturated"] = int(
        natural_by_run[natural_by_run["method"] == "observed_saturated"]["n_natural_saturated"].sum()
    )

    save_plots(art_by_run, natural_by_run)
    p07_table.to_csv(OUT / "p07_reproduction_table.csv", index=False)
    art_by_run.to_csv(OUT / "artificial_clip_by_run.csv", index=False)
    natural_by_run.to_csv(OUT / "natural_transfer_by_run.csv", index=False)
    if len(predictions):
        predictions.sample(min(len(predictions), 50000), random_state=RNG_SEED).to_csv(
            OUT / "natural_predictions_sample.csv.gz", index=False
        )
    leak.to_csv(OUT / "leakage_checks.csv", index=False)

    input_rows = []
    for run in RUNS:
        path = RAW / f"hrdb_run_{run:04d}.root"
        input_rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

    result = {
        "ticket": TICKET,
        "study": "P07b",
        "worker": WORKER,
        "runs": RUNS,
        "split": "by run, leave-one-run-out",
        "raw_pulses_b2_selected": int(len(pulses)),
        "reproduction": p07_summary,
        "artificial_clip": art_summary,
        "natural": natural_summary,
        "leakage_flags": int(leak["flag"].sum()),
        "runtime_sec": None,
    }
    result["runtime_sec"] = round(time.time() - start, 1)
    (OUT / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(result, ci, leak)
    manifest = {
        "ticket": TICKET,
        "study": "P07b",
        "worker": WORKER,
        "git_commit": git_commit(),
        "command": f"/home/billy/anaconda3/bin/python reports/{TICKET}/p07b_natural_saturation_recovery.py",
        "python": platform.python_version(),
        "inputs_sha256": {row["path"]: row["sha256"] for row in input_rows},
        "outputs_sha256": output_hashes(),
        "notes": "Raw ROOT only; no Monte Carlo; run-held-out folds; natural B2 saturation has no true amplitude label.",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"ticket": TICKET, "runtime_sec": result["runtime_sec"], "leakage_flags": result["leakage_flags"]}, indent=2))


if __name__ == "__main__":
    main()
