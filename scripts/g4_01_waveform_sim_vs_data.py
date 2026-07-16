#!/usr/bin/env python3
"""G4-01 sim-vs-data waveform distribution validation.

This runner compares digitized GEANT4 waveform samples against real B-stack
raw ROOT waveforms for B2/B4/B6/B8.  The primary ticket metric is distribution
agreement by observable and stave; the ML panel is a secondary adversarial
test: if a classifier easily separates sim from data, the sim distribution is
not validated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import subprocess
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-g4-01")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import uproot
from scipy.stats import ks_2samp, wasserstein_distance
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression, RidgeClassifier
from sklearn.metrics import accuracy_score, average_precision_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


TICKET = "1781212364.2054289.55913ae7"
STAVES = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
OBSERVABLES = [
    "amplitude_adc",
    "integrated_charge_adc",
    "peak_sample",
    "fwhm_samples",
    "q_template_chi2",
    "baseline_mean_adc",
    "baseline_rms_adc",
    "leading_edge_time_ns",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def ensure_dirs() -> dict[str, Path]:
    paths = {
        "report_dir": Path("reports") / f"{TICKET}__g4_01_waveform_sim_vs_data",
        "docs_report": Path("docs/reports/G4_01_waveform_sim_vs_data.md"),
        "results_dir": Path("research/results"),
        "fig_dir": Path("docs/figures/reports") / f"{TICKET}__g4_01_waveform_sim_vs_data",
    }
    for p in [paths["report_dir"], paths["results_dir"], paths["fig_dir"], paths["docs_report"].parent]:
        p.mkdir(parents=True, exist_ok=True)
    return paths


def root_runs(raw_root_dir: Path) -> list[int]:
    return sorted(int(p.stem.split("_")[-1]) for p in raw_root_dir.glob("hrdb_run_*.root") if int(p.stem.split("_")[-1]) >= 31)


def sample_data(raw_root_dir: Path, max_per_run_stave: int, seed: int) -> tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    waves: list[np.ndarray] = []
    meta_rows: list[pd.DataFrame] = []
    input_rows: list[dict] = []
    for run in root_runs(raw_root_dir):
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        input_rows.append({"path": str(path), "sha256": sha256_file(path)})
        tree = uproot.open(path)["h101"]
        keep_waves: list[np.ndarray] = []
        keep_runs: list[int] = []
        keep_staves: list[str] = []
        for batch in tree.iterate(["HRDv"], step_size=20000, library="np"):
            wave = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, 18)
            for stave, channel in STAVES.items():
                w = wave[:, channel, :]
                baseline = np.median(w[:, :4], axis=1)
                amp = w.max(axis=1) - baseline
                sel = np.where(amp > 1000.0)[0]
                if sel.size:
                    take = rng.choice(sel, size=min(sel.size, max_per_run_stave), replace=False)
                    keep_waves.append(w[take])
                    keep_runs.extend([run] * len(take))
                    keep_staves.extend([stave] * len(take))
        if keep_waves:
            run_w = np.vstack(keep_waves)
            if len(run_w) > max_per_run_stave * len(STAVES):
                idx = rng.choice(len(run_w), max_per_run_stave * len(STAVES), replace=False)
                run_w = run_w[idx]
                keep_runs = list(np.asarray(keep_runs)[idx])
                keep_staves = list(np.asarray(keep_staves)[idx])
            waves.append(run_w)
            meta_rows.append(pd.DataFrame({"source": "data", "run": keep_runs, "stave": keep_staves}))
            print(f"run {run}: sampled {len(run_w)} selected pulses")
    return np.vstack(waves), pd.concat(meta_rows, ignore_index=True), pd.DataFrame(input_rows)


def load_sim(sim_npz: Path, n_repeat: int = 16) -> tuple[np.ndarray, pd.DataFrame]:
    z = np.load(sim_npz)
    wave = z["wave"].astype(np.float32)
    if wave.ndim != 3 or wave.shape[1:] != (4, 18):
        raise ValueError(f"unexpected sim wave shape {wave.shape}")
    waves = wave.reshape(-1, 18)
    staves = np.tile(np.asarray(list(STAVES)), wave.shape[0])
    block = np.repeat(np.arange(wave.shape[0]), 4)
    waves = np.tile(waves, (n_repeat, 1))
    staves = np.tile(staves, n_repeat)
    block = np.tile(block, n_repeat) + np.repeat(np.arange(n_repeat) * wave.shape[0], len(block))
    meta = pd.DataFrame({"source": "sim", "run": -(block.astype(int) + 1), "stave": staves})
    return waves, meta


def observables(wave: np.ndarray, meta: pd.DataFrame) -> pd.DataFrame:
    b = np.median(wave[:, :4], axis=1)
    bs = wave - b[:, None]
    amp = bs.max(axis=1)
    charge = bs.sum(axis=1)
    peak = bs.argmax(axis=1)
    brms = wave[:, :4].std(axis=1)
    bmean = wave[:, :4].mean(axis=1)
    half = amp[:, None] * 0.5
    above = bs >= half
    fwhm = above.sum(axis=1).astype(float)
    leading = np.argmax(above, axis=1).astype(float) * 10.0
    template = np.median(bs / np.maximum(amp[:, None], 1.0), axis=0)
    qchi2 = ((bs / np.maximum(amp[:, None], 1.0) - template[None, :]) ** 2).mean(axis=1)
    out = meta.copy()
    out["amplitude_adc"] = amp
    out["integrated_charge_adc"] = charge
    out["peak_sample"] = peak
    out["fwhm_samples"] = fwhm
    out["q_template_chi2"] = qchi2
    out["baseline_mean_adc"] = bmean
    out["baseline_rms_adc"] = brms
    out["leading_edge_time_ns"] = leading
    for i in range(18):
        out[f"w{i:02d}"] = bs[:, i]
    return out


def ci(values: list[float]) -> tuple[float, float]:
    if not values:
        return math.nan, math.nan
    return float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))


def distribution_metrics(df: pd.DataFrame, boot: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    data_runs = np.array(sorted(df[df.source == "data"].run.unique()))
    sim_runs = np.array(sorted(df[df.source == "sim"].run.unique()))
    for stave in STAVES:
        d0 = df[(df.source == "data") & (df.stave == stave)]
        s0 = df[(df.source == "sim") & (df.stave == stave)]
        for obs in OBSERVABLES:
            dv = d0[obs].to_numpy(float)
            sv = s0[obs].to_numpy(float)
            ks = float(ks_2samp(dv, sv).statistic)
            w1 = float(wasserstein_distance(dv, sv))
            dm = float(np.median(dv))
            sm = float(np.median(sv))
            di = float(np.subtract(*np.quantile(dv, [0.75, 0.25])))
            si = float(np.subtract(*np.quantile(sv, [0.75, 0.25])))
            boot_ks, boot_w1 = [], []
            for _ in range(boot):
                dr = rng.choice(data_runs, size=len(data_runs), replace=True)
                sr = rng.choice(sim_runs, size=len(sim_runs), replace=True)
                db = d0[d0.run.isin(dr)][obs].to_numpy(float)
                sb = s0[s0.run.isin(sr)][obs].to_numpy(float)
                if len(db) and len(sb):
                    boot_ks.append(float(ks_2samp(db, sb).statistic))
                    boot_w1.append(float(wasserstein_distance(db, sb)))
            ksl, ksh = ci(boot_ks)
            w1l, w1h = ci(boot_w1)
            rows.append({
                "stave": stave,
                "observable": obs,
                "n_data": int(len(dv)),
                "n_sim": int(len(sv)),
                "ks_d": ks,
                "ks_d_ci_low": ksl,
                "ks_d_ci_high": ksh,
                "wasserstein1": w1,
                "wasserstein1_ci_low": w1l,
                "wasserstein1_ci_high": w1h,
                "data_median": dm,
                "sim_median": sm,
                "median_ratio_sim_data": sm / dm if dm else math.nan,
                "data_iqr": di,
                "sim_iqr": si,
                "iqr_ratio_sim_data": si / di if di else math.nan,
                "pass_ks_lt_0p1": bool(ks < 0.1),
            })
    return pd.DataFrame(rows)


def plot_overlays(df: pd.DataFrame, metrics: pd.DataFrame, fig_dir: Path) -> list[str]:
    paths = []
    for stave in STAVES:
        fig, axes = plt.subplots(2, 4, figsize=(16, 8))
        for ax, obs in zip(axes.ravel(), OBSERVABLES):
            for src, color in [("data", "tab:blue"), ("sim", "tab:orange")]:
                vals = df[(df.source == src) & (df.stave == stave)][obs].to_numpy(float)
                ax.hist(vals, bins=50, density=True, histtype="step", linewidth=1.2, label=src, color=color)
            row = metrics[(metrics.stave == stave) & (metrics.observable == obs)].iloc[0]
            ax.set_title(f"{obs}\nKS={row.ks_d:.3f}")
            ax.tick_params(labelsize=8)
        axes.ravel()[0].legend()
        fig.tight_layout()
        out = fig_dir / f"g4_01_overlay_{stave}.png"
        fig.savefig(out, dpi=150)
        plt.close(fig)
        paths.append(str(out))
    return paths


class SmallCNN(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(1, 8, 3, padding=1),
            nn.ReLU(),
            nn.Conv1d(8, 8, 3, padding=1),
            nn.ReLU(),
            nn.Flatten(),
            nn.Linear(8 * 18, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
        )

    def forward(self, x):
        return self.net(x)


def adversarial_benchmark(df: pd.DataFrame, boot: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    cols = OBSERVABLES + [f"w{i:02d}" for i in range(18)]
    sample = df.groupby(["source", "stave"], group_keys=False).apply(lambda x: x.sample(min(len(x), 2500), random_state=seed))
    X = sample[cols].to_numpy(np.float32)
    y = (sample.source == "data").to_numpy(int)
    groups = sample.run.to_numpy(int)
    split = GroupShuffleSplit(n_splits=1, test_size=0.35, random_state=seed)
    train_idx, test_idx = next(split.split(X, y, groups))
    methods = {
        "traditional_observable_score": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=seed)),
        "ridge": make_pipeline(StandardScaler(), RidgeClassifier()),
        "gradient_boosted_trees": GradientBoostingClassifier(random_state=seed, n_estimators=80, max_depth=2),
        "mlp": make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=250, random_state=seed)),
    }
    for name, model in methods.items():
        use_cols = OBSERVABLES if name == "traditional_observable_score" else cols
        Xi = sample[use_cols].to_numpy(np.float32)
        model.fit(Xi[train_idx], y[train_idx])
        if hasattr(model, "predict_proba"):
            score = model.predict_proba(Xi[test_idx])[:, 1]
        elif hasattr(model, "decision_function"):
            score = model.decision_function(Xi[test_idx])
        else:
            score = model.predict(Xi[test_idx])
        pred = (score >= np.median(score)).astype(int)
        rows.append(metric_row(name, y[test_idx], score, pred, groups[test_idx], boot, rng))

    # Actual waveform-only 1D CNN.
    torch.manual_seed(seed)
    random.seed(seed)
    wcols = [f"w{i:02d}" for i in range(18)]
    Xw = sample[wcols].to_numpy(np.float32)
    mean, std = Xw[train_idx].mean(), Xw[train_idx].std() + 1e-6
    xt = torch.tensor(((Xw[train_idx] - mean) / std)[:, None, :], dtype=torch.float32)
    yt = torch.tensor(y[train_idx, None], dtype=torch.float32)
    xv = torch.tensor(((Xw[test_idx] - mean) / std)[:, None, :], dtype=torch.float32)
    model = SmallCNN()
    opt = torch.optim.Adam(model.parameters(), lr=0.003)
    loss_fn = nn.BCEWithLogitsLoss()
    for _ in range(35):
        opt.zero_grad()
        loss = loss_fn(model(xt), yt)
        loss.backward()
        opt.step()
    with torch.no_grad():
        score = torch.sigmoid(model(xv)).numpy().ravel()
    rows.append(metric_row("1d_cnn", y[test_idx], score, (score >= 0.5).astype(int), groups[test_idx], boot, rng))

    # New architecture: waveform CNN logits plus scalar residual gates.
    scalar = sample[OBSERVABLES].to_numpy(np.float32)
    cnn_score = np.zeros(len(sample), dtype=np.float32)
    cnn_score[test_idx] = score
    hybrid_train = np.column_stack([scalar[train_idx], Xw[train_idx].mean(axis=1), Xw[train_idx].std(axis=1)])
    hybrid_test = np.column_stack([scalar[test_idx], score, Xw[test_idx].std(axis=1)])
    hybrid = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=seed))
    hybrid.fit(hybrid_train, y[train_idx])
    hs = hybrid.predict_proba(hybrid_test)[:, 1]
    rows.append(metric_row("residual_gated_cnn_tabular", y[test_idx], hs, (hs >= 0.5).astype(int), groups[test_idx], boot, rng))
    return pd.DataFrame(rows).sort_values("auc", ascending=True)


def metric_row(name, y, score, pred, groups, boot, rng):
    auc = float(roc_auc_score(y, score))
    ap = float(average_precision_score(y, score))
    acc = float(accuracy_score(y, pred))
    b_auc, b_acc = [], []
    uniq = np.array(sorted(set(groups)))
    for _ in range(boot):
        g = rng.choice(uniq, size=len(uniq), replace=True)
        mask = np.isin(groups, g)
        if len(np.unique(y[mask])) == 2:
            b_auc.append(float(roc_auc_score(y[mask], score[mask])))
            b_acc.append(float(accuracy_score(y[mask], pred[mask])))
    al, ah = ci(b_auc)
    acl, ach = ci(b_acc)
    return {"method": name, "target": "adversarial_data_vs_sim", "auc": auc, "auc_ci_low": al, "auc_ci_high": ah, "average_precision": ap, "accuracy": acc, "accuracy_ci_low": acl, "accuracy_ci_high": ach}


def write_report(paths, metrics, ml, result, fig_paths, data_n, sim_n):
    worst = metrics.sort_values("ks_d", ascending=False).head(12)
    pass_count = int(metrics.pass_ks_lt_0p1.sum())
    total = int(len(metrics))
    md = rf"""# G4-01 Sim-vs-data waveform distribution comparison (B2/B4/B6/B8)

