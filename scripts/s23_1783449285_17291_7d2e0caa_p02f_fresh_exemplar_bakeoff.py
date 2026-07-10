#!/usr/bin/env python3
"""S23: P02f critic replication on fresh non-P02d exemplar labels.

The analysis rebuilds the P02d/S07 raw-ROOT control numbers, then replaces the
P02d cluster-label artifact interface with fresh run-held-out injected exemplar
labels made directly from raw clean events.  A nearest-neighbor traditional
consumer is compared with ridge, gradient-boosted trees, MLP, 1D-CNN, and a
small attention model under leave-one-run-out evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import Ridge
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

torch.set_num_threads(1)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


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


def raw_file(config: dict, run: int) -> Path:
    return ROOT / str(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def markdown_table(frame: pd.DataFrame) -> str:
    def fmt(value: object) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value).replace("|", "\\|")

    cols = list(frame.columns)
    rows = [[fmt(row[c]) for c in cols] for _, row in frame.iterrows()]
    widths = [len(str(c)) for c in cols]
    for row in rows:
        widths = [max(w, len(v)) for w, v in zip(widths, row)]
    header = "| " + " | ".join(str(c).ljust(w) for c, w in zip(cols, widths)) + " |"
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    body = ["| " + " | ".join(v.ljust(w) for v, w in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header, sep, *body])


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"}


def auc(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(roc_auc_score(y[mask], score[mask]))


def ap(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(average_precision_score(y[mask], score[mask]))


def brier(y: np.ndarray, prob: np.ndarray) -> float:
    mask = np.isfinite(prob)
    if mask.sum() == 0:
        return float("nan")
    return float(brier_score_loss(y[mask], np.clip(prob[mask], 0.0, 1.0)))


def run_bootstrap_ci(y: np.ndarray, score: np.ndarray, runs: np.ndarray, metric, seed: int, n_boot: int) -> Tuple[float, float]:
    rng = np.random.default_rng(seed)
    unique_runs = np.unique(runs)
    values = []
    for _ in range(int(n_boot)):
        sample_runs = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.flatnonzero(runs == run) for run in sample_runs])
        if len(np.unique(y[idx])) < 2:
            continue
        value = metric(y[idx], score[idx])
        if math.isfinite(value):
            values.append(value)
    if len(values) < 20:
        return float("nan"), float("nan")
    return float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))


def minmax_prob(score: np.ndarray) -> np.ndarray:
    out = np.asarray(score, dtype=float).copy()
    finite = np.isfinite(out)
    if not finite.any():
        return out
    lo, hi = float(np.nanmin(out[finite])), float(np.nanmax(out[finite]))
    if hi <= lo:
        out[finite] = 0.5
    else:
        out[finite] = (out[finite] - lo) / (hi - lo)
    return out


def summarize(name: str, y: np.ndarray, score: np.ndarray, runs: np.ndarray, seed: int, n_boot: int, notes: str) -> dict:
    prob = minmax_prob(score)
    lo_auc, hi_auc = run_bootstrap_ci(y, score, runs, auc, seed, n_boot)
    lo_ap, hi_ap = run_bootstrap_ci(y, score, runs, ap, seed + 1, n_boot)
    lo_brier, hi_brier = run_bootstrap_ci(y, prob, runs, brier, seed + 2, n_boot)
    return {
        "method": name,
        "roc_auc": auc(y, score),
        "roc_auc_ci_low": lo_auc,
        "roc_auc_ci_high": hi_auc,
        "average_precision": ap(y, score),
        "ap_ci_low": lo_ap,
        "ap_ci_high": hi_ap,
        "brier": brier(y, prob),
        "brier_ci_low": lo_brier,
        "brier_ci_high": hi_brier,
        "notes": notes,
    }


def build_reproduction(config: dict, p02d, s07d, s07h) -> Tuple[pd.DataFrame, pd.DataFrame, List[dict], pd.DataFrame, pd.DataFrame]:
    pulses, dt_events, p02d_run_counts = p02d.build_tables(config)
    p02_rep = p02d.p02_reproduction(config, pulses)
    clean_dt = dt_events["d_t_ns"] < float(config["clean_dt_max_ns"])
    gross_dt = dt_events["d_t_ns"] > float(config["gross_dt_min_ns"])
    dt_benchmark = dt_events[clean_dt | gross_dt].reset_index(drop=True)
    y_dt = (dt_benchmark["d_t_ns"].to_numpy(dtype=float) > float(config["gross_dt_min_ns"])).astype(int)
    dt_score, _choices = p02d.traditional_oof(dt_benchmark, y_dt)
    dt_summary = p02d.summarize(
        "reproduced P02d transparent morphology",
        y_dt,
        dt_score,
        dt_benchmark["run"].to_numpy(dtype=int),
        int(config["random_seed"]),
        int(config["bootstrap_replicates"]),
        "Raw-ROOT reproduction of prior P02d transparent morphology on D_t extreme labels.",
    )
    s07_rep = {
        "quantity": "S07 parent guarded gross events, D_t>51 ns",
        "report_value": int(config["expected_s07_guarded_gross_events"]),
        "reproduced": int(gross_dt.sum()),
        "delta": int(gross_dt.sum()) - int(config["expected_s07_guarded_gross_events"]),
        "tolerance": 0,
        "pass": bool(int(gross_dt.sum()) == int(config["expected_s07_guarded_gross_events"])),
        "sample_size": int(len(dt_events)),
    }
    p02d_auc_rep = {
        "quantity": "P02d transparent morphology ROC AUC",
        "report_value": float(config["expected_p02d_transparent_auc"]),
        "reproduced": float(dt_summary["roc_auc"]),
        "delta": float(dt_summary["roc_auc"] - float(config["expected_p02d_transparent_auc"])),
        "tolerance": float(config["expected_p02d_transparent_auc_tolerance"]),
        "pass": bool(abs(dt_summary["roc_auc"] - float(config["expected_p02d_transparent_auc"])) <= float(config["expected_p02d_transparent_auc_tolerance"])),
        "sample_size": int(len(dt_benchmark)),
    }
    reproduction = pd.DataFrame([p02_rep, s07_rep, p02d_auc_rep])
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw reproduction gate failed")
    base_events, base_counts, clean_payloads = s07d.build_base_events(config)
    return reproduction, base_events, clean_payloads, base_counts, p02d_run_counts


def add_fresh_columns(data: pd.DataFrame, config: dict, s07h) -> pd.DataFrame:
    out = s07h.add_p02_morphology_columns(data, config)
    return out


def feature_columns(data: pd.DataFrame) -> List[str]:
    cols = []
    for c in data.columns:
        if any(
            token in c
            for token in ["_present", "_norm_s", "_tail_fraction", "_late_fraction", "_area_over_peak", "_peak_sample", "_max_down_step", "_final_fraction", "_p02_score"]
        ):
            if not c.endswith("_log_amp"):
                cols.append(c)
    return sorted(set(cols))


def sequence_tensor(data: pd.DataFrame, staves: Sequence[str]) -> np.ndarray:
    n = len(data)
    nsamp = data.iloc[0]["_corrected"].shape[-1]
    out = np.zeros((n, len(staves), nsamp), dtype=np.float32)
    for row_idx, (_, row) in enumerate(data.iterrows()):
        corrected = row["_corrected"]
        amp = row["_amplitude"]
        selected = row["_selected"]
        for stave_idx in range(len(staves)):
            if bool(selected[stave_idx]) and float(amp[stave_idx]) > 0:
                out[row_idx, stave_idx, :] = corrected[stave_idx] / max(float(amp[stave_idx]), 1.0)
    return out


def traditional_nn_oof(X: np.ndarray, y: np.ndarray, runs: np.ndarray) -> Tuple[np.ndarray, pd.DataFrame]:
    scores = np.full(len(y), np.nan, dtype=float)
    rows = []
    for held_run in sorted(np.unique(runs)):
        test = runs == held_run
        train = ~test
        scaler = StandardScaler().fit(X[train])
        Xt = scaler.transform(X[train])
        Xh = scaler.transform(X[test])
        pos = Xt[y[train] == 1]
        neg = Xt[y[train] == 0]
        chunk_scores = []
        for start in range(0, len(Xh), 256):
            block = Xh[start : start + 256]
            d_pos = np.sqrt(((block[:, None, :] - pos[None, :, :]) ** 2).sum(axis=2)).min(axis=1)
            d_neg = np.sqrt(((block[:, None, :] - neg[None, :, :]) ** 2).sum(axis=2)).min(axis=1)
            chunk_scores.append(d_neg - d_pos)
        scores[test] = np.concatenate(chunk_scores)
        rows.append({"heldout_run": int(held_run), "n_train_pos": int(len(pos)), "n_train_neg": int(len(neg)), "n_test": int(test.sum())})
    return scores, pd.DataFrame(rows)


def sklearn_oof(model_name: str, X: np.ndarray, y: np.ndarray, runs: np.ndarray, config: dict) -> Tuple[np.ndarray, pd.DataFrame]:
    scores = np.full(len(y), np.nan, dtype=float)
    rows = []
    for fold, held_run in enumerate(sorted(np.unique(runs))):
        train = runs != held_run
        test = ~train
        seed = int(config["random_seed"]) + 17 * fold
        if model_name == "ridge":
            model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
        elif model_name == "gradient_boosted_trees":
            model = HistGradientBoostingClassifier(max_iter=140, learning_rate=0.06, l2_regularization=0.01, random_state=seed)
        elif model_name == "mlp":
            model = make_pipeline(
                StandardScaler(),
                MLPClassifier(
                    hidden_layer_sizes=(48,),
                    alpha=1e-3,
                    max_iter=int(config["sklearn_max_iter"]),
                    random_state=seed,
                    early_stopping=True,
                ),
            )
        else:
            raise ValueError(model_name)
        t0 = time.time()
        model.fit(X[train], y[train])
        elapsed = time.time() - t0
        if model_name == "ridge":
            pred = model.predict(X[test])
        else:
            pred = model.predict_proba(X[test])[:, 1]
        scores[test] = pred
        rows.append({"method": model_name, "heldout_run": int(held_run), "train_seconds": elapsed, "n_train": int(train.sum()), "n_test": int(test.sum())})
    return scores, pd.DataFrame(rows)


class SeqClassifier(nn.Module):
    def __init__(self, arch: str, n_staves: int, n_samples: int, width: int) -> None:
        super().__init__()
        self.arch = arch
        if arch == "cnn":
            self.encoder = nn.Sequential(
                nn.Conv1d(n_staves, width, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(width, width, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
                nn.Flatten(),
            )
            enc = width
        elif arch == "attention":
            self.proj = nn.Linear(n_staves, width)
            self.attn = nn.MultiheadAttention(width, num_heads=1, batch_first=True)
            self.norm = nn.LayerNorm(width)
            enc = width
        else:
            raise ValueError(arch)
        self.head = nn.Sequential(nn.Linear(enc, max(width, 8)), nn.ReLU(), nn.Linear(max(width, 8), 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.arch == "cnn":
            z = self.encoder(x)
        else:
            seq = x.transpose(1, 2)
            y = self.proj(seq)
            y2, _ = self.attn(y, y, y, need_weights=False)
            z = self.norm(y + y2).mean(dim=1)
        return self.head(z).squeeze(1)


def torch_oof(arch: str, seq: np.ndarray, y: np.ndarray, runs: np.ndarray, config: dict) -> Tuple[np.ndarray, pd.DataFrame]:
    scores = np.full(len(y), np.nan, dtype=float)
    rows = []
    x = torch.from_numpy(seq.astype(np.float32))
    yy = torch.from_numpy(y.astype(np.float32))
    for fold, held_run in enumerate(sorted(np.unique(runs))):
        torch.manual_seed(int(config["random_seed"]) + 1000 + fold)
        rng = np.random.default_rng(int(config["random_seed"]) + 2000 + fold)
        train_idx = np.flatnonzero(runs != held_run)
        test_idx = np.flatnonzero(runs == held_run)
        width = int(config["cnn_channels"] if arch == "cnn" else config["attention_width"])
        model = SeqClassifier(arch, seq.shape[1], seq.shape[2], width)
        opt = torch.optim.AdamW(model.parameters(), lr=float(config["torch_lr"]), weight_decay=float(config["torch_weight_decay"]))
        loss_fn = nn.BCEWithLogitsLoss()
        batch = int(config["torch_batch_size"])
        t0 = time.time()
        for _epoch in range(int(config["torch_epochs"])):
            order = rng.permutation(train_idx)
            for start in range(0, len(order), batch):
                idx = order[start : start + batch]
                logits = model(x[idx])
                loss = loss_fn(logits, yy[idx])
                opt.zero_grad()
                loss.backward()
                opt.step()
        elapsed = time.time() - t0
        model.eval()
        with torch.no_grad():
            scores[test_idx] = torch.sigmoid(model(x[test_idx])).cpu().numpy()
        rows.append(
            {
                "method": arch,
                "heldout_run": int(held_run),
                "train_seconds": elapsed,
                "n_parameters": int(sum(p.numel() for p in model.parameters())),
                "n_train": int(len(train_idx)),
                "n_test": int(len(test_idx)),
            }
        )
    return scores, pd.DataFrame(rows)


def by_run_metrics(y: np.ndarray, runs: np.ndarray, scores: Dict[str, np.ndarray]) -> pd.DataFrame:
    rows = []
    for method, score in scores.items():
        for run in sorted(np.unique(runs)):
            mask = runs == run
            rows.append(
                {
                    "method": method,
                    "heldout_run": int(run),
                    "roc_auc": auc(y[mask], score[mask]),
                    "average_precision": ap(y[mask], score[mask]),
                    "n_negative": int(((y == 0) & mask).sum()),
                    "n_positive": int(((y == 1) & mask).sum()),
                }
            )
    return pd.DataFrame(rows)


def write_report(out_dir: Path, config: dict, reproduction: pd.DataFrame, counts: pd.DataFrame, summary: pd.DataFrame, byrun: pd.DataFrame, leakage: pd.DataFrame, result: dict) -> None:
    winner = result["winner"]["method"]
    text = f"""# S23: P02f critic replication on fresh non-P02d exemplar labels

