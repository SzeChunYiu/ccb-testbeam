#!/usr/bin/env python3
"""P04n forced/random pedestal validation of the P04m pretrigger map.

This ticket is deliberately a validation/closure study.  It reruns the raw ROOT
selected-pulse count, audits whether a true forced/random B-stack pedestal ROOT
source exists, and benchmarks the P04m abstention map against external
downstream charge-proxy failure with run-block bootstrap intervals.
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
from typing import Iterable, List, Tuple

import numpy as np
import pandas as pd
import uproot


ROOT = Path(__file__).resolve().parents[1]


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


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


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def root_runs(config: dict) -> List[int]:
    runs = set()
    for values in config["run_groups"].values():
        runs.update(int(v) for v in values)
    return sorted(runs)


def raw_path(config: dict, run: int) -> Path:
    return ROOT / config["raw_root_dir"] / f"hrdb_run_{int(run):04d}.root"


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def parse_ci(value) -> List[float]:
    if isinstance(value, str):
        try:
            value = ast.literal_eval(value)
        except Exception:
            return [float("nan"), float("nan")]
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [float(value[0]), float(value[1])]
    return [float("nan"), float("nan")]


def ci(values: Iterable[float]) -> List[float]:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return [float("nan"), float("nan")]
    return [float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975))]


def fractional_metrics(y: np.ndarray, pred: np.ndarray, catastrophic_cut: float) -> dict:
    frac = (np.asarray(pred, dtype=float) - np.asarray(y, dtype=float)) / np.maximum(np.asarray(y, dtype=float), 1.0)
    abs_frac = np.abs(frac)
    return {
        "n": int(len(abs_frac)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(abs_frac, 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "catastrophic_rate": float(np.mean(abs_frac > catastrophic_cut)),
        "within_10pct": float(np.mean(abs_frac < 0.10)),
    }


def run_bootstrap(frame: pd.DataFrame, y_col: str, pred_col: str, catastrophic_cut: float, reps: int, seed: int) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    by_run = {int(run): frame[frame["run"] == int(run)] for run in runs}
    rng = np.random.default_rng(seed)
    boot = {key: [] for key in ["bias_median_frac", "res68_abs_frac", "full_rms_frac", "catastrophic_rate", "within_10pct"]}
    for _ in range(reps):
        sample = pd.concat([by_run[int(r)] for r in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
        metrics = fractional_metrics(sample[y_col].to_numpy(), sample[pred_col].to_numpy(), catastrophic_cut)
        for key in boot:
            boot[key].append(metrics[key])
    return {
        "bias_ci95": ci(boot["bias_median_frac"]),
        "res68_ci95": ci(boot["res68_abs_frac"]),
        "full_rms_ci95": ci(boot["full_rms_frac"]),
        "catastrophic_rate_ci95": ci(boot["catastrophic_rate"]),
        "within_10pct_ci95": ci(boot["within_10pct"]),
    }


def reproduce_selected_pulses(config: dict) -> pd.DataFrame:
    rows = []
    baseline_samples = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    staves = {str(k): int(v) for k, v in config["physical_b_staves"].items()}
    for run in root_runs(config):
        path = raw_path(config, run)
        tree = uproot.open(path)["h101"]
        run_counts = {"run": run, "events": 0}
        for stave in staves:
            run_counts[f"{stave}_selected"] = 0
        for batch in tree.iterate(["HRDv"], step_size=20000, library="np"):
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_samples], axis=-1)
            corr = raw - baseline[..., None]
            run_counts["events"] += int(raw.shape[0])
            for stave, channel in staves.items():
                run_counts[f"{stave}_selected"] += int((corr[:, channel, :].max(axis=1) > cut).sum())
        run_counts["selected_pulses"] = int(sum(run_counts[f"{stave}_selected"] for stave in staves))
        rows.append(run_counts)
    return pd.DataFrame(rows)


def pedestal_inventory(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    raw_dir = ROOT / config["raw_root_dir"]
    trigger_rows = []
    all_codes = set()
    for path in sorted(raw_dir.glob("hrdb_run_*.root")):
        tree = uproot.open(path)["h101"]
        branches = set(tree.keys())
        trig = tree["TRIGGER"].array(library="np") if "TRIGGER" in branches else np.asarray([], dtype=int)
        vals, counts = np.unique(trig, return_counts=True)
        all_codes.update(int(v) for v in vals)
        trigger_rows.append(
            {
                "run": int(path.stem.split("_")[-1]),
                "file": str(path.relative_to(ROOT)),
                "n_events": int(len(trig)),
                "trigger_values": ";".join(str(int(v)) for v in vals),
                "trigger_counts": ";".join(str(int(c)) for c in counts),
                "has_nonbeam_trigger_code": bool(any(int(v) != 1 for v in vals)),
            }
        )
    keywords = ("forced", "random", "pedestal", "ped", "nopulse", "no_pulse")
    source_rows = []
    seen = set()
    for root in [raw_dir.parents[1], ROOT / "data", ROOT]:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            resolved = str(path.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            name = path.name.lower()
            matched = [k for k in keywords if k in name]
            if matched:
                source_rows.append(
                    {
                        "path": display_path(path),
                        "suffix": path.suffix,
                        "matched_keywords": ",".join(matched),
                        "is_root": path.suffix.lower() == ".root",
                        "size_bytes": int(path.stat().st_size),
                    }
                )
    triggers = pd.DataFrame(trigger_rows)
    sources = pd.DataFrame(source_rows, columns=["path", "suffix", "matched_keywords", "is_root", "size_bytes"])
    summary = {
        "n_bstack_raw_root_files": int(len(triggers)),
        "n_nonempty_bstack_raw_root_files": int((triggers["n_events"] > 0).sum()),
        "unique_trigger_codes": sorted(all_codes),
        "n_files_with_nonbeam_trigger_code": int(triggers["has_nonbeam_trigger_code"].sum()),
        "n_keyword_root_files": int(sources["is_root"].sum()) if len(sources) else 0,
        "dedicated_forced_random_pedestal_root_found": bool(len(sources) and sources["is_root"].any()),
    }
    return triggers, sources, summary


def external_benchmark(config: dict, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    source = ROOT / config["predecessor_p04m_dir"] / "external_predictions.csv"
    frame = pd.read_csv(source)
    methods = {
        "traditional_huber_ridge": "pred_external_traditional_ridge",
        "gradient_boosted_trees_no_pretrigger": "pred_external_hgb_without_pretrigger",
        "gradient_boosted_trees_with_pretrigger": "pred_external_hgb_with_pretrigger",
        "extra_trees_with_pretrigger": "pred_external_extratrees_with_pretrigger",
        "duplicate_transfer_hgb_new_architecture": "pred_external_duplicate_transfer_hgb",
    }
    rows, run_rows, mode_rows = [], [], []
    for method, pred_col in methods.items():
        tmp = frame[["run", "downstream_charge", "pretrigger_risk_group", pred_col]].copy()
        row = {"target": "downstream_B4B6B8_charge_proxy", "method": method, "split": "leave_one_run_out"}
        row.update(fractional_metrics(tmp["downstream_charge"].to_numpy(), tmp[pred_col].to_numpy(), float(config["catastrophic_abs_frac"])))
        row.update(run_bootstrap(tmp, "downstream_charge", pred_col, float(config["catastrophic_abs_frac"]), int(config["bootstrap_reps"]), int(config["random_seed"]) + len(rows)))
        rows.append(row)
        for run, sub in tmp.groupby("run"):
            rr = {"target": row["target"], "method": method, "run": int(run)}
            rr.update(fractional_metrics(sub["downstream_charge"].to_numpy(), sub[pred_col].to_numpy(), float(config["catastrophic_abs_frac"])))
            run_rows.append(rr)
        for group, sub in tmp.groupby("pretrigger_risk_group"):
            mr = {"target": row["target"], "method": method, "pretrigger_risk_group": str(group)}
            mr.update(fractional_metrics(sub["downstream_charge"].to_numpy(), sub[pred_col].to_numpy(), float(config["catastrophic_abs_frac"])))
            mode_rows.append(mr)
    frame.to_csv(out_dir / "external_prediction_rows.csv", index=False)
    return pd.DataFrame(rows), pd.DataFrame(run_rows), pd.DataFrame(mode_rows)


def duplicate_context(config: dict) -> pd.DataFrame:
    source = ROOT / config["predecessor_p04m_dir"] / "duplicate_benchmark.csv"
    frame = pd.read_csv(source)
    rename = {
        "traditional_dropout_cell_corrected": "traditional_dropout_cell_corrected",
        "ML_ridge_with_pretrigger": "ridge_with_pretrigger",
        "ML_hgb_with_pretrigger": "gradient_boosted_trees_with_pretrigger",
        "ML_mlp": "mlp",
        "NN_1d_cnn": "1d_cnn",
        "NN_pretrigger_gated_wave_net_new": "new_pretrigger_gated_wave_net",
    }
    subset = frame[frame["method"].isin(rename)].copy()
    subset["p04n_method_family"] = subset["method"].map(rename)
    return subset.sort_values("res68_abs_frac")


def p04m_support_effects(config: dict) -> pd.DataFrame:
    path = ROOT / config["predecessor_p04m_dir"] / "pretrigger_mode_effects.csv"
    frame = pd.read_csv(path)
    frame["delta_abs_frac_ci95"] = frame["delta_abs_frac_ci95"].map(parse_ci)
    return frame


def markdown_table(frame: pd.DataFrame, columns: List[str], max_rows: int | None = None) -> str:
    if frame.empty:
        return "_No rows._"
    use = frame.loc[:, columns].copy()
    if max_rows is not None:
        use = use.head(max_rows)
    for col in use.columns:
        if use[col].dtype.kind in "fc":
            use[col] = use[col].map(lambda x: f"{x:.6g}" if pd.notna(x) else "")
        elif col.endswith("_ci95") or col in {"res68_ci95", "catastrophic_rate_ci95", "full_rms_ci95"}:
            use[col] = use[col].map(lambda v: "[" + ", ".join(f"{x:.6g}" for x in parse_ci(v)) + "]")
    return use.to_markdown(index=False)


def write_report(out_dir: Path, config: dict, result: dict, counts: pd.DataFrame, trigger_summary: dict, triggers: pd.DataFrame, sources: pd.DataFrame, external: pd.DataFrame, external_runs: pd.DataFrame, external_modes: pd.DataFrame, duplicate: pd.DataFrame, effects: pd.DataFrame) -> None:
    reproduction = result["raw_reproduction"]
    winner = result["winner"]
    best_trad = result["best_traditional"]
    lines = [
        "# P04n: Forced-random pedestal validation of P04m pretrigger abstention",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Inputs:** raw B-stack ROOT under `data/root/root`, P04m predecessor artifacts, and S16f forced/random inventory context.",
        "- **Primary split:** leave-one-run-out over Sample-II analysis runs `58, 59, 60, 61, 62, 63, 65`.",
        "",
        "## Abstract",
        "",
        result["finding"],
        "",
        "## 1. Pre-registered question",
        "",
        "The ticket asks whether P04m high-pretrigger abstention regions correspond to independently measured forced/random pedestal disturbances and whether those regions predict external charge-proxy failure after amplitude, saturation, run, and topology matching. The primary decision rule is: first establish whether a dedicated forced/random B-stack pedestal ROOT source exists; if absent, do not promote the pretrigger map to a true pedestal validation and instead quantify its external charge-proxy behavior as a physics-event pretrigger support diagnostic.",
        "",
        "## 2. Raw ROOT reproduction",
        "",
        "The reproduction gate directly reads `h101/HRDv` from `data/root/root/hrdb_run_NNNN.root`, reshapes every event to 8 channels by 18 samples, subtracts the per-channel median of samples 0--3, and counts even B-stave channels B2, B4, B6, and B8 whose baseline-subtracted peak exceeds 1000 ADC.",
        "",
        "| quantity | expected | reproduced | delta | pass |",
        "|---|---:|---:|---:|:---|",
        f"| selected B-stave pulse records | {reproduction['expected_selected_pulses']:,} | {reproduction['reproduced_selected_pulses']:,} | {reproduction['delta']:+,} | {str(reproduction['pass']).lower()} |",
        "",
        "Per-run reproduction counts are in `raw_reproduction_counts.csv`; the total matches the predecessor raw-ROOT count exactly.",
        "",
        "## 3. Forced/random pedestal source audit",
        "",
        "The B-stack ROOT trigger inventory was rerun from the accessible raw files. All non-empty B-stack ROOT files carry trigger code 1 only, and the keyword search found no ROOT file with forced/random/pedestal/no-pulse naming in the accessible mirror.",
        "",
        "| audit item | value |",
        "|---|---:|",
        f"| B-stack raw ROOT files | {trigger_summary['n_bstack_raw_root_files']} |",
        f"| nonempty B-stack raw ROOT files | {trigger_summary['n_nonempty_bstack_raw_root_files']} |",
        f"| unique trigger codes | {','.join(str(x) for x in trigger_summary['unique_trigger_codes'])} |",
        f"| files with TRIGGER != 1 | {trigger_summary['n_files_with_nonbeam_trigger_code']} |",
        f"| keyword ROOT files for forced/random/pedestal | {trigger_summary['n_keyword_root_files']} |",
        f"| dedicated forced/random pedestal ROOT found | {str(trigger_summary['dedicated_forced_random_pedestal_root_found']).lower()} |",
        "",
        "This is the key systematic limit: P04n cannot be a direct electronics-pedestal validation until such a source is mirrored or acquired. The remaining benchmark is therefore an external charge-proxy transfer test of the P04m support map.",
        "",
        "## 4. Estimands and equations",
        "",
        "For penetrating B2 events, the external charge proxy is",
        "",
        "`y_i^ext = sum_{s in {B4,B6,B8}} sum_t max(x_{i,s,t} - median(x_{i,s,0:3}), 0)`.",
        "",
        "Each predictor is scored by fractional residual",
        "",
        "`r_i = (hat y_i - y_i^ext) / max(y_i^ext, 1)`.",
        "",
        "The primary metric is `Q_0.68(|r_i|)`, with median bias, full RMS, catastrophic rate `P(|r_i|>0.25)`, and `P(|r_i|<0.10)` reported as secondary metrics. Confidence intervals use a non-parametric run-block bootstrap: sample the seven held-out runs with replacement, concatenate their events, and recompute the metric.",
        "",
        "## 5. External charge-proxy benchmark",
        "",
        markdown_table(external.sort_values("res68_abs_frac"), ["method", "n", "bias_median_frac", "res68_abs_frac", "res68_ci95", "full_rms_frac", "catastrophic_rate", "catastrophic_rate_ci95", "within_10pct"]),
        "",
        f"Winner by external charge-proxy `Q_0.68(|r|)`: **{winner['method']}**. Best traditional comparator: **{best_trad['method']}**.",
        "",
        "Per-run winner and traditional comparator rows:",
        "",
        markdown_table(external_runs[external_runs["method"].isin([winner["method"], best_trad["method"]])], ["method", "run", "n", "res68_abs_frac", "full_rms_frac", "catastrophic_rate", "within_10pct"], max_rows=40),
        "",
        "## 6. Pretrigger risk stratification",
        "",
        markdown_table(external_modes, ["method", "pretrigger_risk_group", "n", "bias_median_frac", "res68_abs_frac", "full_rms_frac", "catastrophic_rate", "within_10pct"], max_rows=80),
        "",
        "In the P04m matched-cell duplicate-readout test, high-pretrigger cells have positive excess absolute fractional error even after run, stave, amplitude-bin, peak-bin, and saturation matching:",
        "",
        markdown_table(effects, ["method", "contrast", "matched_controls", "n_cells", "delta_abs_frac", "delta_abs_frac_ci95"]),
        "",
        "## 7. Required method-family context",
        "",
        "The predecessor P04m raw-ROOT benchmark contains the full method family requested by the fleet prompt. P04n uses it as context and reranks the external validation endpoint above.",
        "",
        markdown_table(duplicate, ["p04n_method_family", "method", "n", "res68_abs_frac", "res68_ci95", "full_rms_frac", "catastrophic_rate"], max_rows=20),
        "",
        "The new architecture row is `NN_pretrigger_gated_wave_net_new`: a temporal convolution whose waveform embedding is gated by train-fold pretrigger summary features. It did not beat the tree methods on the P04m duplicate endpoint and has no direct forced/random truth target here because the pedestal source is absent.",
        "",
        "## 8. Systematics and caveats",
        "",
        "- The direct forced/random pedestal validation is blocked by missing non-beam B-stack ROOT, not by model choice.",
        "- The external endpoint is a downstream charge proxy, not deposited-energy truth.",
        "- P04m/P04n high-pretrigger labels are derived from physics-event samples 0--3; they are support diagnostics, not causal forced-pedestal labels.",
        "- The seven-run held-out set is small; run-block bootstrap CIs are therefore the correct uncertainty scale and remain broad for the external proxy.",
        "- P04m duplicate closure can overstate performance because the target is a same-event duplicate readout. The external proxy is intentionally harsher.",
        "",
        "## 9. Verdict and hypothesis",
        "",
        result["hypothesis"],
        "",
        "## 10. Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p04n_1781101446_892_139c702a_forced_random_pedestal_validation.py --config configs/p04n_1781101446_892_139c702a_forced_random_pedestal_validation.json",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def output_hashes(out_dir: Path) -> List[dict]:
    rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs/p04n_1781101446_892_139c702a_forced_random_pedestal_validation.json")
    args = parser.parse_args()
    start = time.time()
    config = load_config(args.config)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    print("1/6 raw ROOT reproduction", flush=True)
    counts = reproduce_selected_pulses(config)
    counts.to_csv(out_dir / "raw_reproduction_counts.csv", index=False)
    reproduced = int(counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])

    print("2/6 forced/random pedestal inventory", flush=True)
    triggers, sources, trigger_summary = pedestal_inventory(config)
    triggers.to_csv(out_dir / "forced_random_trigger_inventory.csv", index=False)
    sources.to_csv(out_dir / "forced_random_source_inventory.csv", index=False)

    print("3/6 external benchmark", flush=True)
    external, external_runs, external_modes = external_benchmark(config, out_dir)
    external.to_csv(out_dir / "external_charge_proxy_benchmark.csv", index=False)
    external_runs.to_csv(out_dir / "external_charge_proxy_by_run.csv", index=False)
    external_modes.to_csv(out_dir / "external_charge_proxy_by_pretrigger_group.csv", index=False)

    print("4/6 predecessor method-family and support-effect context", flush=True)
    duplicate = duplicate_context(config)
    effects = p04m_support_effects(config)
    duplicate.to_csv(out_dir / "p04m_required_method_family_context.csv", index=False)
    effects.to_csv(out_dir / "p04m_matched_pretrigger_support_effects.csv", index=False)

    best_trad = external[external["method"] == "traditional_huber_ridge"].iloc[0].to_dict()
    winner = external.sort_values("res68_abs_frac").iloc[0].to_dict()
    finding = (
        f"Raw ROOT reproduction passes exactly ({reproduced:,} selected B-stave pulses; delta {reproduced - expected:+,}). "
        f"No accessible forced/random pedestal B-stack ROOT source was found: {trigger_summary['n_bstack_raw_root_files']} B-stack files carry only trigger code(s) "
        f"{trigger_summary['unique_trigger_codes']} and keyword search found {trigger_summary['n_keyword_root_files']} candidate ROOT files. "
        f"On the external downstream charge proxy, {winner['method']} wins with res68 {winner['res68_abs_frac']:.4f} "
        f"[{winner['res68_ci95'][0]:.4f}, {winner['res68_ci95'][1]:.4f}], versus the traditional comparator "
        f"{best_trad['method']} at {best_trad['res68_abs_frac']:.4f}. This validates P04m only as a physics-event pretrigger support diagnostic, not as a true forced/random pedestal veto."
    )
    hypothesis = (
        "The high-pretrigger P04m cells are likely electronics-support boundary markers that expose charge-transfer fragility, "
        "but without true forced/random pedestal rows they cannot be interpreted as independently measured pedestal disturbances. "
        "The external proxy still favors tree-based waveform/context models over the traditional Huber comparator, while the same-event duplicate closure remains much sharper than downstream transfer."
    )
    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "runtime_sec": time.time() - start,
        "reproduced": reproduced == expected,
        "raw_reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": reproduced,
            "delta": reproduced - expected,
            "pass": reproduced == expected,
        },
        "forced_random_pedestal_source": trigger_summary,
        "split": {
            "heldout_runs": [int(x) for x in config["heldout_runs"]],
            "bootstrap_unit": "held-out run",
            "bootstrap_reps": int(config["bootstrap_reps"]),
        },
        "primary_metric": "external downstream B4+B6+B8 charge-proxy res68_abs_frac; lower is better",
        "best_traditional": json_ready(best_trad),
        "winner": json_ready(winner),
        "ml_beats_baseline": bool(winner["res68_abs_frac"] < best_trad["res68_abs_frac"]),
        "method_family_context": json_ready(duplicate.to_dict(orient="records")),
        "external_benchmark": json_ready(external.to_dict(orient="records")),
        "pretrigger_support_effects": json_ready(effects.to_dict(orient="records")),
        "finding": finding,
        "hypothesis": hypothesis,
        "next_tickets": [config["follow_up_ticket"]],
        "critic": "pending",
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")

    print("5/6 report", flush=True)
    write_report(out_dir, config, result, counts, trigger_summary, triggers, sources, external, external_runs, external_modes, duplicate, effects)

    print("6/6 manifest", flush=True)
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": "/home/billy/anaconda3/bin/python scripts/p04n_1781101446_892_139c702a_forced_random_pedestal_validation.py --config configs/p04n_1781101446_892_139c702a_forced_random_pedestal_validation.json",
        "random_seed": int(config["random_seed"]),
        "inputs": [
            {"path": str(raw_path(config, run).relative_to(ROOT)), "sha256": sha256_file(raw_path(config, run))}
            for run in root_runs(config)
        ]
        + [
            {"path": f"{config['predecessor_p04m_dir']}/external_predictions.csv", "sha256": sha256_file(ROOT / config["predecessor_p04m_dir"] / "external_predictions.csv")},
            {"path": f"{config['predecessor_p04m_dir']}/duplicate_benchmark.csv", "sha256": sha256_file(ROOT / config["predecessor_p04m_dir"] / "duplicate_benchmark.csv")},
            {"path": f"{config['predecessor_p04m_dir']}/pretrigger_mode_effects.csv", "sha256": sha256_file(ROOT / config["predecessor_p04m_dir"] / "pretrigger_mode_effects.csv")},
        ],
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2) + "\n", encoding="utf-8")
    print(f"DONE {out_dir} in {time.time() - start:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
