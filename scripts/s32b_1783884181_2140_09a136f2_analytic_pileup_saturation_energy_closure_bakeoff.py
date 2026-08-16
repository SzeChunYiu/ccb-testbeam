#!/usr/bin/env python3
"""S32b analytic pile-up saturation energy-closure bakeoff."""

from __future__ import annotations

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
from sklearn.multioutput import MultiOutputRegressor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402
import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as base  # noqa: E402
import s26b_1783798536_2368_2ce12433_saturation_energy_recovery_architecture_bakeoff as s26b  # noqa: E402


TICKET = "1783884181.2140.09a136f2"
TITLE = "S32b analytic pile-up saturation energy-closure bakeoff"
SLUG = "s32b_analytic_pileup_saturation_energy_closure_bakeoff"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")
WORKER = "testbeam-laptop-3"
ADC_CLIP = 11800.0


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def load_config() -> dict:
    cfg = base.load_base_config()
    cfg.update(
        {
            "study_id": "S32b",
            "ticket_id": TICKET,
            "title": TITLE,
            "worker": WORKER,
            "raw_root_dir": str(RAW_ROOT_DIR),
            "output_dir": str(OUT),
            "random_seed": 2026071212,
            "max_clean_pulses_per_run_stave": 96,
            "injected_per_train_run": 58,
            "clean_per_train_run": 58,
            "injected_per_heldout_run": 78,
            "clean_per_heldout_run": 78,
        }
    )
    cfg["ml"].update(
        {
            "bootstrap_samples": 400,
            "cnn_epochs": 90,
            "cnn_channels": 12,
            "max_iter": 260,
        }
    )
    return cfg


def apply_adc_clipping(waveforms: np.ndarray) -> np.ndarray:
    """Apply the ticket-local saturation ceiling after pedestal/noise injection."""
    return np.minimum(np.asarray(waveforms, dtype=float), ADC_CLIP)


def saturation_features(waveforms: np.ndarray) -> np.ndarray:
    baseline = np.median(waveforms[:, :4], axis=1)
    corr = waveforms - baseline[:, None]
    sat = waveforms >= (ADC_CLIP - 1e-6)
    sat_count = sat.sum(axis=1).astype(float)
    sat_frac = sat_count / waveforms.shape[1]
    peak = np.maximum(corr.max(axis=1), 1.0)
    area = corr.sum(axis=1)
    early_area = corr[:, 4:9].sum(axis=1)
    late_area = corr[:, 9:].sum(axis=1)
    tail_frac = late_area / np.maximum(area, 1.0)
    plateau_width = (corr > 0.94 * peak[:, None]).sum(axis=1).astype(float)
    clip_depth_proxy = np.maximum(area / np.maximum(peak, 1.0) - 3.7, 0.0)
    return np.column_stack(
        [
            sat_count,
            sat_frac,
            np.log1p(np.maximum(peak, 0.0)),
            area / np.maximum(peak, 1.0),
            early_area / np.maximum(area, 1.0),
            tail_frac,
            plateau_width,
            clip_depth_proxy,
        ]
    )


def saturation_aware_traditional_prediction(trad: pd.DataFrame, waveforms: np.ndarray) -> pd.DataFrame:
    pred = base.template_prediction(trad)
    sf = saturation_features(waveforms)
    sat_count = sf[:, 0]
    tail_frac = np.clip(sf[:, 5], -0.5, 1.5)
    plateau_width = sf[:, 6]
    correction = 1.0 + 0.018 * sat_count + 0.035 * np.maximum(plateau_width - 2.0, 0.0) + 0.06 * np.maximum(tail_frac, 0.0)
    correction = np.clip(correction, 1.0, 1.42)
    pred["amp1_adc"] = pred["amp1_adc"].to_numpy(float) * correction
    pred["amp2_adc"] = pred["amp2_adc"].to_numpy(float) * correction
    pred["method"] = "analytic_clipped_template_sideband_traditional"
    return pred


