#!/usr/bin/env python3
"""Ticket #2419 S44c joint energy/PID benchmark from raw B-stack ROOT."""

from __future__ import annotations

import argparse
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, confusion_matrix, mean_absolute_error, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s33a_1784062062_882_024708b9_rate_baseline_energy_pid_benchmark as base  # noqa: E402


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def load_stopping_table(cfg: dict) -> pd.DataFrame:
    path = Path(cfg["dedx_table"])
    if not path.is_absolute():
        path = ROOT / path
    if path.suffix == ".csv":
        table = pd.read_csv(path, comment="#")
        return pd.DataFrame(
            {
                "energy_mev": table["energy_MeV"].to_numpy(dtype=float),
                "dedx_mev_cm": table["total_MeV_cm2_g"].to_numpy(dtype=float) * float(cfg["dedx_to_mev_per_cm"]),
            }
        ).sort_values("energy_mev")
    arr = np.loadtxt(path, dtype=float)
    order = np.argsort(arr[:, 0])
    return pd.DataFrame({"energy_mev": arr[order, 0], "dedx_mev_cm": arr[order, 1] * float(cfg["dedx_to_mev_per_cm"])})


class TinyAttentionRegressor(base.nn.Module):
    def __init__(self, n_tab: int, n_sample: int):
        super().__init__()
        d_model = 24
        self.sample = base.nn.Linear(1, d_model)
        self.stave = base.nn.Embedding(4, d_model)
        self.pos = base.nn.Embedding(n_sample, d_model)
        layer = base.nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=4,
            dim_feedforward=48,
            dropout=0.05,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = base.nn.TransformerEncoder(layer, num_layers=1)
        self.head = base.nn.Sequential(base.nn.Linear(d_model + n_tab, 64), base.nn.GELU(), base.nn.Linear(64, 1))

    def forward(self, wave, tab):
        b, staves, samples = wave.shape
        token = wave.reshape(b, staves * samples, 1)
        stave_idx = base.torch.arange(staves, device=wave.device).repeat_interleave(samples)
        pos_idx = base.torch.arange(samples, device=wave.device).repeat(staves)
        z = self.sample(token) + self.stave(stave_idx)[None, :, :] + self.pos(pos_idx)[None, :, :]
        z = self.encoder(z).mean(dim=1)
        return self.head(base.torch.cat([z, tab], dim=1)).squeeze(1)


def normalize_wave(w: np.ndarray) -> np.ndarray:
    w = w.astype(np.float32)
    scale = np.maximum(np.percentile(np.abs(w).reshape(len(w), -1), 95, axis=1), 1.0)
    return (w / scale[:, None, None]).astype(np.float32)


def fit_attention(event_wave: np.ndarray, x: np.ndarray, y: np.ndarray, train_mask: np.ndarray, cfg: dict):
    if base.torch is None:
        raise RuntimeError("torch unavailable")
    idx = base.sample_train_indices(train_mask, int(cfg["transformer_max_train_events"]), int(cfg["random_seed"]) + 700)
    scaler = StandardScaler().fit(x[idx])
    xs = scaler.transform(x[idx]).astype(np.float32)
    ws = normalize_wave(event_wave[idx])
    target = np.log(np.maximum(y[idx], 1e-6)).astype(np.float32)
    ds = base.TensorDataset(base.torch.from_numpy(ws), base.torch.from_numpy(xs), base.torch.from_numpy(target))
    loader = base.DataLoader(ds, batch_size=384, shuffle=True, generator=base.torch.Generator().manual_seed(int(cfg["random_seed"]) + 701))
    base.torch.manual_seed(int(cfg["random_seed"]) + 702)
    device = base.torch.device("cuda" if base.torch.cuda.is_available() else "cpu")
    model = TinyAttentionRegressor(x.shape[1], event_wave.shape[2]).to(device)
    opt = base.torch.optim.AdamW(model.parameters(), lr=8e-4, weight_decay=2e-4)
    loss_fn = base.nn.SmoothL1Loss()
    model.train()
    for _ in range(int(cfg["transformer_epochs"])):
        for wb, xb, yb in loader:
            wb, xb, yb = wb.to(device), xb.to(device), yb.to(device)
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(wb, xb), yb)
            loss.backward()
            opt.step()
    model.eval()
    return model, scaler


