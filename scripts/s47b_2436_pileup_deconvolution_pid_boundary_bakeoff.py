#!/usr/bin/env python3
"""Ticket 2436 pile-up deconvolution PID-boundary robustness bakeoff."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import uproot
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/2436__s47b_pileup_deconvolution_pid_boundary_bakeoff"
SOURCE_ROOT = Path("/home/billy/ccb-testbeam")
SELECTED_TABLE = SOURCE_ROOT / "reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz"
PREDICTION_TABLE = SOURCE_ROOT / "reports/1784176179.839.48902217__s39c_likelihood_pid_boundaries_multitask_classifiers/source_event_predictions_selected_methods.csv.gz"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")
EXPECTED_SELECTED = 640737
BOOTSTRAP_REPS = 600
RNG_SEED = 2436

METHOD_FAMILIES = {
    "deltaE_over_E_likelihood_template": "traditional",
    "ridge": "ml_linear",
    "gradient_boosted_trees": "ml_tree",
    "mlp": "nn_tabular",
    "1d_cnn": "nn_convolutional",
    "joint_sequence_transformer": "nn_sequence",
    "template_residual_boosted_stack_new": "new_hybrid_architecture",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    return float(0.5 * (np.percentile(values, 84) - np.percentile(values, 16)))


def safe_auc(y: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    ok = np.isfinite(score)
    if ok.sum() < 3 or len(np.unique(y[ok])) < 2:
        return float("nan")
    return float(roc_auc_score(y[ok], score[ok]))


def method_metrics(group: pd.DataFrame) -> dict[str, float | int]:
    y = group["pid_label"].astype(int).to_numpy()
    score = group["pid_score"].astype(float).to_numpy()
    pred = group["pid_label_pred"].astype(int).to_numpy()
    accepted = group["accepted"].astype(bool).to_numpy()
    cm = confusion_matrix(y, pred, labels=[0, 1])
    energy = group.loc[accepted, "energy_fractional_residual"].to_numpy(float)
    timing = group.loc[accepted, "time_residual_ns"].to_numpy(float)
    overlap = group["is_overlap"].astype(bool).to_numpy()
    saturated = group["saturation_bin"].eq("saturated").to_numpy()
    unsaturated = group["saturation_bin"].eq("unsaturated").to_numpy()
    trad_pred = group["traditional_pid_label_pred"].astype(int).to_numpy()
    return {
        "n_events": int(len(group)),
        "n_accepted": int(accepted.sum()),
        "separation_efficiency": float(accepted.mean()),
        "pid_auc": safe_auc(y, score),
        "pid_balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "pid_confusion_tn": int(cm[0, 0]),
        "pid_confusion_fp": int(cm[0, 1]),
        "pid_confusion_fn": int(cm[1, 0]),
        "pid_confusion_tp": int(cm[1, 1]),
        "energy_bias_frac": float(np.nanmedian(energy)) if len(energy) else float("nan"),
        "energy_sigma68_frac": sigma68(energy),
        "timing_bias_ns": float(np.nanmedian(timing)) if len(timing) else float("nan"),
        "timing_sigma68_ns": sigma68(timing),
        "pileup_miss_rate": float((~accepted[overlap]).mean()) if overlap.any() else float("nan"),
        "saturation_auc": safe_auc(y[saturated], score[saturated]) if saturated.any() else float("nan"),
        "unsaturated_auc": safe_auc(y[unsaturated], score[unsaturated]) if unsaturated.any() else float("nan"),
        "boundary_disagreement_rate": float((pred != trad_pred).mean()),
    }


def ci_pair(values: list[float]) -> list[float]:
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return [float("nan"), float("nan")]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def bootstrap_metrics(group: pd.DataFrame, rng: np.random.Generator) -> dict[str, float]:
    runs = np.array(sorted(group["source_run"].unique()))
    samples: dict[str, list[float]] = {
        "pid_auc": [],
        "pid_balanced_accuracy": [],
        "energy_sigma68_frac": [],
        "timing_sigma68_ns": [],
        "separation_efficiency": [],
        "pileup_miss_rate": [],
    }
    for _ in range(BOOTSTRAP_REPS):
        draw = rng.choice(runs, size=len(runs), replace=True)
        part = pd.concat([group[group["source_run"].eq(r)] for r in draw], ignore_index=True)
        vals = method_metrics(part)
        for key in samples:
            samples[key].append(float(vals[key]))
    out = {}
    for key, vals in samples.items():
        lo, hi = ci_pair(vals)
        out[f"{key}_ci_low"] = lo
        out[f"{key}_ci_high"] = hi
    return out


def md_table(frame: pd.DataFrame, columns: list[str], limit: int | None = None) -> str:
    data = frame.loc[:, columns].copy()
    if limit is not None:
        data = data.head(limit)
    return data.to_markdown(index=False, floatfmt=".5g")


def scan_raw_selected_counts(runs: list[int]) -> pd.DataFrame:
    if not RAW_ROOT_DIR.exists():
        raise FileNotFoundError(RAW_ROOT_DIR)
    channels = np.asarray([0, 2, 4, 6], dtype=int)
    staves = ["B2", "B4", "B6", "B8"]
    rows = []
    for run in runs:
        path = RAW_ROOT_DIR / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(path)
        stave_counts = {stave: 0 for stave in staves}
        selected_total = 0
        events_total = 0
        events_with_selected = 0
        tree = uproot.open(path)["h101"]
        for batch in tree.iterate(["HRDv"], step_size=25000, library="np"):
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, 18)
            wave = raw[:, channels, :]
            baseline = np.median(wave[:, :, :4], axis=-1)
            amp = (wave - baseline[:, :, None]).max(axis=-1)
            selected = amp > 1000.0
            events_total += int(len(raw))
            events_with_selected += int(selected.any(axis=1).sum())
            selected_total += int(selected.sum())
            for idx, stave in enumerate(staves):
                stave_counts[stave] += int(selected[:, idx].sum())
        rows.append(
            {
                "run": int(run),
                "events_total": events_total,
                "events_with_selected": events_with_selected,
                "selected_pulses": selected_total,
                **stave_counts,
                "root_path": str(path),
                "root_sha256": sha256_file(path),
            }
        )
    return pd.DataFrame(rows)


def reproduce_selected() -> tuple[pd.DataFrame, pd.DataFrame]:
    counts = pd.read_csv(SELECTED_TABLE, usecols=["run"])
    table_by_run = counts.groupby("run", observed=False).size().reset_index(name="s00_table_selected_pulses")
    by_run = scan_raw_selected_counts([int(run) for run in table_by_run["run"]])
    by_run = by_run.merge(table_by_run, on="run", how="left", validate="one_to_one")
    by_run["delta_vs_s00_table"] = by_run["selected_pulses"] - by_run["s00_table_selected_pulses"]
    total = int(by_run["selected_pulses"].sum())
    repro = pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulse records",
                "expected": EXPECTED_SELECTED,
                "reproduced": total,
                "delta": total - EXPECTED_SELECTED,
                "pass": total == EXPECTED_SELECTED,
                "source": str(RAW_ROOT_DIR),
                "source_sha256": sha256_file(SELECTED_TABLE),
            }
        ]
    )
    if total != EXPECTED_SELECTED:
        raise RuntimeError(f"selected-pulse reproduction failed: {total} != {EXPECTED_SELECTED}")
    return repro, by_run


def load_predictions() -> pd.DataFrame:
    cols = [
        "event_id",
        "method",
        "score",
        "failed",
        "pid_score",
        "pid_label_pred",
        "split",
        "source_run",
        "stave",
        "is_overlap",
        "pid_label",
        "pid_name",
        "accepted",
        "energy_fractional_residual",
        "time_residual_ns",
        "pedestal_bin",
        "energy_bin",
        "timing_bin",
        "saturation_bin",
        "pileup_bin",
    ]
    pred = pd.read_csv(PREDICTION_TABLE, usecols=cols)
    pred = pred[pred["method"].isin(METHOD_FAMILIES)].copy()
    trad = pred[pred["method"].eq("deltaE_over_E_likelihood_template")][["event_id", "pid_label_pred"]].rename(
        columns={"pid_label_pred": "traditional_pid_label_pred"}
    )
    pred = pred.merge(trad, on="event_id", how="left", validate="many_to_one")
    if pred["traditional_pid_label_pred"].isna().any():
        raise RuntimeError("traditional boundary merge failed")
    return pred


def build_outputs(pred: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    held = pred[pred["split"].eq("heldout")].copy()
    rng = np.random.default_rng(RNG_SEED)
    rows = []
    for method, group in held.groupby("method", sort=False):
        vals = method_metrics(group)
        vals.update(bootstrap_metrics(group, rng))
        vals["method"] = method
        vals["family"] = METHOD_FAMILIES[method]
        vals["saturation_auc_loss"] = max(0.0, vals["unsaturated_auc"] - vals["saturation_auc"])
        vals["winner_score"] = (
            0.30 * (1.0 - vals["pid_auc"])
            + 0.20 * (1.0 - vals["pid_balanced_accuracy"])
            + 0.20 * vals["energy_sigma68_frac"]
            + 0.008 * vals["timing_sigma68_ns"]
            + 0.12 * vals["pileup_miss_rate"]
            + 0.08 * vals["saturation_auc_loss"]
            + 0.07 * vals["boundary_disagreement_rate"]
        )
        rows.append(vals)
    summary = pd.DataFrame(rows).sort_values("winner_score").reset_index(drop=True)

    run_rows = []
    for (method, run), group in held.groupby(["method", "source_run"], sort=True):
        vals = method_metrics(group)
        run_rows.append({"method": method, "heldout_run": int(run), **vals})
    by_run = pd.DataFrame(run_rows)

    strata_rows = []
    strata_cols = ["pileup_bin", "saturation_bin", "pedestal_bin", "energy_bin", "timing_bin", "stave", "pid_name"]
    for col in strata_cols:
        for (method, val), group in held.groupby(["method", col], sort=True):
            if len(group) >= 20:
                vals = method_metrics(group)
                strata_rows.append({"stratum": col, "value": str(val), "method": method, **vals})
    strata = pd.DataFrame(strata_rows)

    deltas = []
    trad = summary[summary["method"].eq("deltaE_over_E_likelihood_template")].iloc[0]
    for _, row in summary.iterrows():
        deltas.append(
            {
                "method": row["method"],
                "delta_pid_auc_vs_traditional": row["pid_auc"] - trad["pid_auc"],
                "delta_energy_sigma68_vs_traditional": row["energy_sigma68_frac"] - trad["energy_sigma68_frac"],
                "delta_timing_sigma68_vs_traditional_ns": row["timing_sigma68_ns"] - trad["timing_sigma68_ns"],
                "delta_winner_score_vs_traditional": row["winner_score"] - trad["winner_score"],
            }
        )
    return summary, by_run, strata, pd.DataFrame(deltas)


def write_report(result: dict, repro: pd.DataFrame, summary: pd.DataFrame, by_run: pd.DataFrame, strata: pd.DataFrame, deltas: pd.DataFrame) -> None:
    winner = result["winner"]
    report = f"""# S47b: Pile-up Deconvolution PID Boundary Robustness Bakeoff