def saturation_residual_fusion_new(
    events: pd.DataFrame, waveforms: np.ndarray, trad: pd.DataFrame, seed: int
) -> pd.DataFrame:
    x0 = base.features(waveforms)
    sf = saturation_features(waveforms)
    trad_cols = trad[["trad_score", "trad_t1_sample", "trad_t2_sample", "trad_amp1_adc", "trad_amp2_adc"]].to_numpy(float)
    trad_cols = np.nan_to_num(trad_cols, nan=0.0, posinf=0.0, neginf=0.0)
    x = np.hstack([x0, sf, trad_cols])
    y_class = events["is_overlap"].to_numpy(int)
    y_reg, max_amp = base.regression_targets(events, waveforms)
    train = events["split"].to_numpy() == "train"
    pos_train = train & (y_class == 1)
    clf = HistGradientBoostingClassifier(
        max_iter=95, learning_rate=0.055, l2_regularization=0.025, random_state=seed + 30
    )
    reg = MultiOutputRegressor(
        HistGradientBoostingRegressor(
            max_iter=95, learning_rate=0.055, l2_regularization=0.025, random_state=seed + 31
        )
    )
    clf.fit(x[train], y_class[train])
    reg.fit(x[pos_train], y_reg[pos_train])
    return base.as_prediction(
        events,
        clf.predict_proba(x)[:, 1],
        reg.predict(x),
        max_amp,
        "saturation_residual_fusion_new",
    )


def add_clip_columns(events: pd.DataFrame, waveforms: np.ndarray) -> pd.DataFrame:
    out = events.copy()
    sf = saturation_features(waveforms)
    out["saturated_sample_count"] = sf[:, 0].astype(int)
    out["clip_fraction"] = sf[:, 1]
    out["plateau_width"] = sf[:, 6]
    out["pedestal_state"] = np.where(np.abs(np.median(waveforms[:, :4], axis=1)) > 45.0, "shifted", "nominal")
    out["morphology_state"] = np.where(sf[:, 5] > np.nanmedian(sf[:, 5]), "late_tail_high", "late_tail_low")
    out["pid_proxy_class"] = np.where(
        (out["stave"].isin(["B2", "B4"])) & ((out["true_amp1_adc"] + out["true_amp2_adc"]) > 9000.0),
        "inner_high_charge",
        "other",
    )
    return out


def energy_strata_summary(joined: pd.DataFrame) -> pd.DataFrame:
    held = joined[(joined["split"] == "heldout") & (joined["is_overlap"] == 1)].copy()
    held["spacing_ns"] = held["true_sep_sample"] * 10.0
    held["spacing_bin"] = pd.cut(held["spacing_ns"], bins=[0, 10, 25, 45, 70], include_lowest=True)
    held["ratio_bin"] = pd.cut(held["true_ratio"], bins=[0, 0.35, 0.625, 0.875, 1.05], include_lowest=True)
    held["saturation_bin"] = pd.cut(
        held["saturated_sample_count"], bins=[-0.5, 0.5, 2.5, 5.5, 18.5], labels=["0", "1-2", "3-5", "6+"]
    )
    fields = ["spacing_bin", "ratio_bin", "saturation_bin", "pedestal_state", "morphology_state", "pid_proxy_class", "stave"]
    rows = []
    for field in fields:
        for (method, value), group in held.groupby(["method", field], observed=False):
            if len(group) == 0:
                continue
            rows.append({"stratum": field, "value": str(value), "method": method, **base.metric_values(group)})
    return pd.DataFrame(rows)


def winner_table(overall: pd.DataFrame) -> pd.DataFrame:
    out = overall.copy()
    out["winner_score"] = (
        out["energy_fractional_sigma68"]
        + 0.20 * out["energy_fractional_bias"].abs()
        + 0.008 * out["time_sigma68_ns"]
        + 0.04 * out["pileup_miss_rate"]
        + 0.04 * out["false_split_rate"]
    )
    return out.sort_values(["winner_score", "energy_fractional_sigma68", "time_sigma68_ns"]).reset_index(drop=True)


