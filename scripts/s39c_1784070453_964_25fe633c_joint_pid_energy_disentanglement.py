#!/usr/bin/env python3
"""S39c joint PID, energy, and timing benchmark under pile-up/saturation."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import confusion_matrix, mean_absolute_error, roc_auc_score
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import s33a_1784062062_882_024708b9_rate_baseline_energy_pid_benchmark as s33  # noqa: E402


def sigma68(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return float("nan")
    return float((np.percentile(x, 84) - np.percentile(x, 16)) / 2.0)


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), 1e-5, 1 - 1e-5)
    return np.log(p / (1 - p))


def timing_target(events: pd.DataFrame, event_wave: np.ndarray) -> np.ndarray:
    """Train-frozen proxy target: charge-weighted selected peak sample."""
    charge = np.clip(event_wave, 0.0, None).sum(axis=2)
    peak = event_wave.argmax(axis=2).astype(float)
    weight = charge / np.maximum(charge.sum(axis=1, keepdims=True), 1.0)
    return (weight * peak).sum(axis=1)


def pedestal_state(events: pd.DataFrame, counts: pd.DataFrame, train_mask: np.ndarray) -> np.ndarray:
    rms_by_run = counts.set_index("run")["baseline_rms_adc"]
    rms = events["run"].map(rms_by_run).to_numpy(dtype=float)
    q1, q2 = np.quantile(rms[train_mask], [1 / 3, 2 / 3])
    return np.where(rms <= q1, "low", np.where(rms <= q2, "mid", "high"))


def coverage(y: np.ndarray, pred: np.ndarray, sigma: np.ndarray, mask: np.ndarray) -> dict:
    z = np.abs(np.asarray(pred)[mask] - np.asarray(y)[mask]) <= 1.64 * np.maximum(np.asarray(sigma)[mask], 1e-9)
    return {"nominal": 0.90, "empirical": float(z.mean()), "abs_error": float(abs(z.mean() - 0.90)), "n": int(mask.sum())}


class MultiTaskCNN(nn.Module):
    def __init__(self, n_tab: int, out_dim: int = 3):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(4, 16, 3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 24, 3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Linear(24 + n_tab, 64), nn.ReLU(), nn.Linear(64, out_dim))

    def forward(self, wave, tab):
        z = self.conv(wave).squeeze(-1)
        return self.head(torch.cat([z, tab], dim=1))


class TinyTransformer(nn.Module):
    def __init__(self, n_tab: int, out_dim: int = 3):
        super().__init__()
        self.proj = nn.Linear(4, 24)
        enc = nn.TransformerEncoderLayer(d_model=24, nhead=4, dim_feedforward=48, batch_first=True, dropout=0.05)
        self.enc = nn.TransformerEncoder(enc, num_layers=1)
        self.head = nn.Sequential(nn.Linear(24 + n_tab, 64), nn.ReLU(), nn.Linear(64, out_dim))

    def forward(self, wave, tab):
        seq = wave.transpose(1, 2)
        z = self.enc(self.proj(seq)).mean(dim=1)
        return self.head(torch.cat([z, tab], dim=1))


def torch_fit(model: nn.Module, event_wave: np.ndarray, x: np.ndarray, y: np.ndarray, train: np.ndarray, cfg: dict, seed: int):
    idx = np.flatnonzero(train)
    rng = np.random.default_rng(seed)
    if len(idx) > int(cfg["cnn_max_train_events"]):
        idx = rng.choice(idx, size=int(cfg["cnn_max_train_events"]), replace=False)
    scaler = StandardScaler().fit(x[idx])
    xs = scaler.transform(x[idx]).astype(np.float32)
    w = event_wave[idx].astype(np.float32)
    scale = np.maximum(np.percentile(np.abs(w).reshape(len(w), -1), 95, axis=1), 1.0)
    w = (w / scale[:, None, None]).astype(np.float32)
    ds = TensorDataset(torch.from_numpy(w), torch.from_numpy(xs), torch.from_numpy(y[idx].astype(np.float32)))
    loader = DataLoader(ds, batch_size=512, shuffle=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(seed)
    model = model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=8e-4, weight_decay=2e-4)
    loss_fn = nn.SmoothL1Loss()
    model.train()
    for _ in range(int(cfg["cnn_epochs"])):
        for wb, xb, yb in loader:
            wb, xb, yb = wb.to(device), xb.to(device), yb.to(device)
            opt.zero_grad()
            loss = loss_fn(model(wb, xb), yb)
            loss.backward()
            opt.step()
    model.eval()
    return model, scaler


def torch_predict(model, scaler, event_wave: np.ndarray, x: np.ndarray) -> np.ndarray:
    device = next(model.parameters()).device
    xs = scaler.transform(x).astype(np.float32)
    outs = []
    for start in range(0, len(x), 4096):
        stop = min(start + 4096, len(x))
        w = event_wave[start:stop].astype(np.float32)
        scale = np.maximum(np.percentile(np.abs(w).reshape(len(w), -1), 95, axis=1), 1.0)
        w = (w / scale[:, None, None]).astype(np.float32)
        with torch.no_grad():
            outs.append(model(torch.from_numpy(w).to(device), torch.from_numpy(xs[start:stop]).to(device)).cpu().numpy())
    return np.vstack(outs)


def run_bootstrap(events: pd.DataFrame, held: np.ndarray, labels: np.ndarray, y_e: np.ndarray, y_t: np.ndarray, pred: dict, reps: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    idx0 = np.flatnonzero(held & (labels >= 0))
    blocks = [idx0[events.iloc[idx0]["run"].to_numpy(dtype=int) == r] for r in sorted(events.iloc[idx0]["run"].unique())]
    vals = {"pid_auc": [], "energy_sigma68": [], "energy_bias": [], "timing_sigma68_ns": []}
    for _ in range(reps):
        idx = np.concatenate([blocks[i] for i in rng.integers(0, len(blocks), len(blocks))])
        if len(np.unique(labels[idx])) < 2:
            continue
        vals["pid_auc"].append(float(roc_auc_score(labels[idx], pred["pid"][idx])))
        vals["energy_sigma68"].append(sigma68((pred["energy"][idx] - y_e[idx]) / np.maximum(y_e[idx], 1e-9)))
        vals["energy_bias"].append(float(np.median((pred["energy"][idx] - y_e[idx]) / np.maximum(y_e[idx], 1e-9))))
        vals["timing_sigma68_ns"].append(10.0 * sigma68(pred["timing"][idx] - y_t[idx]))
    return {f"{k}_ci95": [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in vals.items()}


def metrics_for(events: pd.DataFrame, held: np.ndarray, labels: np.ndarray, y_e: np.ndarray, y_t: np.ndarray, pred: dict, cfg: dict, family: str) -> dict:
    idx = held & (labels >= 0)
    frac = (pred["energy"][idx] - y_e[idx]) / np.maximum(y_e[idx], 1e-9)
    y = labels[idx]
    s = pred["pid"][idx]
    pp = (s >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pp, labels=[0, 1]).ravel()
    auc = float(roc_auc_score(y, s))
    row = {
        "method": pred["method"],
        "family": family,
        "n": int(idx.sum()),
        "pid_auc": auc,
        "pid_balanced_error": float(1.0 - 0.5 * (tp / max(tp + fn, 1) + tn / max(tn + fp, 1))),
        "energy_bias_frac": float(np.median(frac)),
        "energy_sigma68_frac": sigma68(frac),
        "energy_mae_mev": float(mean_absolute_error(y_e[idx], pred["energy"][idx])),
        "timing_bias_ns": float(10.0 * np.median(pred["timing"][idx] - y_t[idx])),
        "timing_sigma68_ns": float(10.0 * sigma68(pred["timing"][idx] - y_t[idx])),
    }
    row.update(run_bootstrap(events, held, labels, y_e, y_t, pred, int(cfg["bootstrap_reps"]), int(cfg["random_seed"]) + len(pred["method"])))
    return row


def md_table(df: pd.DataFrame, cols: List[str], limit: int | None = None) -> str:
    view = df[cols].head(limit).copy() if limit else df[cols].copy()
    for col in view.columns:
        if view[col].dtype.kind in "fc":
            view[col] = view[col].map(lambda v: "nan" if pd.isna(v) else f"{v:.5g}")
    return view.to_markdown(index=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/s39c_1784070453_964_25fe633c_joint_pid_energy_disentanglement.yaml")
    args = ap.parse_args()
    t0 = time.time()
    cfg_path = ROOT / args.config
    cfg = s33.load_config(cfg_path)
    out = ROOT / cfg["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "claimed_ticket.txt").write_text(cfg["ticket_id"] + "\n# " + cfg["title"] + "\n", encoding="utf-8")

    events, pulses, event_wave, _pulse_wave, counts = s33.extract_tables(cfg)
    total = int(counts["selected_pulses"].sum())
    expected = int(cfg["expected_selected_pulses"])
    if total != expected:
        raise RuntimeError(f"raw selected-pulse reproduction failed: {total} != {expected}")

    valid = (events["odd_total_charge"].to_numpy(float) > 100.0) & (events["even_total_charge"].to_numpy(float) > 100.0)
    events = events.loc[valid].reset_index(drop=True)
    event_wave = event_wave[valid]
    valid_ids = set(events["event_id"].astype(int))
    pulses = pulses[pulses["event_id"].isin(valid_ids) & (pulses["odd_charge"].to_numpy(float) > 20.0)].reset_index(drop=True)
    held = events["run"].isin(s33.heldout_runs(cfg)).to_numpy()
    train = ~held
    pulse_train = ~pulses["run"].isin(s33.heldout_runs(cfg)).to_numpy()

    dedx = s33.load_dedx_table(cfg)
    range_table = s33.build_range_table(dedx)
    prior = s33.geant4_stave_priors(cfg, range_table, cfg["nominal_geometry"])
    birks = s33.fit_birks(pulses, prior, pulse_train, "odd_charge")
    y_energy = s33.aggregate_event(pulses, s33.charge_to_edep(pulses, prior, birks, "odd_charge"), events)
    birks_energy = s33.aggregate_event(pulses, s33.charge_to_edep(pulses, prior, birks, "even_charge"), events)
    y_timing = timing_target(events, event_wave)
    x, feature_names = s33.event_features(events, event_wave)
    ped = pedestal_state(events, counts, train)
    labels, _pid_coord, pid_info = s33.pid_proxy_labels(events, y_energy, train, cfg)

    target = np.column_stack([np.log(np.maximum(y_energy, 1e-6)), y_timing, logit(np.where(labels >= 0, labels, 0.5) * 0.98 + 0.01)])
    train_idx = train & (labels >= 0)
    families = {}
    preds: Dict[str, dict] = {}

    trad_pid = s33.traditional_pid_score(events, train, held, labels)
    trad_time = events["even_max_amp"].to_numpy(float) * 0.0 + np.median(y_timing[train])
    preds["traditional_charge_ratio_template"] = {"method": "traditional_charge_ratio_template", "energy": birks_energy, "pid": trad_pid, "timing": trad_time}
    families["traditional_charge_ratio_template"] = "traditional"

    ridge = make_pipeline(StandardScaler(), MultiOutputRegressor(Ridge(alpha=2.0))).fit(x[train_idx], target[train_idx])
    ridge_o = ridge.predict(x)
    preds["ridge"] = {"method": "ridge", "energy": np.exp(ridge_o[:, 0]), "timing": ridge_o[:, 1], "pid": 1 / (1 + np.exp(-np.clip(ridge_o[:, 2], -40, 40)))}
    families["ridge"] = "linear_ml"

    gbr_e = GradientBoostingRegressor(n_estimators=70, max_depth=3, learning_rate=0.05, random_state=int(cfg["random_seed"]) + 1).fit(x[train], np.log(y_energy[train]))
    gbr_t = GradientBoostingRegressor(n_estimators=70, max_depth=3, learning_rate=0.05, random_state=int(cfg["random_seed"]) + 2).fit(x[train], y_timing[train])
    gbc = GradientBoostingClassifier(n_estimators=70, max_depth=3, learning_rate=0.05, random_state=int(cfg["random_seed"]) + 3).fit(x[train_idx], labels[train_idx])
    preds["gradient_boosted_trees"] = {"method": "gradient_boosted_trees", "energy": np.exp(gbr_e.predict(x)), "timing": gbr_t.predict(x), "pid": gbc.predict_proba(x)[:, 1]}
    families["gradient_boosted_trees"] = "tree_ml"

    mlp_e = make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(48, 24), alpha=1e-3, max_iter=int(cfg["mlp_max_iter"]) * 8, random_state=int(cfg["random_seed"]) + 4)).fit(x[train], np.log(y_energy[train]))
    mlp_t = make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(48, 24), alpha=1e-3, max_iter=int(cfg["mlp_max_iter"]) * 8, random_state=int(cfg["random_seed"]) + 5)).fit(x[train], y_timing[train])
    mlp_c = make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(48, 24), alpha=1e-3, max_iter=int(cfg["mlp_max_iter"]) * 8, random_state=int(cfg["random_seed"]) + 6)).fit(x[train_idx], labels[train_idx])
    preds["mlp"] = {"method": "mlp", "energy": np.exp(mlp_e.predict(x)), "timing": mlp_t.predict(x), "pid": mlp_c.predict_proba(x)[:, 1]}
    families["mlp"] = "neural_tabular"

    if torch is not None:
        cnn, csc = torch_fit(MultiTaskCNN(x.shape[1]), event_wave, x, target, train_idx, cfg, int(cfg["random_seed"]) + 7)
        co = torch_predict(cnn, csc, event_wave, x)
        preds["1d_cnn"] = {"method": "1d_cnn", "energy": np.exp(co[:, 0]), "timing": co[:, 1], "pid": 1 / (1 + np.exp(-np.clip(co[:, 2], -40, 40)))}
        families["1d_cnn"] = "neural_waveform"
        tr, tsc = torch_fit(TinyTransformer(x.shape[1]), event_wave, x, target, train_idx, cfg, int(cfg["random_seed"]) + 8)
        to = torch_predict(tr, tsc, event_wave, x)
        preds["tiny_transformer_multitask"] = {"method": "tiny_transformer_multitask", "energy": np.exp(to[:, 0]), "timing": to[:, 1], "pid": 1 / (1 + np.exp(-np.clip(to[:, 2], -40, 40)))}
        families["tiny_transformer_multitask"] = "sequence_nn_new"

    resid_x = np.column_stack([x, np.log(np.maximum(birks_energy, 1e-6)), preds["gradient_boosted_trees"]["pid"], preds["gradient_boosted_trees"]["timing"]])
    fusion = make_pipeline(StandardScaler(), MultiOutputRegressor(Ridge(alpha=0.8))).fit(
        resid_x[train_idx],
        np.column_stack([
            np.log(np.maximum(y_energy[train_idx], 1e-6)) - np.log(np.maximum(birks_energy[train_idx], 1e-6)),
            y_timing[train_idx],
            logit(labels[train_idx] * 0.98 + 0.01),
        ]),
    )
    fo = fusion.predict(resid_x)
    preds["pedestal_tail_fusion_new"] = {"method": "pedestal_tail_fusion_new", "energy": birks_energy * np.exp(np.clip(fo[:, 0], -4, 4)), "timing": fo[:, 1], "pid": 1 / (1 + np.exp(-np.clip(fo[:, 2], -40, 40)))}
    families["pedestal_tail_fusion_new"] = "new_hybrid"

    lo, hi = np.percentile(y_energy[train], [0.1, 99.9])
    for p in preds.values():
        p["energy"] = np.clip(p["energy"], lo, hi)

    metric_rows = [metrics_for(events, held, labels, y_energy, y_timing, p, cfg, families[name]) for name, p in preds.items()]
    metrics = pd.DataFrame(metric_rows)
    metrics["winner_score"] = (
        (1.0 - metrics["pid_auc"]) + metrics["energy_sigma68_frac"] + 0.01 * metrics["timing_sigma68_ns"] + 0.15 * metrics["pid_balanced_error"] + 0.10 * metrics["energy_bias_frac"].abs()
    )
    metrics = metrics.sort_values("winner_score").reset_index(drop=True)
    winner = metrics.iloc[0]

    run_rows = []
    strata_rows = []
    for name, p in preds.items():
        for run, sub in events.loc[held & (labels >= 0)].groupby("run"):
            idx = sub.index.to_numpy()
            run_rows.append({"run": int(run), "method": name, "n": int(len(idx)), "pid_auc": float(roc_auc_score(labels[idx], p["pid"][idx])), "energy_sigma68_frac": sigma68((p["energy"][idx] - y_energy[idx]) / y_energy[idx]), "timing_sigma68_ns": 10.0 * sigma68(p["timing"][idx] - y_timing[idx])})
        for key, values in {"multiplicity": events["multiplicity"], "saturation": events["saturated_count"], "pedestal_state": pd.Series(ped)}.items():
            for val in sorted(pd.Series(values[held & (labels >= 0)]).unique(), key=str):
                idx = held & (labels >= 0) & (np.asarray(values).astype(str) == str(val))
                if idx.sum() < 20:
                    continue
                strata_rows.append({"stratum": key, "value": str(val), "method": name, "n": int(idx.sum()), "energy_sigma68_frac": sigma68((p["energy"][idx] - y_energy[idx]) / y_energy[idx]), "timing_sigma68_ns": 10.0 * sigma68(p["timing"][idx] - y_timing[idx])})
    byrun = pd.DataFrame(run_rows)
    strata = pd.DataFrame(strata_rows)

    rng = np.random.default_rng(int(cfg["random_seed"]) + 90)
    null_labels = labels.copy()
    shuffled_train_labels = null_labels[train_idx].copy()
    rng.shuffle(shuffled_train_labels)
    null_labels[train_idx] = shuffled_train_labels
    null_lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)).fit(x[train_idx], null_labels[train_idx])
    null_auc = float(roc_auc_score(labels[held & (labels >= 0)], null_lr.predict_proba(x[held & (labels >= 0)])[:, 1]))
    perm_x = x.copy()
    rng.shuffle(perm_x[:, -1])
    perm_e = GradientBoostingRegressor(n_estimators=40, max_depth=2, random_state=int(cfg["random_seed"]) + 91).fit(perm_x[train], np.log(y_energy[train]))
    perm_sigma = sigma68((np.exp(perm_e.predict(perm_x[held])) - y_energy[held]) / y_energy[held])
    uncertainty = coverage(y_energy, preds[str(winner["method"])]["energy"], np.full(len(y_energy), sigma68((preds[str(winner["method"])]["energy"][train] - y_energy[train]) / y_energy[train]) * np.maximum(y_energy, 1e-9)), held)

    counts.to_csv(out / "counts_by_run.csv", index=False)
    pd.DataFrame([{"quantity": "S00 selected B-stave pulse records", "expected": expected, "reproduced": total, "delta": total - expected, "pass": total == expected}]).to_csv(out / "reproduction_match_table.csv", index=False)
    metrics.to_csv(out / "method_metrics.csv", index=False)
    byrun.to_csv(out / "run_heldout_metrics.csv", index=False)
    strata.to_csv(out / "strata_metrics.csv", index=False)
    prior.to_csv(out / "geant4_stave_priors.csv", index=False)
    pd.DataFrame([birks]).to_csv(out / "birks_fit.csv", index=False)
    pd.DataFrame([{"check": "null_label_pid_auc_against_true_heldout_labels", "value": null_auc}, {"check": "permuted_feature_energy_sigma68", "value": perm_sigma}]).to_csv(out / "null_permutation_controls.csv", index=False)

    input_paths = [s33.raw_path(cfg, run) for run in s33.configured_runs(cfg)] + [Path(cfg["dedx_table"])]
    input_sha = pd.DataFrame([{"path": str(p), "bytes": p.stat().st_size, "sha256": s33.sha256_file(p)} for p in input_paths])
    input_sha.to_csv(out / "input_sha256.csv", index=False)

    result = {
        "study": cfg["study_id"],
        "ticket_id": cfg["ticket_id"],
        "worker": cfg["worker"],
        "status": "complete",
        "claim_command": f"tn-ticket claim {cfg['worker']} --project testbeam",
        "raw_reproduction": {"expected_selected_pulses": expected, "reproduced_selected_pulses": total, "delta": total - expected, "pass": total == expected},
        "split": {"train_runs": sorted(int(x) for x in events.loc[train, "run"].unique()), "heldout_runs": sorted(int(x) for x in events.loc[held, "run"].unique())},
        "required_method_coverage": {"traditional": "traditional_charge_ratio_template", "ridge": "ridge", "gradient_boosted_trees": "gradient_boosted_trees", "mlp": "mlp", "one_dimensional_cnn": "1d_cnn", "new_architecture": "tiny_transformer_multitask and pedestal_tail_fusion_new"},
        "winner": {"method": str(winner["method"]), "family": str(winner["family"]), "criterion": "minimum joint PID-energy-timing held-out score", "winner_score": float(winner["winner_score"]), "pid_auc": float(winner["pid_auc"]), "pid_auc_ci95": winner["pid_auc_ci95"], "energy_sigma68_frac": float(winner["energy_sigma68_frac"]), "energy_sigma68_ci95": winner["energy_sigma68_ci95"], "energy_bias_frac": float(winner["energy_bias_frac"]), "timing_sigma68_ns": float(winner["timing_sigma68_ns"]), "timing_sigma68_ci95": winner["timing_sigma68_ns_ci95"]},
        "pid_proxy": pid_info,
        "uncertainty_coverage_90pct": uncertainty,
        "null_controls": {"null_label_pid_auc_against_true_heldout_labels": null_auc, "permuted_feature_energy_sigma68": perm_sigma},
        "novel_tickets_appended": [],
        "artifacts": ["REPORT.md", "result.json", "method_metrics.csv", "run_heldout_metrics.csv", "strata_metrics.csv", "reproduction_match_table.csv", "null_permutation_controls.csv", "input_sha256.csv"],
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    report = f"""# S39c: Joint PID-Energy Disentanglement under Pile-Up and Saturation

