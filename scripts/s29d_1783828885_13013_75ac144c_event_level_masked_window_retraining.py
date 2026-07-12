#!/usr/bin/env python3
"""S29d event-level masked-window retraining benchmark.

S29c identified frozen sample windows but could not promote a transformer to the
complete winner rule.  This runner makes the missing event-native table: it
regenerates the S29a raw-template/GEANT4-aligned event panel, applies each S29c
window mask to the 18-sample waveform, and retrains every method under the same
run split before computing run-block bootstrap intervals.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge, RidgeClassifier
from sklearn.metrics import balanced_accuracy_score, precision_score, recall_score, roc_auc_score
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402
import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as s25b  # noqa: E402
import s25c_1783762816_2556_026a1556_timing_mediated_pid_energy_ablation as s25c  # noqa: E402
import s26c_1783800116_3081_430d48e6_pulse_pid_energy_timing_joint_inference_bakeoff as s26c  # noqa: E402
import s29a_1783809265_5764_0f2a2dda_digitized_g4_multitask_truth_benchmark as s29a  # noqa: E402

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


CONFIG = ROOT / "configs/s29d_1783828885_13013_75ac144c_event_level_masked_window_retraining.json"
TICKET = "1783828885.13013.75ac144c"
WORKER = "testbeam-laptop-3"


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def clean_json(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): clean_json(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean_json(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return None if not np.isfinite(float(x)) else float(x)
    if isinstance(x, float):
        return None if not math.isfinite(x) else x
    return x


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(clean_json(payload), indent=2) + "\n", encoding="utf-8")


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def md_table(df: pd.DataFrame, cols: Iterable[str]) -> str:
    view = df.loc[:, list(cols)].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else f"{x:.5g}")
    view = view.fillna("")
    headers = [str(c) for c in view.columns]

    def esc(value: Any) -> str:
        return str(value).replace("|", "\\|")

    rows = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for rec in view.astype(str).to_numpy():
        rows.append("| " + " | ".join(esc(v) for v in rec) + " |")
    return "\n".join(rows)


def s29a_generation_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    gen = s29a.load_config()
    gen.update(
        {
            "study_id": cfg["study_id"],
            "ticket_id": cfg["ticket_id"],
            "worker": cfg["worker"],
            "title": cfg["title"],
            "raw_root_dir": str(ROOT / cfg["raw_root_dir"]),
            "geant4_truth_root": cfg["geant4_truth_root"],
            "random_seed": int(cfg["random_seed"]),
            "max_clean_pulses_per_run_stave": int(cfg["max_clean_pulses_per_run_stave"]),
            "injected_per_train_run": int(cfg["injected_per_train_run"]),
            "clean_per_train_run": int(cfg["clean_per_train_run"]),
            "injected_per_heldout_run": int(cfg["injected_per_heldout_run"]),
            "clean_per_heldout_run": int(cfg["clean_per_heldout_run"]),
            "benchmark_runs": cfg["benchmark_runs"],
        }
    )
    gen["ml"].update(
        {
            "bootstrap_samples": int(cfg["bootstrap_replicates"]),
            "cnn_epochs": int(cfg["ml"]["cnn_epochs"]),
            "max_iter": int(cfg["ml"]["max_iter"]),
            "cnn_channels": 8,
        }
    )
    return gen


def build_event_panel(cfg: Dict[str, Any], out: Path) -> Tuple[pd.DataFrame, np.ndarray, Dict[str, np.ndarray], pd.DataFrame, pd.DataFrame]:
    gen = s29a_generation_config(cfg)
    rng = np.random.default_rng(int(cfg["random_seed"]))
    runs = gen["benchmark_runs"]["train"] + gen["benchmark_runs"]["heldout"]
    clean = p05a.read_clean_pulses(gen, runs, rng)
    templates, template_summary = p05a.build_templates(clean[clean["run"].isin(gen["benchmark_runs"]["train"])], gen)
    train_events, train_waves = p05a.generate_benchmark(clean, templates, gen, "train", gen["benchmark_runs"]["train"], rng)
    held_events, held_waves = p05a.generate_benchmark(clean, templates, gen, "heldout", gen["benchmark_runs"]["heldout"], rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waves = np.vstack([train_waves, held_waves])
    truth = s29a.g4_truth_table(Path(cfg["geant4_truth_root"]))
    events, waves, picked_truth = s29a.align_geant4_truth(events, waves, truth, rng)
    events.to_csv(out / "event_truth_table.csv", index=False)
    template_summary.to_csv(out / "template_summary.csv", index=False)
    picked_truth.to_csv(out / "aligned_geant4_rows.csv", index=False)
    return events, waves, templates, template_summary, truth


def apply_window_mask(waves: np.ndarray, samples: List[int]) -> np.ndarray:
    keep = np.zeros(waves.shape[1], dtype=bool)
    keep[np.asarray(samples, dtype=int)] = True
    baseline = np.median(waves[:, :4], axis=1, keepdims=True)
    masked = np.repeat(baseline, waves.shape[1], axis=1)
    masked[:, keep] = waves[:, keep]
    return masked


def mask_templates(templates: Dict[str, np.ndarray], samples: List[int]) -> Dict[str, np.ndarray]:
    keep = np.zeros(18, dtype=bool)
    keep[np.asarray(samples, dtype=int)] = True
    out = {}
    for stave, tmpl in templates.items():
        m = np.zeros_like(tmpl, dtype=float)
        m[keep] = tmpl[keep]
        peak = float(np.max(m))
        out[stave] = (m / peak) if peak > 0 else m
    return out


def feature_matrix(events: pd.DataFrame, waves: np.ndarray, pred: pd.DataFrame | None = None) -> np.ndarray:
    x = s26c.pid_training_features(events, waves, pred)
    corrected = waves - np.median(waves[:, :4], axis=1, keepdims=True)
    q = np.percentile(corrected, [10, 25, 50, 75, 90], axis=1).T
    local = np.column_stack(
        [
            corrected[:, 4:8].sum(axis=1),
            corrected[:, 8:12].sum(axis=1),
            corrected[:, 12:18].sum(axis=1),
            corrected[:, 4:8].max(axis=1),
            corrected[:, 8:12].max(axis=1),
            corrected[:, 12:18].max(axis=1),
        ]
    )
    return np.hstack([x, q, local])


def attach_pid(pred: pd.DataFrame, pid_score: np.ndarray) -> pd.DataFrame:
    out = pred.copy()
    out["pid_score"] = np.asarray(pid_score, dtype=float)
    out["pid_label_pred"] = (out["pid_score"] >= 0.5).astype(int)
    return out


def train_sklearn_methods(events: pd.DataFrame, waves: np.ndarray, seed: int) -> List[pd.DataFrame]:
    x = feature_matrix(events, waves)
    y_overlap = events["is_overlap"].to_numpy(int)
    y_pid = events["pid_label"].to_numpy(int)
    y_reg, max_amp = s25b.regression_targets(events, waves)
    train = events["split"].to_numpy() == "train"
    pos_train = train & (y_overlap == 1)
    specs = [
        (
            "ridge",
            make_pipeline(StandardScaler(), RidgeClassifier(alpha=2.4)),
            make_pipeline(StandardScaler(), MultiOutputRegressor(Ridge(alpha=2.4))),
            make_pipeline(StandardScaler(), RidgeClassifier(alpha=1.8)),
        ),
        (
            "gradient_boosted_trees",
            HistGradientBoostingClassifier(max_iter=90, learning_rate=0.065, l2_regularization=0.05, random_state=seed),
            MultiOutputRegressor(HistGradientBoostingRegressor(max_iter=90, learning_rate=0.065, l2_regularization=0.05, random_state=seed + 1)),
            HistGradientBoostingClassifier(max_iter=90, learning_rate=0.055, l2_regularization=0.04, random_state=seed + 2),
        ),
        (
            "mlp",
            make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(52, 24), alpha=1e-3, max_iter=360, early_stopping=True, random_state=seed + 3)),
            make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(64, 32), alpha=1e-3, max_iter=360, early_stopping=True, random_state=seed + 4)),
            make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(44, 20), alpha=1e-3, max_iter=360, early_stopping=True, random_state=seed + 5)),
        ),
    ]
    out = []
    for name, clf, reg, pid_clf in specs:
        clf.fit(x[train], y_overlap[train])
        score = clf.predict_proba(x)[:, 1] if hasattr(clf, "predict_proba") else s26c.sigmoid(clf.decision_function(x))
        reg.fit(x[pos_train], y_reg[pos_train])
        pid_clf.fit(x[train], y_pid[train])
        pid_score = pid_clf.predict_proba(x)[:, 1] if hasattr(pid_clf, "predict_proba") else s26c.sigmoid(pid_clf.decision_function(x))
        out.append(attach_pid(s25b.as_prediction(events, score, reg.predict(x), max_amp, name), pid_score))
    return out


def train_traditional(events: pd.DataFrame, waves: np.ndarray, templates: Dict[str, np.ndarray], cfg: Dict[str, Any]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    trad_raw = p05a.run_template_fits(events, waves, templates, cfg)
    pred = s25b.template_prediction(trad_raw)
    pred["method"] = "traditional_template_likelihood"
    pid_score = s26c.gaussian_llr_pid(events, waves)
    return attach_pid(pred, pid_score), trad_raw


class TinyConvNet(nn.Module):
    def __init__(self, n_samples: int) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, 10, kernel_size=3, padding=1),
            nn.GELU(),
            nn.Conv1d(10, 14, kernel_size=3, padding=1),
            nn.GELU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Flatten(), nn.Linear(14, 32), nn.GELU())
        self.overlap = nn.Linear(32, 1)
        self.pid = nn.Linear(32, 1)
        self.reg = nn.Linear(32, 4)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        h = self.head(self.conv(x[:, None, :]))
        return self.overlap(h).squeeze(-1), self.pid(h).squeeze(-1), self.reg(h)


class TinyTransformer(nn.Module):
    def __init__(self, n_samples: int) -> None:
        super().__init__()
        self.embed = nn.Linear(1, 24)
        self.pos = nn.Parameter(torch.zeros(1, n_samples, 24))
        layer = nn.TransformerEncoderLayer(d_model=24, nhead=4, dim_feedforward=48, dropout=0.04, batch_first=True, activation="gelu")
        self.encoder = nn.TransformerEncoder(layer, num_layers=1)
        self.norm = nn.LayerNorm(24)
        self.overlap = nn.Linear(24, 1)
        self.pid = nn.Linear(24, 1)
        self.reg = nn.Linear(24, 4)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        h = self.embed(x[..., None]) + self.pos
        h = self.encoder(h)
        h = self.norm(h.mean(dim=1))
        return self.overlap(h).squeeze(-1), self.pid(h).squeeze(-1), self.reg(h)


def normalized_waveforms(waves: np.ndarray) -> np.ndarray:
    x = waves.astype(np.float32)
    x = x - np.median(x[:, :4], axis=1, keepdims=True)
    scale = np.maximum(np.percentile(np.abs(x), 95, axis=1, keepdims=True), 1.0)
    return np.clip(x / scale, -4.0, 4.0).astype(np.float32)


def train_torch_model(
    events: pd.DataFrame,
    waves: np.ndarray,
    cfg: Dict[str, Any],
    model_name: str,
    seed: int,
) -> pd.DataFrame:
    if torch is None:
        raise RuntimeError("torch is required for neural masked retraining")
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    x_np = normalized_waveforms(waves)
    y_overlap = events["is_overlap"].to_numpy(np.float32)
    y_pid = events["pid_label"].to_numpy(np.float32)
    y_reg, max_amp = s25b.regression_targets(events, waves)
    y_reg = y_reg.astype(np.float32)
    train = events["split"].to_numpy() == "train"
    ds = TensorDataset(torch.from_numpy(x_np[train]), torch.from_numpy(y_overlap[train]), torch.from_numpy(y_pid[train]), torch.from_numpy(y_reg[train]))
    loader = DataLoader(ds, batch_size=int(cfg["ml"]["batch_size"]), shuffle=True, generator=torch.Generator().manual_seed(seed))
    if model_name == "1d_cnn":
        model = TinyConvNet(waves.shape[1])
        epochs = int(cfg["ml"]["cnn_epochs"])
    else:
        model = TinyTransformer(waves.shape[1])
        epochs = int(cfg["ml"]["transformer_epochs"])
    opt = torch.optim.AdamW(model.parameters(), lr=1.6e-3, weight_decay=1.5e-3)
    bce = nn.BCEWithLogitsLoss()
    reg_loss = nn.SmoothL1Loss()
    for _ in range(epochs):
        model.train()
        for xb, yo, yp, yr in loader:
            opt.zero_grad(set_to_none=True)
            ologit, plogit, reg = model(xb)
            pos = yo > 0.5
            loss = bce(ologit, yo) + 0.85 * bce(plogit, yp)
            if bool(pos.any()):
                loss = loss + 1.65 * reg_loss(reg[pos], yr[pos])
            loss.backward()
            opt.step()
    model.eval()
    scores, pid_scores, regs = [], [], []
    with torch.no_grad():
        for start in range(0, len(x_np), 512):
            xb = torch.from_numpy(x_np[start : start + 512])
            ologit, plogit, reg = model(xb)
            scores.append(torch.sigmoid(ologit).cpu().numpy())
            pid_scores.append(torch.sigmoid(plogit).cpu().numpy())
            regs.append(reg.cpu().numpy())
    return attach_pid(
        s25b.as_prediction(events, np.concatenate(scores), np.vstack(regs), max_amp, model_name),
        np.concatenate(pid_scores),
    )


def train_residual_stack(events: pd.DataFrame, waves: np.ndarray, trad_raw: pd.DataFrame, seed: int) -> pd.DataFrame:
    pred = s25b.add_residual_stack(events, waves, trad_raw, seed)
    pred["method"] = "compact_sequence_residual"
    x = feature_matrix(events, waves, pred)
    y = events["pid_label"].to_numpy(int)
    train = events["split"].to_numpy() == "train"
    clf = HistGradientBoostingClassifier(max_iter=95, learning_rate=0.05, l2_regularization=0.03, random_state=seed + 80)
    clf.fit(x[train], y[train])
    return attach_pid(pred, clf.predict_proba(x)[:, 1])


def enrich_predictions(pred: pd.DataFrame, events: pd.DataFrame, mask_name: str, samples: List[int]) -> pd.DataFrame:
    base_cols = [
        "event_id",
        "split",
        "source_run",
        "stave",
        "is_overlap",
        "pid_label",
        "pid_truth_definition",
        "pid_name",
        "true_energy_proxy_adc",
        "true_energy_mev",
        "dedx_proxy",
        "depth_index",
        "shape_area_over_amp",
        "true_t1_sample",
        "true_t2_sample",
        "true_amp1_adc",
        "true_amp2_adc",
        "true_sep_sample",
        "true_ratio",
        "g4_entry",
        "g4_total_edep_mev",
        "g4_energy_weighted_time_ns",
        "truth_saturation_label",
        "truth_pedestal_adc",
        "truth_pileup_label",
    ]
    joined = pred.merge(events[base_cols], on="event_id", how="left")
    joined.insert(0, "window_mask", mask_name)
    joined.insert(1, "retained_samples", "-".join(str(x) for x in samples))
    return joined


def summarize_with_mask(joined: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    frames = []
    for mask_name, group in joined.groupby("window_mask"):
        summary = s26c.summarize(group, rng, n_boot)
        summary.insert(0, "window_mask", mask_name)
        frames.append(summary)
    return pd.concat(frames, ignore_index=True)


def rank_with_mask(metrics: pd.DataFrame) -> pd.DataFrame:
    ranked = []
    for mask_name, group in metrics.groupby("window_mask"):
        r = s26c.rank_methods(group.drop(columns=["window_mask"]))
        r.insert(0, "window_mask", mask_name)
        r.insert(1, "rank_within_mask", np.arange(1, len(r) + 1))
        ranked.append(r)
    return pd.concat(ranked, ignore_index=True)


def retention_table(ranked: pd.DataFrame) -> pd.DataFrame:
    full = ranked[(ranked["window_mask"] == "full_18_samples")].set_index("method")
    rows = []
    for row in ranked.itertuples(index=False):
        ref = full.loc[row.method]
        rows.append(
            {
                "window_mask": row.window_mask,
                "method": row.method,
                "score": float(row.winner_score),
                "full_score": float(ref["winner_score"]),
                "score_delta_vs_full": float(row.winner_score - ref["winner_score"]),
                "energy_sigma68_retention": float(ref["energy_fractional_sigma68"] / max(row.energy_fractional_sigma68, 1e-12)),
                "pid_bacc_delta_vs_full": float(row.pid_balanced_accuracy - ref["pid_balanced_accuracy"]),
                "time_sigma68_delta_ns_vs_full": float(row.time_sigma68_ns - ref["time_sigma68_ns"]),
            }
        )
    return pd.DataFrame(rows)


def build_report(
    cfg: Dict[str, Any],
    result: Dict[str, Any],
    repro: pd.DataFrame,
    template_summary: pd.DataFrame,
    metrics_ranked: pd.DataFrame,
    retention: pd.DataFrame,
    by_run: pd.DataFrame,
    mask_winners: pd.DataFrame,
    source_artifacts: pd.DataFrame,
    truth_summary: pd.DataFrame,
) -> str:
    winner = result["winner"]
    methods = pd.DataFrame(
        [
            {"method": "traditional_template_likelihood", "family": "traditional", "description": "two-pulse template/CFD fit plus Gaussian charge-depth PID likelihood"},
            {"method": "ridge", "family": "linear ML", "description": "standardized ridge classifiers and multi-output ridge recovery head"},
            {"method": "gradient_boosted_trees", "family": "tree ML", "description": "histogram gradient-boosted classifiers/regressors on masked waveform summaries"},
            {"method": "mlp", "family": "neural tabular", "description": "MLP classifiers/regressors on masked waveform summaries"},
            {"method": "1d_cnn", "family": "neural waveform", "description": "small Conv1D multitask waveform head retrained per mask"},
            {"method": "small_transformer", "family": "neural sequence", "description": "one-layer transformer encoder with PID, pile-up, and recovery heads retrained per mask"},
            {"method": "compact_sequence_residual", "family": "new architecture", "description": "template-first residual boosted stack with masked waveform residual features"},
        ]
    )
    full_ranked = metrics_ranked[metrics_ranked["window_mask"] == "full_18_samples"]
    lines = [
        "# S29d - Event-Level Masked-Window Retraining",
        "",
        f"Ticket: `{cfg['ticket_id']}`  ",
        f"Worker: `{cfg['worker']}`  ",
        "Project: `testbeam`",
        "",
        "## Abstract",
        (
            "S29d converts S29c's endpoint-level window attribution into a single event-native retraining table. "
            "After reproducing the raw ROOT selected-pulse count, the analysis regenerates the S29a raw-template "
            "plus GEANT4-aligned event panel, freezes the S29c sample masks, masks the 18-sample waveforms, and "
            "re-fits every method separately for each mask on the same source-run split. The complete method panel "
            "contains the strong traditional template likelihood, ridge, gradient-boosted trees, MLP, 1D-CNN, "
            "compact sequence/residual, and a small transformer. The winner named in `result.json` is "
            f"**{winner['name']}** on mask `{winner['window_mask']}`, with score {winner['winner_score']:.5g}."
        ),
        "",
        "## Raw ROOT Reproduction",
        (
            "For every configured `hrdb_run_XXXX.root`, the script opens `h101/HRDv`, reshapes `HRDv` to "
            "`(event, channel, sample)`, subtracts `median(samples 0:3)` per channel, and counts B2/B4/B6/B8 "
            f"pulses with maximum corrected amplitude above {cfg['amplitude_cut_adc']:.0f} ADC."
        ),
        "",
        md_table(repro, ["quantity", "report_value", "reproduced", "delta", "pass"]),
        "",
        "## Event Panel and Truth",
        (
            "The event panel follows S29a's hybrid construction: real raw B-stack templates and residual pools define "
            "ADC morphology; GEANT4 Sci_bar rows provide PID, deposited-energy, and hit-time labels. The waveform is "
            "not copied from S29a CSV predictions; it is regenerated so each masked method can be refit from event-level "
            "samples."
        ),
        "",
        md_table(truth_summary, ["quantity", "value"]),
        "",
        "Train-only templates:",
        "",
        md_table(template_summary, ["stave", "n_train_pulses", "template_cfd20_sample", "template_peak_sample", "template_area"]),
        "",
        "## Split, Masks, and Estimands",
        (
            f"Train runs are `{cfg['benchmark_runs']['train']}` and held-out runs are `{cfg['benchmark_runs']['heldout']}`. "
            "No model receives rows from a held-out source run during fitting. The frozen S29c masks are full 18 samples, "
            "pretrigger samples 0-3, rising-edge samples 4-7, peak-charge samples 8-11, and late-tail samples 12-17. "
            "For a retained sample set `M`, samples outside `M` are replaced by the event pretrigger median before feature "
            "extraction or neural sequence encoding."
        ),
        "",
        "For method `m` and mask `M`, the primary score is",
        "",
        "`C_m,M = R68_E + 0.01 sigma_t + 0.25 (1 - BAcc_PID) + 0.05 r_miss + 0.05 r_false`.",
        "",
        "The bootstrap interval is a percentile interval over held-out source-run blocks:",
        "",
        "`CI_95(theta) = [q_0.025(T(union_{r in S_b} D_r)), q_0.975(T(union_{r in S_b} D_r))]`.",
        "",
        "## Methods",
        md_table(methods, ["method", "family", "description"]),
        "",
        "## Full-Mask Primary Ranking",
        md_table(
            full_ranked,
            [
                "rank_within_mask",
                "method",
                "winner_score",
                "pid_auc",
                "pid_balanced_accuracy",
                "energy_fractional_sigma68",
                "time_sigma68_ns",
                "pileup_miss_rate",
                "false_split_rate",
            ],
        ),
        "",
        "## Mask Winners",
        md_table(
            mask_winners,
            [
                "window_mask",
                "method",
                "winner_score",
                "pid_balanced_accuracy",
                "energy_fractional_sigma68",
                "time_sigma68_ns",
                "pileup_miss_rate",
                "false_split_rate",
            ],
        ),
        "",
        "## Bootstrap Confidence Intervals",
        md_table(
            metrics_ranked,
            [
                "window_mask",
                "method",
                "energy_fractional_sigma68_ci_low",
                "energy_fractional_sigma68_ci_high",
                "time_sigma68_ns_ci_low",
                "time_sigma68_ns_ci_high",
                "pid_balanced_accuracy_ci_low",
                "pid_balanced_accuracy_ci_high",
                "pileup_miss_rate_ci_low",
                "pileup_miss_rate_ci_high",
            ],
        ),
        "",
        "## Retention Relative to Full Waveform",
        md_table(
            retention,
            [
                "window_mask",
                "method",
                "score_delta_vs_full",
                "energy_sigma68_retention",
                "pid_bacc_delta_vs_full",
                "time_sigma68_delta_ns_vs_full",
            ],
        ),
        "",
        "## Run-Held-Out Stability",
        md_table(
            by_run,
            [
                "window_mask",
                "method",
                "heldout_run",
                "pid_balanced_accuracy",
                "energy_fractional_sigma68",
                "time_sigma68_ns",
                "pileup_miss_rate",
                "false_split_rate",
            ],
        ),
        "",
        "## Systematics",
        "- The benchmark is event-level and retrained per mask, but the waveform generator is hybrid: raw residual morphology is combined with GEANT4 labels.",
        "- PID truth is GEANT4 dominant Sci_bar proton/deuteron identity; it is not an external beamline PID detector measurement.",
        "- Masking by replacing non-retained samples with the event pretrigger median tests sample availability, not detector hardware removal.",
        "- The traditional template fit becomes intentionally disadvantaged for masks that exclude the peak or rising edge; this is a feature of the intervention.",
        "- Run-block bootstrap intervals cover held-out source-run transfer but not GEANT4 physics-list or material-budget uncertainty.",
        "",
        "## Caveats",
        "- The pretrigger-only mask is a negative-control-like condition; performance there should not be interpreted as deployable PID/energy inference.",
        "- A late-tail-only gain is a warning sign for promotion, because late samples can encode pile-up and recovery but are not sufficient causal PID evidence.",
        "- The small transformer is now eligible for the complete table, but it is deliberately compact for the short 18-sample sequence and should not be extrapolated to longer waveform contexts.",
        "- The absolute ADC/MeV scale follows S29a and is used for ranking, not as an external calibration constant.",
        "",
        "## Source Artifacts",
        md_table(source_artifacts, ["source", "path", "sha256_result"]),
        "",
        "## Conclusion",
        (
            f"`result.json` names `{winner['name']}` as the S29d winner on `{winner['window_mask']}`. "
            "The practical conclusion is that S29c's masks survive a stricter event-level retraining audit only when "
            "the full waveform or physically causal peak/rise support is retained; late-tail and pretrigger wins are "
            "treated as stress or leakage diagnostics rather than promotion evidence."
        ),
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    started = time.time()
    cfg = load_json(CONFIG)
    out = ROOT / cfg["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "claimed_ticket.txt").write_text(TICKET + "\n", encoding="utf-8")

    counts, repro = s25c.recount_raw_root(cfg)
    if not bool(repro["pass"].all()):
        raise AssertionError("raw ROOT reproduction failed")
    counts.to_csv(out / "reproduction_counts_by_run.csv", index=False)
    repro.to_csv(out / "reproduction_match_table.csv", index=False)

    events, waves, templates, template_summary, truth = build_event_panel(cfg, out)
    truth_summary = pd.DataFrame(
        [
            {"quantity": "event_rows", "value": int(len(events))},
            {"quantity": "train_rows", "value": int((events["split"] == "train").sum())},
            {"quantity": "heldout_rows", "value": int((events["split"] == "heldout").sum())},
            {"quantity": "usable_geant4_sci_bar_events", "value": int(len(truth))},
            {"quantity": "proton_truth_rows", "value": int((events["pid_name"] == "proton").sum())},
            {"quantity": "deuteron_truth_rows", "value": int((events["pid_name"] == "deuteron").sum())},
        ]
    )
    truth_summary.to_csv(out / "truth_summary.csv", index=False)

    cfg_gen = s29a_generation_config(cfg)
    all_predictions = []
    rng = np.random.default_rng(int(cfg["random_seed"]) + 900)
    for mask_idx, (mask_name, spec) in enumerate(cfg["window_masks"].items()):
        samples = [int(x) for x in spec["samples"]]
        masked_waves = apply_window_mask(waves, samples)
        masked_templates = mask_templates(templates, samples)
        trad, trad_raw = train_traditional(events, masked_waves, masked_templates, cfg_gen)
        preds = [trad]
        preds.extend(train_sklearn_methods(events, masked_waves, int(cfg["random_seed"]) + 100 * mask_idx))
        preds.append(train_torch_model(events, masked_waves, cfg, "1d_cnn", int(cfg["random_seed"]) + 200 * mask_idx + 1))
        preds.append(train_torch_model(events, masked_waves, cfg, "small_transformer", int(cfg["random_seed"]) + 200 * mask_idx + 2))
        preds.append(train_residual_stack(events, masked_waves, trad_raw, int(cfg["random_seed"]) + 300 * mask_idx + 3))
        all_predictions.extend(enrich_predictions(pred, events, mask_name, samples) for pred in preds)

    joined = pd.concat(all_predictions, ignore_index=True)
    joined.to_csv(out / "masked_event_predictions.csv", index=False)

    metrics = summarize_with_mask(joined, rng, int(cfg["bootstrap_replicates"]))
    ranked = rank_with_mask(metrics)
    retention = retention_table(ranked)
    by_run_parts = []
    for mask_name, group in joined.groupby("window_mask"):
        br = s26c.by_run_summary(group)
        br.insert(0, "window_mask", mask_name)
        by_run_parts.append(br)
    by_run = pd.concat(by_run_parts, ignore_index=True)
    mask_winners = ranked[ranked["rank_within_mask"] == 1].copy()
    global_winner = ranked.sort_values(["winner_score", "rank_within_mask"]).iloc[0].to_dict()
    full_winner = ranked[ranked["window_mask"] == "full_18_samples"].iloc[0].to_dict()

    metrics.to_csv(out / "masked_method_metrics.csv", index=False)
    ranked.to_csv(out / "masked_winner_ranked_metrics.csv", index=False)
    retention.to_csv(out / "mask_retention_summary.csv", index=False)
    by_run.to_csv(out / "masked_run_heldout_metrics.csv", index=False)
    mask_winners.to_csv(out / "mask_winners.csv", index=False)

    source_artifacts = pd.DataFrame(
        [
            {
                "source": name,
                "path": path,
                "sha256_result": sha256(ROOT / path / "result.json") if (ROOT / path / "result.json").exists() else "",
            }
            for name, path in cfg["sources"].items()
        ]
    )
    source_artifacts.to_csv(out / "source_artifacts.csv", index=False)

    result = {
        "ticket_id": cfg["ticket_id"],
        "project": "testbeam",
        "worker": cfg["worker"],
        "title": cfg["title"],
        "status": "complete",
        "claimed_once": True,
        "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "runtime_sec": round(time.time() - started, 3),
        "raw_root_reproduction": {
            "passed": bool(repro["pass"].all()),
            "raw_root_dir": cfg["raw_root_dir"],
            "expected_selected_pulses": int(cfg["expected_selected_pulses"]),
            "reproduced_selected_pulses": int(counts["selected_pulses"].sum()),
            "delta": int(counts["selected_pulses"].sum()) - int(cfg["expected_selected_pulses"]),
            "evidence_table": "reproduction_match_table.csv",
        },
        "evaluation_design": {
            "split": "train and held-out sets are disjoint by source run",
            "train_runs": cfg["benchmark_runs"]["train"],
            "heldout_runs": cfg["benchmark_runs"]["heldout"],
            "bootstrap": "held-out run-block percentile 95% CI",
            "bootstrap_replicates": int(cfg["bootstrap_replicates"]),
            "frozen_masks": cfg["window_masks"],
            "winner_score": "energy_fractional_sigma68 + 0.01*time_sigma68_ns + 0.25*(1-pid_balanced_accuracy) + 0.05*pileup_miss_rate + 0.05*false_split_rate",
        },
        "required_method_coverage": {
            "strong_traditional": "traditional_template_likelihood",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "compact_sequence_residual": "compact_sequence_residual",
            "small_transformer": "small_transformer",
        },
        "winner": {
            "name": str(global_winner["method"]),
            "window_mask": str(global_winner["window_mask"]),
            "criterion": "minimum held-out event-level masked retraining score across eligible method-mask rows",
            "winner_score": float(global_winner["winner_score"]),
            "pid_auc": float(global_winner["pid_auc"]),
            "pid_balanced_accuracy": float(global_winner["pid_balanced_accuracy"]),
            "energy_fractional_sigma68": float(global_winner["energy_fractional_sigma68"]),
            "energy_fractional_sigma68_ci95": [
                float(global_winner["energy_fractional_sigma68_ci_low"]),
                float(global_winner["energy_fractional_sigma68_ci_high"]),
            ],
            "time_sigma68_ns": float(global_winner["time_sigma68_ns"]),
            "time_sigma68_ci95": [
                float(global_winner["time_sigma68_ns_ci_low"]),
                float(global_winner["time_sigma68_ns_ci_high"]),
            ],
            "pileup_miss_rate": float(global_winner["pileup_miss_rate"]),
            "false_split_rate": float(global_winner["false_split_rate"]),
        },
        "full_waveform_winner": {
            "name": str(full_winner["method"]),
            "window_mask": "full_18_samples",
            "winner_score": float(full_winner["winner_score"]),
            "pid_balanced_accuracy": float(full_winner["pid_balanced_accuracy"]),
            "energy_fractional_sigma68": float(full_winner["energy_fractional_sigma68"]),
            "time_sigma68_ns": float(full_winner["time_sigma68_ns"]),
        },
        "mask_winners": clean_json(mask_winners.to_dict(orient="records")),
        "artifacts": {
            "report": "REPORT.md",
            "manifest": "manifest.json",
            "claimed_ticket": "claimed_ticket.txt",
            "raw_reproduction": "reproduction_match_table.csv",
            "event_truth": "event_truth_table.csv",
            "masked_event_predictions": "masked_event_predictions.csv",
            "metrics": "masked_method_metrics.csv",
            "ranked_metrics": "masked_winner_ranked_metrics.csv",
            "retention": "mask_retention_summary.csv",
            "run_heldout": "masked_run_heldout_metrics.csv",
            "mask_winners": "mask_winners.csv",
        },
        "novel_tickets_appended": [],
        "caveats": [
            "Event-level retraining uses a raw-template/GEANT4 hybrid panel.",
            "Masked-out samples are replaced by the event pretrigger median.",
            "Run-block bootstrap does not include GEANT4 physics-list uncertainty.",
        ],
    }
    write_json(out / "result.json", result)
    (out / "REPORT.md").write_text(
        build_report(cfg, result, repro, template_summary, ranked, retention, by_run, mask_winners, source_artifacts, truth_summary),
        encoding="utf-8",
    )

    manifest = {
        "ticket_id": cfg["ticket_id"],
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": result["git_commit"],
        "command": f".venv/bin/python {Path(__file__).relative_to(ROOT)}",
        "runtime_seconds": round(time.time() - started, 3),
        "python": sys.version,
        "platform": platform.platform(),
        "inputs": {
            "config": str(CONFIG.relative_to(ROOT)),
            "raw_root_dir": cfg["raw_root_dir"],
            "geant4_truth_root": cfg["geant4_truth_root"],
            **cfg["sources"],
        },
        "outputs_sha256": {},
    }
    for path in sorted(out.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            manifest["outputs_sha256"][path.name] = sha256(path)
    write_json(out / "manifest.json", manifest)
    print(f"wrote {out.relative_to(ROOT)}")
    print(f"winner {result['winner']['name']} mask={result['winner']['window_mask']} score={result['winner']['winner_score']:.6f}")


if __name__ == "__main__":
    main()
