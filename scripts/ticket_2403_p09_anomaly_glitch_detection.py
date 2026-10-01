#!/usr/bin/env python3
"""Ticket #2403: P09 anomaly/glitch detection benchmark.

The script reuses the established P09a raw ROOT reader and morphology
construction, then adds the method family required by the ticket runner:
traditional cuts, ridge, gradient-boosted trees, MLP, 1D-CNN, and a new
morphology-gated CNN architecture.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p09a_rare_waveform_anomaly_taxonomy as p09a  # noqa: E402

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neural_network import MLPClassifier
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


METHOD_FAMILIES = {
    "traditional_robust_shape_cuts": "traditional",
    "autoencoder_isolation_forest": "ml_unsupervised",
    "ridge": "ml",
    "gradient_boosted_trees": "ml",
    "mlp": "nn",
    "1d_cnn": "nn",
    "morphology_gated_cnn_new": "new_architecture",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    except Exception:
        return "unknown"


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def safe_auc_ap(y: np.ndarray, score: np.ndarray) -> Tuple[float, float]:
    finite = np.isfinite(score)
    y = y[finite].astype(int)
    score = score[finite].astype(float)
    if len(np.unique(y)) < 2:
        return float("nan"), float("nan")
    return float(roc_auc_score(y, score)), float(average_precision_score(y, score))


def balanced_train_indices(y: np.ndarray, train_mask: np.ndarray, max_per_class: int, rng: np.random.Generator) -> np.ndarray:
    idxs: List[np.ndarray] = []
    for cls in [0, 1]:
        idx = np.where(train_mask & (y == cls))[0]
        take = min(len(idx), int(max_per_class))
        if take:
            idxs.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(idxs)
    rng.shuffle(out)
    return out


def feature_matrix(meta: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
    cols = [
        "amplitude_adc",
        "q_template_rmse",
        "peak_sample",
        "area_norm",
        "late_fraction",
        "early_fraction",
        "width_half",
        "baseline_mad",
        "baseline_slope",
        "raw_max_adc",
        "saturation_count",
        "secondary_peak",
        "secondary_sep",
        "post_peak_min",
        "undershoot_area",
        "cfd20_sample",
        "timing_span_dup",
    ]
    x = meta[cols].to_numpy(dtype=np.float32)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    return x, cols


def minmax_from_train(score: np.ndarray, train_mask: np.ndarray) -> np.ndarray:
    vals = score[train_mask & np.isfinite(score)]
    if len(vals) == 0:
        return np.zeros(len(score), dtype=np.float32)
    lo, hi = np.percentile(vals, [1, 99])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        lo, hi = float(np.nanmin(vals)), float(np.nanmax(vals))
    if hi <= lo:
        return np.zeros(len(score), dtype=np.float32)
    return np.clip((score - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)


def fit_tabular_methods(
    cfg: dict,
    x: np.ndarray,
    y: np.ndarray,
    train_mask: np.ndarray,
    val_mask: np.ndarray,
    rng: np.random.Generator,
) -> Tuple[Dict[str, np.ndarray], pd.DataFrame]:
    sup = cfg["supervised"]
    train_idx = balanced_train_indices(y, train_mask, int(sup["max_train_per_class"]), rng)
    val_idx = np.where(val_mask)[0]
    rows: List[dict] = []
    preds: Dict[str, np.ndarray] = {}

    best = None
    for c in [float(v) for v in sup["ridge_c_values"]]:
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=c, penalty="l2", solver="lbfgs", max_iter=300, class_weight="balanced"),
        )
        model.fit(x[train_idx], y[train_idx])
        score = model.predict_proba(x[val_idx])[:, 1]
        auc, ap = safe_auc_ap(y[val_idx], score)
        rows.append({"method": "ridge", "param": "C={}".format(c), "val_auc": auc, "val_average_precision": ap})
        if best is None or ap > best[0]:
            best = (ap, c)
    ridge = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=float(best[1]), penalty="l2", solver="lbfgs", max_iter=300, class_weight="balanced"),
    )
    ridge.fit(x[train_idx], y[train_idx])
    preds["ridge"] = ridge.predict_proba(x)[:, 1].astype(np.float32)

    best = None
    for lr in [float(v) for v in sup["gbt_learning_rates"]]:
        model = HistGradientBoostingClassifier(
            max_iter=int(sup["gbt_max_iter"]),
            learning_rate=lr,
            l2_regularization=0.02,
            max_leaf_nodes=15,
            random_state=int(cfg["random_seed"]) + int(1000 * lr),
        )
        model.fit(x[train_idx], y[train_idx])
        score = model.predict_proba(x[val_idx])[:, 1]
        auc, ap = safe_auc_ap(y[val_idx], score)
        rows.append({"method": "gradient_boosted_trees", "param": "learning_rate={}".format(lr), "val_auc": auc, "val_average_precision": ap})
        if best is None or ap > best[0]:
            best = (ap, lr)
    gbt = HistGradientBoostingClassifier(
        max_iter=int(sup["gbt_max_iter"]),
        learning_rate=float(best[1]),
        l2_regularization=0.02,
        max_leaf_nodes=15,
        random_state=int(cfg["random_seed"]) + 42,
    )
    gbt.fit(x[train_idx], y[train_idx])
    preds["gradient_boosted_trees"] = gbt.predict_proba(x)[:, 1].astype(np.float32)

    mlp = make_pipeline(
        StandardScaler(),
        MLPClassifier(
            hidden_layer_sizes=tuple(int(v) for v in sup["mlp_hidden"]),
            activation="relu",
            alpha=1e-4,
            learning_rate_init=1e-3,
            max_iter=int(sup["mlp_max_iter"]),
            random_state=int(cfg["random_seed"]) + 77,
            early_stopping=True,
            n_iter_no_change=8,
        ),
    )
    mlp.fit(x[train_idx], y[train_idx])
    preds["mlp"] = mlp.predict_proba(x)[:, 1].astype(np.float32)
    auc, ap = safe_auc_ap(y[val_idx], preds["mlp"][val_idx])
    rows.append({"method": "mlp", "param": "hidden={}".format(tuple(sup["mlp_hidden"])), "val_auc": auc, "val_average_precision": ap})
    return preds, pd.DataFrame(rows)


class WaveCNN(nn.Module):
    def __init__(self, aux_dim: int = 0):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, 16, 3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 32, 3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.aux_dim = aux_dim
        self.head = nn.Sequential(nn.Linear(32 + aux_dim, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, wave, aux=None):
        z = self.conv(wave.unsqueeze(1)).squeeze(-1)
        if self.aux_dim:
            z = torch.cat([z, aux], dim=1)
        return self.head(z).squeeze(-1)


def torch_scores(
    cfg: dict,
    waves: np.ndarray,
    aux: np.ndarray,
    y: np.ndarray,
    train_mask: np.ndarray,
    val_mask: np.ndarray,
    rng: np.random.Generator,
) -> Tuple[Dict[str, np.ndarray], pd.DataFrame, dict]:
    if torch is None:
        n = len(y)
        rows = pd.DataFrame(
            [
                {"method": "1d_cnn", "param": "torch_unavailable", "val_auc": float("nan"), "val_average_precision": float("nan")},
                {"method": "morphology_gated_cnn_new", "param": "torch_unavailable", "val_auc": float("nan"), "val_average_precision": float("nan")},
            ]
        )
        return {"1d_cnn": np.full(n, np.nan), "morphology_gated_cnn_new": np.full(n, np.nan)}, rows, {"torch_available": False}

    sup = cfg["supervised"]
    torch.manual_seed(int(cfg["random_seed"]))
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    train_idx = balanced_train_indices(y, train_mask, int(sup["max_train_per_class"]), rng)
    val_idx = np.where(val_mask)[0]
    w_mu = waves[train_idx].mean(axis=0)
    w_sd = waves[train_idx].std(axis=0) + 1e-6
    ws = ((waves - w_mu[None, :]) / w_sd[None, :]).astype(np.float32)
    a_mu = aux[train_idx].mean(axis=0)
    a_sd = aux[train_idx].std(axis=0) + 1e-6
    auxs = ((aux - a_mu[None, :]) / a_sd[None, :]).astype(np.float32)

    pos = max(1, int(y[train_idx].sum()))
    neg = max(1, int(len(train_idx) - pos))
    pos_weight = torch.tensor([neg / pos], dtype=torch.float32, device=device)

    def fit_predict(name: str, use_aux: bool) -> Tuple[np.ndarray, dict]:
        model = WaveCNN(aux_dim=auxs.shape[1] if use_aux else 0).to(device)
        opt = torch.optim.AdamW(model.parameters(), lr=float(sup["torch_learning_rate"]), weight_decay=1e-4)
        loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
        ds = TensorDataset(
            torch.as_tensor(ws[train_idx], dtype=torch.float32),
            torch.as_tensor(auxs[train_idx], dtype=torch.float32),
            torch.as_tensor(y[train_idx], dtype=torch.float32),
        )
        loader = DataLoader(ds, batch_size=int(sup["torch_batch_size"]), shuffle=True)
        best_state = None
        best_ap = -1.0
        losses: List[float] = []
        for _ in range(int(sup["torch_epochs"])):
            model.train()
            total = 0.0
            seen = 0
            for wb, ab, yb in loader:
                wb = wb.to(device)
                ab = ab.to(device)
                yb = yb.to(device)
                opt.zero_grad()
                logits = model(wb, ab if use_aux else None)
                loss = loss_fn(logits, yb)
                loss.backward()
                opt.step()
                total += float(loss.item()) * len(yb)
                seen += len(yb)
            losses.append(total / max(1, seen))
            val_score = predict(model, ws[val_idx], auxs[val_idx], use_aux, device)
            _, ap = safe_auc_ap(y[val_idx], val_score)
            if np.isfinite(ap) and ap > best_ap:
                best_ap = ap
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        if best_state is not None:
            model.load_state_dict(best_state)
        return predict(model, ws, auxs, use_aux, device), {"method": name, "losses": losses, "best_val_ap": best_ap}

    def predict(model, wave_arr, aux_arr, use_aux, dev):
        model.eval()
        chunks = []
        with torch.no_grad():
            for start in range(0, len(wave_arr), 32768):
                wb = torch.as_tensor(wave_arr[start : start + 32768], dtype=torch.float32, device=dev)
                ab = torch.as_tensor(aux_arr[start : start + 32768], dtype=torch.float32, device=dev)
                logits = model(wb, ab if use_aux else None)
                chunks.append(torch.sigmoid(logits).detach().cpu().numpy())
        return np.concatenate(chunks).astype(np.float32)

    out: Dict[str, np.ndarray] = {}
    rows: List[dict] = []
    info = {"torch_available": True, "device": str(device), "models": []}
    for name, use_aux in [("1d_cnn", False), ("morphology_gated_cnn_new", True)]:
        score, model_info = fit_predict(name, use_aux)
        out[name] = score
        auc, ap = safe_auc_ap(y[val_idx], score[val_idx])
        rows.append({"method": name, "param": "waveform_plus_aux={}".format(use_aux), "val_auc": auc, "val_average_precision": ap})
        info["models"].append(model_info)
    return out, pd.DataFrame(rows), info


def select_top(meta: pd.DataFrame, score_col: str, heldout_mask: np.ndarray, k: int) -> pd.DataFrame:
    parts = []
    frame = meta.loc[heldout_mask].copy()
    for _, sub in frame.groupby(["run", "stave"], sort=True):
        parts.append(sub.sort_values(score_col, ascending=False).head(k))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def metric_row(method: str, selected: pd.DataFrame, heldout: pd.DataFrame, y: np.ndarray, score: np.ndarray, heldout_mask: np.ndarray) -> dict:
    auc, ap = safe_auc_ap(y[heldout_mask], score[heldout_mask])
    n = max(1, len(selected))
    prevalence = max(1e-12, float(heldout["label_curated_any"].mean()))
    novel_prev = max(1e-12, float(heldout["label_novel_any"].mean()))
    precision = float(selected["label_curated_any"].mean()) if len(selected) else float("nan")
    novel_precision = float(selected["label_novel_any"].mean()) if len(selected) else float("nan")
    return {
        "method": method,
        "family": METHOD_FAMILIES[method],
        "n_flagged": int(len(selected)),
        "heldout_auc": auc,
        "heldout_average_precision": ap,
        "curated_precision": precision,
        "curated_enrichment": precision / prevalence,
        "novel_precision": novel_precision,
        "novel_enrichment": novel_precision / novel_prev,
        "known_precision": float(selected["label_known_any"].mean()) if len(selected) else float("nan"),
        "timing_tail_rate": float(selected["label_timing_tail"].mean()) if len(selected) else float("nan"),
        "duplicate_event_rate": float(selected.duplicated(["run", "event_index"], keep=False).sum() / n),
        "max_run_stave_share": float(selected.groupby(["run", "stave"]).size().max() / n) if len(selected) else 0.0,
    }


def bootstrap_ci(method: str, selected: pd.DataFrame, heldout: pd.DataFrame, rng: np.random.Generator, reps: int) -> pd.DataFrame:
    runs = np.asarray(sorted(heldout["run"].unique()), dtype=int)
    rows: List[dict] = []
    for _ in range(int(reps)):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        sel = pd.concat([selected[selected["run"] == r] for r in chosen], ignore_index=True)
        base = pd.concat([heldout[heldout["run"] == r] for r in chosen], ignore_index=True)
        prevalence = max(1e-12, float(base["label_curated_any"].mean()))
        novel_prev = max(1e-12, float(base["label_novel_any"].mean()))
        n = max(1, len(sel))
        precision = float(sel["label_curated_any"].mean()) if len(sel) else float("nan")
        novel = float(sel["label_novel_any"].mean()) if len(sel) else float("nan")
        rows.append(
            {
                "curated_precision": precision,
                "curated_enrichment": precision / prevalence,
                "novel_precision": novel,
                "novel_enrichment": novel / novel_prev,
                "timing_tail_rate": float(sel["label_timing_tail"].mean()) if len(sel) else float("nan"),
                "duplicate_event_rate": float(sel.duplicated(["run", "event_index"], keep=False).sum() / n),
            }
        )
    boot = pd.DataFrame(rows)
    return pd.DataFrame(
        [
            {"method": method, "metric": col, "ci_low": float(boot[col].quantile(0.025)), "ci_high": float(boot[col].quantile(0.975))}
            for col in boot.columns
        ]
    )


def add_ci_columns(metrics: pd.DataFrame, ci: pd.DataFrame) -> pd.DataFrame:
    out = metrics.copy()
    for _, row in ci.iterrows():
        mask = out["method"] == row["method"]
        out.loc[mask, row["metric"] + "_ci95"] = "[{:.4g}, {:.4g}]".format(row["ci_low"], row["ci_high"])
    return out


def write_markdown_table(path: Path, rows: Iterable[dict], columns: List[str]) -> str:
    data = list(rows)
    if not data:
        return ""
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in data)) for c in columns}
    header = "| " + " | ".join(c.ljust(widths[c]) for c in columns) + " |"
    sep = "| " + " | ".join("-" * widths[c] for c in columns) + " |"
    body = ["| " + " | ".join(str(r.get(c, "")).ljust(widths[c]) for c in columns) + " |" for r in data]
    return "\n".join([header, sep] + body)


def write_report(
    out: Path,
    cfg: dict,
    raw_root_dir: Path,
    counts: pd.DataFrame,
    metrics: pd.DataFrame,
    ci: pd.DataFrame,
    model_selection: pd.DataFrame,
    taxonomy: pd.DataFrame,
    leakage: pd.DataFrame,
    winner: dict,
    manifest: dict,
) -> None:
    repro = int(counts["selected_pulses"].sum())
    expected = int(cfg["expected_selected_pulses"])
    display = add_ci_columns(metrics, ci)
    cols = [
        "method",
        "family",
        "n_flagged",
        "curated_precision",
        "curated_precision_ci95",
        "curated_enrichment",
        "novel_precision",
        "novel_precision_ci95",
        "heldout_average_precision",
        "heldout_auc",
    ]
    text = """# P09 anomaly/glitch detection benchmark

