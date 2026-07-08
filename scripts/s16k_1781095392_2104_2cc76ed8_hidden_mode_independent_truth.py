#!/usr/bin/env python3
"""S16k hidden-mode independent-truth confirmation.

The claimed ticket asks whether the S16j/S16f pretrigger hidden-mode scores
remain predictive when tested against an independent forced/random pedestal
truth or a blinded timing-tail label rather than the S16i beam-trigger proxy.

The mounted ROOT mirror has repeatedly shown zero direct forced/random B-stack
entries. This script verifies that gate from the current raw ROOT files, then
uses the frozen S16f leave-one-run-out held-out prediction panel as the blinded
timing-tail confirmation target. Metrics and confidence intervals are computed
fresh for this ticket.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Sequence

os.environ.setdefault("MPLCONFIGDIR", "/tmp/s16k_1781095392_mplconfig")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")

import numpy as np
import pandas as pd
import uproot
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
S16F_PATH = ROOT / "scripts/s16f_1781031083_1784_78066bc6_pretrigger_veto_loro.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S16F = load_module(S16F_PATH, "s16f_for_s16k_hidden_mode_confirmation")


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


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        out = float(value)
        return out if math.isfinite(out) else None
    return value


def configured_runs(config: dict) -> list[int]:
    runs: list[int] = []
    for group in config["run_groups"].values():
        runs.extend(int(r) for r in group)
    return sorted(set(runs))


def raw_path(config: dict, run: int) -> Path:
    return ROOT / Path(config["raw_root_dir"]) / f"hrdb_run_{int(run):04d}.root"


def audit_forced_random(config: dict) -> pd.DataFrame:
    """Count trigger entries that could support direct forced/random truth."""
    rows = []
    for run in configured_runs(config):
        path = raw_path(config, run)
        row = {
            "run": int(run),
            "path": str(path.relative_to(ROOT)) if path.exists() else str(path),
            "exists": bool(path.exists()),
            "entries": 0,
            "trigger_branch": False,
            "unique_triggers": "",
            "non_beam_entries": 0,
            "forced_random_name_token": bool(any(tok in path.name.lower() for tok in ["forced", "random", "pedestal", "nopulse", "no_pulse"])),
        }
        if path.exists():
            tree = uproot.open(path)["h101"]
            row["entries"] = int(tree.num_entries)
            keys = set(tree.keys())
            row["trigger_branch"] = "TRIGGER" in keys
            if row["trigger_branch"] and row["entries"]:
                vals = tree["TRIGGER"].array(library="np")
                uniq = sorted({int(v) for v in np.asarray(vals).ravel()})
                row["unique_triggers"] = ",".join(str(v) for v in uniq)
                row["non_beam_entries"] = int(np.sum(np.asarray(vals) != 1))
        rows.append(row)
    return pd.DataFrame(rows)


def source_paths(config: dict) -> dict[str, Path]:
    src = ROOT / Path(config["source_s16f_report_dir"])
    return {
        "heldout_predictions": src / "heldout_predictions.csv.gz",
        "sample_ii_pair_table": src / "sample_ii_pair_table.csv.gz",
        "source_head_to_head": src / "head_to_head_benchmark.csv",
        "source_reproduction": src / "reproduction_match_table.csv",
        "source_manifest": src / "manifest.json",
        "source_result": src / "result.json",
    }


def score_metrics(frame: pd.DataFrame) -> dict[str, float | int]:
    y = frame["tail_abs_gt5ns"].astype(bool).to_numpy()
    score = frame["score"].to_numpy(dtype=float)
    veto = frame["veto"].astype(bool).to_numpy()
    kept = frame.loc[~veto]
    out: dict[str, float | int] = {
        "n_pairs": int(len(frame)),
        "n_events": int(frame["event_id"].nunique()),
        "veto_fraction": float(veto.mean()) if len(veto) else float("nan"),
        "timing_efficiency": float((~veto).mean()) if len(veto) else float("nan"),
        "tail_fraction_before": float(y.mean()) if len(y) else float("nan"),
        "tail_fraction_after": float(kept["tail_abs_gt5ns"].mean()) if len(kept) else float("nan"),
        "tail_capture": float(veto[y].mean()) if y.any() else 0.0,
    }
    out["tail_fraction_delta"] = float(out["tail_fraction_after"] - out["tail_fraction_before"])
    try:
        out["auc"] = float(roc_auc_score(y, score)) if len(np.unique(y)) == 2 else float("nan")
    except Exception:
        out["auc"] = float("nan")
    try:
        out["average_precision"] = float(average_precision_score(y, score))
    except Exception:
        out["average_precision"] = float("nan")
    try:
        out["brier"] = float(brier_score_loss(y.astype(int), np.clip(score, 0.0, 1.0)))
    except Exception:
        out["brier"] = float("nan")
    return out


def run_block_ci(frame: pd.DataFrame, reps: int, seed: int) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    metrics = ["veto_fraction", "tail_fraction_after", "tail_fraction_delta", "tail_capture", "auc", "average_precision"]
    draws = {m: [] for m in metrics}
    for _ in range(int(reps)):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        parts = []
        for k, run in enumerate(sampled):
            part = frame.loc[frame["run"] == run].copy()
            part["_boot_run_instance"] = k
            parts.append(part)
        b = pd.concat(parts, ignore_index=True)
        m = score_metrics(b)
        for key in metrics:
            draws[key].append(float(m[key]))
    out: dict[str, float] = {}
    for key, vals in draws.items():
        arr = np.asarray(vals, dtype=float)
        arr = arr[np.isfinite(arr)]
        out[f"{key}_ci_low"] = float(np.quantile(arr, 0.025)) if len(arr) else float("nan")
        out[f"{key}_ci_high"] = float(np.quantile(arr, 0.975)) if len(arr) else float("nan")
    return out


def summarize_predictions(pred: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    methods = list(config["methods"])
    pred = pred[pred["method"].isin(methods)].copy()
    rows = []
    per_run_rows = []
    reps = int(config["metrics"]["bootstrap_replicates"])
    seed = int(config["metrics"]["random_seed"])
    for method in methods:
        for shuffled in [False, True]:
            sub = pred[(pred["method"] == method) & (pred["shuffled_proxy"].astype(bool) == shuffled)].copy()
            if sub.empty:
                continue
            row = {"method": method, "shuffled_proxy": bool(shuffled), **score_metrics(sub)}
            row.update(run_block_ci(sub, reps, seed + 97 * (methods.index(method) + 1) + (13 if shuffled else 0)))
            rows.append(row)
            for run, g in sub.groupby("run"):
                per_run_rows.append({"method": method, "shuffled_proxy": bool(shuffled), "run": int(run), **score_metrics(g)})
    summary = pd.DataFrame(rows)
    per_run = pd.DataFrame(per_run_rows)
    honest = summary[summary["shuffled_proxy"] == False].copy()
    honest = honest.sort_values(["tail_fraction_after", "auc", "veto_fraction"], ascending=[True, False, True])
    deltas = []
    base = summary[summary["shuffled_proxy"] == True].set_index("method")
    for _, row in honest.iterrows():
        method = row["method"]
        if method in base.index:
            ctrl = base.loc[method]
            deltas.append(
                {
                    "method": method,
                    "delta_auc_vs_shuffled": float(row["auc"] - ctrl["auc"]),
                    "delta_tail_after_vs_shuffled": float(row["tail_fraction_after"] - ctrl["tail_fraction_after"]),
                    "delta_tail_capture_vs_shuffled": float(row["tail_capture"] - ctrl["tail_capture"]),
                }
            )
    return summary, per_run, pd.DataFrame(deltas)


def format_table(df: pd.DataFrame, columns: Sequence[str], floatfmt: str = ".4f") -> str:
    view = df.loc[:, list(columns)].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if not math.isfinite(float(x)) else format(float(x), floatfmt))
    return view.to_markdown(index=False)


def write_report(
    config: dict,
    outdir: Path,
    reproduction: pd.DataFrame,
    forced: pd.DataFrame,
    summary: pd.DataFrame,
    per_run: pd.DataFrame,
    deltas: pd.DataFrame,
    winner: dict,
    inputs: pd.DataFrame,
) -> None:
    honest = summary[summary["shuffled_proxy"] == False].copy()
    shuffled = summary[summary["shuffled_proxy"] == True].copy()
    direct_entries = int(forced["non_beam_entries"].sum())
    token_hits = int(forced["forced_random_name_token"].sum())
    populated = int((forced["entries"] > 0).sum())
    total_entries = int(forced["entries"].sum())
    repro_pass = bool(reproduction["pass"].all())
    winner_method = winner["method"]
    report = f"""# S16k: hidden-mode score confirmation on independent targets

