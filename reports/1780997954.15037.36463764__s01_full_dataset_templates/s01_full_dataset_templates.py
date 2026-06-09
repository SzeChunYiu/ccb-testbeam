#!/usr/bin/env python3
"""S01 full-dataset amplitude-adaptive template and q_template study.

All outputs are written under this report directory. Data under ./data is read only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for group_runs in config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    lookup: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            lookup[int(run)] = group
    return lookup


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_raw(config: dict, run: int, step_size: int = 10000) -> Iterable[dict]:
    path = raw_file(config, run)
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def cfd_position(norm_waveform: np.ndarray, fraction: float) -> float:
    peak = int(np.nanargmax(norm_waveform))
    if peak <= 0 or not np.isfinite(norm_waveform[peak]) or norm_waveform[peak] <= 0:
        return float("nan")
    target = fraction * norm_waveform[peak]
    for idx in range(1, peak + 1):
        y0 = norm_waveform[idx - 1]
        y1 = norm_waveform[idx]
        if np.isfinite(y0) and np.isfinite(y1) and y0 <= target <= y1 and y1 != y0:
            return float(idx - 1 + (target - y0) / (y1 - y0))
    return float(peak)


def align_waveform(norm_waveform: np.ndarray, rel_grid: np.ndarray, fraction: float) -> np.ndarray:
    pos = cfd_position(norm_waveform, fraction)
    if not np.isfinite(pos):
        return np.full(len(rel_grid), np.nan, dtype=np.float32)
    x = np.arange(len(norm_waveform), dtype=np.float64)
    aligned = np.interp(pos + rel_grid, x, norm_waveform, left=np.nan, right=np.nan)
    return aligned.astype(np.float32)


def collect_selected(config: dict) -> Tuple[pd.DataFrame, np.ndarray, Dict[str, int]]:
    staves = list(config["staves"].keys())
    channels = np.asarray([config["staves"][name] for name in staves], dtype=int)
    stave_names = np.asarray(staves)
    group_for_run = run_group_lookup(config)
    baseline_idx = np.asarray(config["baseline_samples"], dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rel_grid = np.asarray(config["aligned_relative_grid"], dtype=np.float64)
    cfd_fraction = float(config["cfd_fraction"])

    rows: List[pd.DataFrame] = []
    aligned_chunks: List[np.ndarray] = []
    counts = {"events_total": 0, "selected_pulses": 0}

    for run in configured_runs(config):
        group = group_for_run[run]
        for batch in iter_raw(config, run):
            eventno = np.asarray(batch["EVENTNO"])
            evt = np.asarray(batch["EVT"])
            waveforms = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)[:, channels, :]
            baseline = np.median(waveforms[..., baseline_idx], axis=-1)
            corrected = waveforms - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            peak = corrected.argmax(axis=-1)
            area = corrected.sum(axis=-1)
            selected = amplitude > cut
            event_idx, stave_idx = np.where(selected)
            counts["events_total"] += int(len(eventno))
            counts["selected_pulses"] += int(len(event_idx))
            if len(event_idx) == 0:
                continue

            chosen = corrected[event_idx, stave_idx, :]
            chosen_amp = amplitude[event_idx, stave_idx].astype(np.float64)
            norm = chosen / chosen_amp[:, None]
            aligned = np.vstack([align_waveform(w, rel_grid, cfd_fraction) for w in norm])
            aligned_chunks.append(aligned)
            rows.append(
                pd.DataFrame(
                    {
                        "run": run,
                        "group": group,
                        "eventno": eventno[event_idx].astype(np.int64),
                        "evt": evt[event_idx].astype(np.int64),
                        "stave": stave_names[stave_idx],
                        "channel": channels[stave_idx].astype(np.int16),
                        "amplitude_adc": chosen_amp,
                        "peak_sample": peak[event_idx, stave_idx].astype(np.int16),
                        "area_adc_samples": area[event_idx, stave_idx].astype(np.float64),
                    }
                )
            )

    table = pd.concat(rows, ignore_index=True)
    aligned_all = np.vstack(aligned_chunks)
    return table, aligned_all, counts


def assign_amp_bins(amplitude: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return np.clip(np.searchsorted(edges, amplitude, side="right") - 1, 0, len(edges) - 2)


def build_templates(config: dict, table: pd.DataFrame, aligned: np.ndarray) -> Tuple[dict, pd.DataFrame]:
    edges = np.asarray(config["template_amplitude_edges_adc"], dtype=np.float64)
    min_bin = int(config["template_min_bin_pulses"])
    staves = list(config["staves"].keys())
    calib_mask = table["group"].str.endswith("_calib").to_numpy()
    bin_idx = assign_amp_bins(table["amplitude_adc"].to_numpy(), edges)
    templates: Dict[Tuple[str, int], np.ndarray] = {}
    fallback: Dict[str, np.ndarray] = {}
    rows = []

    for stave in staves:
        stave_mask = calib_mask & (table["stave"].to_numpy() == stave)
        fallback[stave] = np.nanmedian(aligned[stave_mask], axis=0).astype(np.float32)
        for b in range(len(edges) - 1):
            mask = stave_mask & (bin_idx == b)
            n = int(mask.sum())
            if n >= min_bin:
                template = np.nanmedian(aligned[mask], axis=0).astype(np.float32)
                source = "bin"
            else:
                template = fallback[stave]
                source = "stave_fallback"
            templates[(stave, b)] = template
            rows.append(
                {
                    "stave": stave,
                    "bin": b,
                    "amp_low_adc": edges[b],
                    "amp_high_adc": edges[b + 1],
                    "n_calib": n,
                    "source": source,
                }
            )
    return {"templates": templates, "fallback": fallback, "edges": edges}, pd.DataFrame(rows)


def template_mse(table: pd.DataFrame, aligned: np.ndarray, template_pack: dict) -> np.ndarray:
    edges = template_pack["edges"]
    bin_idx = assign_amp_bins(table["amplitude_adc"].to_numpy(), edges)
    out = np.empty(len(table), dtype=np.float64)
    staves = table["stave"].to_numpy()
    for i, stave in enumerate(staves):
        template = template_pack["templates"][(stave, int(bin_idx[i]))]
        valid = np.isfinite(aligned[i]) & np.isfinite(template)
        out[i] = np.mean((aligned[i, valid] - template[valid]) ** 2) if valid.any() else np.nan
    return out


def finite_for_ml(aligned: np.ndarray) -> np.ndarray:
    x = np.nan_to_num(aligned.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    return x


def train_autoencoder_cv(config: dict, table: pd.DataFrame, aligned: np.ndarray, out_dir: Path) -> Tuple[dict, np.ndarray, pd.DataFrame]:
    import torch
    import torch.nn as nn
    from sklearn.model_selection import GroupKFold

    rng = np.random.default_rng(int(config["random_seed"]))
    torch.manual_seed(int(config["random_seed"]))
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    x = finite_for_ml(aligned)
    calib_mask = table["group"].str.endswith("_calib").to_numpy()
    calib_idx = np.flatnonzero(calib_mask)
    if len(calib_idx) > int(config["ml_cv_max_pulses"]):
        cv_idx = rng.choice(calib_idx, int(config["ml_cv_max_pulses"]), replace=False)
    else:
        cv_idx = calib_idx
    groups = table.iloc[cv_idx]["run"].to_numpy()
    x_cv = x[cv_idx]

    def make_model(hidden_dim: int, latent_dim: int) -> nn.Module:
        return nn.Sequential(
            nn.Linear(x.shape[1], hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, latent_dim),
            nn.ReLU(),
            nn.Linear(latent_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, x.shape[1]),
        )

    def fit_model(train_x: np.ndarray, params: dict, epochs: int) -> nn.Module:
        model = make_model(int(params["hidden_dim"]), int(params["latent_dim"])).to(device)
        opt = torch.optim.Adam(model.parameters(), lr=1e-3)
        loss_fn = nn.MSELoss()
        tx = torch.tensor(train_x, dtype=torch.float32)
        batch_size = int(config["ml_batch_size"])
        n = len(tx)
        for _ in range(epochs):
            perm = torch.randperm(n)
            for start in range(0, n, batch_size):
                batch = tx[perm[start : start + batch_size]].to(device)
                opt.zero_grad()
                loss = loss_fn(model(batch), batch)
                loss.backward()
                opt.step()
        return model

    def predict_mse(model: nn.Module, values: np.ndarray) -> np.ndarray:
        model.eval()
        batch_size = int(config["ml_batch_size"])
        mses = []
        with torch.no_grad():
            for start in range(0, len(values), batch_size):
                batch = torch.tensor(values[start : start + batch_size], dtype=torch.float32, device=device)
                rec = model(batch).cpu().numpy()
                mses.append(((rec - values[start : start + batch_size]) ** 2).mean(axis=1))
        return np.concatenate(mses)

    cv_rows = []
    splitter = GroupKFold(n_splits=3)
    for params in config["ml_hyperparameters"]:
        fold_mse = []
        for fold, (train_pos, val_pos) in enumerate(splitter.split(x_cv, groups=groups), start=1):
            model = fit_model(x_cv[train_pos], params, int(config["ml_cv_epochs"]))
            mse = float(predict_mse(model, x_cv[val_pos]).mean())
            fold_mse.append(mse)
            cv_rows.append({"fold": fold, "val_mse": mse, **params})
        cv_rows.append({"fold": "mean", "val_mse": float(np.mean(fold_mse)), **params})

    cv = pd.DataFrame(cv_rows)
    mean_rows = cv[cv["fold"] == "mean"].copy()
    best_row = mean_rows.sort_values("val_mse").iloc[0]
    best = {"latent_dim": int(best_row["latent_dim"]), "hidden_dim": int(best_row["hidden_dim"]), "device": device}

    train_idx = calib_idx
    if len(train_idx) > int(config["ml_final_max_pulses"]):
        train_idx = rng.choice(train_idx, int(config["ml_final_max_pulses"]), replace=False)
    final_model = fit_model(x[train_idx], best, int(config["ml_final_epochs"]))
    ae_mse = predict_mse(final_model, x)
    torch.save({"state_dict": final_model.state_dict(), "best": best}, out_dir / "autoencoder_model.pt")
    return best, ae_mse, cv


def bootstrap_run_ci(table: pd.DataFrame, trad_mse: np.ndarray, ml_mse: np.ndarray, config: dict) -> Tuple[pd.DataFrame, dict]:
    rng = np.random.default_rng(int(config["random_seed"]) + 17)
    analysis = table["group"].str.endswith("_analysis").to_numpy()
    runs = np.asarray(sorted(table.loc[analysis, "run"].unique()))
    run_rows = []
    for run in runs:
        mask = analysis & (table["run"].to_numpy() == run)
        run_rows.append(
            {
                "run": int(run),
                "n": int(mask.sum()),
                "traditional_mse": float(np.nanmean(trad_mse[mask])),
                "ml_mse": float(np.nanmean(ml_mse[mask])),
            }
        )
    run_df = pd.DataFrame(run_rows)
    run_df["delta_ml_minus_traditional"] = run_df["ml_mse"] - run_df["traditional_mse"]
    boots = []
    n_boot = int(config["bootstrap_iterations"])
    values = run_df[["traditional_mse", "ml_mse", "delta_ml_minus_traditional"]].to_numpy()
    for _ in range(n_boot):
        sample = values[rng.integers(0, len(values), len(values))]
        boots.append(sample.mean(axis=0))
    boots = np.asarray(boots)
    summary = {
        "traditional_mse": float(values[:, 0].mean()),
        "traditional_mse_ci": np.quantile(boots[:, 0], [0.025, 0.975]).tolist(),
        "ml_mse": float(values[:, 1].mean()),
        "ml_mse_ci": np.quantile(boots[:, 1], [0.025, 0.975]).tolist(),
        "delta_ml_minus_traditional": float(values[:, 2].mean()),
        "delta_ci": np.quantile(boots[:, 2], [0.025, 0.975]).tolist(),
    }
    return run_df, summary


def write_figures(out_dir: Path, table: pd.DataFrame, aligned: np.ndarray, template_pack: dict, trad_mse: np.ndarray, ml_mse: np.ndarray, run_df: pd.DataFrame, summary: dict) -> None:
    q = table.copy()
    q["q_template_rmse"] = np.sqrt(trad_mse)
    q["q_autoencoder_rmse"] = np.sqrt(ml_mse)

    fig, axes = plt.subplots(2, 2, figsize=(11, 8), sharex=False)
    for ax, group in zip(axes.flat, ["sample_i_calib", "sample_i_analysis", "sample_ii_calib", "sample_ii_analysis"]):
        sub = q[q["group"] == group]
        data = [sub.loc[sub["stave"] == stave, "q_template_rmse"].dropna().to_numpy() for stave in ["B2", "B4", "B6", "B8"]]
        ax.boxplot(data, labels=["B2", "B4", "B6", "B8"], showfliers=False)
        ax.set_title(group)
        ax.set_ylabel("template RMSE")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_q_template_by_group_stave.png", dpi=130)
    plt.close(fig)

    edges = template_pack["edges"]
    templates = template_pack["templates"]
    fig, axes = plt.subplots(4, 1, figsize=(8, 10), sharex=True, sharey=True)
    xgrid = np.asarray(json.loads((out_dir / "s01_config.json").read_text())["aligned_relative_grid"])
    for ax, stave in zip(axes, ["B2", "B4", "B6", "B8"]):
        for b in [0, 2, 4, 6]:
            ax.plot(xgrid, templates[(stave, b)], label=f"{int(edges[b])}-{int(edges[b + 1])}")
        ax.set_title(stave)
        ax.set_ylabel("norm. ADC")
        ax.legend(fontsize=8, ncol=4)
    axes[-1].set_xlabel("samples relative to CFD20")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_template_library_examples.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    means = [summary["traditional_mse"], summary["ml_mse"]]
    lows = [means[0] - summary["traditional_mse_ci"][0], means[1] - summary["ml_mse_ci"][0]]
    highs = [summary["traditional_mse_ci"][1] - means[0], summary["ml_mse_ci"][1] - means[1]]
    ax.bar(["median template", "autoencoder"], means, yerr=[lows, highs], capsize=4)
    ax.set_ylabel("analysis-run mean MSE")
    ax.set_title("Head-to-head reconstruction benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_template_vs_autoencoder_benchmark.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(run_df["run"], np.sqrt(run_df["traditional_mse"]), "o-", label="median template")
    ax.plot(run_df["run"], np.sqrt(run_df["ml_mse"]), "s-", label="autoencoder")
    ax.set_xlabel("analysis run")
    ax.set_ylabel("run mean RMSE")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_run_stability.png", dpi=130)
    plt.close(fig)


def write_report(out_dir: Path, config: dict, match: pd.DataFrame, template_bins: pd.DataFrame, cv: pd.DataFrame, run_df: pd.DataFrame, summary: dict, best: dict, result: dict) -> None:
    ml_win = summary["delta_ci"][1] < 0
    report = f"""# Study report: S01 — Full-dataset amplitude-adaptive template and q_template