## Abstract

Ticket `{cfg['ticket_id']}` was claimed by `{cfg['worker']}`.  The analysis reruns the raw ROOT selection gate and then benchmarks a strong traditional charge-ratio/template method against ridge, gradient-boosted trees, MLP, 1D-CNN, a small waveform transformer, and a new pedestal-tail fusion architecture.  Held-out runs are disjoint from train runs.  The winner named in `result.json` is **{winner['method']}** with PID AUC `{winner['pid_auc']:.5f}`, energy sigma68 `{winner['energy_sigma68_frac']:.5f}`, and timing sigma68 `{winner['timing_sigma68_ns']:.5f}` ns.

## Raw ROOT Reproduction

The gate reads `h101/HRDv` from `{cfg['raw_root_dir']}`, reshapes to `(event, channel, sample)`, subtracts the median of samples 0--3, and counts even B-stave pulses with peak amplitude above 1000 ADC.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| S00 selected B-stave pulse records | {expected:,} | {total:,} | {total - expected:+,} | {str(total == expected).lower()} |

## Targets and Split

The train runs are `{result['split']['train_runs']}` and held-out runs are `{result['split']['heldout_runs']}`.  Energy truth is duplicate-readout closure anchored by a GEANT4 stopping-power/Birks calibration.  The PID endpoint is a train-frozen weak label from the duplicate odd-readout charge-depth coordinate, because the raw ROOT branch set has no particle species field.  Timing truth is a charge-weighted selected peak-sample proxy; residuals are reported in ns using the 10 ns sample spacing.

