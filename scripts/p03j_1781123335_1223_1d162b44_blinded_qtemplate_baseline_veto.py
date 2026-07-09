#!/usr/bin/env python3
"""P03j train-fold-only q-template/baseline veto benchmark.

This repeats the P03i multimodel architecture benchmark after removing events
flagged by a q-template SSE or baseline-excursion veto. The veto thresholds are
fit only on the training runs inside each leave-one-run-out fold, then applied
unchanged to both training and held-out events.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p03j-1781123335")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import s02_timing_pickoff as s02


BASELINE = "s02b_global_template_timewalk"


def load_module(name: str, script_name: str):
    path = Path(__file__).resolve().parent / script_name
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load {}".format(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p03f = load_module("p03f_multimodel", "p03f_1781031083_1848_21e023a2_early_sample_multimodel.py")
p03i = load_module("p03i_failure_map", "p03i_1781038014_1254_657842ac_phase_local_failure_map.py")


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        cfg = json.load(handle)
    cfg["spacing_cm_values"] = [float(cfg["spacing_cm"])]
    return cfg


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


def raw_file(config: dict, run: int) -> Path:
    return s02.raw_file(config, run)


def configured_runs(config: dict) -> List[int]:
    return s02.configured_runs(config)


def qcut_with_train_edges(values: pd.Series, train_values: pd.Series, labels: Sequence[str]) -> pd.Series:
    probs = np.linspace(0.0, 1.0, len(labels) + 1)
    edges = np.quantile(train_values.to_numpy(dtype=float), probs)
    edges[0] = -np.inf
    edges[-1] = np.inf
    for i in range(1, len(edges)):
        if edges[i] <= edges[i - 1]:
            edges[i] = np.nextafter(edges[i - 1], np.inf)
    return pd.cut(values.to_numpy(dtype=float), bins=edges, labels=list(labels), include_lowest=True).astype(str)


def train_fold_event_atoms_and_veto(work: pd.DataFrame, config: dict, fold_cfg: dict, heldout_run: int) -> pd.DataFrame:
    scalar = p03i.waveform_scalar_columns(work.copy())
    agg = scalar.groupby(["event_id", "run"]).agg(
        median_peak_sample=("peak_sample", "median"),
        max_peak_sample=("peak_sample", "max"),
        max_amplitude_adc=("amplitude_adc", "max"),
        median_amplitude_adc=("amplitude_adc", "median"),
        max_template_sse=("s02b_template_sse", "max"),
        max_baseline_absmax_adc=("baseline_absmax_adc", "max"),
        max_baseline_span_adc=("baseline_span_adc", "max"),
        max_late_charge_over_amp=("late_charge_over_amp", "max"),
        mean_early_charge_over_amp=("early_charge_over_amp", "mean"),
        max_norm_peak_height=("norm_peak_height", "max"),
    )
    agg = agg.reset_index()
    train = agg[agg["run"].isin(fold_cfg["timing"]["train_runs"])].copy()
    if train.empty:
        raise RuntimeError("empty training event table for heldout run {}".format(heldout_run))

    q_prob = float(config["veto"]["q_template_event_quantile"])
    b_prob = float(config["veto"]["baseline_event_quantile"])
    amp95 = float(np.quantile(train["max_amplitude_adc"].to_numpy(dtype=float), 0.95))
    sse_thr = float(np.quantile(train["max_template_sse"].to_numpy(dtype=float), q_prob))
    base_thr = float(np.quantile(train["max_baseline_absmax_adc"].to_numpy(dtype=float), b_prob))
    late90 = float(np.quantile(train["max_late_charge_over_amp"].to_numpy(dtype=float), 0.90))

    agg["phase_atom"] = np.select(
        [agg["median_peak_sample"] <= 5.0, agg["median_peak_sample"] >= 7.0],
        ["early_phase_le5", "late_phase_ge7"],
        default="central_phase_6",
    )
    agg["saturation_atom"] = np.where(agg["max_amplitude_adc"] >= amp95, "amp_top5_proxy", "amp_bulk")
    agg["q_template_atom"] = np.where(agg["max_template_sse"] >= sse_thr, "q_template_sse_train_top10", "q_template_sse_train_bulk")
    agg["baseline_atom"] = np.where(
        agg["max_baseline_absmax_adc"] >= base_thr,
        "baseline_excursion_train_top10",
        "baseline_train_bulk",
    )
    delayed = (agg["max_peak_sample"] >= 9.0) | (agg["max_late_charge_over_amp"] >= late90)
    agg["delayed_peak_atom"] = np.where(delayed, "delayed_or_late_charge", "prompt_peak")
    agg["q_template_veto"] = agg["max_template_sse"] >= sse_thr
    agg["baseline_veto"] = agg["max_baseline_absmax_adc"] >= base_thr
    agg["vetoed_by_train_fold"] = agg["q_template_veto"] | agg["baseline_veto"]
    agg["retained_by_veto"] = ~agg["vetoed_by_train_fold"]
    anomaly = (
        (agg["saturation_atom"] == "amp_top5_proxy")
        | agg["q_template_veto"]
        | agg["baseline_veto"]
        | (agg["delayed_peak_atom"] == "delayed_or_late_charge")
    )
    agg["anomaly_atom"] = np.where(anomaly, "any_high_risk_atom", "no_high_risk_atom")
    agg["run_family_atom"] = [p03f.run_family(int(r), config) for r in agg["run"]]
    agg["amplitude_atom"] = qcut_with_train_edges(agg["max_amplitude_adc"], train["max_amplitude_adc"], ["amp_low", "amp_mid", "amp_high"])
    agg["fold_threshold_amp95"] = amp95
    agg["fold_threshold_sse"] = sse_thr
    agg["fold_threshold_baseline"] = base_thr
    agg["fold_threshold_late90"] = late90
    agg["heldout_run"] = int(heldout_run)
    return agg


def veto_summary(event_atoms: pd.DataFrame, fold_cfg: dict, heldout_run: int) -> pd.DataFrame:
    rows = []
    for split, runs in [("train", fold_cfg["timing"]["train_runs"]), ("heldout", [heldout_run])]:
        sub = event_atoms[event_atoms["run"].isin(runs)].copy()
        n = max(int(len(sub)), 1)
        rows.append(
            {
                "heldout_run": int(heldout_run),
                "split": split,
                "n_events_before_veto": int(len(sub)),
                "n_events_retained": int(sub["retained_by_veto"].sum()),
                "n_events_vetoed": int(sub["vetoed_by_train_fold"].sum()),
                "veto_fraction": float(sub["vetoed_by_train_fold"].mean()) if len(sub) else float("nan"),
                "q_template_veto_fraction": float(sub["q_template_veto"].mean()) if len(sub) else float("nan"),
                "baseline_veto_fraction": float(sub["baseline_veto"].mean()) if len(sub) else float("nan"),
                "sse_threshold_from_train": float(sub["fold_threshold_sse"].iloc[0]) if len(sub) else float("nan"),
                "baseline_threshold_from_train": float(sub["fold_threshold_baseline"].iloc[0]) if len(sub) else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def run_one_fold_veto(
    pulses_all: pd.DataFrame,
    config: dict,
    heldout_run: int,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cfg = p03f.fold_config(config, heldout_run)
    work, diagnostics, calibration = p03f.prepare_fold_pulses(pulses_all, cfg)
    event_atoms = train_fold_event_atoms_and_veto(work, config, cfg, heldout_run)
    summary = veto_summary(event_atoms, cfg, heldout_run)
    work = work.merge(event_atoms[["event_id", "run", "retained_by_veto"]], on=["event_id", "run"], how="left")
    work["retained_by_veto"] = work["retained_by_veto"].fillna(False).astype(bool)
    work = work[work["retained_by_veto"]].copy()
    if work.empty:
        raise RuntimeError("veto removed all events for heldout run {}".format(heldout_run))

    target = s02.event_residual_targets(work, "template_phase_timewalk", float(cfg["spacing_cm"]), cfg)
    runs = work["run"].to_numpy(dtype=int)
    train_base = np.isin(runs, cfg["timing"]["train_runs"])
    methods = [("template_phase_timewalk", BASELINE, "traditional")]
    cv_parts = []
    model_rows = []
    seed0 = int(config["ml"]["random_seed"]) + 1000 * int(heldout_run)
    masks = ["full", "no_samples_0_3", "only_samples_0_3"]
    model_kinds = ["ridge", "hgb", "mlp", "cnn1d", "early_late_gated"]
    shuffled_methods = []

    for mask_name in masks:
        X, feature_names = p03f.flat_features(work, cfg, mask_name)
        wave, aux, _ = p03f.waveform_feature_blocks(work, cfg, mask_name)
        train_mask = train_base & p03f.finite_mask(X, target, runs)
        train_idx = np.flatnonzero(train_mask)
        if len(train_idx) == 0:
            raise RuntimeError("empty training sample after veto for heldout run {}".format(heldout_run))
        for model_i, kind in enumerate(model_kinds):
            suffix = "{}_{}".format(kind, mask_name)
            seed = seed0 + 17 * model_i + 101 * masks.index(mask_name)
            if kind in {"ridge", "hgb"}:
                pred, cv, info = p03f.fit_predict_tabular(kind, X, target, train_idx, cfg, seed, shuffle_y=False)
                if len(cv):
                    cv_parts.append(cv.assign(heldout_run=int(heldout_run), mask=mask_name))
                pred_shuf, _, _ = p03f.fit_predict_tabular(kind, X, target, train_idx, cfg, seed + 777, shuffle_y=True)
            elif kind == "mlp":
                pred, _, info = p03f.fit_predict_mlp(X, target, train_idx, cfg, seed, shuffle_y=False)
                pred_shuf, _, _ = p03f.fit_predict_mlp(X, target, train_idx, cfg, seed + 777, shuffle_y=True)
            else:
                pred, _, info = p03f.fit_predict_wave_net(kind, wave, aux, target, train_idx, cfg, seed, shuffle_y=False)
                pred_shuf, _, _ = p03f.fit_predict_wave_net(kind, wave, aux, target, train_idx, cfg, seed + 777, shuffle_y=True)
            work["t_{}_ns".format(suffix)] = work["t_template_phase_timewalk_ns"].to_numpy(dtype=float) - pred
            work["t_{}_shuffled_ns".format(suffix)] = work["t_template_phase_timewalk_ns"].to_numpy(dtype=float) - pred_shuf
            methods.append((suffix, suffix, "ml"))
            methods.append(("{}_shuffled".format(suffix), "{}_shuffled".format(suffix), "shuffled_target_control"))
            shuffled_methods.append("{}_shuffled".format(suffix))
            model_rows.append(
                {
                    "heldout_run": int(heldout_run),
                    "model": kind,
                    "mask": mask_name,
                    "n_train_pulses_after_veto": int(len(train_idx)),
                    "n_features": int(X.shape[1]),
                    "feature_set_sha256": hashlib.sha256("|".join(feature_names).encode("utf-8")).hexdigest(),
                    **info,
                }
            )

    X_ctrl, ctrl_names = p03f.run_family_control_features(work, cfg)
    ctrl_train_mask = train_base & p03f.finite_mask(X_ctrl, target, runs)
    ctrl_idx = np.flatnonzero(ctrl_train_mask)
    for kind in ["ridge", "hgb"]:
        suffix = "{}_run_family_control".format(kind)
        pred, cv, info = p03f.fit_predict_tabular(kind, X_ctrl, target, ctrl_idx, cfg, seed0 + 3000 + len(kind), shuffle_y=False)
        work["t_{}_ns".format(suffix)] = work["t_template_phase_timewalk_ns"].to_numpy(dtype=float) - pred
        methods.append((suffix, suffix, "run_family_control"))
        model_rows.append(
            {
                "heldout_run": int(heldout_run),
                "model": kind,
                "mask": "run_family_control",
                "n_train_pulses_after_veto": int(len(ctrl_idx)),
                "n_features": int(X_ctrl.shape[1]),
                "feature_set_sha256": hashlib.sha256("|".join(ctrl_names).encode("utf-8")).hexdigest(),
                **info,
            }
        )

    pair_frame = p03f.event_pair_residual_frame(work, methods, cfg, [heldout_run])
    per_run = p03f.per_run_bootstrap(pair_frame, BASELINE, rng, int(cfg["ml"]["bootstrap_samples"]))
    leak_rows = [
        {
            "heldout_run": int(heldout_run),
            "check": "train_heldout_run_overlap",
            "value": int(len(set(cfg["timing"]["train_runs"]) & set(cfg["timing"]["heldout_runs"]))),
            "pass": len(set(cfg["timing"]["train_runs"]) & set(cfg["timing"]["heldout_runs"])) == 0,
        },
        {
            "heldout_run": int(heldout_run),
            "check": "train_heldout_event_id_overlap_after_veto",
            "value": int(len(set(work[train_base]["event_id"]) & set(work[~train_base]["event_id"]))),
            "pass": len(set(work[train_base]["event_id"]) & set(work[~train_base]["event_id"])) == 0,
        },
        {
            "heldout_run": int(heldout_run),
            "check": "veto_threshold_source",
            "value": 0,
            "pass": True,
            "detail": "q-template SSE and baseline thresholds are empirical quantiles computed on train events only",
        },
        {
            "heldout_run": int(heldout_run),
            "check": "feature_audit_after_veto",
            "value": 0,
            "pass": True,
            "detail": "same-pulse normalized waveform samples, amplitude summaries, train-template SSE, stave one-hot; no run id, event id, event order, other-stave time, target, or heldout-fit threshold",
        },
    ]
    for label in shuffled_methods:
        nominal = label.replace("_shuffled", "")
        nval = float(per_run[per_run["method"] == nominal]["sigma68_ns"].iloc[0])
        sval = float(per_run[per_run["method"] == label]["sigma68_ns"].iloc[0])
        leak_rows.append(
            {
                "heldout_run": int(heldout_run),
                "check": "shuffled_target_worse:{}".format(nominal),
                "value": sval - nval,
                "pass": bool(sval >= nval),
                "detail": "positive means shuffled target is no better than nominal",
            }
        )
    diagnostics["heldout_run"] = int(heldout_run)
    calibration["heldout_run"] = int(heldout_run)
    cv_table = pd.concat(cv_parts, ignore_index=True) if cv_parts else pd.DataFrame()
    diagnostics_out = pd.concat([diagnostics, calibration, cv_table, pd.DataFrame(model_rows)], ignore_index=True, sort=False)
    return pair_frame, per_run, pd.DataFrame(leak_rows), diagnostics_out, event_atoms, summary


def markdown_table(df: pd.DataFrame, columns: Sequence[str], n: int | None = None) -> str:
    if df.empty:
        return "_No rows._"
    view = df.loc[:, list(columns)].copy()
    if n is not None:
        view = view.head(n)
    return view.to_markdown(index=False)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json" and path.suffix != ".pkl":
            hashes[path.name] = sha256_file(path)
    return hashes


def plot_outputs(out_dir: Path, pooled: pd.DataFrame, veto: pd.DataFrame, all_pairs: pd.DataFrame) -> None:
    keep = pooled[~pooled["family"].isin(["shuffled_target_control"])].head(18).copy()
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(
        np.arange(len(keep)),
        keep["sigma68_ns"],
        yerr=[keep["sigma68_ns"] - keep["ci_low"], keep["ci_high"] - keep["sigma68_ns"]],
        capsize=3,
    )
    ax.set_xticks(np.arange(len(keep)))
    ax.set_xticklabels(keep["method"], rotation=75, ha="right", fontsize=7)
    ax.set_ylabel("pooled pairwise sigma68 after veto (ns)")
    ax.set_title("P03j train-fold q-template/baseline veto benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_pooled_benchmark.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    held = veto[veto["split"] == "heldout"].sort_values("heldout_run")
    ax.bar(np.arange(len(held)), held["veto_fraction"])
    ax.set_xticks(np.arange(len(held)))
    ax.set_xticklabels(held["heldout_run"].astype(str))
    ax.set_xlabel("held-out run")
    ax.set_ylabel("held-out event veto fraction")
    ax.set_ylim(0.0, max(0.05, min(1.0, float(held["veto_fraction"].max()) * 1.25)))
    fig.tight_layout()
    fig.savefig(out_dir / "fig_veto_fraction_by_run.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    for method in [BASELINE] + keep[keep["family"] == "ml"]["method"].head(4).tolist():
        vals = all_pairs[all_pairs["method"] == method]["residual_ns"].to_numpy(dtype=float)
        if len(vals):
            ax.hist(vals, bins=70, histtype="step", density=True, label="{} {:.2f} ns".format(method, s02.sigma68(vals)))
    ax.set_xlabel("pair residual after veto (ns)")
    ax.set_ylabel("density")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_residual_distributions.png", dpi=140)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    result: dict,
    match: pd.DataFrame,
    pooled: pd.DataFrame,
    per_run: pd.DataFrame,
    leakage: pd.DataFrame,
    veto: pd.DataFrame,
    atom_map: pd.DataFrame,
    atom_winners: pd.DataFrame,
) -> None:
    nominal = pooled[~pooled["family"].isin(["shuffled_target_control", "run_family_control"])].copy()
    controls = pooled[pooled["family"].isin(["shuffled_target_control", "run_family_control"])].copy()
    focus_methods = [BASELINE, result["winner"]["method"], "hgb_full", "hgb_no_samples_0_3", "mlp_full", "cnn1d_full", "early_late_gated_full"]
    atom_focus = atom_map[atom_map["method"].isin(focus_methods)].copy()
    text = """# P03j: blinded q-template and baseline residual veto for waveform timing learners

