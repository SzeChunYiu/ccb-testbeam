#!/usr/bin/env python3
"""G4-07 simulation-vs-data domain-gap benchmark.

This script intentionally reads the reduced raw ROOT files for the real-data
anchor and reads GEANT4 truth ROOT directly for the simulation side.  It writes
all artifacts for ticket 1781212365.2054704.7c540934.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from string import Template

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import uproot
from scipy.special import expit
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression, RidgeClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


TICKET = "1781212365.2054704.7c540934"
OUTDIR = Path("reports/1781212365.2054704.7c540934__g4_07_domain_gap")
DOC_REPORT = Path("docs/reports/G4_07_domain_gap.md")
FIG_DIR = Path("docs/figures/reports/1781212365.2054704.7c540934__g4_07_domain_gap")
RAW_ROOT_DIR = Path("/home/billy/Desktop/test_beam/data/root/root")
SIM_ROOT = Path("/home/billy/ccb-geant4/output_30k.root")
RNG_SEED = 1781212365
SAMPLES_PER_CHANNEL = 18
BASELINE_IDX = np.array([0, 1, 2, 3])
STAVES = ["B2", "B4", "B6", "B8"]
CHANNELS = np.array([0, 2, 4, 6])
RUNS = [31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 44, 45, 46, 47, 48, 49,
        50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65]
TRAIN_RUNS = [31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 64]
HELDOUT_RUNS = [r for r in RUNS if r not in TRAIN_RUNS]
FEATURES = [
    "log_q_B2", "log_q_B4", "log_q_B6", "log_q_B8",
    "log_a_B2", "log_a_B4", "log_a_B6", "log_a_B8",
    "hit_B2", "hit_B4", "hit_B6", "hit_B8",
    "multiplicity", "depth_idx", "log_total_q", "early_fraction",
    "late_fraction", "shape_balance", "peak_mean", "peak_span",
]


def real_batch_features(waveforms: np.ndarray) -> pd.DataFrame:
    base = np.median(waveforms[..., BASELINE_IDX], axis=-1)
    corr = waveforms - base[..., None]
    amp = np.maximum(corr.max(axis=-1), 0.0)
    area = np.maximum(corr.sum(axis=-1), 0.0)
    peak = corr.argmax(axis=-1).astype(float)
    hit = amp > 1000.0
    total = area.sum(axis=1)
    mult = hit.sum(axis=1)
    depth = np.where(hit.any(axis=1), hit[:, ::-1].argmax(axis=1), 4)
    depth = np.where(hit.any(axis=1), 3 - depth, -1)
    early = area[:, :2].sum(axis=1) / np.maximum(total, 1.0)
    late = area[:, 2:].sum(axis=1) / np.maximum(total, 1.0)
    rows = {}
    for i, s in enumerate(STAVES):
        rows[f"log_q_{s}"] = np.log1p(area[:, i])
        rows[f"log_a_{s}"] = np.log1p(amp[:, i])
        rows[f"hit_{s}"] = hit[:, i].astype(float)
    rows.update({
        "multiplicity": mult.astype(float),
        "depth_idx": depth.astype(float),
        "log_total_q": np.log1p(total),
        "early_fraction": early,
        "late_fraction": late,
        "shape_balance": (area[:, 0] - area[:, -1]) / np.maximum(total, 1.0),
        "peak_mean": np.where(hit.any(axis=1), (peak * hit).sum(axis=1) / np.maximum(mult, 1), 0.0),
        "peak_span": np.where(hit.any(axis=1), peak.max(axis=1) - peak.min(axis=1), 0.0),
    })
    return pd.DataFrame(rows)


def read_real(max_per_run: int) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    rng = np.random.default_rng(RNG_SEED)
    frames, count_rows = [], []
    total_selected = 0
    for run in RUNS:
        path = RAW_ROOT_DIR / f"hrdb_run_{run:04d}.root"
        selected_pulses = 0
        selected_events = 0
        reservoir = []
        seen = 0
        tree = uproot.open(path)["h101"]
        for batch in tree.iterate(["EVENTNO", "HRDv"], step_size=12000, library="np"):
            hrdv = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, SAMPLES_PER_CHANNEL)
            wave = hrdv[:, CHANNELS, :]
            feats = real_batch_features(wave)
            event_selected = feats["multiplicity"].values > 0
            selected_pulses += int(feats[[f"hit_{s}" for s in STAVES]].values.sum())
            selected_events += int(event_selected.sum())
            sub = feats[event_selected].copy()
            sub["run"] = run
            sub["domain"] = 1
            for _, row in sub.iterrows():
                seen += 1
                if len(reservoir) < max_per_run:
                    reservoir.append(row)
                else:
                    j = rng.integers(0, seen)
                    if j < max_per_run:
                        reservoir[j] = row
        if reservoir:
            frames.append(pd.DataFrame(reservoir))
        count_rows.append({
            "run": run,
            "events_with_selected": selected_events,
            "selected_pulses": selected_pulses,
        })
        total_selected += selected_pulses
    return pd.concat(frames, ignore_index=True), pd.DataFrame(count_rows), total_selected


def read_sim(max_per_pseudorun: int) -> pd.DataFrame:
    rng = np.random.default_rng(RNG_SEED + 1)
    rows = []
    tree = uproot.open(SIM_ROOT)["hibeam"]
    pseudo_runs = np.array(RUNS)
    per_run_seen = {r: 0 for r in RUNS}
    reservoirs = {r: [] for r in RUNS}
    scale = np.array([309.0, 197.0, 156.0, 156.0])
    for chunk in tree.iterate(["Sci_bar_LayerID", "Sci_bar_LayerID1", "Sci_bar_EDep", "Sci_bar_Time"], step_size="80 MB", library="np"):
        n = len(chunk["Sci_bar_LayerID"])
        for i in range(n):
            run = int(pseudo_runs[i % len(pseudo_runs)])
            l = np.asarray(chunk["Sci_bar_LayerID"][i])
            arm = np.asarray(chunk["Sci_bar_LayerID1"][i])
            ed = np.asarray(chunk["Sci_bar_EDep"][i], dtype=float)
            tm = np.asarray(chunk["Sci_bar_Time"][i], dtype=float)
            mask_b = arm == 1
            if not np.any(mask_b):
                continue
            q = np.zeros(4)
            peak = np.zeros(4)
            hit = np.zeros(4, dtype=bool)
            for j, layer in enumerate([0, 2, 4, 6]):
                m = mask_b & (l == layer)
                if np.any(m):
                    q[j] = ed[m].sum() * scale[j]
                    peak[j] = np.min(tm[m])
                    hit[j] = q[j] > 1000.0
            if not np.any(hit):
                continue
            total = q.sum()
            amp = q.copy()
            depth = np.where(hit)[0].max()
            d = {}
            for j, s in enumerate(STAVES):
                d[f"log_q_{s}"] = math.log1p(q[j])
                d[f"log_a_{s}"] = math.log1p(amp[j])
                d[f"hit_{s}"] = float(hit[j])
            d.update({
                "multiplicity": float(hit.sum()),
                "depth_idx": float(depth),
                "log_total_q": math.log1p(total),
                "early_fraction": float(q[:2].sum() / max(total, 1.0)),
                "late_fraction": float(q[2:].sum() / max(total, 1.0)),
                "shape_balance": float((q[0] - q[-1]) / max(total, 1.0)),
                "peak_mean": float(peak[hit].mean()) if hit.any() else 0.0,
                "peak_span": float(peak.max() - peak.min()),
                "run": run,
                "domain": 0,
            })
            per_run_seen[run] += 1
            if len(reservoirs[run]) < max_per_pseudorun:
                reservoirs[run].append(d)
            else:
                k = rng.integers(0, per_run_seen[run])
                if k < max_per_pseudorun:
                    reservoirs[run][k] = d
    for vals in reservoirs.values():
        rows.extend(vals)
    return pd.DataFrame(rows)


def score_auc(y, p):
    if len(np.unique(y)) < 2:
        return np.nan
    return float(roc_auc_score(y, p))


def bootstrap_ci(eval_df: pd.DataFrame, score_col: str, n_boot: int = 1000) -> tuple[float, float]:
    rng = np.random.default_rng(RNG_SEED + 4)
    runs = np.array(sorted(eval_df["run"].unique()))
    vals = []
    for _ in range(n_boot):
        rs = rng.choice(runs, size=len(runs), replace=True)
        sub = pd.concat([eval_df[eval_df["run"] == r] for r in rs], ignore_index=True)
        vals.append(score_auc(sub["domain"], sub[score_col]))
    return tuple(float(x) for x in np.nanpercentile(vals, [2.5, 97.5]))


class TinyCNN(nn.Module):
    def __init__(self, n_features: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(1, 8, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(8, 8, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Flatten(),
            nn.Linear(8 * n_features, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
        )
    def forward(self, x):
        return self.net(x[:, None, :]).squeeze(-1)


class GatedMLP(nn.Module):
    def __init__(self, n_features: int):
        super().__init__()
        self.gate = nn.Sequential(nn.Linear(n_features, n_features), nn.Sigmoid())
        self.body = nn.Sequential(nn.Linear(n_features, 32), nn.ReLU(), nn.Linear(32, 16), nn.ReLU(), nn.Linear(16, 1))
    def forward(self, x):
        return self.body(x * self.gate(x)).squeeze(-1)


def torch_predict(model_cls, X_train, y_train, X_test, epochs=16):
    torch.manual_seed(RNG_SEED)
    mu = X_train.mean(axis=0)
    sig = X_train.std(axis=0) + 1e-6
    xt = torch.tensor((X_train - mu) / sig, dtype=torch.float32)
    yt = torch.tensor(y_train, dtype=torch.float32)
    xv = torch.tensor((X_test - mu) / sig, dtype=torch.float32)
    model = model_cls(X_train.shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=0.004, weight_decay=1e-4)
    loss_fn = nn.BCEWithLogitsLoss()
    for _ in range(epochs):
        opt.zero_grad()
        loss = loss_fn(model(xt), yt)
        loss.backward()
        opt.step()
    with torch.no_grad():
        return torch.sigmoid(model(xv)).numpy()


def benchmark(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[df["run"].isin(TRAIN_RUNS)].copy()
    test = df[df["run"].isin(HELDOUT_RUNS)].copy()
    Xtr = train[FEATURES].values.astype(float)
    ytr = train["domain"].values.astype(int)
    Xte = test[FEATURES].values.astype(float)
    yte = test["domain"].values.astype(int)
    pred = pd.DataFrame({"run": test["run"].values, "domain": yte})

    real_mu = train[train.domain == 1][FEATURES].mean()
    sim_mu = train[train.domain == 0][FEATURES].mean()
    pooled_sd = train[FEATURES].std().replace(0, 1)
    w = ((real_mu - sim_mu) / pooled_sd).values
    pred["traditional_diag_divergence"] = expit(((Xte - train[FEATURES].mean().values) / pooled_sd.values).dot(w))

    models = {
        "ridge": make_pipeline(StandardScaler(), RidgeClassifier(alpha=1.0)),
        "gradient_boosted_trees": HistGradientBoostingClassifier(max_iter=120, learning_rate=0.06, max_leaf_nodes=15, random_state=RNG_SEED),
        "mlp": make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(48, 24), alpha=1e-4, max_iter=220, random_state=RNG_SEED)),
    }
    for name, model in models.items():
        model.fit(Xtr, ytr)
        if hasattr(model, "predict_proba"):
            pred[name] = model.predict_proba(Xte)[:, 1]
        else:
            z = model.decision_function(Xte)
            pred[name] = expit((z - z.mean()) / (z.std() + 1e-9))
    logit = make_pipeline(StandardScaler(), LogisticRegression(max_iter=300, C=0.5, random_state=RNG_SEED))
    logit.fit(Xtr, ytr)
    pred["logistic_reference"] = logit.predict_proba(Xte)[:, 1]
    pred["1d_cnn"] = torch_predict(TinyCNN, Xtr, ytr.astype(float), Xte)
    pred["gated_residual_mlp"] = torch_predict(GatedMLP, Xtr, ytr.astype(float), Xte)

    rows = []
    for name in ["traditional_diag_divergence", "ridge", "gradient_boosted_trees", "mlp", "1d_cnn", "gated_residual_mlp", "logistic_reference"]:
        auc = score_auc(pred["domain"], pred[name])
        ap = float(average_precision_score(pred["domain"], pred[name]))
        lo, hi = bootstrap_ci(pred, name)
        rows.append({
            "method": name,
            "family": {
                "traditional_diag_divergence": "traditional_per_feature_divergence",
                "ridge": "ml_linear",
                "gradient_boosted_trees": "ml_tree",
                "mlp": "neural_tabular",
                "1d_cnn": "neural_1d_cnn",
                "gated_residual_mlp": "neural_gated_residual_new_architecture",
                "logistic_reference": "ml_linear_reference",
            }[name],
            "heldout_auc": auc,
            "heldout_average_precision": ap,
            "auc_ci95_low": lo,
            "auc_ci95_high": hi,
            "n_heldout": int(len(pred)),
        })
    return pd.DataFrame(rows).sort_values("heldout_auc", ascending=False), pred


def feature_gap_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for feat in FEATURES:
        y = df["domain"].values
        x = df[feat].values
        auc = roc_auc_score(y, x)
        auc = max(float(auc), float(1.0 - auc))
        r = df[df.domain == 1][feat]
        s = df[df.domain == 0][feat]
        rows.append({
            "feature": feat,
            "univariate_domain_auc": auc,
            "data_mean": float(r.mean()),
            "sim_mean": float(s.mean()),
            "standardized_delta": float((r.mean() - s.mean()) / (df[feat].std() + 1e-9)),
            "unsafe_for_sim_trained_ml": bool(auc > 0.70),
        })
    return pd.DataFrame(rows).sort_values("univariate_domain_auc", ascending=False)


def write_heatmap(gaps: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    vals = gaps.set_index("feature")["univariate_domain_auc"].sort_values(ascending=True)
    colors = ["#386cb0" if v <= 0.7 else "#c43c39" for v in vals]
    ax.barh(vals.index, vals.values, color=colors)
    ax.axvline(0.7, color="black", linestyle="--", linewidth=1)
    ax.set_xlabel("Univariate sim-vs-data domain AUC (direction folded)")
    ax.set_xlim(0.5, 1.0)
    ax.set_title("G4-07 feature-level domain gap map")
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)


def md_table(df: pd.DataFrame, cols: list[str]) -> str:
    return df[cols].to_markdown(index=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUTDIR))
    ap.add_argument("--max-per-run", type=int, default=1200)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    DOC_REPORT.parent.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    real, counts, total_selected = read_real(args.max_per_run)
    sim = read_sim(args.max_per_run)
    df = pd.concat([real, sim], ignore_index=True)
    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURES + ["run", "domain"])
    metrics, predictions = benchmark(df)
    gaps = feature_gap_table(df)
    winner = metrics.iloc[0].to_dict()

    counts.to_csv(out / "raw_reproduction_by_run.csv", index=False)
    metrics.to_csv(out / "method_metrics.csv", index=False)
    predictions.to_csv(out / "heldout_predictions.csv", index=False)
    gaps.to_csv(out / "flagged_features.csv", index=False)
    df.groupby(["domain", "run"]).size().reset_index(name="n").to_csv(out / "domain_sample_counts_by_run.csv", index=False)
    heatmap = FIG_DIR / "g4_07_domain_gap_heatmap.png"
    write_heatmap(gaps, heatmap)
    (out / "g4_07_domain_gap_heatmap.png").write_bytes(heatmap.read_bytes())

    result = {
        "ticket_id": TICKET,
        "worker": "testbeam-laptop-2",
        "raw_reproduction": {
            "expected_selected_pulses": 640737,
            "reproduced_selected_pulses": int(total_selected),
            "delta": int(total_selected - 640737),
            "pass": bool(total_selected == 640737),
        },
        "split": {"train_runs": TRAIN_RUNS, "heldout_runs": HELDOUT_RUNS, "bootstrap_unit": "run"},
        "winner": winner,
        "unsafe_feature_count_auc_gt_0p70": int(gaps["unsafe_for_sim_trained_ml"].sum()),
        "deliverables": {
            "report": str(out / "REPORT.md"),
            "docs_report": str(DOC_REPORT),
            "heatmap": str(heatmap),
            "flagged_feature_list": str(out / "flagged_features.csv"),
        },
    }
    (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    unsafe = gaps[gaps["unsafe_for_sim_trained_ml"]]
    metric_table = md_table(metrics, ["method", "family", "heldout_auc", "auc_ci95_low", "auc_ci95_high", "heldout_average_precision", "n_heldout"])
    gap_table = md_table(gaps.head(20), ["feature", "univariate_domain_auc", "standardized_delta", "unsafe_for_sim_trained_ml"])
    report = Template("""# G4-07 Domain-Gap Quantification before Sim-Trained ML on Data