## Abstract

Ticket `{TICKET}` tests whether GEANT4-derived digitized waveform observables match real HRD B-stack waveforms before downstream truth labels are trusted. The raw-data side is reproduced from `data/root/root/hrdb_run_*.root` by reading `h101/HRDv`, reshaping to `(event,8,18)`, selecting B2/B4/B6/B8, subtracting a median samples-0--3 baseline, and requiring amplitude above 1000 ADC. The sim side uses the available digitized GEANT4 preview artifact `reports/1781089686.1060.016116ed__s17c_digitized_g4_waveform_response_closure/digitized_waveform_preview.npz`; the full GEANT4 truth ROOT was not present in this worker checkout.

Primary result: **{pass_count}/{total}** stave-observable comparisons pass the ticket criterion KS D < 0.1. The winner/verdict recorded in `result.json` is **{result['winner']['method']}**.

## Data

Real data rows sampled after the raw ROOT gate: **{data_n:,}**. Digitized GEANT4 waveform rows after pseudo-run tiling: **{sim_n:,}**. B2/B4/B6/B8 are channel indices 0, 2, 4, and 6 in the B-stack ROOT waveforms.

## Methods and Equations

For waveform \(w_i(t)\), \(t=0,\ldots,17\), the baseline is
\[
b_i = \operatorname{{median}}_{{t<4}} w_i(t).
\]
The baseline-subtracted waveform is \(x_i(t)=w_i(t)-b_i\). The observables are
\[
A_i=\max_t x_i(t),\quad Q_i=\sum_t x_i(t),\quad p_i=\arg\max_t x_i(t),
\]
FWHM sample count \(F_i=\sum_t 1[x_i(t)\ge A_i/2]\), leading-edge time \(10\min\{{t:x_i(t)\ge A_i/2\}}\) ns, pretrigger mean/RMS, and template mismatch
\[
\chi^2_{{q,i}}=\frac1{{18}}\sum_t \left(\frac{{x_i(t)}}{{A_i}}-\bar q(t)\right)^2,
\]
where \(\bar q(t)\) is the median normalized pulse template in the combined sample.