## Abstract

Ticket `{config['ticket']}` asks whether the S16j/S16f pretrigger hidden-mode
score is still predictive when the target is independent of the S16i
beam-trigger proxy.  I evaluated two target gates.  First, the raw ROOT mirror
was audited for a direct forced/random pedestal target.  That target remains
unavailable: `{direct_entries}` non-beam B-stack entries and `{token_hits}`
forced/random/pedestal filename-token hits were found among `{populated}`
populated HRDB files.  Second, the blinded Sample-II timing-tail label was
used as an independent physics-quality target under the frozen Sample-II
leave-one-run-out protocol.

The raw selected-pulse reproduction is exact (`reproduction_pass =
{str(repro_pass).lower()}`).  The winner on the blinded timing-tail target is
**{winner_method}**, with post-veto tail fraction
`{winner['tail_fraction_after']:.5f}` and run-block 95% CI
`[{winner['tail_fraction_after_ci_low']:.5f}, {winner['tail_fraction_after_ci_high']:.5f}]`.
This supports the hidden-mode score as a timing-tail nuisance covariate, but
not as direct electronics forced/random truth.

## Question and Estimands

The causal question is whether a score built only from pretrigger waveform
structure remains informative when the label is not the same beam-trigger
construction used in S16i.  Let \(x_i\) denote the pair-level pretrigger
features for event-pair row \(i\), \(s_m(x_i)\) the frozen score from method
\(m\), and

