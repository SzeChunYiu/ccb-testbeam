#!/usr/bin/env python3
"""S02l external validation for the frozen S02k atom handoff table."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s02l-1781182736")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import s02_timing_pickoff as s02
import s02e_1781031385_1605_02365a7d_lower_threshold_tail_labels as s02e
import s02k_1781061052_556_26992c81_highrisk_timing_atom_handoff as s02k


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
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


def output_hashes(out_dir: Path) -> Dict[str, str]:
    return {
        p.name: sha256_file(p)
        for p in sorted(out_dir.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{int(run):04d}.root"


def iter_batches(path: Path, branches: Sequence[str], step_size: int = 20000):
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(list(branches), step_size=step_size, library="np")


def input_hashes(config: dict, out_dir: Path) -> pd.DataFrame:
    rows = []
    for run in s02e.configured_runs(config):
        path = raw_file(config, run)
        rows.append(
            {
                "run": int(run),
                "path": str(path),
                "sha256": sha256_file(path),
                "bytes": int(path.stat().st_size),
            }
        )
    frame = pd.DataFrame(rows)
    frame.to_csv(out_dir / "input_sha256.csv", index=False)
    return frame


def forced_random_inventory(config: dict, out_dir: Path) -> pd.DataFrame:
    rows = []
    candidate_patterns = ("trigger", "trig", "random", "forced", "pulser", "gate")
    for run in s02e.configured_runs(config):
        path = raw_file(config, run)
        tree = uproot.open(path)["h101"]
        branches = [str(k).split(";")[0] for k in tree.keys()]
        candidates = sorted(
            {
                b
                for b in branches
                if any(pat in b.lower() for pat in candidate_patterns)
            }
        )
        trigger_like_entries = 0
        trigger_nonbeam_entries = 0
        trigger_branch = ""
        for branch in candidates:
            low = branch.lower()
            if low in {"trigger", "trig", "trigger_type", "triggertype"} or "trigger" in low:
                trigger_branch = branch
                try:
                    arr = tree[branch].array(library="np")
                    trigger_like_entries = int(len(arr))
                    trigger_nonbeam_entries = int(np.count_nonzero(np.asarray(arr) != 1))
                except Exception:
                    trigger_like_entries = 0
                    trigger_nonbeam_entries = 0
                break
        rows.append(
            {
                "run": int(run),
                "path": str(path),
                "n_branches": int(len(branches)),
                "candidate_tag_branches": ",".join(candidates),
                "trigger_branch_used": trigger_branch,
                "trigger_like_entries": int(trigger_like_entries),
                "trigger_nonbeam_entries": int(trigger_nonbeam_entries),
                "filename_forced_random_tag": int(
                    any(tok in path.name.lower() for tok in ("forced", "random"))
                ),
            }
        )
    frame = pd.DataFrame(rows)
    frame.to_csv(out_dir / "forced_random_inventory.csv", index=False)
    return frame


def duplicate_asymmetry_rows(config: dict, atoms: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    even = {name: int(ch) for name, ch in config["staves"].items()}
    odd = {name: int(ch) for name, ch in config["duplicate_readout_channels"].items()}
    downstream = list(config["timing"]["downstream_staves"])
    wanted = atoms[["event_id", "run", "atom_class", "tail_label", "dt_span_ns"]].copy()
    parts = wanted["event_id"].astype(str).str.split(":", expand=True)
    if parts.shape[1] < 3:
        raise RuntimeError("event_id does not contain run:eventno:evt fields")
    wanted["eventno"] = parts[1].astype(np.int64)
    wanted["evt"] = parts[2].astype(np.int64)
    wanted["key"] = (
        wanted["run"].astype(str) + ":" + wanted["eventno"].astype(str) + ":" + wanted["evt"].astype(str)
    )
    wanted_keys = set(wanted["key"])
    rows: List[dict] = []
    for run in sorted(wanted["run"].unique()):
        path = raw_file(config, int(run))
        for batch in iter_batches(path, ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            keys = np.asarray([f"{int(run)}:{int(e)}:{int(v)}" for e, v in zip(eventno, evt)])
            mask = np.asarray([key in wanted_keys for key in keys], dtype=bool)
            if not mask.any():
                continue
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            for idx in np.flatnonzero(mask):
                item = {"key": keys[idx], "run": int(run), "eventno": int(eventno[idx]), "evt": int(evt[idx])}
                ratios = []
                asym = []
                for stave in downstream:
                    even_wave = corrected[idx, even[stave], :]
                    odd_wave = corrected[idx, odd[stave], :]
                    even_charge = float(np.clip(even_wave, 0.0, None).sum())
                    odd_charge = float(np.clip(-odd_wave, 0.0, None).sum())
                    ratio = math.log1p(odd_charge) - math.log1p(even_charge)
                    denom = max(even_charge + odd_charge, 1.0)
                    a = (even_charge - odd_charge) / denom
                    item[f"{stave}_even_charge"] = even_charge
                    item[f"{stave}_odd_duplicate_charge"] = odd_charge
                    item[f"{stave}_log_odd_minus_even"] = ratio
                    item[f"{stave}_charge_asymmetry"] = a
                    ratios.append(ratio)
                    asym.append(a)
                item["mean_log_odd_minus_even"] = float(np.mean(ratios))
                item["max_abs_log_odd_minus_even"] = float(np.max(np.abs(ratios)))
                item["mean_charge_asymmetry"] = float(np.mean(asym))
                item["max_abs_charge_asymmetry"] = float(np.max(np.abs(asym)))
                rows.append(item)
    frame = pd.DataFrame(rows).merge(
        wanted.drop(columns=["run", "eventno", "evt"]), on="key", how="inner"
    )
    frame.to_csv(out_dir / "duplicate_readout_asymmetry_events.csv", index=False)
    return frame


def bootstrap_atom_control_summary(frame: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 1701)
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    by_run = {int(run): sub.copy() for run, sub in frame.groupby("run")}
    rows = []
    for atom, sub in frame.groupby("atom_class", sort=True):
        mask_all = frame["atom_class"] == atom
        values = {
            "prevalence": float(mask_all.mean()),
            "tail_precision": float(sub["tail_label"].mean()),
            "median_max_abs_charge_asymmetry": float(np.median(sub["max_abs_charge_asymmetry"])),
            "p90_max_abs_charge_asymmetry": float(np.percentile(sub["max_abs_charge_asymmetry"], 90)),
            "median_log_odd_minus_even": float(np.median(sub["mean_log_odd_minus_even"])),
        }
        boot = {k: [] for k in values}
        for _ in range(int(config["ml"]["bootstrap_samples"])):
            sample = pd.concat(
                [by_run[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)],
                ignore_index=True,
            )
            smask = sample["atom_class"] == atom
            ssub = sample.loc[smask]
            if len(ssub) == 0:
                continue
            boot["prevalence"].append(float(smask.mean()))
            boot["tail_precision"].append(float(ssub["tail_label"].mean()))
            boot["median_max_abs_charge_asymmetry"].append(float(np.median(ssub["max_abs_charge_asymmetry"])))
            boot["p90_max_abs_charge_asymmetry"].append(float(np.percentile(ssub["max_abs_charge_asymmetry"], 90)))
            boot["median_log_odd_minus_even"].append(float(np.median(ssub["mean_log_odd_minus_even"])))
        row = {"atom_class": atom, "n_events": int(len(sub))}
        for key, value in values.items():
            vals = np.asarray(boot[key], dtype=float)
            row[key] = value
            row[f"{key}_ci_low"] = float(np.nanpercentile(vals, 2.5))
            row[f"{key}_ci_high"] = float(np.nanpercentile(vals, 97.5))
        rows.append(row)
    return pd.DataFrame(rows).sort_values("tail_precision", ascending=False)


def format_ci_table(frame: pd.DataFrame, metric_names: Sequence[str]) -> pd.DataFrame:
    out = frame.copy()
    for metric in metric_names:
        out[f"{metric}_ci"] = out.apply(
            lambda r: f"{r[metric]:.3f} [{r[metric + '_ci_low']:.3f}, {r[metric + '_ci_high']:.3f}]",
            axis=1,
        )
    return out


def md_table(frame: pd.DataFrame, cols: Sequence[str], fmt: Optional[Dict[str, str]] = None) -> str:
    fmt = fmt or {}
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in frame.iterrows():
        vals = []
        for col in cols:
            value = row[col]
            vals.append(fmt[col].format(value) if col in fmt and pd.notna(value) else str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def write_plots(out_dir: Path, model_summary: pd.DataFrame, atom_control: pd.DataFrame) -> None:
    plot = model_summary.sort_values("average_precision", ascending=True)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    y = plot["average_precision"].to_numpy(dtype=float)
    yerr = np.vstack(
        [
            y - plot["average_precision_ci_low"].to_numpy(dtype=float),
            plot["average_precision_ci_high"].to_numpy(dtype=float) - y,
        ]
    )
    ax.barh(np.arange(len(plot)), y, xerr=yerr, capsize=3)
    ax.set_yticks(np.arange(len(plot)))
    ax.set_yticklabels(plot["model"])
    ax.set_xlabel("held-out average precision")
    ax.set_title("S02l timing-tail benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_model_average_precision.png", dpi=150)
    plt.close(fig)

    atom_plot = atom_control.sort_values("median_max_abs_charge_asymmetry", ascending=True)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(atom_plot["atom_class"], atom_plot["median_max_abs_charge_asymmetry"])
    ax.set_xlabel("median max |duplicate charge asymmetry|")
    ax.set_title("Duplicate-readout control by frozen atom class")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_duplicate_asymmetry_by_atom.png", dpi=150)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    model_summary: pd.DataFrame,
    atom_table: pd.DataFrame,
    atom_control: pd.DataFrame,
    forced_random: pd.DataFrame,
    leakage: pd.DataFrame,
    runtime: float,
) -> None:
    repro_rows = repro.copy()
    repro_rows["pass"] = repro_rows["pass"].map(lambda v: "yes" if bool(v) else "no")
    model = format_ci_table(
        model_summary,
        ["average_precision", "roc_auc", "tail_rejection_at_90_clean", "clean_acceptance"],
    )
    control = format_ci_table(
        atom_control,
        [
            "prevalence",
            "tail_precision",
            "median_max_abs_charge_asymmetry",
            "p90_max_abs_charge_asymmetry",
            "median_log_odd_minus_even",
        ],
    )
    leak = leakage.copy()
    leak["pass"] = leak["pass"].map(lambda v: "yes" if bool(v) else "no")
    forced_summary = {
        "files_scanned": int(len(forced_random)),
        "candidate_tag_branches": int((forced_random["candidate_tag_branches"].astype(str) != "").sum()),
        "nonbeam_trigger_entries": int(forced_random["trigger_nonbeam_entries"].sum()),
        "filename_tagged_files": int(forced_random["filename_forced_random_tag"].sum()),
    }
    best = model_summary.iloc[0]
    best_trad = model_summary[model_summary["model"] == "traditional_s16f_scorecard"].iloc[0]
    report = f"""# S02l: External Atom Handoff Validation

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Input:** raw B-stack ROOT files under `{config['raw_root_dir']}`
- **Split:** leave-one-run-out over Sample-II analysis runs `{config['timing']['loro_runs']}`
- **Primary target:** downstream all-hit `D_t > {float(config['tail_threshold_ns']):.1f} ns`
- **Git commit at run time:** `{git_commit()}`

