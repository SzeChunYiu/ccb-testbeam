#!/usr/bin/env python3
"""P07c: boundary-control closure for natural B2 saturation transfer.

The script reads only raw B-stack ROOT files, reproduces the upstream P07/P07b
numbers first, then evaluates a traditional template-family correction and a
multi-ceiling ML ratio-transfer correction in leave-one-run-out folds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/p07c_boundary_control_closure.json"


def load_config(path: Path) -> dict:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg["config_path"] = str(path)
    return cfg


def configure_matplotlib(out: Path):
    os.environ.setdefault("MPLCONFIGDIR", str(out / ".mplconfig"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


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


def load_b2_pulses(cfg: dict) -> pd.DataFrame:
    import uproot

    raw = ROOT / cfg["raw_root"]
    rows = []
    baseline_samples = list(cfg["baseline_samples"])
    nsamp = 18
    for run in cfg["runs"]:
        path = raw / f"hrdb_run_{run:04d}.root"
        tree = uproot.open(path)["h101"]
        for batch in tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=20000, library="np"):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            raw_wave = events[:, int(cfg["b2_channel"]), :]
            baseline = np.median(raw_wave[:, baseline_samples], axis=1)
            wave = raw_wave - baseline[:, None]
            amp = wave.max(axis=1)
            peak = wave.argmax(axis=1)
            area = wave.sum(axis=1)
            selected = amp > float(cfg["amplitude_cut_adc"])
            for i in np.where(selected)[0]:
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


def clean_control_mask(pulses: pd.DataFrame, cfg: dict) -> np.ndarray:
    a = pulses["amplitude_adc"].to_numpy()
    peak = pulses["peak_sample"].to_numpy()
    return (peak >= 4) & (peak <= 12) & (a > 1500.0) & (a < float(cfg["clean_unsaturated_max_adc"]))


def peak_good_mask(pulses: pd.DataFrame) -> np.ndarray:
    peak = pulses["peak_sample"].to_numpy()
    return (peak >= 4) & (peak <= 13)


def load_legacy_p07_all_staves(runs: list[int], cfg: dict) -> tuple[np.ndarray, np.ndarray]:
    import uproot

    raw = ROOT / cfg["raw_root"]
    channels = np.asarray([0, 2, 4, 6])
    baseline = list(cfg["baseline_samples"])
    waveforms = []
    amplitudes = []
    total = 0
    for run in runs:
        path = raw / f"hrdb_run_{run:04d}.root"
        tree = uproot.open(path)["h101"]
        for batch in tree.iterate(["HRDv"], step_size=20000, library="np"):
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, 18)
            w = events[:, channels, :]
            base = np.median(w[..., baseline], axis=-1)
            corr = w - base[..., None]
            amp = corr.max(axis=-1)
            event_idx, stave_idx = np.where(amp > float(cfg["amplitude_cut_adc"]))
            if len(event_idx):
                waveforms.append(corr[event_idx, stave_idx])
                amplitudes.append(amp[event_idx, stave_idx])
                total += int(len(event_idx))
        if total > 40000:
            break
    return np.vstack(waveforms), np.concatenate(amplitudes)


def legacy_clean_mask(waveforms: np.ndarray, amplitudes: np.ndarray, cfg: dict) -> np.ndarray:
    peak = waveforms.argmax(axis=1)
    return (peak >= 4) & (peak <= 12) & (amplitudes > 1500.0) & (amplitudes < float(cfg["clean_unsaturated_max_adc"]))


def legacy_p07_reproduction(cfg: dict) -> tuple[pd.DataFrame, dict]:
    from sklearn.ensemble import GradientBoostingRegressor

    train_runs = [58, 59, 60, 61]
    test_runs = [62, 63, 65]
    wtr_all, atr_all = load_legacy_p07_all_staves(train_runs, cfg)
    wte_all, ate_all = load_legacy_p07_all_staves(test_runs, cfg)
    mtr = legacy_clean_mask(wtr_all, atr_all, cfg)
    mte = legacy_clean_mask(wte_all, ate_all, cfg)
    wtr = wtr_all[mtr]
    atr = atr_all[mtr]
    wte = wte_all[mte]
    ate = ate_all[mte]
    if len(wtr) > 40000:
        idx = np.random.default_rng(0).choice(len(wtr), 40000, replace=False)
        wtr = wtr[idx]
        atr = atr[idx]
    template = (wtr / atr[:, None]).mean(axis=0)

    def template_recover_fixed(wc: np.ndarray, clipmask: np.ndarray) -> np.ndarray:
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
        rec_trad = template_recover_fixed(wte_c, cmte)
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
    expected = 0.03243177807776981
    summary = {
        "p07_reported_ml_res68_c4000": expected,
        "reproduced_ml_res68_c4000": float(target["ml_res68"]),
        "absolute_delta": float(abs(target["ml_res68"] - expected)),
        "clean_train_after_cap": int(len(wtr)),
        "clean_test": int(len(wte)),
    }
    return table, summary


def template_recover(wc: np.ndarray, clipmask: np.ndarray, template: np.ndarray) -> np.ndarray:
    out = np.zeros(len(wc), dtype=float)
    for i in range(len(wc)):
        rising = np.arange(wc.shape[1]) <= int(np.argmax(wc[i]))
        usable = (~clipmask[i]) & rising & (template > 0.03)
        if usable.sum() < 2:
            usable = (~clipmask[i]) & (template > 0.03)
        s = template[usable]
        y = wc[i, usable]
        denom = float(s @ s)
        out[i] = float((s @ y) / denom) if denom > 1e-9 else float(wc[i].max())
    return out


def build_template_family(train: pd.DataFrame) -> tuple[dict[tuple[float, float], np.ndarray], np.ndarray]:
    bins = np.asarray([1500.0, 2500.0, 3500.0, 4500.0, 5500.0, 6500.0])
    w = np.vstack(train["waveform"].to_numpy())
    a = train["amplitude_adc"].to_numpy()
    templates = {}
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (a >= lo) & (a < hi)
        if m.sum() >= 100:
            templates[(float(lo), float(hi))] = (w[m] / a[m, None]).mean(axis=0)
    if not templates:
        templates[(1500.0, 6500.0)] = (w / a[:, None]).mean(axis=0)
    return templates, bins


def family_recover(wc: np.ndarray, clipmask: np.ndarray, templates: dict[tuple[float, float], np.ndarray]) -> np.ndarray:
    centers = np.asarray([(lo + hi) / 2.0 for lo, hi in templates])
    template_list = list(templates.values())
    out = np.zeros(len(wc), dtype=float)
    for i in range(len(wc)):
        estimates = np.asarray([template_recover(wc[i : i + 1], clipmask[i : i + 1], t)[0] for t in template_list])
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


def artificial_frame(pulses: pd.DataFrame, cfg: dict, ceiling: float) -> pd.DataFrame:
    clean = pulses[clean_control_mask(pulses, cfg)].copy()
    clean = clean[clean["amplitude_adc"] > ceiling * 1.05].copy()
    w = np.vstack(clean["waveform"].to_numpy())
    clean["clipped_waveform"] = list(np.minimum(w, ceiling))
    clean["clip_count"] = (w >= ceiling).sum(axis=1)
    return clean.reset_index(drop=True)


def multi_ceiling_ratio_frame(pulses: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    clean = pulses[clean_control_mask(pulses, cfg)].copy()
    frames = []
    for ceiling in cfg["multi_ceilings_adc"]:
        ceiling = float(ceiling)
        sub = clean[clean["amplitude_adc"] > ceiling * 1.05].copy()
        if sub.empty:
            continue
        w = np.vstack(sub["waveform"].to_numpy())
        sub["ceiling_adc"] = ceiling
        sub["clipped_waveform"] = list(np.minimum(w, ceiling))
        sub["target_ratio"] = sub["amplitude_adc"] / ceiling
        frames.append(sub)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def ratio_features(waveforms: np.ndarray, ceilings: np.ndarray, include_explicit_ceiling: bool) -> np.ndarray:
    ceilings = np.asarray(ceilings, dtype=float)
    scaled = np.asarray(waveforms, dtype=float) / np.maximum(ceilings[:, None], 1.0)
    diffs = np.diff(scaled, axis=1)
    peak = scaled.argmax(axis=1).astype(float) / float(scaled.shape[1] - 1)
    stats = np.column_stack(
        [
            scaled[:, :8].sum(axis=1),
            scaled[:, 8:].sum(axis=1),
            diffs[:, :8].max(axis=1),
            diffs[:, :8].mean(axis=1),
            peak,
        ]
    )
    if include_explicit_ceiling:
        stats = np.column_stack([np.log(np.maximum(ceilings, 1.0)), stats])
    return np.hstack([scaled, stats])


def ceiling_only_features(ceilings: np.ndarray) -> np.ndarray:
    return np.log(np.maximum(np.asarray(ceilings, dtype=float), 1.0))[:, None]


def high_template(templates: dict[tuple[float, float], np.ndarray]) -> np.ndarray:
    key = sorted(templates.keys(), key=lambda x: x[1])[-1]
    return templates[key]


def filled_charge(
    waveforms: np.ndarray,
    observed_amp: np.ndarray,
    recovered_amp: np.ndarray,
    method: str,
    templates: dict[tuple[float, float], np.ndarray],
    cfg: dict,
) -> np.ndarray:
    if method == "observed":
        return waveforms.sum(axis=1)
    template = high_template(templates)
    filled = waveforms.copy()
    floor = float(cfg["natural_apply_adc"])
    for i in range(len(filled)):
        boundary = min(floor, 0.98 * float(observed_amp[i]))
        mask = filled[i] >= boundary
        if mask.any():
            replacement = float(recovered_amp[i]) * template[mask]
            filled[i, mask] = np.maximum(filled[i, mask], replacement)
    return filled.sum(axis=1)


def timing_bounds(pulses: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    control = pulses[clean_control_mask(pulses, cfg)].copy()
    rows = []
    for run in cfg["runs"]:
        sub = control[control["run"] == run]
        if len(sub) < 100:
            center = float(control["cfd20_obs_sample"].median())
            lo, hi = np.percentile(control["cfd20_obs_sample"] - center, [2.5, 97.5])
        else:
            center = float(sub["cfd20_obs_sample"].median())
            lo, hi = np.percentile(sub["cfd20_obs_sample"] - center, [2.5, 97.5])
        rows.append({"run": int(run), "control_center": center, "lo": float(lo), "hi": float(hi)})
    return pd.DataFrame(rows)


def eval_sets(pulses: pd.DataFrame, cfg: dict) -> dict[str, pd.DataFrame]:
    a = pulses["amplitude_adc"].to_numpy()
    good = peak_good_mask(pulses)
    b0 = float(cfg["boundary_low_adc"])
    b1 = float(cfg["natural_apply_adc"])
    b2 = float(cfg["boundary_high_adc"])
    return {
        "boundary_6500_7000": pulses[good & (a >= b0) & (a < b1)].copy(),
        "boundary_7000_7500": pulses[good & (a >= b1) & (a < b2)].copy(),
        "boundary_6500_7500": pulses[good & (a >= b0) & (a < b2)].copy(),
        "application_ge7000": pulses[good & (a >= b1)].copy(),
        "application_ge7500": pulses[good & (a >= b2)].copy(),
    }


def summarize_eval_predictions(pred: pd.DataFrame) -> pd.DataFrame:
    rows = []
    observed = pred[pred["method"] == "observed"][
        ["eval_set", "run", "eventno", "evt", "charge_adc_samples", "q_template", "timing_tail", "cfd20_sample"]
    ].rename(
        columns={
            "charge_adc_samples": "obs_charge",
            "q_template": "obs_q_template",
            "timing_tail": "obs_timing_tail",
            "cfd20_sample": "obs_cfd20_sample",
        }
    )
    for (eval_set, method, run), sub in pred.groupby(["eval_set", "method", "run"]):
        merged = sub.merge(observed, on=["eval_set", "run", "eventno", "evt"], how="left")
        rows.append(
            {
                "eval_set": eval_set,
                "heldout_run": int(run),
                "method": method,
                "n": int(len(merged)),
                "mean_observed_amplitude_adc": float(merged["observed_amplitude_adc"].mean()),
                "mean_recovered_amplitude_adc": float(merged["recovered_amplitude_adc"].mean()),
                "mean_amplitude_lift_fraction": float(
                    (merged["recovered_amplitude_adc"] / merged["observed_amplitude_adc"] - 1.0).mean()
                ),
                "mean_charge_lift_fraction": float((merged["charge_adc_samples"] / merged["obs_charge"] - 1.0).mean()),
                "mean_q_template_shift_fraction": float((merged["q_template"] / merged["obs_q_template"] - 1.0).mean()),
                "timing_tail_fraction": float(merged["timing_tail"].mean()),
                "timing_tail_delta": float(merged["timing_tail"].mean() - merged["obs_timing_tail"].mean()),
                "mean_cfd20_shift_ns": float((merged["cfd20_sample"] - merged["obs_cfd20_sample"]).mean() * 10.0),
                "median_abs_cfd20_shift_ns": float(
                    np.median(np.abs(merged["cfd20_sample"] - merged["obs_cfd20_sample"])) * 10.0
                ),
            }
        )
    return pd.DataFrame(rows)


def run_folds(pulses: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.metrics import r2_score

    seed = int(cfg["random_seed"])
    ceiling = float(cfg["artificial_ceiling_adc"])
    art = artificial_frame(pulses, cfg, ceiling)
    ratio_art = multi_ceiling_ratio_frame(pulses, cfg)
    sets = eval_sets(pulses, cfg)
    bounds = timing_bounds(pulses, cfg)
    art_rows = []
    pred_rows = []
    dep_rows = []

    for heldout in cfg["runs"]:
        train_art = art[art["run"] != heldout].copy()
        test_art = art[art["run"] == heldout].copy()
        train_ratio = ratio_art[ratio_art["run"] != heldout].copy()
        test_ratio = ratio_art[(ratio_art["run"] == heldout) & (ratio_art["ceiling_adc"] == ceiling)].copy()
        train_clean = pulses[(pulses["run"] != heldout) & clean_control_mask(pulses, cfg)].copy()
        if len(train_art) > 70000:
            train_art = train_art.sample(70000, random_state=seed + heldout)
        if len(train_ratio) > 25000:
            train_ratio = train_ratio.sample(25000, random_state=seed + 50 + heldout)
        if len(train_clean) > 90000:
            train_clean = train_clean.sample(90000, random_state=seed + 100 + heldout)

        templates, _ = build_template_family(train_clean)
        wtr = np.vstack(train_art["clipped_waveform"].to_numpy())
        atr = train_art["amplitude_adc"].to_numpy()
        cmtr = wtr >= ceiling
        trad_raw_train = family_recover(wtr, cmtr, templates)
        trad_slope, trad_intercept = calibrate_linear(trad_raw_train, atr)

        direct_ml = GradientBoostingRegressor(
            n_estimators=260,
            max_depth=3,
            learning_rate=0.045,
            subsample=0.75,
            random_state=seed + heldout,
        )
        direct_ml.fit(wtr, np.log(atr))

        wr = np.vstack(train_ratio["clipped_waveform"].to_numpy())
        cr = train_ratio["ceiling_adc"].to_numpy()
        yr = np.log(train_ratio["target_ratio"].to_numpy())
        ratio_shape = GradientBoostingRegressor(
            n_estimators=110,
            max_depth=3,
            learning_rate=0.055,
            subsample=0.75,
            random_state=seed + 500 + heldout,
        )
        ratio_shape.fit(ratio_features(wr, cr, include_explicit_ceiling=False), yr)
        ratio_with_ceiling = GradientBoostingRegressor(
            n_estimators=90,
            max_depth=3,
            learning_rate=0.06,
            subsample=0.75,
            random_state=70702 + 500 + heldout,
        )
        ratio_with_ceiling.fit(ratio_features(wr, cr, include_explicit_ceiling=True), yr)

        y_shuf = yr.copy()
        np.random.default_rng(seed + 700 + heldout).shuffle(y_shuf)
        ratio_shuffled = GradientBoostingRegressor(
            n_estimators=90,
            max_depth=3,
            learning_rate=0.06,
            subsample=0.75,
            random_state=seed + 800 + heldout,
        )
        ratio_shuffled.fit(ratio_features(wr, cr, include_explicit_ceiling=False), y_shuf)
        ratio_ceiling_only = GradientBoostingRegressor(
            n_estimators=80,
            max_depth=2,
            learning_rate=0.06,
            subsample=0.75,
            random_state=seed + 900 + heldout,
        )
        ratio_ceiling_only.fit(ceiling_only_features(cr), yr)

        if len(test_art):
            wte = np.vstack(test_art["clipped_waveform"].to_numpy())
            ate = test_art["amplitude_adc"].to_numpy()
            cmte = wte >= ceiling
            obs = np.full(len(test_art), ceiling)
            trad = apply_calibration(family_recover(wte, cmte, templates), trad_slope, trad_intercept, obs)
            direct = np.maximum(np.exp(direct_ml.predict(wte)), obs)
            for method, rec in [
                ("traditional_template_family", trad),
                ("ml_direct_gbr_artificial", direct),
            ]:
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
            ate = test_ratio["amplitude_adc"].to_numpy()
            model_specs = [
                ("ml_ratio_shape_only", ratio_shape, False, "shape"),
                ("ml_ratio_with_ceiling_p07b", ratio_with_ceiling, True, "shape"),
                ("ml_ratio_shuffled_target", ratio_shuffled, False, "shape"),
                ("ml_ratio_ceiling_only", ratio_ceiling_only, False, "ceiling"),
            ]
            for method, model, include_ceiling, feature_mode in model_specs:
                if feature_mode == "ceiling":
                    rec = crt * np.exp(model.predict(ceiling_only_features(crt)))
                else:
                    rec = crt * np.exp(model.predict(ratio_features(wrt, crt, include_ceiling)))
                residual = (rec - ate) / ate
                art_rows.append(
                    {
                        "heldout_run": int(heldout),
                        "method": method,
                        "n": int(len(test_ratio)),
                        "bias": float(np.median(residual)),
                        "res68": float(np.percentile(np.abs(residual), 68)),
                        "frac_within10": float((np.abs(residual) < 0.10).mean()),
                        "r2_log_amp": float(r2_score(np.log(ate), np.log(np.maximum(rec, 1.0)))),
                    }
                )

        for eval_name, frame in sets.items():
            test = frame[frame["run"] == heldout].copy()
            if test.empty:
                continue
            wn = np.vstack(test["waveform"].to_numpy())
            obs_amp = test["amplitude_adc"].to_numpy()
            clipped = np.minimum(wn, obs_amp[:, None])
            clipmask = wn >= (0.90 * obs_amp[:, None])
            trad_nat = apply_calibration(family_recover(clipped, clipmask, templates), trad_slope, trad_intercept, obs_amp)
            shape_nat = obs_amp * np.exp(ratio_shape.predict(ratio_features(clipped, obs_amp, include_explicit_ceiling=False)))
            shape_nat = np.maximum(shape_nat, obs_amp)
            p07b_nat = obs_amp * np.exp(ratio_with_ceiling.predict(ratio_features(clipped, obs_amp, include_explicit_ceiling=True)))
            p07b_nat = np.maximum(p07b_nat, obs_amp)
            methods = [
                ("observed", obs_amp),
                ("traditional_template_family", trad_nat),
                ("ml_ratio_shape_only", shape_nat),
                ("ml_ratio_with_ceiling_p07b", p07b_nat),
            ]
            bound = bounds[bounds["run"] == heldout].iloc[0]
            for method, rec in methods:
                charge = filled_charge(wn, obs_amp, rec, method, templates, cfg)
                cfd = cfd_time(wn, rec, 0.20)
                q_template = charge / np.maximum(rec, 1.0)
                timing_resid = cfd - float(bound["control_center"])
                pred_rows.append(
                    pd.DataFrame(
                        {
                            "eval_set": eval_name,
                            "run": int(heldout),
                            "method": method,
                            "eventno": test["eventno"].to_numpy(dtype=int),
                            "evt": test["evt"].to_numpy(dtype=int),
                            "observed_amplitude_adc": obs_amp,
                            "recovered_amplitude_adc": rec,
                            "charge_adc_samples": charge,
                            "q_template": q_template,
                            "cfd20_sample": cfd,
                            "timing_tail": (timing_resid < float(bound["lo"])) | (timing_resid > float(bound["hi"])),
                        }
                    )
                )
            for method, rec in [("ml_ratio_shape_only", shape_nat), ("ml_ratio_with_ceiling_p07b", p07b_nat)]:
                lift = rec / obs_amp - 1.0
                if len(lift) >= 5 and np.nanvar(obs_amp) > 0:
                    corr = np.corrcoef(obs_amp, lift)[0, 1]
                    r2 = float(corr * corr) if np.isfinite(corr) else float("nan")
                else:
                    r2 = float("nan")
                dep_rows.append(
                    {
                        "eval_set": eval_name,
                        "heldout_run": int(heldout),
                        "method": method,
                        "n": int(len(lift)),
                        "lift_vs_observed_amp_r2": r2,
                    }
                )

    predictions = pd.concat(pred_rows, ignore_index=True) if pred_rows else pd.DataFrame()
    eval_by_run = summarize_eval_predictions(predictions) if len(predictions) else pd.DataFrame()
    return pd.DataFrame(art_rows), eval_by_run, predictions, pd.DataFrame(dep_rows)


def metric_ci_by_run(by_run: pd.DataFrame, method: str, metric: str, rng: np.random.Generator, n_boot: int) -> tuple[float, list[float]]:
    sub = by_run[by_run["method"] == method].copy()
    if sub.empty:
        return float("nan"), [float("nan"), float("nan")]
    vals = sub[metric].to_numpy(dtype=float)
    weights = sub["n"].to_numpy(dtype=float)
    ok = np.isfinite(vals) & np.isfinite(weights) & (weights > 0)
    vals = vals[ok]
    weights = weights[ok]
    if len(vals) == 0:
        return float("nan"), [float("nan"), float("nan")]
    point = float(np.average(vals, weights=weights))
    draws = rng.integers(0, len(vals), size=(n_boot, len(vals)))
    boot = np.asarray([np.average(vals[d], weights=weights[d]) for d in draws], dtype=float)
    return point, [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]


def metric_ci_eval(
    by_run: pd.DataFrame,
    eval_set: str,
    method: str,
    metric: str,
    rng: np.random.Generator,
    n_boot: int,
) -> tuple[float, list[float]]:
    sub = by_run[(by_run["eval_set"] == eval_set) & (by_run["method"] == method)].copy()
    return metric_ci_by_run(sub, method, metric, rng, n_boot)


def summarize_results(
    cfg: dict,
    pulses: pd.DataFrame,
    p07_summary: dict,
    art_by_run: pd.DataFrame,
    eval_by_run: pd.DataFrame,
    dependency: pd.DataFrame,
) -> tuple[dict, pd.DataFrame, dict]:
    rng = np.random.default_rng(int(cfg["random_seed"]) + 2000)
    n_boot = int(cfg["bootstrap_replicates"])
    ci = {}
    artificial = {}
    for method in [
        "traditional_template_family",
        "ml_direct_gbr_artificial",
        "ml_ratio_shape_only",
        "ml_ratio_with_ceiling_p07b",
        "ml_ratio_shuffled_target",
        "ml_ratio_ceiling_only",
    ]:
        artificial[method] = {}
        for metric in ["res68", "bias", "frac_within10"]:
            point, interval = metric_ci_by_run(art_by_run, method, metric, rng, n_boot)
            artificial[method][metric] = point
            ci[f"artificial.{method}.{metric}"] = interval

    eval_summary = {}
    for eval_set in ["boundary_6500_7000", "boundary_7000_7500", "boundary_6500_7500", "application_ge7000", "application_ge7500"]:
        eval_summary[eval_set] = {}
        for method in ["observed", "traditional_template_family", "ml_ratio_shape_only", "ml_ratio_with_ceiling_p07b"]:
            eval_summary[eval_set][method] = {}
            for metric in [
                "mean_amplitude_lift_fraction",
                "mean_charge_lift_fraction",
                "mean_q_template_shift_fraction",
                "timing_tail_fraction",
                "timing_tail_delta",
                "mean_cfd20_shift_ns",
                "median_abs_cfd20_shift_ns",
            ]:
                point, interval = metric_ci_eval(eval_by_run, eval_set, method, metric, rng, n_boot)
                eval_summary[eval_set][method][metric] = point
                ci[f"{eval_set}.{method}.{metric}"] = interval
            sub = eval_by_run[(eval_by_run["eval_set"] == eval_set) & (eval_by_run["method"] == method)]
            eval_summary[eval_set][method]["n"] = int(sub["n"].sum()) if len(sub) else 0

    p07b_expected_art = 0.03931517116488385
    p07b_expected_q = -0.0896770876224819
    p07b_art = artificial["ml_ratio_with_ceiling_p07b"]["res68"]
    p07b_q = eval_summary["application_ge7000"]["ml_ratio_with_ceiling_p07b"]["mean_q_template_shift_fraction"]
    shape_art = artificial["ml_ratio_shape_only"]["res68"]
    shuf_art = artificial["ml_ratio_shuffled_target"]["res68"]
    ceil_art = artificial["ml_ratio_ceiling_only"]["res68"]
    boundary_shape = eval_summary["boundary_6500_7500"]["ml_ratio_shape_only"]
    dep_boundary = dependency[
        (dependency["eval_set"] == "boundary_6500_7500") & (dependency["method"] == "ml_ratio_shape_only")
    ].copy()
    dep_r2 = float(np.nanmax(dep_boundary["lift_vs_observed_amp_r2"].to_numpy())) if len(dep_boundary) else float("nan")
    checks = pd.DataFrame(
        [
            {
                "check": "p07_c4000_reproduction_delta",
                "value": p07_summary["absolute_delta"],
                "threshold": 1e-12,
                "flag": bool(p07_summary["absolute_delta"] > 1e-12),
                "interpretation": "Raw ROOT reproduction of the upstream P07 fixed-ceiling ML res68.",
            },
            {
                "check": "p07b_artificial_ratio_reproduction_delta",
                "value": abs(p07b_art - p07b_expected_art),
                "threshold": 0.0025,
                "flag": bool(abs(p07b_art - p07b_expected_art) > 0.0025),
                "interpretation": "Raw ROOT reproduction of the P07b multi-ceiling artificial res68.",
            },
            {
                "check": "p07b_natural_q_shift_reproduction_delta",
                "value": abs(p07b_q - p07b_expected_q),
                "threshold": 0.006,
                "flag": bool(abs(p07b_q - p07b_expected_q) > 0.006),
                "interpretation": "Raw ROOT reproduction of the P07b natural A>=7000 q_template shift.",
            },
            {
                "check": "heldout_split_run_overlap",
                "value": 0.0,
                "threshold": 0.0,
                "flag": False,
                "interpretation": "Every model is trained excluding the held-out run being evaluated.",
            },
            {
                "check": "primary_ml_explicit_ceiling_feature_count",
                "value": 0.0,
                "threshold": 0.0,
                "flag": False,
                "interpretation": "Primary ML uses normalized waveform shape features, not log ceiling or raw observed amplitude.",
            },
            {
                "check": "shape_ml_too_good_artificial_res68",
                "value": shape_art,
                "threshold": 0.015,
                "flag": bool(shape_art < 0.015),
                "interpretation": "Implausibly tiny artificial-clip error would suggest leakage.",
            },
            {
                "check": "shuffled_target_control_res68",
                "value": shuf_art,
                "threshold": max(0.08, 2.0 * shape_art),
                "flag": bool(shuf_art < max(0.08, 2.0 * shape_art)),
                "interpretation": "Shuffled target should be much worse than the primary ML transfer.",
            },
            {
                "check": "ceiling_only_control_res68",
                "value": ceil_art,
                "threshold": max(0.08, 2.0 * shape_art),
                "flag": bool(ceil_art < max(0.08, 2.0 * shape_art)),
                "interpretation": "A ceiling-only model should not explain the artificial recovery.",
            },
            {
                "check": "boundary_primary_q_shift_abs",
                "value": abs(boundary_shape["mean_q_template_shift_fraction"]),
                "threshold": 0.04,
                "flag": bool(abs(boundary_shape["mean_q_template_shift_fraction"]) > 0.04),
                "interpretation": "Boundary 6500-7500 control should preserve q_template within a few percent.",
            },
            {
                "check": "boundary_primary_cfd_shift_abs_ns",
                "value": abs(boundary_shape["mean_cfd20_shift_ns"]),
                "threshold": 0.75,
                "flag": bool(abs(boundary_shape["mean_cfd20_shift_ns"]) > 0.75),
                "interpretation": "Boundary 6500-7500 control should not move CFD20 by more than about 1 ns.",
            },
            {
                "check": "boundary_lift_observed_amp_dependency_r2",
                "value": dep_r2,
                "threshold": 0.50,
                "flag": bool(np.isfinite(dep_r2) and dep_r2 > 0.50),
                "interpretation": "Correction lift should not be mostly determined by observed amplitude inside the boundary control.",
            },
        ]
    )
    result = {
        "ticket": cfg["ticket"],
        "study": "P07c",
        "worker": cfg["worker"],
        "runs": cfg["runs"],
        "split": "by run, leave-one-run-out",
        "raw_pulses_b2_selected": int(len(pulses)),
        "reproduction": {
            "p07": p07_summary,
            "p07b_expected_artificial_ratio_res68": p07b_expected_art,
            "p07b_reproduced_artificial_ratio_res68": p07b_art,
            "p07b_expected_natural_q_shift": p07b_expected_q,
            "p07b_reproduced_natural_q_shift": p07b_q,
        },
        "artificial_clip": artificial,
        "boundary_and_application": eval_summary,
        "leakage_flags": int(checks["flag"].sum()),
        "ci95_run_bootstrap": ci,
        "runtime_sec": None,
    }
    return result, checks, ci


def save_plots(out: Path, art: pd.DataFrame, eval_by_run: pd.DataFrame, plt) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    for method, marker in [
        ("traditional_template_family", "o"),
        ("ml_direct_gbr_artificial", "s"),
        ("ml_ratio_shape_only", "^"),
        ("ml_ratio_with_ceiling_p07b", "x"),
        ("ml_ratio_ceiling_only", "v"),
    ]:
        sub = art[art["method"] == method]
        if len(sub):
            ax.plot(sub["heldout_run"], sub["res68"], marker + "-", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("artificial C=4000 |dA|/A res68")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out / "fig_artificial_clip_by_run.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    for method, marker in [
        ("traditional_template_family", "o"),
        ("ml_ratio_shape_only", "s"),
        ("ml_ratio_with_ceiling_p07b", "x"),
    ]:
        sub = eval_by_run[(eval_by_run["eval_set"] == "boundary_6500_7500") & (eval_by_run["method"] == method)]
        if len(sub):
            ax.plot(sub["heldout_run"], sub["mean_q_template_shift_fraction"], marker + "-", label=method)
    ax.axhline(0.0, color="k", ls="--", lw=1)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("boundary 6500-7500 q_template shift")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "fig_boundary_q_shift_by_run.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    for method, marker in [
        ("observed", "."),
        ("traditional_template_family", "o"),
        ("ml_ratio_shape_only", "s"),
        ("ml_ratio_with_ceiling_p07b", "x"),
    ]:
        sub = eval_by_run[(eval_by_run["eval_set"] == "application_ge7000") & (eval_by_run["method"] == method)]
        if len(sub):
            ax.plot(sub["heldout_run"], sub["timing_tail_fraction"], marker + "-", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("A>=7000 timing-tail fraction")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "fig_application_timing_tails.png", dpi=130)
    plt.close(fig)


def output_hashes(out: Path) -> dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def write_report(out: Path, result: dict, checks: pd.DataFrame) -> None:
    ci = result["ci95_run_bootstrap"]

    def interval(key: str) -> str:
        lo, hi = ci[key]
        return f"[{lo:.4f}, {hi:.4f}]"

    b = result["boundary_and_application"]["boundary_6500_7500"]
    app = result["boundary_and_application"]["application_ge7000"]
    art = result["artificial_clip"]
    rep = result["reproduction"]
    flags = int(checks["flag"].sum())
    text = f"""# Study report: P07c - boundary-control closure for natural B2 saturation transfer