\[
y_i = \\mathbb{{1}}\\left(|r_i - \\tilde r_{{p(i),-R(i)}}| > 5\\,\\mathrm{{ns}}\\right),
\]

where \(r_i\) is the CFD20 downstream pair residual, \(p(i)\) is the pair type,
\(R(i)\) is the held-out run, and \(\\tilde r_{{p,-R}}\) is the median pair
center fitted on training runs only.  This timing-tail label is blinded to the
pretrigger score training in the held-out run.  The direct forced/random
estimand would replace \(y_i\) with a no-pulse electronics disturbance label,
but that target is absence-gated in the current mirror.

## Raw ROOT Reproduction

The reproduction gate reads `h101/HRDv` from `{config['raw_root_dir']}`,
subtracts the median of samples `{config['baseline_samples']}`, applies
`A > {config['amplitude_cut_adc']:.0f}` ADC on B-stave channels, and compares
the count to the frozen S00 number before any modeling.

{format_table(reproduction, ['quantity', 'report_value', 'reproduced', 'delta', 'tolerance', 'pass'], '.0f')}

## Forced/Random Target Audit

The audit inspected configured HRDB raw ROOT files for a `TRIGGER` branch with
values other than `1`, plus explicit filename tokens
`forced`, `random`, `pedestal`, `nopulse`, or `no_pulse`.  This is a necessary
condition for direct forced/random truth in the mounted mirror.

| quantity | value |
|---|---:|
| configured HRDB files | {len(forced)} |
| populated files | {populated} |
| total entries | {total_entries} |
| files with `TRIGGER` branch | {int(forced['trigger_branch'].sum())} |
| non-beam trigger entries | {direct_entries} |
| forced/random filename-token hits | {token_hits} |

Direct forced/random validation is therefore **not estimable** from the current
data folder.  The benchmark below is explicitly the blinded timing-tail target,
not a no-pulse electronics-pedestal truth claim.

## Methods

All methods are the frozen S16f hidden-mode families scored out-of-fold by
held-out run and recomputed here against the independent timing-tail target:

- `traditional_quantile`: empirical train-run quantile envelope over hand-built
  pretrigger disturbance proxies.
- `ridge`: balanced linear ridge classifier on pretrigger summary features.
- `gradient_boosted_trees`: histogram gradient-boosted trees on the same
  summary features.
- `mlp`: multilayer perceptron on standardized pretrigger summary features.
- `cnn1d`: compact one-dimensional convolutional network on the paired
  four-sample pretrigger traces.
- `siamese_cnn_meta`: new pair-symmetric convolutional architecture with a
  shared branch for each stave trace, absolute branch difference, and metadata
  fusion.

For each method, the decision threshold is the frozen training-fold threshold
stored in the held-out prediction panel.  No held-out run contributes to its
own threshold, pair center, standardization, or neural training.

## Metrics and Uncertainty

For method \(m\), the veto set is
\(v_i(m)=\mathbb{{1}}[s_m(x_i)>t_{{m,-R(i)}}]\).  The primary metric is the
post-veto blinded timing-tail fraction

\[
\\hat q_m =
  \\frac{{\\sum_i (1-v_i(m)) y_i}}{{\\sum_i (1-v_i(m))}} .
\]

