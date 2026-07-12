#!/usr/bin/env python3
"""S27e weak-label perturbation audit for the S27d event benchmark.

The ticket asks whether S27d architecture gains are stable to alternative
PID/stress weak-label definitions and fixed-efficiency thresholds.  This driver
keeps the S27d raw ROOT reproduction, complete-run split, masks, and model
panel, then retrains every method under each label scenario and bootstraps by
held-out run.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import uproot
from sklearn.base import clone
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor, HistGradientBoostingClassifier, HistGradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import mean_absolute_error, roc_auc_score
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/s27e_1783828129_24566_25c559ca_weak_label_perturbation_audit.json"


def clean_json(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): clean_json(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean_json(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return None if not np.isfinite(float(x)) else float(x)
    if isinstance(x, float):
        return None if not math.isfinite(x) else x
    return x


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(clean_json(payload), indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def configured_runs(cfg: Dict[str, Any]) -> List[int]:
    runs: List[int] = []
    for group_runs in cfg["run_groups"].values():
        runs.extend(int(r) for r in group_runs)
    return sorted(set(runs))


def group_for_run(cfg: Dict[str, Any]) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in cfg["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def res68(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return math.nan
    x = x[np.isfinite(x)]
    if x.size == 0:
        return math.nan
    return float(np.percentile(np.abs(x - np.median(x)), 68))


def cfd_time(w: np.ndarray) -> np.ndarray:
    amp = np.maximum(w.max(axis=-1), 1e-6)
    thr = 0.5 * amp
    above = w >= thr[:, None]
    first = above.argmax(axis=1).astype(float)
    first[~above.any(axis=1)] = 8.0
    return first


def read_events(cfg: Dict[str, Any]) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame, pd.DataFrame]:
    ns = int(cfg["samples_per_channel"])
    base_idx = np.asarray(cfg["baseline_samples"], dtype=int)
    stave_names = list(cfg["staves"].keys())
    stave_idx = np.asarray([cfg["staves"][k] for k in stave_names], dtype=int)
    run_group = group_for_run(cfg)
    rng = np.random.default_rng(int(cfg["random_seed"]))
    rows: List[pd.DataFrame] = []
    waves: List[np.ndarray] = []
    count_rows: List[Dict[str, Any]] = []

    for run in configured_runs(cfg):
        path = ROOT / cfg["raw_root_dir"] / f"hrdb_run_{run:04d}.root"
        tree = uproot.open(path)["h101"]
        event_frames: List[pd.DataFrame] = []
        event_waves: List[np.ndarray] = []
        events = 0
        selected = 0
        per_stave = {name: 0 for name in stave_names}
        for batch in tree.iterate(["HRDv"], step_size=25000, library="np"):
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, ns)
            corr = raw - np.median(raw[..., base_idx], axis=-1)[..., None]
            b = corr[:, stave_idx, :]
            amp = b.max(axis=-1)
            sel = amp > float(cfg["amplitude_cut_adc"])
            keep = sel.any(axis=1)
            events += int(len(raw))
            selected += int(sel.sum())
            for i, name in enumerate(stave_names):
                per_stave[name] += int(sel[:, i].sum())
            if keep.any():
                bw = b[keep]
                pos = np.clip(bw, 0, None)
                charge = pos.sum(axis=-1)
                total = charge.sum(axis=1)
                peak = amp[keep].max(axis=1)
                late = pos[:, :, 12:18].sum(axis=(1, 2)) / np.maximum(total, 1.0)
                distal = (charge[:, 2] + charge[:, 3]) / np.maximum(total, 1.0)
                charge_asymmetry = ((charge[:, 2] + charge[:, 3]) - (charge[:, 0] + charge[:, 1])) / np.maximum(total, 1.0)
                earliest = np.min(np.stack([cfd_time(bw[:, j, :]) for j in range(bw.shape[1])], axis=1), axis=1)
                frame = pd.DataFrame({
                    "run": run,
                    "group": run_group[run],
                    "event_charge": total,
                    "energy_log": np.log1p(total),
                    "distal_fraction": distal,
                    "charge_asymmetry": charge_asymmetry,
                    "timing_proxy_sample": earliest,
                    "late_tail_fraction": late,
                    "peak_adc": peak,
                    "n_selected_staves": sel[keep].sum(axis=1),
                })
                event_frames.append(frame)
                event_waves.append(bw.astype(np.float32))
        count_rows.append({"run": run, "group": run_group[run], "events": events, "selected_pulses": selected, **per_stave})
        if event_frames:
            rf = pd.concat(event_frames, ignore_index=True)
            rw = np.concatenate(event_waves, axis=0)
            n = min(len(rf), int(cfg["subsample_per_run"]))
            take = np.sort(rng.choice(len(rf), size=n, replace=False))
            rows.append(rf.iloc[take].reset_index(drop=True))
            waves.append(rw[take])

    counts = pd.DataFrame(count_rows)
    repro_rows: List[Dict[str, Any]] = []
    total = int(counts["selected_pulses"].sum())
    repro_rows.append({"quantity": "total selected B-stave pulses", "expected": cfg["expected_selected_pulses"], "reproduced": total, "delta": total - int(cfg["expected_selected_pulses"]), "pass": total == int(cfg["expected_selected_pulses"])})
    for group, expected in cfg["expected_group_counts"].items():
        got = int(counts.loc[counts["group"] == group, "selected_pulses"].sum())
        repro_rows.append({"quantity": f"{group} selected pulses", "expected": expected, "reproduced": got, "delta": got - int(expected), "pass": got == int(expected)})
    df = pd.concat(rows, ignore_index=True)
    wave = np.concatenate(waves, axis=0)
    return df, wave, counts, pd.DataFrame(repro_rows)


def apply_label_scenario(df: pd.DataFrame, cfg: Dict[str, Any], scenario: Dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    train = out["group"].isin(cfg["train_groups"])
    pid_rule = scenario["pid_rule"]
    pid_q = float(scenario["pid_quantile"])
    if pid_rule in {"distal_median", "distal_quantile"}:
        pid_score = out["distal_fraction"].to_numpy()
        pid_thr = float(out.loc[train, "distal_fraction"].quantile(pid_q))
    elif pid_rule == "distal_charge_balance":
        pid_score = (out["distal_fraction"] + 0.5 * out["charge_asymmetry"]).to_numpy()
        pid_thr = float((out.loc[train, "distal_fraction"] + 0.5 * out.loc[train, "charge_asymmetry"]).quantile(pid_q))
    else:
        raise ValueError(f"unknown pid_rule={pid_rule}")
    out["pid_proxy"] = (pid_score > pid_thr).astype(int)
    out["pid_score_definition"] = pid_rule
    out["pid_threshold"] = pid_thr

    late_q = float(scenario["stress_late_quantile"])
    peak_q = float(scenario["stress_peak_quantile"])
    late_thr = float(out.loc[train, "late_tail_fraction"].quantile(late_q))
    peak_thr = float(out.loc[train, "peak_adc"].quantile(peak_q)) if peak_q < 1.0 else float("inf")
    late_flag = out["late_tail_fraction"].to_numpy() > late_thr
    peak_flag = out["peak_adc"].to_numpy() > peak_thr
    stress_rule = scenario["stress_rule"]
    if stress_rule == "late_or_peak":
        stress = late_flag | peak_flag
    elif stress_rule == "late_only":
        stress = late_flag
    else:
        raise ValueError(f"unknown stress_rule={stress_rule}")
    out["stress_proxy"] = stress.astype(int)
    out["stress_late_threshold"] = late_thr
    out["stress_peak_threshold"] = peak_thr
    return out


def masked_features(wave: np.ndarray, samples: Iterable[int], arch: str) -> np.ndarray:
    s = np.asarray(list(samples), dtype=int)
    x = wave[:, :, s]
    flat = x.reshape(len(x), -1)
    pos = np.clip(x, 0, None)
    summaries = [flat, pos.sum(axis=2), x.max(axis=2), x.mean(axis=2), x.std(axis=2)]
    if arch in {"cnn1d", "residual_cnn_gru_new", "attention_transformer_small"}:
        d = np.diff(x, axis=2) if x.shape[2] > 1 else np.zeros((len(x), x.shape[1], 1), dtype=x.dtype)
        summaries.extend([d.reshape(len(x), -1), d.max(axis=2), d.min(axis=2)])
    if arch in {"residual_cnn_gru_new", "attention_transformer_small"}:
        summaries.extend([np.cumsum(x, axis=2).reshape(len(x), -1), (x[:, :, -1] - x[:, :, 0])])
    if arch == "attention_transformer_small":
        weights = np.exp(x - x.max(axis=2, keepdims=True))
        weights = weights / np.maximum(weights.sum(axis=2, keepdims=True), 1e-6)
        summaries.extend([(weights * x).sum(axis=2), (weights * np.arange(x.shape[2])).sum(axis=2)])
    return np.concatenate([a.reshape(len(x), -1) for a in summaries], axis=1)


def model_specs(seed: int) -> Dict[str, Dict[str, Any]]:
    return {
        "traditional_charge_depth_timewalk": {"family": "traditional"},
        "ridge": {"family": "linear", "reg": make_pipeline(StandardScaler(), Ridge(alpha=8.0)), "clf": make_pipeline(StandardScaler(), LogisticRegression(C=0.4, max_iter=1000, random_state=seed))},
        "gradient_boosted_trees": {"family": "tree", "reg": HistGradientBoostingRegressor(max_iter=30, learning_rate=0.08, l2_regularization=0.05, random_state=seed), "clf": HistGradientBoostingClassifier(max_iter=30, learning_rate=0.08, l2_regularization=0.05, random_state=seed)},
        "mlp": {"family": "neural_tabular", "reg": make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(24,), alpha=0.004, learning_rate_init=0.004, max_iter=30, random_state=seed, early_stopping=True)), "clf": make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(24,), alpha=0.004, learning_rate_init=0.004, max_iter=30, random_state=seed, early_stopping=True))},
        "cnn1d": {"family": "neural_waveform", "reg": make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(28,), alpha=0.003, learning_rate_init=0.004, max_iter=30, random_state=seed, early_stopping=True)), "clf": make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(28,), alpha=0.003, learning_rate_init=0.004, max_iter=30, random_state=seed, early_stopping=True))},
        "residual_cnn_gru_new": {"family": "new_architecture", "reg": RandomForestRegressor(n_estimators=35, min_samples_leaf=10, max_features="sqrt", random_state=seed, n_jobs=-1), "clf": RandomForestClassifier(n_estimators=35, min_samples_leaf=10, max_features="sqrt", random_state=seed, n_jobs=-1)},
        "attention_transformer_small": {"family": "attention", "reg": GradientBoostingRegressor(n_estimators=30, learning_rate=0.08, max_depth=2, random_state=seed), "clf": GradientBoostingClassifier(n_estimators=30, learning_rate=0.08, max_depth=2, random_state=seed)},
    }


def predict_traditional(df: pd.DataFrame, wave: np.ndarray, train: np.ndarray) -> Dict[str, np.ndarray]:
    pos = np.clip(wave, 0, None)
    charge = pos[:, :, 8:12].sum(axis=(1, 2)) + 0.35 * pos[:, :, 12:18].sum(axis=(1, 2))
    distal = pos[:, 2:, 8:12].sum(axis=(1, 2)) / np.maximum(pos[:, :, 8:12].sum(axis=(1, 2)), 1.0)
    late = pos[:, :, 12:18].sum(axis=(1, 2)) / np.maximum(pos.sum(axis=(1, 2)), 1.0)
    peak = wave.max(axis=(1, 2))
    return {
        "energy": np.log1p(charge),
        "timing": np.min(np.stack([cfd_time(wave[:, j, :]) for j in range(wave.shape[1])], axis=1), axis=1),
        "pid": distal,
        "stress": 0.6 * late + 0.4 * (peak > np.quantile(peak[train], 0.95)).astype(float),
    }


def score_predictions(df: pd.DataFrame, pred: Dict[str, np.ndarray], idx: np.ndarray) -> Dict[str, float]:
    e = df["energy_log"].to_numpy()[idx]
    t = df["timing_proxy_sample"].to_numpy()[idx]
    pid = df["pid_proxy"].to_numpy()[idx]
    stress = df["stress_proxy"].to_numpy()[idx]
    er = pred["energy"][idx] - e
    tr = pred["timing"][idx] - t
    out = {
        "energy_res68": res68(er),
        "energy_mae": float(mean_absolute_error(e, pred["energy"][idx])),
        "energy_bias": float(np.median(er)),
        "timing_res68_samples": res68(tr),
        "timing_mae_samples": float(mean_absolute_error(t, pred["timing"][idx])),
        "pid_auc": float(roc_auc_score(pid, pred["pid"][idx])) if len(np.unique(pid)) == 2 else math.nan,
        "stress_auc": float(roc_auc_score(stress, pred["stress"][idx])) if len(np.unique(stress)) == 2 else math.nan,
        "n_events": int(len(idx)),
        "n_runs": int(df.iloc[idx]["run"].nunique()),
    }
    return out


def bootstrap_ci(df: pd.DataFrame, pred: Dict[str, np.ndarray], held_idx: np.ndarray, reps: int, seed: int) -> Dict[str, Tuple[float, float]]:
    rng = np.random.default_rng(seed)
    blocks = [g.index.to_numpy() for _, g in df.iloc[held_idx].groupby("run")]
    vals: Dict[str, List[float]] = {k: [] for k in ["energy_res68", "timing_res68_samples", "pid_auc", "stress_auc"]}
    for _ in range(reps):
        sample = np.concatenate([blocks[i] for i in rng.integers(0, len(blocks), len(blocks))])
        m = score_predictions(df, pred, sample)
        for k in vals:
            vals[k].append(float(m[k]))
    return {k: (float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))) for k, v in vals.items()}


def train_panel(cfg: Dict[str, Any], df: pd.DataFrame, wave: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    specs = model_specs(int(cfg["random_seed"]))
    metric_rows: List[Dict[str, Any]] = []
    per_run_rows: List[Dict[str, Any]] = []
    scenario_rows: List[Dict[str, Any]] = []
    for scenario_name, scenario in cfg["label_scenarios"].items():
        sdf = apply_label_scenario(df, cfg, scenario)
        train = sdf["group"].isin(cfg["train_groups"]).to_numpy()
        held = sdf["group"].isin(cfg["heldout_groups"]).to_numpy()
        train_idx = np.where(train)[0]
        held_idx = np.where(held)[0]
        scenario_rows.append({
            "scenario": scenario_name,
            "pid_rule": scenario["pid_rule"],
            "pid_positive_train_fraction": float(sdf.loc[train, "pid_proxy"].mean()),
            "pid_positive_heldout_fraction": float(sdf.loc[held, "pid_proxy"].mean()),
            "stress_rule": scenario["stress_rule"],
            "stress_positive_train_fraction": float(sdf.loc[train, "stress_proxy"].mean()),
            "stress_positive_heldout_fraction": float(sdf.loc[held, "stress_proxy"].mean()),
            "pid_threshold": float(sdf["pid_threshold"].iloc[0]),
            "stress_late_threshold": float(sdf["stress_late_threshold"].iloc[0]),
            "stress_peak_threshold": float(sdf["stress_peak_threshold"].iloc[0]),
        })
        y = {
            "energy": sdf["energy_log"].to_numpy(),
            "timing": sdf["timing_proxy_sample"].to_numpy(),
            "pid": sdf["pid_proxy"].to_numpy(),
            "stress": sdf["stress_proxy"].to_numpy(),
        }
        for mask_name, samples in cfg["window_masks"].items():
            for method, spec in specs.items():
                if method == "traditional_charge_depth_timewalk":
                    pred = predict_traditional(sdf, wave, train)
                else:
                    X = masked_features(wave, samples, method)
                    pred = {}
                    for target in ["energy", "timing"]:
                        model = clone(spec["reg"])
                        model.fit(X[train_idx], y[target][train_idx])
                        pred[target] = model.predict(X)
                    for target in ["pid", "stress"]:
                        model = clone(spec["clf"])
                        model.fit(X[train_idx], y[target][train_idx])
                        pred[target] = model.predict_proba(X)[:, 1]
                m = score_predictions(sdf, pred, held_idx)
                ci = bootstrap_ci(sdf, pred, held_idx, int(cfg["bootstrap_replicates"]), int(cfg["random_seed"]) + len(metric_rows))
                score = (
                    cfg["score_weights"]["pid_auc_loss"] * (1.0 - m["pid_auc"])
                    + cfg["score_weights"]["energy_res68"] * m["energy_res68"]
                    + cfg["score_weights"]["timing_res68"] * (m["timing_res68_samples"] / 2.0)
                    + cfg["score_weights"]["stress_auc_loss"] * (1.0 - m["stress_auc"])
                    + cfg["score_weights"]["energy_bias"] * abs(m["energy_bias"])
                )
                row = {
                    "scenario": scenario_name, "mask": mask_name, "samples": ",".join(map(str, samples)), "method": method,
                    "family": spec["family"], "joint_score": float(score), **m,
                }
                for key, (lo, hi) in ci.items():
                    row[f"{key}_ci_low"] = lo
                    row[f"{key}_ci_high"] = hi
                metric_rows.append(row)
                for run, sub in sdf.loc[held].groupby("run"):
                    idx = sub.index.to_numpy()
                    pr = score_predictions(sdf, pred, idx)
                    per_run_rows.append({"scenario": scenario_name, "mask": mask_name, "method": method, "run": int(run), **pr})
    metrics = pd.DataFrame(metric_rows).sort_values("joint_score").reset_index(drop=True)
    return metrics, pd.DataFrame(per_run_rows), pd.DataFrame(scenario_rows)


def md_table(df: pd.DataFrame, cols: List[str], n: int | None = None) -> str:
    view = df.loc[:, cols].head(n).copy() if n else df.loc[:, cols].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else f"{x:.5g}")
    labels = [str(c) for c in view.columns]
    rows = [[str(v) for v in row] for row in view.astype(object).to_numpy()]
    widths = [len(c) for c in labels]
    for row in rows:
        widths = [max(w, len(cell)) for w, cell in zip(widths, row)]
    header = "| " + " | ".join(c.ljust(w) for c, w in zip(labels, widths)) + " |"
    rule = "| " + " | ".join("-" * w for w in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(w) for cell, w in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header, rule, *body])


def finalize_outputs(cfg: Dict[str, Any], out: Path, started: float) -> None:
    counts = pd.read_csv(out / "reproduction_counts_by_run.csv")
    repro = pd.read_csv(out / "reproduction_match_table.csv")
    df = pd.read_csv(out / "event_table.csv.gz")
    metrics = pd.read_csv(out / "method_mask_metrics.csv")
    per_run = pd.read_csv(out / "per_run_metrics.csv")
    scenarios = pd.read_csv(out / "label_scenario_summary.csv")
    if not bool(repro["pass"].all()):
        raise AssertionError("raw ROOT reproduction failed")
    metrics = metrics.sort_values("joint_score").reset_index(drop=True)
    winner = metrics.iloc[0].to_dict()
    result = {
        "ticket_id": cfg["ticket_id"],
        "study_id": cfg["study_id"],
        "worker": cfg["worker"],
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "raw_root_dir": cfg["raw_root_dir"],
        "raw_reproduction": {"passed": True, "selected_pulses": int(counts["selected_pulses"].sum()), "expected_selected_pulses": int(cfg["expected_selected_pulses"]), "checks": repro.to_dict(orient="records")},
        "split": {"train_groups": cfg["train_groups"], "heldout_groups": cfg["heldout_groups"], "heldout_runs": sorted(df.loc[df["group"].isin(cfg["heldout_groups"]), "run"].unique().astype(int).tolist())},
        "bootstrap": {"unit": "held-out run", "replicates": int(cfg["bootstrap_replicates"]), "ci": "95% percentile"},
        "methods": sorted(metrics["method"].unique().tolist()),
        "masks": cfg["window_masks"],
        "label_scenarios": cfg["label_scenarios"],
        "winner": winner["method"],
        "winner_scenario": winner["scenario"],
        "winner_mask": winner["mask"],
        "winner_metric": "lowest weighted joint score",
        "winner_details": winner,
        "scenario_winners": metrics.sort_values("joint_score").groupby("scenario", as_index=False).first().to_dict(orient="records"),
        "next_tickets": [],
        "novel_ticket_appended": None,
        "runtime_sec": round(time.time() - started, 3)
    }
    (out / "REPORT.md").write_text(build_report(cfg, result, repro, scenarios, metrics, per_run), encoding="utf-8")
    write_json(out / "result.json", result)
    manifest = {"ticket_id": cfg["ticket_id"], "generated_utc": datetime.now(timezone.utc).isoformat(), "command": f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}", "artifacts": {}}
    for p in sorted(out.iterdir()):
        if p.is_file():
            manifest["artifacts"][p.name] = {"bytes": p.stat().st_size, "sha256": sha256(p)}
    write_json(out / "manifest.json", manifest)
    print(f"wrote {out.relative_to(ROOT)}")
    print(f"winner {winner['method']} mask={winner['mask']} score={winner['joint_score']:.6f}")


def build_report(cfg: Dict[str, Any], result: Dict[str, Any], repro: pd.DataFrame, scenarios: pd.DataFrame, metrics: pd.DataFrame, per_run: pd.DataFrame) -> str:
    winner = result["winner_details"]
    scenario_best = metrics.sort_values("joint_score").groupby("scenario", as_index=False).first()
    mask_best = metrics.sort_values("joint_score").groupby(["scenario", "mask"], as_index=False).first()
    method_stability = metrics.sort_values("joint_score").groupby(["scenario", "method"], as_index=False).first().sort_values(["scenario", "joint_score"])
    lines = [
        f"# S27e - Weak-Label Perturbation Audit for S27d Event-Level Mask Winners",
        "",
        f"Ticket: `{cfg['ticket_id']}`  ",
        f"Worker: `{cfg['worker']}`",
        "",
        "## Abstract",
        (
            "S27e repeats the S27d event-native masked benchmark under five alternative PID/stress weak-label "
            "definitions, including fixed-efficiency stress thresholds. The raw ROOT selected-pulse count is "
            "reproduced exactly before any modeling. The lowest held-out joint loss is obtained by "
            f"**{result['winner']}** in scenario `{winner['scenario']}` under mask `{winner['mask']}` "
            f"with score {winner['joint_score']:.5f}. The audit separates architecture performance from "
            "proxy-label choice by requiring every method to retrain from the same raw-derived event table "
            "for each scenario."
        ),
        "",
        "## Raw ROOT Reproduction",
        "The script opens `h101/HRDv`, reshapes each row to `(event, channel, sample)`, subtracts the median of samples 0--3, and counts B2/B4/B6/B8 pulses with corrected peak above 1000 ADC.",
        "",
        md_table(repro, ["quantity", "expected", "reproduced", "delta", "pass"]),
        "",
        "## Event Targets",
        "For event `i`, corrected waveform `x_{ics}` is obtained from raw ADC waveform `a_{ics}` by",
        "",
        "`x_{ics}=a_{ics}-median_{s in {0,1,2,3}} a_{ics}`.",
        "",
        "The event-level energy and timing endpoints are unchanged from S27d, while PID and stress are recomputed per scenario from full-window raw observables and then predicted from masked windows:",
        "",
        "`E_i = log(1 + sum_{c,s} max(x_{ics},0))` for energy closure;",
        "`D_i=(Q_{B6}+Q_{B8}) / sum_c Q_c` and `A_i=((Q_{B6}+Q_{B8})-(Q_{B2}+Q_{B4})) / sum_c Q_c` define PID perturbations;",
        "`T_i = min_c CFD50(x_{ic})` as a timing proxy in sample units;",
        "`S_i = 1{tail_i > Q_alpha^train or peak_i > Q_beta^train}` or the tail-only variant defines fixed-efficiency stress labels.",
        "",
        "These are not external particle-truth labels; they are raw-data, event-native weak targets used to test whether the S27d winner is robust to proxy-label choice.",
        "",
        "## Split and Confidence Intervals",
        f"Training runs are groups `{', '.join(cfg['train_groups'])}`; held-out runs are `{', '.join(cfg['heldout_groups'])}`. Each run is a complete block. Bootstrap intervals resample the held-out runs with replacement for {cfg['bootstrap_replicates']} replicates.",
        "",
        "## Label Scenarios",
        md_table(scenarios, ["scenario", "pid_rule", "pid_positive_train_fraction", "pid_positive_heldout_fraction", "stress_rule", "stress_positive_train_fraction", "stress_positive_heldout_fraction", "pid_threshold", "stress_late_threshold", "stress_peak_threshold"]),
        "",
        "## Methods",
        "- `traditional_charge_depth_timewalk`: fixed charge-window, distal-charge, late-tail, and CFD50 formulas with no event-row training.",
        "- `ridge`: standardized linear ridge/logistic models.",
        "- `gradient_boosted_trees`: histogram gradient boosting for nonlinear tabular closure.",
        "- `mlp`: two-layer tabular neural network.",
        "- `cnn1d`: neural model on convolution-like local difference features from the masked waveform.",
        "- `residual_cnn_gru_new`: new residual sequence architecture approximation using cumulative/residual features and random forests, retained as the novel architecture family under perturbation.",
        "- `attention_transformer_small`: transformer-like attention summary features over masked samples with boosted heads; included in the complete winner rule.",
        "",
        "The joint score minimized in `result.json` is",
        "",
        "`L = 0.28(1-AUC_PID) + 0.30 R68_E + 0.20 R68_T/2 + 0.17(1-AUC_stress) + 0.05 |bias_E|`.",
        "",
        "## Primary Results",
        md_table(metrics, ["scenario", "mask", "method", "family", "joint_score", "pid_auc", "energy_res68", "timing_res68_samples", "stress_auc", "energy_bias"], 24),
        "",
        "## Bootstrap Intervals",
        md_table(metrics, ["scenario", "mask", "method", "energy_res68_ci_low", "energy_res68_ci_high", "timing_res68_samples_ci_low", "timing_res68_samples_ci_high", "pid_auc_ci_low", "pid_auc_ci_high", "stress_auc_ci_low", "stress_auc_ci_high"], 24),
        "",
        "## Scenario Winners",
        md_table(scenario_best, ["scenario", "mask", "method", "joint_score", "pid_auc", "energy_res68", "timing_res68_samples", "stress_auc"]),
        "",
        "## Method Stability",
        md_table(method_stability, ["scenario", "method", "mask", "joint_score", "pid_auc", "stress_auc"], 35),
        "",
        "## Best Method by Mask",
        md_table(mask_best, ["scenario", "mask", "method", "joint_score", "pid_auc", "energy_res68", "timing_res68_samples", "stress_auc"], 36),
        "",
        "## Per-Run Held-Out Diagnostics",
        md_table(per_run.sort_values(["scenario", "method", "mask", "run"]), ["scenario", "mask", "method", "run", "n_events", "pid_auc", "energy_res68", "timing_res68_samples", "stress_auc"], 50),
        "",
        "## Systematics",
        "The dominant systematic is still target definition: PID and stress are weak proxies derived from B-stack waveform topology, not external truth. S27e turns that systematic into an explicit nuisance axis by changing PID topology thresholds, adding a charge-balance PID definition, and replacing the nominal stress rule with fixed-efficiency and tail-only thresholds. The subsample is stratified by run to limit compute while preserving complete-run split semantics. Bootstrap intervals quantify held-out run variability within each weak-label scenario; they do not cover gain calibration, channel mapping, or ROOT decoding alternatives.",
        "",
        "## Caveats",
        "- The perturbations are raw-derived weak labels, not external particle-identification truth.",
        "- Fixed-efficiency stress thresholds are defined on the training groups and can shift held-out prevalence when the sample-II distribution drifts.",
        "- Late-tail masks are noncausal for online PID/timing promotion even when predictive.",
        "- The neural rows are compact sklearn approximations of waveform architectures; the study is a controlled benchmark audit, not a final high-capacity network training campaign.",
        "",
        "## Conclusion",
        f"`result.json` names `{result['winner']}` in scenario `{winner['scenario']}` on `{winner['mask']}` as the S27e winner. The scenario table reports whether the S27d-style tree winner remains competitive when PID and stress weak-label choices are perturbed under the same ridge, GBT, MLP, 1D-CNN, residual sequence, attention, and traditional-method panel.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    started = time.time()
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    out = ROOT / cfg["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    reusable = [
        out / "reproduction_counts_by_run.csv",
        out / "reproduction_match_table.csv",
        out / "event_table.csv.gz",
        out / "method_mask_metrics.csv",
        out / "per_run_metrics.csv",
        out / "label_scenario_summary.csv",
    ]
    if all(p.exists() for p in reusable):
        finalize_outputs(cfg, out, started)
        return
    df, wave, counts, repro = read_events(cfg)
    if not bool(repro["pass"].all()):
        raise AssertionError("raw ROOT reproduction failed")
    metrics, per_run, scenarios = train_panel(cfg, df, wave)
    counts.to_csv(out / "reproduction_counts_by_run.csv", index=False)
    repro.to_csv(out / "reproduction_match_table.csv", index=False)
    df.drop(columns=[]).to_csv(out / "event_table.csv.gz", index=False, compression="gzip")
    metrics.to_csv(out / "method_mask_metrics.csv", index=False)
    per_run.to_csv(out / "per_run_metrics.csv", index=False)
    scenarios.to_csv(out / "label_scenario_summary.csv", index=False)
    (out / "claimed_ticket.txt").write_text(cfg["ticket_id"] + "\n", encoding="utf-8")
    finalize_outputs(cfg, out, started)


if __name__ == "__main__":
    main()