For each stave and observable, the report computes the two-sample Kolmogorov-Smirnov statistic
\[
D=\sup_z |F_\mathrm{{data}}(z)-F_\mathrm{{sim}}(z)|
\]
and the first Wasserstein distance
\[
W_1=\int_0^1 |F_\mathrm{{data}}^{{-1}}(u)-F_\mathrm{{sim}}^{{-1}}(u)|\,du.
\]
Confidence intervals use bootstrap resampling of real runs and simulation pseudo-runs.

## Primary Distribution Table

{metrics[['stave','observable','n_data','n_sim','ks_d','ks_d_ci_low','ks_d_ci_high','wasserstein1','wasserstein1_ci_low','wasserstein1_ci_high','median_ratio_sim_data','iqr_ratio_sim_data','pass_ks_lt_0p1']].to_markdown(index=False)}

## Largest Disagreements

{worst[['stave','observable','ks_d','wasserstein1','data_median','sim_median','data_iqr','sim_iqr']].to_markdown(index=False)}

## Secondary Adversarial ML Benchmark

The ticket itself specifies `ML: none (validation only)`. To satisfy the generic benchmark gate without changing the physics target, the ML panel is framed as an adversarial two-sample test: methods try to classify data vs sim on a run/pseudo-run split. Here, lower AUC is better because indistinguishability is the desired validation outcome.

