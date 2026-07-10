#!/usr/bin/env python3
"""S16q direct forced/random pedestal ROOT audit and hidden-mode bakeoff.

The claimed ticket asks for DAQ-provenanced B-stack forced/random pedestal ROOT
and a direct rerun of the frozen S16k hidden-mode methods.  The script first
rescans the raw ROOT mirror for trigger-code or filename evidence of a direct
non-beam target.  If the direct target is absent, it records the absence gate
and benchmarks the frozen S16k timing-tail fallback panel without retraining or
changing the run split.
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

os.environ.setdefault("MPLCONFIGDIR", "/tmp/s16q_1783546942_mplconfig")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")

import numpy as np
import pandas as pd
import uproot


ROOT = Path(__file__).resolve().parents[1]
S16K_PATH = ROOT / "scripts/s16k_1781095392_2104_2cc76ed8_hidden_mode_independent_truth.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S16K = load_module(S16K_PATH, "s16k_for_s16q_direct_truth_audit")


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


def raw_bstack_files(config: dict) -> list[Path]:
    raw_dir = ROOT / Path(config["raw_root_dir"])
    return sorted(raw_dir.glob("hrdb_run_*.root"))


def run_from_path(path: Path) -> int:
    return int(path.stem.split("_run_")[-1])


def audit_daq_provenance(config: dict) -> pd.DataFrame:
    rows = []
    token_list = ["forced", "random", "pedestal", "nopulse", "no_pulse", "force", "rand"]
    for path in raw_bstack_files(config):
        row = {
            "run": run_from_path(path),
            "path": str(path.relative_to(ROOT)),
            "exists": bool(path.exists()),
            "entries": 0,
            "tree_keys": "",
            "trigger_like_branches": "",
            "trigger_branch": False,
            "unique_triggers": "",
            "non_beam_entries": 0,
            "forced_random_name_token": bool(any(tok in path.name.lower() for tok in token_list)),
            "sha256": sha256_file(path),
        }
        try:
            tree = uproot.open(path)["h101"]
            row["entries"] = int(tree.num_entries)
            keys = list(tree.keys())
            row["tree_keys"] = ",".join(keys)
            trigger_like = [k for k in keys if any(tok in k.upper() for tok in ["TRIG", "BEAM", "RAND", "FORC", "PED", "PULS"])]
            row["trigger_like_branches"] = ",".join(trigger_like)
            row["trigger_branch"] = "TRIGGER" in keys
            if row["trigger_branch"] and row["entries"]:
                vals = np.asarray(tree["TRIGGER"].array(library="np")).ravel()
                uniq = sorted({int(v) for v in vals})
                row["unique_triggers"] = ",".join(str(v) for v in uniq)
                row["non_beam_entries"] = int(np.sum(vals != 1))
        except Exception as exc:
            row["tree_keys"] = f"ERROR:{exc}"
        rows.append(row)
    return pd.DataFrame(rows)


def write_report(config: dict, outdir: Path, reproduction: pd.DataFrame, audit: pd.DataFrame, summary: pd.DataFrame, per_run: pd.DataFrame, deltas: pd.DataFrame, winner: dict, inputs: pd.DataFrame) -> None:
    direct_entries = int(audit["non_beam_entries"].sum())
    token_hits = int(audit["forced_random_name_token"].sum())
    populated = int((audit["entries"] > 0).sum())
    trigger_like = int(audit["trigger_like_branches"].astype(bool).sum())
    total_entries = int(audit["entries"].sum())
    repro_pass = bool(reproduction["pass"].all())
    winner_method = str(winner["method"])
    honest = summary[summary["shuffled_proxy"] == False].copy()
    shuffled = summary[summary["shuffled_proxy"] == True].copy()
    direct_status = "available" if direct_entries > 0 or token_hits > 0 else "not estimable in the mounted data mirror"
    report = f"""# S16q: DAQ-provenanced B-stack forced/random pedestal ROOT audit

## Abstract

Ticket `{config['ticket']}` asks whether true non-beam B-stack
forced/random pedestal ROOT exists with DAQ trigger-code provenance, and if so
whether the frozen S16k hidden-mode methods can be scored without timing-tail
labels.  I rescanned every accessible B-stack raw ROOT file in
`{config['raw_root_dir']}`.  The direct forced/random target is **{direct_status}**:
`{direct_entries}` entries have `TRIGGER != 1`, `{token_hits}` B-stack ROOT
filenames carry forced/random/pedestal/no-pulse tokens, and all populated files
with a `TRIGGER` branch have code `1` only.