## Equations

The Birks calibration fits

`Q = alpha * DeltaE / (1 + kB dE/dx)`.

The fractional energy residual is

`r_E = (E_hat - E_odd) / E_odd`.

The timing residual is

`r_t = 10 ns * (t_hat - t_proxy)`.

Resolution is

`sigma68(x) = [Q84(x) - Q16(x)] / 2`.

The winner minimizes

`L = (1 - AUC_PID) + sigma68_E + 0.01 sigma68_t + 0.15 balanced_error_PID + 0.10 |bias_E|`.

All CIs are percentile 95% intervals from `{cfg['bootstrap_reps']}` held-out run-block bootstrap resamples.

## Methods

| method | family | summary |
|---|---|---|
| traditional_charge_ratio_template | traditional | GEANT4/Birks energy inversion plus Gaussian charge-depth PID and median timing |
| ridge | linear ML | standardized multi-output ridge/logistic approximation |
| gradient_boosted_trees | tree ML | separate boosted energy, timing, and PID heads |
| mlp | neural tabular | tabular MLP regressors/classifier |
| 1d_cnn | neural waveform | convolution over the four B-stave 18-sample waveforms |
| tiny_transformer_multitask | new sequence NN | one-layer self-attention waveform encoder with joint heads |
| pedestal_tail_fusion_new | new hybrid | Birks residual correction using pedestal, tail, timing, and boosted-PID summaries |