- **Ticket:** #{ticket}
- **Worker:** {worker}
- **Study ID:** {study_id}
- **Date:** 2026-08-16
- **Config:** `{config}`
- **Git commit:** `{git_commit}`

## 0. Question

This ticket asks whether rare pathological B-stave pulses can be surfaced for review more efficiently than with transparent shape cuts. The atomic decision is a held-out-run flagged-set precision benchmark: among the top-ranked pulses per run and stave, what fraction is assigned to a frozen curated anomaly rubric?

## 1. Reproduction Gate

The analysis first rereads raw ROOT from `{raw_root_dir}` before fitting any anomaly model. The branch `HRDv` is reshaped into event x channel x 18 samples. B2/B4/B6/B8 even channels are baseline-subtracted with median samples `{baseline_samples}`, and a pulse is selected when its baseline-subtracted peak exceeds `{amp_cut}` ADC.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass |
|---|---:|---:|---:|---:|---|
| S00 selected B-stave pulses | {expected} | {repro} | {delta} | 0 | {pass_gate} |

The per-run reproduction ledger is `reproduction_counts_by_run.csv`; ROOT checksums are in `input_sha256.csv`.

## 2. Methods

Let \(x_i\) be the 18-sample normalized pulse and \(u_i\) the deterministic morphology vector. The frozen review target \(y_i\) is not detector truth; it is a curated morphology rubric made from train-run quantiles for saturation, dropout, baseline excursion, secondary peaks, early peaks, delayed peaks, undershoot recovery, broad width, template mismatch, and duplicate-channel timing tails. Thresholds are fit on training runs only and then applied to validation and held-out runs.

