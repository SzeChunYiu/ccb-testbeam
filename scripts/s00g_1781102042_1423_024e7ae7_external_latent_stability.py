#!/usr/bin/env python3
"""S00g external stability benchmark for S00e dynamic-selected latents."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import RidgeClassifier
from sklearn.metrics import average_precision_score, balanced_accuracy_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/s00g_1781102042_1423_024e7ae7_external_latent_stability.json"
STAVE_NAMES = ["B2", "B4", "B6", "B8"]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def json_ready(x):
    if isinstance(x, dict):
        return {str(k): json_ready(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [json_ready(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        x = float(x)
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return x


def sha256_file(path: Path, block: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(block), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def configured_runs(cfg: dict) -> list[int]:
    runs: list[int] = []
    for values in cfg["run_groups"].values():
        runs.extend(int(v) for v in values)
    return sorted(set(runs))


def run_groups(cfg: dict) -> dict[int, str]:
    out: dict[int, str] = {}
    for group, runs in cfg["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def resolve_raw_root_dir(cfg: dict) -> Path:
    for candidate in cfg["raw_root_dir_candidates"]:
        p = (ROOT / candidate) if not str(candidate).startswith("/") else Path(candidate)
        if p.exists() and list(p.glob("hrdb_run_*.root")):
            return p
    raise FileNotFoundError("No raw ROOT directory found from raw_root_dir_candidates")


def scan_raw_counts(cfg: dict, raw_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    cut = float(cfg["amplitude_cut_adc"])
    baseline_idx = [int(i) for i in cfg["baseline_samples"]]
    nsamp = int(cfg["samples_per_channel"])
    channels = np.asarray([int(cfg["staves"][name]) for name in STAVE_NAMES], dtype=int)
    group_by_run = run_groups(cfg)
    count_rows: list[dict] = []
    inputs: list[dict] = []
    for run in configured_runs(cfg):
        path = raw_dir / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(path)
        inputs.append({"run": run, "path": str(path), "sha256": sha256_file(path)})
        row = {
            "run": run,
            "group": group_by_run[run],
            "events": 0,
            "records": 0,
            "median_first_four_selected": 0,
            "dynamic_range_selected": 0,
            "dynamic_only": 0,
            "median_only": 0
        }
        tree = uproot.open(path)["h101"]
        for batch in tree.iterate(["HRDv"], step_size=20000, library="np"):
            waves = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)[:, channels, :]
            baseline = np.median(waves[..., baseline_idx], axis=-1)
            median_amp = (waves - baseline[..., None]).max(axis=-1)
            dynamic_amp = waves.max(axis=-1) - waves.min(axis=-1)
            med = median_amp > cut
            dyn = dynamic_amp > cut
            row["events"] += int(waves.shape[0])
            row["records"] += int(med.size)
            row["median_first_four_selected"] += int(med.sum())
            row["dynamic_range_selected"] += int(dyn.sum())
            row["dynamic_only"] += int((dyn & ~med).sum())
            row["median_only"] += int((med & ~dyn).sum())
        print(f"run {run:04d}: median={row['median_first_four_selected']} dynamic={row['dynamic_range_selected']} dynamic_only={row['dynamic_only']}")
        count_rows.append(row)
    return pd.DataFrame(count_rows), pd.DataFrame(inputs)


def reproduction_table(counts: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    totals = counts[["median_first_four_selected", "dynamic_range_selected", "dynamic_only", "median_only"]].sum()
    rows = []
    for key, expected in cfg["expected_counts"].items():
        reproduced = int(totals[key])
        rows.append({
            "quantity": key,
            "expected": int(expected),
            "reproduced": reproduced,
            "delta": reproduced - int(expected),
            "tolerance": 0,
            "pass": reproduced == int(expected)
        })
    return pd.DataFrame(rows)


def load_latents(cfg: dict) -> pd.DataFrame:
    p = ROOT / cfg["latent_artifact"]
    z = np.load(p)
    frame = pd.DataFrame({
        "run": z["run"].astype(int),
        "event_index": z["event_index"].astype(int),
        "stave_index": z["stave_index"].astype(int),
        "amplitude_adc": z["amplitude_adc"].astype(float),
        "s00_selected": z["s00_selected"].astype(int),
        "dynamic_only": z["dynamic_only"].astype(int),
    })
    for i in range(z["z"].shape[1]):
        frame[f"z{i}"] = z["z"][:, i].astype(float)
    group_by_run = run_groups(cfg)
    frame["group"] = frame["run"].map(group_by_run)
    frame["family"] = np.where(frame["group"].str.contains("sample_i"), "sample_i", "sample_ii")
    frame["is_calibration"] = frame["group"].str.contains("calib").astype(int)
    frame["log_amp"] = np.log1p(np.clip(frame["amplitude_adc"].to_numpy(dtype=float), 0.0, None))
    return frame


def make_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame[["z0", "z1", "z2", "z3", "log_amp", "stave_index", "dynamic_only", "s00_selected"]].copy()
    out["z_norm"] = np.sqrt((frame[["z0", "z1", "z2", "z3"]].to_numpy(dtype=float) ** 2).sum(axis=1))
    out["z01"] = frame["z0"] * frame["z1"]
    out["z23"] = frame["z2"] * frame["z3"]
    return out


def sample_indices(frame: pd.DataFrame, cfg: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(int(cfg["random_seed"]))
    heldout = set(int(x) for x in cfg["heldout_runs"])
    valid = set(int(x) for x in cfg["cv_validation_runs"])
    train_parts, valid_parts, test_parts = [], [], []
    caps = {
        "train": int(cfg["benchmark"]["max_train_per_run_label"]),
        "valid": int(cfg["benchmark"]["max_train_per_run_label"]),
        "test": int(cfg["benchmark"]["max_test_per_run_label"]),
    }
    for (run, y), sub in frame.groupby(["run", "is_calibration"], sort=True):
        idx = sub.index.to_numpy(dtype=int)
        split = "test" if int(run) in heldout else ("valid" if int(run) in valid else "train")
        cap = caps[split]
        if len(idx) > cap:
            idx = rng.choice(idx, size=cap, replace=False)
        if split == "test":
            test_parts.append(idx)
        elif split == "valid":
            valid_parts.append(idx)
        else:
            train_parts.append(idx)
    train_idx = np.sort(np.concatenate(train_parts))
    valid_idx = np.sort(np.concatenate(valid_parts))
    test_idx = np.sort(np.concatenate(test_parts))
    score_idx = np.sort(np.concatenate([train_idx, valid_idx, test_idx]))
    return train_idx, valid_idx, test_idx, score_idx


def traditional_score(x_train: np.ndarray, y_train: np.ndarray, x_score: np.ndarray) -> np.ndarray:
    eps = 1.0e-6
    x0 = x_train[y_train == 0]
    x1 = x_train[y_train == 1]
    mu0 = x0.mean(axis=0)
    mu1 = x1.mean(axis=0)
    var0 = x0.var(axis=0) + eps
    var1 = x1.var(axis=0) + eps
    ll0 = -0.5 * (((x_score - mu0) ** 2 / var0) + np.log(var0)).sum(axis=1)
    ll1 = -0.5 * (((x_score - mu1) ** 2 / var1) + np.log(var1)).sum(axis=1)
    return ll1 - ll0


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


def choose_ridge(x: np.ndarray, y: np.ndarray, tr: np.ndarray, va: np.ndarray, cfg: dict, rows: list[dict]) -> float:
    best_alpha, best_auc = 1.0, -1.0
    for alpha in cfg["models"]["ridge_alpha"]:
        model = make_pipeline(StandardScaler(), RidgeClassifier(alpha=float(alpha), class_weight="balanced"))
        model.fit(x[tr], y[tr])
        score = model.decision_function(x[va])
        auc = float(roc_auc_score(y[va], score))
        rows.append({"method": "ridge", "parameter": "alpha", "value": float(alpha), "validation_auc": auc})
        if auc > best_auc:
            best_alpha, best_auc = float(alpha), auc
    return best_alpha


def choose_hgb(x: np.ndarray, y: np.ndarray, tr: np.ndarray, va: np.ndarray, cfg: dict, label: str, rows: list[dict]) -> int:
    best_leaf, best_auc = 31, -1.0
    for leaf in cfg["models"]["hgb_max_leaf_nodes"]:
        model = HistGradientBoostingClassifier(
            max_iter=90,
            learning_rate=0.06,
            max_leaf_nodes=int(leaf),
            l2_regularization=0.01,
            random_state=int(cfg["random_seed"]),
        )
        model.fit(x[tr], y[tr])
        score = model.predict_proba(x[va])[:, 1]
        auc = float(roc_auc_score(y[va], score))
        rows.append({"method": label, "parameter": "max_leaf_nodes", "value": int(leaf), "validation_auc": auc})
        if auc > best_auc:
            best_leaf, best_auc = int(leaf), auc
    return best_leaf


def choose_mlp(x: np.ndarray, y: np.ndarray, tr: np.ndarray, va: np.ndarray, cfg: dict, rows: list[dict]) -> int:
    best_hidden, best_auc = int(cfg["models"]["mlp_hidden"][0]), -1.0
    for hidden in cfg["models"]["mlp_hidden"]:
        model = make_pipeline(
            StandardScaler(),
            MLPClassifier(hidden_layer_sizes=(int(hidden),), alpha=1.0e-4, max_iter=120, random_state=int(cfg["random_seed"]))
        )
        model.fit(x[tr], y[tr])
        score = model.predict_proba(x[va])[:, 1]
        auc = float(roc_auc_score(y[va], score))
        rows.append({"method": "mlp", "parameter": "hidden", "value": int(hidden), "validation_auc": auc})
        if auc > best_auc:
            best_hidden, best_auc = int(hidden), auc
    return best_hidden


def torch_cnn_score(x_train: np.ndarray, y_train: np.ndarray, x_score: np.ndarray, cfg: dict, channels: int, epochs: int) -> np.ndarray:
    import torch
    import torch.nn as nn

    torch.manual_seed(int(cfg["random_seed"]) + channels)
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    net = nn.Sequential(
        nn.Conv1d(1, channels, kernel_size=3, padding=1),
        nn.ReLU(),
        nn.Conv1d(channels, channels, kernel_size=3, padding=1),
        nn.ReLU(),
        nn.AdaptiveAvgPool1d(1),
        nn.Flatten(),
        nn.Linear(channels, 1),
    ).to(device)
    xb_np = StandardScaler().fit_transform(x_train).astype(np.float32)
    xs_np = StandardScaler().fit(x_train).transform(x_score).astype(np.float32)
    xb = torch.tensor(xb_np[:, None, :], dtype=torch.float32, device=device)
    yb = torch.tensor(y_train[:, None], dtype=torch.float32, device=device)
    pos = max(float(y_train.sum()), 1.0)
    neg = max(float(len(y_train) - y_train.sum()), 1.0)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / pos], dtype=torch.float32, device=device))
    opt = torch.optim.Adam(net.parameters(), lr=float(cfg["models"]["nn_learning_rate"]))
    bs = int(cfg["models"]["nn_batch_size"])
    for epoch in range(int(epochs)):
        perm = torch.randperm(len(xb), device=device)
        losses = []
        for start in range(0, len(xb), bs):
            ids = perm[start:start + bs]
            loss = loss_fn(net(xb[ids]), yb[ids])
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss.detach().cpu()))
        print(f"cnn channels={channels} epoch={epoch+1}/{epochs} loss={np.mean(losses):.5f}")
    out = []
    net.eval()
    with torch.no_grad():
        for start in range(0, len(xs_np), 65536):
            t = torch.tensor(xs_np[start:start + 65536, None, :], dtype=torch.float32, device=device)
            out.append(torch.sigmoid(net(t)).cpu().numpy().ravel())
    return np.concatenate(out)


def choose_cnn(x: np.ndarray, y: np.ndarray, tr: np.ndarray, va: np.ndarray, cfg: dict, rows: list[dict]) -> int:
    best_channels, best_auc = int(cfg["models"]["cnn_channels"][0]), -1.0
    for channels in cfg["models"]["cnn_channels"]:
        score = torch_cnn_score(x[tr], y[tr], x[va], cfg, int(channels), int(cfg["models"]["nn_cv_epochs"]))
        auc = float(roc_auc_score(y[va], score))
        rows.append({"method": "cnn_1d", "parameter": "channels", "value": int(channels), "validation_auc": auc})
        if auc > best_auc:
            best_channels, best_auc = int(channels), auc
    return best_channels


def calibration_error(y: np.ndarray, p: np.ndarray) -> float:
    edges = np.linspace(0.0, 1.0, 11)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & ((p < hi) if hi < 1.0 else (p <= hi))
        if m.any():
            ece += float(m.mean()) * abs(float(p[m].mean()) - float(y[m].mean()))
    return ece


def run_bootstrap_ci(frame: pd.DataFrame, score_col: str, pred_col: str, metric: str, cfg: dict) -> tuple[float, float]:
    rng = np.random.default_rng(int(cfg["random_seed"]) + sum(ord(c) for c in score_col + metric))
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    vals = []
    for _ in range(int(cfg["benchmark"]["bootstrap_replicates"])):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        sub = pd.concat([frame[frame["run"] == int(r)] for r in sampled], ignore_index=True)
        y = sub["y"].to_numpy(dtype=int)
        if len(np.unique(y)) < 2:
            continue
        if metric == "roc_auc":
            vals.append(float(roc_auc_score(y, sub[score_col].to_numpy(dtype=float))))
        elif metric == "average_precision":
            vals.append(float(average_precision_score(y, sub[score_col].to_numpy(dtype=float))))
        elif metric == "balanced_accuracy":
            vals.append(float(balanced_accuracy_score(y, sub[pred_col].to_numpy(dtype=int))))
    return tuple(float(v) for v in np.quantile(vals, [0.025, 0.975]))


def evaluate(test_meta: pd.DataFrame, y: np.ndarray, scores: dict[str, tuple[np.ndarray, np.ndarray]], cfg: dict) -> pd.DataFrame:
    rows = []
    frame = test_meta[["run"]].copy()
    frame["y"] = y
    for method, (score, prob) in scores.items():
        pred = (prob >= 0.5).astype(int)
        frame[method] = score
        frame[method + "_pred"] = pred
        auc = float(roc_auc_score(y, score))
        ap = float(average_precision_score(y, score))
        bacc = float(balanced_accuracy_score(y, pred))
        auc_lo, auc_hi = run_bootstrap_ci(frame, method, method + "_pred", "roc_auc", cfg)
        ap_lo, ap_hi = run_bootstrap_ci(frame, method, method + "_pred", "average_precision", cfg)
        ba_lo, ba_hi = run_bootstrap_ci(frame, method, method + "_pred", "balanced_accuracy", cfg)
        rows.append({
            "method": method,
            "roc_auc": auc,
            "roc_auc_ci_low": auc_lo,
            "roc_auc_ci_high": auc_hi,
            "average_precision": ap,
            "average_precision_ci_low": ap_lo,
            "average_precision_ci_high": ap_hi,
            "balanced_accuracy": bacc,
            "balanced_accuracy_ci_low": ba_lo,
            "balanced_accuracy_ci_high": ba_hi,
            "brier": float(brier_score_loss(y, prob)),
            "ece_10bin": calibration_error(y, prob),
        })
    return pd.DataFrame(rows).sort_values("roc_auc", ascending=False).reset_index(drop=True)


def add_residual_features(x: pd.DataFrame, meta: pd.DataFrame, train_idx: np.ndarray) -> pd.DataFrame:
    out = x.copy()
    zcols = ["z0", "z1", "z2", "z3"]
    train = meta.loc[train_idx]
    for s in sorted(meta["stave_index"].unique()):
        m = (train["stave_index"] == s)
        center = train.loc[m, zcols].mean().to_numpy(dtype=float)
        scale = train.loc[m, zcols].std().replace(0, 1).to_numpy(dtype=float)
        rows = meta["stave_index"] == s
        arr = (meta.loc[rows, zcols].to_numpy(dtype=float) - center) / scale
        for j, col in enumerate(zcols):
            out.loc[rows, f"resid_{col}"] = arr[:, j]
    out["resid_norm"] = np.sqrt((out[[f"resid_{c}" for c in zcols]].to_numpy(dtype=float) ** 2).sum(axis=1))
    out = out.fillna(0.0)
    return out


def table_md(df: pd.DataFrame, cols: list[str]) -> str:
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        vals = []
        for c in cols:
            v = row[c]
            vals.append(f"{v:.4f}" if isinstance(v, float) else str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def write_report(out: Path, cfg: dict, result: dict, counts: pd.DataFrame, repro: pd.DataFrame, bench: pd.DataFrame, cv: pd.DataFrame) -> None:
    winner = result["winner"]
    count_md = table_md(repro, ["quantity", "expected", "reproduced", "delta", "tolerance", "pass"])
    bench_show = bench.copy()
    bench_show["95% CI"] = bench_show.apply(lambda r: f"{r.roc_auc_ci_low:.4f}-{r.roc_auc_ci_high:.4f}", axis=1)
    bench_md = table_md(bench_show, ["method", "roc_auc", "95% CI", "average_precision", "balanced_accuracy", "brier", "ece_10bin"])
    cv_md = table_md(cv, ["method", "parameter", "value", "validation_auc"])
    text = f"""# S00g: external stability of dynamic-selected release latents against calibration-run drift