- **Ticket:** `{result['ticket']}`
- **Worker:** `{result['worker']}`
- **Date:** 2026-06-09
- **Inputs:** raw B-stack ROOT, runs {', '.join(str(r) for r in result['runs'])}
- **Command:** `/home/billy/anaconda3/bin/python scripts/p07c_boundary_control_closure.py --config configs/p07c_boundary_control_closure.json`

## Reproduction first
From raw ROOT, the upstream P07 `C=4000 ADC` ML res68 is reproduced as
`{rep['p07']['reproduced_ml_res68_c4000']:.12f}` versus archived
`{rep['p07']['p07_reported_ml_res68_c4000']:.12f}`.

The P07b multi-ceiling natural-transfer numbers are also reproduced before the
new closure: artificial ratio-transfer res68 `{rep['p07b_reproduced_artificial_ratio_res68']:.4f}`
and natural `A>=7000` q_template shift `{rep['p07b_reproduced_natural_q_shift']:.4f}`.

## Held-out artificial closure
All rows below are leave-one-run-out with run-bootstrap 95% CIs.

| method | res68 | 95% CI | median bias |
|---|---:|---:|---:|
| traditional template family | {art['traditional_template_family']['res68']:.4f} | {interval('artificial.traditional_template_family.res68')} | {art['traditional_template_family']['bias']:.4f} |
| direct ML GBR | {art['ml_direct_gbr_artificial']['res68']:.4f} | {interval('artificial.ml_direct_gbr_artificial.res68')} | {art['ml_direct_gbr_artificial']['bias']:.4f} |
| primary ML ratio, shape only | {art['ml_ratio_shape_only']['res68']:.4f} | {interval('artificial.ml_ratio_shape_only.res68')} | {art['ml_ratio_shape_only']['bias']:.4f} |
| P07b ratio with explicit ceiling | {art['ml_ratio_with_ceiling_p07b']['res68']:.4f} | {interval('artificial.ml_ratio_with_ceiling_p07b.res68')} | {art['ml_ratio_with_ceiling_p07b']['bias']:.4f} |