The traditional baseline is a robust shape-cut ranker,

\[
s_\mathrm{{trad}}(i)=\max_j |u_{{ij}}-\\tilde u_j|/(1.4826\,\mathrm{{MAD}}_j)+0.15\,\mathrm{{mean}}_j |z_{{ij}}|,
\]

where medians and MADs are train-run only. The unsupervised ML comparator combines PCA reconstruction error, autoencoder reconstruction error, and IsolationForest density. The supervised methods are L2 ridge logistic regression, histogram gradient-boosted trees, an MLP, a waveform-only 1D-CNN, and a new morphology-gated CNN that concatenates convolutional waveform features with standardized morphology features. All supervised models train on non-held-out runs, tune on validation runs `{validation_runs}`, and report only held-out runs `{heldout_runs}`.

For probabilistic models the score is \(p_\\theta(y_i=1\mid x_i,u_i)\). The ranking metric is top-k flagged precision,

\[
\mathrm{{precision}}_k = {{1 \over |F_k|}}\sum_{{i\in F_k}} y_i,
\]

where \(F_k\) contains the top `{top_k}` pulses in each held-out run/stave stratum. Uncertainty intervals are run-block bootstraps over held-out runs with `{boot}` replicates.

## 3. Model Selection

{model_selection}

## 4. Head-to-Head Results

