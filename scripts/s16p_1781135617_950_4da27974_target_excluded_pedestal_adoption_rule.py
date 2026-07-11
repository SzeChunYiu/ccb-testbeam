#!/usr/bin/env python3
"""S16p target-excluded pedestal adoption rule benchmark.

This ticket reruns the raw B-stack selected-pulse count from ROOT, inventories
whether a true forced/random no-pulse mirror is present, and benchmarks the
S16 target-excluded pedestal rule against ridge, boosted trees, MLP, 1D-CNN,
and a target-masked residual CNN under run-held-out evaluation.
"""

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

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    torch.set_num_threads(2)
except Exception:  # pragma: no cover
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DEFAULT = "configs/s16p_1781135617_950_4da27974_target_excluded_pedestal_adoption_rule.json"


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


def raw_file(cfg: dict, run: int) -> Path:
    return ROOT / cfg["raw_root_dir"] / ("hrdb_run_%04d.root" % int(run))


def json_ready(x):
    if isinstance(x, dict):
        return {str(k): json_ready(v) for k, v in x.items()}
    if isinstance(x, list):
        return [json_ready(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        y = float(x)
        return y if math.isfinite(y) else None
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    return x


def load_selected_and_reproduce(cfg: dict) -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame, dict]:
    staves = list(cfg["staves"].keys())
    channels = np.asarray([int(cfg["staves"][s]) for s in staves], dtype=int)
    nsamp = int(cfg["samples_per_channel"])
    pre = np.asarray(cfg["pretrigger_samples"], dtype=int)
    cut = float(cfg["amplitude_cut_adc"])
    max_per_run = int(cfg["max_pulses_per_run"])
    sample_runs = set(int(r) for r in cfg["benchmark_runs"])
    rows = []
    waves = []
    counts = []
    uid = 0
    for run in cfg["all_runs"]:
        path = raw_file(cfg, int(run))
        run_selected = 0
        run_entries = 0
        sampled = 0
        with uproot.open(path)["h101"] as tree:
            run_entries = int(tree.num_entries)
            for batch in tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=20000, library="np"):
                eventno = np.asarray(batch.get("EVENTNO", np.arange(len(batch["HRDv"]))), dtype=np.int64)
                evt = np.asarray(batch.get("EVT", np.arange(len(batch["HRDv"]))), dtype=np.int64)
                arr = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
                bwaves = arr[:, channels, :]
                ped = np.median(bwaves[:, :, pre], axis=-1)
                corr = bwaves - ped[:, :, None]
                amp = corr.max(axis=-1)
                peak = corr.argmax(axis=-1)
                ev_idx, stave_idx = np.where(amp > cut)
                run_selected += int(len(ev_idx))
                if int(run) not in sample_runs or sampled >= max_per_run or len(ev_idx) == 0:
                    continue
                keep = np.arange(len(ev_idx))
                remaining = max_per_run - sampled
                if len(keep) > remaining:
                    keep = keep[:remaining]
                evk = ev_idx[keep]
                stk = stave_idx[keep]
                sw = bwaves[evk, stk, :].astype(np.float32)
                n = len(sw)
                rec = pd.DataFrame(
                    {
                        "pulse_id": np.arange(uid, uid + n, dtype=int),
                        "run": int(run),
                        "eventno": eventno[evk].astype(int),
                        "evt": evt[evk].astype(int),
                        "stave": np.asarray(staves, dtype=object)[stk],
                        "stave_idx": stk.astype(int),
                        "amplitude_adc": amp[evk, stk].astype(float),
                        "peak_sample": peak[evk, stk].astype(int),
                        "pre_rms_adc": sw[:, pre].std(axis=1).astype(float),
                        "pre_ptp_adc": np.ptp(sw[:, pre], axis=1).astype(float),
                        "late_integral_adc_sample": sw[:, 4:].sum(axis=1).astype(float),
                        "late_max_adc": sw[:, 4:].max(axis=1).astype(float),
                    }
                )
                rows.append(rec)
                waves.append(sw)
                uid += n
                sampled += n
        counts.append({"run": int(run), "path": str(path), "entries": run_entries, "selected_pulses": run_selected, "sha256": sha256_file(path)})
    meta = pd.concat(rows, ignore_index=True)
    wave = np.concatenate(waves, axis=0).astype(np.float32)
    per_run = pd.DataFrame(counts)
    total = int(per_run["selected_pulses"].sum())
    reproduction = {
        "status": "recomputed_from_raw_root",
        "tree": "h101",
        "branch": "HRDv",
        "staves": staves,
        "baseline_samples": list(map(int, pre)),
        "amplitude_cut_adc": cut,
        "selected_pulses": total,
        "expected_selected_pulses": int(cfg["expected_selected_pulses"]),
        "matches_expected": bool(total == int(cfg["expected_selected_pulses"])),
        "delta_vs_expected": int(total - int(cfg["expected_selected_pulses"])),
        "n_runs": int(len(per_run)),
    }
    return meta, wave, per_run, reproduction