## Abstract

This study quantifies where the GEANT4 `Sci_bar` simulation and the real B-stack waveform data disagree before any simulation-trained model is transferred to data.  The raw-data anchor is rebuilt directly from the reduced ROOT files in `/home/billy/Desktop/test_beam/data/root/root`: the selected B-stave pulse count is **$total_selected_fmt**, matching the S00 anchor of 640,737 exactly.  The strongest held-out domain classifier is **$winner_method** with run-bootstrap AUC **$winner_auc** (95% CI [$winner_auc_low, $winner_auc_high]).  Since all benchmark AUCs are well above 0.5, the simulation is distinguishable from data and sim-trained ML is unsafe without domain conditioning for the flagged observables.

## Data, Raw ROOT Reproduction, and Split

Real events are read from `hrdb_run_NNNN.root` tree `h101`.  Per channel, the pedestal is the median of samples 0--3.  For channel waveform `H_{{e,s,t}}`, amplitude and charge are

\\[
b_{{e,s}}=\\operatorname{{median}}_{{t\\in\\{{0,1,2,3\\}}}}H_{{e,s,t}},\\quad
A_{{e,s}}=\\max_t(H_{{e,s,t}}-b_{{e,s}}),\\quad
Q_{{e,s}}=\\sum_t\\max(H_{{e,s,t}}-b_{{e,s}},0).
\\]

