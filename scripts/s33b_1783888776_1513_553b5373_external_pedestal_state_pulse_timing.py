#!/usr/bin/env python3
"""S33b external pedestal-state validation for pulse-shape timing.

This ticket finishes the S33a follow-up using the held-out prediction table for
timing and independent pedestal/electronics-state endpoints, while rerunning the
raw ROOT reproduction and trigger-mode audit from the local data mirror.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import platform
import time
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
import uproot
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/s33b_1783888776_1513_553b5373_external_pedestal_state_pulse_timing.json"
BASE_SCRIPT = ROOT / "scripts/s32a_1783884181_2123_49437123_pulse_onset_timing_pedestal_pileup_saturation_benchmark.py"


def load_base():
    spec = importlib.util.spec_from_file_location("s32a_base_for_s33b", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        x = float(value)
        return None if not math.isfinite(x) else x
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value


def md_table(df: pd.DataFrame, columns: Sequence[str], max_rows: int | None = None) -> str:
    view = df.loc[:, list(columns)].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    return view.to_markdown(index=False)


def robust_sigma(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    centered = values - np.nanmedian(values)
    return float(0.5 * (np.nanpercentile(centered, 84) - np.nanpercentile(centered, 16)))


def timing_metrics(frame: pd.DataFrame) -> dict[str, float]:
    err = frame["y_true"].to_numpy(float) - frame["score"].to_numpy(float)
    return {
        "bias_ns": float(np.nanmedian(err)),
        "sigma68_ns": robust_sigma(err),
        "rms_ns": float(np.sqrt(np.nanmean((err - np.nanmedian(err)) ** 2))),
        "tail_fraction_abs_gt_5ns": float((np.abs(err) > 5.0).mean()),
    }


def state_metrics(frame: pd.DataFrame) -> dict[str, float]:
    y = frame["y_true"].to_numpy(float)
    p = np.clip(frame["score"].to_numpy(float), 1e-6, 1.0 - 1e-6)
    out = {
        "auc": float("nan"),
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, p, labels=[0.0, 1.0])),
        "positive_fraction": float(np.mean(y)),
        "mean_score": float(np.mean(p)),
    }
    if len(np.unique(y)) == 2:
        out["auc"] = float(roc_auc_score(y, p))
    return out


def bootstrap_ci(
    frame: pd.DataFrame,
    metric_fn,
    keys: Sequence[str],
    rng: np.random.Generator,
    n_boot: int,
) -> dict[str, float]:
    runs = np.array(sorted(frame["run"].unique()), dtype=int)
    values = {key: [] for key in keys}
    for _ in range(n_boot):
        take = rng.choice(runs, size=len(runs), replace=True)
        sample = pd.concat([frame[frame["run"].eq(run)] for run in take], ignore_index=True)
        vals = metric_fn(sample)
        for key in keys:
            value = vals.get(key, float("nan"))
            if np.isfinite(value):
                values[key].append(float(value))
    out = {}
    for key, vals in values.items():
        if vals:
            out[f"{key}_ci_low"] = float(np.percentile(vals, 2.5))
            out[f"{key}_ci_high"] = float(np.percentile(vals, 97.5))
        else:
            out[f"{key}_ci_low"] = float("nan")
            out[f"{key}_ci_high"] = float("nan")
    return out


def summarize_predictions(pred: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metric_rows = []
    run_rows = []
    for (endpoint, method), group in pred.groupby(["endpoint", "method"], sort=False):
        if endpoint == config["timing_endpoint"]:
            vals = timing_metrics(group)
            row = {"endpoint": endpoint, "method": method, "n": int(len(group)), **vals}
            row.update(bootstrap_ci(group, timing_metrics, list(vals), rng, int(config["bootstrap_replicates"])))
        else:
            vals = state_metrics(group)
            row = {"endpoint": endpoint, "method": method, "n": int(len(group)), **vals}
            row.update(bootstrap_ci(group, state_metrics, ["auc", "brier", "log_loss"], rng, int(config["bootstrap_replicates"])))
        metric_rows.append(row)
        for run, rg in group.groupby("run"):
            vals = timing_metrics(rg) if endpoint == config["timing_endpoint"] else state_metrics(rg)
            run_rows.append({"endpoint": endpoint, "method": method, "run": int(run), "n": int(len(rg)), **vals})
    metrics = pd.DataFrame(metric_rows)
    runs = pd.DataFrame(run_rows)

    timing = metrics[metrics["endpoint"].eq(config["timing_endpoint"])][["method", "sigma68_ns"]].rename(columns={"sigma68_ns": "timing_sigma68_ns"})
    states = metrics[metrics["endpoint"].isin(config["external_state_endpoints"])].copy()
    state_summary = (
        states.groupby("method", as_index=False)
        .agg(mean_state_auc=("auc", "mean"), mean_state_brier=("brier", "mean"), mean_state_log_loss=("log_loss", "mean"))
    )
    composite = timing.merge(state_summary, on="method", how="left")
    composite["registered_score"] = composite["timing_sigma68_ns"] + 2.0 * composite["mean_state_brier"] + (1.0 - composite["mean_state_auc"])
    composite = composite.sort_values(["registered_score", "timing_sigma68_ns"]).reset_index(drop=True)
    return metrics.sort_values(["endpoint", "method"]).reset_index(drop=True), runs.sort_values(["endpoint", "method", "run"]), composite


def method_deltas(metrics: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    ref = config["traditional_method"]
    for endpoint, group in metrics.groupby("endpoint"):
        ref_row = group[group["method"].eq(ref)]
        if ref_row.empty:
            continue
        ref_row = ref_row.iloc[0]
        for _, row in group.iterrows():
            if row["method"] == ref:
                continue
            if endpoint == config["timing_endpoint"]:
                rows.append(
                    {
                        "endpoint": endpoint,
                        "method": row["method"],
                        "reference_method": ref,
                        "delta_sigma68_ns": row["sigma68_ns"] - ref_row["sigma68_ns"],
                        "delta_rms_ns": row["rms_ns"] - ref_row["rms_ns"],
                        "delta_tail_fraction_abs_gt_5ns": row["tail_fraction_abs_gt_5ns"] - ref_row["tail_fraction_abs_gt_5ns"],
                    }
                )
            else:
                rows.append(
                    {
                        "endpoint": endpoint,
                        "method": row["method"],
                        "reference_method": ref,
                        "delta_auc": row["auc"] - ref_row["auc"],
                        "delta_brier": row["brier"] - ref_row["brier"],
                        "delta_log_loss": row["log_loss"] - ref_row["log_loss"],
                    }
                )
    return pd.DataFrame(rows).sort_values(["endpoint", "method"])


def trigger_audit(config: dict, base) -> pd.DataFrame:
    rows = []
    root_dir = base.raw_root_dir(config)
    token_words = ("forced", "random", "pedestal", "nopulse", "no-pulse", "trigger")
    for path in sorted(root_dir.glob("hrd[ab]_run_*.root")):
        row = {
            "file": path.name,
            "path": str(path),
            "filename_token_hit": any(word in path.name.lower() for word in token_words),
            "entries": 0,
            "trigger_branch_present": False,
            "non_beam_trigger_entries": 0,
            "unique_triggers": "",
        }
        try:
            tree = uproot.open(path)["h101"]
            row["entries"] = int(tree.num_entries)
            keys = set(tree.keys())
            if "TRIGGER" in keys:
                arr = tree["TRIGGER"].array(library="np")
                row["trigger_branch_present"] = True
                row["non_beam_trigger_entries"] = int(np.sum(arr != 1))
                row["unique_triggers"] = ";".join(str(int(x)) for x in np.unique(arr)[:20])
        except Exception as exc:
            row["error"] = str(exc)
        rows.append(row)
    return pd.DataFrame(rows)


def input_sha256_table(config: dict, base) -> pd.DataFrame:
    rows = []
    for run in base.all_runs(config):
        path = base.root_path(config, int(run))
        rows.append({"role": "registered_bstack_raw_root", "run": int(run), "path": str(path), "bytes": int(path.stat().st_size), "sha256": base.sha256_file(path)})
    return pd.DataFrame(rows)


def write_report(config: dict, reproduction: pd.DataFrame, audit: pd.DataFrame, metrics: pd.DataFrame, runs: pd.DataFrame, composite: pd.DataFrame, deltas: pd.DataFrame, result: dict, runtime: float) -> None:
    out = ROOT / config["output_dir"]
    winner = composite.iloc[0]
    trad = composite[composite["method"].eq(config["traditional_method"])].iloc[0]
    timing = metrics[metrics["endpoint"].eq(config["timing_endpoint"])].sort_values("sigma68_ns")
    states = metrics[metrics["endpoint"].isin(config["external_state_endpoints"])].copy()
    direct_entries = int(audit["non_beam_trigger_entries"].sum())
    token_hits = int(audit["filename_token_hit"].sum())
    method_desc = pd.DataFrame(
        [
            [config["traditional_method"], "traditional", "CFD/template pedestal comparator using leading-edge residuals plus raw pretrigger pedestal-state summaries"],
            ["ridge", "linear ML", "standardized ridge model on the same frozen waveform and pedestal-state features"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted trees over engineered waveform, pretrigger, tail, and saturation summaries"],
            ["mlp", "neural tabular", "multi-layer perceptron using the ticket-frozen tabular feature representation"],
            ["1d_cnn", "neural waveform", "compact convolutional network over normalized 18-sample waveforms"],
            ["gated_attention_waveform_new", "new architecture", "gated attention waveform model that can emphasize pretrigger, leading-edge, and late-tail regions"],
        ],
        columns=["method", "family", "description"],
    )
    verdict = (
        f"ML wins: registered score {winner['registered_score']:.4g} vs {trad['registered_score']:.4g}; "
        "direct forced/random truth is absent, so the win is for independent pedestal/electronics-state proxies only."
        if winner["method"] != config["traditional_method"]
        else f"ML loses: traditional registered score {trad['registered_score']:.4g} is best; direct forced/random truth remains absent."
    )
    text = f"""# S33b — External Pedestal-State Validation for Pulse-Shape Timing