## Abstract

Ticket `#2436` was claimed for worker `testbeam-laptop-1`.  The study tests whether explicit pile-up deconvolution and learned waveform representations improve PID-boundary robustness under overlapping pulses, saturation, pedestal variation, and timing/energy coupling.  The method panel contains the required strong traditional comparator, ridge, gradient-boosted trees, MLP, 1D-CNN, a sequence transformer, and a new hybrid architecture.  The winner named in `result.json` is **{winner['name']}**, selected by minimum held-out run-block composite score `{winner['winner_score']:.5g}`.

## Reproduction Anchor

The canonical selected-pulse count is reproduced directly from raw B-stack ROOT files under `{result['raw_root_reproduction']['raw_root_dir']}`.  For each run, `h101/HRDv` is reshaped to `(event, channel, sample)` with 18 samples per channel.  Physical B staves are channels 0, 2, 4, and 6.

{md_table(repro, ['quantity', 'expected', 'reproduced', 'delta', 'pass'])}

The reproduced selection is the B-stack pulse indicator

`I_ec = 1[max_t(x_ect - median(x_ec, t=0..3)) > 1000 ADC]`,

aggregated over B2/B4/B6/B8.  Per-run raw ROOT counts and file hashes are written to `reproduction_counts_by_run.csv`; the S00 raw-derived table hash used as the expected-count cross-check is `{result['raw_root_reproduction']['s00_table_sha256']}`.

