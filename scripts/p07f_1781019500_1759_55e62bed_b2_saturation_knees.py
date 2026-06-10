#!/usr/bin/env python3
"""P07f: estimate natural B2 saturation knees from odd duplicate signatures.

The raw B-stack ROOT files are read directly.  The odd duplicate channel is used to identify the
point where the physical even B2 channel bends away from its low-amplitude response.  Estimates
are made per held-out run with event bootstrap CIs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import ExtraTreesClassifier


@dataclass
class PiecewiseFit:
    intercept: float
    pre_slope: float
    slope_change: float
    xk: float
    sse: float
    n_bins: int

    @property
    def post_slope(self) -> float:
        return self.pre_slope + self.slope_change

    @property
    def knee_adc(self) -> float:
        return self.xk

    def predict(self, x: np.ndarray) -> np.ndarray:
        return self.intercept + self.pre_slope * x + self.slope_change * np.maximum(0.0, x - self.xk)

    def low_linear(self, x: np.ndarray) -> np.ndarray:
        return self.intercept + self.pre_slope * x


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


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for group_runs in config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def raw_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_batches(path: Path, step_size: int = 30000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def extract_b2_duplicate_rows(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    b2_ch = int(config["staves"]["B2"])
    b2_odd_ch = int(config["duplicate_readout_channels"]["B2"])
    physical_channels = np.asarray([int(ch) for ch in config["staves"].values()], dtype=int)
    groups = run_group_lookup(config)
    sel_cfg = config["duplicate_selection"]

    frames: List[pd.DataFrame] = []
    waves: List[np.ndarray] = []
    counts: List[dict] = []
    for run in configured_runs(config):
        path = raw_path(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        count = {
            "run": run,
            "group": groups[run],
            "events_total": 0,
            "s00_selected_pulses": 0,
            "b2_selected": 0,
            "p07e_high_duplicate_rows": 0,
            "p07f_duplicate_rows": 0,
        }
        for batch in iter_batches(path):
            eventno = np.asarray(batch["EVENTNO"], dtype=np.int64)
            evt = np.asarray(batch["EVT"], dtype=np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            even_all = corrected[:, physical_channels, :]
            even_amp_all = even_all.max(axis=-1)
            b2 = corrected[:, b2_ch, :]
            odd = -corrected[:, b2_odd_ch, :]
            b2_amp = b2.max(axis=1)
            b2_charge = np.clip(b2, 0.0, None).sum(axis=1)
            b2_peak = b2.argmax(axis=1)
            odd_amp = odd.max(axis=1)
            odd_charge = np.clip(odd, 0.0, None).sum(axis=1)
            odd_peak = odd.argmax(axis=1)
            odd_ok = (odd_amp >= float(sel_cfg["min_odd_amp"])) & (odd_charge >= float(sel_cfg["min_odd_charge"]))
            selected = b2_amp > cut
            high_duplicate = (b2_amp >= float(config["saturation_proxy_adc"])) & odd_ok
            keep = (
                (b2_amp >= float(sel_cfg["min_b2_amp_adc"]))
                & odd_ok
                & (b2_peak >= int(sel_cfg["min_peak_sample"]))
                & (b2_peak <= int(sel_cfg["max_peak_sample"]))
            )
            count["events_total"] += int(len(eventno))
            count["s00_selected_pulses"] += int((even_amp_all > cut).sum())
            count["b2_selected"] += int(selected.sum())
            count["p07e_high_duplicate_rows"] += int(high_duplicate.sum())
            count["p07f_duplicate_rows"] += int(keep.sum())
            if not keep.any():
                continue
            idx = np.flatnonzero(keep)
            kept_waves = b2[idx].astype(np.float32)
            plateau_count = (kept_waves >= (0.995 * b2_amp[idx])[:, None]).sum(axis=1)
            top2 = np.sort(kept_waves, axis=1)[:, -2:]
            top2_gap_frac = (top2[:, 1] - top2[:, 0]) / np.maximum(top2[:, 1], 1.0)
            waves.append(kept_waves)
            frames.append(
                pd.DataFrame(
                    {
                        "run": run,
                        "group": groups[run],
                        "eventno": eventno[idx],
                        "evt": evt[idx],
                        "b2_amp": b2_amp[idx],
                        "b2_charge": b2_charge[idx],
                        "b2_peak": b2_peak[idx].astype(np.int16),
                        "odd_amp": odd_amp[idx],
                        "odd_charge": odd_charge[idx],
                        "odd_peak": odd_peak[idx].astype(np.int16),
                        "log_odd_charge": np.log(np.maximum(odd_charge[idx], 1.0)),
                        "duplicate_charge_ratio": odd_charge[idx] / np.maximum(b2_charge[idx], 1.0),
                        "plateau_count": plateau_count.astype(np.int16),
                        "top2_gap_frac": top2_gap_frac,
                    }
                )
            )
        counts.append(count)
    return pd.concat(frames, ignore_index=True), np.vstack(waves), pd.DataFrame(counts)


def binned_xy(frame: pd.DataFrame, bins: int, min_bin_rows: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = frame["b2_amp"].to_numpy(dtype=float)
    y = frame["duplicate_charge_ratio"].to_numpy(dtype=float)
    edges = np.unique(np.quantile(x, np.linspace(0.0, 1.0, int(bins) + 1)))
    if len(edges) < 4:
        edges = np.linspace(float(np.min(x)), float(np.max(x)), int(bins) + 1)
    xs: List[float] = []
    ys: List[float] = []
    ws: List[float] = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (x >= lo) & (x <= hi if hi == edges[-1] else x < hi)
        n = int(mask.sum())
        if n < int(min_bin_rows):
            continue
        xs.append(float(np.median(x[mask])))
        ys.append(float(np.median(y[mask])))
        ws.append(float(np.sqrt(n)))
    return np.asarray(xs), np.asarray(ys), np.asarray(ws)


def fit_piecewise(frame: pd.DataFrame, config: dict) -> PiecewiseFit:
    trad = config["traditional"]
    x, y, w = binned_xy(frame, int(trad["bins"]), int(trad["min_bin_rows"]))
    if len(x) < 12:
        raise ValueError(f"too few populated duplicate-proxy bins: {len(x)}")
    lo, hi = np.percentile(x, [20, 86])
    grids = np.linspace(lo, hi, int(trad["grid_points"]))
    best = None
    min_ratio = float(trad["min_post_to_pre_slope_ratio"])
    max_ratio = float(trad["max_post_to_pre_slope_ratio"])
    for xk in grids:
        design = np.column_stack([np.ones_like(x), x, np.maximum(0.0, x - xk)])
        wd = design * w[:, None]
        wy = y * w
        coef, *_ = np.linalg.lstsq(wd, wy, rcond=None)
        pred = design @ coef
        pre = float(coef[1])
        post = float(coef[1] + coef[2])
        ratio = post / pre if abs(pre) > 1e-9 else np.inf
        if pre <= 0.0 or ratio < min_ratio or ratio > max_ratio:
            continue
        sse = float(np.mean(((y - pred) * w) ** 2))
        cand = PiecewiseFit(float(coef[0]), pre, float(coef[2]), float(xk), sse, int(len(x)))
        if best is None or cand.sse < best.sse:
            best = cand
    if best is None:
        raise ValueError("no constrained piecewise duplicate-proxy knee fit")
    return best


def waveform_features(wave: np.ndarray, frame: pd.DataFrame) -> np.ndarray:
    amp = np.maximum(frame["b2_amp"].to_numpy(dtype=float), 1.0)
    charge = np.maximum(frame["b2_charge"].to_numpy(dtype=float), 1.0)
    norm = wave.astype(float) / amp[:, None]
    return np.column_stack(
        [
            np.log(amp),
            charge / amp,
            frame["b2_peak"].to_numpy(dtype=float),
            frame["plateau_count"].to_numpy(dtype=float),
            frame["top2_gap_frac"].to_numpy(dtype=float),
            np.clip(wave[:, 10:], 0.0, None).sum(axis=1) / charge,
            (wave > (0.50 * amp)[:, None]).sum(axis=1),
            norm,
        ]
    )


def saturation_labels(frame: pd.DataFrame, fit: PiecewiseFit, config: dict) -> np.ndarray:
    x = frame["b2_amp"].to_numpy(dtype=float)
    y = frame["duplicate_charge_ratio"].to_numpy(dtype=float)
    low_pred = np.maximum(fit.low_linear(x), 1e-9)
    residual_frac = (y - low_pred) / low_pred
    return (
        (x >= fit.xk)
        & (
            (residual_frac >= float(config["ml"]["saturation_residual_frac"]))
            | (frame["plateau_count"].to_numpy() >= 2)
        )
    )


def train_ml(frame: pd.DataFrame, wave: np.ndarray, train_mask: np.ndarray, train_fit: PiecewiseFit, config: dict, rng: np.random.Generator):
    train_idx = np.flatnonzero(train_mask)
    labels = saturation_labels(frame.iloc[train_idx], train_fit, config)
    max_rows = int(config["ml"]["max_train_rows"])
    if len(train_idx) > max_rows:
        chosen = rng.choice(np.arange(len(train_idx)), size=max_rows, replace=False)
        train_idx = train_idx[chosen]
        labels = labels[chosen]
    model = ExtraTreesClassifier(
        n_estimators=int(config["ml"]["n_estimators"]),
        max_depth=int(config["ml"]["max_depth"]),
        min_samples_leaf=int(config["ml"]["min_samples_leaf"]),
        n_jobs=-1,
        random_state=int(config["ml"]["random_seed"]),
        class_weight="balanced",
    )
    model.fit(waveform_features(wave[train_idx], frame.iloc[train_idx]), labels.astype(int))
    return model, labels


def knee_from_probability(amp: np.ndarray, prob: np.ndarray, threshold: float) -> float:
    finite = np.isfinite(amp) & np.isfinite(prob)
    amp = amp[finite]
    prob = prob[finite]
    if len(amp) < 50:
        return float("nan")
    order = np.argsort(amp)
    amp = amp[order]
    prob = prob[order]
    edges = np.unique(np.quantile(amp, np.linspace(0.0, 1.0, 61)))
    xs: List[float] = []
    ps: List[float] = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (amp >= lo) & (amp <= hi if hi == edges[-1] else amp < hi)
        if mask.sum() < 20:
            continue
        xs.append(float(np.median(amp[mask])))
        ps.append(float(np.mean(prob[mask])))
    if len(xs) < 8:
        return float("nan")
    xs_arr = np.asarray(xs)
    ps_arr = np.convolve(np.asarray(ps), np.ones(3) / 3.0, mode="same")
    after = np.flatnonzero((ps_arr >= threshold) & (xs_arr >= np.percentile(amp, 45)))
    if len(after):
        return float(xs_arr[int(after[0])])
    return float(xs_arr[int(np.argmax(ps_arr))])


def estimate_ml_knee(model, frame: pd.DataFrame, wave: np.ndarray, threshold: float) -> Tuple[float, np.ndarray]:
    prob = model.predict_proba(waveform_features(wave, frame))[:, 1]
    return knee_from_probability(frame["b2_amp"].to_numpy(dtype=float), prob, threshold), prob


def bootstrap_traditional(frame: pd.DataFrame, config: dict, rng: np.random.Generator, reps: int) -> List[float]:
    vals: List[float] = []
    n = len(frame)
    for _ in range(reps):
        idx = rng.integers(0, n, size=n)
        try:
            vals.append(float(fit_piecewise(frame.iloc[idx], config).knee_adc))
        except Exception:
            continue
    return vals


def bootstrap_ml(frame: pd.DataFrame, prob: np.ndarray, config: dict, rng: np.random.Generator, reps: int) -> List[float]:
    vals: List[float] = []
    amp = frame["b2_amp"].to_numpy(dtype=float)
    n = len(frame)
    for _ in range(reps):
        idx = rng.integers(0, n, size=n)
        val = knee_from_probability(amp[idx], prob[idx], float(config["ml"]["probability_threshold"]))
        if np.isfinite(val):
            vals.append(float(val))
    return vals


def ci95(vals: List[float]) -> List[float]:
    if not vals:
        return [float("nan"), float("nan")]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def run_block_summary(per_run: pd.DataFrame, rng: np.random.Generator, reps: int) -> pd.DataFrame:
    rows: List[dict] = []
    for method in sorted(per_run["method"].unique()):
        vals = per_run.loc[per_run["method"] == method, "knee_adc"].to_numpy(dtype=float)
        vals = vals[np.isfinite(vals)]
        boots = [float(np.median(rng.choice(vals, size=len(vals), replace=True))) for _ in range(reps)]
        rows.append(
            {
                "method": method,
                "runs": int(len(vals)),
                "median_knee_adc": float(np.median(vals)),
                "run_block_median_knee_adc_ci95": ci95(boots),
                "run_to_run_iqr_adc": float(np.percentile(vals, 75) - np.percentile(vals, 25)),
                "min_knee_adc": float(np.min(vals)),
                "max_knee_adc": float(np.max(vals)),
            }
        )
    return pd.DataFrame(rows)


def leakage_audit(frame: pd.DataFrame, wave: np.ndarray, runs: np.ndarray, per_run: pd.DataFrame, config: dict) -> dict:
    overlaps: List[int] = []
    for run in runs:
        train = frame["run"].to_numpy() != run
        held = frame["run"].to_numpy() == run
        train_hashes = {hashlib.sha256(row.astype(np.float32).tobytes()).hexdigest() for row in wave[train]}
        overlap = sum(1 for row in wave[held] if hashlib.sha256(row.astype(np.float32).tobytes()).hexdigest() in train_hashes)
        overlaps.append(int(overlap))
    ml = per_run[per_run["method"] == "ml_waveform_classifier"]
    trad = per_run[per_run["method"] == "traditional_duplicate_piecewise"]
    merged = trad[["run", "knee_adc"]].merge(ml[["run", "knee_adc"]], on="run", suffixes=("_trad", "_ml"))
    merged = merged[np.isfinite(merged["knee_adc_trad"]) & np.isfinite(merged["knee_adc_ml"])]
    median_abs_delta = float(np.median(np.abs(merged["knee_adc_ml"] - merged["knee_adc_trad"])))
    too_good = bool(median_abs_delta < 5.0)
    return {
        "split": "leave-one-run-out by run",
        "ml_features_excluded": ["run_id", "event_id", "odd_channel_samples", "odd_amp", "odd_charge", "odd_peak", "heldout_duplicate_labels"],
        "max_exact_waveform_hash_overlap_train_heldout": int(max(overlaps) if overlaps else 0),
        "median_abs_ml_minus_traditional_knee_adc": median_abs_delta,
        "too_good_triggered": too_good,
        "too_good_rule": "median absolute ML-traditional knee difference below 5 ADC or exact waveform overlap would trigger manual leakage review",
    }


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(
    out_dir: Path,
    result: dict,
    reproduction: pd.DataFrame,
    summary: pd.DataFrame,
    per_run: pd.DataFrame,
    traditional_families: pd.DataFrame,
) -> None:
    brief = per_run.pivot(index="run", columns="method", values="knee_adc").reset_index()
    lines = [
        "# P07f: natural B2 saturation knees from duplicate readout",
        "",
        f"Ticket `{result['ticket_id']}`. Raw B-stack ROOT was read directly; no Monte Carlo was used.",
        "",
        "## Raw reproduction first",
        "",
        reproduction.to_markdown(index=False),
        "",
        "## Method",
        "",
        "Rows are physical B2 pulses with an odd duplicate readout. The duplicate channel is used as an independent size proxy to find where the even B2 amplitude bends away from its low-amplitude response.",
        "",
        "- `traditional_duplicate_piecewise`: binned median odd-charge/B2-charge ratio versus B2 amplitude, fit with a constrained linear-to-bent piecewise model; the knee is the fitted upward bend point in B2 ADC.",
        "- `ml_waveform_classifier`: leave-one-run-out ExtraTrees classifier trained on duplicate-derived saturation labels from the other runs, using only even-channel waveform features; the knee is where held-out saturation probability crosses 0.5 versus B2 amplitude.",
        "",
        "Each row is held out by run. CIs in `knee_by_run.csv` are event bootstraps of the held-out run with the trained model fixed for the ML method. The summary CI resamples held-out runs.",
        "",
        "## Knee summary",
        "",
        summary.to_markdown(index=False),
        "",
        "## Traditional run families",
        "",
        traditional_families.to_markdown(index=False),
        "",
        "## Per-run knees",
        "",
        brief.to_markdown(index=False),
        "",
        "Full per-run event-bootstrap intervals and fit diagnostics are in `knee_by_run.csv`.",
        "",
        "## Leakage checks",
        "",
        f"- Split: `{result['leakage_audit']['split']}`.",
        "- ML features exclude run id, event id, all odd-channel variables, and held-out duplicate labels.",
        f"- Max exact even-waveform hash overlap between train and held-out runs: `{result['leakage_audit']['max_exact_waveform_hash_overlap_train_heldout']}`.",
        f"- Median absolute ML-minus-traditional knee difference: `{result['leakage_audit']['median_abs_ml_minus_traditional_knee_adc']:.1f}` ADC.",
        f"- Too-good trigger fired: `{result['leakage_audit']['too_good_triggered']}`.",
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p07f_1781019500_1759_55e62bed_b2_saturation_knees.py --config configs/p07f_1781019500_1759_55e62bed_b2_saturation_knees.json",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p07f_1781019500_1759_55e62bed_b2_saturation_knees.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    print("1/4 extracting B2 duplicate rows and reproducing raw counts", flush=True)
    frame, wave, counts = extract_b2_duplicate_rows(config)
    reproduction = pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulse records",
                "expected": int(config["expected_selected_pulses"]),
                "reproduced": int(counts["s00_selected_pulses"].sum()),
                "delta": int(counts["s00_selected_pulses"].sum()) - int(config["expected_selected_pulses"]),
                "pass": int(counts["s00_selected_pulses"].sum()) == int(config["expected_selected_pulses"]),
            },
            {
                "quantity": "P07e high-amplitude B2 duplicate rows",
                "expected": int(config["expected_p07e_high_duplicate_rows"]),
                "reproduced": int(counts["p07e_high_duplicate_rows"].sum()),
                "delta": int(counts["p07e_high_duplicate_rows"].sum()) - int(config["expected_p07e_high_duplicate_rows"]),
                "pass": int(counts["p07e_high_duplicate_rows"].sum()) == int(config["expected_p07e_high_duplicate_rows"]),
            },
            {
                "quantity": "P07f duplicate-proxy knee rows",
                "expected": "data-derived",
                "reproduced": int(counts["p07f_duplicate_rows"].sum()),
                "delta": "",
                "pass": True,
            },
        ]
    )
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw reproduction gate failed")

    print("2/4 estimating traditional and ML held-out run knees", flush=True)
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    all_run_fit = fit_piecewise(frame, config)
    per_run_rows: List[dict] = []
    prediction_rows: List[pd.DataFrame] = []
    reps = int(config["bootstrap_reps"])
    for run in runs:
        print(f"  held-out run {int(run)}", flush=True)
        held_mask = frame["run"].to_numpy() == run
        train_mask = ~held_mask
        held = frame.loc[held_mask].reset_index(drop=True)
        held_wave = wave[held_mask]
        if len(held) < int(config["traditional"]["min_run_rows"]):
            continue

        trad_fit = None
        trad_status = "ok"
        try:
            trad_fit = fit_piecewise(held, config)
            trad_boot = bootstrap_traditional(held, config, rng, reps)
            trad_row = {
                "run": int(run),
                "method": "traditional_duplicate_piecewise",
                "n": int(len(held)),
                "knee_adc": float(trad_fit.knee_adc),
                "knee_adc_ci95": ci95(trad_boot),
                "xk_b2_amp_adc": float(trad_fit.xk),
                "post_to_pre_slope_ratio": float(trad_fit.post_slope / trad_fit.pre_slope),
                "bootstrap_reps_ok": int(len(trad_boot)),
                "fit_status": trad_status,
            }
        except Exception as exc:
            trad_status = f"no stable constrained duplicate-ratio bend: {exc}"
            trad_row = {
                "run": int(run),
                "method": "traditional_duplicate_piecewise",
                "n": int(len(held)),
                "knee_adc": float("nan"),
                "knee_adc_ci95": [float("nan"), float("nan")],
                "xk_b2_amp_adc": float("nan"),
                "post_to_pre_slope_ratio": float("nan"),
                "bootstrap_reps_ok": 0,
                "fit_status": trad_status,
            }
        per_run_rows.append(trad_row)

        train_fit = fit_piecewise(frame.loc[train_mask], config)
        ml_model, train_labels = train_ml(frame, wave, train_mask, train_fit, config, rng)
        ml_knee, ml_prob = estimate_ml_knee(ml_model, held, held_wave, float(config["ml"]["probability_threshold"]))
        ml_boot = bootstrap_ml(held, ml_prob, config, rng, reps)
        per_run_rows.append(
            {
                "run": int(run),
                "method": "ml_waveform_classifier",
                "n": int(len(held)),
                "knee_adc": float(ml_knee),
                "knee_adc_ci95": ci95(ml_boot),
                "xk_b2_amp_adc": float("nan"),
                "post_to_pre_slope_ratio": float("nan"),
                "bootstrap_reps_ok": int(len(ml_boot)),
                "train_positive_frac": float(np.mean(train_labels)),
                "fit_status": "ok",
            }
        )
        label_fit = trad_fit if trad_fit is not None else all_run_fit
        prediction_rows.append(
            pd.DataFrame(
                {
                    "run": int(run),
                    "b2_amp": held["b2_amp"].to_numpy(dtype=float),
                    "ml_saturation_probability": ml_prob,
                    "traditional_duplicate_saturation_label": saturation_labels(held, label_fit, config),
                    "traditional_label_source": "heldout_run_fit" if trad_fit is not None else "global_fallback_fit",
                }
            )
        )

    per_run = pd.DataFrame(per_run_rows).sort_values(["run", "method"])
    predictions = pd.concat(prediction_rows, ignore_index=True)
    summary = run_block_summary(per_run, rng, reps).sort_values("method")

    print("3/4 auditing leakage and writing artifacts", flush=True)
    leakage = leakage_audit(frame, wave, runs, per_run, config)
    trad_summary = summary[summary["method"] == "traditional_duplicate_piecewise"].iloc[0]
    ml_summary = summary[summary["method"] == "ml_waveform_classifier"].iloc[0]
    delta = float(ml_summary["median_knee_adc"] - trad_summary["median_knee_adc"])
    trad_valid = per_run[
        (per_run["method"] == "traditional_duplicate_piecewise")
        & np.isfinite(per_run["knee_adc"].to_numpy(dtype=float))
    ].copy()
    trad_valid["family"] = np.where(trad_valid["knee_adc"] >= 5000.0, "high-knee", "low-knee")
    traditional_families = (
        trad_valid.groupby("family")
        .agg(
            runs=("run", "nunique"),
            median_knee_adc=("knee_adc", "median"),
            min_knee_adc=("knee_adc", "min"),
            max_knee_adc=("knee_adc", "max"),
        )
        .reset_index()
        .sort_values("median_knee_adc")
    )
    no_trad_runs = sorted(
        int(run)
        for run in per_run.loc[
            (per_run["method"] == "traditional_duplicate_piecewise")
            & ~np.isfinite(per_run["knee_adc"].to_numpy(dtype=float)),
            "run",
        ]
    )
    finding = (
        f"The duplicate-ratio method does not support a single natural B2 knee. It finds two run "
        f"families: a low-knee family near {traditional_families.iloc[0]['median_knee_adc']:.0f} ADC "
        f"and a high-knee family near {traditional_families.iloc[-1]['median_knee_adc']:.0f} ADC; "
        f"runs {no_trad_runs} have no stable constrained duplicate-ratio bend. The held-out waveform "
        f"ML classifier instead places its median knee at {ml_summary['median_knee_adc']:.0f} ADC "
        f"with CI {ml_summary['run_block_median_knee_adc_ci95']} (ML minus traditional median "
        f"{delta:+.0f} ADC), so it does not validate the duplicate-ratio knee calibration. "
        "For production timing/PID, recovered B2 amplitudes should therefore carry run-family "
        "systematics and should not be accepted above a fixed 7000 ADC proxy without a per-run "
        "duplicate-readout check."
    )
    result = {
        "study": "P07f",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_reproduction": reproduction.to_dict(orient="records"),
        "split": "leave-one-run-out by run; event-bootstrap CIs within held-out runs; run-block bootstrap summary",
        "methods": ["traditional_duplicate_piecewise", "ml_waveform_classifier"],
        "summary": summary.to_dict(orient="records"),
        "traditional_run_families": traditional_families.to_dict(orient="records"),
        "leakage_audit": leakage,
        "global_duplicate_piecewise_knee_adc": float(all_run_fit.knee_adc),
        "finding": finding,
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 2),
    }

    counts.to_csv(out_dir / "run_counts.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_gate.csv", index=False)
    per_run.to_csv(out_dir / "knee_by_run.csv", index=False)
    summary.to_csv(out_dir / "knee_summary.csv", index=False)
    predictions.groupby("run").agg(
        n=("b2_amp", "size"),
        median_ml_probability=("ml_saturation_probability", "median"),
        frac_ml_probability_gt_half=("ml_saturation_probability", lambda s: float(np.mean(s > 0.5))),
        frac_traditional_duplicate_label=("traditional_duplicate_saturation_label", "mean"),
    ).reset_index().to_csv(out_dir / "prediction_sanity_by_run.csv", index=False)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, result, reproduction, summary, per_run, traditional_families)

    inputs = {str(raw_path(config, int(run))): sha256_file(raw_path(config, int(run))) for run in configured_runs(config)}
    manifest = {
        "ticket": config["ticket_id"],
        "study": "P07f",
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
    print(json.dumps({"out_dir": str(out_dir), "finding": finding, "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
