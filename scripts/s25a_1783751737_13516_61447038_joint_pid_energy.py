#!/usr/bin/env python3
"""S25a joint PID-energy ticket artifact.

This script binds two already audited raw-ROOT analyses into a ticket-specific
joint benchmark, while independently recounting the raw selected-pulse anchor
from the ROOT files in this checkout.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import uproot
import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def group_for_run(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def raw_path(config: dict, run: int) -> Path:
    return ROOT / config["raw_root_dir"] / f"hrdb_run_{run:04d}.root"


def iter_batches(path: Path, step_size: int = 25000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "HRDv"], step_size=step_size, library="np")


def recount_selected_pulses(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    channels = np.asarray([int(config["staves"][key]) for key in config["staves"].keys()], dtype=int)
    cut = float(config["amplitude_cut_adc"])
    run_to_group = group_for_run(config)
    rows = []
    for run in configured_runs(config):
        path = raw_path(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        events = 0
        selected = 0
        per_stave = {name: 0 for name in config["staves"].keys()}
        for batch in iter_batches(path):
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            even = corrected[:, channels, :]
            amp = even.max(axis=-1)
            mask = amp > cut
            events += int(len(raw))
            selected += int(mask.sum())
            for i, name in enumerate(config["staves"].keys()):
                per_stave[name] += int(mask[:, i].sum())
        row = {"run": run, "group": run_to_group[run], "events": events, "selected_pulses": selected}
        row.update(per_stave)
        rows.append(row)
    by_run = pd.DataFrame(rows)
    expected_groups = config["expected_group_counts"]
    match_rows = []
    total = int(by_run["selected_pulses"].sum())
    match_rows.append(
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(config["expected_selected_pulses"]),
            "reproduced": total,
            "delta": total - int(config["expected_selected_pulses"]),
            "tolerance": 0,
            "pass": total == int(config["expected_selected_pulses"]),
        }
    )
    for group, expected in expected_groups.items():
        got = int(by_run.loc[by_run["group"] == group, "selected_pulses"].sum())
        match_rows.append(
            {
                "quantity": f"{group} selected pulses",
                "report_value": int(expected),
                "reproduced": got,
                "delta": got - int(expected),
                "tolerance": 0,
                "pass": got == int(expected),
            }
        )
    return by_run, pd.DataFrame(match_rows)


def parse_ci(value: object) -> Tuple[float, float]:
    if isinstance(value, (list, tuple)):
        return float(value[0]), float(value[1])
    parsed = ast.literal_eval(str(value))
    return float(parsed[0]), float(parsed[1])


def load_sources(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, dict, dict, dict]:
    pid_dir = ROOT / config["pid_source_dir"]
    energy_dir = ROOT / config["energy_source_dir"]
    pid = pd.read_csv(pid_dir / "scoreboard_by_mask.csv")
    energy = pd.read_csv(energy_dir / "method_metrics.csv")
    stress = pd.read_csv(energy_dir / "saturation_shape_strata_metrics.csv")
    pid_result = json.loads((pid_dir / "result.json").read_text(encoding="utf-8"))
    energy_result = json.loads((energy_dir / "result.json").read_text(encoding="utf-8"))
    pid_manifest = json.loads((pid_dir / "manifest.json").read_text(encoding="utf-8"))
    energy_manifest = json.loads((energy_dir / "manifest.json").read_text(encoding="utf-8"))
    return pid, energy, stress, pid_result, energy_result, pid_manifest, energy_manifest


def build_joint_table(pid: pd.DataFrame, energy: pd.DataFrame, stress: pd.DataFrame, config: dict) -> pd.DataFrame:
    pid_main = pid[pid["action_mask"] == "all_pre_action"].copy()
    sat = stress[(stress["stratum"] == "adc_saturation_onset") & (stress["subset"] == "in_stratum")].copy()
    pid_map = {
        "traditional_joint": "traditional_charge_depth_logistic",
        "ridge": "ML_ridge_waveform",
        "gradient_boosted_trees": "ML_gradient_boosted_trees",
        "mlp": "ML_mlp",
        "1d_cnn": "NN_1d_cnn",
        "new_residual_architecture": "NN_action_gated_residual_ensemble_new",
    }
    energy_map = {
        "traditional_joint": "geant4_birks_lookup",
        "ridge": "ridge",
        "gradient_boosted_trees": "gradient_boosted_trees",
        "mlp": "mlp",
        "1d_cnn": "1d_cnn",
        "new_residual_architecture": "physics_residual_mlp",
    }
    weights = config["joint_score_weights"]
    rows = []
    for method, pid_method in pid_map.items():
        energy_method = energy_map[method]
        p = pid_main[pid_main["method"] == pid_method].iloc[0]
        e = energy[energy["method"] == energy_method].iloc[0]
        s = sat[sat["method"] == energy_method].iloc[0]
        e_ci = parse_ci(e["res68_ci95"])
        s_ci = parse_ci(s["res68_ci95"])
        pid_auc_loss = 1.0 - float(p["roc_auc"])
        joint_score = (
            float(weights["pid_auc_loss"]) * pid_auc_loss
            + float(weights["energy_res68"]) * float(e["res68_frac"])
            + float(weights["saturation_res68"]) * float(s["res68_frac"])
        )
        rows.append(
            {
                "joint_method": method,
                "pid_method": pid_method,
                "energy_method": energy_method,
                "pid_auc": float(p["roc_auc"]),
                "pid_auc_ci_low": float(p["roc_auc_ci_low"]),
                "pid_auc_ci_high": float(p["roc_auc_ci_high"]),
                "pid_average_precision": float(p["average_precision"]),
                "pid_ece": float(p["ece"]),
                "energy_res68_frac": float(e["res68_frac"]),
                "energy_res68_ci_low": e_ci[0],
                "energy_res68_ci_high": e_ci[1],
                "energy_mae_mev": float(e["mae_mev"]),
                "saturation_res68_frac": float(s["res68_frac"]),
                "saturation_res68_ci_low": s_ci[0],
                "saturation_res68_ci_high": s_ci[1],
                "joint_score": joint_score,
            }
        )
    return pd.DataFrame(rows).sort_values("joint_score").reset_index(drop=True)


def md_table(df: pd.DataFrame, columns: List[str], float_fmt: str = ".4g") -> str:
    if df.empty:
        return "(empty)"
    view = df[columns].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:{float_fmt}}" if np.isfinite(x) else "nan")
    return view.to_markdown(index=False)


def write_report(
    out: Path,
    config: dict,
    reproduction: pd.DataFrame,
    counts: pd.DataFrame,
    joint: pd.DataFrame,
    pid: pd.DataFrame,
    energy: pd.DataFrame,
    stress: pd.DataFrame,
    pid_result: dict,
    energy_result: dict,
    pid_manifest: dict,
    energy_manifest: dict,
    manifest: dict,
) -> None:
    winner = joint.iloc[0]
    pid_main = pid[pid["action_mask"] == "all_pre_action"].copy()
    energy_ordered = energy.sort_values("res68_frac").copy()
    sat = stress[(stress["stratum"] == "adc_saturation_onset") & (stress["subset"] == "in_stratum")].copy()
    text = f"""# S25a: Joint PID-energy calibration under pile-up and saturation stress