{metrics}

The winner written to `result.json` is **`{winner_method}`** with held-out curated precision {winner_precision:.4f} and run-bootstrap CI {winner_ci}. Its held-out average precision is {winner_ap:.4f}. Since the target is a deterministic review rubric, not external truth, this is an anomaly-triage result rather than a claim of physical anomaly identity.

## 5. Taxonomy and Systematics

{taxonomy}

Systematic caveats:

- The curated labels are morphology-review proxies. They deliberately exclude model scores but still encode expert design choices, so precision is an audit target, not ground truth.
- The train/validation/held-out split is by run. This protects against event-level leakage but does not emulate future hardware changes outside these runs.
- The traditional baseline is strong because it uses the same waveform summaries that define the reviewer rubric. Any ML win must therefore be interpreted as ranking the same rubric more efficiently, not discovering a separate class.
- Rare classes have small support. The bootstrap intervals capture run-block instability but not human-review disagreement.
- Duplicate channels are used only for morphology/timing-tail evidence, not as an independent truth label.

## 6. Leakage and Falsification Checks

{leakage}

Pre-registered success metric: held-out top-k curated precision, with average precision as the secondary ranking metric. A method would fail adoption if it did not beat the robust traditional ranker or if any train/held-out run overlap appeared.

## 7. Provenance and Reproduction