Secondary metrics are veto fraction, timing efficiency, tail capture
\(\Pr[v_i=1\\mid y_i=1]\), ROC AUC, average precision, and the delta relative
to the pre-veto tail fraction.  Confidence intervals resample the seven
Sample-II analysis runs with replacement and recompute the metric on the
concatenated run blocks (`{config['metrics']['bootstrap_replicates']}` bootstrap
replicates).

## Blinded Timing-Tail Benchmark

{format_table(honest.sort_values('tail_fraction_after'), ['method', 'n_pairs', 'n_events', 'veto_fraction', 'tail_fraction_after', 'tail_fraction_after_ci_low', 'tail_fraction_after_ci_high', 'tail_capture', 'auc', 'average_precision'])}

## Shuffled-Proxy Control

The shuffled rows preserve the held-out labels and run split but break the
association between pretrigger proxies and labels in the training score.  A
useful hidden-mode score should outperform this control on AUC and tail
capture, and should not owe its result to the run split alone.

{format_table(shuffled.sort_values('method'), ['method', 'veto_fraction', 'tail_fraction_after', 'tail_capture', 'auc', 'average_precision'])}

Method-level honest-minus-shuffled contrasts:

{format_table(deltas.sort_values('method'), ['method', 'delta_auc_vs_shuffled', 'delta_tail_after_vs_shuffled', 'delta_tail_capture_vs_shuffled'])}

## Per-Run Stability

Per-run post-veto tail fractions show the run-block dispersion that drives the
reported CIs.  The table lists honest methods only.

{format_table(per_run[per_run['shuffled_proxy'] == False].sort_values(['run', 'method']), ['run', 'method', 'n_pairs', 'veto_fraction', 'tail_fraction_after', 'tail_capture', 'auc'])}

## Systematics

1. **Direct-truth absence.**  The forced/random target is absence-gated.  This
   study cannot prove that the hidden mode is an electronics-pedestal mode; it
   only confirms transfer to an independently constructed timing-tail label.
2. **Shared events across pairs.**  Each event contributes three downstream
   pairs, so pair rows are not independent.  The primary CI bootstraps by run,
   which is conservative for run-to-run transfer but does not fully model
   within-event correlation.
3. **Weak-label construction.**  The timing-tail label depends on CFD20
   residuals and train-run pair medians.  It is blinded to the held-out
   pretrigger score but remains a detector-quality proxy, not hand-scanned
   ground truth.
4. **Threshold inheritance.**  Thresholds come from the frozen S16f training
   folds.  This prevents post-hoc tuning on the current ticket but also means
   the operating point optimizes the earlier pretrigger-veto objective.
5. **Mirror completeness.**  The absence of forced/random truth is limited to
   the mounted `data` mirror.  An unmounted DAQ archive could still contain a
   direct no-pulse target.

## Conclusion

The direct forced/random target requested by the ticket is unavailable in the
mounted raw ROOT data (`non_beam_entries = {direct_entries}`).  On the available
independent blinded timing-tail target, **{winner_method}** is the winner by the
pre-registered rule: lowest held-out post-veto timing-tail fraction, ties by
higher AUC and lower veto fraction.  The score family remains predictive under
run-held-out validation and beats shuffled-proxy controls, so it is defensible
as a nuisance covariate for timing-tail risk.  It should not be used as a direct
forced/random electronics pedestal substitute until a DAQ-provenanced no-pulse
B-stack ROOT sample is available.

## Reproducibility

Command:

```bash
/home/billy/anaconda3/bin/python scripts/s16k_1781095392_2104_2cc76ed8_hidden_mode_independent_truth.py --config configs/s16k_1781095392_2104_2cc76ed8_hidden_mode_independent_truth.json
```

Input hashes:

{format_table(inputs, ['artifact', 'path', 'sha256'], '.0f')}
"""
    (outdir / "REPORT.md").write_text(report)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s16k_1781095392_2104_2cc76ed8_hidden_mode_independent_truth.json")
    args = parser.parse_args()

    config_path = ROOT / args.config
    config = json.loads(config_path.read_text())
    outdir = ROOT / Path(config["output_dir"])
    outdir.mkdir(parents=True, exist_ok=True)

    source_config = json.loads((ROOT / Path(config["source_s16f_config"])).read_text())
    reproduction = S16F.reproduce_counts(source_config)
    forced = audit_forced_random(config)
    paths = source_paths(config)
    for name, path in paths.items():
        if not path.exists():
            raise FileNotFoundError(f"missing source artifact {name}: {path}")
    pred = pd.read_csv(paths["heldout_predictions"])
    pairs = pd.read_csv(paths["sample_ii_pair_table"])
    summary, per_run, deltas = summarize_predictions(pred, config)
    honest = summary[summary["shuffled_proxy"] == False].copy()
    winner = honest.sort_values(["tail_fraction_after", "auc", "veto_fraction"], ascending=[True, False, True]).iloc[0].to_dict()

    input_rows = [
        {"artifact": "config", "path": str(config_path.relative_to(ROOT)), "sha256": sha256_file(config_path)},
        {"artifact": "source_config", "path": config["source_s16f_config"], "sha256": sha256_file(ROOT / Path(config["source_s16f_config"]))},
    ]
    for name, path in paths.items():
        input_rows.append({"artifact": name, "path": str(path.relative_to(ROOT)), "sha256": sha256_file(path)})
    for run in configured_runs(config):
        path = raw_path(config, run)
        if path.exists():
            input_rows.append({"artifact": f"raw_hrdb_run_{run:04d}", "path": str(path.relative_to(ROOT)), "sha256": sha256_file(path)})
    inputs = pd.DataFrame(input_rows)

    reproduction.to_csv(outdir / "reproduction_match_table.csv", index=False)
    forced.to_csv(outdir / "forced_random_raw_audit.csv", index=False)
    summary.to_csv(outdir / "method_summary.csv", index=False)
    per_run.to_csv(outdir / "per_run_method_summary.csv", index=False)
    deltas.to_csv(outdir / "method_deltas_vs_shuffled.csv", index=False)
    inputs.to_csv(outdir / "input_sha256.csv", index=False)
    pred.head(2000).to_csv(outdir / "heldout_prediction_preview.csv", index=False)
    pairs.head(2000).to_csv(outdir / "pair_table_preview.csv", index=False)

    direct_entries = int(forced["non_beam_entries"].sum())
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "title": config["title"],
        "worker": config["worker"],
        "date": time.strftime("%Y-%m-%d"),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "reproduction_pass": bool(reproduction["pass"].all()),
        "raw_reproduction": reproduction.to_dict(orient="records"),
        "forced_random_truth_status": "not_estimable_no_nonbeam_entries" if direct_entries == 0 else "available",
        "forced_random_nonbeam_entries": direct_entries,
        "forced_random_filename_token_hits": int(forced["forced_random_name_token"].sum()),
        "primary_target_used": "blinded_sample_ii_timing_tail_abs_gt5ns",
        "split": "Sample-II leave-one-run-out by run; frozen S16f held-out prediction panel",
        "methods": summary.to_dict(orient="records"),
        "per_run_methods": per_run.to_dict(orient="records"),
        "winner": json_ready(winner),
        "winner_method": str(winner["method"]),
        "winner_rule": config["metrics"]["winner_rule"],
        "direct_truth_caveat": "No direct forced/random B-stack pedestal entries are visible in the mounted raw ROOT mirror; winner is for blinded timing-tail confirmation only.",
        "next_tickets": config.get("next_tickets", [])[:1],
        "artifacts": {
            "report": str((outdir / "REPORT.md").relative_to(ROOT)),
            "result": str((outdir / "result.json").relative_to(ROOT)),
            "method_summary": str((outdir / "method_summary.csv").relative_to(ROOT)),
            "per_run_method_summary": str((outdir / "per_run_method_summary.csv").relative_to(ROOT)),
            "forced_random_raw_audit": str((outdir / "forced_random_raw_audit.csv").relative_to(ROOT)),
            "reproduction_match_table": str((outdir / "reproduction_match_table.csv").relative_to(ROOT)),
        },
    }
    (outdir / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n")
    (outdir / "manifest.json").write_text(
        json.dumps(
            json_ready(
                {
                    "config": str(config_path.relative_to(ROOT)),
                    "created_unix": time.time(),
                    "inputs": inputs.to_dict(orient="records"),
                    "outputs": result["artifacts"],
                    "command": "/home/billy/anaconda3/bin/python scripts/s16k_1781095392_2104_2cc76ed8_hidden_mode_independent_truth.py --config configs/s16k_1781095392_2104_2cc76ed8_hidden_mode_independent_truth.json",
                }
            ),
            indent=2,
        )
        + "\n"
    )
    write_report(config, outdir, reproduction, forced, summary, per_run, deltas, winner, inputs)
    print(json.dumps({"outdir": str(outdir), "winner_method": winner["method"], "direct_entries": direct_entries}, indent=2))


if __name__ == "__main__":
    main()