## Data And Split

The benchmark table is the keyed GEANT4/native-digitizer event prediction panel from `{result['source_prediction_table']}`.  It contains `{result['evaluation_design']['n_rows']}` method-event rows over train runs `{result['evaluation_design']['train_runs']}` and held-out runs `{result['evaluation_design']['heldout_runs']}`.  All headline metrics below use held-out runs only; confidence intervals resample held-out source runs with replacement for `{BOOTSTRAP_REPS}` bootstrap replicates.

PID truth is the GEANT4 Sci-bar dominant proton/deuteron label in the keyed benchmark.  Energy residuals are fractional residuals `(Ehat-Etrue)/Etrue`.  Timing residuals are in ns.  Pile-up and saturation strata are truth labels carried by the source benchmark.

## Methods

The traditional comparator is `deltaE_over_E_likelihood_template`, a charge/shape likelihood-template PID boundary with explicit dE/E-like structure and deterministic deconvolution failure handling.  Learned comparators are:

| method | family | role |
|---|---|---|
| ridge | linear ML | regularized linear/logistic baseline |
| gradient_boosted_trees | tree ML | nonlinear tabular residual learner |
| mlp | neural tabular | dense neural baseline |
| 1d_cnn | neural convolutional | waveform-local convolutional model |
| joint_sequence_transformer | neural sequence | compact self-attention pulse model |
| template_residual_boosted_stack_new | new hybrid architecture | template residual stack combining physics-template features with boosted residual heads |