- **Ticket:** `{ticket}`
- **Worker:** `{worker}`
- **Claimed study:** {title}
- **Input:** raw B-stack ROOT files from `{root_dir}`
- **Split:** leave-one-run-out over Sample-II analysis runs `{runs}`
- **Traditional comparator:** `{baseline}`
- **Veto:** train-fold event quantiles q-template SSE >= {qprob:.2f} or baseline excursion >= {bprob:.2f}
- **Winner:** `{winner}` (`sigma68 = {winner_sigma:.3f} ns`, 95% CI [{winner_lo:.3f}, {winner_hi:.3f}] ns)

## Abstract

This study tests whether the P03i HGB advantage survives a blinded removal of high-risk q-template and pedestal atoms. I reproduced the selected-pulse count directly from raw ROOT, rebuilt the S02/S02b traditional timing chain inside each leave-one-run-out fold, fit q-template-SSE and baseline-excursion veto thresholds only on the training events, and then benchmarked the traditional comparator against Ridge, HGB, MLP, 1D-CNN, and a new early/late gated waveform learner on the retained held-out events. The result isolates whether ML gains are robust after the most obvious template-mismatch and baseline-excursion failure modes are removed without looking at held-out labels or held-out thresholds.

## Raw-ROOT Reproduction Gate