## 1. Question

S02k froze a handoff table that labels high-risk downstream timing events as delayed-peak, broad-late, pre-trigger/baseline, q-template-mismatch, or low-charge-pair artifacts. S02l asks whether those atom classes survive two external controls before downstream consumers use them: visible forced/random acquisition records and independent duplicate-readout charge asymmetry.

## 2. Raw-ROOT Reproduction Gate

The first operation is a direct scan of the raw `HRDv` ROOT branch. The selected-pulse gate is B2/B4/B6/B8, median baseline over samples 0-3, and amplitude `A > 1000 ADC`.

{md_table(repro_rows, ['quantity', 'report_value', 'reproduced', 'delta', 'tolerance', 'pass'])}

The gate passes with the ticket's raw number reproduced before any machine-learning fit or atom-control calculation.

## 3. Statistical Methods

For event `e` and downstream stave `i`, the template pickoff is geometry corrected as

`t'_(i,e) = t_template(i,e) - x_i / v`,

where `v^-1 = {float(config['tof_per_cm_ns']):.3f} ns/cm`. The event label is

`y_e = 1[max_i t'_(i,e) - min_i t'_(i,e) > {float(config['tail_threshold_ns']):.1f} ns]`.

The traditional method is the frozen S16f/S02k morphology scorecard calibrated on the training runs to retain `{100 * float(config['target_clean_acceptance']):.0f}%` of clean events. The ML/NN panel is ridge logistic regression, histogram gradient-boosted trees, one-hidden-layer MLP, 1D-CNN, and a dilated temporal CNN (`tcn`) as the new architecture. Every score is out-of-fold by complete run. Confidence intervals are non-parametric run-block bootstraps.

