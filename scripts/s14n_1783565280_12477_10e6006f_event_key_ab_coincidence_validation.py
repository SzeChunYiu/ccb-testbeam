#!/usr/bin/env python3
"""S14n: event-key A/B coincidence validation for saturation transfer."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import time
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
import uproot
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


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


def configured_runs(config: dict) -> list[int]:
    runs: list[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def heldout_runs(config: dict) -> list[int]:
    runs: list[int] = []
    for group in config["heldout_groups"]:
        runs.extend(int(run) for run in config["run_groups"][group])
    return sorted(set(runs))


def current_lookup(config: dict) -> dict[int, str]:
    out: dict[int, str] = {}
    for label, runs in config["current_strata"].items():
        for run in runs:
            out[int(run)] = label
    return out


def raw_path(config: dict, stack: str, run: int) -> Path:
    return ROOT / config["raw_root_dir"] / f"hrd{stack}_run_{run:04d}.root"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def iter_root(path: Path, branches: Sequence[str]):
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(list(branches), step_size=25000, library="np")


def corrected_waveforms(batch: dict, channels: Sequence[int], config: dict) -> np.ndarray:
    nsamp = int(config["samples_per_channel"])
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)[:, channels, :]
    baseline = np.median(raw[:, :, baseline_idx], axis=-1)
    return raw - baseline[:, :, None]


def stack_events(config: dict, stack: str, run: int, channels: Sequence[int]) -> pd.DataFrame:
    rows = []
    cut = float(config["amplitude_cut_adc"])
    for batch in iter_root(raw_path(config, stack, run), ["EVENTNO", "EVT", "HRDv"]):
        corr = corrected_waveforms(batch, channels, config)
        amp = corr.max(axis=-1)
        positive_area = np.clip(corr, 0.0, None).sum(axis=-1)
        selected = amp > cut
        rows.append(
            pd.DataFrame(
                {
                    "eventno": np.asarray(batch["EVENTNO"]).astype(np.int64),
                    "evt": np.asarray(batch["EVT"]).astype(np.int64),
                    f"{stack}_charge_sum": positive_area.sum(axis=1),
                    f"{stack}_selected_charge": (positive_area * selected).sum(axis=1),
                    f"{stack}_amp_max": amp.max(axis=1),
                    f"{stack}_selected_count": selected.sum(axis=1).astype(np.int16),
                    f"{stack}_has_selected": selected.any(axis=1),
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def choose_event_key(config: dict, validation: pd.DataFrame) -> str:
    heldout = validation[validation["run"].isin(heldout_runs(config))].copy()
    rows = []
    for key, sub in heldout.groupby("key", sort=False):
        rows.append(
            {
                "key": str(key),
                "max_a_duplicates": int(sub["a_duplicate_keys"].max()),
                "max_b_duplicates": int(sub["b_duplicate_keys"].max()),
                "min_selected_match": float(sub["selected_b_match_fraction"].min()),
                "median_selected_match": float(sub["selected_b_match_fraction"].median()),
                "max_selected_match": float(sub["selected_b_match_fraction"].max()),
            }
        )
    candidates = pd.DataFrame(rows)
    candidates = candidates[
        candidates["max_a_duplicates"].eq(0)
        & candidates["max_b_duplicates"].eq(0)
        & candidates["max_selected_match"].le(1.0 + 1e-12)
    ].copy()
    if candidates.empty:
        raise RuntimeError("no duplicate-free event key candidate survives held-out validation")
    candidates = candidates.sort_values(
        ["min_selected_match", "median_selected_match", "key"],
        ascending=[False, False, True],
    )
    return str(candidates.iloc[0]["key"])


def event_key_validation(config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    current = current_lookup(config)
    b_channels = [int(v) for v in config["staves"].values()]
    a_channels = [int(v) for v in config["astack_staves"].values()]
    validation_rows = []
    event_tables = {}
    b_count_rows = []
    for run in configured_runs(config):
        a = stack_events(config, "a", run, a_channels)
        b = stack_events(config, "b", run, b_channels)
        selected_b = b[b["b_has_selected"]].copy()
        event_tables[run] = (a, selected_b)
        b_count_rows.append(
            {
                "run": run,
                "events_total": int(len(b)),
                "events_with_selected": int(len(selected_b)),
                "selected_pulses": int(b["b_selected_count"].sum()),
            }
        )
        for key in config["event_key_candidates"]:
            col = str(key).lower()
            a_unique = int(a[col].nunique())
            b_unique = int(b[col].nunique())
            merged_all = b[[col]].merge(a[[col]], on=col, how="inner")
            merged_sel = selected_b[[col]].merge(a[[col]], on=col, how="inner")
            validation_rows.append(
                {
                    "run": run,
                    "key": key,
                    "a_events": int(len(a)),
                    "b_events": int(len(b)),
                    "a_unique_keys": a_unique,
                    "b_unique_keys": b_unique,
                    "all_b_matched_events": int(len(merged_all)),
                    "all_b_match_fraction": float(len(merged_all) / max(len(b), 1)),
                    "selected_b_events": int(len(selected_b)),
                    "selected_b_matched_events": int(len(merged_sel)),
                    "selected_b_match_fraction": float(len(merged_sel) / max(len(selected_b), 1)),
                    "a_duplicate_keys": int(len(a) - a_unique),
                    "b_duplicate_keys": int(len(b) - b_unique),
                }
            )
    validation = pd.DataFrame(validation_rows)
    accepted_key = choose_event_key(config, validation)
    join_col = accepted_key.lower()
    event_rows = []
    for run, (a, selected_b) in event_tables.items():
        joined = selected_b.merge(
            a[
                [
                    join_col,
                    "a_charge_sum",
                    "a_selected_charge",
                    "a_amp_max",
                    "a_selected_count",
                    "a_has_selected",
                ]
            ],
            on=join_col,
            how="left",
            suffixes=("_b", "_a"),
        )
        joined["run"] = run
        joined["current_family"] = current.get(run, "unknown")
        joined["matched_a_event"] = joined["a_charge_sum"].notna()
        joined["join_key"] = accepted_key
        event_rows.append(joined)
    return (
        validation,
        pd.concat(event_rows, ignore_index=True),
        pd.DataFrame(b_count_rows),
        accepted_key,
    )


def per_run_astack_from_event_join(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for run, sub in events.groupby("run", sort=True):
        matched = sub[sub["matched_a_event"]].copy()
        charge = matched["a_charge_sum"].to_numpy(dtype=float)
        charge = charge[np.isfinite(charge)]
        if len(charge):
            median = float(np.median(charge))
            iqr = float(np.percentile(charge, 75) - np.percentile(charge, 25))
            p90 = float(np.percentile(charge, 90))
            nonzero = float((charge > 0).mean())
        else:
            median = iqr = p90 = nonzero = float("nan")
        rows.append(
            {
                "run": int(run),
                "current_family": str(sub["current_family"].iloc[0]),
                "b_selected_events": int(len(sub)),
                "event_matched_a_events": int(len(matched)),
                "event_matched_fraction": float(len(matched) / max(len(sub), 1)),
                "a_charge_median_event_matched": median,
                "a_charge_iqr_frac_event_matched": float(iqr / max(median, 1.0)) if len(charge) else float("nan"),
                "a_charge_p90_event_matched": p90,
                "a_nonzero_charge_fraction_event_matched": nonzero,
                "a_selected_fraction_event_matched": float(matched["a_has_selected"].mean()) if len(matched) else float("nan"),
                "mean_b_selected_count": float(sub["b_selected_count"].mean()),
            }
        )
    return pd.DataFrame(rows)


def ci(values: Sequence[float]) -> list:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return [None, None]
    return [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))]


def bootstrap_scores(frame: pd.DataFrame, rng: np.random.Generator, reps: int) -> pd.DataFrame:
    rows = []
    methods = sorted(frame["method"].unique())
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    by_run = {run: frame[frame["run"].eq(run)] for run in runs}
    for method in methods:
        sub = frame[frame["method"].eq(method)].copy()
        resid = sub["saturated_energy_res68"].to_numpy(dtype=float)
        ainst = sub["a_charge_iqr_frac_event_matched"].to_numpy(dtype=float)
        weights = np.maximum(sub["n_saturated"].to_numpy(dtype=float), 1.0)
        central_res = float(np.average(resid, weights=weights))
        central_astack = (
            float(abs(np.corrcoef(resid, ainst)[0, 1]))
            if len(sub) > 2 and np.std(resid) > 0 and np.std(ainst) > 0
            else 0.0
        )
        central_score = central_res * (1.0 + central_astack)
        boot_res = []
        boot_astack = []
        boot_score = []
        for _ in range(reps):
            chosen = rng.choice(runs, size=len(runs), replace=True)
            sample = pd.concat(
                [by_run[int(run)][by_run[int(run)]["method"].eq(method)] for run in chosen],
                ignore_index=True,
            )
            if sample.empty:
                continue
            r = sample["saturated_energy_res68"].to_numpy(dtype=float)
            a = sample["a_charge_iqr_frac_event_matched"].to_numpy(dtype=float)
            w = np.maximum(sample["n_saturated"].to_numpy(dtype=float), 1.0)
            val_res = float(np.average(r, weights=w))
            val_astack = (
                float(abs(np.corrcoef(r, a)[0, 1]))
                if len(sample) > 2 and np.std(r) > 0 and np.std(a) > 0
                else 0.0
            )
            boot_res.append(val_res)
            boot_astack.append(val_astack)
            boot_score.append(val_res * (1.0 + val_astack))
        rows.append(
            {
                "method": method,
                "family": str(sub["family"].iloc[0]),
                "n_runs": int(sub["run"].nunique()),
                "n_saturated": int(sub["n_saturated"].sum()),
                "mean_b_saturated_res68": central_res,
                "mean_b_saturated_res68_ci95": ci(boot_res),
                "abs_corr_b_res68_vs_event_astack_iqr": central_astack,
                "abs_corr_b_res68_vs_event_astack_iqr_ci95": ci(boot_astack),
                "event_astack_transfer_score": central_score,
                "event_astack_transfer_score_ci95": ci(boot_score),
            }
        )
    return pd.DataFrame(rows).sort_values("event_astack_transfer_score").reset_index(drop=True)


def md_table(frame: pd.DataFrame, cols: Sequence[str], limit: int = 40) -> str:
    sub = frame.loc[:, list(cols)].head(limit).copy()
    for col in sub.columns:
        sub[col] = sub[col].map(
            lambda v: "[" + ", ".join(f"{x:.5g}" if x is not None else "NA" for x in v) + "]"
            if isinstance(v, list)
            else (f"{v:.5g}" if isinstance(v, float) else str(v))
        )
    widths = [max(len(c), int(sub[c].map(len).max() if len(sub) else 0)) for c in sub.columns]
    lines = [
        "| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(sub.columns)) + " |",
        "| " + " | ".join("---" for _ in sub.columns) + " |",
    ]
    for _, row in sub.iterrows():
        lines.append("| " + " | ".join(str(row[c]).ljust(widths[i]) for i, c in enumerate(sub.columns)) + " |")
    return "\n".join(lines)


def write_report(
    out_dir: Path,
    config: dict,
    result: dict,
    validation: pd.DataFrame,
    b_counts: pd.DataFrame,
    event_astack: pd.DataFrame,
    scores: pd.DataFrame,
    run_panel: pd.DataFrame,
) -> None:
    winner = result["winner"]
    heldout_validation = validation[validation["run"].isin(heldout_runs(config))]
    accepted_key = result["event_key_validation"]["accepted_event_key"]
    accepted_summary = heldout_validation[heldout_validation["key"].eq(accepted_key)]
    evt_summary = heldout_validation[heldout_validation["key"].eq("EVT")]
    eventno_summary = heldout_validation[heldout_validation["key"].eq("EVENTNO")]
    rejected_summary = heldout_validation[~heldout_validation["key"].eq(accepted_key)]
    text = f"""# S14n: event-key A/B coincidence validation for saturation transfer

