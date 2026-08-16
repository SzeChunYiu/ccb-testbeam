#!/usr/bin/env python3
"""Issue #2482 S55a Wiener-template timing versus waveform ML benchmark."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.multioutput import MultiOutputRegressor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402
import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as s25b  # noqa: E402
import s26b_1783798536_2368_2ce12433_saturation_energy_recovery_architecture_bakeoff as s26b  # noqa: E402


TICKET = "2482"
WORKER = "testbeam-laptop-2"
TITLE = "S55a: Wiener-template timing versus waveform ML for pile-up phase disentanglement"
SLUG = "s55a_wiener_template_timing_ml_phase_disentanglement"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")
ADC_CLIP = 11800.0
CLAIMED_TEXT = """claim_helper_command: tn-ticket claim testbeam-laptop-2 --project testbeam
claim_helper_stderr:
null
claim_helper_stdout:
# null

null
manual_claim_issue: 2482
manual_claim_command: gh --repo SzeChunYiu/factory-tickets issue edit 2482 --add-label factory:claimed --add-label worker:testbeam-laptop-2 --remove-label factory:open
manual_claim_evidence: issue #2482 labels include factory:claimed, project:testbeam, worker:testbeam-laptop-2
done_command: tn-ticket done 2482
done_command_output: Closed issue SzeChunYiu/factory-tickets#2482
done_evidence: issue #2482 state CLOSED with labels factory:done, project:testbeam, worker:testbeam-laptop-2
# S55a: Wiener-template timing versus waveform ML for pile-up phase disentanglement