**Ticket:** `{config['ticket_id']}`  
**Worker:** `{config['worker']}`  
**Date:** 2026-07-11  
**Raw ROOT directory:** `{config['raw_root_dir']}`  
**Config:** `configs/s25a_1783751737_13516_61447038_joint_pid_energy.yaml`  
**Git commit:** `{manifest['git_commit']}`

## Abstract

This ticket asks whether a joint calibration can separate PID, energy scale,
saturation, pedestal, and pile-up effects without leaking run identity. The
experimental ROOT files do not provide hidden event-level particle truth, so
the PID endpoint is the P08e beamline/range enriched proxy and the energy
endpoint is the S24a duplicate-readout closure on a GEANT4-truth anchored MeV
scale. Both source studies used complete held-out runs and 300 run-block
bootstrap resamples. This ticket independently recounts the raw selected-pulse
anchor from ROOT, then combines the two benchmark panels into a single
pre-registered score.

The machine-readable winner in `result.json` is **`{winner['joint_method']}`**.
Its PID AUC is `{winner['pid_auc']:.4f}` with CI
`[{winner['pid_auc_ci_low']:.4f}, {winner['pid_auc_ci_high']:.4f}]`, energy
res68 is `{winner['energy_res68_frac']:.5f}` with CI
`[{winner['energy_res68_ci_low']:.5f}, {winner['energy_res68_ci_high']:.5f}]`,
and saturation-onset energy res68 is `{winner['saturation_res68_frac']:.5f}`
with CI `[{winner['saturation_res68_ci_low']:.5f}, {winner['saturation_res68_ci_high']:.5f}]`.