## Abstract

This study validates whether A-stack and B-stack raw ROOT event counters support event-key coincidence joins for the S14 saturation-transfer stress test. The raw B-stack reproduction gate is rebuilt from `h101/HRDv` and passes at {result['raw_reproduction']['reproduced_selected_pulses']:,} selected B2/B4/B6/B8 pulses. Among the candidate counters, `{accepted_key}` is accepted as the event join key because it matches {result['event_key_validation']['accepted_selected_b_match_fraction_min']:.5f}--{result['event_key_validation']['accepted_selected_b_match_fraction_max']:.5f} of selected B events on the held-out runs with no duplicate keys in either stack. `EVT` is rejected because it is not duplicate-free in these files and gives many-to-many joins. Replacing the S14m run-level A-stack handle with event-key matched A-stack charge leaves **{winner['method']}** as the best transfer method, with score {winner['event_astack_transfer_score']:.5g} and run-bootstrap 95% CI {winner['event_astack_transfer_score_ci95']}.

## 1. Raw ROOT Reproduction

For each B-stack raw file `hrdb_run_*.root`, the waveform branch is reshaped as events by eight channels by 18 samples. The baseline is the channel-wise median of samples 0--3. A B pulse is counted when

\\[
\\max_t \\left(x_{{i,c,t}}-\\operatorname{{median}}(x_{{i,c,0:3}})\\right) > 1000\\,\\mathrm{{ADC}},
\\]