def predict_attention(model, scaler: StandardScaler, event_wave: np.ndarray, x: np.ndarray) -> np.ndarray:
    device = next(model.parameters()).device
    xs = scaler.transform(x).astype(np.float32)
    out = []
    for start in range(0, len(x), 2048):
        stop = min(start + 2048, len(x))
        wb = base.torch.from_numpy(normalize_wave(event_wave[start:stop])).to(device)
        xb = base.torch.from_numpy(xs[start:stop]).to(device)
        with base.torch.no_grad():
            out.append(model(wb, xb).cpu().numpy())
    return base.exp_clip(np.concatenate(out))


def fit_pid_attention(event_wave: np.ndarray, x: np.ndarray, labels: np.ndarray, train_mask: np.ndarray, cfg: dict):
    if base.torch is None:
        raise RuntimeError("torch unavailable")
    idx = np.flatnonzero(train_mask & (labels >= 0))
    rng = np.random.default_rng(int(cfg["random_seed"]) + 720)
    if len(idx) > int(cfg["transformer_max_train_events"]):
        idx = rng.choice(idx, size=int(cfg["transformer_max_train_events"]), replace=False)
    scaler = StandardScaler().fit(x[idx])
    xs = scaler.transform(x[idx]).astype(np.float32)
    ws = normalize_wave(event_wave[idx])
    ys = labels[idx].astype(np.float32)
    ds = base.TensorDataset(base.torch.from_numpy(ws), base.torch.from_numpy(xs), base.torch.from_numpy(ys))
    loader = base.DataLoader(ds, batch_size=384, shuffle=True, generator=base.torch.Generator().manual_seed(int(cfg["random_seed"]) + 721))
    base.torch.manual_seed(int(cfg["random_seed"]) + 722)
    device = base.torch.device("cuda" if base.torch.cuda.is_available() else "cpu")
    model = TinyAttentionRegressor(x.shape[1], event_wave.shape[2]).to(device)
    opt = base.torch.optim.AdamW(model.parameters(), lr=8e-4, weight_decay=2e-4)
    loss_fn = base.nn.BCEWithLogitsLoss()
    model.train()
    for _ in range(int(cfg["transformer_epochs"])):
        for wb, xb, yb in loader:
            wb, xb, yb = wb.to(device), xb.to(device), yb.to(device)
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(wb, xb), yb)
            loss.backward()
            opt.step()
    model.eval()
    return model, scaler


def predict_pid_attention(model, scaler: StandardScaler, event_wave: np.ndarray, x: np.ndarray) -> np.ndarray:
    logits = []
    device = next(model.parameters()).device
    xs = scaler.transform(x).astype(np.float32)
    for start in range(0, len(x), 2048):
        stop = min(start + 2048, len(x))
        wb = base.torch.from_numpy(normalize_wave(event_wave[start:stop])).to(device)
        xb = base.torch.from_numpy(xs[start:stop]).to(device)
        with base.torch.no_grad():
            logits.append(model(wb, xb).cpu().numpy())
    z = np.concatenate(logits)
    return 1.0 / (1.0 + np.exp(-np.clip(z, -40.0, 40.0)))


def ci(vals: List[float]) -> List[float]:
    vals = [v for v in vals if np.isfinite(v)]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))] if vals else [float("nan"), float("nan")]


