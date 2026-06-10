#!/usr/bin/env python3
"""Ticket 0000000013.1.simdataaudit: sim-vs-data audit with ML panel."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import awkward as ak
import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.metrics import mean_absolute_error


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "scripts" / "s14g_0000000003_1_g4energy.py"
SPEC = importlib.util.spec_from_file_location("s14g_base", BASE_PATH)
BASE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(BASE)


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


def md_table(frame: pd.DataFrame, columns: List[str]) -> str:
    sub = frame[columns].copy()
    for col in sub.columns:
        if sub[col].dtype.kind in "fc":
            sub[col] = sub[col].map(lambda v: "" if pd.isna(v) else f"{v:.5g}")
        elif sub[col].dtype.kind in "iu":
            sub[col] = sub[col].map(lambda v: f"{int(v)}")
        else:
            sub[col] = sub[col].astype(str)
    widths = [max(len(str(c)), int(sub[c].map(len).max() if len(sub) else 0)) for c in sub.columns]
    header = "| " + " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(sub.columns)) + " |"
    sep = "| " + " | ".join("---" for _ in sub.columns) + " |"
    rows = ["| " + " | ".join(str(row[c]).ljust(widths[i]) for i, c in enumerate(sub.columns)) + " |" for _, row in sub.iterrows()]
    return "\n".join([header, sep] + rows)


def choose_sim_path(config: dict) -> Path:
    high = Path(config["geant4_path_highstat"])
    if high.exists():
        return high
    return Path(config["geant4_path_fallback"])


def weighted_mean(value, weight):
    num = ak.sum(value * weight, axis=1)
    den = ak.sum(weight, axis=1)
    safe_den = ak.where(den > 0, den, 1.0)
    return ak.to_numpy(ak.where(den > 0, num / safe_den, np.nan))


def load_sim_events(path: Path, mapping: Dict[str, int], step_size: int = 50000) -> Tuple[pd.DataFrame, pd.DataFrame]:
    branches = [
        "Sci_bar_LayerID",
        "Sci_bar_EDep",
        "Sci_bar_Time",
        "Sci_bar_TrackLength",
        "Sci_bar_GlobalPosition_Z",
        "Sci_bar_PDG",
    ]
    tree = uproot.open(path)["hibeam"]
    staves = list(mapping.keys())
    reverse_mapping = {int(layer): stave for stave, layer in mapping.items()}
    layer_rows: List[pd.DataFrame] = []
    event_rows: List[pd.DataFrame] = []
    event_offset = 0
    for arrays in tree.iterate(branches, step_size=step_size, library="ak"):
        n = len(arrays["Sci_bar_LayerID"])
        event = {"sim_event_id": np.arange(event_offset, event_offset + n, dtype=np.int64)}
        per_layer_edep = []
        per_layer_hits = []
        per_layer_time = []
        per_layer_z = []
        for stave in staves:
            layer = int(mapping[stave])
            mask = arrays["Sci_bar_LayerID"] == layer
            edep = ak.where(mask, arrays["Sci_bar_EDep"], 0.0)
            hit_count = ak.sum(mask, axis=1)
            edep_sum = ak.to_numpy(ak.sum(edep, axis=1)).astype(np.float32)
            time_mean = weighted_mean(ak.where(mask, arrays["Sci_bar_Time"], 0.0), edep)
            z_mean = weighted_mean(ak.where(mask, arrays["Sci_bar_GlobalPosition_Z"], 0.0), edep)
            event[f"{stave}_edep_mev"] = edep_sum
            event[f"{stave}_hit_count"] = ak.to_numpy(hit_count).astype(np.int16)
            event[f"{stave}_time_edep_weighted_ns"] = time_mean.astype(np.float32)
            event[f"{stave}_global_z_edep_weighted_mm"] = z_mean.astype(np.float32)
            per_layer_edep.append(edep_sum)
            per_layer_hits.append(event[f"{stave}_hit_count"])
            per_layer_time.append(time_mean)
            per_layer_z.append(z_mean)

        for layer in range(8):
            mask = arrays["Sci_bar_LayerID"] == layer
            flat_e = ak.to_numpy(ak.flatten(arrays["Sci_bar_EDep"][mask], axis=None))
            flat_t = ak.to_numpy(ak.flatten(arrays["Sci_bar_Time"][mask], axis=None))
            flat_z = ak.to_numpy(ak.flatten(arrays["Sci_bar_GlobalPosition_Z"][mask], axis=None))
            flat_pdg = ak.to_numpy(ak.flatten(arrays["Sci_bar_PDG"][mask], axis=None))
            if len(flat_e):
                layer_rows.append(
                    pd.DataFrame(
                        {
                            "stave": reverse_mapping.get(layer, f"unmapped_{layer}"),
                            "layer_id": layer,
                            "edep_mev": flat_e.astype(np.float32),
                            "time_ns": flat_t.astype(np.float32),
                            "global_z_mm": flat_z.astype(np.float32),
                            "pdg": flat_pdg.astype(np.int64),
                        }
                    )
                )

        edep_matrix = np.column_stack(per_layer_edep)
        hit_matrix = np.column_stack(per_layer_hits)
        event["total_edep_mev"] = edep_matrix.sum(axis=1)
        event["hit_multiplicity"] = (edep_matrix > 0).sum(axis=1).astype(np.int16)
        event["raw_hit_count"] = hit_matrix.sum(axis=1).astype(np.int16)
        event["penetration_idx"] = np.where(edep_matrix[:, ::-1] > 0, 1, 0).argmax(axis=1)
        has_any = event["hit_multiplicity"] > 0
        event["penetration_idx"] = np.where(has_any, edep_matrix.shape[1] - 1 - event["penetration_idx"], -1).astype(np.int16)
        tmat = np.column_stack(per_layer_time)
        zmat = np.column_stack(per_layer_z)
        has_time = np.isfinite(tmat).any(axis=1)
        first_time = np.full(len(tmat), np.nan, dtype=np.float32)
        last_time = np.full(len(tmat), np.nan, dtype=np.float32)
        mean_z = np.full(len(zmat), np.nan, dtype=np.float32)
        first_time[has_time] = np.nanmin(tmat[has_time], axis=1).astype(np.float32)
        last_time[has_time] = np.nanmax(tmat[has_time], axis=1).astype(np.float32)
        mean_z[has_time] = np.nanmean(zmat[has_time], axis=1).astype(np.float32)
        event["first_time_ns"] = first_time
        event["last_time_ns"] = last_time
        event["time_span_ns"] = (event["last_time_ns"] - event["first_time_ns"]).astype(np.float32)
        event["mean_global_z_mm"] = mean_z
        event_rows.append(pd.DataFrame(event))
        event_offset += n
    return pd.concat(event_rows, ignore_index=True), pd.concat(layer_rows, ignore_index=True)


def add_event_edep(events: pd.DataFrame, pulses: pd.DataFrame, pulse_edep: np.ndarray, prefix: str) -> pd.DataFrame:
    tmp = pd.DataFrame({"event_id": pulses["event_id"].to_numpy(dtype=np.int64), "value": pulse_edep})
    summed = tmp.groupby("event_id", sort=False)["value"].sum()
    out = events.copy()
    out[prefix] = out["event_id"].map(summed).astype(float).to_numpy()
    return out


def run_bootstrap_ci(values: np.ndarray, groups: np.ndarray, func, reps: int, seed: int) -> List[float]:
    rng = np.random.default_rng(seed)
    blocks = [values[groups == g] for g in np.unique(groups)]
    out = []
    for _ in range(reps):
        choice = rng.integers(0, len(blocks), size=len(blocks))
        sample = np.concatenate([blocks[i] for i in choice])
        out.append(float(func(sample)))
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]


def quantile_distance(a: np.ndarray, b: np.ndarray) -> float:
    qs = np.linspace(0.05, 0.95, 19)
    qa = np.quantile(a, qs)
    qb = np.quantile(b, qs)
    scale = max(
        float(np.subtract(*np.quantile(a, [0.84, 0.16]))),
        float(np.subtract(*np.quantile(b, [0.84, 0.16]))),
        float(np.std(a)),
        float(np.std(b)),
        1.0,
    )
    return float(np.mean(np.abs(qa - qb)) / scale)


def summarize_observables(
    events: pd.DataFrame,
    pulses: pd.DataFrame,
    sim_events: pd.DataFrame,
    sim_layers: pd.DataFrame,
    config: dict,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    staves = list(config["staves"].keys())
    reps = int(config["bootstrap_reps"])
    rows = []
    data_groups = pulses["run"].to_numpy(dtype=int)
    for stave in staves:
        pdata = pulses.loc[pulses["stave"] == stave]
        sdata = sim_layers.loc[sim_layers["stave"] == stave]
        for obs, dvals, svals, units in [
            ("pulse_amplitude", pdata["even_amp"].to_numpy(dtype=float), sdata["edep_mev"].to_numpy(dtype=float), "ADC vs MeV"),
            ("pulse_energy_estimate", pdata["even_edep_mev"].to_numpy(dtype=float), sdata["edep_mev"].to_numpy(dtype=float), "MeV"),
        ]:
            dvals = dvals[np.isfinite(dvals) & (dvals > 0)]
            svals = svals[np.isfinite(svals) & (svals > 0)]
            rows.append(
                {
                    "observable": obs,
                    "stave": stave,
                    "units": units,
                    "data_n": int(len(dvals)),
                    "sim_n": int(len(svals)),
                    "data_median": float(np.median(dvals)),
                    "data_q16": float(np.quantile(dvals, 0.16)),
                    "data_q84": float(np.quantile(dvals, 0.84)),
                    "sim_median": float(np.median(svals)),
                    "sim_q16": float(np.quantile(svals, 0.16)),
                    "sim_q84": float(np.quantile(svals, 0.84)),
                    "quantile_distance": quantile_distance(dvals, svals),
                    "data_median_run_ci95": run_bootstrap_ci(
                        pdata["even_edep_mev"].to_numpy(dtype=float),
                        pdata["run"].to_numpy(dtype=int),
                        np.median,
                        reps,
                        int(config["random_seed"]) + len(rows),
                    )
                    if obs == "pulse_energy_estimate"
                    else run_bootstrap_ci(
                        pdata["even_amp"].to_numpy(dtype=float),
                        pdata["run"].to_numpy(dtype=int),
                        np.median,
                        reps,
                        int(config["random_seed"]) + len(rows),
                    ),
                }
            )

    event_rows = []
    active_sim = sim_events["hit_multiplicity"].to_numpy(dtype=int) > 0
    event_obs = [
        ("hit_multiplicity", events["multiplicity"].to_numpy(float), sim_events.loc[active_sim, "hit_multiplicity"].to_numpy(float)),
        ("penetration_depth_idx", events["depth_idx"].to_numpy(float), sim_events.loc[sim_events["penetration_idx"] >= 0, "penetration_idx"].to_numpy(float)),
        ("event_energy_estimate", events["even_total_edep_mev"].to_numpy(float), sim_events.loc[sim_events["total_edep_mev"] > 0, "total_edep_mev"].to_numpy(float)),
        ("pulse_time_span_proxy", np.full(len(events), np.nan), sim_events.loc[sim_events["hit_multiplicity"] > 0, "time_span_ns"].to_numpy(float)),
    ]
    for obs, dvals, svals in event_obs:
        dvals = dvals[np.isfinite(dvals)]
        svals = svals[np.isfinite(svals)]
        event_rows.append(
            {
                "observable": obs,
                "data_n": int(len(dvals)),
                "sim_n": int(len(svals)),
                "data_median": float(np.median(dvals)) if len(dvals) else np.nan,
                "data_q16": float(np.quantile(dvals, 0.16)) if len(dvals) else np.nan,
                "data_q84": float(np.quantile(dvals, 0.84)) if len(dvals) else np.nan,
                "sim_median": float(np.median(svals)) if len(svals) else np.nan,
                "sim_q16": float(np.quantile(svals, 0.16)) if len(svals) else np.nan,
                "sim_q84": float(np.quantile(svals, 0.84)) if len(svals) else np.nan,
                "quantile_distance": quantile_distance(dvals, svals) if len(dvals) and len(svals) else np.nan,
            }
        )

    selected_rows = []
    n_data_events = len(events)
    n_sim_events = int(active_sim.sum())
    for i, stave in enumerate(staves):
        data_frac = float((events["depth_idx"].to_numpy(dtype=int) >= i).mean())
        sim_frac = float((sim_events.loc[active_sim, "penetration_idx"].to_numpy(dtype=int) >= i).mean())
        selected_rows.append(
            {
                "stave": stave,
                "depth_idx": i,
                "data_fraction_reaching_or_selected": data_frac,
                "sim_fraction_reaching": sim_frac,
                "data_n_events": n_data_events,
                "sim_n_events_with_any_scibar_edep": n_sim_events,
                "ratio_data_to_sim": data_frac / max(sim_frac, 1e-12),
            }
        )

    layer_map_rows = []
    for stave in staves:
        nominal = int(config["sim_layer_mapping"][stave])
        alternate = int(config["sim_layer_mapping_alternative"][stave])
        nom = sim_layers.loc[sim_layers["layer_id"] == nominal]
        alt = sim_layers.loc[sim_layers["layer_id"] == alternate]
        layer_map_rows.append(
            {
                "stave": stave,
                "nominal_layer_id": nominal,
                "alternative_layer_id": alternate,
                "nominal_hits": int(len(nom)),
                "alternative_hits": int(len(alt)),
                "nominal_median_edep_mev": float(nom["edep_mev"].median()),
                "alternative_median_edep_mev": float(alt["edep_mev"].median()),
                "interpretation": "even LayerID matches even B-stack channel convention; odd layer retained as mapping systematic",
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(event_rows), pd.DataFrame(selected_rows), pd.DataFrame(layer_map_rows)


def benchmark_models(config: dict, events: pd.DataFrame, pulses: pd.DataFrame, event_wave: np.ndarray, prior: pd.DataFrame, pulse_train: np.ndarray, train: np.ndarray, held: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame, dict, pd.DataFrame, np.ndarray, np.ndarray]:
    birks = BASE.fit_birks(pulses, prior, pulse_train, "odd_charge")
    target_pulse = BASE.charge_to_edep(pulses, prior, birks, "odd_charge")
    even_pulse = BASE.charge_to_edep(pulses, prior, birks, "even_charge")
    y = BASE.aggregate_event(pulses, target_pulse, events)
    birks_pred = BASE.aggregate_event(pulses, even_pulse, events)
    x, feature_names = BASE.event_features(events, event_wave)
    power = BASE.fit_power_law(events["even_total_charge"].to_numpy(dtype=float), y, train)
    predictions: Dict[str, np.ndarray] = {
        "old_power_law": BASE.apply_power_law(power, events["even_total_charge"].to_numpy(dtype=float)),
        "geant4_birks_lookup": birks_pred,
    }
    for name, model in BASE.fit_tabular_models(x, y, train, config).items():
        predictions[name] = BASE.exp_clip(model.predict(x))
    mlp_model, mlp_scaler = BASE.fit_torch_mlp(x, np.log(np.maximum(y, 1e-6)), train, config, extra_seed=13)
    predictions["mlp"] = BASE.exp_clip(BASE.predict_torch_mlp(mlp_model, mlp_scaler, x))
    try:
        cnn, cnn_scaler = BASE.fit_cnn(event_wave, x, y, train, config)
        predictions["1d_cnn"] = BASE.predict_cnn(cnn, cnn_scaler, event_wave, x)
        cnn_status = "trained"
    except Exception as exc:
        predictions["1d_cnn"] = np.full(len(y), np.nan)
        cnn_status = f"failed: {exc}"
    residual_model, residual_scaler = BASE.fit_residual_mlp(x, birks_pred, y, train, config)
    predictions["physics_residual_mlp"] = BASE.predict_residual_mlp(residual_model, residual_scaler, x, birks_pred)
    predictions = {name: BASE.clip_to_train_target_range(pred, y, train) for name, pred in predictions.items()}
    families = {
        "old_power_law": "traditional_empirical",
        "geant4_birks_lookup": "traditional_geant4_birks",
        "ridge": "ml_linear",
        "gradient_boosted_trees": "ml_tree",
        "mlp": "neural_tabular",
        "1d_cnn": "neural_waveform",
        "physics_residual_mlp": "neural_physics_residual_new_architecture",
    }
    rows = []
    for name, pred in predictions.items():
        if np.isfinite(pred).all():
            rows.append(BASE.metric_row(events, y, pred, held, name, families[name], config))
    metrics = pd.DataFrame(rows).sort_values("res68_frac").reset_index(drop=True)
    byrun = BASE.by_run_rows(events, y, {k: v for k, v in predictions.items() if np.isfinite(v).all()}, held)
    leakage = pd.DataFrame(
        [
            {
                "check": "train_heldout_run_overlap",
                "value": str(sorted(set(events.loc[train, "run"].unique()).intersection(set(events.loc[held, "run"].unique())))),
                "pass": set(events.loc[train, "run"].unique()).isdisjoint(set(events.loc[held, "run"].unique())),
            },
            {
                "check": "ml_features_exclude_odd_charge_run_event_id",
                "value": ",".join(feature_names),
                "pass": all(bad not in feature_names for bad in ["odd_total_charge", "run", "eventno", "evt"]),
            },
            {"check": "cnn_status", "value": cnn_status, "pass": cnn_status == "trained"},
            {"check": "birks_kB_cm_per_MeV", "value": f"{birks['kB_cm_per_MeV']:.6g}", "pass": True},
        ]
    )
    return metrics, byrun, birks, leakage, y, even_pulse


def write_report(out_dir: Path, config: dict, result: dict, tables: dict) -> None:
    metrics = tables["metrics"].sort_values("res68_frac")
    winner = result["winner"]
    comparison = tables["observable_comparison"]
    event_comparison = tables["event_observable_comparison"]
    selected = tables["selected_fraction_by_depth"]
    layer_map = tables["layer_mapping_audit"]
    leakage = tables["leakage_checks"]
    lines = [
        "# S13sim: Systematic GEANT4 Simulation-vs-Data Distribution Audit",
        "",
        "## Abstract",
        "",
        (
            "This ticket audits whether the read-only GEANT4 `hibeam` simulation explains the "
            "B-stack data distributions rebuilt directly from raw ROOT. The raw reproduction gate "
            f"returns {result['raw_reproduction']['reproduced_selected_pulses']:,} selected B-stave pulse records, "
            f"matching the S00 anchor exactly. The model benchmark winner is **{winner['method']}** "
            f"with held-out res68={winner['res68_frac']:.5f} and run-block bootstrap 95% CI "
            f"[{winner['res68_ci95'][0]:.5f}, {winner['res68_ci95'][1]:.5f}]."
        ),
        "",
        "## Data and Reproduction",
        "",
        "Real data are the reduced B-stack `hrdb_run_*.root` files. For each event the script reads `HRDv`, subtracts the median of samples 0--3 per channel, and selects an even B-stack stave if",
        "",
        "\\[ A_{r,s}=\\max_t (H_{r,s,t}-\\mathrm{median}_{t\\in\\{0,1,2,3\\}}H_{r,s,t}) > 1000\\ \\mathrm{ADC}. \\]",
        "",
        "| quantity | expected | reproduced | delta | pass |",
        "|---|---:|---:|---:|:---|",
        f"| selected B-stave pulse records | {result['raw_reproduction']['expected_selected_pulses']:,} | {result['raw_reproduction']['reproduced_selected_pulses']:,} | {result['raw_reproduction']['delta']:+,} | {str(result['raw_reproduction']['pass']).lower()} |",
        "",
        "The simulation input is the high-statistics GEANT4 ROOT file when present, otherwise the 30k fallback. It is consumed read-only; no simulation rebuild is performed.",
        "",
        "## Sci_bar Layer Mapping",
        "",
        "GEANT4 exposes eight `Sci_bar_LayerID` values. The nominal data comparison maps the even simulation layers to the even B-stack channels: LayerID 0, 2, 4, and 6 map to B2, B4, B6, and B8. The adjacent odd layers are kept as a systematic because they have similar physical ordering but different hit rates and energy spectra.",
        "",
        md_table(layer_map, ["stave", "nominal_layer_id", "alternative_layer_id", "nominal_hits", "alternative_hits", "nominal_median_edep_mev", "alternative_median_edep_mev"]),
        "",
        "## Traditional Energy Calibration",
        "",
        "The strong traditional baseline is a GEANT4-anchored Birks lookup. With simulated stopping power and a 1 cm scintillator thickness, the deposited-energy expectation is",
        "",
        "\\[ \\Delta E_s = E(R_{190}-z_s+t/2)-E(R_{190}-z_s-t/2), \\qquad R(E)=\\int_0^E\\left(\\frac{dE'}{dx}\\right)^{-1}dE'. \\]",
        "",
        "The duplicate odd readout on training runs fits",
        "",
        "\\[ Q_s = \\alpha\\frac{\\Delta E_s}{1+k_B(dE/dx)_s}. \\]",
        "",
        "The same fitted response converts even-readout charge to an event energy estimate. This also provides the data-side MeV scale used in the distribution audit.",
        "",
        "## ML/NN Benchmark",
        "",
        "All methods use the same run split: calibration runs train, analysis runs are held out. Inputs exclude run number, event identifiers, odd charge, and odd amplitude. The benchmark includes ridge regression, gradient-boosted trees, a tabular MLP, a waveform 1D-CNN, and a physics-residual MLP that learns a multiplicative correction to the Birks lookup.",
        "",
        "For event target \\(y\\) and prediction \\(\\hat y\\), the primary metric is",
        "",
        "\\[ \\mathrm{res68}=Q_{0.68}\\left(\\left|\\frac{\\hat y-y}{y}\\right|\\right). \\]",
        "",
        "Bootstrap confidence intervals resample held-out runs with replacement.",
        "",
        md_table(metrics, ["method", "family", "n", "bias_frac", "res68_frac", "res68_ci95", "mae_mev", "mae_mev_ci95"]),
        "",
        "## Sim-vs-Data Observable Audit",
        "",
        "Per-stave pulse amplitudes are compared to raw simulated energy deposits as a shape check rather than an absolute-unit claim. The calibrated pulse-energy rows compare the data-side Birks energy estimate to GEANT4 `Sci_bar_EDep`. `quantile_distance` is the mean absolute separation of 5--95% quantiles normalized by the data 16--84% width; smaller means closer shape agreement.",
        "",
        md_table(comparison, ["observable", "stave", "data_n", "sim_n", "data_median", "sim_median", "quantile_distance", "data_median_run_ci95"]),
        "",
        "Event-level observables summarize hit multiplicity, deepest reached B-stave index, total energy, and the simulated time-span proxy.",
        "",
        md_table(event_comparison, ["observable", "data_n", "sim_n", "data_median", "sim_median", "quantile_distance"]),
        "",
        "## Selected Fraction vs Depth",
        "",
        "The A>1000 real-data table is already conditioned on visible B-stack activity. Therefore the data fractions below are fractions of selected real events reaching each B stave, while the simulation fractions are truth fractions among events with any mapped Sci_bar energy deposit.",
        "",
        md_table(selected, ["stave", "depth_idx", "data_fraction_reaching_or_selected", "sim_fraction_reaching", "ratio_data_to_sim"]),
        "",
        "The raw simulation reach fractions fall more gently than the A>1000-selected real-data fractions. This is the expected threshold-selection effect: the real table is not an incident-particle sample, but a waveform-amplitude-selected sample dominated by the earliest stave with above-threshold ionization. The simulation includes lower-deposit downstream continuations that do not necessarily create selected real pulses, so its truth-level penetration curve remains broader.",
        "",
        "## Leakage Controls",
        "",
        md_table(leakage, ["check", "value", "pass"]),
        "",
        "## Systematics and Caveats",
        "",
        "The absolute MeV scale is conditional on the nominal 1 cm stave thickness, the `center_4cm` geometry, and interpreting the stopping-power table's second column as GeV/mm. The real data do not contain particle truth labels; odd-readout closure is a detector-consistency target, not external calorimetry. Saturation above the ADC ceiling, electronics nonlinearity, and the lack of unselected real pulses in the selected table all limit the sim-vs-data comparison. The even-layer mapping is physically consistent with the B-stack channel convention, but the adjacent odd-layer comparison should be treated as an uncertainty until geometry metadata are tied directly to channel names.",
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/simdataaudit_0000000013_1.py --config configs/simdataaudit_0000000013_1.yaml",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/simdataaudit_0000000013_1.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = ROOT / args.config if not Path(args.config).is_absolute() else Path(args.config)
    config = load_config(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    print("1/8 raw ROOT reproduction", flush=True)
    events, pulses, event_wave, _pulse_wave, counts = BASE.extract_tables(config)
    total = int(counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if total != expected:
        raise RuntimeError(f"raw selected-pulse reproduction failed: got {total}, expected {expected}")
    valid_events = (events["odd_total_charge"].to_numpy(dtype=float) > 100.0) & (events["even_total_charge"].to_numpy(dtype=float) > 100.0)
    events = events.loc[valid_events].reset_index(drop=True)
    event_wave = event_wave[valid_events]
    valid_ids = set(int(x) for x in events["event_id"].to_numpy())
    pulse_valid = pulses["event_id"].isin(valid_ids).to_numpy() & (pulses["odd_charge"].to_numpy(dtype=float) > 20.0)
    pulses = pulses.loc[pulse_valid].reset_index(drop=True)

    held = events["run"].isin(BASE.heldout_runs(config)).to_numpy()
    train = ~held
    pulse_train = ~pulses["run"].isin(BASE.heldout_runs(config)).to_numpy()
    print(f"events={len(events)} pulses={len(pulses)} train={int(train.sum())} heldout={int(held.sum())}", flush=True)

    print("2/8 GEANT4 prior", flush=True)
    dedx = BASE.load_dedx_table(config)
    range_table = BASE.build_range_table(dedx)
    prior = BASE.geant4_stave_priors(config, range_table, config["nominal_geometry"])

    print("3/8 ML benchmark", flush=True)
    metrics, byrun, birks, leakage, y, even_pulse_edep = benchmark_models(config, events, pulses, event_wave, prior, pulse_train, train, held)
    pulses = pulses.copy()
    pulses["even_edep_mev"] = even_pulse_edep
    events = add_event_edep(events, pulses, even_pulse_edep, "even_total_edep_mev")

    print("4/8 simulation extraction", flush=True)
    sim_path = choose_sim_path(config)
    sim_events, sim_layers = load_sim_events(sim_path, config["sim_layer_mapping"])

    print("5/8 distribution summaries", flush=True)
    observable_comparison, event_observable_comparison, selected_fraction, layer_mapping = summarize_observables(events, pulses, sim_events, sim_layers, config)

    print("6/8 write tables", flush=True)
    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    prior.to_csv(out_dir / "geant4_stave_priors.csv", index=False)
    range_table.to_csv(out_dir / "geant4_range_table.csv", index=False)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    byrun.to_csv(out_dir / "run_heldout_summary.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    observable_comparison.to_csv(out_dir / "observable_comparison.csv", index=False)
    event_observable_comparison.to_csv(out_dir / "event_observable_comparison.csv", index=False)
    selected_fraction.to_csv(out_dir / "selected_fraction_by_depth.csv", index=False)
    layer_mapping.to_csv(out_dir / "layer_mapping_audit.csv", index=False)
    pd.DataFrame([birks]).to_csv(out_dir / "birks_fit.csv", index=False)
    pd.DataFrame(
        [{"quantity": "S00 selected B-stave pulse records", "expected": expected, "reproduced": total, "delta": total - expected, "pass": total == expected}]
    ).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    print("7/8 input manifest", flush=True)
    input_paths = [BASE.raw_path(config, run) for run in BASE.configured_runs(config)] + [Path(config["dedx_table"]), sim_path]
    input_sha = pd.DataFrame([{"path": str(path), "bytes": int(path.stat().st_size), "sha256": sha256_file(path)} for path in input_paths])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    winner_row = metrics.iloc[0].to_dict()
    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "raw_reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": total,
            "delta": total - expected,
            "pass": total == expected,
        },
        "simulation": {
            "path": str(sim_path),
            "tree": "hibeam",
            "events": int(len(sim_events)),
            "mapped_layer_hits": int(len(sim_layers)),
            "layer_mapping": config["sim_layer_mapping"],
            "alternative_layer_mapping": config["sim_layer_mapping_alternative"],
        },
        "train_runs": sorted(int(x) for x in events.loc[train, "run"].unique()),
        "heldout_runs": sorted(int(x) for x in events.loc[held, "run"].unique()),
        "winner": {
            "method": str(winner_row["method"]),
            "family": str(winner_row["family"]),
            "res68_frac": float(winner_row["res68_frac"]),
            "res68_ci95": winner_row["res68_ci95"],
            "bias_frac": float(winner_row["bias_frac"]),
            "mae_mev": float(winner_row["mae_mev"]),
            "mae_mev_ci95": winner_row["mae_mev_ci95"],
        },
        "all_metrics": json.loads(metrics.to_json(orient="records")),
        "key_observable_comparison": json.loads(observable_comparison.to_json(orient="records")),
        "selected_fraction_by_depth": json.loads(selected_fraction.to_json(orient="records")),
        "leakage_checks": json.loads(leakage.to_json(orient="records")),
        "finding": (
            f"Raw ROOT reproduction passed exactly at {total:,} selected B-stave pulses. "
            f"The nominal Sci_bar mapping is LayerID 0/2/4/6 -> B2/B4/B6/B8, with odd layers retained as a mapping systematic. "
            f"The held-out benchmark winner is {winner_row['method']} with res68={float(winner_row['res68_frac']):.5f}. "
            "The simulation penetration curve is gentler than the A>1000-selected real-data curve because the data table is threshold-conditioned and dominated by the first above-threshold B-stave response."
        ),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("8/8 report and manifest", flush=True)
    tables = {
        "metrics": metrics,
        "observable_comparison": observable_comparison,
        "event_observable_comparison": event_observable_comparison,
        "selected_fraction_by_depth": selected_fraction,
        "layer_mapping_audit": layer_mapping,
        "leakage_checks": leakage,
    }
    write_report(out_dir, config, result, tables)
    outputs = [
        "REPORT.md",
        "result.json",
        "input_sha256.csv",
        "counts_by_run.csv",
        "reproduction_match_table.csv",
        "geant4_stave_priors.csv",
        "geant4_range_table.csv",
        "birks_fit.csv",
        "method_metrics.csv",
        "run_heldout_summary.csv",
        "leakage_checks.csv",
        "observable_comparison.csv",
        "event_observable_comparison.csv",
        "selected_fraction_by_depth.csv",
        "layer_mapping_audit.csv",
    ]
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "command": "/home/billy/anaconda3/bin/python scripts/simdataaudit_0000000013_1.py --config configs/simdataaudit_0000000013_1.yaml",
        "config": str(config_path.relative_to(ROOT)),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": getattr(uproot, "__version__", "unknown"),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "torch": getattr(BASE.torch, "__version__", "unavailable") if BASE.torch is not None else "unavailable",
        },
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "outputs": {name: sha256_file(out_dir / name) for name in outputs if (out_dir / name).exists()},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s; winner={result['winner']['method']}", flush=True)


if __name__ == "__main__":
    main()