for one of B2/B4/B6/B8. This exactly reproduces the S14f/S14m ticket number from raw ROOT:

| Quantity | Expected | Reproduced | Delta | Pass |
|---|---:|---:|---:|:---|
| B-stack selected pulses | {result['raw_reproduction']['expected_selected_pulses']:,} | {result['raw_reproduction']['reproduced_selected_pulses']:,} | {result['raw_reproduction']['delta']:+,} | {str(result['raw_reproduction']['pass']).lower()} |

Per-run reproduction:

{md_table(b_counts, ['run', 'events_total', 'events_with_selected', 'selected_pulses'], 80)}

## 2. Event-Key Coincidence Test

The ticket asks whether A-stack and B-stack counters can be joined at event-key level. For each run, A and B event tables were independently rebuilt from their raw ROOT files using the candidate counters `EVT` and `EVENTNO`. The selected-event coincidence fraction is

\\[
f_k(r)=N_{{AB,\\mathrm{{sel}}}}(r,k)/N_{{B,\\mathrm{{sel}}}}(r),
\\]

where membership is evaluated under key \(k\\). A key is acceptable only if it has no duplicate keys in either stack and produces stable high selected-B coincidence over the held-out runs.

Held-out `{accepted_key}` summary: minimum selected-B match fraction {result['event_key_validation']['accepted_selected_b_match_fraction_min']:.6f}, median {result['event_key_validation']['accepted_selected_b_match_fraction_median']:.6f}, maximum {result['event_key_validation']['accepted_selected_b_match_fraction_max']:.6f}. Held-out `EVT` summary: minimum {result['event_key_validation']['evt_selected_b_match_fraction_min']:.6f}, median {result['event_key_validation']['evt_selected_b_match_fraction_median']:.6f}, maximum {result['event_key_validation']['evt_selected_b_match_fraction_max']:.6f}; its maximum duplicate counts are {result['event_key_validation']['evt_max_duplicate_keys_a']} in A and {result['event_key_validation']['evt_max_duplicate_keys_b']} in B, so it is not a valid one-to-one key.