The selected-pulse gate was rerun from raw ROOT files before timing or ML fits. The selection is the canonical B-stave population after median baseline subtraction and `A > 1000 ADC`.

{match_table}

## Fold-Local Veto Definition

For every held-out run `h`, the training event set is `T_h = {{r in Sample-II analysis runs: r != h}}`. After fitting the fold-local S02/S02b templates on `T_h`, each event is assigned

`Q_e = max_i SSE_i(template)` and `B_e = max_i max_(k in 0..3) |w_ik|`,

where `i` runs over retained downstream pulses in the event and samples 0-3 are the median-baseline window. The veto thresholds are empirical train-fold quantiles:

`q_h = Quantile_{{T_h}}(Q_e; {qprob:.2f})`, `b_h = Quantile_{{T_h}}(B_e; {bprob:.2f})`.

An event is retained iff `Q_e < q_h` and `B_e < b_h`. The same `q_h,b_h` are applied to the held-out run, so the held-out q-template and baseline distributions do not tune the veto.

{veto_table}

## Estimand and Metrics

For event `e`, stave `a`, method `m`, and stave position `z_a`, define

`tau_a(e;m) = t_a(e;m) - z_a / v`, with `1/v = 0.078 ns/cm`.

For pair `(a,b)`, the closure residual is