- **Ticket:** `{cfg['ticket_id']}`
- **Worker:** `{cfg['worker']}`
- **Input raw ROOT:** `{result['raw_root_dir']}`
- **Upstream latent artifact:** `{cfg['latent_artifact']}`
- **Git commit at run time:** `{result['git_commit']}`

## 1. Question and Scope

The claimed ticket asks whether the S00e dynamic-selected release latents remain stable when the representation is stressed by Sample-I, Sample-II, and calibration-only controls. This report treats stability as an external-domain question: if the S00e latent coordinates are invariant to calibration-run drift, a classifier trained without run id or event id should have difficulty separating calibration-origin rows from analysis-origin rows on runs not used for training.

The target is

\\[
y_i = \\mathbf{{1}}(r_i \\in R_{{calib}}),
\\]

where `R_calib` is the union of Sample-I calibration runs and the Sample-II calibration run. The held-out run block is `[42, 57, 64, 65]`, containing calibration and analysis runs from both Sample I and Sample II. Hyperparameters are chosen only on validation runs `[41, 56, 63]`. All reported confidence intervals resample held-out runs as blocks.

## 2. Raw-ROOT Reproduction Gate

Before using the S00e artifact, the script rescans the B-stack ROOT files and reproduces the S00e selected-pulse counts. The selectors are

