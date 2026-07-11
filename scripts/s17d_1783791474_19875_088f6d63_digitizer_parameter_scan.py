#!/usr/bin/env python3
"""S17d: detector-response parameter scan for the digitized GEANT4 bridge.

The ticket asks which optical/electronics parameter family in the S17c
digitizer best explains S24a's remaining saturation residual strata.  This
script keeps the S17c raw-ROOT reproduction and supervised benchmark machinery,
scans one parameter family at a time against S24a real-data strata, and then
runs the requested traditional/ML/NN bakeoff on the best matching digitizer.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import uproot

import s17c_1783760285_digitized_g4_waveform_bridge as s17c


ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def md_table(df: pd.DataFrame, cols: List[str], n: int = 999) -> str:
    d = df.loc[:, cols].head(n).copy()
    for col in d.columns:
        if d[col].dtype.kind in "fc":
            d[col] = d[col].map(lambda x: "" if pd.isna(x) else f"{x:.5g}")
        elif d[col].dtype.kind in "iu":
            d[col] = d[col].map(lambda x: f"{int(x)}")
        else:
            d[col] = d[col].astype(str)
    header = "| " + " | ".join(d.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(d.columns)) + " |"
    rows = ["| " + " | ".join(str(row[col]) for col in d.columns) + " |" for _, row in d.iterrows()]
    return "\n".join([header, sep] + rows)


def variant_config(cfg: dict, family: str, value: float) -> dict:
    out = copy.deepcopy(cfg)
    out["digitizer"] = copy.deepcopy(cfg["digitizer"])
    out["saturation_adc"] = float(cfg["saturation_adc"])
    if family == "light_yield_scale":
        out["digitizer"]["light_yield_adc_per_mev"] = float(cfg["digitizer"]["light_yield_adc_per_mev"]) * float(value)
    elif family == "shaping_tau_samples":
        out["digitizer"]["shaping_tau_samples"] = float(value)
    elif family == "pedestal_run_drift_adc":
        out["digitizer"]["pedestal_run_drift_adc"] = float(value)
    elif family == "saturation_adc":
        out["saturation_adc"] = float(value)
    else:
        raise KeyError(family)
    stable = hashlib.sha256(f"{family}:{float(value):.9g}".encode("ascii")).hexdigest()
    out["random_seed"] = int(cfg["random_seed"]) + int(stable[:8], 16) % 100000
    return out


def real_strata_targets(path: Path) -> pd.DataFrame:
    real = pd.read_csv(path)
    real = real[
        (real["method"].astype(str) == "geant4_birks_lookup")
        & (real["subset"].astype(str) == "in_stratum")
    ].copy()
    keep = ["adc_saturation_onset", "late_pulse_shape", "pedestal_drift_proxy_high", "pileup_or_multihit"]
    real = real[real["stratum"].isin(keep)]
    if real.empty:
        real = pd.read_csv(path)
        real = real[(real["method"].astype(str) == "geant4_birks_lookup") & (real["subset"].astype(str) == "in_stratum")].head(4)
    return real[["stratum", "definition", "n", "bias_frac", "res68_frac", "mae_mev"]].reset_index(drop=True)


def truth_birks_prediction(cfg: dict, truth: np.ndarray, wave: np.ndarray) -> np.ndarray:
    charge_by = np.clip(wave, 0, None).sum(axis=2)
    alpha = float(cfg["digitizer"]["light_yield_adc_per_mev"])
    kb = float(cfg["digitizer"].get("birks_kb_cm_per_mev", 0.0))
    dedx = np.nan_to_num(truth[:, :, 1], nan=0.0)
    return (charge_by * (1.0 + kb * dedx) / max(alpha, 1e-9)).sum(axis=1)


def sim_strata_metrics(cfg: dict, meta: pd.DataFrame, truth: np.ndarray, wave: np.ndarray, extra: pd.DataFrame) -> pd.DataFrame:
    y = meta["true_energy_mev"].to_numpy(float)
    pred = truth_birks_prediction(cfg, truth, wave)
    held = meta["pseudo_run"].isin([8, 9, 10]).to_numpy()
    corr = np.clip(wave, 0, None)
    late_fraction = corr[:, :, 10:].sum(axis=(1, 2)) / np.maximum(corr.sum(axis=(1, 2)), 1.0)
    masks = {
        "adc_saturation_onset": extra["saturated_count"].to_numpy(float) > 0,
        "late_pulse_shape": meta["depth_idx"].to_numpy(int) >= 2,
        "pedestal_drift_proxy_high": late_fraction >= np.quantile(late_fraction[held], 0.84),
        "pileup_or_multihit": meta["multiplicity"].to_numpy(int) >= 2,
    }
    rows = []
    for stratum, mask in masks.items():
        use = held & mask
        if int(use.sum()) == 0:
            rows.append({"stratum": stratum, "n": 0, "bias_frac": np.nan, "res68_frac": np.nan, "mae_mev": np.nan})
            continue
        rows.append(
            {
                "stratum": stratum,
                "n": int(use.sum()),
                "bias_frac": s17c.bias(y[use], pred[use]),
                "res68_frac": s17c.res68(y[use], pred[use]),
                "mae_mev": float(np.mean(np.abs(pred[use] - y[use]))),
            }
        )
    return pd.DataFrame(rows)


def scan_digitizer(cfg: dict, meta: pd.DataFrame, truth: np.ndarray, real_targets: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, dict, np.ndarray, pd.DataFrame]:
    base = ("baseline", 1.0, cfg)
    candidates = [base]
    for family, values in cfg["scan"].items():
        for value in values:
            candidates.append((family, float(value), variant_config(cfg, family, float(value))))

    scan_rows = []
    strata_rows = []
    best = None
    best_wave = None
    best_extra = None
    for family, value, ccfg in candidates:
        wave, extra = s17c.digitize(ccfg, meta, truth)
        sim = sim_strata_metrics(ccfg, meta, truth, wave, extra)
        merged = real_targets.merge(sim, on="stratum", suffixes=("_real", "_sim"))
        merged = merged.dropna(subset=["res68_frac_real", "res68_frac_sim"])
        if merged.empty:
            distance = float("inf")
            signed = float("nan")
        else:
            delta = np.log(np.maximum(merged["res68_frac_sim"], 1e-9)) - np.log(np.maximum(merged["res68_frac_real"], 1e-9))
            distance = float(np.sqrt(np.mean(delta * delta)))
            signed = float(delta.mean())
        sat_rate = float((extra["saturated_count"].to_numpy(float) > 0).mean())
        row = {
            "family": family,
            "value": value,
            "distance_log_res68_rms": distance,
            "mean_log_res68_delta_sim_minus_real": signed,
            "sim_saturation_event_fraction": sat_rate,
            "light_yield_adc_per_mev": float(ccfg["digitizer"]["light_yield_adc_per_mev"]),
            "shaping_tau_samples": float(ccfg["digitizer"]["shaping_tau_samples"]),
            "pedestal_run_drift_adc": float(ccfg["digitizer"]["pedestal_run_drift_adc"]),
            "saturation_adc": float(ccfg["saturation_adc"]),
        }
        scan_rows.append(row)
        sim["family"] = family
        sim["value"] = value
        strata_rows.append(sim)
        if best is None or distance < best["distance_log_res68_rms"]:
            best = row
            best_wave = wave
            best_extra = extra
    assert best is not None and best_wave is not None and best_extra is not None
    return (
        pd.DataFrame(scan_rows).sort_values(["distance_log_res68_rms", "family", "value"]).reset_index(drop=True),
        pd.concat(strata_rows, ignore_index=True),
        variant_config(cfg, best["family"], best["value"]) if best["family"] != "baseline" else copy.deepcopy(cfg),
        best_wave,
        best_extra,
    )


def write_report(
    out: Path,
    cfg: dict,
    result: dict,
    raw_counts: pd.DataFrame,
    real_targets: pd.DataFrame,
    scan: pd.DataFrame,
    strata: pd.DataFrame,
    metrics: pd.DataFrame,
    byrun: pd.DataFrame,
    response: pd.DataFrame,
):
    winner = result["winner"]
    best = result["best_digitizer_variant"]
    report = [
        "# S17d: Optical and Electronics Parameter Scan for the Digitized GEANT4 Bridge",
        "",
        "## Abstract",
        "",
        f"Ticket `{cfg['ticket_id']}` scans the S17c digitizer's optical yield, shaping time, pedestal drift, and ADC clipping parameters against the S24a real residual strata. The raw ROOT reproduction gate is direct: `h101/HRDv` from `{cfg['raw_root_dir']}` is baseline-subtracted and counted with the S00 B-stave threshold, reproducing **{result['raw_reproduction']['reproduced_selected_pulses']:,}** selected pulses against **{result['raw_reproduction']['expected_selected_pulses']:,}**. The best response-family match is **{best['family']}={best['value']}** with log-res68 RMS distance **{best['distance_log_res68_rms']:.4f}** to the S24a strata. On the selected digitizer, the benchmark winner written to `result.json` is **{winner['method']}**, res68 **{winner['res68_frac']:.5f}** with 95% run-bootstrap CI **{winner['res68_ci95']}**.",
        "",
        "## Raw ROOT Reproduction",
        "",
        "For each configured run, `HRDv` is reshaped to `(channel, sample)=(8,18)`. The per-channel median over samples 0--3 is subtracted. Even B-stave channels B2/B4/B6/B8 are selected when the corrected maximum exceeds 1000 ADC. This reproduces the ticket-scale number before any GEANT4, digitizer, or model step is run.",
        "",
        md_table(pd.DataFrame([result["raw_reproduction"]]), ["expected_selected_pulses", "reproduced_selected_pulses", "delta", "pass"]),
        "",
        "## Parameterized Digitizer",
        "",
        "GEANT4 `Sci_bar_EDep` and `Sci_bar_TrackLength` are reduced to the mapped even B-stave layers. The baseline S17c charge model is",
        "",
        "\\[ Q_{ij}=\\alpha E_{ij}(1+k_B(dE/dx)_{ij})^{-1}, \\]",
        "",
        "where `i` indexes events and `j` indexes B staves. The electronics response uses a normalized semi-Gaussian waveform with shaping time \\(\\tau\\), pedestal offset \\(p_r\\), event common-mode noise \\(c_i\\), channel noise \\(n_{ijt}\\), afterpulse fraction \\(f_a\\), and clipping level \\(C\\):",
        "",
        "\\[ H_{ijt}=\\operatorname{clip}\\{p_r+c_i+n_{ijt}+A_{ij}g_\\tau(t-t_{0,ij})+f_aA_{ij}g_\\tau(t-t_{0,ij}-3),0,C\\}. \\]",
        "",
        "The scan changes one family at a time relative to the S17c baseline: optical light yield \\(\\alpha\\), shaping time \\(\\tau\\), run pedestal drift width, and ADC clipping ceiling. Each candidate is scored by the RMS log-distance between simulated held-out Birks residual width and the S24a real in-stratum Birks residual width.",
        "",
        "## S24a Residual Targets",
        "",
        md_table(real_targets, ["stratum", "definition", "n", "bias_frac", "res68_frac", "mae_mev"]),
        "",
        "## Parameter Scan Results",
        "",
        md_table(scan, ["family", "value", "distance_log_res68_rms", "mean_log_res68_delta_sim_minus_real", "sim_saturation_event_fraction"], 12),
        "",
        "The scan identifies which detector-response family moves the digitized simulation toward the real-data residual topology. The distance is not an absolute likelihood; it is a structured diagnostic over the S24a strata and is interpreted together with the supervised benchmark below.",
        "",
        "## Supervised Benchmark",
        "",
        "The selected digitizer is then benchmarked under the same pseudo-run split as S17c: pseudo-runs 1--7 train, 8--10 are held out. Bootstrap confidence intervals resample held-out pseudo-runs as blocks. The primary metric is",
        "",
        "\\[ \\mathrm{res68}=Q_{0.68}\\left(\\left|\\frac{\\hat E-E}{E}\\right|\\right), \\]",
        "",
        "with signed median fractional bias and mean absolute error as secondary scores. Methods include the strong traditional digitized Birks inversion, ridge, histogram gradient-boosted trees, MLP, 1D-CNN, and a new gated residual CNN that learns a multiplicative waveform correction to Birks after tabular saturation/shape gating.",
        "",
        md_table(metrics, ["method", "family", "n", "bias_frac", "res68_frac", "res68_ci95", "mae_mev", "mae_mev_ci95"]),
        "",
        "## Held-Out Pseudo-Run Breakdown",
        "",
        md_table(byrun[byrun["method"].isin([winner["method"], "truth_birks_lookup"])], ["pseudo_run", "method", "n", "bias_frac", "res68_frac", "mae_mev"]),
        "",
        "## Sim-vs-Real Method Consistency",
        "",
        md_table(response, ["method", "sim_res68_frac", "real_s24a_res68_frac", "delta_sim_minus_real", "interpretation"]),
        "",
        "## Systematics",
        "",
        "- The scan is one-factor-at-a-time. It isolates families but does not fit a full joint optical/electronics likelihood.",
        "- GEANT4 and HRD events are not event-aligned; S24a comparison is stratum-level rather than row-level.",
        "- Pseudo-runs are deterministic simulation blocks, so bootstrap intervals cover block composition but not true beam-condition drift.",
        "- The optical-yield scan inherits the S24a Birks calibration and does not replace an optical photon simulation.",
        "- Clipping and pedestal drift are applied after waveform synthesis; unmodeled baseline recovery and front-end nonlinearities can still dominate real saturation tails.",
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Artifacts and Reproducibility",
        "",
        "Primary outputs are `result.json`, `REPORT.md`, `manifest.json`, `raw_reproduction_by_run.csv`, `digitizer_parameter_scan.csv`, `scan_strata_metrics.csv`, `selected_method_metrics.csv`, `selected_by_pseudorun.csv`, and `sim_vs_real_method_residuals.csv`.",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/s17d_1783791474_19875_088f6d63_digitizer_parameter_scan.py --config {cfg['_config_arg']}",
        "```",
    ]
    (out / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s17d_1783791474_19875_088f6d63_digitizer_parameter_scan.yaml")
    args = parser.parse_args()
    t0 = time.time()
    cfg_path = ROOT / args.config
    cfg = s17c.load_config(cfg_path)
    cfg["_config_arg"] = args.config
    out = ROOT / cfg["output_dir"]
    out.mkdir(parents=True, exist_ok=True)

    total, raw_counts = s17c.raw_reproduction(cfg)
    if int(total) != int(cfg["expected_selected_pulses"]):
        raise RuntimeError(f"raw reproduction failed: got {total}, expected {cfg['expected_selected_pulses']}")

    meta, truth = s17c.load_sim_truth(cfg)
    real_targets = real_strata_targets(ROOT / cfg["reference_s24a_strata"])
    scan, strata, best_cfg, best_wave, best_extra = scan_digitizer(cfg, meta, truth, real_targets)
    x, feature_names = s17c.make_features(meta, best_wave, best_extra)
    metrics, byrun, _ = s17c.benchmark(best_cfg, meta, truth, best_wave, x)

    real_metrics = pd.read_csv(ROOT / cfg["reference_s24a_metrics"])
    response_rows = []
    for _, row in metrics.iterrows():
        real_method = str(row["method"]).replace("truth_birks_lookup", "geant4_birks_lookup")
        hit = real_metrics[real_metrics["method"].astype(str).eq(real_method)]
        if len(hit):
            real_res68 = float(hit.iloc[0]["res68_frac"])
            response_rows.append(
                {
                    "method": row["method"],
                    "sim_res68_frac": float(row["res68_frac"]),
                    "real_s24a_res68_frac": real_res68,
                    "delta_sim_minus_real": float(row["res68_frac"]) - real_res68,
                    "interpretation": "same method label after Birks-name normalization",
                }
            )
    response = pd.DataFrame(response_rows)

    winner = metrics.iloc[0].to_dict()
    best = scan.iloc[0].to_dict()
    raw_repro = {
        "expected_selected_pulses": int(cfg["expected_selected_pulses"]),
        "reproduced_selected_pulses": int(total),
        "delta": int(total - int(cfg["expected_selected_pulses"])),
        "pass": int(total) == int(cfg["expected_selected_pulses"]),
    }
    result = {
        "study": cfg["study_id"],
        "ticket_id": cfg["ticket_id"],
        "worker": cfg["worker"],
        "raw_reproduction": raw_repro,
        "sim_events_with_scibar_truth": int(len(meta)),
        "train_pseudo_runs": [1, 2, 3, 4, 5, 6, 7],
        "heldout_pseudo_runs": [8, 9, 10],
        "best_digitizer_variant": json_ready(best),
        "selected_digitizer": json_ready(dict(best_cfg["digitizer"], saturation_adc=float(best_cfg["saturation_adc"]))),
        "winner": {
            "method": str(winner["method"]),
            "family": str(winner["family"]),
            "res68_frac": float(winner["res68_frac"]),
            "res68_ci95": json_ready(winner["res68_ci95"]),
            "bias_frac": float(winner["bias_frac"]),
            "mae_mev": float(winner["mae_mev"]),
            "mae_mev_ci95": json_ready(winner["mae_mev_ci95"]),
        },
        "methods_benchmarked": metrics["method"].astype(str).tolist(),
        "feature_names": feature_names,
        "all_metrics": json_ready(metrics.to_dict(orient="records")),
        "parameter_scan_top": json_ready(scan.head(12).to_dict(orient="records")),
        "real_s24a_strata_targets": json_ready(real_targets.to_dict(orient="records")),
        "sim_vs_real_method_residuals": json_ready(response.to_dict(orient="records")),
        "new_architecture": "gated_residual_cnn: 1D waveform convolutions modulated by tabular saturation/shape gates, trained as a multiplicative residual correction to digitized Birks.",
        "finding": (
            f"Raw ROOT reproduction passed exactly at {total:,} selected B-stave pulses. "
            f"The closest one-factor digitizer family to S24a real residual strata is {best['family']}={best['value']} "
            f"(RMS log-res68 distance {best['distance_log_res68_rms']:.4f}). "
            f"On that selected response model, {winner['method']} wins the held-out pseudo-run benchmark with "
            f"res68={float(winner['res68_frac']):.5f}; the conclusion is that {best['family']} is the most plausible "
            "single missing detector-response handle among the scanned families, while real-data deployment remains bounded by the S24a non-event-aligned comparison."
        ),
        "next_tickets": [],
        "runtime_sec": round(time.time() - t0, 1),
    }

    raw_counts.to_csv(out / "raw_reproduction_by_run.csv", index=False)
    real_targets.to_csv(out / "s24a_real_strata_targets.csv", index=False)
    scan.to_csv(out / "digitizer_parameter_scan.csv", index=False)
    strata.to_csv(out / "scan_strata_metrics.csv", index=False)
    metrics.to_csv(out / "selected_method_metrics.csv", index=False)
    byrun.to_csv(out / "selected_by_pseudorun.csv", index=False)
    response.to_csv(out / "sim_vs_real_method_residuals.csv", index=False)
    best_extra.describe().T.to_csv(out / "selected_digitized_waveform_summary.csv")
    (out / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")

    write_report(out, cfg, result, raw_counts, real_targets, scan, strata, metrics, byrun, response)

    inputs = [
        cfg_path,
        Path(cfg["truth_root"]),
        ROOT / cfg["reference_s24a_metrics"],
        ROOT / cfg["reference_s24a_strata"],
        ROOT / cfg["reference_s24a_result"],
    ] + [Path(cfg["raw_root_dir"]) / f"hrdb_run_{run:04d}.root" for run in s17c.configured_runs(cfg)]
    manifest = {
        "study": cfg["study_id"],
        "ticket_id": cfg["ticket_id"],
        "worker": cfg["worker"],
        "git_commit": git_commit(),
        "command": f"/home/billy/anaconda3/bin/python scripts/s17d_1783791474_19875_088f6d63_digitizer_parameter_scan.py --config {args.config}",
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "uproot": uproot.__version__,
            "torch": getattr(s17c.torch, "__version__", "unavailable"),
        },
        "inputs": [{"path": str(path), "bytes": int(path.stat().st_size), "sha256": sha256_file(path)} for path in inputs],
        "outputs": {path.name: sha256_file(path) for path in sorted(out.iterdir()) if path.is_file()},
    }
    (out / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket": cfg["ticket_id"], "out_dir": str(out.relative_to(ROOT)), "winner": result["winner"]["method"], "best_digitizer_family": best["family"], "runtime_sec": result["runtime_sec"]}, indent=2))


if __name__ == "__main__":
    main()
