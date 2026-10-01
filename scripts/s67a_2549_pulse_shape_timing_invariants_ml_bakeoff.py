#!/usr/bin/env python3
"""S67a/#2549 pulse-shape timing invariant atlas under pedestal drift and pile-up."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.multioutput import MultiOutputRegressor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402
import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as base  # noqa: E402
import s26b_1783798536_2368_2ce12433_saturation_energy_recovery_architecture_bakeoff as s26b  # noqa: E402


TICKET = "2549"
ISSUE_URL = "https://github.com/SzeChunYiu/factory-tickets/issues/2549"
WORKER = "testbeam-laptop-1"
TITLE = "S67a pulse-shape timing invariants under pedestal drift and pile-up"
SLUG = "s67a_pulse_shape_timing_invariants_ml_bakeoff"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def load_config() -> dict:
    cfg = base.load_base_config()
    cfg.update(
        {
            "study_id": "S67a",
            "ticket_id": TICKET,
            "title": TITLE,
            "worker": WORKER,
            "raw_root_dir": str(RAW_ROOT_DIR),
            "output_dir": str(OUT),
            "random_seed": 2026081701,
            "max_clean_pulses_per_run_stave": 92,
            "injected_per_train_run": 52,
            "clean_per_train_run": 52,
            "injected_per_heldout_run": 72,
            "clean_per_heldout_run": 72,
            "benchmark_runs": {
                "train": [50, 51, 52, 53, 54, 55, 56, 57],
                "heldout": [58, 60, 62, 64, 65],
            },
        }
    )
    cfg["ml"].update({"bootstrap_samples": 400, "cnn_epochs": 90, "cnn_channels": 12, "max_iter": 240})
    return cfg


def timing_sideband_features(waveforms: np.ndarray) -> np.ndarray:
    baseline = np.median(waveforms[:, :4], axis=1)
    corr = waveforms - baseline[:, None]
    amp = np.maximum(corr.max(axis=1), 1.0)
    area = corr.sum(axis=1)
    deriv = np.diff(corr, axis=1, prepend=corr[:, :1])
    pos_deriv = np.maximum(deriv, 0.0).sum(axis=1)
    neg_deriv = np.maximum(-deriv, 0.0).sum(axis=1)
    early = corr[:, 4:8].sum(axis=1)
    core = corr[:, 8:12].sum(axis=1)
    late = corr[:, 12:].sum(axis=1)
    cfd20 = np.array([p05a.cfd_time_one(wf, 0.2) for wf in corr])
    cfd50 = np.array([p05a.cfd_time_one(wf, 0.5) for wf in corr])
    return np.column_stack(
        [
            baseline,
            amp,
            area / amp,
            early / np.maximum(area, 1.0),
            core / np.maximum(area, 1.0),
            late / np.maximum(area, 1.0),
            pos_deriv / amp,
            neg_deriv / amp,
            np.nan_to_num(cfd50 - cfd20, nan=0.0),
            np.argmax(corr, axis=1),
        ]
    )


def derivative_matched_filter_traditional(trad: pd.DataFrame, waveforms: np.ndarray) -> pd.DataFrame:
    pred = base.template_prediction(trad)
    corr = waveforms - np.median(waveforms[:, :4], axis=1)[:, None]
    deriv = np.diff(corr, axis=1, prepend=corr[:, :1])
    sharp = np.maximum(deriv.max(axis=1), 1.0) / np.maximum(corr.max(axis=1), 1.0)
    slew = np.clip((sharp - np.nanmedian(sharp)) * 0.45, -0.35, 0.35)
    pred["t1_sample"] = np.clip(pred["t1_sample"].to_numpy(float) - slew, 0.0, 17.0)
    pred["t2_sample"] = np.clip(pred["t2_sample"].to_numpy(float) - 0.5 * slew, 0.0, 17.0)
    pred["method"] = "cfd_derivative_matched_filter_traditional"
    return pred


def timing_invariant_residual_fusion_new(
    events: pd.DataFrame, waveforms: np.ndarray, trad: pd.DataFrame, seed: int
) -> pd.DataFrame:
    x0 = base.features(waveforms)
    side = timing_sideband_features(waveforms)
    trad_cols = trad[["trad_score", "trad_t1_sample", "trad_t2_sample", "trad_amp1_adc", "trad_amp2_adc"]].to_numpy(float)
    x = np.hstack([x0, side, np.nan_to_num(trad_cols, nan=0.0, posinf=0.0, neginf=0.0)])
    y_class = events["is_overlap"].to_numpy(int)
    y_reg, max_amp = base.regression_targets(events, waveforms)
    train = events["split"].to_numpy() == "train"
    pos_train = train & (y_class == 1)
    clf = HistGradientBoostingClassifier(
        max_iter=95, learning_rate=0.055, l2_regularization=0.025, random_state=seed + 41
    )
    reg = MultiOutputRegressor(
        HistGradientBoostingRegressor(
            max_iter=95, learning_rate=0.055, l2_regularization=0.025, random_state=seed + 42
        )
    )
    clf.fit(x[train], y_class[train])
    reg.fit(x[pos_train], y_reg[pos_train])
    return base.as_prediction(events, clf.predict_proba(x)[:, 1], reg.predict(x), max_amp, "timing_invariant_residual_fusion_new")


def add_pedestal_shape_columns(events: pd.DataFrame, waveforms: np.ndarray) -> pd.DataFrame:
    out = events.copy()
    side = timing_sideband_features(waveforms)
    out["pedestal_adc"] = side[:, 0]
    out["rise_width_sample"] = side[:, 8]
    out["late_fraction"] = side[:, 5]
    out["derivative_balance"] = side[:, 6] - side[:, 7]
    ped_q = pd.qcut(out["pedestal_adc"], q=3, duplicates="drop")
    out["pedestal_state"] = ped_q.astype(str)
    out["phase_state"] = pd.cut(out["true_t1_sample"], bins=[0, 4.5, 6.5, 9.5, 17.5], include_lowest=True)
    out["pileup_state"] = pd.cut(out["true_sep_sample"].fillna(99), bins=[0, 1.5, 3.0, 6.5, 100], labels=["tight", "moderate", "wide", "single"], include_lowest=True)
    return out


def residual_shape_atlas(joined: pd.DataFrame, events: pd.DataFrame, waveforms: np.ndarray) -> pd.DataFrame:
    held_events = events[events["split"] == "heldout"].copy()
    idx = held_events.index.to_numpy(int)
    corr = waveforms[idx] - np.median(waveforms[idx, :4], axis=1)[:, None]
    scale = np.maximum(np.percentile(np.abs(corr), 95, axis=1), 1.0)
    z = corr / scale[:, None]
    ncomp = min(5, z.shape[1])
    pc = PCA(n_components=ncomp, random_state=0).fit_transform(z)
    k = min(4, len(held_events))
    labels = KMeans(n_clusters=k, random_state=7, n_init=20).fit_predict(pc[:, : min(3, ncomp)])
    held_events["shape_cluster"] = labels
    rows = []
    merged = joined.merge(held_events[["event_id", "shape_cluster"]], on="event_id", how="inner")
    for (method, cluster), group in merged.groupby(["method", "shape_cluster"]):
        vals = base.metric_values(group)
        rows.append({"method": method, "shape_cluster": int(cluster), **vals})
    return pd.DataFrame(rows).sort_values(["method", "shape_cluster"])


def timing_strata_summary(joined: pd.DataFrame) -> pd.DataFrame:
    held = joined[joined["split"] == "heldout"].copy()
    held["spacing_ns"] = held["true_sep_sample"] * 10.0
    held["spacing_bin"] = pd.cut(held["spacing_ns"].fillna(999), bins=[0, 15, 30, 65, 1000], labels=["0-15", "15-30", "30-65", "single"], include_lowest=True)
    held["ratio_bin"] = pd.cut(held["true_ratio"].fillna(0), bins=[0, 0.35, 0.625, 0.875, 1.05], include_lowest=True)
    rows = []
    fields = ["spacing_bin", "ratio_bin", "stave", "pedestal_state", "phase_state", "pileup_state"]
    for field in fields:
        for (method, value), group in held.groupby(["method", field], observed=False):
            if len(group) == 0:
                continue
            rows.append({"stratum": field, "value": str(value), "method": method, **base.metric_values(group)})
    return pd.DataFrame(rows)


def winner_table(overall: pd.DataFrame) -> pd.DataFrame:
    out = overall.copy()
    out["winner_score"] = (
        out["time_sigma68_ns"]
        + 0.40 * out["time_bias_ns"].abs()
        + 18.0 * out["pileup_miss_rate"]
        + 18.0 * out["false_split_rate"]
        + 0.8 * out["late_tail_rate_abs_gt_15ns"]
    )
    return out.sort_values(["winner_score", "time_sigma68_ns", "pileup_miss_rate"]).reset_index(drop=True)


def fmt(x: object) -> str:
    try:
        val = float(x)
    except Exception:
        return str(x)
    return f"{val:.4g}" if np.isfinite(val) else "nan"


def md_table(df: pd.DataFrame, cols: list[str], max_rows: int = 80) -> str:
    view = df.loc[:, [c for c in cols if c in df.columns]].head(max_rows).copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(fmt)
    return view.to_markdown(index=False)


def write_report(
    cfg: dict,
    match: pd.DataFrame,
    ranked: pd.DataFrame,
    by_run: pd.DataFrame,
    strata: pd.DataFrame,
    shape: pd.DataFrame,
    templates: pd.DataFrame,
    winner: str,
    runtime: float,
) -> None:
    best = ranked.iloc[0]
    trad = ranked[ranked["method"] == "cfd_derivative_matched_filter_traditional"].iloc[0]
    text = f"""# S67a/#2549: Pulse-Shape Timing Invariants under Pedestal Drift and Pile-up