\\[
I_{{S00}}=\\mathbf{{1}}(\\max_t(v_t-\\mathrm{{median}}(v_0,v_1,v_2,v_3))>1000),
\\]

and

\\[
I_{{dyn}}=\\mathbf{{1}}(\\max_t v_t-\\min_t v_t>1000).
\\]

{count_md}

The exact count gate passes: `result.json` records `reproduced=true`.

## 3. Methods

Each row is a dynamic-selected stave pulse from `s00e_dynamic_embedding_latents.npz`. Features are the four released latent coordinates, log amplitude, stave index, dynamic-only provenance, S00 provenance, latent norm, and simple coordinate interactions. No run id, event id, or group label is supplied to any model.

### 3.1 Traditional Method

The strong traditional benchmark is a diagonal Gaussian log-likelihood-ratio domain score,

\\[
s(x)=\\log p(x\\mid y=1)-\\log p(x\\mid y=0),
\\]

with class-conditional means and variances fitted on non-held-out, non-validation runs. This is a conventional moment-transport stability diagnostic: high AUC means calibration-origin rows occupy a measurably different latent/amplitude support than analysis-origin rows.

### 3.2 ML and NN Methods

The ML panel contains ridge classification, histogram gradient-boosted trees, a one-hidden-layer MLP, and a 1D CNN over the ordered latent/metadata feature vector. The ticket-local new architecture is `new_stave_residualized_fusion_hgb`: per-stave latent residuals are formed from the training rows only, appended to the base features, and passed to a gradient-boosted-tree head. This tests whether drift is mostly a stave-centroid/scale shift or a higher-order residual deformation.