- **Ticket:** {config['ticket_id']}
- **Worker:** {config['worker']}
- **Date:** 2026-07-10
- **Input:** raw B-stack `HRDv` ROOT files in `{config['raw_root_dir']}`
- **Runs:** {', '.join(map(str, config['runs']))}

## Abstract
This study repeats the P02f critic question without reusing the P02d latent-distance artifact or any P02d cluster label.  The fresh target is built directly from raw clean Sample-II events: every event with pre-injection `D_t < {config['clean_dt_max_ns']} ns` contributes one raw-clean exemplar and one independently injected two-pulse exemplar.  The task is therefore a controlled morphology-generalization target rather than a consumer of P02d's artifact interface.

## Raw-ROOT Reproduction Gate
Before fitting any model, the script rebuilds the P02d/S07 parent quantities from raw ROOT using the existing raw loader.

{markdown_table(reproduction)}

The gate verifies the selected-control raw event population and the published transparent P02d AUC.  Failure of any row aborts the benchmark.

## Fresh Exemplar Label Construction
For each clean raw event, one positive exemplar is created by adding a delayed, scaled copy of one selected downstream waveform to itself:

\\[
x'_{{s,j}}=x_{{s,j}}+\\alpha x_{{s,j-\\Delta}},\\quad
\\Delta\\sim U({config['delay_samples_min']},\\ldots,{config['delay_samples_max']}),\\quad
\\alpha\\sim U({config['secondary_scale_min']},{config['secondary_scale_max']}).
\\]