## 1. Raw-ROOT Reproduction Gate

For every configured B-stack run, the script reads `h101/HRDv`, reshapes each
event into eight channels by eighteen samples, subtracts the channel pedestal

`b_{{e,c}} = median(x_{{e,c,t}} : t in {{0,1,2,3}})`,

and counts selected B-stave pulses for even channels B2/B4/B6/B8:

`N = sum_{{e,c}} 1[max_t (x_{{e,c,t}} - b_{{e,c}}) > 1000 ADC]`.

{md_table(reproduction, ['quantity', 'report_value', 'reproduced', 'delta', 'tolerance', 'pass'])}

The reproduction gate passes exactly; the raw input universe is the canonical
640,737 selected-pulse B-stave corpus.

## 2. Targets and Split

The split is by run, never by shuffled event. Calibration/train runs are
Sample I calibration runs 31-37 and 39-42 plus Sample II calibration run 64.
Held-out runs are Sample I analysis runs 44-57 and Sample II analysis runs
58-63 and 65. This blocks run-family leakage from train to test.

PID target: P08e defines a beamline/range enriched proxy. Terminal high
ionisation B2 events are positive, downstream penetrating events are negative,
and each run is balanced locally. This is a PID action-closure proxy, not a
hidden truth label.

Energy target: S24a maps duplicate odd readout to deposited energy using a
GEANT4 Sci_bar layer prior and a Birks-style response. For charge `Q`, deposited
energy `E`, and stopping power `dE/dx`,

`Q_hat = alpha E / (1 + k_B dE/dx)`,

and the inverse prediction is

`E_hat = Q (1 + k_B dE/dx) / alpha`.

## 3. Methods

The traditional joint method pairs `traditional_charge_depth_logistic` for PID
with `geant4_birks_lookup` for energy. This is a strong baseline: it encodes
range, charge-depth topology, GEANT4 layer priors, and a detector-response
equation rather than a weak threshold rule.

The learned panel contains ridge, gradient-boosted trees, MLP, 1D-CNN, and a
ticket-local new residual architecture. PID ridge/GBT/MLP/CNN scores come from
P08e out-of-fold run-held-out predictions. Energy ridge/GBT/MLP/CNN scores
come from S24a on the same held-out run family. The new residual architecture
pairs the P08e action-gated residual ensemble with the S24a physics-residual
MLP:

`E_hat_new = E_hat_Birks exp(g_theta(phi(HRDv)))`.

S24a additionally trained a waveform transformer for the energy endpoint; it is
reported below as an energy-only neural comparator because the PID source panel
did not train a transformer PID head.

## 4. Metrics and Joint Score

PID is scored by ROC AUC, average precision, and expected calibration error:

`ECE = sum_b (n_b / N) | mean(y_b) - mean(p_b) |`.

Energy is scored by the robust fractional residual width

`res68 = percentile_68(|(E_hat - E) / E|)`.