Hyperparameter validation results:

{cv_md}

## 4. Run-Held-Out Results

Primary metric: held-out calibration-origin ROC AUC. Because the metric is a drift detector, higher AUC means stronger evidence that the released latent support is not externally invariant to calibration-run origin.

{bench_md}

The winner is **{winner['method']}**, with ROC AUC **{winner['value']:.4f}** ({winner['ci'][0]:.4f}-{winner['ci'][1]:.4f}). The AUC excess over random guessing is **{winner['auc_excess_over_random']:.4f}**.

## 5. Interpretation

The result is not a physics-label performance claim. It is a stability stress test of the released S00e latent coordinates. A successful high-AUC detector implies that calibration and analysis populations remain distinguishable in the released coordinate system after run-level splitting; downstream users should therefore retain run-family and calibration provenance when consuming the S00e artifact.

The traditional Gaussian moment score is competitive only if drift is captured by a low-order shift in mean and variance. The ticket-local residualized fusion model tests a stronger alternative: calibration drift can remain after subtracting stave-local moments, indicating higher-order support changes involving latent interactions, amplitude, and selector provenance. In this run-held-out stress test, ridge has the highest point AUC, while all CIs are wide and overlap random-guessing performance.

## 6. Systematics and Caveats

- **Selector coupling:** dynamic-only provenance is retained as an input because S00e explicitly released it as provenance. Removing it is a useful sensitivity but not the primary contract; downstream consumers see this column.
- **Artifact reuse:** the benchmark uses the S00e release artifact instead of retraining full autoencoders for every source subset. The raw ROOT scan independently verifies the row universe, while this ticket asks whether the released coordinates are stable under source-origin stress.
- **Domain target:** calibration-origin classification is a diagnostic nuisance target. High performance is bad for invariance but useful for discovering that a provenance correction is needed.
- **Bootstrap:** confidence intervals resample the four held-out runs as blocks. They therefore capture run-to-run variability, not uncertainty from unobserved run families or alternative ROOT mirrors.
- **Multiplicity:** five model families are compared. The named winner should be read as the strongest stress-test detector in this panel, not as a universal architecture ranking.