## Abstract

Ticket `{TICKET}` asks for a raw-ROOT reproduction followed by an academic-grade
benchmark of a strong traditional timing method against ridge, gradient-boosted
trees, MLP, 1D-CNN, and a sequence model/new architecture.  The claimed issue is
{ISSUE_URL}; the worker is `{WORKER}`.  The winner is **`{winner}`** by the
predeclared held-out timing-invariant score.  It has constituent timing sigma68
`{fmt(best['time_sigma68_ns'])}` ns with 95% run-block bootstrap CI
[`{fmt(best['time_sigma68_ns_ci_low'])}`, `{fmt(best['time_sigma68_ns_ci_high'])}`],
pile-up miss rate `{fmt(best['pileup_miss_rate'])}`, and false-split rate
`{fmt(best['false_split_rate'])}`.

## Raw ROOT Reproduction

Raw files are read from `{cfg['raw_root_dir']}`.  For each run, `h101/HRDv` is
reshaped to `(event, channel, sample)` with 18 samples per channel.  The B-stack
selection uses B2/B4/B6/B8 and the pedestal

`b_ec = median_{{t in {{0,1,2,3}}}} x_ect`,

with corrected pulse `y_ect = x_ect - b_ec` and selected-pulse indicator

`I_ec = 1[max_t y_ect > 1000 ADC]`.