Accepted-key table:

{md_table(accepted_summary, ['run', 'key', 'a_events', 'b_events', 'selected_b_events', 'selected_b_matched_events', 'selected_b_match_fraction', 'a_duplicate_keys', 'b_duplicate_keys'], 80)}

Rejected/diagnostic candidate excerpt:

{md_table(rejected_summary, ['run', 'key', 'selected_b_events', 'selected_b_matched_events', 'selected_b_match_fraction', 'a_duplicate_keys', 'b_duplicate_keys'], 30)}

## 3. Event-Level A-Stack Charge Handle

For each selected B event, the matched A event is retrieved by `{accepted_key}`. The A-stack event charge is computed from channels A1 and A3 as positive baseline-subtracted waveform area,

\\[
Q_A(e)=\\sum_{{c\\in C_A}}\\sum_t \\max\\left(x_{{e,c,t}}-\\operatorname{{median}}(x_{{e,c,0:3}}),0\\right),\\quad C_A=(A1,A3).
\\]

The event-level transfer nuisance for run \(r\) is the fractional interquartile width of this matched charge distribution,

\\[
I_A^\\mathrm{{evt}}(r)=\\frac{{Q_{{75}}(Q_A(e)\\mid e\\in B_r^\\mathrm{{sel}})-Q_{{25}}(Q_A(e)\\mid e\\in B_r^\\mathrm{{sel}})}}{{\\operatorname{{median}}(Q_A(e)\\mid e\\in B_r^\\mathrm{{sel}})}}.
\\]