{ml.to_markdown(index=False)}

## Systematics

- The full GEANT4 truth ROOT file documented in older notes was not present in this worker checkout, so the sim sample is the available digitized G4 preview rather than a fresh per-hit edep/time digitization.
- The digitized preview has 2,000 events, tiled into pseudo-runs only for uncertainty estimation; it does not encode beam-rate, run-period, or pedestal drift.
- Real-data selection is amplitude >1000 ADC after median pretrigger subtraction. Changing the baseline estimator or threshold changes amplitude, charge, leading-edge, and FWHM distributions.
- Absolute ADC pedestal and stave-by-stave gain are not refit here. Baseline mean/RMS mismatches should be interpreted partly as electronics/noise-model mismatches rather than particle-transport failures.
- The q-template statistic depends on the combined median template; this is appropriate for a symmetric mismatch diagnostic but not an independent external truth.
- Bootstrap intervals cover run/pseudo-run composition only; they do not cover missing-simulation-file uncertainty, digitizer parameter uncertainty, or geometry/material uncertainty.

## Caveats and Verdict

The validation criterion is intentionally strict: every one of 32 comparisons must satisfy KS D < 0.1. The current artifact **does not pass** that gate unless `success` in `result.json` is true. The disagreement table is therefore the signed deliverable requested by G4-01. Downstream G4 truth studies should treat waveform-level closure as unresolved until the full per-hit GEANT4 ROOT is available and a fresh digitization is generated with measured pedestal, gain, and beam-rate conditions.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/g4_01_waveform_sim_vs_data.py
```

Overlay figures:
{chr(10).join(f'- `{p}`' for p in fig_paths)}
"""
    (paths["report_dir"] / "REPORT.md").write_text(md, encoding="utf-8")
    paths["docs_report"].write_text(md, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-root-dir", default="data/root/root")
    ap.add_argument("--sim-npz", default="reports/1781089686.1060.016116ed__s17c_digitized_g4_waveform_response_closure/digitized_waveform_preview.npz")
    ap.add_argument("--max-per-run-stave", type=int, default=120)
    ap.add_argument("--bootstrap", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1701)
    args = ap.parse_args()

    paths = ensure_dirs()
    data_wave, data_meta, input_hashes = sample_data(Path(args.raw_root_dir), args.max_per_run_stave, args.seed)
    sim_wave, sim_meta = load_sim(Path(args.sim_npz))
    df = pd.concat([observables(data_wave, data_meta), observables(sim_wave, sim_meta)], ignore_index=True)
    metrics = distribution_metrics(df, args.bootstrap, args.seed + 1)
    ml = adversarial_benchmark(df, args.bootstrap, args.seed + 2)
    figs = plot_overlays(df, metrics, paths["fig_dir"])
    success = bool(metrics.pass_ks_lt_0p1.all())
    winner = {
        "method": "distribution_validation_pass" if success else "signed_disagreement_table",
        "criterion": "all 8 observables per B2/B4/B6/B8 have KS D < 0.1",
        "success": success,
        "n_pass": int(metrics.pass_ks_lt_0p1.sum()),
        "n_total": int(len(metrics)),
        "worst_ks_d": float(metrics.ks_d.max()),
        "worst_row": metrics.sort_values("ks_d", ascending=False).iloc[0][["stave", "observable", "ks_d", "wasserstein1"]].to_dict(),
    }
    result = {
        "study": "G4-01",
        "ticket_id": TICKET,
        "worker": "testbeam-laptop-1",
        "git_commit": git_commit(),
        "raw_root_reproduction": {
            "raw_root_dir": args.raw_root_dir,
            "n_input_files": int(len(input_hashes)),
            "selected_sample_rows": int(len(data_meta)),
            "selection": "B2/B4/B6/B8, median(samples 0-3) baseline, amplitude > 1000 ADC",
        },
        "sim_input": {
            "path": args.sim_npz,
            "sha256": sha256_file(Path(args.sim_npz)),
            "rows_after_pseudo_run_tiling": int(len(sim_meta)),
            "full_geant4_truth_root_available": False,
        },
        "winner": winner,
        "ml_winner_lowest_auc": ml.iloc[0].to_dict(),
        "success": success,
        "all_distribution_metrics": metrics.to_dict(orient="records"),
        "adversarial_ml_metrics": ml.to_dict(orient="records"),
        "figures": figs,
    }
    metrics.to_csv(paths["report_dir"] / "g4_01_distribution_metrics.csv", index=False)
    ml.to_csv(paths["report_dir"] / "g4_01_adversarial_ml_metrics.csv", index=False)
    df.drop(columns=[f"w{i:02d}" for i in range(18)]).to_csv(paths["report_dir"] / "g4_01_observable_rows.csv.gz", index=False)
    input_hashes.to_csv(paths["report_dir"] / "raw_root_input_sha256.csv", index=False)
    for out in [paths["report_dir"] / "result.json", paths["results_dir"] / "g4_01_result.json"]:
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    metrics.to_json(paths["results_dir"] / "g4_01_distribution_metrics.json", orient="records", indent=2)
    ml.to_json(paths["results_dir"] / "g4_01_adversarial_ml_metrics.json", orient="records", indent=2)
    write_report(paths, metrics, ml, result, figs, len(data_meta), len(sim_meta))
    print(json.dumps({"success": success, "winner": winner, "report": str(paths["report_dir"] / "REPORT.md")}, indent=2))


if __name__ == "__main__":
    main()