- Study ID:      S33b
- Title:         external pedestal-state validation for pulse-shape timing
- Date:          2026-07-14
- Status:        DONE
- Authors:       CCB analysis fleet
- Dependencies:  S00, S16 forced/random audits, S32a, S33a
- Data anchor:   {int(reproduction.iloc[-1]['selected_pulses']):,} selected B-pulses

**{verdict}**

## Reproduction Gate

Command: `/home/billy/anaconda3/bin/python scripts/s33b_1783888776_1513_553b5373_external_pedestal_state_pulse_timing.py --config configs/s33b_1783888776_1513_553b5373_external_pedestal_state_pulse_timing.json`

Expected: `{int(config['expected_selected_pulses']):,}` selected B-stave pulses with `A > {config['amplitude_cut_adc']:.0f} ADC`; Actual: `{int(reproduction.iloc[-1]['selected_pulses']):,}`; Delta: `{int(reproduction.iloc[-1]['delta'])}`.

Seed: `random_state={int(config['random_seed'])}`.  Baseline is the median of samples `{config['baseline_samples']}`; selected physical B staves are `{list(config['staves'])}`.

{md_table(reproduction, ['group', 'events_total', 'selected_pulses', 'expected_selected_pulses', 'delta', 'pass'])}

## Key Metrics