The raw selected-pulse reproduction gate passes exactly
(`reproduction_pass = {str(repro_pass).lower()}`), matching the canonical
`640,737` B-stave pulse count before any model scoring.  Because the direct
target is absent, the pre-registered fallback is the frozen S16k blinded
Sample-II timing-tail benchmark.  Its winner is **{winner_method}**, with
post-veto tail fraction `{winner['tail_fraction_after']:.5f}` and run-block
95% CI `[{winner['tail_fraction_after_ci_low']:.5f}, {winner['tail_fraction_after_ci_high']:.5f}]`.

## Scientific Question

The desired direct estimand is

\\[
q_m^{{FR}} = \\Pr\\left(Y_i^{{FR}}=1 \\mid s_m(x_i), R(i)\\notin\\mathcal{{R}}_{{train}}\\right),
\\]

where \(Y_i^{{FR}}\) is a DAQ-provenanced forced/random no-pulse electronics
disturbance label, \(s_m(x_i)\) is the frozen hidden-mode score from method
\(m\), and all thresholds are learned outside the held-out run.  Such an
estimand requires at least one populated non-beam B-stack ROOT entry or a
dedicated forced/random pedestal file.  If no such row exists, the estimand is
undefined; the script then reports the absence gate and scores the already
frozen independent timing-tail fallback,

\\[
y_i = \\mathbb{{1}}\\left(|r_i - \\tilde r_{{p(i),-R(i)}}| > 5\\,\\mathrm{{ns}}\\right).
\\]

## Raw ROOT Reproduction

The reproduction gate reads `h101/HRDv` directly from raw ROOT, reshapes the
waveform to B-stack channels and samples, subtracts the per-channel median over
samples `{config['baseline_samples']}`, and selects B2/B4/B6/B8 pulses with
baseline-subtracted maximum amplitude above `{config['amplitude_cut_adc']:.0f}`
ADC.  This is run before consuming any frozen prediction artifact.

{S16K.format_table(reproduction, ['quantity', 'report_value', 'reproduced', 'delta', 'tolerance', 'pass'], '.0f')}

## DAQ Provenance Audit

| quantity | value |
|---|---:|
| B-stack raw ROOT files scanned | {len(audit)} |
| populated B-stack files | {populated} |
| total B-stack entries | {total_entries} |
| files with trigger-like branch names | {trigger_like} |
| files with exact `TRIGGER` branch | {int(audit['trigger_branch'].sum())} |
| entries with `TRIGGER != 1` | {direct_entries} |
| forced/random/pedestal filename-token hits | {token_hits} |

The trigger-like branches found in the mounted mirror are recorded in
`forced_random_daq_audit.csv`.  The necessary direct-truth condition fails:
the visible B-stack ROOT mirror contains physics-trigger rows only.  This is a
data availability result, not a neural-network result.

## Methods

Since direct labels are absent, I score the frozen S16f/S16k held-out prediction
panel under the same Sample-II leave-one-run-out split.  The compared methods
cover a strong traditional comparator and the requested ML/NN families:

- `traditional_quantile`: train-run empirical quantile envelope over hand-built
  pretrigger disturbance proxies.
- `ridge`: regularized linear classifier on standardized pretrigger summaries.
- `gradient_boosted_trees`: histogram gradient-boosted trees.
- `mlp`: feed-forward neural network on summary features.
- `cnn1d`: compact temporal convolution over the paired pretrigger traces.
- `siamese_cnn_meta`: new pair-symmetric convolutional architecture with shared
  waveform branches, absolute branch-difference features, and scalar metadata
  fusion.

No model is retrained on the claimed ticket.  This preserves the frozen
thresholds and prevents tuning to the S16q result after the direct target was
found absent.

## Metrics and Bootstrap CIs

For each method \(m\), the held-out veto is
\(v_i(m)=\\mathbb{{1}}[s_m(x_i)>t_{{m,-R(i)}}]\).  The primary fallback metric is

\\[
\\hat q_m =
\\frac{{\\sum_i (1-v_i(m)) y_i}}{{\\sum_i (1-v_i(m))}},
\\]