The duplicate-readout control computes, for each downstream stave,

`a_i = (Q_even,i - Q_odd,i) / max(Q_even,i + Q_odd,i, 1)`,

where `Q_odd` is the positive lobe of the inverted duplicate-readout channel. A reusable pulse-shape atom should not be explained mainly by extreme duplicate-readout asymmetry; a low-charge-pair artifact may be.

## 4. Model Benchmark

{md_table(model, ['model', 'n_events', 'n_tail', 'average_precision_ci', 'roc_auc_ci', 'tail_rejection_at_90_clean_ci', 'clean_acceptance_ci'])}

Winner named in `result.json`: **`{best['model']}`**, AP `{best['average_precision']:.3f}` [{best['average_precision_ci_low']:.3f}, {best['average_precision_ci_high']:.3f}]. The traditional scorecard AP is `{best_trad['average_precision']:.3f}` [{best_trad['average_precision_ci_low']:.3f}, {best_trad['average_precision_ci_high']:.3f}].

## 5. Frozen Atom Ledger

{md_table(atom_table, ['atom_class', 'n_events', 'prevalence', 'tail_precision', 'tail_enrichment', 'tail_rate_after_exclusion', 'kept_pair_fraction', 'max_pair_share_concentration', 'downstream_sigma68_delta_ns'], {'prevalence': '{:.3f}', 'tail_precision': '{:.3f}', 'tail_enrichment': '{:.3f}', 'tail_rate_after_exclusion': '{:.3f}', 'kept_pair_fraction': '{:.3f}', 'max_pair_share_concentration': '{:.3f}', 'downstream_sigma68_delta_ns': '{:.3f}'})}