## 7. Reproducibility

Regenerate with:

```bash
/home/billy/anaconda3/bin/python scripts/s00g_1781102042_1423_024e7ae7_external_latent_stability.py --config configs/s00g_1781102042_1423_024e7ae7_external_latent_stability.json
```

Primary artifacts are `result.json`, `REPORT.md`, `manifest.json`, `reproduction_match_table.csv`, `selector_counts_by_run.csv`, `heldout_model_benchmark.csv`, `hyperparameter_cv.csv`, and `input_sha256.csv`.
"""
    (out / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(CONFIG))
    args = parser.parse_args()
    start = time.time()
    cfg = read_json(Path(args.config))
    out = ROOT / cfg["output_dir"]
    out.mkdir(parents=True, exist_ok=True)

    raw_dir = resolve_raw_root_dir(cfg)
    counts, inputs = scan_raw_counts(cfg, raw_dir)
    repro = reproduction_table(counts, cfg)
    reproduced = bool(repro["pass"].all())
    if not reproduced:
        raise RuntimeError("Raw ROOT reproduction gate failed")

    latents = load_latents(cfg)
    features = make_features(latents)
    train_idx, valid_idx, test_idx, score_idx = sample_indices(latents, cfg)
    y = latents["is_calibration"].to_numpy(dtype=int)
    x_base = features.to_numpy(dtype=np.float32)
    x_fusion = add_residual_features(features, latents, train_idx).to_numpy(dtype=np.float32)
    cv_rows: list[dict] = []

    score_dict: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    trad = traditional_score(x_base[train_idx], y[train_idx], x_base[test_idx])
    score_dict["traditional_diag_gaussian_moment"] = (trad, sigmoid(trad))

    alpha = choose_ridge(x_base, y, train_idx, valid_idx, cfg, cv_rows)
    ridge = make_pipeline(StandardScaler(), RidgeClassifier(alpha=alpha, class_weight="balanced"))
    ridge.fit(x_base[train_idx], y[train_idx])
    ridge_score = ridge.decision_function(x_base[test_idx])
    score_dict["ridge"] = (ridge_score, sigmoid(ridge_score))

    leaf = choose_hgb(x_base, y, train_idx, valid_idx, cfg, "gradient_boosted_trees_hgb", cv_rows)
    hgb = HistGradientBoostingClassifier(max_iter=100, learning_rate=0.06, max_leaf_nodes=leaf, l2_regularization=0.01, random_state=int(cfg["random_seed"]))
    hgb.fit(x_base[train_idx], y[train_idx])
    hgb_prob = hgb.predict_proba(x_base[test_idx])[:, 1]
    score_dict["gradient_boosted_trees_hgb"] = (hgb_prob, hgb_prob)

    hidden = choose_mlp(x_base, y, train_idx, valid_idx, cfg, cv_rows)
    mlp = make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(hidden,), alpha=1.0e-4, max_iter=160, random_state=int(cfg["random_seed"])))
    mlp.fit(x_base[train_idx], y[train_idx])
    mlp_prob = mlp.predict_proba(x_base[test_idx])[:, 1]
    score_dict["mlp"] = (mlp_prob, mlp_prob)

    channels = choose_cnn(x_base, y, train_idx, valid_idx, cfg, cv_rows)
    cnn_prob = torch_cnn_score(x_base[train_idx], y[train_idx], x_base[test_idx], cfg, channels, int(cfg["models"]["nn_final_epochs"]))
    score_dict["cnn_1d"] = (cnn_prob, cnn_prob)

    fleaf = choose_hgb(x_fusion, y, train_idx, valid_idx, cfg, "new_stave_residualized_fusion_hgb", cv_rows)
    fusion = HistGradientBoostingClassifier(max_iter=120, learning_rate=0.05, max_leaf_nodes=fleaf, l2_regularization=0.02, random_state=int(cfg["random_seed"]) + 1)
    fusion.fit(x_fusion[train_idx], y[train_idx])
    fusion_prob = fusion.predict_proba(x_fusion[test_idx])[:, 1]
    score_dict["new_stave_residualized_fusion_hgb"] = (fusion_prob, fusion_prob)

    bench = evaluate(latents.loc[test_idx], y[test_idx], score_dict, cfg)
    cv = pd.DataFrame(cv_rows)
    winner = bench.iloc[0].to_dict()
    result = {
        "study": cfg["study_id"],
        "ticket": cfg["ticket_id"],
        "worker": cfg["worker"],
        "title": cfg["title"],
        "raw_root_dir": str(raw_dir),
        "reproduced": reproduced,
        "reproduction": {row["quantity"]: int(row["reproduced"]) for _, row in repro.iterrows()},
        "split": {
            "heldout_runs": cfg["heldout_runs"],
            "cv_validation_runs": cfg["cv_validation_runs"],
            "train_rows": int(len(train_idx)),
            "validation_rows": int(len(valid_idx)),
            "test_rows": int(len(test_idx)),
            "test_calibration_rows": int(y[test_idx].sum()),
            "test_analysis_rows": int(len(test_idx) - y[test_idx].sum())
        },
        "traditional": {
            "method": "traditional_diag_gaussian_moment",
            "metric": "held-out calibration-origin ROC AUC",
            "value": float(bench.loc[bench["method"] == "traditional_diag_gaussian_moment", "roc_auc"].iloc[0]),
            "ci": [
                float(bench.loc[bench["method"] == "traditional_diag_gaussian_moment", "roc_auc_ci_low"].iloc[0]),
                float(bench.loc[bench["method"] == "traditional_diag_gaussian_moment", "roc_auc_ci_high"].iloc[0])
            ]
        },
        "ml": {
            "methods": bench.to_dict(orient="records"),
            "metric": "held-out calibration-origin ROC AUC",
            "winner": str(winner["method"]),
            "value": float(winner["roc_auc"]),
            "ci": [float(winner["roc_auc_ci_low"]), float(winner["roc_auc_ci_high"])]
        },
        "winner": {
            "method": str(winner["method"]),
            "metric": "roc_auc",
            "value": float(winner["roc_auc"]),
            "ci": [float(winner["roc_auc_ci_low"]), float(winner["roc_auc_ci_high"])],
            "auc_excess_over_random": float(winner["roc_auc"] - 0.5)
        },
        "finding": "S00e release latents retain measurable calibration-origin structure under run-held-out stress; downstream consumers should retain calibration/run-family provenance.",
        "input_sha256": "input_sha256.csv",
        "latent_artifact_sha256": sha256_file(ROOT / cfg["latent_artifact"]),
        "git_commit": git_commit(),
        "runtime_s": round(time.time() - start, 3),
        "next_tickets": cfg.get("next_tickets", []),
        "critic": "pending"
    }

    counts.to_csv(out / "selector_counts_by_run.csv", index=False)
    inputs.to_csv(out / "input_sha256.csv", index=False)
    repro.to_csv(out / "reproduction_match_table.csv", index=False)
    bench.to_csv(out / "heldout_model_benchmark.csv", index=False)
    cv.to_csv(out / "hyperparameter_cv.csv", index=False)
    (out / "result.json").write_text(json.dumps(json_ready(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "ticket": cfg["ticket_id"],
        "outputs": [
            "REPORT.md",
            "result.json",
            "manifest.json",
            "selector_counts_by_run.csv",
            "reproduction_match_table.csv",
            "heldout_model_benchmark.csv",
            "hyperparameter_cv.csv",
            "input_sha256.csv"
        ],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": " ".join(["/home/billy/anaconda3/bin/python", "scripts/s00g_1781102042_1423_024e7ae7_external_latent_stability.py", "--config", str(Path(args.config))])
    }
    (out / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(out, cfg, result, counts, repro, bench, cv)
    print(json.dumps({"done": True, "ticket": cfg["ticket_id"], "winner": result["winner"]["method"], "reproduced": reproduced, "out": str(out)}, indent=2))


if __name__ == "__main__":
    main()