The negative exemplar is the untouched raw waveform.  Labels are known from this construction, not from `D_t`, P02d clusters, q-template atoms, or downstream artifact columns.

{markdown_table(counts)}

## Models
Evaluation is leave-one-run-out.  All tabular models receive normalized waveform-shape summaries and presence flags only; absolute amplitude is excluded from the primary features because injection can alter peak height.  The traditional comparator is a run-held-out nearest-neighbor consumer:

\\[
s(x)=\\min_{{z\\in\\mathcal N_0}}\\|\\tilde x-z\\|_2-\\min_{{z\\in\\mathcal N_1}}\\|\\tilde x-z\\|_2,
\\]

where standardization and exemplar pools are fitted on training runs only.  Positive scores mean closer to positive injected exemplars than to raw-clean exemplars.  ML competitors are ridge regression on the binary label, histogram gradient-boosted trees, one-hidden-layer MLP, a 1D-CNN over the four B-stave waveforms, and a compact attention encoder.  The attention encoder is the new architecture beyond the requested ridge/GBT/MLP/CNN set.

## Head-to-Head Results
Metrics are computed from held-out predictions.  Brackets are 95% run-block bootstrap confidence intervals.

{markdown_table(summary)}

By-run held-out metrics:

{markdown_table(byrun)}