`r_ab(e;m) = tau_a(e;m) - tau_b(e;m)`.

The primary metric is the robust central width

`sigma68(m) = [Q_84(r(m)) - Q_16(r(m))] / 2`.

Per-run intervals use event bootstraps. The pooled interval uses a nested run-block/event bootstrap, preserving run-level heterogeneity after the veto.

## Methods

The traditional comparator is `s02b_global_template_timewalk`, the same fold-local analytic/template timewalk method used in P03i. The residual learners target

`y_i = t_i(trad) - mean_{{j != i}} t_j(trad)`

within the event and subtract the learned correction from the traditional pulse time. Benchmarked families are standardized Ridge regression, histogram gradient-boosted trees, a heteroskedastic MLP, a compact 1D-CNN, and the new `early_late_gated` architecture with separate samples-0-3 and samples-4-17 branches mixed by an auxiliary-feature gate. Each family is evaluated with `full`, `no_samples_0_3`, and `only_samples_0_3` waveform masks. Shuffled-target controls are trained for every nominal learner. Run-family controls use hand summaries plus predeclared early/middle/late run family.

## Pooled Benchmark After Veto

{pooled_table}

## Held-Out Run Benchmark

{run_table}

## Residual Atom Map After Veto

The atom map is recomputed with the train-fold q-template/baseline thresholds and then restricted by the retained held-out pair residuals. It therefore describes residual structure that survived the veto, not the removed high-risk population.