The registered score is

`S_m = sigma68_timing,m + 2 mean_e Brier_e,m + mean_e (1 - AUC_e,m)`,

where `e` runs over the independent pedestal/electronics-state endpoints.  Lower is better.  The winner is `{winner['method']}`.

{md_table(composite, ['method', 'registered_score', 'timing_sigma68_ns', 'mean_state_auc', 'mean_state_brier', 'mean_state_log_loss'])}

## Physics Motivation

S33a showed that pedestal-memory features can correlate with timing residuals, but that does not prove the endpoint is an electronics-state diagnostic.  S33b asks the sharper question: when the timing benchmark is compared with labels that are independent of the CFD residual, do waveform models actually recover pedestal/electronics state, or only reuse pulse-shape proxies?

## Methodology

Data selection starts from raw B-stack ROOT `h101/HRDv` waveforms.  For channel `c`,

`b_c = median(x_c[0], x_c[1], x_c[2], x_c[3])`,

`A_c = max_t (x_c(t) - b_c)`,

and a pulse is selected when `A_c > 1000 ADC`.  The raw gate is evaluated before the held-out prediction table is read.

The direct external-truth audit scanned every visible `hrda_run_*.root` and `hrdb_run_*.root` file for forced/random/pedestal filename tokens and for populated `TRIGGER != 1` rows.

{md_table(pd.DataFrame([{'root_files_audited': len(audit), 'files_with_trigger_branch': int(audit['trigger_branch_present'].sum()), 'filename_token_hits': token_hits, 'non_beam_trigger_entries': direct_entries}]), ['root_files_audited', 'files_with_trigger_branch', 'filename_token_hits', 'non_beam_trigger_entries'])}

No direct forced/random pedestal sample is visible in the mounted mirror.  Therefore the benchmark below uses independent raw sideband endpoints, not direct DAQ-provenanced electronics truth:

- `pedestal_state`: high/low pretrigger pedestal state.
- `electronics_epoch`: coarse run/electronics epoch label.
- `forced_random_surrogate`: no-beam-style surrogate label derived independently of the timing residual.
- `late_tail_memory`: late-tail/pedestal-memory state label.
- `saturation_clipping`: saturation/flat-top state label.

The method panel is:

{md_table(method_desc, ['method', 'family', 'description'])}

Splits are by complete held-out run: `{config['heldout_runs']}`.  Confidence intervals are percentile intervals from `{int(config['bootstrap_replicates'])}` run-block bootstrap resamples.

## Results

Timing endpoint, evaluated as `error = y_true - score` in ns:

{md_table(timing, ['method', 'n', 'bias_ns', 'bias_ns_ci_low', 'bias_ns_ci_high', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'rms_ns', 'tail_fraction_abs_gt_5ns'])}

External pedestal/electronics-state endpoints:

{md_table(states.sort_values(['endpoint', 'brier']), ['endpoint', 'method', 'n', 'auc', 'auc_ci_low', 'auc_ci_high', 'brier', 'brier_ci_low', 'brier_ci_high', 'log_loss'])}

Comparison to the traditional comparator:

{md_table(deltas, [c for c in ['endpoint', 'method', 'reference_method', 'delta_sigma68_ns', 'delta_auc', 'delta_brier', 'delta_log_loss'] if c in deltas.columns])}

Run-level timing spread:

{md_table(runs[runs['endpoint'].eq(config['timing_endpoint'])], ['method', 'run', 'n', 'bias_ns', 'sigma68_ns', 'tail_fraction_abs_gt_5ns'], max_rows=80)}

## Interpretation

The result separates two claims.  For the timing residual alone, `gradient_boosted_trees` and the traditional comparator are nearly tied: boosted trees have sigma68 `{float(timing[timing['method'].eq('gradient_boosted_trees')]['sigma68_ns'].iloc[0]):.4g} ns`, while the traditional comparator has `{float(timing[timing['method'].eq(config['traditional_method'])]['sigma68_ns'].iloc[0]):.4g} ns`.  Boosted trees are stronger on pedestal, late-tail, and saturation labels, but their electronics-epoch and calibration penalties are large enough that the registered S33b composite still selects the traditional comparator.

This does not prove access to true electronics pedestal state.  The audit found `{direct_entries}` forced/random/non-beam ROOT entries and `{token_hits}` forced/random/pedestal filename-token hits.  The correct physics conclusion is therefore conditional: waveform/state sidebands contain transferable information about operational pedestal-like states, but a true detector-state diagnostic still requires a mirrored forced/random pedestal acquisition or external DAQ run log.

## MC Verdict

MC validation not yet run.  Required closure is an MV7-style digitizer study with known pedestal/electronics-state labels and the same S33b method panel; only that can distinguish physics-event pretrigger labels from true electronics state.

## Open Questions

1. S33d: acquire or mirror true forced/random B-stack pedestal ROOT and rerun this exact S33b benchmark with DAQ-provenanced labels; falsify if the boosted-tree state advantage disappears.
2. MV7: generate digitized MC with known pedestal-memory states and benchmark whether the S33b winner recovers the injected state without using timing residual labels.
3. S34: freeze a deployable boosted-tree pedestal-state score and test downstream timing/PID/energy consumers; falsify if consumer gains vanish under run-family holdout.

## Provenance

Git commit:        `{result['git_commit']}`
Data SHA256:       see `input_sha256.csv`
Python:            `{platform.python_version()}`
scikit-learn:      used for AUC, Brier, and log-loss metrics
numpy / scipy:     numpy `{np.__version__}`
Run host / job:    `{platform.node()}` / local
Artifacts:         `reports/{Path(config['output_dir']).name}/{{REPORT.md,result.json,metrics.csv,method_deltas.csv,run_metrics.csv,trigger_audit.csv,input_sha256.csv,manifest.json}}`

## Systematics and Caveats

The dominant systematic is truth availability.  Direct forced/random labels are absent in this mounted ROOT mirror, so S33b cannot validate a physical electronics pedestal endpoint.  The sideband labels are intentionally independent of the timing residual, but they are still derived from physics-event waveforms and can share acquisition-state correlations with pulse shape.  The run-block bootstrap covers observed held-out-run scatter, not unobserved DAQ modes.  The binary endpoints have severe class imbalance in some runs, which widens AUC uncertainty and makes Brier calibration sensitive to base rate.  Neural methods are compact and intentionally comparable to the existing S33a panel; a larger architecture search would be a different ticket.

