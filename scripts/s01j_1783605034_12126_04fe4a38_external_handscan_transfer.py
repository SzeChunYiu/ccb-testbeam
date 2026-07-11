#!/usr/bin/env python3
"""S01j q-template atom transfer to external hand-scan labels.

The script deliberately performs the raw ROOT selected-pulse reproduction before
loading the hand-scan labels.  The labelled sample is small, so all learned
methods are evaluated leave-one-run-out across the hand-scan runs and uncertainty
is a run-block bootstrap.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s01j-handscan")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, RidgeClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import torch
import torch.nn as nn


DEFAULT_CONFIG = "configs/s01j_1783605034_12126_04fe4a38_external_handscan_transfer.yaml"
SCRIPT_PATH = "scripts/s01j_1783605034_12126_04fe4a38_external_handscan_transfer.py"
STAVES = ["B2", "B4", "B6", "B8"]


def load_yaml(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def clean_json(x):
    if isinstance(x, dict):
        return {str(k): clean_json(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean_json(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        x = float(x)
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return x


def run_groups(config: dict) -> dict[int, str]:
    out = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = str(group)
    return out


def scan_raw_counts(config: dict) -> tuple[pd.DataFrame, int]:
    raw_dir = Path(config["raw_root_dir"])
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    channel_map = {k: int(v) for k, v in config["staves"].items()}
    channels = np.asarray([channel_map[s] for s in STAVES], dtype=int)
    group_for_run = run_groups(config)
    rows = []
    for run in sorted(group_for_run):
        path = raw_dir / f"hrdb_run_{run:04d}.root"
        tree = uproot.open(path)["h101"]
        counts = {
            "run": run,
            "group": group_for_run[run],
            "events_total": 0,
            "events_with_selected": 0,
            "selected_pulses": 0,
        }
        counts.update({s: 0 for s in STAVES})
        for batch in tree.iterate(["HRDv"], step_size=50000, library="np"):
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            base = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - base[..., None]
            selected_waves = corrected[:, channels, :]
            amp = selected_waves.max(axis=-1)
            selected = amp > cut
            counts["events_total"] += int(raw.shape[0])
            counts["events_with_selected"] += int(selected.any(axis=1).sum())
            counts["selected_pulses"] += int(selected.sum())
            for j, stave in enumerate(STAVES):
                counts[stave] += int(selected[:, j].sum())
        print(f"run {run:04d}: {counts['selected_pulses']} selected pulses")
        rows.append(counts)
    table = pd.DataFrame(rows)
    return table, int(table["selected_pulses"].sum())


def parse_waveforms(series: pd.Series) -> np.ndarray:
    vals = []
    for text in series:
        vals.append(np.asarray(ast.literal_eval(str(text)), dtype=np.float32))
    return np.stack(vals).astype(np.float32)


def add_hand_features(df: pd.DataFrame, waves: np.ndarray) -> pd.DataFrame:
    out = df.copy()
    pos = np.clip(waves, 0.0, None)
    total = np.maximum(pos.sum(axis=1), 1e-9)
    out["wave_early_fraction"] = pos[:, :5].sum(axis=1) / total
    out["wave_late_fraction"] = pos[:, 10:].sum(axis=1) / total
    out["wave_area"] = waves.sum(axis=1)
    out["wave_width_proxy"] = (waves > 0.35).sum(axis=1)
    out["wave_derivative_min"] = np.diff(waves, axis=1).min(axis=1)
    out["wave_derivative_max"] = np.diff(waves, axis=1).max(axis=1)
    out["wave_tail_rise"] = waves[:, -4:].mean(axis=1) - waves[:, 8:12].mean(axis=1)
    out["log_amp"] = np.log1p(np.maximum(out["amplitude_adc"].astype(float), 0.0))
    out["baseline_log1p"] = np.log1p(np.maximum(out["baseline_mad"].astype(float), 0.0))
    out["stave_idx"] = out["stave"].map({s: i for i, s in enumerate(STAVES)}).astype(int)
    out["method_is_ml_gallery"] = out["method"].eq("ml_pca_ae_isolation").astype(int)
    out["saturation_atom"] = out["saturation_count"].astype(float).gt(0).astype(int)
    out["late_peak_atom"] = out["peak_sample"].astype(float).ge(8).astype(int)
    out["q_bad_atom"] = out["q_template_rmse"].astype(float).ge(out["q_template_rmse"].quantile(0.75)).astype(int)
    out["baseline_atom"] = out["baseline_mad"].astype(float).ge(out["baseline_mad"].quantile(0.75)).astype(int)
    return out


def safe_auc(y, score) -> float:
    y = np.asarray(y, dtype=int)
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, score))


def safe_ap(y, score) -> float:
    y = np.asarray(y, dtype=int)
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(average_precision_score(y, score))


def bootstrap_ci(pred: pd.DataFrame, n_boot: int, rng: np.random.Generator) -> dict:
    runs = sorted(pred["run"].unique())
    blocks = [(pred.loc[pred.run.eq(r), "y_true"].to_numpy(int), pred.loc[pred.run.eq(r), "score"].to_numpy(float)) for r in runs]
    aucs, aps = [], []
    for _ in range(int(n_boot)):
        take = rng.integers(0, len(blocks), size=len(blocks))
        y = np.concatenate([blocks[i][0] for i in take])
        s = np.concatenate([blocks[i][1] for i in take])
        aucs.append(safe_auc(y, s))
        aps.append(safe_ap(y, s))
    aucs = np.asarray([v for v in aucs if np.isfinite(v)])
    aps = np.asarray([v for v in aps if np.isfinite(v)])
    return {
        "auc_ci_low": float(np.quantile(aucs, 0.025)),
        "auc_ci_high": float(np.quantile(aucs, 0.975)),
        "ap_ci_low": float(np.quantile(aps, 0.025)),
        "ap_ci_high": float(np.quantile(aps, 0.975)),
    }


def tabular_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    forbidden = {
        "gallery_row_id",
        "run",
        "event_index",
        "eventno",
        "evt",
        "normalized_waveform",
        "reviewer_a_label",
        "reviewer_b_label",
        "consensus_label",
        "reviewers_agree",
        "consensus_target_any",
        "p09a_target_any",
        "consensus_curated_any",
        "review_peak_sample",
        "review_peak_value",
        "review_width_half",
        "review_width_035",
        "review_early_fraction",
        "review_late_fraction",
        "review_secondary_peak",
        "review_secondary_sep",
        "review_post_peak_min",
        "review_undershoot_area",
        "review_first4_span",
        "review_last4_mean",
        "review_tail_rise",
    }
    cats = ["stave", "method", "taxon"]
    nums = [c for c in df.columns if c not in forbidden and c not in cats and pd.api.types.is_numeric_dtype(df[c])]
    return nums, cats


def make_preprocessor(num_cols: list[str], cat_cols: list[str]) -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), num_cols),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse=False), cat_cols),
        ],
        remainder="drop",
    )


def fit_traditional_score(train: pd.DataFrame, test: pd.DataFrame, y_train: np.ndarray, config: dict) -> tuple[np.ndarray, str]:
    best_col, best_sign, best_auc = None, 1.0, -np.inf
    for col in config["benchmark"]["traditional_candidates"]:
        if col not in train:
            continue
        vals = train[col].astype(float).to_numpy()
        if np.nanstd(vals) == 0:
            continue
        for sign in (1.0, -1.0):
            auc = safe_auc(y_train, sign * vals)
            if np.isfinite(auc) and auc > best_auc:
                best_auc, best_col, best_sign = auc, col, sign
    if best_col is None:
        raise RuntimeError("no usable traditional score candidate")
    return best_sign * test[best_col].astype(float).to_numpy(), f"{best_col} sign {best_sign:+.0f}"


class SmallCNN(nn.Module):
    def __init__(self, gated: bool, n_tab: int):
        super().__init__()
        self.gated = gated
        self.conv = nn.Sequential(
            nn.Conv1d(1, 12, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(12, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveMaxPool1d(1),
        )
        extra = n_tab if gated else 0
        self.head = nn.Sequential(nn.Linear(16 + extra, 16), nn.ReLU(), nn.Linear(16, 1))

    def forward(self, wave, tab=None):
        z = self.conv(wave[:, None, :]).squeeze(-1)
        if self.gated:
            z = torch.cat([z, tab], dim=1)
        return self.head(z).squeeze(1)


def train_torch_model(w_train, tab_train, y_train, w_test, tab_test, config, gated: bool, seed: int) -> np.ndarray:
    torch.manual_seed(seed)
    model = SmallCNN(gated=gated, n_tab=tab_train.shape[1] if gated else 0)
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["models"]["torch_lr"]), weight_decay=float(config["models"]["torch_weight_decay"]))
    loss_fn = nn.BCEWithLogitsLoss()
    xw = torch.tensor(w_train, dtype=torch.float32)
    xt = torch.tensor(tab_train, dtype=torch.float32)
    y = torch.tensor(y_train.astype(np.float32), dtype=torch.float32)
    batch = int(config["models"]["torch_batch_size"])
    for _ in range(int(config["models"]["torch_epochs"])):
        order = torch.randperm(len(y))
        for start in range(0, len(y), batch):
            idx = order[start : start + batch]
            opt.zero_grad()
            logits = model(xw[idx], xt[idx] if gated else None)
            loss = loss_fn(logits, y[idx])
            loss.backward()
            opt.step()
    with torch.no_grad():
        logits = model(torch.tensor(w_test, dtype=torch.float32), torch.tensor(tab_test, dtype=torch.float32) if gated else None)
    return torch.sigmoid(logits).numpy()


def run_benchmark(df: pd.DataFrame, waves: np.ndarray, config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]))
    target_col = config["target"]["column"]
    y_all = df[target_col].astype(int).to_numpy()
    runs = sorted(df["run"].unique())
    num_cols, cat_cols = tabular_columns(df)
    methods = {
        "traditional_train_selected_score": [],
        "ridge": [],
        "gradient_boosted_trees": [],
        "mlp": [],
        "1d_cnn": [],
        "atom_gated_cnn_new": [],
    }
    choices = []
    for fold, run in enumerate(runs):
        train_mask = df["run"].ne(run).to_numpy()
        test_mask = ~train_mask
        y_train, y_test = y_all[train_mask], y_all[test_mask]
        train, test = df.loc[train_mask].copy(), df.loc[test_mask].copy()
        trad_score, trad_choice = fit_traditional_score(train, test, y_train, config)
        choices.append({"heldout_run": int(run), "traditional_choice": trad_choice})
        methods["traditional_train_selected_score"].append(pd.DataFrame({"method": "traditional_train_selected_score", "run": run, "y_true": y_test, "score": trad_score}))

        pre = make_preprocessor(num_cols, cat_cols)
        x_train = pre.fit_transform(train)
        x_test = pre.transform(test)

        ridge = RidgeClassifier(alpha=float(config["models"]["ridge_alpha"]))
        ridge.fit(x_train, y_train)
        methods["ridge"].append(pd.DataFrame({"method": "ridge", "run": run, "y_true": y_test, "score": ridge.decision_function(x_test)}))

        hgb = HistGradientBoostingClassifier(
            max_iter=int(config["models"]["hgb_max_iter"]),
            learning_rate=float(config["models"]["hgb_learning_rate"]),
            max_leaf_nodes=int(config["models"]["hgb_max_leaf_nodes"]),
            l2_regularization=float(config["models"]["hgb_l2_regularization"]),
            random_state=int(config["random_seed"]) + fold,
        )
        hgb.fit(x_train, y_train)
        methods["gradient_boosted_trees"].append(pd.DataFrame({"method": "gradient_boosted_trees", "run": run, "y_true": y_test, "score": hgb.predict_proba(x_test)[:, 1]}))

        mlp = MLPClassifier(
            hidden_layer_sizes=tuple(config["models"]["mlp_hidden"]),
            alpha=float(config["models"]["mlp_alpha"]),
            max_iter=int(config["models"]["mlp_max_iter"]),
            random_state=int(config["random_seed"]) + fold,
            early_stopping=False,
        )
        mlp.fit(x_train, y_train)
        methods["mlp"].append(pd.DataFrame({"method": "mlp", "run": run, "y_true": y_test, "score": mlp.predict_proba(x_test)[:, 1]}))

        tab_small_cols = ["q_template_rmse", "late_fraction", "baseline_mad", "saturation_atom", "late_peak_atom", "q_bad_atom", "baseline_atom"]
        scaler = StandardScaler()
        tab_train = scaler.fit_transform(train[tab_small_cols].astype(float).to_numpy())
        tab_test = scaler.transform(test[tab_small_cols].astype(float).to_numpy())
        w_train, w_test = waves[train_mask], waves[test_mask]
        cnn_score = train_torch_model(w_train, tab_train, y_train, w_test, tab_test, config, gated=False, seed=int(config["random_seed"]) + fold)
        gated_score = train_torch_model(w_train, tab_train, y_train, w_test, tab_test, config, gated=True, seed=int(config["random_seed"]) + 100 + fold)
        methods["1d_cnn"].append(pd.DataFrame({"method": "1d_cnn", "run": run, "y_true": y_test, "score": cnn_score}))
        methods["atom_gated_cnn_new"].append(pd.DataFrame({"method": "atom_gated_cnn_new", "run": run, "y_true": y_test, "score": gated_score}))

    pred = pd.concat([pd.concat(parts, ignore_index=True) for parts in methods.values()], ignore_index=True)
    rows = []
    for method, g in pred.groupby("method", sort=False):
        ci = bootstrap_ci(g, int(config["benchmark"]["bootstrap_samples"]), rng)
        rows.append({
            "method": method,
            "family": "traditional" if method.startswith("traditional") else ("new_architecture" if method.endswith("_new") else ("nn" if method in {"mlp", "1d_cnn"} else "ml")),
            "n": int(len(g)),
            "positives": int(g["y_true"].sum()),
            "roc_auc": safe_auc(g["y_true"], g["score"]),
            "average_precision": safe_ap(g["y_true"], g["score"]),
            **ci,
        })
    summary = pd.DataFrame(rows).sort_values(["roc_auc", "average_precision"], ascending=False)
    per_run = []
    for (method, run), g in pred.groupby(["method", "run"]):
        per_run.append({"method": method, "run": int(run), "n": int(len(g)), "positives": int(g["y_true"].sum()), "roc_auc": safe_auc(g["y_true"], g["score"]), "average_precision": safe_ap(g["y_true"], g["score"])})
    return pred, summary, pd.DataFrame(per_run), pd.DataFrame(choices)


def write_report(
    out_dir: Path,
    config: dict,
    result: dict,
    summary: pd.DataFrame,
    per_run: pd.DataFrame,
    repro: pd.DataFrame,
    choices: pd.DataFrame,
    label_diag: pd.DataFrame,
    transfer_diag: pd.DataFrame,
) -> None:
    winner = result["winner"]
    top = summary.iloc[0]
    trad = summary.loc[summary["family"].eq("traditional")].iloc[0]
    lines = [
        "# S01j q-template atom transfer to real external hand-scan",
        "",
        f"**Ticket:** `{config['ticket_id']}`  ",
        f"**Worker:** `{config['worker']}`  ",
        "**Date:** 2026-07-11",
        "",
        "## Abstract",
        "",
        "This study tests whether the q-template support atom that transferred in S01i's injected-truth panel also transfers to a small externally adjudicated real-waveform gallery. Raw ROOT reproduction is performed before loading the labels. The held-out unit is acquisition run, and uncertainty is a nonparametric run-block bootstrap over the hand-scan runs.",
        "",
        f"The benchmark winner is **{winner}** with ROC AUC **{top.roc_auc:.4f}** [{top.auc_ci_low:.4f}, {top.auc_ci_high:.4f}] and AP **{top.average_precision:.4f}** [{top.ap_ci_low:.4f}, {top.ap_ci_high:.4f}]. The strongest traditional comparator is **{trad.method}** with ROC AUC **{trad.roc_auc:.4f}** [{trad.auc_ci_low:.4f}, {trad.auc_ci_high:.4f}].",
        "",
        "## Raw ROOT Reproduction",
        "",
        result["reproduction_match_table"].to_markdown(index=False),
        "",
        "The selected-pulse count is reproduced directly from `data/root/root/hrdb_run_*.root` by pedestal-subtracting HRDv even B-stave channels and applying the 1000 ADC amplitude threshold. The reproduced count is computed before the hand-scan table is opened.",
        "",
        "## External Hand-Scan Target",
        "",
        f"The labelled target is `{config['target']['column']}` from `{config['label_path']}`. Positive labels denote {config['target']['positive_description']}. The gallery contains only real raw waveforms selected by earlier P09 rankers; it is not synthetic injection truth and not independent beamline particle truth.",
        "",
        label_diag.to_markdown(index=False),
        "",
        "Let \(y_i \\in \\{0,1\\}\) be the consensus target label for labelled waveform \(i\). The run-held-out score \(s_m(x_i)\) for method \(m\) is evaluated by ROC AUC",
        "",
        "\\[\\mathrm{AUC}_m = P(s_m(x^+) > s_m(x^-)) + \\tfrac{1}{2}P(s_m(x^+) = s_m(x^-)),\\]",
        "",
        "with confidence intervals from resampling labelled acquisition runs with replacement.",
        "",
        "## Splitting and Leakage Controls",
        "",
        "All methods use leave-one-run-out folds over the hand-scan runs. Run id, event id, event order, reviewer labels, consensus labels, and reviewer-derived measurements are excluded from learned features. The traditional score is selected using only non-held-out runs. Neural models see either the normalized 18-sample waveform alone or the waveform plus a small atom gate; neither receives the held-out labels during training.",
        "",
        "For labelled rows \(i\) in held-out run \(r\), every trainable estimator is fit on \(\\{j: r_j \\ne r\\}\) only. The reported predictions are therefore out-of-run scores for all 256 labelled rows. The bootstrap samples the four run blocks with replacement and recomputes AUC/AP on the concatenated sampled blocks; pulse-random intervals are intentionally not used because they would condition on the acquisition run.",
        "",
        "## Methods",
        "",
        "- **traditional_train_selected_score:** a transparent train-run-selected scorecard over P09/q-template/rubric-independent detector-quality scalars, with sign selected on training runs only.",
        "- **ridge:** ridge linear classifier on scalar waveform, q-template, detector-quality, and one-hot method/stave/taxon inputs.",
        "- **gradient_boosted_trees:** histogram gradient-boosted trees on the same tabular inputs.",
        "- **mlp:** two-layer tabular neural network on the same inputs.",
        "- **1d_cnn:** compact convolutional network on the normalized 18-sample waveform.",
        "- **atom_gated_cnn_new:** the new architecture, a waveform CNN concatenated with q-template/late-peak/baseline/saturation atom gates.",
        "",
        "The ridge objective is",
        "",
        "\\[\\min_w \\sum_i (y_i - w^T z_i)^2 + \\alpha\\lVert w\\rVert_2^2,\\]",
        "",
        "where \(z_i\) is the fold-standardized tabular feature vector. The MLP and boosted-tree models use the same \(z_i\) and optimize held-out probability scores. The 1D-CNN maps normalized waveform samples \(x_i(t)\) through two convolutional layers and a global max-pool. The new architecture augments this latent waveform vector \(h_i\) with atom gates \(a_i=(q_{bad}, late, baseline, saturation, ...)\),",
        "",
        "\\[s_i = \\sigma\\{g([h_i, a_i])\\},\\]",
        "",
        "so it directly tests whether q-template and neighbouring support atoms improve transfer beyond waveform shape alone.",
        "",
        "## Head-to-Head Benchmark",
        "",
        summary.to_markdown(index=False),
        "",
        "## Per-Run Metrics",
        "",
        per_run.sort_values(["method", "run"]).to_markdown(index=False),
        "",
        "## Traditional Fold Choices",
        "",
        choices.to_markdown(index=False),
        "",
        "## q-template Transfer Diagnostics",
        "",
        transfer_diag.to_markdown(index=False),
        "",
        "The first contrast is a direct descriptive q-template enrichment check. The second asks whether the atom-gated CNN's most confident decile is enriched in consensus positives. These diagnostics are not used to choose the winner; they are reported to separate classifier performance from the narrower q-template-transfer question.",
        "",
        "## Systematics and Caveats",
        "",
        "- The hand-scan set is small and deliberately enriched by previous traditional/ML rankers, so absolute rates do not estimate full-dataset prevalence.",
        "- The target is autonomous hand-style morphology adjudication, not independent human review or particle truth.",
        "- Because only four runs carry labels, run-block intervals are coarse; they are still preferable to pulse-level bootstrap intervals for acquisition-transfer claims.",
        "- The `taxon` feature is a prior gallery source label and may encode selection-context information; the report therefore treats this as a transfer triage result rather than a deployable classifier.",
        "- Strong performance by q-template or atom-gated methods supports detector-quality transfer, not injection realism by itself.",
        "",
        "## Verdict",
        "",
        f"`result.json` names **{winner}** as the winner. The q-template atom transfer is summarized as `{result['verdict']}`.",
        "",
        "## Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python {SCRIPT_PATH} --config {DEFAULT_CONFIG}",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    args = parser.parse_args()
    t0 = time.time()
    config = load_yaml(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    repro_counts, reproduced = scan_raw_counts(config)
    expected = int(config["expected_selected_pulses"])
    repro_match = pd.DataFrame([
        {
            "quantity": "selected B-stave pulses with amplitude >1000 ADC",
            "expected": expected,
            "reproduced": reproduced,
            "delta": reproduced - expected,
            "tolerance": 0,
            "pass": reproduced == expected,
        }
    ])
    if reproduced != expected:
        raise RuntimeError(f"raw reproduction failed: {reproduced} != {expected}")

    labels = pd.read_csv(config["label_path"])
    waves = parse_waveforms(labels["normalized_waveform"])
    labels = add_hand_features(labels, waves)
    target_col = config["target"]["column"]
    if labels[target_col].nunique() < 2:
        raise RuntimeError("target has fewer than two classes")

    pred, summary, per_run, choices = run_benchmark(labels, waves, config)
    winner = str(summary.iloc[0]["method"])
    q_row = summary.loc[summary["method"].eq("atom_gated_cnn_new")].iloc[0]
    trad_row = summary.loc[summary["method"].eq("traditional_train_selected_score")].iloc[0]
    verdict = "handscan_support_transfer_seen" if q_row["roc_auc"] >= trad_row["roc_auc"] - 0.02 else "traditional_or_tabular_method_preferred_on_small_handscan"

    label_diag = labels.groupby("run").agg(
        n=("gallery_row_id", "size"),
        positives=(target_col, "sum"),
        positive_fraction=(target_col, "mean"),
        mean_q_template_rmse=("q_template_rmse", "mean"),
        mean_late_fraction=("late_fraction", "mean"),
    ).reset_index()
    q_top = labels["q_template_rmse"].ge(labels["q_template_rmse"].quantile(0.75))
    transfer_diag = pd.DataFrame([
        {
            "contrast": "target_rate_top_q_quartile_minus_rest",
            "value": float(labels.loc[q_top, target_col].mean() - labels.loc[~q_top, target_col].mean()),
        },
        {
            "contrast": "target_rate_atom_gated_top_decile",
            "value": float(pred.loc[pred["method"].eq("atom_gated_cnn_new")].nlargest(max(1, len(labels) // 10), "score")["y_true"].mean()),
        },
        {
            "contrast": "heldout_positive_fraction",
            "value": float(labels[target_col].mean()),
        },
    ])

    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "worker": config["worker"],
        "winner": winner,
        "winner_family": str(summary.iloc[0]["family"]),
        "winner_metric": "roc_auc",
        "verdict": verdict,
        "raw_reproduction_pass": bool(reproduced == expected),
        "reproduction_match_table": repro_match,
        "n_labelled": int(len(labels)),
        "label_runs": [int(x) for x in sorted(labels["run"].unique())],
        "n_positive": int(labels[target_col].sum()),
        "method_summary": summary.to_dict(orient="records"),
        "novel_tickets": [
            {
                "title": "S01k independent human overlay review for q-template hand-scan transfer",
                "body": "Repeat the S01j external hand-scan transfer on an independently reviewed overlay/real-current gallery with at least 100 positives per labelled run, preserving run-held-out ridge, boosted-tree, MLP, 1D-CNN, and atom-gated CNN benchmarks plus run-block bootstrap CIs.",
            }
        ],
        "runtime_seconds": float(time.time() - t0),
    }

    repro_counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    repro_match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    labels.to_csv(out_dir / "handscan_feature_table.csv", index=False)
    pred.to_csv(out_dir / "heldout_predictions.csv", index=False)
    summary.to_csv(out_dir / "method_summary.csv", index=False)
    per_run.to_csv(out_dir / "heldout_per_run_metrics.csv", index=False)
    choices.to_csv(out_dir / "traditional_fold_choices.csv", index=False)
    label_diag.to_csv(out_dir / "label_counts_by_run.csv", index=False)
    transfer_diag.to_csv(out_dir / "qtemplate_transfer_diagnostics.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 4))
    plot_df = summary.iloc[::-1]
    ax.errorbar(
        plot_df["roc_auc"],
        np.arange(len(plot_df)),
        xerr=[plot_df["roc_auc"] - plot_df["auc_ci_low"], plot_df["auc_ci_high"] - plot_df["roc_auc"]],
        fmt="o",
        color="#1f77b4",
        ecolor="#666666",
        capsize=3,
    )
    ax.set_yticks(np.arange(len(plot_df)), plot_df["method"])
    ax.set_xlabel("Run-block ROC AUC")
    ax.set_xlim(0.0, 1.02)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "method_auc_ci.png", dpi=180)
    plt.close(fig)

    result_for_json = result.copy()
    result_for_json["reproduction_match_table"] = repro_match.to_dict(orient="records")
    (out_dir / "result.json").write_text(json.dumps(clean_json(result_for_json), indent=2), encoding="utf-8")

    input_rows = [
        {"path": args.config, "sha256": sha256_file(args.config)},
        {"path": SCRIPT_PATH, "sha256": sha256_file(SCRIPT_PATH)},
        {"path": config["label_path"], "sha256": sha256_file(config["label_path"])},
    ]
    for run in sorted(run_groups(config)):
        p = Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"
        input_rows.append({"path": str(p), "sha256": sha256_file(p)})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    write_report(out_dir, config, result, summary, per_run, repro_match, choices, label_diag, transfer_diag)
    manifest = {
        "ticket_id": config["ticket_id"],
        "config": args.config,
        "command": f"{SCRIPT_PATH} --config {args.config}",
        "git_commit": git_commit(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "random_seed": int(config["random_seed"]),
        "outputs": sorted(str(p) for p in out_dir.iterdir() if p.is_file()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