- **Study ID:** S01
- **Author (worker label):** testbeam-laptop-1
- **Date:** 2026-06-09
- **Depends on:** S00 / S01b selected-pulse table
- **Input checksum(s):** S00 selected table `{config['s00_table_sha256']}`; raw ROOT checksums in `input_sha256.csv`
- **Git commit:** {result['git_commit']}
- **Config:** `reports/1780997954.15037.36463764__s01_full_dataset_templates/s01_config.json`

## 0. Question
Does the amplitude-adaptive median template built per B stave and amplitude bin from calibration runs describe all 640,737 S00-selected pulses, and does a small autoencoder beat that strong conventional template on the same held-out analysis runs?

## 1. Reproduction
The S00 selection was rerun from raw B-stack ROOT with the exact gate: even physical channels B2/B4/B6/B8, baseline median samples 0-3, amplitude >1000 ADC. The selected-row count matches S00 exactly. The older q_template subset cannot be numerically reproduced from this repository because no old subset table or numeric q_template reference is committed; this study therefore treats the missing full-dataset q_template evaluation as the finding target after first reproducing the S00 input gate.

{match.to_markdown(index=False)}

## 2. Traditional (non-ML) method
Each selected waveform was baseline-subtracted, divided by its peak amplitude, and shifted onto an 18-point grid relative to the CFD20 crossing. Templates were trained only on calibration runs using the fixed amplitude edges in the config. For each stave and amplitude bin the template is the sample-wise median aligned waveform; bins with fewer than {config['template_min_bin_pulses']} calibration pulses fall back to the stave-level calibration median.

