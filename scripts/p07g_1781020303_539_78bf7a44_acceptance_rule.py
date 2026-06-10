#!/usr/bin/env python3
"""P07g: calibrated accept/veto rules for retained-window B2 saturation recovery."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.linear_model import HuberRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/p07g_1781020303_539_78bf7a44_acceptance_rule.json"


def load_p07e():
    path = ROOT / "scripts/p07e_leading_edge_sample_ablation.py"
    spec = importlib.util.spec_from_file_location("p07e_leading_edge_sample_ablation", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P07E = load_p07e()


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


def load_config(path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg["config_path"] = str(path)
    return cfg


def json_sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_sanitize(v) for v in value]
    if isinstance(value, tuple):
        return [json_sanitize(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if math.isfinite(v) else None
    return value


def raw_path(cfg: dict[str, Any], run: int) -> Path:
    return ROOT / cfg["raw_root"] / f"hrdb_run_{run:04d}.root"


def load_odd_b2_metrics(cfg: dict[str, Any]) -> pd.DataFrame:
    rows = []
    event_offset = 0
    baseline_samples = list(P07E.BASELINE_SAMPLES)
    for run in cfg["runs"]:
        path = raw_path(cfg, int(run))
        tree = uproot.open(path)["h101"]
        for batch in tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=25000, library="np"):
            eventno = np.asarray(batch["EVENTNO"], dtype=np.int64)
            evt = np.asarray(batch["EVT"], dtype=np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, P07E.NSAMPLES)
            even_raw = raw[:, 0, :]
            odd_raw = raw[:, 1, :]
            even = even_raw - np.median(even_raw[:, baseline_samples], axis=1)[:, None]
            odd = -(odd_raw - np.median(odd_raw[:, baseline_samples], axis=1)[:, None])
            even_amp = even.max(axis=1)
            selected = even_amp > float(P07E.AMPLITUDE_CUT_ADC)
            idx = np.flatnonzero(selected)
            if len(idx):
                even_charge = np.clip(even[idx], 0.0, None).sum(axis=1)
                odd_charge = np.clip(odd[idx], 0.0, None).sum(axis=1)
                odd_amp = odd[idx].max(axis=1)
                rows.append(
                    pd.DataFrame(
                        {
                            "event_uid": [
                                f"{run}:{int(eventno[i])}:{int(evt[i])}:{event_offset + int(i)}" for i in idx
                            ],
                            "odd_amp": odd_amp,
                            "odd_charge": odd_charge,
                            "even_charge": even_charge,
                            "odd_charge_ratio": odd_charge / np.maximum(even_charge, 1.0),
                            "odd_amp_ratio": odd_amp / np.maximum(even_amp[idx], 1.0),
                        }
                    )
                )
            event_offset += len(eventno)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def clean_b2_mask(meta: pd.DataFrame, cfg: dict[str, Any]) -> np.ndarray:
    return (
        (meta["stave"].to_numpy() == "B2")
        & (meta["amplitude_adc"].to_numpy(dtype=float) >= float(cfg["clean_min_amp_adc"]))
        & (meta["amplitude_adc"].to_numpy(dtype=float) <= float(cfg["clean_max_amp_adc"]))
        & (meta["peak_sample"].to_numpy(dtype=int) >= int(cfg["clean_min_peak_sample"]))
        & (meta["peak_sample"].to_numpy(dtype=int) <= int(cfg["clean_max_peak_sample"]))
    )


def fixed_ceiling_samples_with_index(
    wave: np.ndarray,
    amp: np.ndarray,
    source_idx: np.ndarray,
    ceilings: list[float],
    rng: np.random.Generator,
    max_rows: int | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    xs, ys, obs, src = [], [], [], []
    for ceiling in ceilings:
        keep = amp > 1.05 * float(ceiling)
        if keep.any():
            xs.append(np.minimum(wave[keep], float(ceiling)))
            ys.append(amp[keep])
            obs.append(np.full(int(keep.sum()), float(ceiling), dtype=float))
            src.append(source_idx[keep])
    x = np.vstack(xs)
    y = np.concatenate(ys)
    o = np.concatenate(obs)
    s = np.concatenate(src)
    if max_rows is not None and len(y) > int(max_rows):
        choice = rng.choice(len(y), size=int(max_rows), replace=False)
        x, y, o, s = x[choice], y[choice], o[choice], s[choice]
    return x, y, o, s


def fit_gbr(x: np.ndarray, y: np.ndarray, observed: np.ndarray, window: list[int], seed: int) -> GradientBoostingRegressor:
    model = GradientBoostingRegressor(
        n_estimators=120,
        max_depth=3,
        learning_rate=0.055,
        subsample=0.75,
        random_state=seed,
    )
    model.fit(P07E.masked_features(x, observed, window), np.log(y / observed))
    return model


def fit_huber(x: np.ndarray, y: np.ndarray, observed: np.ndarray, window: list[int]):
    model = make_pipeline(
        StandardScaler(),
        HuberRegressor(epsilon=1.35, alpha=0.0001, max_iter=300),
    )
    model.fit(P07E.masked_features(x, observed, window), np.log(y / observed))
    return model


def cfd_ns(wave: np.ndarray, amp: np.ndarray) -> np.ndarray:
    return float(P07E.SAMPLE_PERIOD_NS) * P07E.cfd_time_samples(wave, amp)


def q_rmse(wave: np.ndarray, amp: np.ndarray, template: np.ndarray) -> np.ndarray:
    return np.sqrt(np.mean((wave / np.maximum(amp[:, None], 1.0) - template[None, :]) ** 2, axis=1))


def risk_feature_frame(
    x: np.ndarray,
    observed: np.ndarray,
    pred: np.ndarray,
    source_idx: np.ndarray,
    meta: pd.DataFrame,
    template: np.ndarray,
    window: list[int],
) -> pd.DataFrame:
    idx = np.asarray(window, dtype=int)
    rows = meta.loc[source_idx].reset_index(drop=True)
    plateau = (x[:, idx] >= 0.995 * observed[:, None]).sum(axis=1)
    window_charge = np.clip(x[:, idx], 0.0, None).sum(axis=1)
    return pd.DataFrame(
        {
            "pred_lift": pred / np.maximum(observed, 1.0) - 1.0,
            "peak_sample": x.argmax(axis=1),
            "plateau_count": plateau,
            "q_rmse_pred": q_rmse(x, pred, template),
            "window_charge_over_obs": window_charge / np.maximum(observed, 1.0),
            "odd_charge_ratio": rows.get("odd_charge_ratio", pd.Series(np.nan, index=rows.index)).to_numpy(dtype=float),
            "odd_amp_ratio": rows.get("odd_amp_ratio", pd.Series(np.nan, index=rows.index)).to_numpy(dtype=float),
        }
    ).fillna(0.0)


def risk_matrix(frame: pd.DataFrame) -> np.ndarray:
    cols = [
        "pred_lift",
        "peak_sample",
        "plateau_count",
        "q_rmse_pred",
        "window_charge_over_obs",
        "odd_charge_ratio",
        "odd_amp_ratio",
    ]
    return frame[cols].to_numpy(dtype=float)


def prediction_frame(
    run: int,
    method: str,
    kind: str,
    x: np.ndarray,
    truth: np.ndarray,
    observed: np.ndarray,
    pred: np.ndarray,
    source_idx: np.ndarray,
    clean_waves: np.ndarray,
    meta: pd.DataFrame,
    template: np.ndarray,
    window: list[int],
    cfg: dict[str, Any],
) -> pd.DataFrame:
    features = risk_feature_frame(x, observed, pred, source_idx, meta, template, window)
    frac = (pred - truth) / np.maximum(truth, 1.0)
    truth_wave = clean_waves[source_idx]
    q_shift = np.clip(x, 0.0, None).sum(axis=1) / np.maximum(pred, 1.0) - np.clip(truth_wave, 0.0, None).sum(axis=1) / np.maximum(truth, 1.0)
    timing_error = cfd_ns(x, pred) - cfd_ns(truth_wave, truth)
    out = pd.DataFrame(
        {
            "run": int(run),
            "kind": kind,
            "method": method,
            "event_uid": meta.loc[source_idx, "event_uid"].to_numpy(),
            "truth_amp": truth,
            "observed_amp": observed,
            "pred_amp": pred,
            "frac_error": frac,
            "abs_frac_error": np.abs(frac),
            "catastrophic": np.abs(frac) > float(cfg["catastrophic_abs_frac"]),
            "q_template_shift": q_shift,
            "timing_error_ns": timing_error,
            "timing_tail": np.abs(timing_error) > float(P07E.TIMING_TAIL_ABS_NS),
        }
    )
    return pd.concat([out, features], axis=1)


def metric_from_events(frame: pd.DataFrame, envelope: float) -> dict[str, float | int]:
    if frame.empty:
        return {
            "n": 0,
            "amp_res68_abs_frac": float("nan"),
            "amp_bias_median_frac": float("nan"),
            "catastrophic_rate": float("nan"),
            "q_template_shift_median": float("nan"),
            "timing_tail_rate": float("nan"),
            "calibration_coverage": float("nan"),
            "acceptance_rate": 0.0,
        }
    if "declared_upper_abs_error" in frame:
        coverage = float((frame["abs_frac_error"].to_numpy(dtype=float) <= frame["declared_upper_abs_error"].to_numpy(dtype=float)).mean())
    else:
        coverage = float((frame["abs_frac_error"] <= envelope).mean())
    return {
        "n": int(len(frame)),
        "amp_res68_abs_frac": float(np.percentile(frame["abs_frac_error"], 68)),
        "amp_bias_median_frac": float(np.median(frame["frac_error"])),
        "catastrophic_rate": float(frame["catastrophic"].mean()),
        "q_template_shift_median": float(np.median(frame["q_template_shift"])),
        "timing_tail_rate": float(frame["timing_tail"].mean()),
        "calibration_coverage": coverage,
        "acceptance_rate": float(frame["accepted"].mean()) if "accepted" in frame else 1.0,
    }


def passes_train_gates(frame: pd.DataFrame, cfg: dict[str, Any]) -> bool:
    if len(frame) < 50:
        return False
    m = metric_from_events(frame, float(cfg["bias_envelope_abs_frac"]))
    gates = cfg["acceptance_train_gates"]
    return bool(
        abs(float(m["amp_bias_median_frac"])) <= float(gates["max_abs_bias_median_frac"])
        and float(m["amp_res68_abs_frac"]) <= float(gates["max_res68_abs_frac"])
        and float(m["catastrophic_rate"]) <= float(gates["max_catastrophic_rate"])
        and float(m["timing_tail_rate"]) <= float(gates["max_timing_tail_rate"])
    )


def choose_traditional_rule(train: pd.DataFrame, cfg: dict[str, Any]) -> dict[str, float]:
    grid = cfg["traditional_grid"]
    best = None
    for max_lift in grid["max_lift"]:
        for max_q in grid["max_q_rmse"]:
            for odd_low in grid["odd_charge_ratio_low"]:
                for odd_high in grid["odd_charge_ratio_high"]:
                    mask = (
                        (train["pred_lift"] <= float(max_lift))
                        & (train["q_rmse_pred"] <= float(max_q))
                        & (train["peak_sample"].between(4, 12))
                        & (train["odd_charge_ratio"] >= float(odd_low))
                        & (train["odd_charge_ratio"] <= float(odd_high))
                    )
                    accepted = train[mask]
                    if not passes_train_gates(accepted, cfg):
                        continue
                    rate = float(mask.mean())
                    score = (rate, -float(max_lift), -float(max_q))
                    if best is None or score > best[0]:
                        best = (score, max_lift, max_q, odd_low, odd_high)
    if best is None:
        return {"max_lift": 0.0, "max_q_rmse": 0.0, "odd_low": 1.0, "odd_high": 0.0}
    _, max_lift, max_q, odd_low, odd_high = best
    return {"max_lift": float(max_lift), "max_q_rmse": float(max_q), "odd_low": float(odd_low), "odd_high": float(odd_high)}


def apply_traditional_rule(frame: pd.DataFrame, rule: dict[str, float]) -> np.ndarray:
    return (
        (frame["pred_lift"] <= rule["max_lift"])
        & (frame["q_rmse_pred"] <= rule["max_q_rmse"])
        & (frame["peak_sample"].between(4, 12))
        & (frame["odd_charge_ratio"] >= rule["odd_low"])
        & (frame["odd_charge_ratio"] <= rule["odd_high"])
    ).to_numpy(dtype=bool)


def fit_ml_rule(train: pd.DataFrame, cfg: dict[str, Any], seed: int) -> dict[str, Any]:
    x = risk_matrix(train)
    y_abs = train["abs_frac_error"].to_numpy(dtype=float)
    reg = GradientBoostingRegressor(
        n_estimators=120,
        max_depth=2,
        learning_rate=0.045,
        subsample=0.8,
        random_state=seed,
    ).fit(x, y_abs)
    residual_q = float(np.quantile(np.maximum(y_abs - reg.predict(x), 0.0), 0.90))
    y_cat = train["catastrophic"].to_numpy(dtype=int)
    clf = None
    if len(np.unique(y_cat)) > 1:
        clf = GradientBoostingClassifier(
            n_estimators=90,
            max_depth=2,
            learning_rate=0.045,
            subsample=0.8,
            random_state=seed + 1,
        ).fit(x, y_cat)
    pred_upper = reg.predict(x) + residual_q
    pred_cat = clf.predict_proba(x)[:, 1] if clf is not None else np.zeros(len(train), dtype=float)
    best = None
    for upper_thr in cfg["ml_grid"]["risk_upper_threshold"]:
        for cat_thr in cfg["ml_grid"]["cat_probability_threshold"]:
            mask = (pred_upper <= float(upper_thr)) & (pred_cat <= float(cat_thr))
            accepted = train[mask]
            if not passes_train_gates(accepted, cfg):
                continue
            rate = float(mask.mean())
            score = (rate, -float(upper_thr), -float(cat_thr))
            if best is None or score > best[0]:
                best = (score, upper_thr, cat_thr)
    if best is None:
        upper_thr = min(cfg["ml_grid"]["risk_upper_threshold"])
        cat_thr = min(cfg["ml_grid"]["cat_probability_threshold"])
    else:
        _, upper_thr, cat_thr = best
    return {
        "regressor": reg,
        "classifier": clf,
        "conformal_q90": residual_q,
        "risk_upper_threshold": float(upper_thr),
        "cat_probability_threshold": float(cat_thr),
    }


def apply_ml_rule(frame: pd.DataFrame, rule: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = risk_matrix(frame)
    pred_upper = rule["regressor"].predict(x) + float(rule["conformal_q90"])
    clf = rule["classifier"]
    pred_cat = clf.predict_proba(x)[:, 1] if clf is not None else np.zeros(len(frame), dtype=float)
    mask = (pred_upper <= float(rule["risk_upper_threshold"])) & (pred_cat <= float(rule["cat_probability_threshold"]))
    return mask, pred_upper, pred_cat


def natural_summary(
    real_rows: pd.DataFrame,
    real_waves: np.ndarray,
    accepted_event_uid: np.ndarray,
    pred_amp: np.ndarray,
    template: np.ndarray,
) -> dict[str, float | int]:
    if len(real_rows) == 0 or len(accepted_event_uid) == 0:
        return {"n_events": 0, "q_template_shift": float("nan"), "timing_tail_delta": float("nan")}
    b2_mask = real_rows["stave"].to_numpy() == "B2"
    b2_rows = real_rows.loc[b2_mask].reset_index(drop=True)
    keep_b2 = b2_rows["event_uid"].isin(set(accepted_event_uid)).to_numpy()
    if not keep_b2.any():
        return {"n_events": 0, "q_template_shift": float("nan"), "timing_tail_delta": float("nan")}
    accepted_ids = set(b2_rows.loc[keep_b2, "event_uid"])
    row_keep = real_rows["event_uid"].isin(accepted_ids).to_numpy()
    method_values = P07E.event_metrics(real_rows.loc[row_keep].copy(), real_waves[row_keep], pred_amp[keep_b2], template)
    obs_amp = b2_rows.loc[keep_b2, "amplitude_adc"].to_numpy(dtype=float)
    observed_values = P07E.event_metrics(real_rows.loc[row_keep].copy(), real_waves[row_keep], obs_amp, template)

    def tail_frac(values: pd.DataFrame) -> float:
        resid = values["timing_residual_ns"].to_numpy(dtype=float)
        finite = np.isfinite(resid)
        if finite.sum() == 0:
            return float("nan")
        centered = resid[finite] - np.median(resid[finite])
        return float(np.mean(np.abs(centered) > float(P07E.TIMING_TAIL_ABS_NS)))

    return {
        "n_events": int(len(method_values)),
        "q_template_shift": float(np.nanmedian(method_values["q_template_rmse"]) - np.nanmedian(observed_values["q_template_rmse"])),
        "timing_tail_delta": float(tail_frac(method_values) - tail_frac(observed_values)),
    }


def run_bootstrap_summary(events: pd.DataFrame, natural: pd.DataFrame, cfg: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(cfg["random_seed"]) + 9000)
    reps = int(cfg["bootstrap_reps"])
    rows = []
    boot_rows = []
    runs = sorted(events["run"].unique())
    envelope = float(cfg["bias_envelope_abs_frac"])
    for rule_name in sorted(events["rule"].unique()):
        sub = events[(events["rule"] == rule_name) & (events["accepted"])].copy()
        all_for_rate = events[events["rule"] == rule_name]
        point = metric_from_events(sub.assign(accepted=all_for_rate["accepted"].to_numpy()[: len(sub)] if len(sub) == len(all_for_rate) else True), envelope)
        point["acceptance_rate"] = float(all_for_rate["accepted"].mean())
        nat_sub = natural[natural["rule"] == rule_name]
        point["q_template_shift_natural"] = float(np.nanmean(nat_sub["q_template_shift"]))
        point["timing_tail_delta_natural"] = float(np.nanmean(nat_sub["timing_tail_delta"]))
        point["rule"] = rule_name
        rows.append(point)
        by_run_events = {run: all_for_rate[all_for_rate["run"] == run] for run in runs}
        by_run_nat = {run: nat_sub[nat_sub["run"] == run] for run in runs}
        for _ in range(reps):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            ev = pd.concat([by_run_events[int(run)] for run in sampled], ignore_index=True)
            acc = ev[ev["accepted"]]
            m = metric_from_events(acc, envelope)
            m["acceptance_rate"] = float(ev["accepted"].mean()) if len(ev) else float("nan")
            nat = pd.concat([by_run_nat[int(run)] for run in sampled], ignore_index=True)
            m["q_template_shift_natural"] = float(np.nanmean(nat["q_template_shift"])) if len(nat) else float("nan")
            m["timing_tail_delta_natural"] = float(np.nanmean(nat["timing_tail_delta"])) if len(nat) else float("nan")
            m["rule"] = rule_name
            boot_rows.append(m)
    summary = pd.DataFrame(rows)
    boot = pd.DataFrame(boot_rows)
    ci_rows = []
    metrics = [
        "amp_res68_abs_frac",
        "amp_bias_median_frac",
        "catastrophic_rate",
        "q_template_shift_median",
        "timing_tail_rate",
        "calibration_coverage",
        "acceptance_rate",
        "q_template_shift_natural",
        "timing_tail_delta_natural",
    ]
    for rule_name, sub in boot.groupby("rule"):
        row = {"rule": rule_name}
        for metric in metrics:
            vals = sub[metric].to_numpy(dtype=float)
            vals = vals[np.isfinite(vals)]
            row[f"{metric}_ci95"] = [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))] if len(vals) else [None, None]
        ci_rows.append(row)
    return summary.merge(pd.DataFrame(ci_rows), on="rule", how="left"), boot


def output_hashes(out: Path) -> dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != "manifest.json"}


def write_report(out: Path, result: dict[str, Any], reproduction: pd.DataFrame, summary: pd.DataFrame, rules: pd.DataFrame, leakage: pd.DataFrame) -> None:
    show_cols = [
        "rule",
        "n",
        "acceptance_rate",
        "acceptance_rate_ci95",
        "amp_res68_abs_frac",
        "amp_res68_abs_frac_ci95",
        "amp_bias_median_frac",
        "catastrophic_rate",
        "q_template_shift_natural",
        "timing_tail_delta_natural",
        "calibration_coverage",
    ]
    lines = [
        "# P07g: saturation recovery acceptance rule from bias envelope",
        "",
        f"Ticket `{result['ticket']}`. Raw Sample-II B-stack ROOT was read directly; no Monte Carlo was used.",
        "",
        "## Reproduction first",
        "",
        reproduction.to_markdown(index=False),
        "",
        "## Method",
        "",
        "The correction under test is the P07e retained-window `w2_8` B2 recovery. Each held-out run is excluded before fitting the retained-window template/GBR and before calibrating accept/veto thresholds.",
        "",
        "- `traditional_envelope`: retained-window robust Huber/template recovery plus fixed cuts on predicted saturation lift, peak sample, corrected q-template RMSE, and B2 odd-duplicate charge consistency.",
        "- `ml_conformal_risk`: retained-window GBR recovery plus a gradient-boosted absolute-error predictor with a train-run conformal residual margin and a catastrophic-error classifier.",
        "",
        "Artificial 4000 ADC clipping supplies amplitude truth for accepted-event bias/res68/catastrophic metrics. Natural `A_B2 >= 7000` events with at least two downstream selected B staves supply q-template and timing-tail deltas versus the observed saturated B2 waveform.",
        "",
        "## Held-out accept/veto performance",
        "",
        summary[show_cols].to_markdown(index=False),
        "",
        "CIs are paired run-block bootstrap 95% intervals over the held-out runs. Calibration coverage is the fraction of accepted artificial events inside the declared 10% error envelope for the traditional rule and inside the ML conformal upper bound for the ML rule.",
        "",
        "## Rule parameters",
        "",
        rules.to_markdown(index=False),
        "",
        "## Leakage checks",
        "",
        leakage.to_markdown(index=False),
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/p07g_1781020303_539_78bf7a44_acceptance_rule.py --config {result['config_path']}",
        "```",
        "",
    ]
    (out / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    cfg = load_config(args.config)
    out = ROOT / "reports" / cfg["ticket"]
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    rng = np.random.default_rng(int(cfg["random_seed"]))
    window = [int(i) for i in cfg["retained_window_samples"]]

    print("1/5 loading raw Sample-II B-stack ROOT", flush=True)
    meta, waves = P07E.load_sample_ii()
    odd = load_odd_b2_metrics(cfg)
    meta = meta.merge(odd, on="event_uid", how="left")
    meta[["odd_amp", "odd_charge", "even_charge", "odd_charge_ratio", "odd_amp_ratio"]] = meta[
        ["odd_amp", "odd_charge", "even_charge", "odd_charge_ratio", "odd_amp_ratio"]
    ].fillna(0.0)
    b2_mask = meta["stave"].to_numpy() == "B2"
    clean_mask = clean_b2_mask(meta, cfg)
    clean_idx_all = np.flatnonzero(clean_mask)
    event_ids = P07E.real_saturated_event_ids(meta)
    real_rows_all = meta[meta["event_uid"].isin(event_ids)].copy()
    real_waves_all = waves[real_rows_all.index.to_numpy()]

    artificial_rows = []
    natural_rows = []
    rule_rows = []
    train_eval_rows = []
    leakage_rows = []
    reproduction_fold_rows = []

    print("2/5 fitting leave-one-run-out retained-window corrections and rules", flush=True)
    for held_run in cfg["runs"]:
        held_run = int(held_run)
        train_idx = clean_idx_all[meta.loc[clean_idx_all, "run"].to_numpy() != held_run]
        held_idx = clean_idx_all[meta.loc[clean_idx_all, "run"].to_numpy() == held_run]
        if len(train_idx) > int(cfg["max_train_clean_per_split"]):
            train_idx = rng.choice(train_idx, size=int(cfg["max_train_clean_per_split"]), replace=False)
        if len(held_idx) > int(cfg["max_held_artificial_per_run"]):
            held_idx = rng.choice(held_idx, size=int(cfg["max_held_artificial_per_run"]), replace=False)
        train_wave = waves[train_idx]
        train_amp = meta.loc[train_idx, "amplitude_adc"].to_numpy(dtype=float)
        held_wave = waves[held_idx]
        held_amp = meta.loc[held_idx, "amplitude_adc"].to_numpy(dtype=float)
        template = P07E.build_template(train_wave, train_amp)
        x_train, y_train, obs_train, src_train = fixed_ceiling_samples_with_index(
            train_wave,
            train_amp,
            train_idx,
            [float(x) for x in cfg["train_ceilings_adc"]],
            rng,
            max_rows=int(cfg["max_train_clean_per_split"]),
        )
        x_held, y_held, obs_held, src_held = fixed_ceiling_samples_with_index(
            held_wave,
            held_amp,
            held_idx,
            [float(cfg["fixed_ceiling_adc"])],
            rng,
            max_rows=int(cfg["max_held_artificial_per_run"]),
        )
        gbr = fit_gbr(x_train, y_train, obs_train, window, int(cfg["random_seed"]) + held_run + len(window))

        huber = fit_huber(x_train, y_train, obs_train, window)
        train_pred_trad = obs_train * np.exp(huber.predict(P07E.masked_features(x_train, obs_train, window)))
        train_pred_gbr = obs_train * np.exp(gbr.predict(P07E.masked_features(x_train, obs_train, window)))
        held_pred_trad = obs_held * np.exp(huber.predict(P07E.masked_features(x_held, obs_held, window)))
        held_pred_gbr = obs_held * np.exp(gbr.predict(P07E.masked_features(x_held, obs_held, window)))

        train_trad = prediction_frame(held_run, "traditional_huber_window", "train_calibration", x_train, y_train, obs_train, train_pred_trad, src_train, waves, meta, template, window, cfg)
        train_gbr = prediction_frame(held_run, "gbr_masked", "train_calibration", x_train, y_train, obs_train, train_pred_gbr, src_train, waves, meta, template, window, cfg)
        held_trad = prediction_frame(held_run, "traditional_huber_window", "heldout", x_held, y_held, obs_held, held_pred_trad, src_held, waves, meta, template, window, cfg)
        held_gbr = prediction_frame(held_run, "gbr_masked", "heldout", x_held, y_held, obs_held, held_pred_gbr, src_held, waves, meta, template, window, cfg)
        reproduction_fold_rows.append({"run": held_run, **P07E.recovery_metrics(y_held, held_pred_gbr)})

        trad_rule = choose_traditional_rule(train_trad, cfg)
        ml_rule = fit_ml_rule(train_gbr, cfg, int(cfg["random_seed"]) + 5000 + held_run)
        trad_mask = apply_traditional_rule(held_trad, trad_rule)
        ml_mask, ml_upper, ml_cat = apply_ml_rule(held_gbr, ml_rule)
        held_trad["accepted"] = trad_mask
        held_trad["rule"] = "traditional_envelope"
        held_trad["declared_upper_abs_error"] = float(cfg["bias_envelope_abs_frac"])
        held_trad["pred_catastrophic_prob"] = np.nan
        held_gbr["accepted"] = ml_mask
        held_gbr["rule"] = "ml_conformal_risk"
        held_gbr["declared_upper_abs_error"] = ml_upper
        held_gbr["pred_catastrophic_prob"] = ml_cat
        artificial_rows.extend([held_trad, held_gbr])

        train_trad_eval = train_trad.copy()
        train_trad_eval["accepted"] = apply_traditional_rule(train_trad_eval, trad_rule)
        train_trad_eval["rule"] = "traditional_envelope"
        train_gbr_eval = train_gbr.copy()
        train_gbr_eval["accepted"], _, _ = apply_ml_rule(train_gbr_eval, ml_rule)
        train_gbr_eval["rule"] = "ml_conformal_risk"
        train_eval_rows.extend([train_trad_eval, train_gbr_eval])

        rule_rows.append({"run": held_run, "rule": "traditional_envelope", **trad_rule})
        rule_rows.append(
            {
                "run": held_run,
                "rule": "ml_conformal_risk",
                "risk_upper_threshold": float(ml_rule["risk_upper_threshold"]),
                "cat_probability_threshold": float(ml_rule["cat_probability_threshold"]),
                "conformal_q90": float(ml_rule["conformal_q90"]),
            }
        )

        real_rows = real_rows_all[real_rows_all["run"] == held_run].copy()
        real_waves = real_waves_all[real_rows_all["run"].to_numpy() == held_run]
        if len(real_rows):
            b2_real = real_rows["stave"].to_numpy() == "B2"
            b2_rows = real_rows.loc[b2_real].reset_index(drop=True)
            b2_wave = real_waves[b2_real]
            b2_obs_amp = b2_rows["amplitude_adc"].to_numpy(dtype=float)
            src_natural = b2_rows.index.to_numpy()
            natural_meta = b2_rows.copy().reset_index(drop=True)
            pred_trad_nat = np.maximum(b2_obs_amp * np.exp(huber.predict(P07E.masked_features(b2_wave, b2_obs_amp, window))), b2_obs_amp)
            pred_gbr_nat = np.maximum(b2_obs_amp * np.exp(gbr.predict(P07E.masked_features(b2_wave, b2_obs_amp, window))), b2_obs_amp)
            nat_trad_features = risk_feature_frame(b2_wave, b2_obs_amp, pred_trad_nat, src_natural, natural_meta, template, window)
            nat_gbr_features = risk_feature_frame(b2_wave, b2_obs_amp, pred_gbr_nat, src_natural, natural_meta, template, window)
            nat_trad_mask = apply_traditional_rule(nat_trad_features, trad_rule)
            nat_gbr_mask, _, _ = apply_ml_rule(nat_gbr_features, ml_rule)
            natural_rows.append(
                {
                    "run": held_run,
                    "rule": "traditional_envelope",
                    "natural_candidates": int(len(b2_rows)),
                    "natural_acceptance_rate": float(nat_trad_mask.mean()) if len(nat_trad_mask) else 0.0,
                    **natural_summary(real_rows, real_waves, b2_rows.loc[nat_trad_mask, "event_uid"].to_numpy(), pred_trad_nat, template),
                }
            )
            natural_rows.append(
                {
                    "run": held_run,
                    "rule": "ml_conformal_risk",
                    "natural_candidates": int(len(b2_rows)),
                    "natural_acceptance_rate": float(nat_gbr_mask.mean()) if len(nat_gbr_mask) else 0.0,
                    **natural_summary(real_rows, real_waves, b2_rows.loc[nat_gbr_mask, "event_uid"].to_numpy(), pred_gbr_nat, template),
                }
            )

        shuffled = train_gbr["abs_frac_error"].to_numpy(dtype=float).copy()
        rng.shuffle(shuffled)
        shuffle_model = GradientBoostingRegressor(n_estimators=80, max_depth=2, learning_rate=0.05, random_state=int(cfg["random_seed"]) + 7000 + held_run)
        shuffle_model.fit(risk_matrix(train_gbr), shuffled)
        shuffle_upper = shuffle_model.predict(risk_matrix(held_gbr)) + float(ml_rule["conformal_q90"])
        shuffle_mask = shuffle_upper <= float(ml_rule["risk_upper_threshold"])
        leakage_rows.append(
            {
                "run": held_run,
                "check": "shuffled_abs_error_risk_acceptance_rate",
                "value": float(shuffle_mask.mean()),
                "flag": bool(shuffle_mask.mean() > max(0.9, 1.5 * max(float(ml_mask.mean()), 1.0e-9))),
            }
        )

    print("3/5 summarizing held-out metrics", flush=True)
    artificial = pd.concat(artificial_rows, ignore_index=True)
    train_eval = pd.concat(train_eval_rows, ignore_index=True)
    natural = pd.DataFrame(natural_rows)
    rules = pd.DataFrame(rule_rows)
    p07e_repro_by_run = pd.DataFrame(reproduction_fold_rows)
    summary, bootstrap = run_bootstrap_summary(artificial, natural, cfg)
    p07e_res68 = float(np.percentile(np.abs(np.concatenate([g["frac_error"].to_numpy() for _, g in artificial[artificial["method"] == "gbr_masked"].groupby("run")])), 68))
    p07e_bias = float(np.median(artificial.loc[artificial["method"] == "gbr_masked", "frac_error"]))
    b2_count = int(b2_mask.sum())
    reproduction = pd.DataFrame(
        [
            {
                "quantity": "Sample-II B2 selected pulses",
                "expected": int(cfg["expected_sample_ii_b2_selected"]),
                "reproduced": b2_count,
                "delta": b2_count - int(cfg["expected_sample_ii_b2_selected"]),
                "pass": b2_count == int(cfg["expected_sample_ii_b2_selected"]),
            },
            {
                "quantity": "P07e w2_8/gbr_masked res68_abs_frac",
                "expected": float(cfg["expected_p07e_best_res68"]),
                "reproduced": p07e_res68,
                "delta": p07e_res68 - float(cfg["expected_p07e_best_res68"]),
                "pass": abs(p07e_res68 - float(cfg["expected_p07e_best_res68"])) <= float(cfg["p07e_reproduction_tolerance_res68"]),
            },
            {
                "quantity": "P07e w2_8/gbr_masked median_bias_frac",
                "expected": float(cfg["expected_p07e_best_bias"]),
                "reproduced": p07e_bias,
                "delta": p07e_bias - float(cfg["expected_p07e_best_bias"]),
                "pass": abs(p07e_bias - float(cfg["expected_p07e_best_bias"])) <= float(cfg["p07e_reproduction_tolerance_bias"]),
            },
            {
                "quantity": "Natural A_B2>=7000 with >=2 downstream selected events",
                "expected": "data-derived",
                "reproduced": int(len(event_ids)),
                "delta": "",
                "pass": True,
            },
        ]
    )
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw reproduction gate failed")

    leakage = pd.DataFrame(leakage_rows)
    train_overlap = 0
    for run in cfg["runs"]:
        held = artificial[artificial["run"] == int(run)]["event_uid"]
        train = train_eval[train_eval["run"] == int(run)]["event_uid"]
        train_overlap += len(set(held).intersection(set(train)))
    primary = summary.set_index("rule").to_dict(orient="index")
    too_good = bool(
        primary["ml_conformal_risk"]["amp_res68_abs_frac"] < 0.02
        or (
            primary["ml_conformal_risk"]["amp_res68_abs_frac"] < 0.05
            and primary["ml_conformal_risk"]["acceptance_rate"] > 0.95
        )
    )
    leakage = pd.concat(
        [
            pd.DataFrame(
                [
                    {"run": "all", "check": "heldout_train_event_overlap", "value": float(train_overlap), "flag": bool(train_overlap != 0)},
                    {"run": "all", "check": "primary_features_exclude_run_event_truth", "value": 1.0, "flag": False},
                    {"run": "all", "check": "too_good_trigger", "value": float(too_good), "flag": too_good},
                ]
            ),
            leakage,
        ],
        ignore_index=True,
    )

    best_rule = summary.sort_values(["amp_res68_abs_frac", "catastrophic_rate"]).iloc[0]
    finding = (
        f"The ML conformal rule accepts {primary['ml_conformal_risk']['acceptance_rate']:.3f} of held-out artificial rows "
        f"with amplitude res68 {primary['ml_conformal_risk']['amp_res68_abs_frac']:.4f}, median bias "
        f"{primary['ml_conformal_risk']['amp_bias_median_frac']:.4f}, catastrophic rate "
        f"{primary['ml_conformal_risk']['catastrophic_rate']:.4f}, and natural timing-tail delta "
        f"{primary['ml_conformal_risk']['timing_tail_delta_natural']:.4f}. The traditional envelope accepts "
        f"{primary['traditional_envelope']['acceptance_rate']:.3f} with res68 "
        f"{primary['traditional_envelope']['amp_res68_abs_frac']:.4f}. Preferred rule: {best_rule['rule']}."
    )

    print("4/5 writing report artifacts", flush=True)
    def group_metrics(g: pd.DataFrame) -> pd.Series:
        row = metric_from_events(g[g["accepted"]], float(cfg["bias_envelope_abs_frac"]))
        row["acceptance_rate"] = float(g["accepted"].mean())
        return pd.Series(row)

    artificial_by_run = (
        artificial.groupby(["run", "rule"], as_index=False)
        .apply(group_metrics)
        .reset_index(drop=True)
    )
    reproduction.to_csv(out / "reproduction_gate.csv", index=False)
    p07e_repro_by_run.to_csv(out / "p07e_reproduction_by_run.csv", index=False)
    artificial_by_run.to_csv(out / "artificial_acceptance_by_run.csv", index=False)
    summary.to_csv(out / "artificial_acceptance_summary.csv", index=False)
    natural.to_csv(out / "natural_acceptance_by_run.csv", index=False)
    rules.to_csv(out / "acceptance_rule_params.csv", index=False)
    leakage.to_csv(out / "leakage_checks.csv", index=False)
    artificial.sample(min(len(artificial), int(cfg.get("event_sample_rows", 5000))), random_state=int(cfg["random_seed"])).to_csv(out / "artificial_acceptance_events_sample.csv", index=False)
    bootstrap.sample(min(len(bootstrap), int(cfg.get("bootstrap_sample_rows", 5000))), random_state=int(cfg["random_seed"])).to_csv(out / "run_block_bootstrap_sample.csv", index=False)

    input_rows = []
    for run in cfg["runs"]:
        path = raw_path(cfg, int(run))
        input_rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out / "input_sha256.csv", index=False)

    result = {
        "ticket": cfg["ticket"],
        "study": cfg["study"],
        "worker": cfg["worker"],
        "title": cfg["title"],
        "config_path": str(args.config),
        "split": "leave-one-run-out by run over Sample-II analysis runs; all rules calibrated on non-held-out runs",
        "raw_root": cfg["raw_root"],
        "runs": cfg["runs"],
        "reproduction": reproduction.to_dict(orient="records"),
        "summary": summary.to_dict(orient="records"),
        "rules": rules.to_dict(orient="records"),
        "leakage_flags": int(leakage["flag"].sum()),
        "too_good_triggered": too_good,
        "finding": finding,
        "preferred_rule": str(best_rule["rule"]),
        "next_tickets": [],
        "follow_up_ticket_status": "skipped: existing STUDIES.md already contains P07g/P14-style accept-veto and downstream saturation follow-ups; no clearly novel non-duplicate ticket appended",
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 2),
    }
    (out / "result.json").write_text(json.dumps(json_sanitize(result), indent=2), encoding="utf-8")
    write_report(out, result, reproduction, summary, rules, leakage)
    manifest = {
        "ticket": cfg["ticket"],
        "study": cfg["study"],
        "worker": cfg["worker"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "command": " ".join([sys.executable] + sys.argv),
        "config": cfg,
        "inputs_sha256": {row["path"]: row["sha256"] for row in input_rows},
        "outputs_sha256": output_hashes(out),
        "runtime_sec": result["runtime_sec"],
    }
    (out / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2), encoding="utf-8")
    print(json.dumps({"ticket": cfg["ticket"], "preferred_rule": result["preferred_rule"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