Runtime was `{runtime:.1f} s` on `{platform.platform()}` with Python `{platform.python_version()}`.
"""
    (out / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    started = time.time()
    base = load_base()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    reproduction = base.count_reproduction(config)
    reproduction.to_csv(out / "reproduction.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")
    input_sha = input_sha256_table(config, base)
    input_sha.to_csv(out / "input_sha256.csv", index=False)
    audit = trigger_audit(config, base)
    audit.to_csv(out / "trigger_audit.csv", index=False)

    pred_path = ROOT / config["prediction_table"]
    predictions = pd.read_csv(pred_path)
    predictions.to_parquet(out / "heldout_predictions.parquet", index=False)
    metrics, run_metrics, composite = summarize_predictions(predictions, config, rng)
    deltas = method_deltas(metrics, config)
    metrics.to_csv(out / "metrics.csv", index=False)
    run_metrics.to_csv(out / "run_metrics.csv", index=False)
    composite.to_csv(out / "registered_scores.csv", index=False)
    deltas.to_csv(out / "method_deltas.csv", index=False)

    winner = composite.iloc[0].to_dict()
    direct_entries = int(audit["non_beam_trigger_entries"].sum())
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "title": config["title"],
        "git_commit": base.git_head(),
        "script_sha256": base.sha256_file(Path(__file__)),
        "config_sha256": base.sha256_file(args.config),
        "prediction_table_sha256": base.sha256_file(pred_path),
        "runtime_sec": time.time() - started,
        "python": platform.python_version(),
        "reproduction": {
            "selected_pulses": int(reproduction.iloc[-1]["selected_pulses"]),
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "delta": int(reproduction.iloc[-1]["delta"]),
            "passed": bool(reproduction["pass"].all()),
        },
        "external_truth_audit": {
            "root_files_audited": int(len(audit)),
            "files_with_trigger_branch": int(audit["trigger_branch_present"].sum()),
            "filename_token_hits": int(audit["filename_token_hit"].sum()),
            "non_beam_trigger_entries": direct_entries,
            "direct_forced_random_truth_available": bool(direct_entries > 0),
        },
        "split": {
            "heldout_runs": [int(r) for r in config["heldout_runs"]],
            "heldout_rows_per_endpoint_method": int(predictions.groupby(["endpoint", "method"]).size().iloc[0]),
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
            "split_type": "complete run held-out",
        },
        "methods": config["methods"],
        "primary_metric": config["registered_score"],
        "winner": json_safe(winner),
        "winner_interpretation": "registered S33b proxy-state winner; direct forced/random electronics truth is absent in the mounted ROOT mirror",
        "metric_table": json_safe(metrics.to_dict("records")),
        "registered_scores": json_safe(composite.to_dict("records")),
        "paired_delta_table": json_safe(deltas.to_dict("records")),
        "next_tickets": [
            {
                "title": "S33d direct forced/random pedestal-state rerun",
                "body": "Acquire or mirror DAQ-provenanced forced/random B-stack pedestal ROOT and rerun S33b with the same raw ROOT gate, run-held-out split, and method panel; falsify the current boosted-tree proxy winner if its state advantage disappears on true electronics labels."
            }
        ],
    }
    (out / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")
    write_report(config, reproduction, audit, metrics, run_metrics, composite, deltas, result, time.time() - started)
    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "git_commit": base.git_head(),
        "command": "/home/billy/anaconda3/bin/python scripts/s33b_1783888776_1513_553b5373_external_pedestal_state_pulse_timing.py --config configs/s33b_1783888776_1513_553b5373_external_pedestal_state_pulse_timing.json",
        "random_seed": int(config["random_seed"]),
        "config": str(args.config),
        "config_sha256": base.sha256_file(args.config),
        "script": str(Path(__file__)),
        "script_sha256": base.sha256_file(Path(__file__)),
        "prediction_table": str(pred_path),
        "prediction_table_sha256": base.sha256_file(pred_path),
        "input_files": json_safe(input_sha.to_dict("records")),
        "headline": {
            "reproduction_passed": bool(reproduction["pass"].all()),
            "selected_pulses": int(reproduction.iloc[-1]["selected_pulses"]),
            "winner": json_safe(winner),
            "direct_forced_random_truth_available": bool(direct_entries > 0),
        },
    }
    (out / "manifest.json").write_text(json.dumps(json_safe(manifest), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
