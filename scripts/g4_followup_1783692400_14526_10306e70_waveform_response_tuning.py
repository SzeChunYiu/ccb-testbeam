#!/usr/bin/env python3
"""G4-04 follow-up waveform-level detector-response tuning.

This ticket-local driver reuses the raw ROOT extraction and GEANT4 truth-prior
utilities from S17b, then adds a response-card scan and a waveform-aware model
panel. The target is still a real-data closure target: duplicate odd readout
converted to MeV through the train-run GEANT4/Birks calibration.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


ROOT = Path(__file__).resolve().parents[1]


def load_s17b():
    path = ROOT / "scripts/s17b_0000000010_1_truthenergy.py"
    spec = importlib.util.spec_from_file_location("s17b_truthenergy", str(path))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


S17B = load_s17b()


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


def md_table(frame: pd.DataFrame, columns: List[str], max_rows: Optional[int] = None) -> str:
    sub = frame[columns].copy()
    if max_rows is not None:
        sub = sub.head(max_rows)
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


def sample_train_indices(train_mask: np.ndarray, max_rows: int, seed: int) -> np.ndarray:
    idx = np.flatnonzero(train_mask)
    if len(idx) <= max_rows:
        return idx
    rng = np.random.default_rng(seed)
    return rng.choice(idx, size=max_rows, replace=False)


def response_features(events: pd.DataFrame, event_wave: np.ndarray, birks_pred: np.ndarray) -> Tuple[np.ndarray, List[str]]:
    base, names = S17B.event_features(events, event_wave)
    wave = event_wave.astype(float)
    positive = np.clip(wave, 0.0, None)
    charge = positive.sum(axis=2)
    total = np.maximum(charge.sum(axis=1), 1.0)
    pre = wave[:, :, :4]
    peak = wave.max(axis=2)
    tail = positive[:, :, 12:].sum(axis=2)
    late_frac = tail.sum(axis=1) / total
    width = (positive > (0.5 * np.maximum(peak, 1.0))[:, :, None]).sum(axis=2)
    asym = (charge[:, 2:].sum(axis=1) - charge[:, :2].sum(axis=1)) / total
    extra = np.column_stack(
        [
            np.log(np.maximum(birks_pred, 1e-6)),
            pre.mean(axis=(1, 2)),
            pre.std(axis=(1, 2)),
            late_frac,
            width.mean(axis=1),
            width.max(axis=1),
            asym,
        ]
    )
    extra_names = [
        "log_traditional_response_scan",
        "pretrigger_mean",
        "pretrigger_std",
        "tail_charge_fraction",
        "mean_halfheight_width",
        "max_halfheight_width",
        "deep_minus_shallow_charge_asymmetry",
    ]
    return np.column_stack([base, extra]), names + extra_names


def tune_response_card(
    events: pd.DataFrame,
    pulses: pd.DataFrame,
    even_edep: np.ndarray,
    y: np.ndarray,
    train_mask: np.ndarray,
    config: dict,
) -> Tuple[np.ndarray, pd.DataFrame, dict]:
    """Grid-search a traditional response card using train runs only.

    The card applies a global light-yield scale, a material-depth slope, and a
    saturation-tail correction to even-channel Birks energy before event
    aggregation. It is intentionally low-dimensional and physics-shaped.
    """
    event_train = events.loc[train_mask, ["event_id"]].copy()
    event_train["target"] = y[train_mask]
    pulse = pulses[["event_id", "stave_idx", "even_amp", "even_peak"]].copy()
    pulse["base"] = even_edep
    pulse["saturation_proxy"] = np.maximum(pulse["even_amp"].to_numpy(dtype=float) - float(config["clean_unsaturated_max_adc"]), 0.0) / 1000.0
    pulse["tail_proxy"] = np.maximum(pulse["even_peak"].to_numpy(dtype=float) - 9.0, 0.0) / 8.0

    rows = []
    best = None
    for light in np.linspace(0.92, 1.08, 9):
        for material_slope in np.linspace(-0.08, 0.08, 9):
            for smear in np.linspace(-0.04, 0.08, 7):
                scale = light * (1.0 + material_slope * (pulse["stave_idx"].to_numpy(dtype=float) - 1.5))
                corr = scale * (1.0 + smear * pulse["saturation_proxy"].to_numpy(dtype=float) * (1.0 + pulse["tail_proxy"].to_numpy(dtype=float)))
                pred_pulse = pulse["base"].to_numpy(dtype=float) * np.maximum(corr, 0.2)
                pred = pd.DataFrame({"event_id": pulse["event_id"], "pred": pred_pulse}).groupby("event_id", sort=False)["pred"].sum()
                frame = event_train.join(pred, on="event_id")
                r68 = S17B.res68(frame["target"].to_numpy(dtype=float), frame["pred"].to_numpy(dtype=float))
                b = S17B.bias(frame["target"].to_numpy(dtype=float), frame["pred"].to_numpy(dtype=float))
                row = {
                    "light_yield_scale": float(light),
                    "material_depth_slope": float(material_slope),
                    "saturation_smear_correction": float(smear),
                    "train_res68_frac": float(r68),
                    "train_bias_frac": float(b),
                }
                rows.append(row)
                if best is None or r68 < best["train_res68_frac"]:
                    best = row
    assert best is not None

    scale = best["light_yield_scale"] * (1.0 + best["material_depth_slope"] * (pulse["stave_idx"].to_numpy(dtype=float) - 1.5))
    corr = scale * (
        1.0
        + best["saturation_smear_correction"]
        * pulse["saturation_proxy"].to_numpy(dtype=float)
        * (1.0 + pulse["tail_proxy"].to_numpy(dtype=float))
    )
    pred_pulse = pulse["base"].to_numpy(dtype=float) * np.maximum(corr, 0.2)
    pred_all = S17B.aggregate_event(pulses, pred_pulse, events)
    return pred_all, pd.DataFrame(rows).sort_values("train_res68_frac").reset_index(drop=True), best


class WaveformGateCNN(nn.Module):
    def __init__(self, n_tab: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(4, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(24, 24, kernel_size=3, padding=1),
            nn.ReLU(),
        )
        self.gate = nn.Sequential(nn.AdaptiveMaxPool1d(1), nn.Flatten(), nn.Linear(24, 24), nn.Sigmoid())
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.head = nn.Sequential(nn.Linear(24 + n_tab + 1, 64), nn.ReLU(), nn.Linear(64, 1))

    def forward(self, wave, tab, log_base):
        z = self.conv(wave)
        z = self.pool(z * self.gate(z).unsqueeze(-1)).squeeze(-1)
        return self.head(torch.cat([z, tab, log_base[:, None]], dim=1)).squeeze(1)


def normalize_wave(w: np.ndarray) -> np.ndarray:
    scale = np.maximum(np.percentile(np.abs(w).reshape(len(w), -1), 95, axis=1), 1.0)
    return (w / scale[:, None, None]).astype(np.float32)


def fit_waveform_gate_cnn(
    event_wave: np.ndarray,
    x: np.ndarray,
    baseline: np.ndarray,
    y: np.ndarray,
    train_mask: np.ndarray,
    config: dict,
) -> Tuple[object, StandardScaler]:
    if torch is None:
        raise RuntimeError("torch unavailable")
    idx = sample_train_indices(train_mask, int(config["cnn_max_train_events"]), int(config["random_seed"]) + 707)
    scaler = StandardScaler().fit(x[idx])
    xs = scaler.transform(x[idx]).astype(np.float32)
    wb = normalize_wave(event_wave[idx].astype(np.float32))
    log_base = np.log(np.maximum(baseline[idx], 1e-6)).astype(np.float32)
    target = (np.log(np.maximum(y[idx], 1e-6)) - log_base).astype(np.float32)
    ds = TensorDataset(torch.from_numpy(wb), torch.from_numpy(xs), torch.from_numpy(log_base), torch.from_numpy(target))
    loader = DataLoader(ds, batch_size=512, shuffle=True)
    torch.manual_seed(int(config["random_seed"]) + 708)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = WaveformGateCNN(x.shape[1]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=8e-4, weight_decay=2e-4)
    loss_fn = nn.SmoothL1Loss()
    model.train()
    for _ in range(int(config["cnn_epochs"])):
        for wave_b, x_b, base_b, y_b in loader:
            wave_b = wave_b.to(device)
            x_b = x_b.to(device)
            base_b = base_b.to(device)
            y_b = y_b.to(device)
            opt.zero_grad()
            loss = loss_fn(model(wave_b, x_b, base_b), y_b)
            loss.backward()
            opt.step()
    model.eval()
    return model, scaler


def predict_waveform_gate_cnn(model: object, scaler: StandardScaler, event_wave: np.ndarray, x: np.ndarray, baseline: np.ndarray) -> np.ndarray:
    device = next(model.parameters()).device
    xs = scaler.transform(x).astype(np.float32)
    out = []
    for start in range(0, len(x), 4096):
        stop = min(start + 4096, len(x))
        w = normalize_wave(event_wave[start:stop].astype(np.float32))
        base = np.log(np.maximum(baseline[start:stop], 1e-6)).astype(np.float32)
        with torch.no_grad():
            pred = model(
                torch.from_numpy(w).to(device),
                torch.from_numpy(xs[start:stop]).to(device),
                torch.from_numpy(base).to(device),
            ).cpu().numpy()
        out.append(base + pred)
    return S17B.exp_clip(np.concatenate(out), lo=-20.0, hi=20.0)


def fit_tabular_panel(x: np.ndarray, y: np.ndarray, train_mask: np.ndarray, config: dict) -> Dict[str, object]:
    idx = sample_train_indices(train_mask, int(config["ml_max_train_events"]), int(config["random_seed"]) + 11)
    target = np.log(np.maximum(y[idx], 1e-6))
    models: Dict[str, object] = {}
    models["ridge"] = make_pipeline(StandardScaler(), Ridge(alpha=2.0))
    models["ridge"].fit(x[idx], target)
    models["gradient_boosted_trees"] = HistGradientBoostingRegressor(
        max_iter=100,
        max_leaf_nodes=31,
        learning_rate=0.05,
        l2_regularization=0.02,
        random_state=int(config["random_seed"]) + 12,
    )
    models["gradient_boosted_trees"].fit(x[idx], target)
    return models


def metric_row(events: pd.DataFrame, y: np.ndarray, pred: np.ndarray, held_mask: np.ndarray, method: str, family: str, config: dict) -> dict:
    idx = np.flatnonzero(held_mask)
    row = {
        "method": method,
        "family": family,
        "n": int(len(idx)),
        "bias_frac": S17B.bias(y[idx], pred[idx]),
        "res68_frac": S17B.res68(y[idx], pred[idx]),
        "mae_mev": float(mean_absolute_error(y[idx], pred[idx])),
    }
    row.update(S17B.run_block_bootstrap(events, y, pred, held_mask, int(config["bootstrap_reps"]), int(config["random_seed"]) + len(method)))
    return row


def by_run_rows(events: pd.DataFrame, y: np.ndarray, predictions: Dict[str, np.ndarray], held_mask: np.ndarray) -> pd.DataFrame:
    rows = []
    for run, sub in events.loc[held_mask].groupby("run"):
        idx = sub.index.to_numpy(dtype=int)
        for method, pred in predictions.items():
            rows.append(
                {
                    "run": int(run),
                    "method": method,
                    "n": int(len(idx)),
                    "bias_frac": S17B.bias(y[idx], pred[idx]),
                    "res68_frac": S17B.res68(y[idx], pred[idx]),
                    "mae_mev": float(mean_absolute_error(y[idx], pred[idx])),
                }
            )
    return pd.DataFrame(rows)


def response_gap_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    baseline = float(metrics.loc[metrics["method"] == "traditional_response_scan", "res68_frac"].iloc[0])
    rows = []
    for _, row in metrics.iterrows():
        rows.append(
            {
                "method": row["method"],
                "res68_frac": float(row["res68_frac"]),
                "relative_reduction_vs_traditional_response_scan": float((baseline - row["res68_frac"]) / baseline),
                "clears_50pct_gate": bool((baseline - row["res68_frac"]) / baseline > 0.5),
            }
        )
    return pd.DataFrame(rows).sort_values("res68_frac").reset_index(drop=True)


def maybe_update_tuned_params(config: dict, result: dict, card: dict) -> None:
    if not result["gate"]["winner_clears_50pct_reduction_gate"]:
        return
    path = ROOT / "docs/reports/tuned_params.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "winner": result["winner"],
        "traditional_response_card": card,
        "updated_by": "testbeam-laptop-3",
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def make_report(
    out_dir: Path,
    config: dict,
    result: dict,
    counts: pd.DataFrame,
    prior: pd.DataFrame,
    truth_event_summary: pd.DataFrame,
    calibration: pd.DataFrame,
    card_scan: pd.DataFrame,
    metrics: pd.DataFrame,
    gap: pd.DataFrame,
    byrun: pd.DataFrame,
    leakage: pd.DataFrame,
) -> None:
    winner = result["winner"]["method"]
    ci = result["winner"]["res68_ci95"]
    prior_present = (ROOT / config["requested_prior_artifact"]).exists()
    report = [
        f"# {config['report_heading']}",
        "",
        "## Abstract",
        "",
        (
            "This study tests whether waveform-level response information closes the remaining detector-response gap "
            "beyond a train-run traditional response-card scan. It rebuilds the selected B-stave pulse population from "
            f"raw ROOT and reproduces {result['raw_reproduction']['reproduced_selected_pulses']:,} selected pulses. "
            "The benchmark uses run-held-out scoring with run-block bootstrap confidence intervals and compares "
            "a response-card traditional method with ridge, histogram gradient-boosted trees, MLP, 1D-CNN, and a new "
            f"waveform-gated response CNN. The held-out winner is **{winner}** with res68={result['winner']['res68_frac']:.5f} "
            f"(95% CI [{ci[0]:.5f}, {ci[1]:.5f}])."
        ),
        "",
        "## Data and Reproduction",
        "",
        "The ROOT-level input is `HRDv`, `EVENTNO`, and `EVT` from the raw B-stack `hrdb_run_*.root` files under `data/root/root`. A selected pulse is an even B-stave channel with baseline-subtracted amplitude above 1000 ADC, where the baseline is the median of samples 0--3.",
        "",
        "| quantity | expected | reproduced | delta | pass |",
        "|---|---:|---:|---:|:---|",
        f"| S00 selected B-stave pulse records | {result['raw_reproduction']['expected_selected_pulses']:,} | {result['raw_reproduction']['reproduced_selected_pulses']:,} | {result['raw_reproduction']['delta']:+,} | {str(result['raw_reproduction']['pass']).lower()} |",
        "",
        md_table(counts, ["run", "group", "events_total", "events_with_selected", "selected_pulses"], max_rows=40),
        "",
        "The ticket referenced `reports/1781212364.2054485.44255c27__g4_04_response_tuning/`. That exact artifact directory was not present in this checkout; the study therefore uses the available S14h/S17b GEANT4 truth-anchor artifacts as the predecessor baseline and records this as a caveat." if not prior_present else "The requested predecessor artifact directory is present and was checked.",
        "",
        "## GEANT4 Truth Prior and Target",
        "",
        "The GEANT4 truth input is the hibeam tree with `Sci_bar_LayerID`, `Sci_bar_EDep`, `Sci_bar_TrackLength`, and `Sci_bar_PDG`. Real HRD events are not event-aligned to simulation, so the truth bridge is a layer prior. For stave \\(j\\) mapped to layer \\(\\ell(j)\\),",
        "",
        "\\[ E_j^{\\mathrm{G4}} = \\operatorname{median}_{i:L_i=\\ell(j)} E_{\\mathrm{dep},i}, \\qquad (dE/dx)_j = \\frac{\\sum_{i:L_i=\\ell(j)} E_{\\mathrm{dep},i}}{\\sum_{i:L_i=\\ell(j)} s_i}. \\]",
        "",
        "Duplicate odd charges on train runs fit a Birks/light-yield response",
        "",
        "\\[ Q_i = \\alpha\\,\\frac{\\Delta E_i}{1+k_B(dE/dx)_i}. \\]",
        "",
        "The closure target for every event is the sum of duplicate odd-readout energies obtained by inverting this train-run response. All learned methods use only even-channel waveforms and derived topology features.",
        "",
        md_table(truth_event_summary, ["truth_tree_entries", "events_with_scibar_hits", "scibar_hit_count", "event_hit_fraction", "event_total_edep_median_mev", "event_total_edep_q16_mev", "event_total_edep_q84_mev"]),
        "",
        md_table(prior, ["stave", "truth_layer_id", "truth_hit_count", "expected_edep_mev", "dedx_mev_cm", "proton_hit_fraction", "deuteron_hit_fraction"]),
        "",
        md_table(calibration, ["stave", "train_pulses", "median_odd_charge_adc_sample", "truth_expected_edep_mev", "truth_dedx_mev_cm", "birks_predicted_charge_adc_sample"]),
        "",
        "## Response-Card Scan",
        "",
        "The strong traditional comparator scans a low-dimensional detector-response card on train runs only:",
        "",
        "\\[ \\widehat E_{ij}=E^{\\mathrm{even}}_{ij}\\,L\\,[1+m(s_j-1.5)]\\,[1+c\\,u_{ij}(1+v_{ij})], \\]",
        "",
        "where \\(E^{\\mathrm{even}}_{ij}\\) is the even-channel Birks-inverted pulse energy, \\(L\\) is light-yield scale, \\(m\\) is a material-depth slope over stave index \\(s_j\\), \\(u\\) is ADC saturation excess above 6500 ADC, and \\(v\\) is a late-peak proxy. The first rows are the best train cards.",
        "",
        md_table(card_scan, ["light_yield_scale", "material_depth_slope", "saturation_smear_correction", "train_res68_frac", "train_bias_frac"], max_rows=12),
        "",
        "## ML and Neural Panel",
        "",
        "Ridge and gradient-boosted trees receive standardized waveform summaries, per-stave charge/amplitude/peak features, multiplicity, saturation count, pretrigger statistics, and the log response-card prediction. The MLP uses the same tabular representation. The 1D-CNN consumes the four selected even-channel 18-sample waveforms plus tabular features. The new architecture, `waveform_gated_response_cnn`, predicts a multiplicative residual on top of the response-card baseline; its convolution channels are gated by waveform maxima before pooling, then concatenated with tabular features and \\(\\log E_{\\mathrm{card}}\\).",
        "",
        "No method receives run id, event id, odd charge, odd waveform, or held-out target information as an input. Splits are by run: calibration runs 31--42 and 64 train the models; analysis runs 44--63 and 65 are held out.",
        "",
        "## Metrics",
        "",
        "The primary residual is \\(r=(\\widehat E-E_{\\mathrm{odd,Birks}})/E_{\\mathrm{odd,Birks}}\\). The primary score is \\(\\operatorname{res68}=P_{68}(|r|)\\). Confidence intervals resample held-out runs with replacement, preserving whole-run correlations.",
        "",
        "## Head-to-Head Results",
        "",
        md_table(metrics.sort_values("res68_frac"), ["method", "family", "n", "bias_frac", "res68_frac", "res68_ci95", "mae_mev", "mae_mev_ci95"]),
        "",
        "## Gate Test",
        "",
        "The ticket gate asks for more than 50% divergence reduction relative to `traditional_response_scan`. Reduction is computed as \\((R_{\\mathrm{trad}}-R_m)/R_{\\mathrm{trad}}\\), where \\(R\\) is held-out res68.",
        "",
        md_table(gap, ["method", "res68_frac", "relative_reduction_vs_traditional_response_scan", "clears_50pct_gate"]),
        "",
        f"Gate result: **{result['gate']['status']}**. `docs/reports/tuned_params.json` was {'updated' if result['gate']['winner_clears_50pct_reduction_gate'] else 'not updated'} because the gate {'cleared' if result['gate']['winner_clears_50pct_reduction_gate'] else 'did not clear'}.",
        "",
        "## Per-Run Held-Out Checks",
        "",
        md_table(byrun[byrun["method"].isin([winner, "traditional_response_scan", "geant4_birks_lookup"])], ["run", "method", "n", "bias_frac", "res68_frac", "mae_mev"]),
        "",
        "## Leakage and Systematics",
        "",
        md_table(leakage, ["check", "value", "pass"]),
        "",
        "Dominant caveats are the absent exact G4-04 predecessor directory in this checkout, the non-event-aligned GEANT4-to-real-data bridge, the use of duplicate odd readout as the closure target, possible optical/electronics response mismatches not modeled by `Sci_bar_EDep`, and limited CPU/GPU training budgets for neural methods. The response-card search is deliberately low-dimensional; a full digitizer with pedestal, time sampling, threshold, saturation, and optical transport would be needed before claiming detector-response closure in absolute simulation space.",
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        config["reproduction_command"],
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/g4_followup_1783692400_14526_10306e70_waveform_response_tuning.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = ROOT / args.config if not Path(args.config).is_absolute() else Path(args.config)
    config = load_config(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    print("1/8 raw ROOT reproduction", flush=True)
    events, pulses, event_wave, _pulse_wave, counts = S17B.extract_tables(config)
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

    held = events["run"].isin(S17B.heldout_runs(config)).to_numpy()
    train = ~held
    pulse_train = ~pulses["run"].isin(S17B.heldout_runs(config)).to_numpy()
    print(f"events={len(events)} pulses={len(pulses)} train_events={int(train.sum())} heldout_events={int(held.sum())}", flush=True)

    print("2/8 GEANT4 truth priors and Birks target", flush=True)
    prior, truth_event_summary = S17B.geant4_truth_layer_priors(config)
    birks = S17B.fit_birks(pulses, prior, pulse_train, "odd_charge")
    calibration = S17B.data_sim_calibration_table(pulses, prior, pulse_train, birks)
    target_pulse = S17B.charge_to_edep(pulses, prior, birks, "odd_charge")
    even_pulse = S17B.charge_to_edep(pulses, prior, birks, "even_charge")
    y = S17B.aggregate_event(pulses, target_pulse, events)
    geant4_birks = S17B.aggregate_event(pulses, even_pulse, events)

    print("3/8 traditional response-card scan", flush=True)
    response_card, card_scan, best_card = tune_response_card(events, pulses, even_pulse, y, train, config)

    print("4/8 feature construction and tabular ML", flush=True)
    x, feature_names = response_features(events, event_wave, response_card)
    models = fit_tabular_panel(x, y, train, config)
    predictions: Dict[str, np.ndarray] = {
        "geant4_birks_lookup": geant4_birks,
        "traditional_response_scan": response_card,
    }
    for name, model in models.items():
        predictions[name] = S17B.exp_clip(model.predict(x))

    print("5/8 MLP", flush=True)
    mlp_model, mlp_scaler = S17B.fit_torch_mlp(x, np.log(np.maximum(y, 1e-6)), train, config, extra_seed=240)
    predictions["mlp"] = S17B.exp_clip(S17B.predict_torch_mlp(mlp_model, mlp_scaler, x))

    print("6/8 1D-CNN", flush=True)
    cnn_status = "trained"
    try:
        cnn_model, cnn_scaler = S17B.fit_cnn(event_wave, x, y, train, config)
        predictions["1d_cnn"] = S17B.predict_cnn(cnn_model, cnn_scaler, event_wave, x)
    except Exception as exc:
        cnn_status = f"failed: {exc}"
        predictions["1d_cnn"] = np.full(len(y), np.nan)

    print("7/8 waveform-gated response CNN", flush=True)
    gate_status = "trained"
    try:
        gate_model, gate_scaler = fit_waveform_gate_cnn(event_wave, x, response_card, y, train, config)
        predictions["waveform_gated_response_cnn"] = predict_waveform_gate_cnn(gate_model, gate_scaler, event_wave, x, response_card)
    except Exception as exc:
        gate_status = f"failed: {exc}"
        predictions["waveform_gated_response_cnn"] = np.full(len(y), np.nan)

    print("8/8 metrics and outputs", flush=True)
    predictions = {name: S17B.clip_to_train_target_range(pred, y, train) for name, pred in predictions.items()}
    families = {
        "geant4_birks_lookup": "traditional_geant4_birks",
        "traditional_response_scan": "traditional_response_card",
        "ridge": "ml_linear",
        "gradient_boosted_trees": "ml_tree",
        "mlp": "neural_tabular",
        "1d_cnn": "neural_waveform",
        "waveform_gated_response_cnn": "new_neural_waveform_response",
    }
    finite_predictions = {k: v for k, v in predictions.items() if np.isfinite(v).all()}
    metrics = pd.DataFrame(
        [metric_row(events, y, pred, held, name, families[name], config) for name, pred in finite_predictions.items()]
    ).sort_values("res68_frac").reset_index(drop=True)
    gap = response_gap_summary(metrics)
    byrun = by_run_rows(events, y, finite_predictions, held)
    winner_row = metrics.iloc[0].to_dict()
    gate_row = gap.loc[gap["method"] == winner_row["method"]].iloc[0]
    gate_clear = bool(gate_row["clears_50pct_gate"])

    leakage = pd.DataFrame(
        [
            {
                "check": "train_heldout_run_overlap",
                "value": str(sorted(set(events.loc[train, "run"].unique()).intersection(set(events.loc[held, "run"].unique())))),
                "pass": set(events.loc[train, "run"].unique()).isdisjoint(set(events.loc[held, "run"].unique())),
            },
            {"check": "raw_reproduction_exact", "value": f"{total} of {expected}", "pass": total == expected},
            {
                "check": "features_exclude_odd_charge_run_event_id",
                "value": ",".join(feature_names),
                "pass": all(bad not in feature_names for bad in ["odd_total_charge", "run", "eventno", "evt"]),
            },
            {"check": "cnn_status", "value": cnn_status, "pass": cnn_status == "trained"},
            {"check": "waveform_gated_response_cnn_status", "value": gate_status, "pass": gate_status == "trained"},
            {
                "check": "requested_prior_artifact_present",
                "value": config["requested_prior_artifact"],
                "pass": (ROOT / config["requested_prior_artifact"]).exists(),
            },
            {"check": "truth_root_used", "value": str(S17B.truth_root_path(config)), "pass": S17B.truth_root_path(config).exists()},
            {
                "check": "truth_layers_mapped_to_even_b_staves",
                "value": ",".join(f"{k}->{v}" for k, v in config["truth_layer_map"].items()),
                "pass": sorted(int(v) for v in config["truth_layer_map"].values()) == [0, 2, 4, 6],
            },
        ]
    )

    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": "testbeam-laptop-3",
        "raw_reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": total,
            "delta": total - expected,
            "pass": total == expected,
        },
        "train_runs": sorted(int(x) for x in events.loc[train, "run"].unique()),
        "heldout_runs": sorted(int(x) for x in events.loc[held, "run"].unique()),
        "n_event_rows_after_valid_charge_cut": int(len(events)),
        "n_pulse_rows_after_valid_charge_cut": int(len(pulses)),
        "traditional_response_card": best_card,
        "winner": {
            "method": str(winner_row["method"]),
            "family": str(winner_row["family"]),
            "res68_frac": float(winner_row["res68_frac"]),
            "res68_ci95": winner_row["res68_ci95"],
            "bias_frac": float(winner_row["bias_frac"]),
            "bias_ci95": winner_row["bias_ci95"],
            "mae_mev": float(winner_row["mae_mev"]),
            "mae_mev_ci95": winner_row["mae_mev_ci95"],
        },
        "gate": {
            "baseline_method": "traditional_response_scan",
            "baseline_res68_frac": float(metrics.loc[metrics["method"] == "traditional_response_scan", "res68_frac"].iloc[0]),
            "winner_relative_reduction": float(gate_row["relative_reduction_vs_traditional_response_scan"]),
            "winner_clears_50pct_reduction_gate": gate_clear,
            "status": "PASS" if gate_clear else "FAIL",
            "tuned_params_path_updated": gate_clear,
        },
        "all_metrics": json.loads(metrics.to_json(orient="records")),
        "response_gap_summary": json.loads(gap.to_json(orient="records")),
        "geant4_truth_anchor": {
            "truth_root": str(S17B.truth_root_path(config)),
            "truth_tree": "hibeam",
            "truth_layer_map": config["truth_layer_map"],
            "truth_track_length_to_cm": float(config["truth_track_length_to_cm"]),
            "truth_edep_statistic": str(config["truth_edep_statistic"]),
            "truth_event_summary": json.loads(truth_event_summary.to_json(orient="records"))[0],
            "truth_layer_priors": json.loads(prior.to_json(orient="records")),
            "birks_fit": birks,
        },
        "new_architecture": "waveform_gated_response_cnn: 1D convolution over four 18-sample even-channel windows, channel gating from waveform maxima, and multiplicative residual prediction around the train-run traditional response card.",
        "finding": (
            f"Raw ROOT reproduction passed exactly at {total:,} selected B-stave pulses. "
            f"The response-card traditional baseline achieved res68={float(metrics.loc[metrics.method == 'traditional_response_scan', 'res68_frac'].iloc[0]):.5f}. "
            f"The held-out winner was {winner_row['method']} with res68={float(winner_row['res68_frac']):.5f}, "
            f"a {float(gate_row['relative_reduction_vs_traditional_response_scan']):.1%} reduction relative to the response-card baseline. "
            f"The 50% gate therefore {'cleared' if gate_clear else 'did not clear'}."
        ),
        "next_tickets": [
            {
                "title": "G4-05: event-aligned digitized GEANT4 waveform closure",
                "body": "Build a small digitizer that turns hibeam_g4 Sci_bar hits into HRD-like 18-sample ADC windows with pedestal, saturation, time smearing, and duplicate-readout response. Benchmark the G4-04 follow-up response-card winner and waveform-gated CNN on simulated waveforms with known truth, then compare residual atoms to real held-out runs.",
            }
        ],
        "runtime_sec": round(time.time() - t0, 1),
    }
    maybe_update_tuned_params(config, result, best_card)

    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    prior.to_csv(out_dir / "geant4_truth_layer_priors.csv", index=False)
    truth_event_summary.to_csv(out_dir / "geant4_truth_event_summary.csv", index=False)
    calibration.to_csv(out_dir / "data_sim_birks_calibration.csv", index=False)
    card_scan.to_csv(out_dir / "response_card_scan.csv", index=False)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    gap.to_csv(out_dir / "response_gap_summary.csv", index=False)
    byrun.to_csv(out_dir / "run_heldout_summary.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    pd.DataFrame([birks]).to_csv(out_dir / "birks_fit.csv", index=False)
    pd.DataFrame(
        [{"quantity": "S00 selected B-stave pulse records", "expected": expected, "reproduced": total, "delta": total - expected, "pass": total == expected}]
    ).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    input_paths = [S17B.raw_path(config, run) for run in S17B.configured_runs(config)] + [S17B.truth_root_path(config)]
    for key in ["reference_s14g_result", "reference_s14h_result"]:
        ref = ROOT / config[key]
        if ref.exists():
            input_paths.append(ref)
    input_sha = pd.DataFrame([{"path": str(path), "bytes": int(path.stat().st_size), "sha256": sha256_file(path)} for path in input_paths])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    make_report(out_dir, config, result, counts, prior, truth_event_summary, calibration, card_scan, metrics, gap, byrun, leakage)

    outputs = [
        "REPORT.md",
        "result.json",
        "input_sha256.csv",
        "counts_by_run.csv",
        "reproduction_match_table.csv",
        "geant4_truth_layer_priors.csv",
        "geant4_truth_event_summary.csv",
        "data_sim_birks_calibration.csv",
        "birks_fit.csv",
        "response_card_scan.csv",
        "method_metrics.csv",
        "response_gap_summary.csv",
        "run_heldout_summary.csv",
        "leakage_checks.csv",
    ]
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": "testbeam-laptop-3",
        "git_commit": git_commit(),
        "command": config["reproduction_command"],
        "config": str(config_path.relative_to(ROOT)),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": getattr(uproot, "__version__", "unknown"),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "sklearn": subprocess.check_output(
                ["/home/billy/anaconda3/bin/python", "-c", "import sklearn; print(sklearn.__version__)"], text=True
            ).strip(),
            "torch": getattr(torch, "__version__", "unavailable") if torch is not None else "unavailable",
        },
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "outputs": {name: sha256_file(out_dir / name) for name in outputs if (out_dir / name).exists()},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s; winner={result['winner']['method']}; gate={result['gate']['status']}", flush=True)


if __name__ == "__main__":
    main()