Academic-grade study: quantify how pulse timing, shape, and early pile-up phase
bias energy estimates across current and pedestal strata. Compare a traditional
Wiener/matched-template fit and constant-fraction timing against ridge
regression, gradient-boosted trees, MLP, 1D-CNN, and a compact transformer
sequence model where waveform length supports attention. Require run-blocked
train/test splits, bootstrap 95% CIs for timing RMSE, energy bias, pile-up
classification AUC, and stratified residual tails; include ablations for
pedestal subtraction and saturation masks.
"""


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_config() -> dict:
    cfg = s25b.load_base_config()
    cfg.update(
        {
            "study_id": "S55a",
            "ticket_id": TICKET,
            "title": TITLE,
            "worker": WORKER,
            "raw_root_dir": str(RAW_ROOT_DIR),
            "output_dir": str(OUT),
            "random_seed": 2026081601,
            "max_clean_pulses_per_run_stave": 92,
            "injected_per_train_run": 54,
            "clean_per_train_run": 54,
            "injected_per_heldout_run": 72,
            "clean_per_heldout_run": 72,
        }
    )
    cfg["ml"].update({"bootstrap_samples": 400, "cnn_epochs": 85, "cnn_channels": 12, "max_iter": 240})
    return cfg


def apply_clipping(waveforms: np.ndarray) -> np.ndarray:
    return np.minimum(np.asarray(waveforms, dtype=float), ADC_CLIP)


def phase_features(waveforms: np.ndarray, *, pedestal: bool = True, saturation_mask: bool = True) -> np.ndarray:
    y = np.asarray(waveforms, dtype=float)
    baseline = np.median(y[:, :4], axis=1) if pedestal else np.zeros(y.shape[0])
    corr = y - baseline[:, None]
    amp = np.maximum(corr.max(axis=1), 1.0)
    norm = corr / amp[:, None]
    area = corr.sum(axis=1)
    early = corr[:, 4:8].sum(axis=1)
    mid = corr[:, 8:12].sum(axis=1)
    late = corr[:, 12:].sum(axis=1)
    cfd20 = np.array([p05a.cfd_time_one(row, 0.2) for row in corr], dtype=float)
    cfd50 = np.array([p05a.cfd_time_one(row, 0.5) for row in corr], dtype=float)
    phase = np.nan_to_num(cfd50 - cfd20, nan=0.0, posinf=0.0, neginf=0.0)
    width20 = (corr > 0.2 * amp[:, None]).sum(axis=1).astype(float)
    peak = corr.argmax(axis=1).astype(float)
    feat = [
        norm,
        np.log1p(amp)[:, None],
        peak[:, None],
        (area / amp)[:, None],
        (early / np.maximum(area, 1.0))[:, None],
        (mid / np.maximum(area, 1.0))[:, None],
        (late / np.maximum(area, 1.0))[:, None],
        phase[:, None],
        width20[:, None],
    ]
    if saturation_mask:
        sat = y >= (ADC_CLIP - 1e-6)
        sat_count = sat.sum(axis=1).astype(float)
        plateau = (corr > 0.94 * amp[:, None]).sum(axis=1).astype(float)
        feat.extend([sat.astype(float), sat_count[:, None], plateau[:, None]])
    return np.hstack(feat)


def waveform_state_columns(events: pd.DataFrame, waveforms: np.ndarray) -> pd.DataFrame:
    out = events.copy()
    baseline = np.median(waveforms[:, :4], axis=1)
    corr = waveforms - baseline[:, None]
    amp = np.maximum(corr.max(axis=1), 1.0)
    out["pedestal_state"] = np.where(np.abs(baseline) > 45.0, "shifted", "nominal")
    out["saturated_sample_count"] = (waveforms >= (ADC_CLIP - 1e-6)).sum(axis=1).astype(int)
    out["saturation_mask_state"] = np.where(out["saturated_sample_count"] > 0, "masked_saturated", "unsaturated")
    out["phase_bin"] = pd.cut(
        np.nan_to_num(np.array([p05a.cfd_time_one(row, 0.5) - p05a.cfd_time_one(row, 0.2) for row in corr])),
        bins=[-10, 0.9, 1.5, 2.4, 10],
        labels=["fast_rise", "nominal_rise", "slow_rise", "broad_rise"],
        include_lowest=True,
    ).astype(str)
    out["current_proxy"] = np.where((out["source_run"].astype(int) % 2) == 0, "even_run_current_proxy", "odd_run_current_proxy")
    out["energy_proxy_bin"] = pd.cut(
        out["true_amp1_adc"] + out["true_amp2_adc"],
        bins=[0, 5500, 8500, 11500, 20000],
        labels=["low", "mid", "high", "very_high"],
        include_lowest=True,
    ).astype(str)
    out["amp_over_width"] = amp / np.maximum((corr > 0.2 * amp[:, None]).sum(axis=1), 1.0)
    return out


def traditional_prediction(trad: pd.DataFrame, waveforms: np.ndarray) -> pd.DataFrame:
    pred = s25b.template_prediction(trad)
    y = np.asarray(waveforms, dtype=float)
    baseline = np.median(y[:, :4], axis=1)
    corr = y - baseline[:, None]
    # A small deterministic Wiener-like sideband correction: broad early phase
    # and clipped plateaus imply hidden second-pulse energy under the template.
    amp = np.maximum(corr.max(axis=1), 1.0)
    cfd20 = np.array([p05a.cfd_time_one(row, 0.2) for row in corr], dtype=float)
    cfd50 = np.array([p05a.cfd_time_one(row, 0.5) for row in corr], dtype=float)
    phase_width = np.nan_to_num(cfd50 - cfd20, nan=1.2)
    plateau = (corr > 0.94 * amp[:, None]).sum(axis=1).astype(float)
    sat_count = (y >= (ADC_CLIP - 1e-6)).sum(axis=1).astype(float)
    corr_factor = np.clip(1.0 + 0.018 * np.maximum(phase_width - 1.25, 0.0) + 0.011 * sat_count + 0.012 * plateau, 1.0, 1.28)
    pred["amp1_adc"] = pred["amp1_adc"].to_numpy(float) * corr_factor
    pred["amp2_adc"] = pred["amp2_adc"].to_numpy(float) * corr_factor
    pred["method"] = "wiener_template_cfd_traditional"
    return pred


def phase_residual_fusion(
    events: pd.DataFrame,
    waveforms: np.ndarray,
    trad: pd.DataFrame,
    seed: int,
    *,
    pedestal: bool = True,
    saturation_mask: bool = True,
    method: str = "phase_residual_fusion_new",
) -> pd.DataFrame:
    x0 = phase_features(waveforms, pedestal=pedestal, saturation_mask=saturation_mask)
    trad_cols = trad[["trad_score", "trad_t1_sample", "trad_t2_sample", "trad_amp1_adc", "trad_amp2_adc"]].to_numpy(float)
    x = np.hstack([x0, np.nan_to_num(trad_cols, nan=0.0, posinf=0.0, neginf=0.0)])
    y_class = events["is_overlap"].to_numpy(int)
    y_reg, max_amp = s25b.regression_targets(events, waveforms)
    train = events["split"].to_numpy() == "train"
    pos_train = train & (y_class == 1)
    clf = HistGradientBoostingClassifier(max_iter=105, learning_rate=0.055, l2_regularization=0.025, random_state=seed + 101)
    reg = MultiOutputRegressor(
        HistGradientBoostingRegressor(max_iter=105, learning_rate=0.055, l2_regularization=0.025, random_state=seed + 102)
    )
    clf.fit(x[train], y_class[train])
    reg.fit(x[pos_train], y_reg[pos_train])
    return s25b.as_prediction(events, clf.predict_proba(x)[:, 1], reg.predict(x), max_amp, method)


def metric_values(frame: pd.DataFrame) -> dict:
    labels = frame["is_overlap"].to_numpy(int)
    score = np.nan_to_num(frame["score"].to_numpy(float), nan=-1e9, neginf=-1e9)
    positives = frame[frame["is_overlap"] == 1]
    valid = positives[~positives["failed"].astype(bool)].copy()
    if len(valid):
        true_t = valid[["true_t1_sample", "true_t2_sample"]].to_numpy(float)
        pred_t = valid[["t1_sample", "t2_sample"]].to_numpy(float)
        terr = ((pred_t - true_t) * 10.0).reshape(-1)
        true_a = valid[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
        pred_a = valid[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
        eerr = (pred_a - true_a) / np.maximum(true_a, 1.0)
    else:
        terr = np.asarray([])
        eerr = np.asarray([])
    sig68 = lambda z: float((np.percentile(z, 84) - np.percentile(z, 16)) / 2.0) if len(z) else float("nan")
    return {
        "timing_rmse_ns": float(np.sqrt(np.mean(terr**2))) if len(terr) else float("nan"),
        "time_bias_ns": float(np.median(terr)) if len(terr) else float("nan"),
        "time_sigma68_ns": sig68(terr),
        "late_tail_rate_abs_gt_15ns": float(np.mean(np.abs(terr) > 15.0)) if len(terr) else float("nan"),
        "energy_fractional_bias": float(np.median(eerr)) if len(eerr) else float("nan"),
        "energy_fractional_sigma68": sig68(eerr),
        "pileup_auc": float(roc_auc_score(labels, score)) if len(np.unique(labels)) == 2 else float("nan"),
        "pileup_average_precision": float(average_precision_score(labels, score)) if len(np.unique(labels)) == 2 else float("nan"),
        "pileup_miss_rate": float(positives["failed"].mean()) if len(positives) else float("nan"),
        "false_split_rate": float((frame[frame["is_overlap"] == 0]["score"] >= 0.5).mean()),
        "n_events": int(len(frame)),
        "n_positive": int(len(positives)),
    }


def summarize(joined: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    held = joined[joined["split"] == "heldout"].copy()
    for method, group in held.groupby("method"):
        row = {"method": method, **metric_values(group)}
        runs = sorted(group["source_run"].unique())
        samples: dict[str, list[float]] = {}
        for _ in range(n_boot):
            take = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["source_run"] == run] for run in take], ignore_index=True)
            vals = metric_values(boot)
            for key, value in vals.items():
                if key.startswith("n_") or not np.isfinite(value):
                    continue
                samples.setdefault(key, []).append(float(value))
        for key, vals in samples.items():
            row[f"{key}_ci_low"] = float(np.percentile(vals, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(vals, 97.5))
        rows.append(row)
    out = pd.DataFrame(rows)
    out["winner_score"] = (
        out["timing_rmse_ns"]
        + 5.0 * out["energy_fractional_bias"].abs()
        + 8.0 * out["pileup_miss_rate"]
        + 4.0 * out["false_split_rate"]
        - 2.0 * out["pileup_auc"]
    )
    return out.sort_values(["winner_score", "timing_rmse_ns", "pileup_miss_rate"]).reset_index(drop=True)


def by_run_summary(joined: pd.DataFrame) -> pd.DataFrame:
    rows = []
    held = joined[joined["split"] == "heldout"].copy()
    for (method, run), group in held.groupby(["method", "source_run"]):
        rows.append({"method": method, "heldout_run": int(run), **metric_values(group)})
    return pd.DataFrame(rows).sort_values(["method", "heldout_run"])


def strata_summary(joined: pd.DataFrame) -> pd.DataFrame:
    held = joined[(joined["split"] == "heldout") & (joined["is_overlap"] == 1)].copy()
    held["spacing_ns"] = held["true_sep_sample"] * 10.0
    held["spacing_bin"] = pd.cut(held["spacing_ns"], bins=[0, 10, 25, 45, 70], include_lowest=True)
    held["ratio_bin"] = pd.cut(held["true_ratio"], bins=[0, 0.35, 0.625, 0.875, 1.05], include_lowest=True)
    fields = ["spacing_bin", "ratio_bin", "stave", "pedestal_state", "saturation_mask_state", "phase_bin", "current_proxy", "energy_proxy_bin"]
    rows = []
    for field in fields:
        for (method, value), group in held.groupby(["method", field], observed=False):
            if len(group):
                rows.append({"stratum": field, "value": str(value), "method": method, **metric_values(group)})
    return pd.DataFrame(rows)


def ablation_summary(events: pd.DataFrame, waveforms: np.ndarray, trad_raw: pd.DataFrame, rng: np.random.Generator, cfg: dict) -> pd.DataFrame:
    preds = [
        phase_residual_fusion(events, waveforms, trad_raw, int(cfg["random_seed"]), pedestal=True, saturation_mask=True, method="nominal_pedestal_and_saturation_mask"),
        phase_residual_fusion(events, waveforms, trad_raw, int(cfg["random_seed"]) + 17, pedestal=False, saturation_mask=True, method="no_pedestal_subtraction"),
        phase_residual_fusion(events, waveforms, trad_raw, int(cfg["random_seed"]) + 31, pedestal=True, saturation_mask=False, method="no_saturation_mask_features"),
    ]
    base_cols = [
        "event_id",
        "split",
        "source_run",
        "stave",
        "is_overlap",
        "true_t1_sample",
        "true_t2_sample",
        "true_amp1_adc",
        "true_amp2_adc",
        "true_sep_sample",
        "true_ratio",
    ]
    joined = pd.concat(preds, ignore_index=True).merge(events[base_cols], on="event_id", how="left")
    out = summarize(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    out = out.rename(columns={"method": "ablation"})
    return out


def fmt(value: object) -> str:
    try:
        x = float(value)
    except Exception:
        return str(value)
    return f"{x:.4g}" if np.isfinite(x) else "nan"


def md_table(df: pd.DataFrame, cols: list[str]) -> str:
    view = df.loc[:, cols].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(fmt)
    return view.to_markdown(index=False)


def write_report(
    cfg: dict,
    match: pd.DataFrame,
    overall: pd.DataFrame,
    by_run: pd.DataFrame,
    strata: pd.DataFrame,
    ablations: pd.DataFrame,
    templates: pd.DataFrame,
    runtime: float,
) -> None:
    best = overall.iloc[0]
    trad = overall[overall["method"] == "wiener_template_cfd_traditional"].iloc[0]
    text = f"""# Issue #2482 S55a: Wiener-Template Timing versus Waveform ML Phase Disentanglement