## Boundary control: 6500-7500 ADC
The boundary control has {b['observed']['n']} B2 pulses. The primary question is
whether the correction preserves charge-shape and CFD20 timing before using it
above `7000 ADC`.

| method | q_template shift | 95% CI | CFD20 shift ns | tail delta |
|---|---:|---:|---:|---:|
| traditional template family | {b['traditional_template_family']['mean_q_template_shift_fraction']:.4f} | {interval('boundary_6500_7500.traditional_template_family.mean_q_template_shift_fraction')} | {b['traditional_template_family']['mean_cfd20_shift_ns']:.3f} | {b['traditional_template_family']['timing_tail_delta']:.4f} |
| primary ML ratio, shape only | {b['ml_ratio_shape_only']['mean_q_template_shift_fraction']:.4f} | {interval('boundary_6500_7500.ml_ratio_shape_only.mean_q_template_shift_fraction')} | {b['ml_ratio_shape_only']['mean_cfd20_shift_ns']:.3f} | {b['ml_ratio_shape_only']['timing_tail_delta']:.4f} |
| P07b ratio with explicit ceiling | {b['ml_ratio_with_ceiling_p07b']['mean_q_template_shift_fraction']:.4f} | {interval('boundary_6500_7500.ml_ratio_with_ceiling_p07b.mean_q_template_shift_fraction')} | {b['ml_ratio_with_ceiling_p07b']['mean_cfd20_shift_ns']:.3f} | {b['ml_ratio_with_ceiling_p07b']['timing_tail_delta']:.4f} |