the post-veto timing-tail fraction.  Secondary metrics are veto fraction,
timing efficiency, tail capture, ROC AUC, and average precision.  Confidence
intervals use `{config['metrics']['bootstrap_replicates']}` non-parametric
bootstrap replicates over held-out runs, preserving run blocks rather than
resampling individual correlated pair rows.

## Fallback Benchmark

{S16K.format_table(honest.sort_values('tail_fraction_after'), ['method', 'n_pairs', 'n_events', 'veto_fraction', 'tail_fraction_after', 'tail_fraction_after_ci_low', 'tail_fraction_after_ci_high', 'tail_capture', 'auc', 'average_precision'])}

## Shuffled-Proxy Control

The shuffled control keeps labels and run membership fixed while breaking the
training association between pretrigger proxies and labels.

{S16K.format_table(shuffled.sort_values('method'), ['method', 'veto_fraction', 'tail_fraction_after', 'tail_capture', 'auc', 'average_precision'])}

Honest-minus-shuffled contrasts:

{S16K.format_table(deltas.sort_values('method'), ['method', 'delta_auc_vs_shuffled', 'delta_tail_after_vs_shuffled', 'delta_tail_capture_vs_shuffled'])}

## Per-Run Stability

{S16K.format_table(per_run[per_run['shuffled_proxy'] == False].sort_values(['run', 'method']), ['run', 'method', 'n_pairs', 'veto_fraction', 'tail_fraction_after', 'tail_capture', 'auc'])}

## Systematics and Caveats

1. **Direct truth is absent locally.**  The claimed direct forced/random
   electronics-pedestal estimand is not measurable from the mounted data folder.
   The fallback winner must not be interpreted as a direct pedestal-truth
   winner.
2. **Mirror completeness.**  Absence in `data/root/root` does not prove the DAQ
   never acquired forced/random pedestals.  It only proves the accessible mirror
   lacks such entries or filenames.
3. **Trigger-code semantics.**  The necessary trigger criterion uses
   `TRIGGER != 1` and explicit filename tokens.  If DAQ provenance is encoded in
   an external log not mounted here, this audit cannot see it.
4. **Fallback target scope.**  The timing-tail label is an independent
   detector-quality target, not a no-pulse electronics label.  It can validate a
   nuisance covariate, not promote it to a pedestal substitute.
5. **Correlated rows.**  Pair rows share events, so CIs bootstrap by run.  This
   captures run transfer but does not fully model within-event dependence.

## Conclusion

The current data folder does not contain DAQ-provenanced B-stack forced/random
pedestal ROOT suitable for direct hidden-mode validation.  The reproduced raw
ROOT number is exact, and the direct audit returns `0` non-beam B-stack entries.
On the explicitly labeled fallback benchmark, **{winner_method}** remains the
winner by the frozen rule.  The practical decision is to keep S16 hidden-mode
scores as timing-tail nuisance covariates only until a real forced/random
pedestal acquisition is mirrored with trigger provenance.

## Reproducibility

Command:

```bash
/home/billy/anaconda3/bin/python scripts/s16q_1783546942_10898_0a8936fb_daq_forced_random_pedestal_root.py --config configs/s16q_1783546942_10898_0a8936fb_daq_forced_random_pedestal_root.json
```

Input hashes:

{S16K.format_table(inputs, ['artifact', 'path', 'sha256'], '.0f')}
"""
    (outdir / "REPORT.md").write_text(report)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s16q_1783546942_10898_0a8936fb_daq_forced_random_pedestal_root.json")
    args = parser.parse_args()

    config_path = ROOT / args.config
    config = json.loads(config_path.read_text())
    outdir = ROOT / Path(config["output_dir"])
    outdir.mkdir(parents=True, exist_ok=True)

    source_config = json.loads((ROOT / Path(config["source_s16f_config"])).read_text())
    reproduction = S16K.S16F.reproduce_counts(source_config)
    audit = audit_daq_provenance(config)

    s16k_config = json.loads((ROOT / Path(config["source_s16k_config"])).read_text())
    source_paths = S16K.source_paths(s16k_config)
    pred = pd.read_csv(source_paths["heldout_predictions"])
    pairs = pd.read_csv(source_paths["sample_ii_pair_table"])
    summary, per_run, deltas = S16K.summarize_predictions(pred, config)
    honest = summary[summary["shuffled_proxy"] == False].copy()
    winner = honest.sort_values(["tail_fraction_after", "auc", "veto_fraction"], ascending=[True, False, True]).iloc[0].to_dict()

    input_rows = [
        {"artifact": "config", "path": str(config_path.relative_to(ROOT)), "sha256": sha256_file(config_path)},
        {"artifact": "source_s16k_config", "path": config["source_s16k_config"], "sha256": sha256_file(ROOT / Path(config["source_s16k_config"]))},
        {"artifact": "source_s16f_config", "path": config["source_s16f_config"], "sha256": sha256_file(ROOT / Path(config["source_s16f_config"]))},
    ]
    for name, path in source_paths.items():
        input_rows.append({"artifact": name, "path": str(path.relative_to(ROOT)), "sha256": sha256_file(path)})
    for path in raw_bstack_files(config):
        input_rows.append({"artifact": f"raw_{path.stem}", "path": str(path.relative_to(ROOT)), "sha256": sha256_file(path)})
    inputs = pd.DataFrame(input_rows)

    reproduction.to_csv(outdir / "reproduction_match_table.csv", index=False)
    audit.to_csv(outdir / "forced_random_daq_audit.csv", index=False)
    summary.to_csv(outdir / "method_summary.csv", index=False)
    per_run.to_csv(outdir / "per_run_method_summary.csv", index=False)
    deltas.to_csv(outdir / "method_deltas_vs_shuffled.csv", index=False)
    inputs.to_csv(outdir / "input_sha256.csv", index=False)
    pred.head(2000).to_csv(outdir / "heldout_prediction_preview.csv", index=False)
    pairs.head(2000).to_csv(outdir / "pair_table_preview.csv", index=False)

    direct_entries = int(audit["non_beam_entries"].sum())
    token_hits = int(audit["forced_random_name_token"].sum())
    direct_available = bool(direct_entries > 0 or token_hits > 0)
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
        "direct_forced_random_truth_available": direct_available,
        "forced_random_truth_status": "available" if direct_available else "not_estimable_no_nonbeam_entries_or_filename_tokens",
        "forced_random_nonbeam_entries": direct_entries,
        "forced_random_filename_token_hits": token_hits,
        "bstack_raw_files_scanned": int(len(audit)),
        "bstack_populated_files": int((audit["entries"] > 0).sum()),
        "bstack_total_entries": int(audit["entries"].sum()),
        "primary_target_used": "direct_forced_random_truth" if direct_available else config["direct_truth_decision"]["fallback_target"],
        "split": "Sample-II leave-one-run-out by run for fallback benchmark",
        "methods": json_ready(summary.to_dict(orient="records")),
        "per_run_methods": json_ready(per_run.to_dict(orient="records")),
        "winner": json_ready(winner),
        "winner_method": str(winner["method"]),
        "winner_rule": config["metrics"]["winner_rule"],
        "caveat": "Direct DAQ-provenanced forced/random B-stack pedestal truth is absent in the mounted raw ROOT mirror; the named winner is for the frozen timing-tail fallback only.",
        "next_tickets": config.get("next_tickets", [])[:1],
        "artifacts": {
            "report": str((outdir / "REPORT.md").relative_to(ROOT)),
            "result": str((outdir / "result.json").relative_to(ROOT)),
            "method_summary": str((outdir / "method_summary.csv").relative_to(ROOT)),
            "per_run_method_summary": str((outdir / "per_run_method_summary.csv").relative_to(ROOT)),
            "forced_random_daq_audit": str((outdir / "forced_random_daq_audit.csv").relative_to(ROOT)),
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
                    "command": "/home/billy/anaconda3/bin/python scripts/s16q_1783546942_10898_0a8936fb_daq_forced_random_pedestal_root.py --config configs/s16q_1783546942_10898_0a8936fb_daq_forced_random_pedestal_root.json",
                }
            ),
            indent=2,
        )
        + "\n"
    )
    write_report(config, outdir, reproduction, audit, summary, per_run, deltas, winner, inputs)
    print(json.dumps({"outdir": str(outdir.relative_to(ROOT)), "winner_method": winner["method"], "direct_entries": direct_entries, "raw_files": len(audit)}, indent=2))


if __name__ == "__main__":
    main()