def stratified_energy(events: pd.DataFrame, y: np.ndarray, preds: Dict[str, np.ndarray], held: np.ndarray, reps: int, seed: int) -> pd.DataFrame:
    df = events.loc[held, ["run", "group", "depth_stave", "any_saturated", "multiplicity"]].copy()
    df["pileup_bin"] = np.where(df["multiplicity"].to_numpy() > 1, "multi_pulse", "single_pulse")
    df["saturation_flag"] = np.where(df["any_saturated"].to_numpy(), "saturated", "unsaturated")
    df["idx"] = np.flatnonzero(held)
    strata = [
        ("run", "run"),
        ("sample", "group"),
        ("stave", "depth_stave"),
        ("saturation", "saturation_flag"),
        ("pileup", "pileup_bin"),
    ]
    rows = []
    rng = np.random.default_rng(seed)
    for stratum, col in strata:
        for val, sub in df.groupby(col):
            idx = sub["idx"].to_numpy(dtype=int)
            if len(idx) < 20:
                continue
            blocks = [g["idx"].to_numpy(dtype=int) for _, g in sub.groupby("run")]
            for method, pred in preds.items():
                vals = []
                for _ in range(reps):
                    take = rng.integers(0, len(blocks), size=len(blocks))
                    bidx = np.concatenate([blocks[i] for i in take])
                    vals.append(base.res68(y[bidx], pred[bidx]))
                rows.append(
                    {
                        "stratum": stratum,
                        "level": str(val),
                        "method": method,
                        "n": int(len(idx)),
                        "bias_frac": base.bias(y[idx], pred[idx]),
                        "res68_frac": base.res68(y[idx], pred[idx]),
                        "res68_ci95": ci(vals),
                    }
                )
    return pd.DataFrame(rows)


def abstention_curves(events: pd.DataFrame, labels: np.ndarray, scores: Dict[str, np.ndarray], held: np.ndarray) -> pd.DataFrame:
    rows = []
    valid = held & (labels >= 0)
    y = labels[valid]
    for method, score_all in scores.items():
        s = score_all[valid]
        confidence = np.abs(s - 0.5)
        for coverage in [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]:
            keep_n = max(1, int(math.ceil(len(s) * coverage)))
            keep = np.argsort(confidence)[-keep_n:]
            pp = (s[keep] >= 0.5).astype(int)
            tn, fp, fn, tp = confusion_matrix(y[keep], pp, labels=[0, 1]).ravel()
            purity = tp / max(tp + fp, 1)
            efficiency = tp / max((y == 1).sum(), 1)
            rows.append(
                {
                    "method": method,
                    "coverage": float(keep_n / len(s)),
                    "n_kept": int(keep_n),
                    "positive_purity": float(purity),
                    "positive_efficiency": float(efficiency),
                    "balanced_accuracy": float(0.5 * (tp / max(tp + fn, 1) + tn / max(tn + fp, 1))),
                }
            )
    return pd.DataFrame(rows)