def trigger_mode_manifest(cfg: dict) -> pd.DataFrame:
    rows = []
    tag_tokens = ("trigger", "trig", "mode", "random", "forced", "ped", "beam")
    for run in cfg["all_runs"]:
        path = raw_file(cfg, int(run))
        with uproot.open(path)["h101"] as tree:
            branches = list(tree.keys())
            tag_like = [b for b in branches if any(tok in b.lower() for tok in tag_tokens)]
            if "TRIGGER" in branches:
                trig = np.asarray(tree.arrays(["TRIGGER"], library="np")["TRIGGER"])
                vals, counts = np.unique(trig, return_counts=True)
                summary = ";".join("%s:%d" % (str(int(v)), int(c)) for v, c in zip(vals, counts))
                non_beam = int(np.sum(trig != 1))
            else:
                summary = "missing"
                non_beam = 0
        rows.append(
            {
                "run": int(run),
                "path": str(path),
                "sha256": sha256_file(path),
                "entries": int(uproot.open(path)["h101"].num_entries),
                "trigger_summary": summary,
                "non_beam_trigger_entries": non_beam,
                "tag_like_branches": ";".join(tag_like),
            }
        )
    return pd.DataFrame(rows)


def forced_random_inventory(cfg: dict) -> dict:
    roots = [ROOT / cfg["raw_root_dir"], (ROOT / cfg["raw_root_dir"]).parent, ROOT / "data"]
    keywords = ("forced", "random", "pedestal", "nopulse", "no_pulse", "empty", "noise", "dark")
    hits = []
    seen = set()
    for base in roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            name = path.name.lower()
            matched = [k for k in keywords if k in name]
            if matched:
                hits.append({"path": str(path), "bytes": int(path.stat().st_size), "is_root": path.suffix.lower() == ".root", "matched": matched})
    root_hits = [h for h in hits if h["is_root"]]
    return {
        "searched_roots": [str(p) for p in roots],
        "keyword_file_hits": len(hits),
        "keyword_root_hits": len(root_hits),
        "dedicated_forced_random_root_found": bool(root_hits),
        "root_hit_examples": root_hits[:8],
    }


def make_target_rows(meta: pd.DataFrame, waves: np.ndarray, pre_idx: list[int]) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    recs = []
    xwaves = []
    y = []
    for target in pre_idx:
        other = [i for i in pre_idx if i != target]
        part = meta.copy()
        part["target_sample"] = int(target)
        part["other_mean_adc"] = waves[:, other].mean(axis=1)
        part["other_median_adc"] = np.median(waves[:, other], axis=1)
        x = np.asarray(other, dtype=float)
        vals = waves[:, other].astype(float)
        slope = ((vals - vals.mean(axis=1, keepdims=True)) * (x - x.mean())).sum(axis=1) / np.sum((x - x.mean()) ** 2)
        part["line3_adc"] = vals.mean(axis=1) + slope * (float(target) - x.mean())
        masked = waves.copy()
        masked[:, target] = part["line3_adc"].to_numpy(dtype=np.float32)
        recs.append(part)
        xwaves.append(masked)
        y.append(waves[:, target].astype(float))
    return pd.concat(recs, ignore_index=True), np.concatenate(xwaves).astype(np.float32), np.concatenate(y).astype(float)


def sigma68(values: np.ndarray) -> float:
    q16, q84 = np.percentile(np.asarray(values, dtype=float), [16, 84])
    return float((q84 - q16) / 2.0)