## Overall Results

{md_table(metrics, ['method', 'family', 'winner_score', 'pid_auc', 'pid_auc_ci95', 'energy_sigma68_frac', 'energy_sigma68_ci95', 'energy_bias_frac', 'timing_sigma68_ns', 'timing_sigma68_ns_ci95'])}

## Held-Out Run Stability

{md_table(byrun[byrun['method'].isin([str(winner['method']), 'traditional_charge_ratio_template', 'gradient_boosted_trees'])], ['run', 'method', 'n', 'pid_auc', 'energy_sigma68_frac', 'timing_sigma68_ns'])}

## Pile-Up, Saturation, and Pedestal Strata

Multiplicity is the event-level selected-pulse count, saturation is the selected even-channel saturated count, and pedestal state is a train-quantiled run-level pretrigger RMS band.

{md_table(strata[strata['method'].isin([str(winner['method']), 'traditional_charge_ratio_template'])], ['stratum', 'value', 'method', 'n', 'energy_sigma68_frac', 'timing_sigma68_ns'], limit=80)}

## Nulls, Coverage, and Systematics

The null-label control has held-out AUC `{null_auc:.5f}` when train labels are shuffled before fitting.  The feature-permutation energy sigma68 is `{perm_sigma:.5f}`.  The winner's nominal 90% energy interval coverage is `{uncertainty['empirical']:.5f}`.

Main caveats: PID is a weak-label robustness endpoint, not hidden particle truth; energy inherits the GEANT4 geometry and duplicate-readout closure assumptions; timing is a peak-sample proxy rather than an external clock residual; saturation above the ADC ceiling remains partially unidentified; and bootstrap CIs quantify transfer across held-out runs rather than event-counting limits.

## Verdict

`result.json` names **{winner['method']}** as the S39c winner.  The result favors the method with the best registered joint PID, energy, and timing score after raw ROOT reproduction, run-held-out evaluation, bootstrap CIs, null checks, and pile-up/saturation/pedestal stratification.
"""
    (out / "REPORT.md").write_text(report, encoding="utf-8")

    manifest = {
        "study": cfg["study_id"],
        "ticket_id": cfg["ticket_id"],
        "worker": cfg["worker"],
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "command": f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)} --config {args.config}",
        "environment": {"python": platform.python_version(), "platform": platform.platform(), "torch": getattr(torch, "__version__", "unavailable") if torch is not None else "unavailable"},
        "outputs": {p.name: s33.sha256_file(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != "manifest.json"},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"DONE {out} winner={winner['method']} runtime={result['runtime_sec']}s", flush=True)


if __name__ == "__main__":
    main()