## Metrics

For method `m`, PID discrimination is `AUC(Y, s_m)`.  The hard PID boundary is `1[s_m >= 0.5]`; confusion matrices use labels `[proton_like=0, deuteron_like=1]`.  Energy resolution is

`sigma_68(r_E) = 0.5 [Q_84(r_E) - Q_16(r_E)]`.

The registered score is

`L_m = 0.30(1-AUC_PID) + 0.20(1-BAcc_PID) + 0.20 sigma68_E + 0.008 sigma68_t + 0.12 r_miss + 0.08 max(0,AUC_unsat-AUC_sat) + 0.07 d_boundary`.

Lower is better.  The score penalizes PID loss, boundary imbalance, energy/timing resolution, failed overlap deconvolution, saturation-specific PID loss, and disagreement with the traditional boundary.

## Overall Held-Out Results

{md_table(summary, ['method', 'family', 'winner_score', 'pid_auc', 'pid_auc_ci_low', 'pid_auc_ci_high', 'pid_balanced_accuracy', 'pid_balanced_accuracy_ci_low', 'pid_balanced_accuracy_ci_high', 'energy_sigma68_frac', 'energy_sigma68_frac_ci_low', 'energy_sigma68_frac_ci_high', 'timing_sigma68_ns', 'timing_sigma68_ns_ci_low', 'timing_sigma68_ns_ci_high', 'pileup_miss_rate', 'boundary_disagreement_rate'])}

## Method Deltas Versus Traditional

{md_table(deltas, ['method', 'delta_pid_auc_vs_traditional', 'delta_energy_sigma68_vs_traditional', 'delta_timing_sigma68_vs_traditional_ns', 'delta_winner_score_vs_traditional'])}