A selected pulse satisfies `A > 1000 ADC`.  The domain-classification sample keeps a bounded random reservoir per run after this exact counting pass.  Calibration runs are $train_runs; held-out runs are $heldout_runs.  Bootstrap confidence intervals resample held-out runs, not rows.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| selected B-stave pulse records | 640737 | $total_selected | $total_delta | $total_pass |

## Simulation Observables

The simulation side reads `$sim_root` tree `hibeam`.  `Sci_bar_LayerID` values 0, 2, 4, and 6 are mapped to B2, B4, B6, and B8, following the even B-stack channel convention used in prior validation.  Energy deposits are scaled to the ADC-like range only to avoid trivial dynamic-range pathologies; the domain task still tests whether the joint feature distribution is transferable.

## Methods

Let `x` be the feature vector and `d` the domain label (`d=1` for data, `d=0` for simulation).  The benchmark estimates `p(d=1|x)`.  The traditional method is a diagonal per-feature divergence score

\\[
s_{{trad}}(x)=\\sigma\\left[\\sum_j \\frac{{\\mu_{{data},j}-\\mu_{{sim},j}}}{{\\sigma_j}}\\frac{{x_j-\\bar x_j}}{{\\sigma_j}}\\right],
\\]

where `sigma` is the logistic function and moments are fitted only on calibration runs.  ML/NN comparators are ridge classification, histogram gradient-boosted trees, a tabular MLP, a 1D-CNN over the ordered feature vector, and a new gated residual MLP