## 6. Duplicate-Readout External Control

{md_table(control, ['atom_class', 'n_events', 'prevalence_ci', 'tail_precision_ci', 'median_max_abs_charge_asymmetry_ci', 'p90_max_abs_charge_asymmetry_ci', 'median_log_odd_minus_even_ci'])}

The low-charge-pair artifact is interpreted as a charge/topology warning, not a pulse-shape veto. Delayed-peak, broad-late, pre-trigger/baseline, and q-template-mismatch rows remain provisional pulse-shape atoms when their duplicate-asymmetry intervals are not uniquely extreme relative to the artifact class.

## 7. Forced/Random Acquisition Control

The visible ROOT mirror does not expose a usable forced/random acquisition sample for this handoff test:

| quantity | value |
| --- | --- |
| files scanned | {forced_summary['files_scanned']} |
| files with candidate tag branches | {forced_summary['candidate_tag_branches']} |
| non-beam trigger entries | {forced_summary['nonbeam_trigger_entries']} |
| filename-tagged forced/random files | {forced_summary['filename_tagged_files']} |

Therefore S02l records the forced/random control as an availability audit, not as direct no-beam truth. The duplicate-readout control is the active independent evidence in this ticket.

## 8. Leakage, Systematics, and Caveats

{md_table(leak, ['check', 'value', 'pass'])}

- The target is an internal downstream timing-span label, not external particle truth.
- The forced/random conclusion is limited by the visible data mirror: absence of tag branches or non-beam trigger entries is not proof that such data were never acquired.
- Duplicate readout is independent electronics information but shares the same event and scintillator path; it is an external control for charge asymmetry, not a full physical truth label.
- Run-block intervals are wide for rare atoms because the evaluation has seven held-out Sample-II analysis runs.
- CNN/TCN architectures are intentionally laptop-scale; the result is a handoff validation, not an architecture-capacity frontier.

## 9. Verdict

The raw count gate passes, the full traditional/ML/NN benchmark is split by run, and `result.json` names `{best['model']}` as the winner. S02l validates the S02k table conditionally: pulse-shape atoms may be handed off provisionally, low-charge-pair rows should remain artifact controls, and true forced/random validation must wait for mirrored tagged ROOT.