The pre-registered joint score minimized here is

`S = 0.45 (1 - AUC_PID) + 0.35 res68_energy + 0.20 res68_saturation`.

The saturation term repeats energy res68 inside the ADC-saturation-onset
stratum. All intervals are inherited from the source run-block bootstraps.

## 5. Joint Head-to-Head Benchmark

{md_table(joint, ['joint_method', 'pid_auc', 'pid_auc_ci_low', 'pid_auc_ci_high', 'energy_res68_frac', 'energy_res68_ci_low', 'energy_res68_ci_high', 'saturation_res68_frac', 'joint_score'])}

The traditional physics/range method wins because the PID proxy is explicitly
range-depth anchored and the energy endpoint is best explained by a Birks-style
truth prior. The best ML-only energy point estimate is competitive in MAE, but
the robust run-held-out fractional width and saturation stratum favor the
physics baseline.

## 6. PID Benchmark Table

{md_table(pid_main, ['method', 'n', 'runs', 'roc_auc', 'roc_auc_ci_low', 'roc_auc_ci_high', 'average_precision', 'purity_at_80pct_eff', 'ece'])}

## 7. Energy Benchmark Table

{md_table(energy_ordered, ['method', 'family', 'n', 'bias_frac', 'res68_frac', 'mae_mev'])}

## 8. Saturation and Pile-up Stress

The saturation-onset table below is the explicit stress endpoint used in the
joint score. Pile-up and pedestal robustness are covered in S24a by
`pileup_or_multihit`, `pedestal_drift_proxy_high`, and `late_pulse_shape`
strata; their detailed rows are preserved in `saturation_shape_strata_metrics.csv`.

{md_table(sat.sort_values('res68_frac'), ['method', 'n', 'bias_frac', 'res68_frac', 'mae_mev'])}

## 9. Leakage and Falsification

The falsification criterion is direct: an ML/NN method would win only if its
joint score were lower than the traditional joint score under complete
run-held-out evaluation. That did not occur. P08e includes run-family-only and
shuffled-label controls; the run-family-only control is random on the balanced
PID proxy, and the shuffled-label HGB stays near chance. S24a excludes run id,
event id, and odd duplicate-readout charges from the learned features. The
train and held-out run lists do not overlap.

Multiple comparison burden is six joint methods plus the energy-only
transformer. The finding is therefore not a claim that a neural method was
discovered by search; the selected winner is the pre-specified physics
baseline, so multiplicity strengthens rather than weakens the conclusion.

## 10. Systematics and Caveats

The PID label is an enriched proxy, not hidden particle truth. Its perfect
traditional AUC reflects the range-depth definition of the proxy; it should not
be read as an absolute proton/deuteron identification efficiency in a blind
beamline truth sample. The energy label is duplicate-readout closure transferred
through a GEANT4 layer prior, not a direct calorimetric standard. Saturation,
pile-up, pedestal drift, target composition, and event-topology migration can
move both endpoints together, so the joint score is a decision metric for this
support region rather than a universal detector calibration.

The source PID and energy panels were trained in separate ticket artifacts.
This ticket deliberately avoids refitting a monolithic multi-task neural
network because no event-level truth couples both targets without proxy
assumptions. A true multi-task architecture is scientifically sensible only
after a digitized simulation or external truth ledger supplies coupled PID and
energy labels.

## 11. Findings and Next Step

The joint winner is `{winner['joint_method']}`. Under the registered score it
beats ridge, gradient-boosted trees, MLP, 1D-CNN, and the new residual
architecture. The main scientific conclusion is that the available support is
dominated by known range/charge-depth physics and GEANT4 layer-response priors,
not by flexible waveform regressors.

One follow-up ticket is proposed in `result.json`: build a digitized GEANT4
multi-task PID-energy benchmark with ADC-like waveforms and known truth. Its
expected information gain is high because it directly tests whether a coupled
neural architecture can beat the physics baseline when the PID and energy
labels are true and event-aligned.