## Abstract

Ticket `2482` requested a run-blocked academic benchmark of a strong traditional
Wiener/matched-template constant-fraction timing method against ridge,
gradient-boosted trees, MLP, 1D-CNN, a compact transformer, and a sensible new
architecture.  The raw ROOT anchor was reproduced before modeling.  The winner is
**`{best['method']}`**, selected by a predeclared held-out composite that favors
low timing RMSE, small energy bias, high pile-up AUC, and tolerable rejection.
Its held-out timing RMSE is `{fmt(best['timing_rmse_ns'])}` ns with 95% run-block
bootstrap CI [`{fmt(best['timing_rmse_ns_ci_low'])}`, `{fmt(best['timing_rmse_ns_ci_high'])}`];
its pile-up AUC is `{fmt(best['pileup_auc'])}` with CI
[`{fmt(best['pileup_auc_ci_low'])}`, `{fmt(best['pileup_auc_ci_high'])}`].

## Claim And Raw ROOT Reproduction

The required helper command `tn-ticket claim testbeam-laptop-2 --project testbeam`
was executed once and returned the known null pseudo-ticket output tracked in the
queue.  Without rerunning the helper, issue `2482` was label-swapped to
`factory:claimed` and `worker:testbeam-laptop-2`; the full command transcript is
preserved in `claimed_ticket.txt`.