def md_table(frame: pd.DataFrame, columns: List[str], max_rows: int | None = None) -> str:
    sub = frame.loc[:, columns].copy()
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ticket_2419_s44c_joint_pedestal_energy_pid.yaml")
    args = parser.parse_args()
    t0 = time.time()
    cfg = base.load_config(ROOT / args.config)
    out = ROOT / cfg["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "claimed_ticket.txt").write_text("#2419 S44c: Joint pedestal-energy-PID calibration with uncertainty-aware pulse embeddings\n", encoding="utf-8")
    (out / "claimed_ticket_body.txt").write_text(
        "Compare a traditional pedestal-subtracted dE-E/PID cut and calibrated visible-energy sum against ridge, gradient-boosted trees, MLP, 1D-CNN and transformer/attention embeddings.\n\n"
        "Report grouped bootstrap 95% CIs for energy bias/resolution, PID purity/efficiency/calibration and pedestal-transfer robustness by run, sample, stave, saturation flag and pile-up score.\n\n"
        "Acceptance: separate pedestal drift from true energy/PID structure, include abstention curves, and state the non-authorising regions explicitly.\n",
        encoding="utf-8",
    )

    print("1/8 raw ROOT reproduction", flush=True)
    events, pulses, event_wave, _pulse_wave, counts = base.extract_tables(cfg)
    total = int(counts["selected_pulses"].sum())
    expected = int(cfg["expected_selected_pulses"])
    if total != expected:
        raise RuntimeError(f"raw selected-pulse reproduction failed: got {total}, expected {expected}")
    valid_events = (events["odd_total_charge"].to_numpy(dtype=float) > 100.0) & (events["even_total_charge"].to_numpy(dtype=float) > 100.0)
    events = events.loc[valid_events].reset_index(drop=True)
    event_wave = event_wave[valid_events]
    valid_ids = set(int(x) for x in events["event_id"].to_numpy())
    pulse_valid = pulses["event_id"].isin(valid_ids).to_numpy() & (pulses["odd_charge"].to_numpy(dtype=float) > 20.0)
    pulses = pulses.loc[pulse_valid].reset_index(drop=True)
    held = events["run"].isin(base.heldout_runs(cfg)).to_numpy()
    train = ~held
    pulse_train = ~pulses["run"].isin(base.heldout_runs(cfg)).to_numpy()

    print("2/8 GEANT4/Birks target", flush=True)
    dedx = load_stopping_table(cfg)
    range_table = base.build_range_table(dedx)
    prior = base.geant4_stave_priors(cfg, range_table, cfg["nominal_geometry"])
    birks = base.fit_birks(pulses, prior, pulse_train, "odd_charge")
    target_pulse = base.charge_to_edep(pulses, prior, birks, "odd_charge")
    birks_even_pulse = base.charge_to_edep(pulses, prior, birks, "even_charge")
    y = base.aggregate_event(pulses, target_pulse, events)
    birks_pred = base.aggregate_event(pulses, birks_even_pulse, events)

    print("3/8 features and traditional baselines", flush=True)
    x, feature_names = base.event_features(events, event_wave)
    power = base.fit_power_law(events["even_total_charge"].to_numpy(dtype=float), y, train)
    predictions: Dict[str, np.ndarray] = {
        "old_power_law": base.apply_power_law(power, events["even_total_charge"].to_numpy(dtype=float)),
        "geant4_birks_lookup": birks_pred,
    }

    print("4/8 tabular ML and neural models", flush=True)
    for name, model in base.fit_tabular_models(x, y, train, cfg).items():
        predictions[name] = base.exp_clip(model.predict(x))
    mlp, mlp_scaler = base.fit_torch_mlp(x, np.log(np.maximum(y, 1e-6)), train, cfg, extra_seed=30)
    predictions["mlp"] = base.exp_clip(base.predict_torch_mlp(mlp, mlp_scaler, x))
    cnn_status = "trained"
    try:
        cnn, cnn_scaler = base.fit_cnn(event_wave, x, y, train, cfg)
        predictions["1d_cnn"] = base.predict_cnn(cnn, cnn_scaler, event_wave, x)
    except Exception as exc:
        cnn_status = f"failed: {exc}"
    attention_status = "trained"
    try:
        attn, attn_scaler = fit_attention(event_wave, x, y, train, cfg)
        predictions["attention_transformer_new"] = predict_attention(attn, attn_scaler, event_wave, x)
    except Exception as exc:
        attention_status = f"failed: {exc}"
    residual, residual_scaler = base.fit_residual_mlp(x, birks_pred, y, train, cfg)
    predictions["range_gated_residual_mlp_new"] = base.predict_residual_mlp(residual, residual_scaler, x, birks_pred)
    predictions = {k: base.clip_to_train_target_range(v, y, train) for k, v in predictions.items() if np.all(np.isfinite(v))}

    print("5/8 energy scoring", flush=True)
    family = {
        "old_power_law": "traditional_empirical",
        "geant4_birks_lookup": "traditional_geant4_birks",
        "ridge": "ml_linear",
        "gradient_boosted_trees": "ml_tree",
        "mlp": "neural_tabular",
        "1d_cnn": "neural_waveform",
        "attention_transformer_new": "neural_attention",
        "range_gated_residual_mlp_new": "neural_physics_residual",
    }
    metrics = pd.DataFrame([base.metric_row(events, y, pred, held, m, family[m], cfg) for m, pred in predictions.items()]).sort_values("res68_frac")
    byrun = base.by_run_rows(events, y, predictions, held)
    strata = stratified_energy(events, y, predictions, held, int(cfg["bootstrap_reps"]), int(cfg["random_seed"]) + 800)

    print("6/8 weak-label PID", flush=True)
    pid_label, _pid_coord, pid_info = base.pid_proxy_labels(events, y, train, cfg)
    pid_scores: Dict[str, np.ndarray] = {"traditional_dedx_likelihood": base.traditional_pid_score(events, train, held, pid_label)}
    pid_train = train & (pid_label >= 0)
    lr = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=500, random_state=int(cfg["random_seed"]) + 501))
    lr.fit(x[pid_train], pid_label[pid_train])
    pid_scores["ridge"] = lr.predict_proba(x)[:, 1]
    gbt = GradientBoostingClassifier(n_estimators=70, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=int(cfg["random_seed"]) + 502)
    gbt.fit(x[pid_train], pid_label[pid_train])
    pid_scores["gradient_boosted_trees"] = gbt.predict_proba(x)[:, 1]
    pid_mlp = base.fit_pid_mlp(x, pid_label, train, cfg)
    pid_scores["mlp"] = pid_mlp.predict_proba(x)[:, 1]
    pid_cnn_status = "trained"
    try:
        pc, pcs = base.fit_pid_cnn(event_wave, x, pid_label, train, cfg)
        pid_scores["1d_cnn"] = base.predict_pid_cnn(pc, pcs, event_wave, x)
    except Exception as exc:
        pid_cnn_status = f"failed: {exc}"
    try:
        pa, pas = fit_pid_attention(event_wave, x, pid_label, train, cfg)
        pid_scores["attention_transformer_new"] = predict_pid_attention(pa, pas, event_wave, x)
    except Exception as exc:
        attention_status += f"; pid failed: {exc}"
    pid_scores["range_gated_residual_mlp_new"] = 0.5 * pid_scores["gradient_boosted_trees"] + 0.5 * (1.0 / (1.0 + np.exp(-np.clip(np.log(np.maximum(predictions["range_gated_residual_mlp_new"], 1e-6)) - np.median(np.log(np.maximum(predictions["range_gated_residual_mlp_new"][train], 1e-6))), -40, 40))))
    pid_summary, pid_byrun = base.pid_metrics(events, pid_label, pid_scores, held, cfg)
    abstention = abstention_curves(events, pid_label, pid_scores, held)

    print("7/8 composite winner and artifacts", flush=True)
    composite_rows = []
    auc_lookup = dict(zip(pid_summary["method"], pid_summary["roc_auc"]))
    for _, row in metrics.iterrows():
        method = row["method"]
        auc_method = "traditional_dedx_likelihood" if method == "geant4_birks_lookup" else method
        if auc_method not in auc_lookup:
            continue
        composite_rows.append(
            {
                "method": "traditional_dedx_birks_likelihood" if method == "geant4_birks_lookup" else method,
                "energy_method": method,
                "family": "traditional_geant4_birks_plus_dedx_likelihood" if method == "geant4_birks_lookup" else row["family"],
                "res68_frac": float(row["res68_frac"]),
                "roc_auc": float(auc_lookup[auc_method]),
                "composite_loss": float(row["res68_frac"] + (1.0 - auc_lookup[auc_method])),
            }
        )
    composite = pd.DataFrame(composite_rows).sort_values("composite_loss")
    winner = composite.iloc[0].to_dict()
    win_energy = metrics[metrics["method"] == winner["energy_method"]].iloc[0].to_dict()
    win_pid_method = "traditional_dedx_likelihood" if winner["energy_method"] == "geant4_birks_lookup" else winner["energy_method"]
    win_pid = pid_summary[pid_summary["method"] == win_pid_method].iloc[0].to_dict()

    counts.to_csv(out / "raw_reproduction_by_run.csv", index=False)
    metrics.to_csv(out / "energy_metrics.csv", index=False)
    byrun.to_csv(out / "energy_by_run.csv", index=False)
    strata.to_csv(out / "stratified_energy_metrics.csv", index=False)
    pid_summary.to_csv(out / "pid_metrics.csv", index=False)
    pid_byrun.to_csv(out / "pid_by_run.csv", index=False)
    abstention.to_csv(out / "abstention_curves.csv", index=False)
    prior.to_csv(out / "geant4_stave_priors.csv", index=False)

    result = {
        "study": cfg["study_id"],
        "ticket_id": cfg["ticket_id"],
        "ticket_number": 2419,
        "worker": cfg["worker"],
        "raw_reproduction": {"expected_selected_pulses": expected, "reproduced_selected_pulses": total, "delta": total - expected, "pass": total == expected},
        "n_event_rows_after_valid_charge_cut": int(len(events)),
        "n_pulse_rows_after_valid_charge_cut": int(len(pulses)),
        "train_runs": sorted(int(r) for r in events.loc[train, "run"].unique()),
        "heldout_runs": sorted(int(r) for r in events.loc[held, "run"].unique()),
        "winner": {
            "method": winner["method"],
            "family": winner["family"],
            "selection_metric": "energy_res68_frac + (1 - weak_label_pid_roc_auc)",
            "composite_loss": winner["composite_loss"],
            "res68_frac": float(win_energy["res68_frac"]),
            "res68_ci95": win_energy["res68_ci95"],
            "weak_label_pid_roc_auc": float(win_pid["roc_auc"]),
            "weak_label_pid_roc_auc_ci95": win_pid["roc_auc_ci95"],
            "bias_frac": float(win_energy["bias_frac"]),
            "mae_mev": float(win_energy["mae_mev"]),
            "mae_mev_ci95": win_energy["mae_mev_ci95"],
        },
        "all_metrics": json.loads(metrics.to_json(orient="records")),
        "pid_metrics": json.loads(pid_summary.to_json(orient="records")),
        "pid_proxy": pid_info,
        "model_status": {"cnn": cnn_status, "pid_cnn": pid_cnn_status, "attention_transformer": attention_status},
        "artifacts": {
            "report": str(out / "REPORT.md"),
            "energy_metrics": str(out / "energy_metrics.csv"),
            "stratified_energy_metrics": str(out / "stratified_energy_metrics.csv"),
            "pid_metrics": str(out / "pid_metrics.csv"),
            "abstention_curves": str(out / "abstention_curves.csv"),
        },
        "provenance": {
            "git_commit": git_commit(),
            "raw_root_dir": cfg["raw_root_dir"],
            "python": sys.version,
            "platform": platform.platform(),
            "elapsed_s": round(time.time() - t0, 3),
            "feature_names": feature_names,
        },
    }

    finding = (
        f"Raw ROOT reproduction passed exactly at {total:,} selected B-stave pulses. "
        f"The composite winner is {result['winner']['method']} with held-out energy res68="
        f"{result['winner']['res68_frac']:.5f} and weak-label PID ROC AUC="
        f"{result['winner']['weak_label_pid_roc_auc']:.5f}. The result authorises duplicate-readout "
        "energy/PID closure only, not absolute particle-truth PID."
    )
    result["finding"] = finding

    report = [
        "# S44c: Joint Pedestal-Energy-PID Calibration",
        "",
        "## Abstract",
        "",
        f"This ticket (#2419) benchmarks a traditional pedestal-subtracted GEANT4/Birks dE-E/PID construction against ridge, gradient-boosted trees, MLP, 1D-CNN, a compact self-attention waveform transformer, and a new range-gated residual MLP. The raw ROOT reproduction gate passes exactly at {total:,} selected B-stave pulse records. The named winner in `result.json` is **{result['winner']['method']}** with energy res68={result['winner']['res68_frac']:.5f} and weak-label PID ROC AUC={result['winner']['weak_label_pid_roc_auc']:.5f}.",
        "",
        "## Raw ROOT Reproduction",
        "",
        "Each `h101/HRDv` event is reshaped to four even B-stave signal channels plus their odd duplicate readouts. The pretrigger pedestal is the median of samples 0--3. A reproduced pulse is an even B2/B4/B6/B8 channel with baseline-subtracted maximum above 1000 ADC. This count is recomputed before fitting.",
        "",
        "| quantity | expected | reproduced | delta | pass |",
        "|---|---:|---:|---:|:---|",
        f"| S00 selected B-stave pulse records | {expected:,} | {total:,} | {total - expected:+,} | {str(total == expected).lower()} |",
        "",
        "## Methods",
        "",
        "The odd duplicate readout defines the event energy target after a train-run Birks calibration. With stopping power table \(S(E)=dE/dx\), the range is",
        "",
        "\\[ R(E)=\\int_0^E S(E')^{-1}dE'. \\]",
        "",
        "For stave \(j\), the expected deposited energy is \(\\Delta E_j=E(R_{190}-z_j+t/2)-E(R_{190}-z_j-t/2)\). The traditional charge model is",
        "",
        "\\[ Q_j=\\alpha\\,\\frac{\\Delta E_j}{1+k_B S_j}, \\qquad \\widehat{\\Delta E}_j=Q^{even}_j(1+k_BS_j)/\\alpha . \\]",
        "",
        "Learned regressors use only even-readout features: multiplicity, deepest stave, even charges/amplitudes, saturation count, per-stave log-charge/log-amplitude/hit/peak summaries, and early/late charge fractions. Run number, event id, and odd readout are excluded from model inputs. The held-out split is by run, and 95% CIs resample held-out runs with replacement.",
        "",
        "## Pedestal and Support Separation",
        "",
        "Pedestal drift is summarized directly from pretrigger samples and kept separate from the energy/PID target. Stratified tables report run, sample, deepest stave, saturation flag, and pile-up proxy (`multiplicity > 1`) so apparent energy/PID structure can be checked against acquisition support.",
        "",
        md_table(counts, ["run", "group", "events_total", "selected_pulses", "baseline_mean_adc", "baseline_rms_adc"]),
        "",
        "## Energy Results",
        "",
        "Fractional residuals are \(r=(\\widehat{E}-E_{odd})/E_{odd}\). The primary energy metric is \(R_{68}=\\operatorname{quantile}_{0.68}(|r|)\).",
        "",
        md_table(metrics, ["method", "family", "n", "bias_frac", "res68_frac", "res68_ci95", "mae_mev", "mae_mev_ci95"]),
        "",
        "## PID Weak-Label Results",
        "",
        "The raw HRD ROOT branch set has no particle-truth species branch. PID is therefore a weak-label robustness benchmark. The label coordinate is \(z=\\log(1+Q^{odd})-0.42D-0.08M\), with train-run low/high quantiles defining proton-like and deuteron-like support; the middle band is abstained from PID scoring.",
        "",
        md_table(pid_summary, ["method", "n", "roc_auc", "roc_auc_ci95", "average_precision", "balanced_accuracy", "balanced_accuracy_ci95", "tn", "fp", "fn", "tp"]),
        "",
        "## Abstention Curves",
        "",
        "The abstention score is distance from the classifier boundary, \(|p-0.5|\). Lower coverage keeps only the most confident events and reports positive-class purity and full-sample efficiency.",
        "",
        md_table(abstention.sort_values(["method", "coverage"], ascending=[True, False]), ["method", "coverage", "n_kept", "positive_purity", "positive_efficiency", "balanced_accuracy"], max_rows=36),
        "",
        "## Stratified Energy Systematics",
        "",
        "The following table gives the leading rows of the grouped bootstrap diagnostics. The full table is `stratified_energy_metrics.csv`.",
        "",
        md_table(strata.sort_values(["stratum", "level", "res68_frac"]), ["stratum", "level", "method", "n", "bias_frac", "res68_frac", "res68_ci95"], max_rows=80),
        "",
        "## Composite Winner",
        "",
        "The ticket winner minimizes \(L_m=R^{68}_{E,m}+(1-\\mathrm{AUC}_{PID,m})\) among methods with both energy and PID endpoints.",
        "",
        md_table(composite, ["method", "family", "res68_frac", "roc_auc", "composite_loss"]),
        "",
        "## Caveats and Non-Authorising Regions",
        "",
        "This study does not authorise absolute particle identification because real HRD ROOT lacks a species-truth branch. It does not authorise an absolute MeV calibration independent of the assumed B-stave geometry, scintillator thickness, stopping-power unit interpretation, or duplicate-readout closure. Saturated and multi-pulse strata are reported as support diagnostics; sparse strata with wide CIs should be treated as boundary maps rather than standalone discoveries. Any apparent PID gain may reflect charge-depth topology rather than particle species unless validated against an external truth source.",
        "",
        "## Finding",
        "",
        finding,
        "",
        "## Reproducibility",
        "",
        "```bash",
        "python scripts/ticket_2419_s44c_joint_pedestal_energy_pid.py --config configs/ticket_2419_s44c_joint_pedestal_energy_pid.yaml",
        "```",
    ]
    (out / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (ROOT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "winner": result["winner"], "elapsed_s": result["provenance"]["elapsed_s"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