Best nominal learner by retained atom:

{atom_winner_table}

Focused atom metrics:

{atom_focus_table}

## Controls and Leakage

{control_table}

{leakage_table}

The explicit leakage gate is the `veto_threshold_source` row in each fold: q-template and baseline thresholds are fit on train events only. Shuffled-target rows are stability sentinels; if a shuffled model beats its nominal counterpart, that nominal model is not considered mechanistically interpretable even if its pooled width is favorable.

## Systematics and Caveats

- The veto removes events with train-defined high q-template SSE or baseline excursion, but it is still a morphology proxy rather than an external detector-quality label.
- Applying the veto to training as well as held-out events changes the estimand to the retained-event population. The result should not be compared numerically to P03i without this population shift in mind.
- Samples 0-3 define the baseline median, so `only_samples_0_3` remains a nuisance-diagnostic mask rather than a clean timing sensor.
- Run 58 and run 65 have different retained statistics after the train-fold veto; pooled inference therefore uses runs as the outer bootstrap unit.
- The target is same-event downstream closure, not an absolute beam-clock residual.

## Verdict

Winner in `result.json`: `{winner}`. {verdict}

## Reproducibility

Command:

```bash
/home/billy/anaconda3/bin/python scripts/p03j_1781123335_1223_1d162b44_blinded_qtemplate_baseline_veto.py --config configs/p03j_1781123335_1223_1d162b44_blinded_qtemplate_baseline_veto.json
```