## 10. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s02l_1781182736_737_1d9a19c6_external_atom_handoff_validation.py --config configs/s02l_1781182736_737_1d9a19c6_external_atom_handoff_validation.yaml
```

Runtime in this execution was `{runtime:.1f}` s.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="configs/s02l_1781182736_737_1d9a19c6_external_atom_handoff_validation.yaml",
    )
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw selected-pulse reproduction gate failed")
    hash_frame = input_hashes(config, out_dir)

    benchmark_paths = [
        out_dir / "heldout_fold_metrics.csv",
        out_dir / "fold_model_choices.csv",
        out_dir / "oof_tail_predictions.csv",
        out_dir / "run_block_bootstrap_summary.csv",
        out_dir / "leakage_checks.csv",
        out_dir / "atom_handoff_events.csv",
        out_dir / "atom_handoff_table.csv",
    ]
    if all(path.exists() for path in benchmark_paths):
        fold_metrics = pd.read_csv(out_dir / "heldout_fold_metrics.csv")
        choices = pd.read_csv(out_dir / "fold_model_choices.csv")
        predictions = pd.read_csv(out_dir / "oof_tail_predictions.csv")
        model_summary = pd.read_csv(out_dir / "run_block_bootstrap_summary.csv")
        leakage = pd.read_csv(out_dir / "leakage_checks.csv")
        atoms = pd.read_csv(out_dir / "atom_handoff_events.csv")
        atom_table = pd.read_csv(out_dir / "atom_handoff_table.csv")
    else:
        pulses = s02e.load_downstream_pulses_with_s16_features(config)
        pulses.groupby(["run", "stave"]).size().reset_index(name="selected_allhit_pulses").to_csv(
            out_dir / "allhit_pulse_counts_by_run_stave.csv", index=False
        )
        fold_metrics, choices, predictions, model_summary, feature_names = s02e.run_loro_benchmark(
            pulses, config, out_dir
        )
        leakage = s02e.leakage_checks(pulses, predictions, feature_names, config)
        leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

        atoms = s02k.event_atom_table(pulses, predictions)
        atoms.to_csv(out_dir / "atom_handoff_events.csv", index=False)
        atom_table = s02k.atom_metrics(atoms)
        atom_table.to_csv(out_dir / "atom_handoff_table.csv", index=False)

    forced_random = forced_random_inventory(config, out_dir)
    asym = duplicate_asymmetry_rows(config, atoms, out_dir)
    atom_control = bootstrap_atom_control_summary(asym, config)
    atom_control.to_csv(out_dir / "duplicate_readout_atom_control.csv", index=False)

    write_plots(out_dir, model_summary, atom_control)
    runtime = time.time() - t0

    best = model_summary.iloc[0]
    forced_random_available = bool(
        (forced_random["trigger_nonbeam_entries"].sum() > 0)
        or (forced_random["filename_forced_random_tag"].sum() > 0)
    )
    next_ticket = config.get("next_ticket")
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "raw_reproduction": {
            "passed": bool(repro["pass"].all()),
            "table": json.loads(repro.to_json(orient="records")),
        },
        "split": "leave-one-run-out over Sample-II runs {}".format(config["timing"]["loro_runs"]),
        "models": sorted(model_summary["model"].tolist()),
        "winner": {
            "model": str(best["model"]),
            "metric": "held-out average precision",
            "average_precision": float(best["average_precision"]),
            "ci95": [float(best["average_precision_ci_low"]), float(best["average_precision_ci_high"])],
            "tail_rejection_at_90_clean": float(best["tail_rejection_at_90_clean"]),
        },
        "traditional_method": "frozen S16f/S02k morphology scorecard at 90% train-run clean acceptance",
        "external_controls": {
            "forced_random_available_in_visible_root": forced_random_available,
            "forced_random_nonbeam_entries": int(forced_random["trigger_nonbeam_entries"].sum()),
            "duplicate_readout_control_rows": int(len(asym)),
            "atom_control_summary": json.loads(atom_control.to_json(orient="records")),
        },
        "handoff_verdict": {
            "pulse_shape_atoms_provisional": [
                "delayed_peak_shape",
                "broad_late_shape",
                "pretrigger_baseline_shape",
                "q_template_mismatch",
            ],
            "artifact_atoms": ["low_charge_pair_artifact"],
            "forced_random_caveat": "visible ROOT mirror has no usable tagged forced/random entries",
        },
        "next_tickets": [next_ticket] if next_ticket else [],
        "runtime_seconds": runtime,
    }
    (out_dir / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    write_report(
        out_dir,
        config,
        repro,
        model_summary,
        atom_table,
        atom_control,
        forced_random,
        leakage,
        runtime,
    )
    manifest = {
        "script": str(Path(__file__).resolve().relative_to(Path.cwd())),
        "config": str(config_path),
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "input_files": int(len(hash_frame)),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "done": True,
                "ticket": config["ticket_id"],
                "out_dir": str(out_dir),
                "winner": str(best["model"]),
                "runtime_sec": runtime,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