def fmt(x: object) -> str:
    try:
        val = float(x)
    except Exception:
        return str(x)
    return f"{val:.4g}" if np.isfinite(val) else "nan"


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
    ranked: pd.DataFrame,
    by_run: pd.DataFrame,
    strata: pd.DataFrame,
    templates: pd.DataFrame,
    winner: str,
    runtime: float,
) -> None:
    best = ranked.iloc[0]
    trad = ranked[ranked["method"] == "analytic_clipped_template_sideband_traditional"].iloc[0]
    text = f"""# S32b: Analytic Pile-up Saturation Energy-Closure Bakeoff

## Abstract

Ticket `{TICKET}` asks for an academic-grade comparison of a strong traditional
multi-pulse analytic method against ridge, gradient-boosted trees, MLP, 1D-CNN,
transformer sequence models, and a sensible new architecture for energy
reconstruction under pile-up and ADC saturation.  The worker is `{WORKER}`.  The
winner is **`{winner}`**, selected by held-out run-block energy closure:
fractional energy sigma68 `{fmt(best['energy_fractional_sigma68'])}` with 95%
CI [`{fmt(best['energy_fractional_sigma68_ci_low'])}`,
`{fmt(best['energy_fractional_sigma68_ci_high'])}`].  Its composite score is
`{fmt(best['winner_score'])}`.

## Raw ROOT Reproduction

Raw files are read from `{cfg['raw_root_dir']}`.  For each run, `h101/HRDv` is
reshaped to `(event, channel, sample)` with 18 samples per channel.  The B-stack
selection uses B2/B4/B6/B8, pedestal

`b_{{ec}} = median_{{t in {{0,1,2,3}}}} x_{{ect}}`,

and selected-pulse indicator

`I_{{ec}} = 1[max_t(x_{{ect}} - b_{{ec}}) > 1000 ADC]`.

The reproduced number is the exact raw-ROOT anchor before any model fitting.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Data-Generating Benchmark

Clean train-run pulse templates are built only from train runs
`{cfg['benchmark_runs']['train']}`.  Candidate pulses have amplitude
1500--12000 ADC and peak sample 4--12.  For stave `s`, the normalized and
CFD-aligned template is

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

{md_table(templates, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

Controlled doublets are generated as

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_{{r,s}}(t) + p`,

where `epsilon` is a run-local residual sampled from raw ROOT clean pulses and
`p` is a pedestal offset.  The observed waveform supplied to every method is
then clipped as

`w_obs(t) = min(w(t), {ADC_CLIP:.0f})`.

The held-out runs `{cfg['benchmark_runs']['heldout']}` are never used for
template estimation or ML fitting.  Negative controls are clipped single-pulse
events sampled from the same held-out run families.

## Methods

The traditional comparator is **analytic_clipped_template_sideband_traditional**.
It fits one- and two-pulse template models by bounded least squares,

`SSE_k = sum_t [w_obs(t) - b - sum_{{j=1}}^k A_j T_s(t-t_j)]^2`,

using constrained positive amplitudes, bounded pedestal, and fixed separation
grid.  It then applies a deterministic saturation sideband correction to the
fitted amplitudes,

`A'_j = A_j [1 + 0.018 n_clip + 0.035 max(W_plateau-2,0) + 0.06 max(f_tail,0)]`,

truncated to `[1, 1.42]`.  This is intentionally transparent: it uses only
plateau width, clipped-sample count, and late-tail sidebands available in the
observed waveform.

The ML panel contains ridge, histogram gradient-boosted trees, MLP, and compact
1D-CNN heads trained on identical run splits.  The transformer sequence model is
`tiny_sequence_transformer`, a one-layer self-attention encoder over the
18-sample waveform.  The new architecture is **saturation_residual_fusion_new**:
it concatenates waveform shape summaries, clipping sidebands, and the analytic
fit outputs, then learns residual boosted-tree corrections for detection and
constituent timing/amplitude.

## Metrics and Uncertainty

For accepted injected doublets, total energy closure is

`e_E = ((hat A_1 + hat A_2) - (A_1 + A_2)) / (A_1 + A_2)`,

and constituent timing error is

`e_t = 10 ns * (hat t - t)`.

The robust resolution is

`sigma_68(e) = [Q_84(e) - Q_16(e)] / 2`.

The predeclared score is

`C_m = sigma_E + 0.20 |bias_E| + 0.008 sigma_t + 0.04 r_miss + 0.04 r_false`,

where miss rate is the failed injected-doublet fraction and false rate is the
clean-control split fraction.  Confidence intervals are percentile 95% intervals
from `{int(cfg['ml']['bootstrap_samples'])}` bootstrap resamples of held-out
runs.

## Overall Held-Out Results

{md_table(ranked, ['method', 'winner_score', 'energy_fractional_bias', 'energy_fractional_sigma68', 'energy_fractional_sigma68_ci_low', 'energy_fractional_sigma68_ci_high', 'time_bias_ns', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high', 'pileup_miss_rate', 'false_split_rate'])}

The traditional comparator has energy sigma68 `{fmt(trad['energy_fractional_sigma68'])}`
and score `{fmt(trad['winner_score'])}`.  The selected winner changes energy
sigma68 by `{fmt(best['energy_fractional_sigma68'] - trad['energy_fractional_sigma68'])}`
and timing sigma68 by `{fmt(best['time_sigma68_ns'] - trad['time_sigma68_ns'])}` ns.

## Run-Held-Out Stability

{md_table(by_run, ['method', 'heldout_run', 'energy_fractional_bias', 'energy_fractional_sigma68', 'time_bias_ns', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'])}

## Strata and Systematics

The stratum scan covers pile-up spacing, saturated sample count, pedestal state,
pulse morphology, amplitude ratio, stave, and a PID proxy class.

{md_table(strata, ['stratum', 'value', 'method', 'energy_fractional_bias', 'energy_fractional_sigma68', 'time_bias_ns', 'time_sigma68_ns', 'pileup_miss_rate'])}

## Caveats

The caveats are material.  First, pile-up truth is from controlled
overlays into raw-ROOT-derived residuals; it validates reconstruction under known
truth but not the true beam pile-up rate.  Second, the ADC clipping level is a
benchmark stressor rather than a decoded electronics flag.  Third, only 18
samples are available, so pedestal memory and late recovery tails can be partly
degenerate with broad second pulses.  Fourth, the bootstrap unit is the held-out
run, giving run-transfer intervals rather than event-counting intervals.  Fifth,
the PID class is a waveform/support proxy, not an external particle label.

## Recommendation

Use `{winner}` as the preferred S32b controlled-overlay energy-closure method
when the analysis goal is saturated doublet recovery with run-held-out
uncertainty propagation.  The analytic clipped-template method remains the
auditable fallback when deterministic extrapolation is more important than the
observed held-out score gain.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s32b")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "claimed_ticket.txt").write_text(TICKET + f"\n# {TITLE}\n", encoding="utf-8")
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
    waves_unclipped = np.vstack([train_waves, held_waves])
    waves = apply_adc_clipping(waves_unclipped)
    events = add_clip_columns(events, waves)

    trad_raw = p05a.run_template_fits(events, waves, templates, cfg)
    preds = [saturation_aware_traditional_prediction(trad_raw, waves)]
    preds.extend(base.run_sklearn_methods(events, waves, int(cfg["random_seed"])))
    preds.append(base.cnn_prediction(events, waves, cfg))
    preds.append(s26b.transformer_prediction(events, waves, cfg))
    preds.append(saturation_residual_fusion_new(events, waves, trad_raw, int(cfg["random_seed"])))

    all_pred = pd.concat(preds, ignore_index=True)
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
        "saturated_sample_count",
        "clip_fraction",
        "plateau_width",
        "pedestal_state",
        "morphology_state",
        "pid_proxy_class",
    ]
    joined = all_pred.merge(events[base_cols], on="event_id", how="left")
    joined.to_csv(OUT / "event_predictions.csv", index=False)
    overall = base.summarize(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    ranked = winner_table(overall)
    by_run = base.by_run_summary(joined)
    strata = energy_strata_summary(joined)
    overall.to_csv(OUT / "method_metrics.csv", index=False)
    ranked.to_csv(OUT / "winner_ranked_metrics.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)

    winner = str(ranked.iloc[0]["method"])
    runtime = time.time() - started
    write_report(cfg, match, overall, ranked, by_run, strata, template_summary, winner, runtime)

    input_rows = []
    for path in sorted(RAW_ROOT_DIR.glob("hrdb_run_*.root")):
        input_rows.append({"path": str(path), "sha256": base.sha256_file(path), "size": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

    result = {
        "ticket_id": TICKET,
        "project": "testbeam",
        "worker": WORKER,
        "title": TITLE,
        "status": "complete",
        "claimed_once": True,
        "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
        "claimed_ticket_text": "S32b analytic pile-up saturation energy-closure bakeoff",
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
            "adc_clip": ADC_CLIP,
            "bootstrap": "held-out run-block percentile 95% CI",
            "bootstrap_replicates": int(cfg["ml"]["bootstrap_samples"]),
            "negative_control": "clipped clean single-pulse controls with matched source-run distribution",
            "winner_score": "energy_fractional_sigma68 + 0.20*abs(energy_fractional_bias) + 0.008*time_sigma68_ns + 0.04*pileup_miss_rate + 0.04*false_split_rate",
        },
        "required_method_coverage": {
            "traditional": "analytic_clipped_template_sideband_traditional",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "transformer_sequence_model": "tiny_sequence_transformer",
            "new_architecture": "saturation_residual_fusion_new",
        },
        "winner": {
            "name": winner,
            "criterion": "minimum held-out composite saturation-energy closure score with run-block bootstrap CIs reported",
            "winner_score": float(ranked.iloc[0]["winner_score"]),
            "energy_fractional_bias": float(ranked.iloc[0]["energy_fractional_bias"]),
            "energy_fractional_sigma68": float(ranked.iloc[0]["energy_fractional_sigma68"]),
            "energy_fractional_sigma68_ci95": [
                float(ranked.iloc[0]["energy_fractional_sigma68_ci_low"]),
                float(ranked.iloc[0]["energy_fractional_sigma68_ci_high"]),
            ],
            "time_sigma68_ns": float(ranked.iloc[0]["time_sigma68_ns"]),
            "time_sigma68_ci95": [
                float(ranked.iloc[0]["time_sigma68_ns_ci_low"]),
                float(ranked.iloc[0]["time_sigma68_ns_ci_high"]),
            ],
            "pileup_miss_rate": float(ranked.iloc[0]["pileup_miss_rate"]),
            "false_split_rate": float(ranked.iloc[0]["false_split_rate"]),
        },
        "artifacts": {
            "report": "REPORT.md",
            "manifest": "manifest.json",
            "claimed_ticket": "claimed_ticket.txt",
            "raw_reproduction": "reproduction_match_table.csv",
            "method_metrics": "method_metrics.csv",
            "winner_ranked_metrics": "winner_ranked_metrics.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "strata_metrics": "strata_metrics.csv",
            "event_predictions": "event_predictions.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "caveats": [
            "Truth comes from controlled injections into raw-ROOT-derived clean pulses.",
            "ADC clipping is an explicit benchmark stressor rather than decoded electronics metadata.",
            "Bootstrap CIs resample held-out runs and should be read as run-transfer intervals.",
        ],
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "ticket_id": TICKET,
        "git_commit": git_commit(),
        "command": f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}",
        "runtime_seconds": runtime,
        "python": sys.version,
        "platform": platform.platform(),
        "outputs_sha256": {
            p.name: base.sha256_file(p)
            for p in sorted(OUT.iterdir())
            if p.is_file() and p.name != "manifest.json"
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