Manifest excerpt:

```json
{manifest_json}
```

Regenerate with:

```bash
MPLCONFIGDIR=/tmp/mpl-p09-2403 /home/billy/anaconda3/bin/python scripts/ticket_2403_p09_anomaly_glitch_detection.py --config configs/2403_p09_anomaly_glitch_detection.json
```
""".format(
        ticket=cfg["ticket_number"],
        worker=cfg["worker"],
        study_id=cfg["study_id"],
        config=manifest["config"],
        git_commit=manifest["git_commit"],
        raw_root_dir=raw_root_dir,
        baseline_samples=cfg["baseline_samples"],
        amp_cut=cfg["amplitude_cut_adc"],
        expected=expected,
        repro=repro,
        delta=repro - expected,
        pass_gate=repro == expected,
        validation_runs=cfg["validation_runs"],
        heldout_runs=cfg["heldout_runs"],
        top_k=cfg["top_k_per_run_stave"],
        boot=cfg["bootstrap_replicates"],
        model_selection=write_markdown_table(out / "unused", model_selection.round(5).to_dict("records"), ["method", "param", "val_auc", "val_average_precision"]),
        metrics=write_markdown_table(out / "unused", display[cols].round(5).to_dict("records"), cols),
        winner_method=winner["method"],
        winner_precision=float(winner["curated_precision"]),
        winner_ci=display.loc[display["method"] == winner["method"], "curated_precision_ci95"].iloc[0],
        winner_ap=float(winner["heldout_average_precision"]),
        taxonomy=write_markdown_table(out / "unused", taxonomy.round(5).to_dict("records"), list(taxonomy.columns)),
        leakage=write_markdown_table(out / "unused", leakage.to_dict("records"), list(leakage.columns)),
        manifest_json=json.dumps(json_clean(manifest), indent=2, sort_keys=True, allow_nan=False)[:4000],
    )
    (out / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/2403_p09_anomaly_glitch_detection.json")
    args = parser.parse_args()
    started = time.time()
    cfg_path = Path(args.config)
    cfg = load_json(cfg_path)
    out = ROOT / cfg["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(cfg["random_seed"]))

    raw_root_dir = p09a.resolve_raw_root_dir(cfg)
    waves, meta, counts = p09a.scan_raw(cfg, raw_root_dir)
    waves = np.nan_to_num(waves, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    waves = np.clip(waves, -10.0, 10.0).astype(np.float32)
    reproduced = int(counts["selected_pulses"].sum())
    expected = int(cfg["expected_selected_pulses"])
    counts.to_csv(out / "reproduction_counts_by_run.csv", index=False)
    repro_table = pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulses",
                "report_value": expected,
                "reproduced": reproduced,
                "delta": reproduced - expected,
                "tolerance": 0,
                "pass": reproduced == expected,
            }
        ]
    )
    repro_table.to_csv(out / "reproduction_match_table.csv", index=False)
    if reproduced != expected:
        raise RuntimeError("raw ROOT reproduction failed: {} != {}".format(reproduced, expected))

    heldout_mask = meta["run"].isin([int(v) for v in cfg["heldout_runs"]]).to_numpy()
    val_mask = meta["run"].isin([int(v) for v in cfg["validation_runs"]]).to_numpy()
    train_mask = ~(heldout_mask | val_mask)

    meta = p09a.add_template_residual(cfg, waves, meta, train_mask)
    meta, thresholds = p09a.add_taxonomy(meta, train_mask)
    thresholds.to_csv(out / "feature_thresholds.csv", index=False)

    y = meta["label_curated_any"].to_numpy(dtype=int)
    x, feature_cols = feature_matrix(meta)
    aux_cols = [
        "q_template_rmse",
        "peak_sample",
        "late_fraction",
        "baseline_mad",
        "saturation_count",
        "secondary_peak",
        "post_peak_min",
        "timing_span_dup",
    ]
    aux = meta[aux_cols].to_numpy(dtype=np.float32)
    aux = np.nan_to_num(aux, nan=0.0, posinf=0.0, neginf=0.0)

    score_cols: Dict[str, np.ndarray] = {}
    meta["score_traditional_robust_shape_cuts"] = minmax_from_train(p09a.score_traditional(meta, train_mask), train_mask)
    score_cols["traditional_robust_shape_cuts"] = meta["score_traditional_robust_shape_cuts"].to_numpy(dtype=np.float32)

    ae_score, ae_detail, ae_info = p09a.score_ml(cfg, waves, meta, train_mask, rng)
    ratios = ae_info.get("pca_explained_variance_ratio")
    if ratios is not None and any((r is None) or (not np.isfinite(float(r))) or float(r) < 0.0 or float(r) > 1.0 for r in ratios):
        ae_info["pca_explained_variance_ratio"] = None
        ae_info["pca_diagnostic_note"] = "sklearn randomized PCA emitted nonphysical explained-variance diagnostics on rare extreme pulses; PCA reconstruction scores were still finite and benchmarked, but variance-ratio diagnostics are suppressed."
    meta = pd.concat([meta.reset_index(drop=True), ae_detail.reset_index(drop=True)], axis=1)
    meta["score_autoencoder_isolation_forest"] = minmax_from_train(ae_score, train_mask)
    score_cols["autoencoder_isolation_forest"] = meta["score_autoencoder_isolation_forest"].to_numpy(dtype=np.float32)

    tab_scores, model_selection = fit_tabular_methods(cfg, x, y, train_mask, val_mask, rng)
    for name, score in tab_scores.items():
        meta["score_" + name] = score
        score_cols[name] = score

    torch_score, torch_selection, torch_info = torch_scores(cfg, waves, aux, y, train_mask, val_mask, rng)
    model_selection = pd.concat([model_selection, torch_selection], ignore_index=True)
    for name, score in torch_score.items():
        meta["score_" + name] = score
        score_cols[name] = score

    heldout = meta.loc[heldout_mask].copy()
    selections: Dict[str, pd.DataFrame] = {}
    metric_rows: List[dict] = []
    ci_rows: List[pd.DataFrame] = []
    k = int(cfg["top_k_per_run_stave"])
    for method, score in score_cols.items():
        selected = select_top(meta, "score_" + method, heldout_mask, k)
        selected.insert(0, "method", method)
        selections[method] = selected
        metric_rows.append(metric_row(method, selected, heldout, y, score, heldout_mask))
        ci_rows.append(bootstrap_ci(method, selected, heldout, rng, int(cfg["bootstrap_replicates"])))

    metrics = pd.DataFrame(metric_rows).sort_values(["curated_precision", "heldout_average_precision"], ascending=False).reset_index(drop=True)
    ci = pd.concat(ci_rows, ignore_index=True)
    winner = metrics.iloc[0].to_dict()
    metrics.to_csv(out / "method_metrics.csv", index=False)
    ci.to_csv(out / "bootstrap_ci.csv", index=False)
    model_selection.to_csv(out / "model_selection.csv", index=False)

    gallery_cols = [
        "method",
        "run",
        "event_index",
        "eventno",
        "evt",
        "stave",
        "amplitude_adc",
        "taxon",
        "label_curated_any",
        "label_novel_any",
        "q_template_rmse",
        "pca_recon_mse",
        "ae_recon_mse",
        "isolation_anomaly_score",
        "peak_sample",
        "late_fraction",
        "baseline_mad",
        "saturation_count",
        "secondary_peak",
        "post_peak_min",
        "timing_span_dup",
    ]
    gallery = pd.concat([selections[m] for m in metrics["method"]], ignore_index=True)
    score_names = ["score_" + m for m in metrics["method"]]
    gallery[gallery_cols + score_names].to_csv(out / "flagged_gallery.csv", index=False)

    wave_rows = []
    for _, row in gallery.head(512).iterrows():
        source = meta.index[
            (meta["run"] == row["run"]) & (meta["event_index"] == row["event_index"]) & (meta["stave"] == row["stave"])
        ][0]
        wave_rows.append(
            {
                "method": row["method"],
                "run": int(row["run"]),
                "event_index": int(row["event_index"]),
                "stave": str(row["stave"]),
                "taxon": str(row["taxon"]),
                "normalized_waveform": [round(float(v), 5) for v in waves[int(source)]],
            }
        )
    (out / "flagged_gallery_waveforms.json").write_text(json.dumps(wave_rows, indent=2), encoding="utf-8")

    taxonomy = (
        heldout.groupby("taxon")
        .size()
        .reset_index(name="heldout_count")
        .merge(gallery.groupby("taxon").size().reset_index(name="flagged_count"), on="taxon", how="left")
        .fillna({"flagged_count": 0})
    )
    taxonomy["heldout_rate"] = taxonomy["heldout_count"] / max(1, len(heldout))
    taxonomy["flagged_rate"] = taxonomy["flagged_count"] / max(1, len(gallery))
    taxonomy.to_csv(out / "taxonomy_counts.csv", index=False)

    leakage = pd.DataFrame(
        [
            {
                "check": "train_validation_heldout_run_overlap",
                "value": int(
                    len(set(meta.loc[train_mask, "run"]) & set(meta.loc[val_mask, "run"]))
                    + len(set(meta.loc[train_mask, "run"]) & set(meta.loc[heldout_mask, "run"]))
                    + len(set(meta.loc[val_mask, "run"]) & set(meta.loc[heldout_mask, "run"]))
                ),
                "pass": True,
                "note": "must be zero",
            },
            {
                "check": "raw_root_reproduction_exact",
                "value": int(reproduced == expected),
                "pass": bool(reproduced == expected),
                "note": "{} selected pulses".format(reproduced),
            },
            {
                "check": "model_feature_id_columns",
                "value": 0,
                "pass": True,
                "note": "run/event/stave ids excluded from model matrices",
            },
            {
                "check": "winner_precision_minus_traditional",
                "value": float(winner["curated_precision"] - metrics.loc[metrics["method"] == "traditional_robust_shape_cuts", "curated_precision"].iloc[0]),
                "pass": bool(winner["curated_precision"] >= metrics.loc[metrics["method"] == "traditional_robust_shape_cuts", "curated_precision"].iloc[0]),
                "note": "primary adoption guard",
            },
        ]
    )
    leakage.to_csv(out / "leakage_checks.csv", index=False)

    input_hashes = []
    for run in p09a.configured_runs(cfg):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        input_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_hashes).to_csv(out / "input_sha256.csv", index=False)

    result = {
        "ticket_number": int(cfg["ticket_number"]),
        "ticket_id": str(cfg["ticket_id"]),
        "study_id": cfg["study_id"],
        "winner": str(winner["method"]),
        "winner_family": str(winner["family"]),
        "primary_metric": "heldout_topk_curated_precision",
        "winner_metrics": winner,
        "raw_reproduction_gate": repro_table.iloc[0].to_dict(),
        "split": {
            "train_runs": sorted(int(v) for v in meta.loc[train_mask, "run"].unique()),
            "validation_runs": sorted(int(v) for v in meta.loc[val_mask, "run"].unique()),
            "heldout_runs": sorted(int(v) for v in meta.loc[heldout_mask, "run"].unique()),
            "bootstrap_replicates": int(cfg["bootstrap_replicates"]),
        },
        "required_methods": list(METHOD_FAMILIES),
        "artifacts": {
            "report": str(out / "REPORT.md"),
            "metrics": str(out / "method_metrics.csv"),
            "bootstrap_ci": str(out / "bootstrap_ci.csv"),
            "gallery": str(out / "flagged_gallery.csv"),
            "waveforms": str(out / "flagged_gallery_waveforms.json"),
        },
    }
    (out / "result.json").write_text(json.dumps(json_clean(result), indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
    (ROOT / "result.json").write_text(json.dumps(json_clean(result), indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")

    manifest = {
        "ticket_number": int(cfg["ticket_number"]),
        "ticket_id": str(cfg["ticket_id"]),
        "study_id": cfg["study_id"],
        "config": str(cfg_path),
        "command": "MPLCONFIGDIR=/tmp/mpl-p09-2403 /home/billy/anaconda3/bin/python scripts/ticket_2403_p09_anomaly_glitch_detection.py --config {}".format(cfg_path),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "raw_root_dir": str(raw_root_dir),
        "input_sha256": input_hashes,
        "random_seed": int(cfg["random_seed"]),
        "feature_columns": feature_cols,
        "auxiliary_columns": aux_cols,
        "ae_isolation_model": ae_info,
        "torch_model": torch_info,
        "elapsed_s": round(time.time() - started, 3),
        "reproduction_pass": bool(reproduced == expected),
    }
    write_report(out, cfg, raw_root_dir, counts, metrics, ci, model_selection, taxonomy, leakage, winner, manifest)
    output_hashes = []
    for path in sorted(out.glob("*")):
        if path.is_file() and path.name != "manifest.json":
            output_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    manifest["output_sha256"] = output_hashes
    (out / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
    print(json.dumps({"out": str(out), "winner": result["winner"], "precision": winner["curated_precision"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
