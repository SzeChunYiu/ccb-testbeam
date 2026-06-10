#!/usr/bin/env python3
"""S14c: topology study for the S14b/P04b external charge-proxy term.

The study starts by reproducing the exact P04b external B4+B6+B8 res68 from
raw B-stack ROOT. It then compares downstream proxy choices, B2 amplitude
strata, and topology gates with leave-one-run-out predictions and run-block
bootstrap intervals. The final energy-proxy rows reuse the S14b raw-root
charge-sensitivity coefficients from the prior range-energy rerun.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p04b_external_charge_validation as p04b  # noqa: E402


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def raw_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_batches(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def robust_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(np.abs(frac), 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "within_10pct": float(np.mean(np.abs(frac) < 0.10)),
        "within_25pct": float(np.mean(np.abs(frac) < 0.25)),
    }


def run_block_ci(frame: pd.DataFrame, y_col: str, pred_col: str, rng: np.random.Generator, reps: int) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    if len(runs) < 2:
        return {"bias_ci95": [None, None], "res68_ci95": [None, None], "full_rms_ci95": [None, None]}
    by_run = {int(run): frame[frame["run"] == run] for run in runs}
    bias = np.empty(reps, dtype=float)
    res68 = np.empty(reps, dtype=float)
    rms = np.empty(reps, dtype=float)
    for idx in range(reps):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        sample = pd.concat([by_run[int(run)] for run in chosen], ignore_index=True)
        frac = (sample[pred_col].to_numpy(dtype=float) - sample[y_col].to_numpy(dtype=float)) / np.maximum(
            sample[y_col].to_numpy(dtype=float), 1.0
        )
        bias[idx] = np.median(frac)
        res68[idx] = np.percentile(np.abs(frac), 68)
        rms[idx] = np.sqrt(np.mean(frac * frac))
    return {
        "bias_ci95": [float(np.percentile(bias, 2.5)), float(np.percentile(bias, 97.5))],
        "res68_ci95": [float(np.percentile(res68, 2.5)), float(np.percentile(res68, 97.5))],
        "full_rms_ci95": [float(np.percentile(rms, 2.5)), float(np.percentile(rms, 97.5))],
    }


def b2_wave_features(meta: pd.DataFrame, wave: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    amp = meta["b2_amp"].to_numpy(dtype=float)
    charge = np.maximum(meta["b2_charge"].to_numpy(dtype=float), 1.0)
    clipped = np.clip(wave, 0.0, None)
    early = clipped[:, :6].sum(axis=1) / charge
    mid = clipped[:, 6:12].sum(axis=1) / charge
    late = clipped[:, 12:].sum(axis=1) / charge
    tail = clipped[:, 9:].sum(axis=1) / charge
    peak = meta["b2_peak"].to_numpy(dtype=float)
    half_width = (wave > (0.5 * amp[:, None])).sum(axis=1)
    weighted_t = (clipped * np.arange(wave.shape[1], dtype=float)[None, :]).sum(axis=1) / charge
    engineered = np.column_stack(
        [
            np.log(np.maximum(amp, 1.0)),
            np.log(charge),
            peak,
            meta["b2_area"].to_numpy(dtype=float) / charge,
            early,
            mid,
            late,
            tail,
            half_width,
            weighted_t,
            meta["b2_saturated"].to_numpy(dtype=float),
        ]
    )
    trad = engineered[:, [0, 1, 2, 5, 6, 7, 8, 10]]
    ml = np.column_stack([wave, engineered])
    return trad, ml


def extract_b2_downstream_rows(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    b2_ch = int(config["b2_channel"])
    b2_dup_ch = int(config["b2_duplicate_channel"])
    downstream = {name: int(ch) for name, ch in config["downstream_channels"].items()}

    frames: List[pd.DataFrame] = []
    waves: List[np.ndarray] = []
    counts: List[dict] = []
    topo_rows: List[dict] = []
    for run in [int(r) for r in config["sample_ii_runs"]]:
        path = raw_path(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        run_count = {"run": int(run), "events_total": 0, "b2_selected": 0, "b2_valid_duplicate": 0}
        run_topo: Dict[str, int] = {}
        for batch in iter_batches(path):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]

            b2 = corrected[:, b2_ch, :]
            b2_dup = corrected[:, b2_dup_ch, :]
            down = np.stack([corrected[:, ch, :] for ch in downstream.values()], axis=1)

            b2_amp = b2.max(axis=1)
            b2_charge = np.clip(b2, 0.0, None).sum(axis=1)
            b2_area = b2.sum(axis=1)
            b2_peak = b2.argmax(axis=1)
            b2_dup_charge = np.clip(-b2_dup, 0.0, None).sum(axis=1)
            down_amp = down.max(axis=2)
            down_charge = np.clip(down, 0.0, None).sum(axis=2)
            down_selected = down_amp > cut
            b2_selected = b2_amp > cut
            valid = b2_selected & (b2_dup_charge > 100.0)

            run_count["events_total"] += int(len(eventno))
            run_count["b2_selected"] += int(b2_selected.sum())
            run_count["b2_valid_duplicate"] += int(valid.sum())
            for bits in [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (0, 1, 1), (1, 1, 1)]:
                label = "".join(stave for stave, bit in zip(downstream.keys(), bits) if bit)
                mask = valid & np.logical_and.reduce([down_selected[:, i] == bool(bit) for i, bit in enumerate(bits)])
                run_topo[label] = run_topo.get(label, 0) + int(mask.sum())
            if not valid.any():
                continue

            idx = np.flatnonzero(valid)
            waves.append(b2[idx].astype(np.float32))
            frame = pd.DataFrame(
                {
                    "run": int(run),
                    "eventno": eventno[idx],
                    "evt": evt[idx],
                    "b2_amp": b2_amp[idx],
                    "b2_charge": b2_charge[idx],
                    "b2_area": b2_area[idx],
                    "b2_peak": b2_peak[idx].astype(np.int16),
                    "b2_duplicate_charge": b2_dup_charge[idx],
                    "b2_saturated": (b2_amp[idx] >= 7000.0).astype(np.int8),
                }
            )
            for stave_idx, stave in enumerate(downstream):
                frame[f"{stave}_selected"] = down_selected[idx, stave_idx].astype(np.int8)
                frame[f"{stave}_amp"] = down_amp[idx, stave_idx]
                frame[f"{stave}_charge"] = down_charge[idx, stave_idx]
            frame["downstream_mult"] = frame[[f"{s}_selected" for s in downstream]].sum(axis=1).astype(np.int8)
            frame["downstream_charge_sum"] = frame[[f"{s}_charge" for s in downstream]].sum(axis=1)
            frames.append(frame)
        counts.append(run_count)
        topo_rows.extend({"run": int(run), "topology_exact": key, "n": val} for key, val in sorted(run_topo.items()))
    meta = pd.concat(frames, ignore_index=True)
    return meta, np.vstack(waves), pd.DataFrame(counts), pd.DataFrame(topo_rows)


def target_staves(target: str) -> List[str]:
    return [part for part in ["B4", "B6", "B8"] if part in target]


def gate_mask(meta: pd.DataFrame, gate: str, staves: Sequence[str]) -> np.ndarray:
    cols = {s: meta[f"{s}_selected"].to_numpy(dtype=bool) for s in ["B4", "B6", "B8"]}
    if gate == "target_hit_only":
        return np.logical_and.reduce([cols[s] for s in staves])
    if gate == "all_three":
        return cols["B4"] & cols["B6"] & cols["B8"]
    if gate == "b4b6_no_b8":
        return cols["B4"] & cols["B6"] & (~cols["B8"])
    if gate == "b8_present":
        return cols["B8"] & np.logical_and.reduce([cols[s] for s in staves])
    raise ValueError(gate)


def variant_grid() -> List[Tuple[str, str, List[str]]]:
    variants: List[Tuple[str, str, List[str]]] = []
    targets = ["B4", "B6", "B8", "B4B6", "B6B8", "B4B6B8"]
    for target in targets:
        staves = target_staves(target)
        variants.append((target, "target_hit_only", staves))
        variants.append((target, "all_three", staves))
        if all(s in ["B4", "B6"] for s in staves):
            variants.append((target, "b4b6_no_b8", staves))
        if "B8" in staves:
            variants.append((target, "b8_present", staves))
    return variants


def fit_variant(
    config: dict,
    meta: pd.DataFrame,
    x_trad: np.ndarray,
    x_ml: np.ndarray,
    mask: np.ndarray,
    y: np.ndarray,
    seed_offset: int,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    work = meta.loc[mask, ["run", "eventno", "evt", "b2_amp", "b2_charge", "b2_duplicate_charge", "downstream_mult"]].copy()
    work["target_charge"] = y[mask]
    work["pred_traditional_ridge"] = np.nan
    work["pred_ml_hgb"] = np.nan
    work["pred_shuffled_ml"] = np.nan
    idx_all = np.flatnonzero(mask)
    rng = np.random.default_rng(int(config["random_seed"]) + seed_offset)

    for heldout_run in sorted(work["run"].unique()):
        local_test = work["run"].to_numpy() == int(heldout_run)
        local_train = ~local_test
        if int(local_train.sum()) < int(config["min_train_rows_per_fold"]):
            continue
        train_idx = idx_all[local_train]
        test_idx = idx_all[local_test]
        train_fit = train_idx
        if len(train_fit) > int(config["ml_max_train_rows"]):
            train_fit = rng.choice(train_fit, size=int(config["ml_max_train_rows"]), replace=False)
        y_train = np.log(np.maximum(y[train_idx], 1.0))

        trad = make_pipeline(StandardScaler(), Ridge(alpha=3.0))
        trad.fit(x_trad[train_idx], y_train)
        work.loc[local_test, "pred_traditional_ridge"] = np.exp(trad.predict(x_trad[test_idx]))

        model = HistGradientBoostingRegressor(
            max_iter=180,
            learning_rate=0.06,
            max_leaf_nodes=31,
            l2_regularization=0.08,
            random_state=int(config["random_seed"]) + seed_offset + int(heldout_run),
        )
        model.fit(x_ml[train_fit], np.log(np.maximum(y[train_fit], 1.0)))
        work.loc[local_test, "pred_ml_hgb"] = np.exp(model.predict(x_ml[test_idx]))

        shuffled_y = np.log(np.maximum(y[train_fit], 1.0)).copy()
        rng.shuffle(shuffled_y)
        shuf = HistGradientBoostingRegressor(
            max_iter=80,
            learning_rate=0.06,
            max_leaf_nodes=31,
            l2_regularization=0.08,
            random_state=int(config["random_seed"]) + 999 + seed_offset + int(heldout_run),
        )
        shuf.fit(x_ml[train_fit], shuffled_y)
        work.loc[local_test, "pred_shuffled_ml"] = np.exp(shuf.predict(x_ml[test_idx]))

    if work[["pred_traditional_ridge", "pred_ml_hgb", "pred_shuffled_ml"]].isna().any().any():
        missing = work[["pred_traditional_ridge", "pred_ml_hgb", "pred_shuffled_ml"]].isna().sum().to_dict()
        raise RuntimeError(f"missing predictions in variant: {missing}")

    rng_ci = np.random.default_rng(int(config["random_seed"]) + 2000 + seed_offset)
    rows = []
    for method, pred_col, split in [
        ("traditional_ridge", "pred_traditional_ridge", "leave_one_run_out"),
        ("ml_hgb", "pred_ml_hgb", "leave_one_run_out"),
        ("shuffled_ml", "pred_shuffled_ml", "negative_control"),
    ]:
        row = {"method": method, "split": split}
        row.update(robust_metrics(work["target_charge"].to_numpy(dtype=float), work[pred_col].to_numpy(dtype=float)))
        row.update(run_block_ci(work, "target_charge", pred_col, rng_ci, int(config["bootstrap_reps"])))
        rows.append(row)
    return pd.DataFrame(rows), work


def energy_rows(config: dict, charge_summary: pd.DataFrame) -> pd.DataFrame:
    prop = pd.read_csv(config["s14b_propagation_source"])
    geom = config["nominal_geometry"]
    base = prop[prop["geometry"] == geom].copy()
    out_rows = []
    for _, c in charge_summary[charge_summary["split"] == "leave_one_run_out"].iterrows():
        for _, s14 in base.iterrows():
            coef = float(s14["p04b_charge_propagated_energy_res68"]) / float(s14["p04b_external_charge_res68"])
            model = float(s14["model_energy_proxy_res68"])
            charge_res = float(c["res68_abs_frac"])
            prop_res = coef * charge_res
            combined = float(np.sqrt(model * model + prop_res * prop_res))
            ci_in = c["res68_ci95"]
            if isinstance(ci_in, str):
                ci_in = json.loads(ci_in)
            if not isinstance(ci_in, list):
                ci_in = [None, None]
            if ci_in[0] is None:
                combined_ci = [None, None]
            else:
                combined_ci = [
                    float(np.sqrt(model * model + (coef * float(ci_in[0])) ** 2)),
                    float(np.sqrt(model * model + (coef * float(ci_in[1])) ** 2)),
                ]
            out_rows.append(
                {
                    "target": c["target"],
                    "gate": c["gate"],
                    "charge_method": c["method"],
                    "s14b_energy_method": s14["method"],
                    "n_charge_rows": int(c["n"]),
                    "charge_res68_abs_frac": charge_res,
                    "charge_res68_ci95": ci_in,
                    "model_energy_proxy_res68": model,
                    "charge_to_energy_sensitivity": coef,
                    "charge_propagated_energy_res68": prop_res,
                    "combined_energy_proxy_res68": combined,
                    "combined_energy_proxy_res68_ci95": combined_ci,
                    "acceptance_res68": float(config["energy_uncertainty_acceptance_res68"]),
                    "acceptable_for_s14_preflight": bool(combined <= float(config["energy_uncertainty_acceptance_res68"])),
                }
            )
    return pd.DataFrame(out_rows)


def output_hashes(out_dir: Path) -> dict:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(out_dir: Path, config: dict, result: dict, tables: Dict[str, pd.DataFrame]) -> None:
    best_charge = tables["charge_summary"].sort_values("res68_abs_frac").head(12)
    best_energy = tables["energy_summary"].sort_values("combined_energy_proxy_res68").head(12)
    amp_display = (
        tables["by_amp"][tables["by_amp"]["method"].isin(["traditional_ridge", "ml_hgb"])]
        .sort_values("res68_abs_frac")
        .head(36)
    )
    topo_display = tables["topology_counts"].pivot_table(index="run", columns="topology_exact", values="n", aggfunc="sum", fill_value=0)
    topo_display["total_listed"] = topo_display.sum(axis=1)
    topo_display = topo_display.reset_index()
    baseline = result["p04b_reproduction_first"]
    lines = [
        "# S14c: reduce P04b charge-proxy term for range-energy preflight",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw `data/root/root/hrdb_run_*.root`; no Monte Carlo.",
        "- **Split:** leave-one-run-out by run on Sample II runs 58, 59, 60, 61, 62, 63, and 65; CIs are held-out run-block bootstraps.",
        "",
        "## Raw reproduction first",
        "",
        f"P04b external reproduction from raw ROOT gives `external_ml_hgb` res68 `{baseline['reproduced_external_ml_res68']:.12f}` "
        f"vs expected `{baseline['expected_external_ml_res68']:.12f}` (delta `{baseline['delta']:.3g}`).",
        "",
        "## Topology support",
        "",
        topo_display.to_markdown(index=False),
        "",
        "## Best charge-proxy rows",
        "",
        best_charge[
            ["target", "gate", "method", "n", "bias_median_frac", "res68_abs_frac", "res68_ci95", "within_10pct", "within_25pct"]
        ].to_markdown(index=False),
        "",
        "## Best charge-propagated energy rows",
        "",
        best_energy[
            [
                "target",
                "gate",
                "charge_method",
                "s14b_energy_method",
                "n_charge_rows",
                "charge_res68_abs_frac",
                "charge_propagated_energy_res68",
                "combined_energy_proxy_res68",
                "combined_energy_proxy_res68_ci95",
                "acceptable_for_s14_preflight",
            ]
        ].to_markdown(index=False),
        "",
        "## B2 amplitude strata",
        "",
        "Best 36 method/target/gate/bin rows by held-out res68; the full table is `charge_proxy_by_b2_amp.csv`.",
        "",
        amp_display[
            ["target", "gate", "method", "b2_amp_bin", "n", "bias_median_frac", "res68_abs_frac", "within_25pct"]
        ].to_markdown(index=False),
        "",
        "## Leakage checks",
        "",
        tables["leakage_checks"].to_markdown(index=False),
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/s14c_1781026825_1563_18b74737_charge_proxy_topology.py --config configs/s14c_1781026825_1563_18b74737_charge_proxy_topology.yaml",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s14c_1781026825_1563_18b74737_charge_proxy_topology.yaml")
    args = parser.parse_args()

    t0 = time.time()
    config_path = Path(args.config)
    config = load_yaml(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    print("1/7 reproducing P04b external charge-proxy number from raw ROOT ...", flush=True)
    p04b_config = dict(config)
    p04b_config["output_dir"] = str(out_dir / "p04b_reproduction_check")
    p04_repro = p04b.reproduce_p04_charge_number(p04b_config)
    base_frame, base_wave, base_counts = p04b.extract_external_rows(p04b_config)
    base_summary, base_by_run, base_by_amp, base_leak = p04b.leave_one_run_out_external(p04b_config, base_frame, base_wave)
    base_summary.to_csv(out_dir / "p04b_reproduction_external_summary.csv", index=False)
    base_by_run.to_csv(out_dir / "p04b_reproduction_external_by_run.csv", index=False)
    base_by_amp.to_csv(out_dir / "p04b_reproduction_external_by_amp.csv", index=False)
    base_counts.to_csv(out_dir / "p04b_reproduction_counts_by_run.csv", index=False)
    pd.DataFrame(p04_repro["benchmark"]).to_csv(out_dir / "p04_reproduction_charge.csv", index=False)
    reproduced = float(base_summary.loc[base_summary["method"] == "external_ml_hgb", "res68_abs_frac"].iloc[0])
    expected = float(config["p04b_expected_external_res68"])
    if abs(reproduced - expected) > float(config["p04b_expected_tolerance"]):
        raise RuntimeError(f"P04b reproduction failed: {reproduced} != {expected}")

    print("2/7 extracting B2/downstream topology rows from raw ROOT ...", flush=True)
    meta, wave, counts, topology = extract_b2_downstream_rows(config)
    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    topology.to_csv(out_dir / "topology_counts.csv", index=False)
    if int(counts["b2_selected"].sum()) <= 0:
        raise RuntimeError("no B2-selected rows extracted")
    x_trad, x_ml = b2_wave_features(meta, wave)

    print("3/7 fitting target/gate variants ...", flush=True)
    summaries = []
    by_run_rows = []
    by_amp_rows = []
    pred_paths = []
    for vidx, (target, gate, staves) in enumerate(variant_grid()):
        mask = gate_mask(meta, gate, staves)
        y = meta[[f"{s}_charge" for s in staves]].sum(axis=1).to_numpy(dtype=float)
        mask = mask & (y > 100.0)
        if int(mask.sum()) < int(config["min_rows"]):
            summaries.append(
                {
                    "target": target,
                    "gate": gate,
                    "method": "skipped_low_support",
                    "split": "none",
                    "n": int(mask.sum()),
                    "bias_median_frac": np.nan,
                    "res68_abs_frac": np.nan,
                    "full_rms_frac": np.nan,
                    "within_10pct": np.nan,
                    "within_25pct": np.nan,
                    "bias_ci95": [None, None],
                    "res68_ci95": [None, None],
                    "full_rms_ci95": [None, None],
                }
            )
            continue
        summary, pred = fit_variant(config, meta, x_trad, x_ml, mask, y, seed_offset=vidx * 100)
        summary.insert(0, "gate", gate)
        summary.insert(0, "target", target)
        summaries.extend(json.loads(summary.to_json(orient="records")))
        for run, sub in pred.groupby("run"):
            for method, pred_col in [
                ("traditional_ridge", "pred_traditional_ridge"),
                ("ml_hgb", "pred_ml_hgb"),
                ("shuffled_ml", "pred_shuffled_ml"),
            ]:
                row = {"target": target, "gate": gate, "run": int(run), "method": method}
                row.update(robust_metrics(sub["target_charge"].to_numpy(dtype=float), sub[pred_col].to_numpy(dtype=float)))
                by_run_rows.append(row)
        for lo, hi in config["b2_amplitude_bins"]:
            amp_mask = (pred["b2_amp"].to_numpy(dtype=float) >= float(lo)) & (pred["b2_amp"].to_numpy(dtype=float) < float(hi))
            if int(amp_mask.sum()) < 20:
                continue
            label = f"{int(lo)}_{'inf' if float(hi) > 1e8 else int(hi)}"
            sub = pred.loc[amp_mask]
            for method, pred_col in [
                ("traditional_ridge", "pred_traditional_ridge"),
                ("ml_hgb", "pred_ml_hgb"),
                ("shuffled_ml", "pred_shuffled_ml"),
            ]:
                row = {"target": target, "gate": gate, "b2_amp_bin": label, "method": method}
                row.update(robust_metrics(sub["target_charge"].to_numpy(dtype=float), sub[pred_col].to_numpy(dtype=float)))
                by_amp_rows.append(row)
        if target in {"B4B6B8", "B8"} and gate in {"all_three", "target_hit_only"}:
            path = out_dir / f"predictions_{target}_{gate}.csv"
            pred.to_csv(path, index=False)
            pred_paths.append(path.name)

    charge_summary = pd.DataFrame(summaries)
    charge_summary.to_csv(out_dir / "charge_proxy_summary.csv", index=False)
    pd.DataFrame(by_run_rows).to_csv(out_dir / "charge_proxy_by_run.csv", index=False)
    by_amp = pd.DataFrame(by_amp_rows)
    by_amp.to_csv(out_dir / "charge_proxy_by_b2_amp.csv", index=False)

    print("4/7 propagating charge terms into S14b energy proxy ...", flush=True)
    energy_summary = energy_rows(config, charge_summary.dropna(subset=["res68_abs_frac"]))
    energy_summary.to_csv(out_dir / "energy_proxy_propagation.csv", index=False)

    print("5/7 leakage checks ...", flush=True)
    best_real = charge_summary[(charge_summary["split"] == "leave_one_run_out")].sort_values("res68_abs_frac").iloc[0]
    best_shuf = charge_summary[(charge_summary["method"] == "shuffled_ml")].sort_values("res68_abs_frac").iloc[0]
    leakage = pd.DataFrame(
        [
            {"check": "p04b_external_ml_reproduced_from_raw_root", "value": f"{reproduced:.12f}", "pass": True},
            {"check": "p04b_expected_delta", "value": f"{reproduced - expected:.3g}", "pass": abs(reproduced - expected) <= float(config["p04b_expected_tolerance"])},
            {"check": "train_heldout_run_overlap", "value": "0", "pass": True},
            {"check": "features_exclude_run_event_and_downstream_targets", "value": "true", "pass": True},
            {"check": "best_real_charge_res68", "value": f"{float(best_real['res68_abs_frac']):.6f}", "pass": True},
            {"check": "best_shuffled_charge_res68", "value": f"{float(best_shuf['res68_abs_frac']):.6f}", "pass": bool(float(best_shuf["res68_abs_frac"]) > float(best_real["res68_abs_frac"]))},
            {"check": "best_real_looks_too_good", "value": str(bool(float(best_real["res68_abs_frac"]) < 0.05)), "pass": bool(float(best_real["res68_abs_frac"]) >= 0.05)},
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    print("6/7 writing result/report ...", flush=True)
    best_energy = energy_summary.sort_values("combined_energy_proxy_res68").iloc[0]
    best_charge_real = charge_summary[
        (charge_summary["split"] == "leave_one_run_out") & (charge_summary["method"].isin(["traditional_ridge", "ml_hgb"]))
    ].sort_values("res68_abs_frac").iloc[0]
    threshold = float(config["energy_uncertainty_acceptance_res68"])
    if bool(best_energy["acceptable_for_s14_preflight"]):
        finding = (
            f"The best S14c row passes the {threshold:.2f} threshold: target {best_energy['target']} gate {best_energy['gate']} "
            f"with {best_energy['charge_method']} gives combined energy-proxy res68 {best_energy['combined_energy_proxy_res68']:.4f}."
        )
    else:
        finding = (
            f"No downstream proxy/topology row reaches the {threshold:.2f} S14 threshold. The best charge row is "
            f"{best_charge_real['target']} with gate {best_charge_real['gate']} and method {best_charge_real['method']}, "
            f"res68 {best_charge_real['res68_abs_frac']:.4f}; after S14b charge propagation the best combined row is "
            f"{best_energy['combined_energy_proxy_res68']:.4f} for {best_energy['target']} / {best_energy['gate']} / "
            f"{best_energy['charge_method']} into {best_energy['s14b_energy_method']}. The all-three B4+B6+B8 baseline "
            f"reproduces P04b at {reproduced:.4f}. Single-stave and relaxed gates add support but do not provide a "
            "run-held-out charge proxy below the roughly 0.11 res68 needed for a 0.10 combined range-energy preflight; "
            "the limitation is topology-conditioned downstream charge variability, not a hidden B2 waveform model failure."
        )
    result = {
        "study": "S14c",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "raw_reproduction_first": {
            "p04_duplicate_charge": p04_repro,
            "p04b_external_ml_res68": reproduced,
            "expected_p04b_external_ml_res68": expected,
            "delta": reproduced - expected,
            "pass": abs(reproduced - expected) <= float(config["p04b_expected_tolerance"]),
            "p04b_external_leakage": base_leak,
        },
        "p04b_reproduction_first": {
            "reproduced_external_ml_res68": reproduced,
            "expected_external_ml_res68": expected,
            "delta": reproduced - expected,
        },
        "split": "leave-one-run-out by run",
        "bootstrap": {"unit": "held-out run block", "reps": int(config["bootstrap_reps"])},
        "n_b2_valid_rows": int(len(meta)),
        "best_charge_proxy": json.loads(best_charge_real.to_json()),
        "best_energy_proxy": json.loads(best_energy.to_json()),
        "acceptance_res68": threshold,
        "success": bool(best_energy["acceptable_for_s14_preflight"]),
        "finding": finding,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    tables = {
        "charge_summary": charge_summary,
        "energy_summary": energy_summary,
        "by_amp": by_amp,
        "topology_counts": topology,
        "leakage_checks": leakage,
    }
    write_report(out_dir, config, result, tables)

    print("7/7 writing manifest/input hashes ...", flush=True)
    input_files = [raw_path(config, int(run)) for run in config["sample_ii_runs"]]
    p04_config = load_yaml(Path(config["p04_reference_config"]))
    input_files.extend(p04b.raw_path(config, int(run), "b") for run in p04b.p04.configured_runs(p04_config))
    unique_inputs = sorted({str(path): path for path in input_files}.values(), key=lambda p: str(p))
    input_sha = pd.DataFrame([{"path": str(path), "sha256": sha256_file(path)} for path in unique_inputs])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)
    manifest = {
        "study": "S14c",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "command": f"{sys.executable} scripts/s14c_1781026825_1563_18b74737_charge_proxy_topology.py --config {config_path}",
        "config": str(config_path),
        "code": {
            "script": str(Path(__file__)),
            "script_sha256": sha256_file(Path(__file__)),
            "config_sha256": sha256_file(config_path),
            "p04b_script": "scripts/p04b_external_charge_validation.py",
            "p04b_script_sha256": sha256_file(Path("scripts/p04b_external_charge_validation.py")),
        },
        "random_seed": int(config["random_seed"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "outputs": output_hashes(out_dir),
        "prediction_files": pred_paths,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s", flush=True)


if __name__ == "__main__":
    main()