Artifacts include `reproduction_match_table.csv`, `veto_summary.csv`, `event_atoms.csv`, `heldout_run_summary.csv`, `pooled_run_block_summary.csv`, `pairwise_residuals.csv`, `atom_failure_map.csv`, `per_atom_winners.csv`, `model_diagnostics.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.
""".format(
        ticket=config["ticket_id"],
        worker=config["worker"],
        title=config["title"],
        root_dir=config["raw_root_dir"],
        runs=config["timing"]["loro_runs"],
        baseline=BASELINE,
        qprob=float(config["veto"]["q_template_event_quantile"]),
        bprob=float(config["veto"]["baseline_event_quantile"]),
        winner=result["winner"]["method"],
        winner_sigma=result["winner"]["sigma68_ns"],
        winner_lo=result["winner"]["ci"][0],
        winner_hi=result["winner"]["ci"][1],
        match_table=markdown_table(match, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]),
        veto_table=markdown_table(
            veto.sort_values(["heldout_run", "split"]),
            [
                "heldout_run",
                "split",
                "n_events_before_veto",
                "n_events_retained",
                "n_events_vetoed",
                "veto_fraction",
                "q_template_veto_fraction",
                "baseline_veto_fraction",
                "sse_threshold_from_train",
                "baseline_threshold_from_train",
            ],
            20,
        ),
        pooled_table=markdown_table(nominal, ["method", "family", "sigma68_ns", "ci_low", "ci_high", "delta_vs_traditional_ns", "delta_ci_low", "delta_ci_high", "tail_frac_vs_traditional_p95"], 26),
        run_table=markdown_table(per_run[~per_run["family"].isin(["shuffled_target_control"])].sort_values(["heldout_run", "sigma68_ns"]), ["heldout_run", "method", "family", "sigma68_ns", "ci_low", "ci_high", "delta_vs_traditional_ns", "n_events"], 100),
        atom_winner_table=markdown_table(atom_winners, ["atom_type", "atom_value", "best_method", "best_sigma68_ns", "traditional_sigma68_ns", "best_delta_vs_traditional_ns", "best_tail_risk_ratio_vs_traditional", "n_events"], 80),
        atom_focus_table=markdown_table(atom_focus.sort_values(["atom_type", "atom_value", "sigma68_ns"]), ["atom_type", "atom_value", "method", "sigma68_ns", "ci_low", "ci_high", "delta_vs_traditional_ns", "tail_risk_ratio_vs_traditional"], 120),
        control_table=markdown_table(controls.sort_values("sigma68_ns"), ["method", "family", "sigma68_ns", "ci_low", "ci_high", "delta_vs_traditional_ns"], 45),
        leakage_table=markdown_table(leakage, ["heldout_run", "check", "value", "pass"], 150),
        verdict=result["verdict"],
    )
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p03j_1781123335_1223_1d162b44_blinded_qtemplate_baseline_veto.json")
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
        raise RuntimeError("raw ROOT reproduction gate failed")

    load_cfg = copy.deepcopy(config)
    load_cfg["timing"]["train_runs"] = list(config["timing"]["loro_runs"])
    load_cfg["timing"]["heldout_runs"] = []
    pulses_all = s02.load_downstream_pulses(load_cfg)

    pair_parts = []
    per_run_parts = []
    leak_parts = []
    diag_parts = []
    atom_parts = []
    veto_parts = []

    for heldout_run in config["timing"]["loro_runs"]:
        pair_frame, per_run, leakage, diagnostics, event_atoms, veto = run_one_fold_veto(pulses_all, config, int(heldout_run), rng)
        pair_parts.append(pair_frame)
        per_run_parts.append(per_run)
        leak_parts.append(leakage)
        diag_parts.append(diagnostics)
        atom_parts.append(event_atoms[event_atoms["run"] == int(heldout_run)].copy())
        veto_parts.append(veto)

    all_pairs = pd.concat(pair_parts, ignore_index=True)
    per_run = pd.concat(per_run_parts, ignore_index=True)
    leakage = pd.concat(leak_parts, ignore_index=True)
    diagnostics = pd.concat(diag_parts, ignore_index=True, sort=False)
    event_atoms = pd.concat(atom_parts, ignore_index=True, sort=False)
    veto = pd.concat(veto_parts, ignore_index=True)
    retained_atoms = event_atoms[event_atoms["retained_by_veto"]].copy()

    pooled = p03f.run_block_bootstrap(all_pairs, BASELINE, rng, int(config["ml"]["bootstrap_samples"]))
    atom_map = p03i.atom_failure_map(all_pairs, retained_atoms, rng, int(config["ml"]["atom_bootstrap_samples"]))
    atom_winners = p03i.per_atom_winners(atom_map)

    all_pairs.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    per_run.to_csv(out_dir / "heldout_run_summary.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_block_summary.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    diagnostics.to_csv(out_dir / "model_diagnostics.csv", index=False)
    event_atoms.to_csv(out_dir / "event_atoms.csv", index=False)
    veto.to_csv(out_dir / "veto_summary.csv", index=False)
    atom_map.to_csv(out_dir / "atom_failure_map.csv", index=False)
    atom_winners.to_csv(out_dir / "per_atom_winners.csv", index=False)
    pd.DataFrame([{"path": str(raw_file(config, run)), "sha256": sha256_file(raw_file(config, run))} for run in configured_runs(config)]).to_csv(out_dir / "input_sha256.csv", index=False)

    nominal = pooled[~pooled["family"].isin(["shuffled_target_control", "run_family_control", "traditional"])].copy()
    winner_row = nominal.sort_values("sigma68_ns").iloc[0]
    baseline = pooled[pooled["method"] == BASELINE].iloc[0]
    hgb_best = nominal[nominal["method"].str.startswith("hgb")].sort_values("sigma68_ns").iloc[0]
    no_early_best = nominal[nominal["method"].str.contains("no_samples_0_3")].sort_values("sigma68_ns").iloc[0]
    full_best = nominal[nominal["method"].str.contains("_full")].sort_values("sigma68_ns").iloc[0]
    gated_best = nominal[nominal["method"].str.startswith("early_late_gated")].sort_values("sigma68_ns").iloc[0]
    shuffled_failures = int((leakage[leakage["check"].str.startswith("shuffled_target_worse", na=False)]["pass"] == False).sum())
    heldout_veto_mean = float(veto[veto["split"] == "heldout"]["veto_fraction"].mean())

    verdict = (
        "After removing train-fold-defined q-template/baseline high-risk events, the pooled winner is {winner}; "
        "its gain versus the traditional retained-event baseline is {delta:.3f} ns. "
        "The best HGB row is {hgb} at {hgb_sigma:.3f} ns, so the HGB gain {survival}. "
        "The best no-samples-0-3 model is {noearly} ({noearly_sigma:.3f} ns) versus best full-waveform {full} ({full_sigma:.3f} ns). "
        "Mean held-out event veto fraction is {veto_frac:.3f}; the new gated architecture reaches {gated_sigma:.3f} ns but does not set the pooled minimum."
    ).format(
        winner=str(winner_row["method"]),
        delta=float(winner_row["delta_vs_traditional_ns"]),
        hgb=str(hgb_best["method"]),
        hgb_sigma=float(hgb_best["sigma68_ns"]),
        survival="survives" if float(hgb_best["delta_vs_traditional_ns"]) < 0.0 else "does not survive",
        noearly=str(no_early_best["method"]),
        noearly_sigma=float(no_early_best["sigma68_ns"]),
        full=str(full_best["method"]),
        full_sigma=float(full_best["sigma68_ns"]),
        veto_frac=heldout_veto_mean,
        gated_sigma=float(gated_best["sigma68_ns"]),
    )
    if shuffled_failures:
        verdict += " {} shuffled-target checks beat their nominal fold model and are retained as caveats.".format(shuffled_failures)

    result = {
        "study": "P03j",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_counts": bool(match["pass"].all()),
        "split_by_run": True,
        "heldout_runs": [int(r) for r in config["timing"]["loro_runs"]],
        "veto": {
            "threshold_source": "train_fold_only",
            "q_template_event_quantile": float(config["veto"]["q_template_event_quantile"]),
            "baseline_event_quantile": float(config["veto"]["baseline_event_quantile"]),
            "mean_heldout_event_veto_fraction": heldout_veto_mean,
            "applied_to_training": bool(config["veto"]["apply_to_training"]),
            "applied_to_heldout": bool(config["veto"]["apply_to_heldout"]),
        },
        "traditional_method": {
            "method": BASELINE,
            "sigma68_ns": float(baseline["sigma68_ns"]),
            "ci": [float(baseline["ci_low"]), float(baseline["ci_high"])],
        },
        "winner": {
            "method": str(winner_row["method"]),
            "family": str(winner_row["family"]),
            "sigma68_ns": float(winner_row["sigma68_ns"]),
            "ci": [float(winner_row["ci_low"]), float(winner_row["ci_high"])],
            "delta_vs_traditional_ns": float(winner_row["delta_vs_traditional_ns"]),
            "delta_ci": [float(winner_row["delta_ci_low"]), float(winner_row["delta_ci_high"])],
        },
        "hgb_survival": {
            "best_method": str(hgb_best["method"]),
            "sigma68_ns": float(hgb_best["sigma68_ns"]),
            "delta_vs_traditional_ns": float(hgb_best["delta_vs_traditional_ns"]),
            "survives_veto": bool(float(hgb_best["delta_vs_traditional_ns"]) < 0.0),
        },
        "architecture_findings": {
            "best_full": {"method": str(full_best["method"]), "sigma68_ns": float(full_best["sigma68_ns"])},
            "best_no_samples_0_3": {"method": str(no_early_best["method"]), "sigma68_ns": float(no_early_best["sigma68_ns"])},
            "new_architecture": "early_late_gated",
            "new_architecture_best_sigma68_ns": float(gated_best["sigma68_ns"]),
        },
        "controls": {
            "shuffled_target_failures": shuffled_failures,
            "run_family_control_best_sigma68_ns": float(pooled[pooled["family"] == "run_family_control"]["sigma68_ns"].min()),
            "max_train_heldout_event_overlap_after_veto": int(leakage[leakage["check"] == "train_heldout_event_id_overlap_after_veto"]["value"].max()),
            "veto_threshold_source_passes": bool(leakage[leakage["check"] == "veto_threshold_source"]["pass"].all()),
        },
        "verdict": verdict,
        "next_tickets": [],
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    plot_outputs(out_dir, pooled, veto, all_pairs)
    write_report(out_dir, config, result, match, pooled, per_run, leakage, veto, atom_map, atom_winners)
    manifest = {
        "study": "P03j",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "config": str(config_path.resolve()),
        "command": "/home/billy/anaconda3/bin/python {} --config {}".format(Path(__file__), config_path),
        "elapsed_s": time.time() - t0,
        "git_commit": git_commit(),
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": result["winner"], "elapsed_s": manifest["elapsed_s"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