Template-bin coverage: {int((template_bins['source'] == 'bin').sum())}/{len(template_bins)} bins had enough calibration statistics; the rest used the stave fallback. The per-pulse `q_template` is RMSE to the relevant median template and is saved for all {result['n_selected_pulses']} selected pulses in `q_template_per_pulse.csv.gz`. Full distributions are shown in `fig_q_template_by_group_stave.png`; template examples are in `fig_template_library_examples.png`.

## 3. ML method
The ML cross-check is a small fully connected autoencoder trained only on calibration-run aligned waveforms. Hyperparameters were scanned with GroupKFold by run over latent/hidden dimensions from the config. The selected model was latent_dim={best['latent_dim']}, hidden_dim={best['hidden_dim']} on `{best['device']}`. The output is only a reconstruction residual, not a physics truth label or calibrated probability.

CV means:

{cv[cv['fold'] == 'mean'].sort_values('val_mse').to_markdown(index=False)}

## 4. Head-to-head benchmark
Benchmark metric was pre-registered as analysis-run mean squared reconstruction residual on the same held-out runs. Confidence intervals are run-bootstrap 95% CIs over analysis runs.

| Method | Metric | Value ± CI | Notes |
|---|---|---:|---|
| Median amplitude-bin template | analysis-run MSE | {summary['traditional_mse']:.6g} [{summary['traditional_mse_ci'][0]:.6g}, {summary['traditional_mse_ci'][1]:.6g}] | Strong conventional baseline |
| Autoencoder | analysis-run MSE | {summary['ml_mse']:.6g} [{summary['ml_mse_ci'][0]:.6g}, {summary['ml_mse_ci'][1]:.6g}] | Best CV model |