The reproduced number is computed directly from raw ROOT before any benchmark
model is fit.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'tolerance', 'pass'])}

## Run Split and Controlled Pile-up

Train runs are `{cfg['benchmark_runs']['train']}` and held-out runs are
`{cfg['benchmark_runs']['heldout']}`.  Clean train pulses define per-stave
templates only on train runs:

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

{md_table(templates, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

For a controlled pile-up event,

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_{{r,s}}(t) + p`,

where `epsilon` is a run-local raw-ROOT residual and `p` is the observed pedestal
state.  Negative controls are clean single-pulse events sampled with the same
run/stave support.  This makes the truth labels controlled while retaining real
baseline, derivative, and residual-shape structure.

## Methods

The traditional comparator is `cfd_derivative_matched_filter_traditional`.  It
starts from a bounded one/two-pulse template fit minimizing

`SSE_k = sum_t [w(t) - b - sum_{{j=1}}^k A_j T_s(t-t_j)]^2`,

then applies a derivative matched-filter slew correction

`t'_j = t_j - alpha_j [max_t Delta w(t) / max_t w(t) - median(sharpness)]`.

The ML panel contains ridge, histogram gradient-boosted trees, MLP, compact
1D-CNN, and `tiny_sequence_transformer`, a one-layer self-attention encoder over
the 18-sample waveform.  The new architecture is
`timing_invariant_residual_fusion_new`: it concatenates waveform features,
pedestal/rise/late-tail sidebands, and the traditional fit outputs, then learns
boosted residual detection and timing corrections on train runs only.

## Metrics and CIs

For detected injected doublets, constituent timing error is

`e_t = 10 ns * (hat t - t_true)`.

The robust timing resolution is

`sigma_68(e_t) = [Q_84(e_t) - Q_16(e_t)] / 2`.

The predeclared score is

`C_m = sigma_t + 0.40 |bias_t| + 18 r_miss + 18 r_false + 0.8 r_|e_t|>15ns`.

Confidence intervals are percentile 95% intervals from
`{int(cfg['ml']['bootstrap_samples'])}` bootstrap resamples of held-out runs.

## Overall Held-Out Results

{md_table(ranked, ['method', 'winner_score', 'time_bias_ns', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high', 'late_tail_rate_abs_gt_15ns', 'pileup_miss_rate', 'false_split_rate', 'energy_fractional_sigma68'])}

The traditional comparator has timing sigma68 `{fmt(trad['time_sigma68_ns'])}` ns
and score `{fmt(trad['winner_score'])}`.  The selected winner changes sigma68 by
`{fmt(best['time_sigma68_ns'] - trad['time_sigma68_ns'])}` ns and the composite
score by `{fmt(best['winner_score'] - trad['winner_score'])}`.

## Run-Held-Out Stability

{md_table(by_run, ['method', 'heldout_run', 'time_bias_ns', 'time_sigma68_ns', 'late_tail_rate_abs_gt_15ns', 'pileup_miss_rate', 'false_split_rate'])}

## Pedestal, Phase, and Pile-up Strata

{md_table(strata, ['stratum', 'value', 'method', 'time_bias_ns', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'], max_rows=120)}

## Shape-Residual Atlas

Held-out normalized residual shapes are embedded with PCA and grouped into four
clusters.  The table reports whether the winning timing invariant remains stable
across residual-shape families rather than only on the aggregate mixture.

{md_table(shape, ['method', 'shape_cluster', 'time_bias_ns', 'time_sigma68_ns', 'late_tail_rate_abs_gt_15ns', 'pileup_miss_rate'], max_rows=80)}

## Systematics and Caveats

The pile-up labels are controlled overlays into real raw-ROOT residuals; they
validate recovery under known truth but do not measure the true beam pile-up
rate.  The pedestal-state strata are empirical quantiles of the first four
samples, not independent electronics telemetry.  The 18-sample readout limits
sub-sample separation information and can confound late tails with broad second
pulses.  Bootstrap CIs resample held-out runs, so they quantify run-transfer
uncertainty rather than event-counting uncertainty.  The shape clusters are
diagnostic unsupervised summaries and should not be interpreted as particle-ID
labels.

## Recommendation

Use `{winner}` for S67a timing-invariant pulse-shape studies when the priority is
run-held-out timing stability under pedestal drift and moderate pile-up.  Retain
`cfd_derivative_matched_filter_traditional` as the auditable fallback for
deterministic checks and systematic variations.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    rng = np.random.default_rng(int(cfg["random_seed"]))

    (OUT / "claimed_ticket.txt").write_text(
        "claim_helper_command: tn-ticket claim testbeam-laptop-1 --project testbeam\n"
        "claim_helper_stdout:\n# null\n\nnull\nnull\n"
        "manual_claim_recovery: gh issue edit 2549 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-1 --remove-label factory:open\n"
        "#2549 NEW S67a pulse-shape timing invariants under pedestal drift and pile-up\n",
        encoding="utf-8",
    )

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
    waves = np.vstack([train_waves, held_waves])
    events = add_pedestal_shape_columns(events, waves)

    trad_raw = p05a.run_template_fits(events, waves, templates, cfg)
    preds = [derivative_matched_filter_traditional(trad_raw, waves)]
    preds.extend(base.run_sklearn_methods(events, waves, int(cfg["random_seed"])))
    preds.append(base.cnn_prediction(events, waves, cfg))
    preds.append(s26b.transformer_prediction(events, waves, cfg))
    preds.append(timing_invariant_residual_fusion_new(events, waves, trad_raw, int(cfg["random_seed"])))

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
        "pedestal_adc",
        "rise_width_sample",
        "late_fraction",
        "derivative_balance",
        "pedestal_state",
        "phase_state",
        "pileup_state",
    ]
    joined = all_pred.merge(events[base_cols], on="event_id", how="left")
    joined.to_csv(OUT / "event_predictions.csv", index=False)
    overall = base.summarize(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    ranked = winner_table(overall)
    by_run = base.by_run_summary(joined)
    strata = timing_strata_summary(joined)
    shape = residual_shape_atlas(joined, events, waves)
    overall.to_csv(OUT / "method_metrics.csv", index=False)
    ranked.to_csv(OUT / "winner_ranked_metrics.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)
    shape.to_csv(OUT / "shape_residual_atlas.csv", index=False)

    winner = str(ranked.iloc[0]["method"])
    runtime = time.time() - started
    write_report(cfg, match, ranked, by_run, strata, shape, template_summary, winner, runtime)

    input_rows = []
    for path in sorted(RAW_ROOT_DIR.glob("hrdb_run_*.root")):
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "size": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

    result = {
        "ticket_id": TICKET,
        "issue_number": 2549,
        "issue_url": ISSUE_URL,
        "project": "testbeam",
        "worker": WORKER,
        "title": TITLE,
        "status": "complete",
        "claim_command": "tn-ticket claim testbeam-laptop-1 --project testbeam",
        "claim_command_ran_once": True,
        "claim_helper_output": {"stdout": "# null\n\nnull\nnull", "note": "manual label recovery used because helper returned null while open tickets existed"},
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
            "negative_control": "clean single-pulse controls with matched source-run distribution",
        },
        "required_method_coverage": {
            "traditional": "cfd_derivative_matched_filter_traditional",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "sequence_model": "tiny_sequence_transformer",
            "new_architecture": "timing_invariant_residual_fusion_new",
        },
        "winner": {
            "name": winner,
            "criterion": "minimum held-out timing-invariant composite score with run-block bootstrap CIs",
            "winner_score": float(ranked.iloc[0]["winner_score"]),
            "time_bias_ns": float(ranked.iloc[0]["time_bias_ns"]),
            "time_sigma68_ns": float(ranked.iloc[0]["time_sigma68_ns"]),
            "time_sigma68_ci95": [
                float(ranked.iloc[0]["time_sigma68_ns_ci_low"]),
                float(ranked.iloc[0]["time_sigma68_ns_ci_high"]),
            ],
            "late_tail_rate_abs_gt_15ns": float(ranked.iloc[0]["late_tail_rate_abs_gt_15ns"]),
            "pileup_miss_rate": float(ranked.iloc[0]["pileup_miss_rate"]),
            "false_split_rate": float(ranked.iloc[0]["false_split_rate"]),
        },
        "artifacts": {
            "report": "REPORT.md",
            "manifest": "manifest.json",
            "raw_reproduction": "reproduction_match_table.csv",
            "method_metrics": "method_metrics.csv",
            "winner_ranked_metrics": "winner_ranked_metrics.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "strata_metrics": "strata_metrics.csv",
            "shape_residual_atlas": "shape_residual_atlas.csv",
            "event_predictions": "event_predictions.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "done_command": "tn-ticket done 2549",
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "ticket_id": TICKET,
        "issue_url": ISSUE_URL,
        "git_commit": git_commit(),
        "command": f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}",
        "runtime_seconds": runtime,
        "python": sys.version,
        "platform": platform.platform(),
        "outputs_sha256": {
            p.name: sha256_file(p)
            for p in sorted(OUT.iterdir())
            if p.is_file() and p.name != "manifest.json"
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
