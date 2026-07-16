#!/usr/bin/env python3
"""S38c PID-aware pulse-shape disentanglement benchmark.

The ticket asks which pulse-shape features retain PID information after
controlling for timing, energy, pedestal, pile-up, and saturation.  This runner
uses the keyed digitized GEANT4 native-join benchmark as the fixed model panel
and adds S38c-specific nuisance residualization, run/species bootstrap
intervals, and stress-slice diagnostics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd
import uproot
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import average_precision_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

REQUIRED_METHODS = {
    "strong_traditional": "deltaE_over_E_likelihood_template",
    "ridge": "ridge",
    "gradient_boosted_trees": "gradient_boosted_trees",
    "mlp": "mlp",
    "one_dimensional_cnn": "1d_cnn",
    "waveform_transformer": "joint_sequence_transformer",
    "new_architecture": "template_residual_boosted_stack_new",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def scan_raw_selected_counts(config: dict) -> pd.DataFrame:
    """Count selected B-stave pulses directly from raw ROOT without materializing waves."""

    raw_dir = Path(config["raw_root_dir"])
    if not raw_dir.exists():
        raise FileNotFoundError(raw_dir)
    channels = np.asarray([int(config["staves"][name]) for name in ["B2", "B4", "B6", "B8"]], dtype=int)
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rows = []
    for run in configured_runs(config):
        path = raw_dir / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(path)
        selected_total = 0
        events_total = 0
        events_with_selected = 0
        stave_counts = {name: 0 for name in ["B2", "B4", "B6", "B8"]}
        tree = uproot.open(path)["h101"]
        for batch in tree.iterate(["HRDv"], step_size=25000, library="np"):
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            wave = raw[:, channels, :]
            baseline = np.median(wave[:, :, baseline_idx], axis=-1)
            amp = (wave - baseline[:, :, None]).max(axis=-1)
            selected = amp > cut
            events_total += int(len(raw))
            events_with_selected += int(selected.any(axis=1).sum())
            selected_total += int(selected.sum())
            for i, name in enumerate(["B2", "B4", "B6", "B8"]):
                stave_counts[name] += int(selected[:, i].sum())
        row = {
            "run": int(run),
            "events_total": events_total,
            "events_with_selected": events_with_selected,
            "selected_pulses": selected_total,
        }
        row.update(stave_counts)
        rows.append(row)
    return pd.DataFrame(rows)


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def sigma68(values: Iterable[float]) -> float:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    return float(0.5 * (np.percentile(arr, 84.0) - np.percentile(arr, 16.0)))


def safe_auc(y: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    if len(y) == 0 or len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, score))


def safe_ap(y: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    if len(y) == 0 or len(np.unique(y)) < 2:
        return float("nan")
    return float(average_precision_score(y, score))


def selected_prediction_frame(source: Path) -> pd.DataFrame:
    pred = pd.read_csv(source / "event_predictions.csv")
    missing = set(REQUIRED_METHODS.values()) - set(pred["method"].unique())
    if missing:
        raise RuntimeError(f"source benchmark is missing required methods: {sorted(missing)}")
    pred = pred[pred["method"].isin(REQUIRED_METHODS.values())].copy()
    pred["accepted"] = ~pred["failed"].astype(bool)
    pred["pid_label_pred"] = (pred["pid_score"] >= 0.5).astype(int)
    pred["pred_energy_mev"] = (pred["amp1_adc"].fillna(0.0) + pred["amp2_adc"].fillna(0.0)) / 250.0
    pred["true_time_ns"] = pred["g4_energy_weighted_time_ns"].astype(float)
    pred["pred_time_ns"] = pred["t1_sample"].astype(float) * 4.0
    pred["time_residual_ns"] = pred["pred_time_ns"] - pred["true_time_ns"]
    pred["energy_fractional_residual"] = (
        pred["pred_energy_mev"] - pred["true_energy_mev"]
    ) / np.maximum(pred["true_energy_mev"], 1e-6)
    pred.loc[pred["failed"].astype(bool), ["time_residual_ns", "energy_fractional_residual"]] = np.nan
    pred["pedestal_abs_adc"] = np.abs(pred["truth_pedestal_adc"].astype(float))
    pred["pedestal_bin"] = pd.qcut(
        pred["pedestal_abs_adc"], 3, labels=["pedestal_low", "pedestal_mid", "pedestal_high"], duplicates="drop"
    ).astype(str)
    pred["energy_bin"] = pd.qcut(
        pred["true_energy_mev"], 3, labels=["energy_low", "energy_mid", "energy_high"], duplicates="drop"
    ).astype(str)
    pred["timing_bin"] = pd.qcut(
        pred["true_time_ns"], 3, labels=["time_early", "time_mid", "time_late"], duplicates="drop"
    ).astype(str)
    pred["saturation_bin"] = np.where(pred["truth_saturation_label"].astype(int) == 1, "saturated", "unsaturated")
    pred["pileup_bin"] = np.where(pred["truth_pileup_label"].astype(int) == 1, "pileup", "single")
    return pred


def nuisance_matrix(frame: pd.DataFrame) -> np.ndarray:
    x = pd.DataFrame(
        {
            "true_energy_mev": frame["true_energy_mev"].astype(float),
            "dedx_proxy": frame["dedx_proxy"].astype(float),
            "depth_index": frame["depth_index"].astype(float),
            "true_time_ns": frame["true_time_ns"].astype(float),
            "truth_pedestal_adc": frame["truth_pedestal_adc"].astype(float),
            "truth_pileup_label": frame["truth_pileup_label"].astype(float),
            "truth_saturation_label": frame["truth_saturation_label"].astype(float),
            "shape_area_over_amp": frame["shape_area_over_amp"].astype(float),
        }
    ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return x.to_numpy(dtype=float)


def residualized_scores(method_frame: pd.DataFrame) -> pd.DataFrame:
    train = method_frame["split"].eq("train").to_numpy()
    held = method_frame["split"].eq("heldout").to_numpy()
    y = method_frame["pid_label"].to_numpy(dtype=int)
    score = method_frame["pid_score"].to_numpy(dtype=float)
    x = nuisance_matrix(method_frame)

    nuisance_clf = make_pipeline(
        StandardScaler(),
        PolynomialFeatures(degree=2, include_bias=False),
        LogisticRegression(max_iter=1000, class_weight="balanced", C=0.6, solver="lbfgs"),
    )
    nuisance_reg = make_pipeline(
        StandardScaler(),
        PolynomialFeatures(degree=2, include_bias=False),
        LinearRegression(),
    )
    nuisance_clf.fit(x[train], y[train])
    nuisance_reg.fit(x[train], score[train])
    nuisance_pid = nuisance_clf.predict_proba(x)[:, 1]
    expected_score = nuisance_reg.predict(x)
    residual_score = score - expected_score
    out = method_frame.loc[held].copy()
    out["nuisance_pid_score"] = nuisance_pid[held]
    out["pid_score_residualized"] = residual_score[held]
    return out


def pearson_abs(a: pd.Series, b: pd.Series) -> float:
    x = np.asarray(a, dtype=float)
    y = np.asarray(b, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 3:
        return float("nan")
    return float(abs(np.corrcoef(x[mask], y[mask])[0, 1]))


def metrics(group: pd.DataFrame) -> Dict[str, float]:
    y = group["pid_label"].to_numpy(dtype=int)
    score = group["pid_score"].to_numpy(dtype=float)
    pred = (score >= 0.5).astype(int)
    accepted = group["accepted"].to_numpy(dtype=bool)
    positive = y == 1
    pileup = group["truth_pileup_label"].to_numpy(dtype=int) == 1
    single = ~pileup
    sat = group["truth_saturation_label"].to_numpy(dtype=int) == 1
    unsat = ~sat

    pid_auc = safe_auc(y, score)
    residual_auc = safe_auc(y, group["pid_score_residualized"].to_numpy(dtype=float))
    nuisance_auc = safe_auc(y, group["nuisance_pid_score"].to_numpy(dtype=float))
    purity = float(precision_score(y, pred, zero_division=0))
    efficiency = float(recall_score(y, pred, zero_division=0))
    pileup_miss_rate = float((~accepted[pileup]).mean()) if pileup.any() else float("nan")
    false_split_rate = float(accepted[single].mean()) if single.any() else float("nan")
    energy_drift = float(np.nanmedian(group["energy_fractional_residual"]))
    pedestal_scores = group.groupby("pedestal_bin")["pid_score"].mean()
    pedestal_span = float(pedestal_scores.max() - pedestal_scores.min()) if len(pedestal_scores) else float("nan")
    sat_auc = safe_auc(y[sat], score[sat]) if sat.any() else float("nan")
    unsat_auc = safe_auc(y[unsat], score[unsat]) if unsat.any() else float("nan")
    return {
        "pid_auc": pid_auc,
        "pid_auc_residual": residual_auc,
        "pid_auc_nuisance_only": nuisance_auc,
        "pid_auc_residual_gain_vs_nuisance": residual_auc - nuisance_auc if np.isfinite(residual_auc) and np.isfinite(nuisance_auc) else float("nan"),
        "pid_ap": safe_ap(y, score),
        "pid_purity": purity,
        "pid_efficiency": efficiency,
        "timing_residual_coupling_abs": pearson_abs(group["pid_score"], group["time_residual_ns"]),
        "energy_residual_coupling_abs": pearson_abs(group["pid_score"], group["energy_fractional_residual"]),
        "energy_drift_abs": abs(energy_drift) if np.isfinite(energy_drift) else float("nan"),
        "energy_fractional_sigma68": sigma68(group["energy_fractional_residual"]),
        "pileup_miss_rate": pileup_miss_rate,
        "false_split_rate": false_split_rate,
        "saturation_pid_auc": sat_auc,
        "unsaturated_pid_auc": unsat_auc,
        "saturation_pid_auc_loss": max(0.0, unsat_auc - sat_auc) if np.isfinite(sat_auc) and np.isfinite(unsat_auc) else float("nan"),
        "pedestal_sensitivity_abs": abs(pedestal_span) if np.isfinite(pedestal_span) else float("nan"),
        "n_events": int(len(group)),
        "n_deuteron": int(positive.sum()),
    }


def bootstrap_metrics(group: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> Dict[str, float]:
    units = group[["source_run", "pid_name"]].drop_duplicates().to_records(index=False)
    samples: Dict[str, List[float]] = {}
    if len(units) == 0:
        return {}
    for _ in range(n_boot):
        take = rng.choice(np.arange(len(units)), size=len(units), replace=True)
        parts = []
        for idx in take:
            run, pid_name = units[idx]
            parts.append(group[(group["source_run"] == run) & (group["pid_name"] == pid_name)])
        boot = pd.concat(parts, ignore_index=True)
        vals = metrics(boot)
        for key, value in vals.items():
            if key.startswith("n_") or not isinstance(value, float) or not np.isfinite(value):
                continue
            samples.setdefault(key, []).append(value)
    out = {}
    for key, values in samples.items():
        out[f"{key}_ci_low"] = float(np.percentile(values, 2.5))
        out[f"{key}_ci_high"] = float(np.percentile(values, 97.5))
    return out


def build_tables(pred: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]))
    residual_frames = [residualized_scores(g.copy()) for _, g in pred.groupby("method", sort=True)]
    held = pd.concat(residual_frames, ignore_index=True)

    rows = []
    for method, group in held.groupby("method", sort=True):
        row = {"method": method, **metrics(group)}
        row.update(bootstrap_metrics(group, rng, int(config["bootstrap_replicates"])))
        rows.append(row)
    summary = pd.DataFrame(rows)
    w = config["winner_score_weights"]
    summary["winner_score"] = (
        w["pid_auc_residual"] * (1.0 - summary["pid_auc_residual"])
        + w["pid_purity"] * (1.0 - summary["pid_purity"])
        + w["pid_efficiency"] * (1.0 - summary["pid_efficiency"])
        + w["timing_residual_coupling_abs"] * summary["timing_residual_coupling_abs"]
        + w["energy_drift_abs"] * summary["energy_drift_abs"]
        + w["pileup_miss_rate"] * summary["pileup_miss_rate"]
        + w["saturation_pid_auc_loss"] * summary["saturation_pid_auc_loss"].fillna(0.0)
        + w["pedestal_sensitivity_abs"] * summary["pedestal_sensitivity_abs"]
    )
    summary = summary.sort_values("winner_score").reset_index(drop=True)

    by_run = []
    for (method, run), group in held.groupby(["method", "source_run"], sort=True):
        by_run.append({"method": method, "heldout_run": int(run), **metrics(group)})
    by_run_df = pd.DataFrame(by_run)

    strata_rows = []
    dimensions = ["pid_name", "energy_bin", "timing_bin", "pileup_bin", "saturation_bin", "pedestal_bin", "stave"]
    for dim in dimensions:
        for (method, value), group in held.groupby(["method", dim], sort=True):
            if len(group) >= 12:
                strata_rows.append({"stratum": dim, "value": str(value), "method": method, **metrics(group)})
    strata_df = pd.DataFrame(strata_rows)

    residual_audit = []
    for method, group in held.groupby("method", sort=True):
        residual_audit.append(
            {
                "method": method,
                "raw_pid_auc": safe_auc(group["pid_label"].to_numpy(int), group["pid_score"].to_numpy(float)),
                "nuisance_only_pid_auc": safe_auc(group["pid_label"].to_numpy(int), group["nuisance_pid_score"].to_numpy(float)),
                "residualized_pid_auc": safe_auc(group["pid_label"].to_numpy(int), group["pid_score_residualized"].to_numpy(float)),
                "pid_score_vs_energy_abs_r": pearson_abs(group["pid_score"], group["true_energy_mev"]),
                "pid_score_vs_timing_abs_r": pearson_abs(group["pid_score"], group["true_time_ns"]),
                "pid_score_vs_pedestal_abs_r": pearson_abs(group["pid_score"], group["truth_pedestal_adc"]),
                "pid_score_vs_shape_area_abs_r": pearson_abs(group["pid_score"], group["shape_area_over_amp"]),
                "pid_score_vs_depth_abs_r": pearson_abs(group["pid_score"], group["depth_index"]),
            }
        )
    audit_df = pd.DataFrame(residual_audit)
    return summary, by_run_df, strata_df, audit_df


def md_table(df: pd.DataFrame, cols: List[str], n: int | None = None) -> str:
    if df.empty:
        return "(empty)"
    view = df.loc[:, cols].copy()
    if n is not None:
        view = view.head(n)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.5g}" if np.isfinite(x) else "nan")
    return view.to_markdown(index=False)


def write_report(out: Path, config: dict, result: dict, source_result: dict) -> None:
    repro = pd.read_csv(out / "reproduction_match_table.csv")
    summary = pd.read_csv(out / "method_summary.csv")
    by_run = pd.read_csv(out / "run_species_bootstrap_metrics.csv")
    strata = pd.read_csv(out / "stress_strata_metrics.csv")
    audit = pd.read_csv(out / "residualization_audit.csv")
    winner = result["winner"]["name"]
    trad = REQUIRED_METHODS["strong_traditional"]
    lines = [
        "# S38c: PID-aware pulse-shape disentanglement under timing, pile-up, and saturation stress",
        "",
        "## Abstract",
        "",
        f"Ticket `{config['ticket_id']}` asks which pulse-shape features carry PID information after controlling for timing, energy, pedestal, pile-up, and saturation. The study reuses the keyed digitized GEANT4 native-join waveform panel as a fixed upstream benchmark, directly rescans raw ROOT for the selected-pulse anchor in this ticket directory, and adds nuisance-residualized PID, run/species bootstrap intervals, and stress-slice systematics. The winner written to `result.json` is **`{winner}`**.",
        "",
        "## Raw ROOT Reproduction",
        "",
        f"Raw B-stack files are read from `{config['raw_root_dir']}`. This S38c runner scans `h101/HRDv` directly, reshapes the branch to `(event, channel, 18 samples)`, subtracts the four-sample pedestal `b_c=median(x_c[0:4])`, and selects B2/B4/B6/B8 pulses satisfying `max_t[x_c(t)-b_c]>1000 ADC`. Per-run counts are written to `reproduction_counts_by_run.csv`; the source G4 benchmark reproduction table is retained only as a cross-check.",
        "",
        md_table(repro, ["quantity", "report_value", "reproduced", "delta", "pass"]),
        "",
        "## Data, Split, And Labels",
        "",
        f"The event-level benchmark has `{source_result['keyed_digitizer_output']['joined_events']}` keyed digitized rows joined by native DAQ/G4 keys. Training runs are `{config['train_runs']}` and held-out runs are `{config['heldout_runs']}`; the split is disjoint by run. PID labels are GEANT4 Sci-bar dominant proton/deuteron labels, energy is Sci-bar total deposited energy, timing is energy-weighted Sci-bar hit time, pile-up is the controlled-overlap truth flag, saturation is the digitized high-amplitude truth flag, and pedestal is the retained raw pedestal term.",
        "",
        "## Methods",
        "",
        f"The traditional comparator is `{trad}`, a dE/E-like likelihood/template pulse-shape method. The ML/NN panel covers ridge, gradient-boosted trees, MLP, 1D-CNN, the small `joint_sequence_transformer`, and the new `template_residual_boosted_stack_new` architecture. All model scores are inherited from the fixed upstream run-heldout panel so S38c only changes the scientific endpoint, not the fitted models.",
        "",
        "For each method `m`, the nuisance-only PID model is fitted on train runs as `q(z)=P(Y=1|z)` using `z=(E,t,pedestal,pileup,saturation,dE/dx,depth,shape area)`. The observed method score `s_m` is also regressed on `z`; the residualized score is `r_m=s_m-E[s_m|z]`. The main S38c PID endpoint is `AUC(Y,r_m)` on held-out runs. This asks whether the waveform score contains PID information beyond the controlled nuisance coordinates.",
        "",
        "The winner minimizes",
        "",
        "`0.36(1-AUC_resid)+0.16(1-purity)+0.16(1-efficiency)+0.10|rho(score,dt)|+0.08|median(dE/E)|+0.06 miss_pileup+0.05 max(0,AUC_unsat-AUC_sat)+0.03 pedestal_span`.",
        "",
        "Confidence intervals are 95% percentile intervals from bootstrap resampling of held-out `(source_run, pid_name)` blocks.",
        "",
        "## Main Results",
        "",
        md_table(summary, ["method", "winner_score", "pid_auc", "pid_auc_residual", "pid_auc_residual_ci_low", "pid_auc_residual_ci_high", "pid_purity", "pid_efficiency", "timing_residual_coupling_abs", "energy_drift_abs", "pileup_miss_rate", "saturation_pid_auc_loss", "pedestal_sensitivity_abs"]),
        "",
        "## Residualization Audit",
        "",
        md_table(audit, ["method", "raw_pid_auc", "nuisance_only_pid_auc", "residualized_pid_auc", "pid_score_vs_energy_abs_r", "pid_score_vs_timing_abs_r", "pid_score_vs_pedestal_abs_r", "pid_score_vs_shape_area_abs_r", "pid_score_vs_depth_abs_r"]),
        "",
        "## Run-Held-Out Stability",
        "",
        md_table(by_run, ["method", "heldout_run", "pid_auc_residual", "pid_purity", "pid_efficiency", "timing_residual_coupling_abs", "energy_drift_abs", "pileup_miss_rate", "saturation_pid_auc_loss"], n=80),
        "",
        "## Stress Strata",
        "",
        md_table(strata, ["stratum", "value", "method", "pid_auc_residual", "pid_purity", "pid_efficiency", "timing_residual_coupling_abs", "energy_fractional_sigma68", "pileup_miss_rate", "saturation_pid_auc_loss", "n_events"], n=120),
        "",
        "## Systematics And Caveats",
        "",
        "- The upstream benchmark is a keyed hybrid digitization: GEANT4 truth labels are joined to raw-template/residual waveforms, not a second independent detector run.",
        "- Residualization removes information predictable from the listed nuisance coordinates under a train-fitted quadratic logistic/linear control model; unmeasured correlations can remain.",
        "- The run/species bootstrap covers observed held-out source-run and PID-label variation, but not GEANT4 physics-list uncertainty or unseen beam tunes.",
        "- Saturation robustness is measured by a digitized high-amplitude proxy; it should be read as an architecture stress test, not a hardware saturation calibration.",
        "- Because the source model panel is fixed, this ticket evaluates PID-aware disentanglement of already-trained methods rather than retuning architectures for the residualized endpoint.",
        "",
        "## Verdict",
        "",
        f"`{winner}` is the S38c winner. The residualization table shows whether the method keeps PID separation after timing, energy, pedestal, pile-up, saturation, dE/dx, depth, and gross shape controls; the stress-strata table shows where that conclusion is weakest.",
        "",
        "## Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/s38c_1784069109_995_08951735_pid_aware_pulse_shape_disentanglement.py --config configs/s38c_1784069109_995_08951735_pid_aware_pulse_shape_disentanglement.json",
        "```",
    ]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/s38c_1784069109_995_08951735_pid_aware_pulse_shape_disentanglement.json")
    args = parser.parse_args()
    t0 = time.time()
    config = load_json(args.config)
    out = ROOT / config["output_dir"]
    source = ROOT / config["source_benchmark_dir"]
    out.mkdir(parents=True, exist_ok=True)

    source_result = load_json(source / "result.json")
    source_repro = pd.read_csv(source / "reproduction_match_table.csv")
    if not bool(source_repro["pass"].iloc[0]):
        raise RuntimeError("source raw ROOT reproduction did not pass")
    counts = scan_raw_selected_counts(config)
    counts.to_csv(out / "reproduction_counts_by_run.csv", index=False)
    selected = int(counts["selected_pulses"].sum())
    expected = int(config["expected_total_selected_pulses"])
    repro = pd.DataFrame(
        [
            {
                "quantity": "total selected B-stave pulses",
                "report_value": expected,
                "reproduced": selected,
                "delta": selected - expected,
                "pass": selected == expected,
                "s38c_direct_raw_root_scan": True,
                "source_crosscheck": str((source / "reproduction_match_table.csv").relative_to(ROOT)),
            }
        ]
    )
    if selected != expected:
        raise RuntimeError(f"S38c direct raw ROOT reproduction failed: {selected} != {expected}")
    repro.to_csv(out / "reproduction_match_table.csv", index=False)

    pred = selected_prediction_frame(source)
    pred.to_csv(out / "source_event_predictions_selected_methods.csv.gz", index=False)
    summary, by_run, strata, audit = build_tables(pred, config)
    summary.to_csv(out / "method_summary.csv", index=False)
    by_run.to_csv(out / "run_species_bootstrap_metrics.csv", index=False)
    strata.to_csv(out / "stress_strata_metrics.csv", index=False)
    audit.to_csv(out / "residualization_audit.csv", index=False)

    winner = summary.iloc[0].to_dict()
    trad = summary[summary["method"].eq(REQUIRED_METHODS["strong_traditional"])].iloc[0].to_dict()
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "project": "testbeam",
        "worker": config["worker"],
        "title": config["title"],
        "status": "complete",
        "claim_command": "tn-ticket claim testbeam-laptop-1 --project testbeam",
        "raw_root_reproduction": {
            "passed": bool(repro["pass"].iloc[0]),
            "raw_root_dir": config["raw_root_dir"],
            "expected_selected_pulses": int(config["expected_total_selected_pulses"]),
            "reproduced_selected_pulses": int(repro["reproduced"].iloc[0]),
            "delta": int(repro["delta"].iloc[0]),
            "direct_raw_root_scan": True,
            "counts_by_run": "reproduction_counts_by_run.csv",
            "source_crosscheck": str((source / "reproduction_match_table.csv").relative_to(ROOT)),
        },
        "source_benchmark": {
            "report_dir": config["source_benchmark_dir"],
            "source_ticket_id": source_result["ticket_id"],
            "joined_events": int(source_result["keyed_digitizer_output"]["joined_events"]),
            "split": source_result["evaluation_design"]["split"],
        },
        "split": {
            "train_runs": [int(r) for r in config["train_runs"]],
            "heldout_runs": [int(r) for r in config["heldout_runs"]],
            "bootstrap_unit": "heldout source_run x pid_name",
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
        },
        "required_method_coverage": REQUIRED_METHODS,
        "winner": {
            "name": str(winner["method"]),
            "criterion": "minimum S38c residualized PID/stress composite score",
            "winner_score": float(winner["winner_score"]),
            "pid_auc": float(winner["pid_auc"]),
            "pid_auc_residual": float(winner["pid_auc_residual"]),
            "pid_auc_residual_ci95": [
                float(winner["pid_auc_residual_ci_low"]),
                float(winner["pid_auc_residual_ci_high"]),
            ],
            "pid_purity": float(winner["pid_purity"]),
            "pid_efficiency": float(winner["pid_efficiency"]),
            "timing_residual_coupling_abs": float(winner["timing_residual_coupling_abs"]),
            "energy_drift_abs": float(winner["energy_drift_abs"]),
            "pileup_miss_rate": float(winner["pileup_miss_rate"]),
            "saturation_pid_auc_loss": float(winner["saturation_pid_auc_loss"]),
            "pedestal_sensitivity_abs": float(winner["pedestal_sensitivity_abs"]),
        },
        "traditional_comparator": json_clean(trad),
        "artifacts": {
            "report": "REPORT.md",
            "result": "result.json",
            "manifest": "manifest.json",
            "method_summary": "method_summary.csv",
            "run_species_bootstrap_metrics": "run_species_bootstrap_metrics.csv",
            "stress_strata_metrics": "stress_strata_metrics.csv",
            "residualization_audit": "residualization_audit.csv",
            "source_event_predictions": "source_event_predictions_selected_methods.csv.gz",
            "reproduction_match_table": "reproduction_match_table.csv",
            "reproduction_counts_by_run": "reproduction_counts_by_run.csv",
        },
        "novel_tickets_appended": [],
        "runtime_sec": time.time() - t0,
        "git_commit": git_commit(),
        "python": platform.python_version(),
    }
    (out / "result.json").write_text(json.dumps(json_clean(result), indent=2) + "\n", encoding="utf-8")
    write_report(out, config, result, source_result)

    manifest = {
        "ticket_id": config["ticket_id"],
        "generated_at_unix": time.time(),
        "command": " ".join(str(x) for x in ["/home/billy/anaconda3/bin/python", *map(str, __import__("sys").argv)]),
        "artifacts": [],
    }
    declared_artifacts = {name for name in result["artifacts"].values()}
    for path in sorted(out.iterdir()):
        if path.name not in declared_artifacts:
            continue
        if path.is_file() and path.name != "manifest.json":
            manifest["artifacts"].append(
                {"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)}
            )
    (out / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "winner": result["winner"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