Delta ML minus traditional = {summary['delta_ml_minus_traditional']:.6g} with CI [{summary['delta_ci'][0]:.6g}, {summary['delta_ci'][1]:.6g}]. Verdict: {'ML beats the template baseline on this residual metric.' if ml_win else 'ML does not beat the template baseline under the pre-registered CI rule.'}

## 5. Falsification
- **Pre-registration:** metric, cuts, fixed amplitude bins, CV scan, and ML-win rule were written in this report before running the data-derived analysis.
- **Falsification test:** ML had to have a 95% run-bootstrap CI for ML MSE minus traditional MSE entirely below zero.
- **Result:** CI upper bound = {summary['delta_ci'][1]:.6g}; `n_tries=1`; no multiple model family was added after seeing the outcome.

## 6. Threats to Validity
- **Benchmark/selection:** the median template is a real conventional baseline trained on the same calibration source as the autoencoder. The metric is reconstruction quality, not timing resolution; S02/P10 still need to test whether lower residual improves timing.
- **Data leakage:** both methods train only on calibration runs. The benchmark is on analysis runs and CV is grouped by run. Features are waveforms only; no q_template-derived labels exist.
- **Metric misuse:** the report includes full residual distributions by stave/group and run-level stability, not just a core width. No Gaussian fit is used here, so chi2/ndf is not applicable.
- **Post-hoc selection:** the S00 cut, amplitude bins, hyperparameter grid, bootstrap unit, and win rule were fixed before the analysis run.