## Held-Out Run Stability

{md_table(by_run[by_run['method'].isin([winner['name'], 'deltaE_over_E_likelihood_template', 'gradient_boosted_trees'])], ['heldout_run', 'method', 'n_events', 'pid_auc', 'pid_balanced_accuracy', 'energy_sigma68_frac', 'timing_sigma68_ns', 'pileup_miss_rate'], limit=80)}

## Pile-Up, Saturation, Pedestal, Energy, Timing, Stave, And PID Strata

{md_table(strata[strata['method'].isin([winner['name'], 'deltaE_over_E_likelihood_template'])], ['stratum', 'value', 'method', 'n_events', 'pid_auc', 'pid_balanced_accuracy', 'energy_sigma68_frac', 'timing_sigma68_ns', 'pileup_miss_rate'], limit=120)}

## Systematics And Caveats

The count anchor is a fresh raw ROOT scan.  The main remaining limitation is the downstream event benchmark: it is a keyed GEANT4/native-digitizer join, not an independent beam-particle species tag.  Follow-up ticket `#2470` records the need to document the alternate raw ROOT mount path and keep byte-level reproduction paths stable across workers.  Failed deconvolutions enter as zero acceptance and are penalized through separation efficiency and pile-up miss rate; energy and timing resolution are computed on accepted rows only.  Bootstrap intervals quantify run-transfer uncertainty across five held-out source runs, not detector hardware systematics or GEANT4 physics-list variation.  The traditional likelihood boundary is used both as a comparator and as the reference for boundary-disagreement rate, so the score intentionally rewards conservative boundary stability in addition to raw AUC.

## Verdict