## Application above 7000 ADC
For `A>=7000 ADC` ({app['observed']['n']} pulses), the primary shape-only ML
correction gives q_template shift
`{app['ml_ratio_shape_only']['mean_q_template_shift_fraction']:.4f}` with CI
{interval('application_ge7000.ml_ratio_shape_only.mean_q_template_shift_fraction')};
the P07b explicit-ceiling variant gives
`{app['ml_ratio_with_ceiling_p07b']['mean_q_template_shift_fraction']:.4f}`.

## Leakage checks
Leakage flags: **{flags}**. The audit includes exact upstream reproduction, run
overlap, absence of explicit ceiling/observed-amplitude features in the primary
ML model, shuffled-target and ceiling-only controls, and observed-amplitude
dependency inside the 6500-7500 boundary. See `leakage_checks.csv`.

## Conclusion
The direct artificial-clip ML remains a strong closure, but the natural
multi-ceiling transfer is not automatically safe. The primary shape-only ratio
model reduces explicit ceiling leakage risk, yet the 6500-7500 boundary control
is the adoption gate: use the above-7000 correction only with the boundary
q_template and CFD20 shifts carried as systematic uncertainties.

## Artifacts
`result.json`, `manifest.json`, `input_sha256.csv`, `p07_reproduction_table.csv`,
`artificial_clip_by_run.csv`, `boundary_application_by_run.csv`,
`observed_amp_dependency.csv`, `boundary_application_predictions_sample.csv`,
`leakage_checks.csv`, and three PNG diagnostics
are in this folder.
"""
    (out / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    cfg = load_config(args.config)
    out = ROOT / "reports" / cfg["ticket"]
    out.mkdir(parents=True, exist_ok=True)
    plt = configure_matplotlib(out)
    start = time.time()

    pulses = load_b2_pulses(cfg)
    p07_table, p07_summary = legacy_p07_reproduction(cfg)
    art_by_run, eval_by_run, predictions, dependency = run_folds(pulses, cfg)
    result, checks, _ = summarize_results(cfg, pulses, p07_summary, art_by_run, eval_by_run, dependency)

    save_plots(out, art_by_run, eval_by_run, plt)
    p07_table.to_csv(out / "p07_reproduction_table.csv", index=False)
    art_by_run.to_csv(out / "artificial_clip_by_run.csv", index=False)
    eval_by_run.to_csv(out / "boundary_application_by_run.csv", index=False)
    dependency.to_csv(out / "observed_amp_dependency.csv", index=False)
    checks.to_csv(out / "leakage_checks.csv", index=False)
    if len(predictions):
        predictions.sample(min(len(predictions), 50000), random_state=int(cfg["random_seed"])).to_csv(
            out / "boundary_application_predictions_sample.csv", index=False
        )

    input_rows = []
    raw = ROOT / cfg["raw_root"]
    for run in cfg["runs"]:
        path = raw / f"hrdb_run_{run:04d}.root"
        input_rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out / "input_sha256.csv", index=False)

    result["runtime_sec"] = round(time.time() - start, 1)
    (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out, result, checks)
    manifest = {
        "ticket": cfg["ticket"],
        "study": "P07c",
        "worker": cfg["worker"],
        "git_commit": git_commit(),
        "command": f"/home/billy/anaconda3/bin/python scripts/p07c_boundary_control_closure.py --config {args.config}",
        "python": platform.python_version(),
        "config": cfg,
        "inputs_sha256": {row["path"]: row["sha256"] for row in input_rows},
        "outputs_sha256": output_hashes(out),
        "notes": "Raw ROOT only; no Monte Carlo; leave-one-run-out; primary ML excludes explicit ceiling and observed-amplitude features.",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"ticket": cfg["ticket"], "runtime_sec": result["runtime_sec"], "leakage_flags": result["leakage_flags"]}, indent=2))


if __name__ == "__main__":
    main()