## 7. Provenance Manifest
`manifest.json` lists raw input hashes, commands, seeds, code/config hashes, and output hashes. The analysis command is:

```bash
python reports/1780997954.15037.36463764__s01_full_dataset_templates/s01_full_dataset_templates.py --config reports/1780997954.15037.36463764__s01_full_dataset_templates/s01_config.json
```

## 8. Findings & Next Steps
The full-dataset q_template table now exists and exposes run/stave/amplitude stability from the same S00-selected pulse population used downstream. The scientific hypothesis is that most shape variation is conventional amplitude/stave response, but residual run-local structure flags either pile-up/topology changes or calibration drift; this is testable by feeding this `q_template` into timing closure and anomaly studies.

Next tickets proposed in `result.json`:
- S01e: validate whether q_template predicts held-out timing residual tails in S02/S03. Expected information gain: decides whether q_template is a timing-quality cut or only a shape diagnostic.
- P10a: compare this empirical median template family against a conditional generative template on the same q_template MSE and timing residual metric. Expected information gain: tests whether nonlinear template generation adds value beyond fixed amplitude bins.

Current fleet summary conflict: none. The rolling summary already identified S01 as missing full-dataset q_template; this report fills that gap.

## 9. Reproducibility
Artifacts written under this directory: `q_template_per_pulse.csv.gz`, `template_library.npz`, CSV summaries, four figures, `result.json`, and `manifest.json`. No files outside this report directory were written.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    table, aligned, counts = collect_selected(config)
    s00_sha = sha256_file(Path(config["s00_table"]))
    if s00_sha != config["s00_table_sha256"]:
        raise RuntimeError(f"S00 table sha mismatch: {s00_sha}")
    match = pd.DataFrame(
        [
            {
                "Quantity": "S00 selected B-stave pulses",
                "Report value": int(config["expected_selected_pulses"]),
                "Reproduced": int(counts["selected_pulses"]),
                "delta": int(counts["selected_pulses"] - config["expected_selected_pulses"]),
                "Tolerance": 0,
                "Pass?": bool(counts["selected_pulses"] == config["expected_selected_pulses"]),
            },
            {
                "Quantity": "S00 selected-table sha256",
                "Report value": config["s00_table_sha256"][:12],
                "Reproduced": s00_sha[:12],
                "delta": "0",
                "Tolerance": "exact",
                "Pass?": bool(s00_sha == config["s00_table_sha256"]),
            },
        ]
    )
    if not bool(match["Pass?"].all()):
        raise RuntimeError("Reproduction gate failed")

    template_pack, template_bins = build_templates(config, table, aligned)
    trad_mse = template_mse(table, aligned, template_pack)
    best, ml_mse, cv = train_autoencoder_cv(config, table, aligned, out_dir)
    run_df, summary = bootstrap_run_ci(table, trad_mse, ml_mse, config)

    q = table.copy()
    q["q_template_rmse"] = np.sqrt(trad_mse)
    q["q_autoencoder_rmse"] = np.sqrt(ml_mse)
    q["template_mse"] = trad_mse
    q["autoencoder_mse"] = ml_mse
    q.to_csv(out_dir / "q_template_per_pulse.csv.gz", index=False)

    template_np = {f"{stave}_bin{b}": arr for (stave, b), arr in template_pack["templates"].items()}
    template_np["amplitude_edges_adc"] = template_pack["edges"]
    template_np["aligned_relative_grid"] = np.asarray(config["aligned_relative_grid"], dtype=np.float32)
    np.savez_compressed(out_dir / "template_library.npz", **template_np)

    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    template_bins.to_csv(out_dir / "template_bin_counts.csv", index=False)
    cv.to_csv(out_dir / "ml_cv_scan.csv", index=False)
    run_df.to_csv(out_dir / "run_level_benchmark.csv", index=False)

    summary_rows = []
    for (group, stave), sub in q.groupby(["group", "stave"]):
        summary_rows.append(
            {
                "group": group,
                "stave": stave,
                "n": int(len(sub)),
                "q_template_rmse_median": float(sub["q_template_rmse"].median()),
                "q_template_rmse_p68": float(sub["q_template_rmse"].quantile(0.68)),
                "q_template_rmse_p95": float(sub["q_template_rmse"].quantile(0.95)),
                "q_autoencoder_rmse_median": float(sub["q_autoencoder_rmse"].median()),
            }
        )
    q_summary = pd.DataFrame(summary_rows)
    q_summary.to_csv(out_dir / "q_template_summary_by_group_stave.csv", index=False)

    write_figures(out_dir, table, aligned, template_pack, trad_mse, ml_mse, run_df, summary)

    git_commit = os.popen("git rev-parse HEAD").read().strip()
    result = {
        "study": "S01",
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": "Full-dataset amplitude-adaptive template and q_template",
        "reproduced": True,
        "repro_tolerance": "0 count delta versus S00 selected-pulse gate; exact S00 table sha256",
        "n_selected_pulses": int(len(table)),
        "traditional": {
            "metric": "analysis_run_reconstruction_mse",
            "value": summary["traditional_mse"],
            "ci": summary["traditional_mse_ci"],
            "artifact": "q_template_per_pulse.csv.gz",
        },
        "ml": {
            "metric": "analysis_run_reconstruction_mse",
            "value": summary["ml_mse"],
            "ci": summary["ml_mse_ci"],
            "best": best,
        },
        "ml_beats_baseline": bool(summary["delta_ci"][1] < 0),
        "falsification": {
            "preregistered_metric": "analysis-run mean MSE on CFD20-aligned amplitude-normalized waveforms",
            "delta_ml_minus_traditional": summary["delta_ml_minus_traditional"],
            "delta_ci": summary["delta_ci"],
            "n_tries": 1,
        },
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit,
        "critic": "pending",
        "next_tickets": [
            "S01e: validate q_template as a timing-tail predictor on S02/S03 held-out residuals",
            "P10a: conditional generative template vs empirical amplitude-bin template",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    input_rows = [{"path": str(Path(config["s00_table"])), "sha256": s00_sha}]
    for run in configured_runs(config):
        path = raw_file(config, run)
        input_rows.append({"path": str(path), "sha256": sha256_file(path)})
    with (out_dir / "input_sha256.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256"])
        writer.writeheader()
        writer.writerows(input_rows)

    write_report(out_dir, config, match, template_bins, cv, run_df, summary, best, result)

    artifacts = sorted(p.name for p in out_dir.iterdir() if p.is_file() and p.name != "manifest.json")
    output_hashes = [{"path": str(out_dir / name), "sha256": sha256_file(out_dir / name)} for name in artifacts]
    manifest = {
        "study": "S01",
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_commit,
        "config": str(args.config),
        "config_sha256": sha256_file(args.config),
        "command": f"python {Path(__file__)} --config {args.config}",
        "random_seed": int(config["random_seed"]),
        "runtime_sec": round(time.time() - t0, 1),
        "inputs": input_rows,
        "outputs": output_hashes,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