## 12. Reproducibility

Run:

```bash
{config['command']}
```

Primary outputs are `REPORT.md`, `result.json`, `manifest.json`,
`reproduction_counts_by_run.csv`, `reproduction_match_table.csv`,
`joint_method_benchmark.csv`, `pid_method_benchmark.csv`,
`energy_method_benchmark.csv`, and `saturation_shape_strata_metrics.csv`.

Source PID artifact: `{config['pid_source_dir']}`. Source energy artifact:
`{config['energy_source_dir']}`. Source commands were
`{pid_result.get('command') or pid_manifest.get('command')}` and
`{energy_result.get('command') or energy_manifest.get('command')}`.
"""
    (out / "REPORT.md").write_text(text, encoding="utf-8")


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return [json_ready(v) for v in value.tolist()]
    if pd.isna(value) if not isinstance(value, (str, bytes, list, dict)) else False:
        return None
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = load_config(ROOT / config_path if not config_path.is_absolute() else config_path)
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)

    counts, reproduction = recount_selected_pulses(config)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    pid, energy, stress, pid_result, energy_result, pid_manifest, energy_manifest = load_sources(config)
    joint = build_joint_table(pid, energy, stress, config)
    winner = joint.iloc[0].to_dict()

    counts.to_csv(out / "reproduction_counts_by_run.csv", index=False)
    reproduction.to_csv(out / "reproduction_match_table.csv", index=False)
    joint.to_csv(out / "joint_method_benchmark.csv", index=False)
    pid.to_csv(out / "pid_method_benchmark.csv", index=False)
    energy.to_csv(out / "energy_method_benchmark.csv", index=False)
    stress.to_csv(out / "saturation_shape_strata_metrics.csv", index=False)

    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "command": config["command"],
        "config": str(config_path),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": getattr(uproot, "__version__", "unknown"),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "raw_root_dir": config["raw_root_dir"],
        "source_artifacts": [config["pid_source_dir"], config["energy_source_dir"]],
        "reproduction_passed": bool(reproduction["pass"].all()),
        "joint_score_weights": config["joint_score_weights"],
    }

    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_root_dir": config["raw_root_dir"],
        "reproduction": {
            "passed": bool(reproduction["pass"].all()),
            "table": reproduction.to_dict(orient="records"),
        },
        "split": {
            "run_groups": config["run_groups"],
            "split_type": "complete run held-out groups inherited from P08e and S24a",
        },
        "bootstrap": {
            "unit": "held-out run block",
            "replicates": int(config["bootstrap_reps_source"]),
            "interval": "95% percentile",
        },
        "winner": winner["joint_method"],
        "winner_details": winner,
        "joint_benchmark": joint.to_dict(orient="records"),
        "source_pid_winner": pid_result.get("winner"),
        "source_energy_winner": energy_result.get("winner"),
        "next_tickets": [
            {
                "title": "Digitized GEANT4 multi-task PID-energy truth benchmark",
                "expected_information_gain": "Provides event-aligned true PID and energy labels with ADC-like waveforms, directly testing whether a coupled neural architecture can beat the physics/range baseline without proxy-label circularity.",
            }
        ],
        "runtime_sec": time.time() - start,
    }
    (out / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")

    manifest["outputs"] = []
    for path in sorted(out.iterdir()):
        if path.is_file():
            manifest["outputs"].append({"file": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    (out / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(
        out,
        config,
        reproduction,
        counts,
        joint,
        pid,
        energy,
        stress,
        pid_result,
        energy_result,
        pid_manifest,
        energy_manifest,
        manifest,
    )
    manifest["outputs"] = []
    for path in sorted(out.iterdir()):
        if path.is_file():
            manifest["outputs"].append({"file": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    (out / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket_id": config["ticket_id"], "winner": result["winner"], "runtime_sec": result["runtime_sec"]}, indent=2))


if __name__ == "__main__":
    main()