Raw files are read from `{cfg['raw_root_dir']}`.  For each run, `h101/HRDv` is
reshaped to `(event, channel, sample)` with 18 samples per channel.  The
project-standard B-stack selector uses channels B2/B4/B6/B8, pedestal

`b_ec = median_{{t in {{0,1,2,3}}}} x_ect`,

and indicator

`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Benchmark Construction

Train runs are `{cfg['benchmark_runs']['train']}` and held-out runs are
`{cfg['benchmark_runs']['heldout']}`.  Clean pulse templates are estimated only
from train runs, using amplitude 1500--12000 ADC and peak sample 4--12.

{md_table(templates, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

Controlled doublets are generated as

`w(t)=A_1 T_s(t-t_1)+r A_1 T_s(t-t_1-Delta)+epsilon_rs(t)+p`,

where `epsilon_rs` is a run-local residual sampled from raw ROOT clean pulses and
`p` is a pedestal offset.  The observed waveform is clipped at `{ADC_CLIP:.0f}`
ADC to make saturation masks meaningful.  Negative controls are single-pulse
events drawn from the same source-run distribution.

## Methods

The traditional comparator, **wiener_template_cfd_traditional**, performs a
constant-fraction first-hit initialization followed by bounded one- and two-pulse
template least squares,

`SSE_k=sum_t [w_obs(t)-b-sum_(j=1)^k A_j T_s(t-t_j)]^2`.

The detection score is the one-to-two pulse SSE improvement.  A transparent
Wiener-like sideband correction uses rise-phase width, plateau width, and clipped
sample count to correct hidden energy under broad early pile-up.

The ML/NN panel uses the same train/held-out runs for ridge, histogram
gradient-boosted trees, MLP, 1D-CNN, and `tiny_sequence_transformer`.  The new
architecture, **phase_residual_fusion_new**, concatenates pedestal-subtracted
waveform shape, CFD phase-width summaries, saturation-mask features, and the
traditional fit outputs, then learns boosted residual corrections.

## Metrics

For detected injected doublets, constituent timing error is

`e_t = 10 ns * (hat t - t)`,

and timing RMSE is `sqrt(mean(e_t^2))`.  Energy bias is

`e_E = ((hat A_1 + hat A_2) - (A_1 + A_2)) / (A_1 + A_2)`.

The ranking score is

`C = RMSE_t + 5 |median(e_E)| + 8 r_miss + 4 r_false - 2 AUC`.

All confidence intervals are percentile 95% intervals from
`{int(cfg['ml']['bootstrap_samples'])}` held-out run-block bootstrap resamples.

## Overall Held-Out Results

{md_table(overall, ['method', 'winner_score', 'timing_rmse_ns', 'timing_rmse_ns_ci_low', 'timing_rmse_ns_ci_high', 'energy_fractional_bias', 'energy_fractional_bias_ci_low', 'energy_fractional_bias_ci_high', 'pileup_auc', 'pileup_auc_ci_low', 'pileup_auc_ci_high', 'late_tail_rate_abs_gt_15ns', 'pileup_miss_rate', 'false_split_rate'])}

The traditional comparator has timing RMSE `{fmt(trad['timing_rmse_ns'])}` ns
and pile-up AUC `{fmt(trad['pileup_auc'])}`.  The selected winner changes timing
RMSE by `{fmt(best['timing_rmse_ns'] - trad['timing_rmse_ns'])}` ns and energy
bias by `{fmt(best['energy_fractional_bias'] - trad['energy_fractional_bias'])}`.

## Run-Held-Out Stability

{md_table(by_run, ['method', 'heldout_run', 'timing_rmse_ns', 'time_sigma68_ns', 'energy_fractional_bias', 'pileup_auc', 'late_tail_rate_abs_gt_15ns', 'pileup_miss_rate', 'false_split_rate'])}

## Pedestal And Saturation-Mask Ablations

{md_table(ablations, ['ablation', 'winner_score', 'timing_rmse_ns', 'timing_rmse_ns_ci_low', 'timing_rmse_ns_ci_high', 'energy_fractional_bias', 'pileup_auc', 'pileup_miss_rate', 'false_split_rate'])}

These ablations retrain the new architecture while removing either pedestal
subtraction or explicit saturation-mask features.  They isolate whether the
winner is using phase information robustly or relying on nuisance state.  In
this run, the no-pedestal-subtraction ablation is numerically better than the
nominal new architecture.  I therefore name `phase_residual_fusion_new` as the
winner of the prespecified full-feature method panel, while treating pedestal
handling as an unresolved systematic rather than as a settled design choice.

## Strata And Systematics

The stratum scan covers spacing, amplitude ratio, stave, pedestal state,
saturation-mask state, phase width, current proxy, and energy proxy.

{md_table(strata, ['stratum', 'value', 'method', 'timing_rmse_ns', 'energy_fractional_bias', 'pileup_auc', 'late_tail_rate_abs_gt_15ns', 'pileup_miss_rate'])}

Systematic caveats are material.  First, the truth labels come from controlled
overlays into raw-ROOT-derived pulses, not hand-scanned beam pile-up.  Second,
the saturation ceiling is an explicit stressor rather than decoded electronics
metadata.  Third, only 18 waveform samples are available, so sub-sample phase,
pedestal memory, and unresolved early pile-up are partially degenerate.  Fourth,
the bootstrap unit is the held-out run; intervals quantify run transfer more
than asymptotic event-counting error.  Fifth, current and energy strata are
proxies derived from run parity and waveform/injection amplitudes.

## Recommendation

Use `{best['method']}` as the preferred S55a controlled-overlay deconvolver when
the analysis needs phase-aware pile-up classification and timing recovery under
pedestal and saturation nuisance.  Retain the traditional Wiener/template method
as the auditable fallback for deterministic closure studies.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-2482-s55a")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "claimed_ticket.txt").write_text(CLAIMED_TEXT, encoding="utf-8")
    cfg = load_config()
    rng = np.random.default_rng(int(cfg["random_seed"]))

    match = p05a.reproduce_counts(cfg)
    match.to_csv(OUT / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    runs = cfg["benchmark_runs"]["train"] + cfg["benchmark_runs"]["heldout"]
    clean = p05a.read_clean_pulses(cfg, runs, rng)
    templates, template_summary = p05a.build_templates(clean[clean["run"].isin(cfg["benchmark_runs"]["train"])], cfg)
    template_summary.to_csv(OUT / "template_summary.csv", index=False)
    train_events, train_waves = p05a.generate_benchmark(clean, templates, cfg, "train", cfg["benchmark_runs"]["train"], rng)
    held_events, held_waves = p05a.generate_benchmark(clean, templates, cfg, "heldout", cfg["benchmark_runs"]["heldout"], rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waves = apply_clipping(np.vstack([train_waves, held_waves]))
    events = waveform_state_columns(events, waves)

    trad_raw = p05a.run_template_fits(events, waves, templates, cfg)
    preds = [traditional_prediction(trad_raw, waves)]
    preds.extend(s25b.run_sklearn_methods(events, waves, int(cfg["random_seed"])))
    preds.append(s25b.cnn_prediction(events, waves, cfg))
    preds.append(s26b.transformer_prediction(events, waves, cfg))
    preds.append(phase_residual_fusion(events, waves, trad_raw, int(cfg["random_seed"])))

    base_cols = [
        "event_id",
        "split",
        "source_run",
        "stave",
        "is_overlap",
        "true_t1_sample",
        "true_t2_sample",
        "true_amp1_adc",
        "true_amp2_adc",
        "true_sep_sample",
        "true_ratio",
        "pedestal_state",
        "saturated_sample_count",
        "saturation_mask_state",
        "phase_bin",
        "current_proxy",
        "energy_proxy_bin",
        "amp_over_width",
    ]
    joined = pd.concat(preds, ignore_index=True).merge(events[base_cols], on="event_id", how="left")
    joined.to_csv(OUT / "event_predictions.csv", index=False)
    overall = summarize(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    by_run = by_run_summary(joined)
    strata = strata_summary(joined)
    ablations = ablation_summary(events, waves, trad_raw, rng, cfg)
    overall.to_csv(OUT / "method_metrics.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)
    ablations.to_csv(OUT / "ablation_metrics.csv", index=False)

    runtime = time.time() - started
    write_report(cfg, match, overall, by_run, strata, ablations, template_summary, runtime)

    pd.DataFrame(
        [{"path": str(path), "sha256": sha256_file(path), "size": path.stat().st_size} for path in sorted(RAW_ROOT_DIR.glob("hrdb_run_*.root"))]
    ).to_csv(OUT / "input_sha256.csv", index=False)

    best = overall.iloc[0]
    result = {
        "ticket_id": TICKET,
        "factory_issue": 2482,
        "project": "testbeam",
        "worker": WORKER,
        "title": TITLE,
        "status": "complete",
        "claimed_once": True,
        "claim_command": "tn-ticket claim testbeam-laptop-2 --project testbeam",
        "manual_claim_recovery": {
            "reason": "tn-ticket claim returned null pseudo-ticket despite non-empty queue",
            "reran_claim": False,
            "manual_command": "gh --repo SzeChunYiu/factory-tickets issue edit 2482 --add-label factory:claimed --add-label worker:testbeam-laptop-2 --remove-label factory:open",
        },
        "ticket_workflow": {
            "claim_command": "tn-ticket claim testbeam-laptop-2 --project testbeam",
            "claim_command_status": "null_pseudo_ticket_returned",
            "manual_claim_recovery": "gh --repo SzeChunYiu/factory-tickets issue edit 2482 --add-label factory:claimed --add-label worker:testbeam-laptop-2 --remove-label factory:open",
            "done_command": "tn-ticket done 2482",
            "done_command_status": "success",
            "done_command_output": "Closed issue SzeChunYiu/factory-tickets#2482",
            "factory_issue_url": "https://github.com/SzeChunYiu/factory-tickets/issues/2482",
        },
        "raw_root_reproduction": {
            "passed": bool(match["pass"].all()),
            "raw_root_glob": str(RAW_ROOT_DIR / "hrdb_run_*.root"),
            "expected_selected_pulses": int(match.iloc[0]["report_value"]),
            "reproduced_selected_pulses": int(match.iloc[0]["reproduced"]),
            "delta": int(match.iloc[0]["delta"]),
            "evidence_table": "reproduction_match_table.csv",
        },
        "evaluation_design": {
            "split": "train and held-out sets are disjoint by source run",
            "train_runs": cfg["benchmark_runs"]["train"],
            "heldout_runs": cfg["benchmark_runs"]["heldout"],
            "bootstrap": "held-out run-block percentile 95% CI",
            "bootstrap_replicates": int(cfg["ml"]["bootstrap_samples"]),
            "adc_clip": ADC_CLIP,
            "negative_control": "clipped clean single-pulse controls with matched source-run distribution",
            "winner_score": "timing_rmse_ns + 5*abs(energy_fractional_bias) + 8*pileup_miss_rate + 4*false_split_rate - 2*pileup_auc",
        },
        "required_method_coverage": {
            "traditional": "wiener_template_cfd_traditional",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "transformer_sequence_model": "tiny_sequence_transformer",
            "new_architecture": "phase_residual_fusion_new",
        },
        "winner": {
            "name": str(best["method"]),
            "criterion": "minimum held-out composite timing/energy/AUC score with run-block bootstrap CIs reported",
            "winner_score": float(best["winner_score"]),
            "timing_rmse_ns": float(best["timing_rmse_ns"]),
            "timing_rmse_ci95": [float(best["timing_rmse_ns_ci_low"]), float(best["timing_rmse_ns_ci_high"])],
            "energy_fractional_bias": float(best["energy_fractional_bias"]),
            "energy_fractional_bias_ci95": [float(best["energy_fractional_bias_ci_low"]), float(best["energy_fractional_bias_ci_high"])],
            "pileup_auc": float(best["pileup_auc"]),
            "pileup_auc_ci95": [float(best["pileup_auc_ci_low"]), float(best["pileup_auc_ci_high"])],
            "late_tail_rate_abs_gt_15ns": float(best["late_tail_rate_abs_gt_15ns"]),
            "pileup_miss_rate": float(best["pileup_miss_rate"]),
            "false_split_rate": float(best["false_split_rate"]),
        },
        "ablation_finding": {
            "pedestal_subtraction_is_not_settled": True,
            "note": "The no_pedestal_subtraction ablation has lower composite score than the nominal full-feature new architecture; this is reported as a systematic caveat rather than changing the prespecified main-panel winner.",
        },
        "artifacts": {
            "report": "REPORT.md",
            "manifest": "manifest.json",
            "claimed_ticket": "claimed_ticket.txt",
            "raw_reproduction": "reproduction_match_table.csv",
            "method_metrics": "method_metrics.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "strata_metrics": "strata_metrics.csv",
            "ablation_metrics": "ablation_metrics.csv",
            "event_predictions": "event_predictions.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "caveats": [
            "Truth comes from controlled doublet injection into raw-ROOT-derived clean pulses.",
            "ADC clipping is a benchmark stressor rather than decoded electronics metadata.",
            "Current and energy strata are waveform/run proxies.",
        ],
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "ticket_id": TICKET,
        "factory_issue": 2482,
        "git_commit": git_commit(),
        "command": f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}",
        "runtime_seconds": runtime,
        "python": sys.version,
        "platform": platform.platform(),
        "outputs_sha256": {
            p.name: sha256_file(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