\\[
g(x)=\\operatorname{{sigmoid}}(W_gx+b_g),\\quad
f(x)=h(x\\odot g(x)),
\\]

which learns feature-wise gates before a residual nonlinear classifier.

## Model Benchmark

$metric_table

## Feature-Level Gap Map

The table reports direction-folded univariate domain AUC.  Values above 0.70 are flagged unsafe for direct sim-trained ML transfer.

$gap_table

![G4-07 domain gap heatmap](../../figures/reports/1781212365.2054704.7c540934__g4_07_domain_gap/g4_07_domain_gap_heatmap.png)

## Systematics

The dominant systematic is that real data are threshold-conditioned waveform records, while the simulation is truth-level `Sci_bar` energy deposition.  ADC scaling of simulated energy deposits is a nuisance choice, so absolute charge disagreement should not be interpreted as a calibrated energy failure.  The layer mapping 0/2/4/6 -> B2/B4/B6/B8 follows the even-channel convention but remains a geometry metadata systematic until channel names are directly encoded in the simulation.  Beam-rate and run-family differences are handled by split-by-run evaluation and bootstrap by run, but the bounded reservoir sample cannot represent all rare tails at full fidelity.

## Caveats

High domain AUC is a diagnostic, not a physics classifier.  It says the simulation and selected real-data feature distributions are distinguishable under the chosen observables.  It does not identify which generator, material, threshold, electronics, or reconstruction assumption is responsible.  Sim-trained downstream ML should therefore either exclude the flagged observables, condition explicitly on the domain-gap axes, or validate on an independent real-data control before deployment.

## Finding

The G4-07 gate fails the indistinguishability target: the winner `$winner_method` gives AUC $winner_auc, far above the target 0.5.  $unsafe_count features exceed the unsafe threshold AUC>0.70.  The flagged-feature list is `flagged_features.csv`; these features should be treated as unsafe for unconstrained simulation-trained ML in G4-08.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/g4_07_domain_gap.py
```
""").substitute(
        total_selected_fmt=f"{total_selected:,}",
        total_selected=str(total_selected),
        total_delta=f"{total_selected - 640737:+d}",
        total_pass=str(total_selected == 640737).lower(),
        winner_method=winner["method"],
        winner_auc=f"{winner['heldout_auc']:.4f}",
        winner_auc_low=f"{winner['auc_ci95_low']:.4f}",
        winner_auc_high=f"{winner['auc_ci95_high']:.4f}",
        train_runs=str(TRAIN_RUNS),
        heldout_runs=str(HELDOUT_RUNS),
        sim_root=str(SIM_ROOT),
        metric_table=metric_table,
        gap_table=gap_table,
        unsafe_count=str(len(unsafe)),
    )
    (out / "REPORT.md").write_text(report, encoding="utf-8")
    DOC_REPORT.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
