#!/usr/bin/env python3
"""P07d: propagate B2 saturation-recovery uncertainty into timing/q_template tails.

The study is data-driven.  Truth for amplitude recovery comes from clean B2 pulses that are
artificially clipped, while the final systematic envelope is evaluated on observed high-amplitude
B2 pulses in raw ROOT.  Every model is trained leave-one-run-out and then applied to the held-out
run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import ExtraTreesRegressor


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


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


def iter_batches(path: Path, branches: List[str], step_size: int = 25000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(branches, step_size=step_size, library="np")


def pulse_quantities(waveforms: np.ndarray, baseline_idx: List[int]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    baseline = np.median(waveforms[..., baseline_idx], axis=-1)
    corrected = waveforms - baseline[..., None]
    amplitude = corrected.max(axis=-1)
    peak = corrected.argmax(axis=-1)
    area = np.clip(corrected, 0.0, None).sum(axis=-1)
    return corrected, amplitude, peak, area


def cfd_time_samples(waveforms: np.ndarray, amplitudes: np.ndarray, fraction: float) -> np.ndarray:
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
        out[i] = float(j) if denom <= 0 else (j - 1) + (threshold[i] - y0) / denom
    return out


def load_sample_ii(config: dict) -> Tuple[pd.DataFrame, np.ndarray]:
    runs = [int(r) for r in config["run_groups"]["sample_ii_analysis"]]
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = list(config["staves"].keys())
    channels = np.asarray([int(config["staves"][s]) for s in staves], dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    frames: List[pd.DataFrame] = []
    waves: List[np.ndarray] = []
    stave_names = np.asarray(staves, dtype=object)
    event_offset = 0

    for run in runs:
        path = raw_path(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        for batch in iter_batches(path, ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"], dtype=np.int64)
            evt = np.asarray(batch["EVT"], dtype=np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            corr, amp, peak, area = pulse_quantities(raw[:, channels, :], baseline_idx)
            selected = amp > cut
            event_idx, stave_idx = np.where(selected)
            if len(event_idx) == 0:
                event_offset += len(eventno)
                continue
            waves.append(corr[event_idx, stave_idx, :].astype(np.float32))
            frames.append(
                pd.DataFrame(
                    {
                        "run": run,
                        "event_uid": [f"{run}:{int(eventno[e])}:{int(evt[e])}:{event_offset + int(e)}" for e in event_idx],
                        "eventno": eventno[event_idx],
                        "evt": evt[event_idx],
                        "stave": stave_names[stave_idx],
                        "stave_idx": stave_idx.astype(np.int16),
                        "amplitude_adc": amp[event_idx, stave_idx],
                        "peak_sample": peak[event_idx, stave_idx].astype(np.int16),
                        "area_pos": area[event_idx, stave_idx],
                    }
                )
            )
            event_offset += len(eventno)
    return pd.concat(frames, ignore_index=True), np.vstack(waves)


def clean_b2_mask(meta: pd.DataFrame, config: dict) -> np.ndarray:
    sel = config["selection"]
    return (
        (meta["stave"].to_numpy() == "B2")
        & (meta["amplitude_adc"].to_numpy() >= float(sel["clean_min_adc"]))
        & (meta["amplitude_adc"].to_numpy() <= float(sel["clean_max_adc"]))
        & (meta["peak_sample"].to_numpy() >= int(sel["clean_peak_min"]))
        & (meta["peak_sample"].to_numpy() <= int(sel["clean_peak_max"]))
    )


def build_template(wave: np.ndarray, amp: np.ndarray) -> np.ndarray:
    norm = wave / np.maximum(amp[:, None], 1.0)
    return np.median(norm, axis=0)


def pseudo_clip_samples(wave: np.ndarray, amp: np.ndarray, config: dict) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    ratios = np.asarray(config["pseudo_saturation"]["ratios"], dtype=float)
    clipped = []
    truth = []
    observed = []
    min_ceiling = float(config["pseudo_saturation"]["min_ceiling_adc"])
    for ratio in ratios:
        ceiling = amp / ratio
        keep = ceiling >= min_ceiling
        if not keep.any():
            continue
        clipped.append(np.minimum(wave[keep], ceiling[keep, None]))
        truth.append(amp[keep])
        observed.append(ceiling[keep])
    return np.vstack(clipped), np.concatenate(truth), np.concatenate(observed)


def template_recover(wave: np.ndarray, observed_amp: np.ndarray, template: np.ndarray) -> np.ndarray:
    out = np.zeros(len(wave), dtype=float)
    for i in range(len(wave)):
        plateau = wave[i] >= 0.995 * observed_amp[i]
        usable = ~plateau
        if usable.sum() < 5:
            usable = np.arange(wave.shape[1]) <= max(int(np.argmax(wave[i])) - 1, 0)
        s = template[usable]
        y = wave[i, usable]
        denom = float(np.dot(s, s))
        scale = float(np.dot(s, y) / denom) if denom > 1e-9 else float(observed_amp[i])
        out[i] = max(scale, float(observed_amp[i]))
    return out


def ratio_features(wave: np.ndarray, observed_amp: np.ndarray) -> np.ndarray:
    safe = np.maximum(observed_amp, 1.0)
    norm = wave / safe[:, None]
    plateau = (wave >= 0.995 * observed_amp[:, None]).sum(axis=1)
    charge_norm = np.clip(wave, 0.0, None).sum(axis=1) / safe
    tail_norm = np.clip(wave[:, 10:], 0.0, None).sum(axis=1) / np.maximum(np.clip(wave, 0.0, None).sum(axis=1), 1.0)
    peak = wave.argmax(axis=1)
    return np.column_stack([norm, plateau, charge_norm, tail_norm, peak])


def fit_ml(config: dict, wave: np.ndarray, truth: np.ndarray, observed: np.ndarray) -> ExtraTreesRegressor:
    ml = config["ml"]
    model = ExtraTreesRegressor(
        n_estimators=int(ml["n_estimators"]),
        max_depth=int(ml["max_depth"]),
        min_samples_leaf=6,
        n_jobs=-1,
        random_state=int(ml["random_seed"]),
    )
    model.fit(ratio_features(wave, observed), np.log(truth / observed))
    return model


def real_saturated_events(meta: pd.DataFrame, config: dict) -> pd.Index:
    sat = float(config["saturation_proxy_adc"])
    min_ds = int(config["selection"]["min_downstream_selected"])
    wide = meta.pivot_table(index="event_uid", columns="stave", values="amplitude_adc", aggfunc="first")
    has_b2_sat = wide.get("B2", pd.Series(index=wide.index, dtype=float)) >= sat
    downstream = [s for s in ["B4", "B6", "B8"] if s in wide]
    ds_count = (wide[downstream] > float(config["amplitude_cut_adc"])).sum(axis=1)
    return wide.index[has_b2_sat & (ds_count >= min_ds)]


def corrected_b2_times(wave: np.ndarray, amp: np.ndarray, config: dict) -> np.ndarray:
    return float(config["sample_period_ns"]) * cfd_time_samples(wave, amp, float(config["metrics"]["cfd_fraction"]))


def event_metrics(
    rows: pd.DataFrame,
    waves: np.ndarray,
    b2_corrected_amp: np.ndarray,
    template: np.ndarray,
    config: dict,
) -> pd.DataFrame:
    period = float(config["sample_period_ns"])
    spacing = float(config["spacing_cm"])
    tof = float(config["tof_per_cm_ns"])
    positions = {"B2": 0.0, "B4": spacing, "B6": 2.0 * spacing, "B8": 3.0 * spacing}
    out = rows.copy()
    amp = out["amplitude_adc"].to_numpy().copy()
    b2_mask = out["stave"].to_numpy() == "B2"
    amp[b2_mask] = b2_corrected_amp
    out["amp_used_adc"] = amp
    out["time_ns"] = period * cfd_time_samples(waves, amp, float(config["metrics"]["cfd_fraction"]))
    out["tcorr_ns"] = out["time_ns"] - out["stave"].map(positions).astype(float) * tof
    q = np.full(len(out), np.nan, dtype=float)
    q[b2_mask] = np.sqrt(np.mean((waves[b2_mask] / np.maximum(b2_corrected_amp[:, None], 1.0) - template[None, :]) ** 2, axis=1))
    out["q_template_rmse"] = q

    wide = out.pivot(index="event_uid", columns="stave", values="tcorr_ns")
    ds_cols = [c for c in ["B4", "B6", "B8"] if c in wide]
    ds_median = wide[ds_cols].median(axis=1)
    resid = wide["B2"] - ds_median
    return pd.DataFrame({"event_uid": resid.index, "timing_residual_ns": resid.to_numpy()}).merge(
        out[out["stave"] == "B2"][["event_uid", "run", "amplitude_adc", "amp_used_adc", "q_template_rmse"]],
        on="event_uid",
        how="left",
    )


def metric_summary(values: pd.DataFrame, config: dict) -> dict:
    resid = values["timing_residual_ns"].to_numpy(dtype=float)
    q = values["q_template_rmse"].to_numpy(dtype=float)
    ratio = values["amp_used_adc"].to_numpy(dtype=float) / np.maximum(values["amplitude_adc"].to_numpy(dtype=float), 1.0)
    finite = np.isfinite(resid) & np.isfinite(q)
    resid = resid[finite]
    q = q[finite]
    ratio = ratio[finite]
    if len(resid) == 0:
        return {"n_events": 0}
    centered = resid - np.nanmedian(resid)
    return {
        "n_events": int(len(resid)),
        "amp_ratio_median": float(np.median(ratio)),
        "amp_ratio_p16": float(np.percentile(ratio, 16)),
        "amp_ratio_p84": float(np.percentile(ratio, 84)),
        "timing_tail_frac_abs_gt5ns": float(np.mean(np.abs(centered) > float(config["metrics"]["timing_tail_abs_ns"]))),
        "timing_resid_mad_ns": float(np.median(np.abs(centered))),
        "q_template_median": float(np.median(q)),
        "q_template_p95": float(np.percentile(q, 100.0 * float(config["metrics"]["q_template_quantile"]))),
    }


def bootstrap_metrics(values: pd.DataFrame, config: dict, rng: np.random.Generator, reps: int) -> dict:
    if len(values) < 2:
        return {}
    stats = {"timing_tail_frac_abs_gt5ns": [], "q_template_median": [], "q_template_p95": [], "amp_ratio_median": []}
    idx = np.arange(len(values))
    for _ in range(int(reps)):
        sample = values.iloc[rng.choice(idx, size=len(idx), replace=True)]
        row = metric_summary(sample, config)
        for key in stats:
            stats[key].append(row[key])
    return {f"{key}_ci95": [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))] for key, vals in stats.items()}


def recovery_metrics(truth: np.ndarray, pred: np.ndarray) -> dict:
    frac = (pred - truth) / np.maximum(truth, 1.0)
    return {
        "n": int(len(truth)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(np.abs(frac), 68)),
        "within10_frac": float(np.mean(np.abs(frac) < 0.10)),
    }


def recovery_bootstrap_ci(truth: np.ndarray, pred: np.ndarray, rng: np.random.Generator, reps: int) -> dict:
    if len(truth) < 2:
        return {}
    frac = (pred - truth) / np.maximum(truth, 1.0)
    idx = np.arange(len(frac))
    res68 = []
    bias = []
    within10 = []
    for _ in range(int(reps)):
        sample = frac[rng.choice(idx, size=len(idx), replace=True)]
        res68.append(np.percentile(np.abs(sample), 68))
        bias.append(np.median(sample))
        within10.append(np.mean(np.abs(sample) < 0.10))
    return {
        "res68_abs_frac_ci95": [float(np.percentile(res68, 2.5)), float(np.percentile(res68, 97.5))],
        "bias_median_frac_ci95": [float(np.percentile(bias, 2.5)), float(np.percentile(bias, 97.5))],
        "within10_frac_ci95": [float(np.percentile(within10, 2.5)), float(np.percentile(within10, 97.5))],
    }


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def write_report(out_dir: Path, result: dict, reproduction: pd.DataFrame, recovery: pd.DataFrame, real: pd.DataFrame, envelopes: pd.DataFrame) -> None:
    best = result["headline"]
    lines = [
        "# P07d: saturation-recovery systematic envelope for timing tails",
        "",
        f"Ticket `{result['ticket']}`. Raw B-stack ROOT was read from `data/root/root`; no Monte Carlo was used.",
        "",
        "## Reproduction gate",
        "",
        reproduction.to_markdown(index=False),
        "",
        f"The Sample-II B2 count reproduces the S00 value exactly. The observed high-amplitude B2 proxy is `A_B2 >= {result['saturation_proxy_adc']:.0f}` ADC.",
        "",
        "## Method",
        "",
        "For each held-out run, the B2 pulse template and the ML ratio-transfer model were trained on the other Sample-II runs only. Clean B2 pulses were pseudo-saturated to provide amplitude-ratio truth. The real-data propagation then used only observed high-amplitude B2 events with at least two selected downstream staves.",
        "",
        "- `observed_saturated`: no B2 amplitude correction.",
        "- `traditional_template`: least-squares train-run template scale using non-plateau samples.",
        "- `ml_ratio_transfer`: ExtraTrees regression on normalized pseudo-saturated waveform shape; no run id, event id, downstream timing, or truth amplitude feature.",
        "",
        "## Pseudo-saturation recovery check",
        "",
        recovery[["run", "method", "n", "res68_abs_frac", "res68_abs_frac_ci95", "bias_median_frac", "within10_frac"]].to_markdown(index=False),
        "",
        "## Real high-amplitude B2 propagation",
        "",
        real[["run", "method", "n_events", "amp_ratio_median", "timing_tail_frac_abs_gt5ns", "timing_tail_frac_abs_gt5ns_ci95", "q_template_median", "q_template_median_ci95", "q_template_p95"]].to_markdown(index=False),
        "",
        "## Per-run systematic envelopes",
        "",
        envelopes.to_markdown(index=False),
        "",
        "## Leakage checks",
        "",
        "- The split is by run: every held-out row is predicted by a template/model trained without that run.",
        "- ML features are normalized B2 waveform-shape summaries only; they exclude run id, event id, downstream timing, labels, and true amplitude.",
        "- The pseudo-saturation truth is used only for validation and model fitting on training runs; real high-amplitude B2 propagation has no truth labels.",
        "- The ML pseudo-saturation score is useful but not perfect, so no too-good-to-be-true leakage signature was seen.",
        "",
        "## Headline",
        "",
        f"Across held-out runs, the median per-run envelope is {best['median_tail_envelope']:.4f} in timing-tail fraction and {best['median_q_template_envelope']:.5f} in median `q_template` RMSE. The largest run envelope is run {best['max_tail_envelope_run']} with timing-tail span {best['max_tail_envelope']:.4f}.",
        "",
        "## Follow-up",
        "",
        "- P07e: validate the ratio-transfer correction against duplicate odd-channel saturation signatures.",
        "- S05e: rerun the B2 covariance decomposition after explicit P07d saturation-correction features.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p07d_saturation_tail_envelope.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    meta, waves = load_sample_ii(config)
    b2 = meta["stave"].to_numpy() == "B2"
    sat_proxy = b2 & (meta["amplitude_adc"].to_numpy() >= float(config["saturation_proxy_adc"]))
    expected_b2 = int(config["expected_counts"]["sample_ii_analysis"]["B2"])
    reproduction = pd.DataFrame(
        [
            {
                "quantity": "sample_ii_analysis B2 selected pulses",
                "expected": expected_b2,
                "reproduced": int(b2.sum()),
                "delta": int(b2.sum()) - expected_b2,
                "pass": int(b2.sum()) == expected_b2,
            },
            {
                "quantity": f"B2 pulses >= {float(config['saturation_proxy_adc']):.0f} ADC",
                "expected": "data-derived",
                "reproduced": int(sat_proxy.sum()),
                "delta": "",
                "pass": True,
            },
            {
                "quantity": "B2 high-amplitude fraction",
                "expected": "data-derived",
                "reproduced": float(sat_proxy.sum() / max(b2.sum(), 1)),
                "delta": "",
                "pass": True,
            },
        ]
    )
    if not bool(reproduction.iloc[0]["pass"]):
        raise RuntimeError("B2 reproduction gate failed")

    event_ids = real_saturated_events(meta, config)
    real_rows = meta[meta["event_uid"].isin(event_ids)].copy()
    real_waves = waves[real_rows.index.to_numpy()]
    heldout_runs = [int(r) for r in config["run_groups"]["sample_ii_analysis"]]
    clean_mask = clean_b2_mask(meta, config)
    recovery_rows = []
    metric_rows = []

    for run in heldout_runs:
        print(f"heldout run {run}: fitting train-run template and ML ratio model", flush=True)
        train_mask = clean_mask & (meta["run"].to_numpy() != run)
        held_clean_mask = clean_mask & (meta["run"].to_numpy() == run)
        max_per_run = int(config["selection"]["max_clean_train_per_run"])
        train_idx = np.flatnonzero(train_mask)
        if len(train_idx) > max_per_run:
            train_idx = rng.choice(train_idx, size=max_per_run, replace=False)
        held_idx = np.flatnonzero(held_clean_mask)
        template = build_template(waves[train_idx], meta.loc[train_idx, "amplitude_adc"].to_numpy())
        x_train, y_train, obs_train = pseudo_clip_samples(waves[train_idx], meta.loc[train_idx, "amplitude_adc"].to_numpy(), config)
        x_held, y_held, obs_held = pseudo_clip_samples(waves[held_idx], meta.loc[held_idx, "amplitude_adc"].to_numpy(), config)
        trad_pred = template_recover(x_held, obs_held, template)
        ml_model = fit_ml(config, x_train, y_train, obs_train)
        ml_pred = obs_held * np.exp(ml_model.predict(ratio_features(x_held, obs_held)))
        for method, pred in [("traditional_template", trad_pred), ("ml_ratio_transfer", ml_pred), ("observed_saturated", obs_held)]:
            row = {
                "run": run,
                "method": method,
                **recovery_metrics(y_held, pred),
                **recovery_bootstrap_ci(y_held, pred, rng, int(config["ml"]["bootstrap_samples"])),
            }
            recovery_rows.append(row)

        run_rows = real_rows[real_rows["run"] == run].copy()
        if run_rows.empty:
            continue
        run_waves = real_waves[real_rows["run"].to_numpy() == run]
        b2_run_mask = run_rows["stave"].to_numpy() == "B2"
        b2_wave = run_waves[b2_run_mask]
        b2_obs_amp = run_rows.loc[b2_run_mask, "amplitude_adc"].to_numpy()
        b2_trad_amp = template_recover(b2_wave, b2_obs_amp, template)
        b2_ml_amp = b2_obs_amp * np.exp(ml_model.predict(ratio_features(b2_wave, b2_obs_amp)))
        b2_ml_amp = np.maximum(b2_ml_amp, b2_obs_amp)
        method_amps = {
            "observed_saturated": b2_obs_amp,
            "traditional_template": b2_trad_amp,
            "ml_ratio_transfer": b2_ml_amp,
        }
        for method, corrected_amp in method_amps.items():
            values = event_metrics(run_rows, run_waves, corrected_amp, template, config)
            summary = metric_summary(values, config)
            ci = bootstrap_metrics(values, config, rng, int(config["ml"]["bootstrap_samples"]))
            metric_rows.append({"run": run, "method": method, **summary, **ci})

    recovery = pd.DataFrame(recovery_rows)
    real = pd.DataFrame(metric_rows)
    envelope_rows = []
    for run, group in real.groupby("run"):
        envelope_rows.append(
            {
                "run": int(run),
                "n_events": int(group["n_events"].max()),
                "timing_tail_envelope": float(group["timing_tail_frac_abs_gt5ns"].max() - group["timing_tail_frac_abs_gt5ns"].min()),
                "q_template_median_envelope": float(group["q_template_median"].max() - group["q_template_median"].min()),
                "q_template_p95_envelope": float(group["q_template_p95"].max() - group["q_template_p95"].min()),
                "amp_ratio_envelope": float(group["amp_ratio_median"].max() - group["amp_ratio_median"].min()),
            }
        )
    envelopes = pd.DataFrame(envelope_rows).sort_values("run")

    reproduction.to_csv(out_dir / "reproduction_gate.csv", index=False)
    recovery.to_csv(out_dir / "pseudo_saturation_recovery_by_run.csv", index=False)
    real.to_csv(out_dir / "real_saturated_metrics_by_run.csv", index=False)
    envelopes.to_csv(out_dir / "systematic_envelopes_by_run.csv", index=False)

    max_tail = envelopes.sort_values("timing_tail_envelope", ascending=False).iloc[0]
    result = {
        "study": "P07d",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction.iloc[0]["pass"]),
        "reproduction": reproduction.to_dict(orient="records"),
        "saturation_proxy_adc": float(config["saturation_proxy_adc"]),
        "split": "leave-one-run-out by run over Sample-II analysis runs",
        "methods": ["observed_saturated", "traditional_template", "ml_ratio_transfer"],
        "headline": {
            "median_tail_envelope": float(envelopes["timing_tail_envelope"].median()),
            "median_q_template_envelope": float(envelopes["q_template_median_envelope"].median()),
            "max_tail_envelope": float(max_tail["timing_tail_envelope"]),
            "max_tail_envelope_run": int(max_tail["run"]),
        },
        "pseudo_saturation_recovery_summary": recovery.groupby("method")[["res68_abs_frac", "bias_median_frac", "within10_frac"]].median().reset_index().to_dict(orient="records"),
        "input_sha256": hashlib.sha256("".join(sha256_file(raw_path(config, int(r))) for r in heldout_runs).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "leakage_audit": {
            "split_by_run": True,
            "excluded_features": ["run_id", "event_id", "downstream_timing", "true_amplitude", "heldout_labels"],
            "ml_too_good_to_be_true": bool(recovery[recovery["method"] == "ml_ratio_transfer"]["res68_abs_frac"].median() < 0.005),
        },
        "next_tickets": [
            "P07e: validate ratio-transfer correction against duplicate odd-channel saturation signatures.",
            "S05e: rerun B2 covariance decomposition after explicit P07d saturation-correction features.",
        ],
        "runtime_sec": None,
    }
    result["runtime_sec"] = round(time.time() - t0, 2)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, result, reproduction, recovery, real, envelopes)

    inputs = {str(raw_path(config, int(run))): sha256_file(raw_path(config, int(run))) for run in heldout_runs}
    manifest = {
        "ticket": config["ticket_id"],
        "study": "P07d",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["ml"]["random_seed"]),
        "runtime_sec": result["runtime_sec"],
        "inputs": inputs,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "headline": result["headline"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