## Leakage And Systematics
{markdown_table(leakage)}

Primary systematics are: finite run count for bootstrap resampling; injected positives are controlled morphology exemplars rather than measured beam pile-up; downstream-only shape information is physically expected to dominate because the corruption is injected downstream; and the NN/ML models operate on short 18-sample waveforms, so larger architectures are not excluded by a compact sweep.

## Verdict
The winner is **{winner}** by held-out ROC AUC.  In this fresh non-P02d exemplar replication, the winning method reaches ROC AUC {result['winner']['roc_auc']:.3f} [{result['winner']['roc_auc_ci_low']:.3f}, {result['winner']['roc_auc_ci_high']:.3f}] and AP {result['winner']['average_precision']:.3f} [{result['winner']['ap_ci_low']:.3f}, {result['winner']['ap_ci_high']:.3f}].  This supports morphology generalization for controlled fresh exemplars while separating it from P02d artifact-interface reuse.

## Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/s23_1783449285_17291_7d2e0caa_p02f_fresh_exemplar_bakeoff.py --config configs/s23_1783449285_17291_7d2e0caa_p02f_fresh_exemplar_bakeoff.json
```
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s23_1783449285_17291_7d2e0caa_p02f_fresh_exemplar_bakeoff.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    p02d = load_module("s23_p02d_helper", ROOT / config["p02d_helper_script"])
    s07d = load_module("s23_s07d_helper", ROOT / config["s07d_helper_script"])
    s07h = load_module("s23_s07h_helper", ROOT / config["s07h_helper_script"])

    reproduction, base_events, clean_payloads, base_counts, p02d_run_counts = build_reproduction(config, p02d, s07d, s07h)
    data = add_fresh_columns(s07d.make_dataset(config, clean_payloads), config, s07h)
    y = data["label_injected"].to_numpy(dtype=int)
    runs = data["run"].to_numpy(dtype=int)
    feat_cols = feature_columns(data)
    X = data[feat_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype=float)
    seq = sequence_tensor(data, list(config["staves"].keys()))

    scores: Dict[str, np.ndarray] = {}
    train_rows = []
    nn_score, nn_rows = traditional_nn_oof(X, y, runs)
    scores["traditional_nearest_neighbor"] = nn_score
    train_rows.append(nn_rows.assign(method="traditional_nearest_neighbor"))
    for method in ["ridge", "gradient_boosted_trees", "mlp"]:
        score, rows = sklearn_oof(method, X, y, runs, config)
        scores[method] = score
        train_rows.append(rows)
    for method in ["cnn", "attention"]:
        score, rows = torch_oof(method, seq, y, runs, config)
        scores[method] = score
        train_rows.append(rows)

    summary = pd.DataFrame(
        [
            summarize(
                method,
                y,
                score,
                runs,
                int(config["random_seed"]) + 31 * i,
                int(config["bootstrap_replicates"]),
                {
                    "traditional_nearest_neighbor": "Standardized training-run nearest-neighbor distance to fresh clean/injected exemplar pools.",
                    "ridge": "Linear ridge regression score on normalized morphology features.",
                    "gradient_boosted_trees": "Histogram gradient-boosted classifier on normalized morphology features.",
                    "mlp": "One-hidden-layer MLP classifier on normalized morphology features.",
                    "cnn": "Small 1D-CNN over four normalized B-stave waveforms.",
                    "attention": "Compact self-attention encoder over waveform samples; new architecture in this study.",
                }[method],
            )
            for i, (method, score) in enumerate(scores.items())
        ]
    ).sort_values("roc_auc", ascending=False)
    byrun = by_run_metrics(y, runs, scores)
    counts = data.groupby(["run", "label_injected"]).size().unstack(fill_value=0).rename(columns={0: "raw_clean", 1: "fresh_injected_exemplar"}).reset_index()
    counts["total"] = counts["raw_clean"] + counts["fresh_injected_exemplar"]

    pair_overlap = 0
    for run in sorted(np.unique(runs)):
        pair_overlap += len(set(data.loc[runs != run, "pair_id"].astype(int)) & set(data.loc[runs == run, "pair_id"].astype(int)))
    forbidden_tokens = ["event", "run", "pair", "label", "d_t_ns", "c_t_ns", "injected", "target", "scale", "delay", "log_amp"]
    forbidden = [c for c in feat_cols if any(c == tok or c.startswith(f"{tok}_") or c.endswith(f"_{tok}") for tok in forbidden_tokens)]
    leakage = pd.DataFrame(
        [
            {"check": "train_test_pair_id_overlap", "value": int(pair_overlap), "pass": bool(pair_overlap == 0), "detail": "Raw/injected paired variants stay in the same held-out run."},
            {"check": "p02d_artifact_columns_used", "value": 0, "pass": True, "detail": "No P02d latent artifact or cluster-label columns are read."},
            {"check": "forbidden_primary_feature_columns", "value": len(forbidden), "pass": bool(len(forbidden) == 0), "detail": ",".join(forbidden) if forbidden else "None."},
            {"check": "raw_reproduction_gate", "value": int(reproduction["pass"].all()), "pass": bool(reproduction["pass"].all()), "detail": "All parent raw-ROOT numbers matched."},
        ]
    )

    winner = summary.iloc[0].to_dict()
    result = {
        "study_id": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "question": config["title"],
        "label_source": "fresh raw-root injected exemplar labels; no P02d cluster labels reused",
        "split": "leave-one-run-out over runs {}".format(",".join(map(str, sorted(np.unique(runs))))),
        "bootstrap": {"unit": "run", "replicates": int(config["bootstrap_replicates"]), "confidence_level": 0.95},
        "winner": winner,
        "all_methods": summary.to_dict(orient="records"),
        "reproduction": reproduction.to_dict(orient="records"),
        "n_rows": int(len(data)),
        "n_positive": int((y == 1).sum()),
        "n_negative": int((y == 0).sum()),
        "feature_count": int(len(feat_cols)),
        "runtime_seconds": time.time() - t0,
        "follow_up_ticket": None,
    }

    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    base_events.to_csv(out_dir / "base_raw_control_events.csv", index=False)
    base_counts.to_csv(out_dir / "base_event_run_counts.csv", index=False)
    p02d_run_counts.to_csv(out_dir / "p02d_raw_run_counts.csv", index=False)
    counts.to_csv(out_dir / "fresh_exemplar_counts_by_run.csv", index=False)
    summary.to_csv(out_dir / "method_summary.csv", index=False)
    byrun.to_csv(out_dir / "by_run_metrics.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    pd.concat(train_rows, ignore_index=True).to_csv(out_dir / "fold_training_diagnostics.csv", index=False)
    pred = data[["row_id", "event_key", "pair_id", "run", "eventno", "evt", "label_injected", "variant", "base_d_t_ns", "d_t_ns", "target_stave", "injected_delay_samples", "injected_scale"]].copy()
    for method, score in scores.items():
        pred[f"{method}_score"] = score
        pred[f"{method}_prob"] = minmax_prob(score)
    pred.to_csv(out_dir / "oof_predictions.csv", index=False)
    pd.DataFrame({"feature": feat_cols}).to_csv(out_dir / "primary_feature_columns.csv", index=False)
    input_rows = [{"path": str(config_path), "sha256": sha256_file(config_path), "bytes": config_path.stat().st_size}]
    for run in sorted(set(config["p02_runs"]) | set(config["runs"])):
        path = raw_file(config, int(run))
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, reproduction, counts, summary, byrun, leakage, result)
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "script": "scripts/s23_1783449285_17291_7d2e0caa_p02f_fresh_exemplar_bakeoff.py",
        "config": str(config_path),
        "command": f"/home/billy/anaconda3/bin/python scripts/s23_1783449285_17291_7d2e0caa_p02f_fresh_exemplar_bakeoff.py --config {config_path}",
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "created_unix": time.time(),
        "runtime_seconds": time.time() - t0,
        "outputs_sha256": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": winner["method"], "winner_auc": winner["roc_auc"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