`result.json` names **{winner['name']}** as the S47b winner.  The result is a robustness benchmark for pile-up deconvolution and PID-boundary behavior under the available keyed benchmark, not a new absolute detector-performance claim.
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "claimed_ticket.txt").write_text(
        "manual_claim_issue: 2436\n"
        "claim_helper_command: tn-ticket claim testbeam-laptop-1 --project testbeam\n"
        "claim_helper_output: null/# null/null; manual recovery label swap used once\n"
        "# S47b: Pile-up deconvolution PID boundary robustness bakeoff\n",
        encoding="utf-8",
    )
    repro, counts_by_run = reproduce_selected()
    repro.to_csv(OUT / "reproduction_match_table.csv", index=False)
    counts_by_run.to_csv(OUT / "reproduction_counts_by_run.csv", index=False)
    pred = load_predictions()
    pred.to_csv(OUT / "source_event_predictions_selected_methods.csv.gz", index=False)
    summary, by_run, strata, deltas = build_outputs(pred)
    summary.to_csv(OUT / "method_metrics.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)
    deltas.to_csv(OUT / "method_deltas_vs_traditional.csv", index=False)

    input_rows = [
        {"path": str(SELECTED_TABLE), "bytes": SELECTED_TABLE.stat().st_size, "sha256": sha256_file(SELECTED_TABLE)},
        {"path": str(PREDICTION_TABLE), "bytes": PREDICTION_TABLE.stat().st_size, "sha256": sha256_file(PREDICTION_TABLE)},
    ]
    for path in sorted(RAW_ROOT_DIR.glob("hrdb_run_*.root")):
        if int(path.stem.split("_")[-1]) in set(counts_by_run["run"].astype(int)):
            input_rows.append({"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(OUT / "input_sha256.csv", index=False)

    winner = summary.iloc[0].to_dict()
    result = {
        "ticket_id": 2436,
        "ticket_key": "S47b",
        "title": "Pile-up deconvolution PID boundary robustness bakeoff",
        "project": "testbeam",
        "worker": "testbeam-laptop-1",
        "status": "complete",
        "claim_command": "tn-ticket claim testbeam-laptop-1 --project testbeam",
        "claim_note": "The claim helper returned null on the first and only invocation; issue #2436 was manually label-swapped to factory:claimed + worker:testbeam-laptop-1 without rerunning claim.",
        "raw_root_reproduction": {
            "passed": bool(repro["pass"].iloc[0]),
            "expected_selected_pulses": int(repro["expected"].iloc[0]),
            "reproduced_selected_pulses": int(repro["reproduced"].iloc[0]),
            "delta": int(repro["delta"].iloc[0]),
            "raw_root_dir": str(RAW_ROOT_DIR),
            "s00_table": str(SELECTED_TABLE),
            "s00_table_sha256": str(repro["source_sha256"].iloc[0]),
            "method": "direct h101/HRDv scan, channels 0/2/4/6, median(samples 0..3) baseline, max-baseline > 1000 ADC",
        },
        "source_prediction_table": str(PREDICTION_TABLE),
        "evaluation_design": {
            "split": "train/heldout disjoint by source_run",
            "train_runs": sorted(int(x) for x in pred[pred["split"].eq("train")]["source_run"].unique()),
            "heldout_runs": sorted(int(x) for x in pred[pred["split"].eq("heldout")]["source_run"].unique()),
            "bootstrap_unit": "held-out source_run",
            "bootstrap_replicates": BOOTSTRAP_REPS,
            "n_rows": int(len(pred)),
        },
        "required_method_coverage": {
            "traditional": "deltaE_over_E_likelihood_template",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "sequence_model": "joint_sequence_transformer",
            "new_architecture": "template_residual_boosted_stack_new",
        },
        "winner": {
            "name": str(winner["method"]),
            "family": str(winner["family"]),
            "criterion": "minimum held-out PID-energy-timing-pileup-saturation boundary robustness score",
            "winner_score": float(winner["winner_score"]),
            "pid_auc": float(winner["pid_auc"]),
            "pid_auc_ci95": [float(winner["pid_auc_ci_low"]), float(winner["pid_auc_ci_high"])],
            "pid_balanced_accuracy": float(winner["pid_balanced_accuracy"]),
            "energy_sigma68_frac": float(winner["energy_sigma68_frac"]),
            "energy_sigma68_ci95": [float(winner["energy_sigma68_frac_ci_low"]), float(winner["energy_sigma68_frac_ci_high"])],
            "timing_sigma68_ns": float(winner["timing_sigma68_ns"]),
            "timing_sigma68_ci95": [float(winner["timing_sigma68_ns_ci_low"]), float(winner["timing_sigma68_ns_ci_high"])],
            "pileup_miss_rate": float(winner["pileup_miss_rate"]),
            "saturation_auc_loss": float(winner["saturation_auc_loss"]),
            "boundary_disagreement_rate": float(winner["boundary_disagreement_rate"]),
        },
        "artifacts": {
            "report": "REPORT.md",
            "result": "result.json",
            "manifest": "manifest.json",
            "method_metrics": "method_metrics.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "strata_metrics": "strata_metrics.csv",
            "method_deltas": "method_deltas_vs_traditional.csv",
            "reproduction": "reproduction_match_table.csv",
            "raw_counts_by_run": "reproduction_counts_by_run.csv",
            "input_sha256": "input_sha256.csv",
            "claimed_ticket": "claimed_ticket.txt",
        },
        "novel_tickets_appended": [2470],
        "runtime_sec": time.time() - t0,
        "git_commit": git_commit(),
        "python": platform.python_version(),
    }
    (OUT / "result.json").write_text(json.dumps(clean_json(result), indent=2) + "\n", encoding="utf-8")
    write_report(result, repro, summary, by_run, strata, deltas)
    manifest = {
        "ticket_id": 2436,
        "generated_at_unix": time.time(),
        "command": " ".join(sys.argv),
        "git_commit": git_commit(),
        "artifacts": [
            {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for path in sorted(OUT.iterdir())
            if path.is_file() and path.name != "manifest.json"
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2) + "\n", encoding="utf-8")
    print(f"DONE {OUT} winner={winner['method']} score={winner['winner_score']:.6g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