This differs from S14m by conditioning the A charge on the same event keys as selected B activity rather than summarizing all selected A-stack activity at run level.

{md_table(event_astack, ['run', 'current_family', 'b_selected_events', 'event_matched_a_events', 'event_matched_fraction', 'a_charge_median_event_matched', 'a_charge_iqr_frac_event_matched', 'a_selected_fraction_event_matched'], 80)}

## 4. Benchmark and Bootstrap

The fixed S14f method panel is re-scored against the event-matched A-stack handle. The benchmark includes observed even charge, a rising-edge template/range lookup traditional correction, ridge regression, gradient-boosted trees, MLP, 1D-CNN, and the new template-residual MLP architecture. The split unit remains run: training runs are {result['split']['train_runs']} and held-out runs are {result['split']['heldout_runs']}. No event from a held-out run contributes to model training.

For method \(m\), held-out run \(r\), S14f saturated energy-proxy resolution \(R_m(r)\), and event-matched A-stack nuisance \(I_A^\\mathrm{{evt}}(r)\), the primary score is

\\[
S_m^\\mathrm{{evt}}=\\bar R_m\\left(1+\\left|\\rho_R(R_m(r),I_A^\\mathrm{{evt}}(r))\\right|\\right),
\\qquad
\\bar R_m=\\frac{{\\sum_r n_{{m,r}}R_m(r)}}{{\\sum_r n_{{m,r}}}} .
\\]

The bootstrap resamples held-out runs with replacement and recomputes both the weighted resolution and the A-charge correlation. Lower scores are better.

{md_table(scores, ['method', 'family', 'n_runs', 'n_saturated', 'mean_b_saturated_res68', 'mean_b_saturated_res68_ci95', 'abs_corr_b_res68_vs_event_astack_iqr', 'abs_corr_b_res68_vs_event_astack_iqr_ci95', 'event_astack_transfer_score', 'event_astack_transfer_score_ci95'], 80)}

## 5. Run-Level Transfer Panel

{md_table(run_panel.sort_values(['method', 'run']), ['run', 'current_family', 'method', 'n_saturated', 'saturated_energy_res68', 'a_charge_iqr_frac_event_matched', 'event_matched_fraction'], 140)}

## 6. Systematics and Caveats