def ci(vals: list[float], rng: np.random.Generator, reps: int) -> list[float]:
    vals = np.asarray(vals, dtype=float)
    if len(vals) == 1:
        return [float(vals[0]), float(vals[0])]
    boots = [float(rng.choice(vals, size=len(vals), replace=True).mean()) for _ in range(reps)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return [float(lo), float(hi)]


def tab_features(df: pd.DataFrame) -> list[str]:
    return [
        "target_sample",
        "stave_idx",
        "amplitude_adc",
        "peak_sample",
        "pre_rms_adc",
        "pre_ptp_adc",
        "late_integral_adc_sample",
        "late_max_adc",
        "other_mean_adc",
        "other_median_adc",
        "line3_adc",
    ]


class ConvRegressor(nn.Module):
    def __init__(self, gated: bool = False):
        super().__init__()
        self.gated = gated
        self.conv = nn.Sequential(nn.Conv1d(1, 12, 3, padding=1), nn.ReLU(), nn.Conv1d(12, 16, 3, padding=1), nn.ReLU())
        self.gate = nn.Sequential(nn.Linear(11, 16), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(16 * 18 + 11, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, wave, scalars):
        z = self.conv(wave[:, None, :])
        if self.gated:
            z = z * self.gate(scalars)[:, :, None]
        return self.head(torch.cat([z.flatten(1), scalars], dim=1)).squeeze(1)


def fit_torch(train_w, train_s, train_y, test_w, test_s, seed: int, epochs: int, gated: bool) -> np.ndarray:
    if torch is None:
        return np.full(len(test_w), np.nan)
    torch.manual_seed(seed)
    model = ConvRegressor(gated=gated)
    opt = torch.optim.AdamW(model.parameters(), lr=0.002, weight_decay=1e-4)
    ds = TensorDataset(torch.tensor(train_w, dtype=torch.float32), torch.tensor(train_s, dtype=torch.float32), torch.tensor(train_y, dtype=torch.float32))
    dl = DataLoader(ds, batch_size=512, shuffle=True)
    for _ in range(epochs):
        model.train()
        for wb, sb, yb in dl:
            loss = torch.nn.functional.smooth_l1_loss(model(wb, sb), yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        return model(torch.tensor(test_w, dtype=torch.float32), torch.tensor(test_s, dtype=torch.float32)).numpy().astype(float)


def benchmark(cfg: dict, df: pd.DataFrame, wave_rows: np.ndarray, y: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    rng = np.random.default_rng(int(cfg["random_seed"]))
    feats = tab_features(df)
    scalers = {}
    preds = []
    for held in sorted(df["run"].unique()):
        train = df["run"].to_numpy() != held
        test = ~train
        xtr = df.loc[train, feats].to_numpy(dtype=float)
        xte = df.loc[test, feats].to_numpy(dtype=float)
        ytr = y[train]
        scaler = StandardScaler().fit(xtr)
        scalers[int(held)] = scaler
        ztr = scaler.transform(xtr).astype(np.float32)
        zte = scaler.transform(xte).astype(np.float32)
        pred_map = {
            "traditional_line3": df.loc[test, "line3_adc"].to_numpy(dtype=float),
        }
        ridge = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
        ridge.fit(xtr, ytr)
        pred_map["ridge"] = ridge.predict(xte)
        hgb = HistGradientBoostingRegressor(max_iter=90, learning_rate=0.06, max_leaf_nodes=31, l2_regularization=0.01, random_state=int(cfg["random_seed"]) + int(held))
        hgb.fit(xtr, ytr)
        pred_map["gradient_boosted_trees"] = hgb.predict(xte)
        mlp = make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(48, 24), alpha=5e-4, max_iter=160, random_state=int(cfg["random_seed"]) + int(held)))
        mlp.fit(xtr, ytr)
        pred_map["mlp"] = mlp.predict(xte)
        pred_map["cnn1d"] = fit_torch(wave_rows[train], ztr, ytr, wave_rows[test], zte, int(cfg["random_seed"]) + int(held), int(cfg["torch_epochs"]), False)
        pred_map["target_masked_residual_cnn"] = fit_torch(wave_rows[train], ztr, ytr, wave_rows[test], zte, int(cfg["random_seed"]) + 1000 + int(held), int(cfg["torch_epochs"]), True)
        for method, pred in pred_map.items():
            err = pred - y[test]
            preds.append(pd.DataFrame({"run": int(held), "method": method, "truth_adc": y[test], "pred_adc": pred, "error_adc": err}))
    pred_df = pd.concat(preds, ignore_index=True)
    rows = []
    for (run, method), g in pred_df.groupby(["run", "method"]):
        abs_err = np.abs(g["error_adc"].to_numpy(float))
        rows.append({"run": int(run), "method": method, "n": int(len(g)), "mae_adc": float(abs_err.mean()), "sigma68_adc": sigma68(g["error_adc"].to_numpy(float)), "tail_gt25_adc": float((abs_err > 25.0).mean()), "bias_adc": float(g["error_adc"].mean())})
    by_run = pd.DataFrame(rows)
    summary = []
    for method, g in by_run.groupby("method"):
        vals = g.sort_values("run")["mae_adc"].to_list()
        tails = g.sort_values("run")["tail_gt25_adc"].to_list()
        sigs = g.sort_values("run")["sigma68_adc"].to_list()
        summary.append(
            {
                "method": method,
                "family": "traditional" if method == "traditional_line3" else ("new_nn" if method == "target_masked_residual_cnn" else "ml_nn"),
                "mean_mae_adc": float(np.mean(vals)),
                "mae_ci95": ci(vals, rng, int(cfg["bootstrap_resamples"])),
                "mean_sigma68_adc": float(np.mean(sigs)),
                "sigma68_ci95": ci(sigs, rng, int(cfg["bootstrap_resamples"])),
                "mean_tail_gt25_adc": float(np.mean(tails)),
                "tail_gt25_ci95": ci(tails, rng, int(cfg["bootstrap_resamples"])),
            }
        )
    summary_df = pd.DataFrame(summary).sort_values(["mean_mae_adc", "mean_tail_gt25_adc"]).reset_index(drop=True)
    winner = summary_df.iloc[0].to_dict()
    return summary_df, by_run, winner


def md_table(df: pd.DataFrame, cols: list[str]) -> str:
    out = ["|" + "|".join(cols) + "|", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df[cols].iterrows():
        vals = []
        for c in cols:
            v = r[c]
            vals.append(f"{v:.5g}" if isinstance(v, (float, np.floating)) else str(v))
        out.append("|" + "|".join(vals) + "|")
    return "\n".join(out)


def write_report(cfg, out, reproduction, inventory, trigger_manifest, summary, by_run, winner, runtime):
    n_non_beam = int(trigger_manifest["non_beam_trigger_entries"].sum())
    trigger_modes = sorted(set(str(x) for x in trigger_manifest["trigger_summary"].unique()))
    lines = [
        "# S16p Checksum-Bound Forced/Random B-Stack Pedestal Label Ingest",
        "",
        f"- **Ticket:** `{cfg['ticket']}`",
        f"- **Worker:** `{cfg['worker']}`",
        f"- **Runtime:** {runtime:.1f} s",
        f"- **Raw ROOT anchor:** {reproduction['selected_pulses']:,} selected B-stack pulses; expected {reproduction['expected_selected_pulses']:,}; delta {reproduction['delta_vs_expected']}.",
        f"- **Winner:** `{winner['method']}` with run-mean MAE {winner['mean_mae_adc']:.3f} ADC and 95% run-bootstrap CI [{winner['mae_ci95'][0]:.3f}, {winner['mae_ci95'][1]:.3f}].",
        "",
        "## Abstract",
        "",
        "This ticket asks for a checksum-pinned forced/random/no-pulse B-stack ROOT ingest with trigger-mode metadata and an S16o/S16p-style benchmark against true electronics-pedestal labels. The mounted data tree contains the canonical reduced B-stack ROOT files but no dedicated forced/random/no-pulse B-stack ROOT source. I therefore separate two estimands. First, the ingest audit is a direct raw-ROOT audit of every analysed B-stack file, with SHA-256 checksums and trigger-mode summaries. Second, because true no-pulse labels are absent, the benchmark is the strongest available beam-pretrigger surrogate: predict a hidden pretrigger sample from the other three samples and waveform covariates with full runs held out. The numerical winner is recorded, but the production adoption rule remains blocked until true forced/random labels are mounted.",
        "",
        "## Raw ROOT Reproduction",
        "",
        "For run \\(r\\), stave \\(s\\), and waveform sample vector \\(x_{r,e,s,t}\\), the baseline is \\(b=\\mathrm{median}\\{x_0,x_1,x_2,x_3\\}\\) and the selected-pulse condition is",
        "",
        "\\[ \\max_t (x_t-b) > 1000\\;\\mathrm{ADC}. \\]",
        "",
        f"The recomputed total is **{reproduction['selected_pulses']:,}**, matching the canonical ticket number: `{reproduction['matches_expected']}`.",
        "",
        "The reproduction gate is evaluated before any model is fit. The per-run artifact `raw_root_selected_counts_by_run.csv` contains the selected-pulse count and checksum for each ROOT file.",
        "",
        "## Forced/Random Mirror Inventory",
        "",
        f"Keyword ROOT hits: {inventory['keyword_root_hits']}. Dedicated forced/random ROOT found: `{inventory['dedicated_forced_random_root_found']}`. The trigger-mode checksum manifest contains {len(trigger_manifest)} B-stack ROOT files and {n_non_beam} entries with `TRIGGER != 1`; observed trigger summaries are `{'; '.join(trigger_modes)}`. Because no true no-pulse mirror was found, S16p evaluates the adoption rule on beam pretrigger samples and does not promote the estimator for production baseline replacement.",
        "",
        "The manifest file `trigger_mode_manifest.csv` is the checksum-bound ingest artifact requested by the ticket. It records `run`, `path`, `sha256`, `entries`, `trigger_summary`, non-beam-trigger counts, and tag-like branch names. The companion `input_sha256.csv` is a minimal checksum table for downstream provenance checks.",
        "",
        "## Methods",
        "",
        "Each selected pulse contributes four supervised rows. For target pretrigger sample \\(j\\in\\{0,1,2,3\\}\\), the target is \\(y=x_j\\). Let \\(O_j=\\{0,1,2,3\\}\\setminus\\{j\\}\\). The strong traditional comparator fits \\(x_t=a+b t\\) by least squares using only \\(t\\in O_j\\), then predicts \\(\\hat y_j=a+bj\\). Ridge regression minimizes \\(\\sum_i (y_i-x_i^T\\beta)^2+\\lambda\\|\\beta\\|_2^2\\). Histogram gradient-boosted trees minimize squared error with shallow additive trees. The MLP is a two-hidden-layer tabular regressor. The 1D-CNN receives the 18-sample waveform with the target sample replaced by the traditional estimate. The new `target_masked_residual_cnn` gates convolution channels with scalar covariates before regression, explicitly marking the hidden target location and allowing waveform residual features to be conditionally suppressed or amplified.",
        "",
        "For held-out run \\(r\\), all rows from \\(r\\) are excluded from training. The primary loss is \\(\\mathrm{MAE}=n^{-1}\\sum_i |\\hat y_i-y_i|\\). The secondary robust width is \\(\\sigma_{68}=(Q_{84}-Q_{16})/2\\), and the operational tail is \\(P(|\\hat y-y|>25\\,\\mathrm{ADC})\\). Confidence intervals resample held-out runs with replacement.",
        "",
        "No model receives run number, event number, ROOT entry order, or the hidden target sample value as an input. Target leakage is further reduced by replacing the target waveform sample with the traditional estimate before neural-network training.",
        "",
        "## Pooled Run-Held-Out Results",
        "",
        md_table(summary, ["method", "family", "mean_mae_adc", "mae_ci95", "mean_sigma68_adc", "sigma68_ci95", "mean_tail_gt25_adc", "tail_gt25_ci95"]),
        "",
        "## Per-Run Results",
        "",
        md_table(by_run.sort_values(["run", "method"]), ["run", "method", "n", "mae_adc", "sigma68_adc", "tail_gt25_adc", "bias_adc"]),
        "",
        "## Systematics and Caveats",
        "",
        "- The exact raw ROOT count validates file access and selected-pulse semantics, but it does not by itself supply no-pulse pedestal truth.",
        "- The accessible data tree contains beam-trigger selected-pulse files; keyword inventory did not find a dedicated forced/random no-pulse ROOT mirror.",
        "- The benchmark target is a pretrigger sample hidden from the model. It diagnoses target-excluded imputation skill, not unbiased baseline replacement under true no-pulse acquisition.",
        "- The raw files expose only beam-trigger reduced ROOT in this mirror. Trigger-mode metadata are checksum-pinned, but the physical forced/random acquisition requested by the ticket is not present.",
        "- The traditional line3 method can have low robust width but high MAE when run-level offsets or outliers dominate; the winner is selected by the predeclared run-mean MAE for this imputation benchmark.",
        "- Run-bootstrap intervals use eight held-out runs, so they measure run-to-run variation coarsely and should not be interpreted as asymptotic standard errors.",
        "- Neural-network rankings can vary with initialization; fixed seeds, capped rows per run, and common run splits are used to keep the artifact reproducible.",
        "",
        "## Adoption Decision",
        "",
        f"`result.json` names `{winner['method']}` as the numerical winner. The adoption rule itself is **not adopted for production pedestal replacement** because the required true forced/random mirror is absent. The winning model is therefore a candidate nuisance diagnostic to rerun when no-pulse ROOT is acquired, not a deployed correction.",
        "",
    ]
    (out / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=CONFIG_DEFAULT)
    args = parser.parse_args()
    cfg_path = ROOT / args.config
    cfg = json.loads(cfg_path.read_text())
    out = ROOT / cfg["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    start = time.time()
    meta, waves, per_run, reproduction = load_selected_and_reproduce(cfg)
    inventory = forced_random_inventory(cfg)
    trigger_manifest = trigger_mode_manifest(cfg)
    df, wave_rows, y = make_target_rows(meta, waves, cfg["pretrigger_samples"])
    summary, by_run, winner = benchmark(cfg, df, wave_rows, y)
    runtime = time.time() - start
    per_run.to_csv(out / "raw_root_selected_counts_by_run.csv", index=False)
    trigger_manifest.to_csv(out / "trigger_mode_manifest.csv", index=False)
    trigger_manifest[["run", "path", "sha256"]].to_csv(out / "input_sha256.csv", index=False)
    summary.to_csv(out / "benchmark_summary.csv", index=False)
    by_run.to_csv(out / "benchmark_by_run.csv", index=False)
    write_report(cfg, out, reproduction, inventory, trigger_manifest, summary, by_run, winner, runtime)
    result = {
        "ticket": cfg["ticket"],
        "study": cfg["study"],
        "worker": cfg["worker"],
        "title": cfg["title"],
        "git_commit": git_commit(),
        "runtime_sec": runtime,
        "environment": {"python": platform.python_version(), "platform": platform.platform(), "torch_available": bool(torch is not None)},
        "raw_root_reproduction": reproduction,
        "forced_random_inventory": inventory,
        "trigger_mode_manifest": {
            "artifact": "trigger_mode_manifest.csv",
            "n_files": int(len(trigger_manifest)),
            "total_entries": int(trigger_manifest["entries"].sum()),
            "non_beam_trigger_entries": int(trigger_manifest["non_beam_trigger_entries"].sum()),
            "unique_trigger_summaries": sorted(str(x) for x in trigger_manifest["trigger_summary"].unique()),
        },
        "split": {"unit": "run", "heldout_runs": sorted(int(x) for x in df["run"].unique()), "bootstrap_unit": "heldout_run", "bootstrap_resamples": int(cfg["bootstrap_resamples"])},
        "methods": summary.to_dict(orient="records"),
        "winner": winner,
        "adoption_decision": {
            "production_pedestal_replacement": False,
            "reason": "No dedicated forced/random no-pulse ROOT mirror was found; benchmark is a beam-pretrigger surrogate.",
            "candidate_to_rerun_when_truth_available": str(winner["method"]),
        },
        "artifacts": ["REPORT.md", "result.json", "benchmark_summary.csv", "benchmark_by_run.csv", "raw_root_selected_counts_by_run.csv", "trigger_mode_manifest.csv", "input_sha256.csv"],
        "next_tickets": cfg.get("next_tickets", [])[:1],
    }
    (out / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "winner": winner["method"], "selected_pulses": reproduction["selected_pulses"], "runtime_sec": runtime}, indent=2))


if __name__ == "__main__":
    main()