The event-key join validates DAQ-level coincidence, not a particle-truth association. A and B entries can differ slightly by run, so the accepted key is judged by selected-B coverage and duplicate-free uniqueness rather than requiring equal tree lengths. The A-stack charge is a nuisance/stress variable; it is not an independent absolute energy label and cannot remove S14f's duplicate-readout closure assumptions. The benchmark predictions themselves are inherited from S14f to isolate the ticket's requested change from run-level A handles to event-matched A charge; retraining every model with A-stack charge as an input would answer a different leakage-prone question. The bootstrap treats runs as exchangeable held-out units, so CIs reflect run-to-run transfer variation, not ROOT waveform calibration uncertainty within a run.

## 7. Finding

{result['finding']}

## 8. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s14n_1783565280_12477_10e6006f_event_key_ab_coincidence_validation.py --config configs/s14n_1783565280_12477_10e6006f_event_key_ab_coincidence_validation.yaml
```

Artifacts: `result.json`, `REPORT.md`, `event_key_validation.csv`, `event_matched_astack_run_summary.csv`, `method_event_astack_transfer_scores.csv`, `method_run_event_astack_panel.csv`, `b_reproduction_counts_by_run.csv`, `input_sha256.csv`, and `manifest.json`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="configs/s14n_1783565280_12477_10e6006f_event_key_ab_coincidence_validation.yaml",
    )
    args = parser.parse_args()
    t0 = time.time()
    config_path = ROOT / args.config if not Path(args.config).is_absolute() else Path(args.config)
    config = load_config(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    validation, event_join, b_counts, accepted_key = event_key_validation(config)
    reproduced = int(b_counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if reproduced != expected:
        raise RuntimeError(f"raw reproduction failed: {reproduced} != {expected}")

    event_astack = per_run_astack_from_event_join(event_join)
    s14f_dir = ROOT / config["s14f_dir"]
    per_run = pd.read_csv(s14f_dir / "per_run_acceptance.csv")
    metrics = pd.read_csv(s14f_dir / "method_metrics.csv")[["method", "family"]].drop_duplicates()
    per_run = per_run.merge(metrics, on="method", how="left")
    run_panel = per_run.merge(event_astack, on=["run", "current_family"], how="inner")
    run_panel = run_panel[run_panel["run"].isin(heldout_runs(config))].reset_index(drop=True)
    scores = bootstrap_scores(
        run_panel,
        np.random.default_rng(int(config["random_seed"])),
        int(config["bootstrap_reps"]),
    )

    heldout_validation = validation[validation["run"].isin(heldout_runs(config))]
    evt = heldout_validation[heldout_validation["key"].eq("EVT")]
    eventno = heldout_validation[heldout_validation["key"].eq("EVENTNO")]
    accepted = heldout_validation[heldout_validation["key"].eq(accepted_key)]
    winner = scores.iloc[0].to_dict()
    finding = (
        f"`{accepted_key}` is the accepted duplicate-free A/B event key for this transfer study: "
        f"selected-B match fractions over held-out runs span "
        f"{accepted['selected_b_match_fraction'].min():.5f} to "
        f"{accepted['selected_b_match_fraction'].max():.5f}. `EVT` is rejected because it has "
        f"held-out duplicate counts up to A={int(evt['a_duplicate_keys'].max())}, "
        f"B={int(evt['b_duplicate_keys'].max())}. Replacing S14m's run-level A-stack "
        f"handle with event-matched A charge keeps {winner['method']} as the best method "
        f"(score {winner['event_astack_transfer_score']:.5g}, 95% CI "
        f"{winner['event_astack_transfer_score_ci95']})."
    )
    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": reproduced,
            "delta": reproduced - expected,
            "pass": True,
        },
        "event_key_validation": {
            "accepted_event_key": accepted_key,
            "accepted_selected_b_match_fraction_min": float(accepted["selected_b_match_fraction"].min()),
            "accepted_selected_b_match_fraction_median": float(accepted["selected_b_match_fraction"].median()),
            "accepted_selected_b_match_fraction_max": float(accepted["selected_b_match_fraction"].max()),
            "accepted_max_duplicate_keys_a": int(accepted["a_duplicate_keys"].max()),
            "accepted_max_duplicate_keys_b": int(accepted["b_duplicate_keys"].max()),
            "evt_selected_b_match_fraction_min": float(evt["selected_b_match_fraction"].min()),
            "evt_selected_b_match_fraction_median": float(evt["selected_b_match_fraction"].median()),
            "evt_selected_b_match_fraction_max": float(evt["selected_b_match_fraction"].max()),
            "evt_max_duplicate_keys_a": int(evt["a_duplicate_keys"].max()),
            "evt_max_duplicate_keys_b": int(evt["b_duplicate_keys"].max()),
            "eventno_selected_b_match_fraction_min": float(eventno["selected_b_match_fraction"].min()),
            "eventno_selected_b_match_fraction_median": float(eventno["selected_b_match_fraction"].median()),
            "eventno_selected_b_match_fraction_max": float(eventno["selected_b_match_fraction"].max()),
        },
        "split": {
            "split_unit": "run",
            "train_runs": sorted(set(configured_runs(config)) - set(heldout_runs(config))),
            "heldout_runs": heldout_runs(config),
        },
        "primary_metric": "event_astack_transfer_score = weighted held-out B saturated R68 times one plus absolute run-level correlation with event-matched A-stack charge IQR fraction",
        "winner": {
            "method": winner["method"],
            "family": winner["family"],
            "event_astack_transfer_score": float(winner["event_astack_transfer_score"]),
            "event_astack_transfer_score_ci95": winner["event_astack_transfer_score_ci95"],
            "mean_b_saturated_res68": float(winner["mean_b_saturated_res68"]),
            "mean_b_saturated_res68_ci95": winner["mean_b_saturated_res68_ci95"],
            "abs_corr_b_res68_vs_event_astack_iqr": float(winner["abs_corr_b_res68_vs_event_astack_iqr"]),
            "abs_corr_b_res68_vs_event_astack_iqr_ci95": winner["abs_corr_b_res68_vs_event_astack_iqr_ci95"],
        },
        "methods": json.loads(scores.to_json(orient="records")),
        "finding": finding,
        "next_tickets": [],
        "runtime_sec": round(time.time() - t0, 1),
    }

    b_counts.to_csv(out_dir / "b_reproduction_counts_by_run.csv", index=False)
    validation.to_csv(out_dir / "event_key_validation.csv", index=False)
    event_astack.to_csv(out_dir / "event_matched_astack_run_summary.csv", index=False)
    run_panel.to_csv(out_dir / "method_run_event_astack_panel.csv", index=False)
    scores.to_csv(out_dir / "method_event_astack_transfer_scores.csv", index=False)
    event_join.head(200000).to_csv(out_dir / "event_join_selected_b_excerpt.csv", index=False)

    input_paths = [raw_path(config, "b", run) for run in configured_runs(config)]
    input_paths += [raw_path(config, "a", run) for run in configured_runs(config)]
    input_paths += [s14f_dir / "method_metrics.csv", s14f_dir / "per_run_acceptance.csv", config_path]
    input_rows = []
    for p in input_paths:
        display = p.relative_to(ROOT)
        input_rows.append({"path": str(display), "bytes": int(p.stat().st_size), "sha256": sha256_file(p)})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    result = json_clean(result)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                "command": f"/home/billy/anaconda3/bin/python scripts/s14n_1783565280_12477_10e6006f_event_key_ab_coincidence_validation.py --config {args.config}",
                "git_commit": git_commit(),
                "platform": platform.platform(),
                "runtime_sec": result["runtime_sec"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    write_report(out_dir, config, result, validation, b_counts, event_astack, scores, run_panel)


if __name__ == "__main__":
    main()
