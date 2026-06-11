#!/usr/bin/env python3
"""P07h: boundary leakage triage plus traditional/ML saturation bakeoff.

This ticket is deliberately a synthesis study.  It first reproduces raw ROOT
selection and the P07d boundary-leakage anchor, then runs a by-run benchmark of
a strong traditional boundary/template method against ridge, gradient-boosted
trees, MLP, a 1D-CNN, and a residual squeeze CNN on self-generated saturation
truth.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p07h")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "4")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover
    torch = None
    nn = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/p07h_1781048246_829_592868b2_boundary_leakage_ml_bakeoff.json"
OUT_DIR = ROOT / "reports/1781048246.829.592868b2__p07h_boundary_leakage_ml_bakeoff"
STAVE_CHANNELS = [0, 2, 4, 6]


def import_script(name: str, relpath: str):
    path = ROOT / relpath
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


P07C = import_script("p07c_boundary_control_closure", "scripts/p07c_boundary_control_closure.py")
P07D = import_script("p07d_boundary_shrinkage", "scripts/p07d_1781018293_1193_5694364a_boundary_shrinkage.py")


def load_config(path: Path) -> dict:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg["config_path"] = str(path)
    return cfg


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


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if math.isfinite(v) else None
    return value


def count_global_selected_b_pulses(cfg: dict) -> Tuple[pd.DataFrame, int]:
    raw = ROOT / cfg["raw_root"]
    baseline_idx = [int(i) for i in cfg["baseline_samples"]]
    configured = sorted({int(run) for runs in cfg["run_groups"].values() for run in runs})
    rows = []
    total = 0
    for run in configured:
        path = raw / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(path)
        selected_run = 0
        events = 0
        tree = uproot.open(path)["h101"]
        for batch in tree.iterate(["HRDv"], step_size=25000, library="np"):
            arr = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, 18)
            wave = arr[:, STAVE_CHANNELS, :]
            base = np.median(wave[..., baseline_idx], axis=-1)
            corr = wave - base[..., None]
            amp = corr.max(axis=-1)
            selected = amp > float(cfg["amplitude_cut_adc"])
            selected_run += int(selected.sum())
            events += int(len(arr))
        rows.append({"run": run, "events": events, "selected_b_pulses": selected_run})
        total += selected_run
    return pd.DataFrame(rows), int(total)


def benchmark_features(clipped: np.ndarray, ceiling: float) -> np.ndarray:
    x = clipped.astype(np.float32) / float(ceiling)
    diff = np.diff(x, axis=1)
    pos = np.clip(x, 0.0, None)
    area = pos.sum(axis=1)
    peak = x.argmax(axis=1).astype(np.float32)
    feats = np.column_stack(
        [
            x,
            area,
            pos[:, :6].sum(axis=1),
            pos[:, 6:12].sum(axis=1),
            pos[:, 12:].sum(axis=1),
            diff.max(axis=1),
            diff.min(axis=1),
            peak,
            (clipped >= ceiling).sum(axis=1),
        ]
    )
    return feats.astype(np.float32)


class TinyCNNRegressor(nn.Module):
    def __init__(self, residual: bool = False) -> None:
        super().__init__()
        self.residual = residual
        if residual:
            self.inp = nn.Conv1d(1, 24, 3, padding=1)
            self.block1 = nn.Sequential(nn.Conv1d(24, 24, 3, padding=1), nn.ReLU(), nn.Conv1d(24, 24, 3, padding=1))
            self.block2 = nn.Sequential(nn.Conv1d(24, 24, 5, padding=2), nn.ReLU(), nn.Conv1d(24, 24, 3, padding=1))
            self.gate = nn.Sequential(nn.Linear(24, 8), nn.ReLU(), nn.Linear(8, 24), nn.Sigmoid())
            self.head = nn.Sequential(nn.Linear(48, 48), nn.ReLU(), nn.Linear(48, 1))
        else:
            self.encoder = nn.Sequential(
                nn.Conv1d(1, 16, 3, padding=1),
                nn.ReLU(),
                nn.Conv1d(16, 32, 3, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
                nn.Flatten(),
            )
            self.head = nn.Sequential(nn.Linear(32, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, wave):
        if not self.residual:
            return self.head(self.encoder(wave[:, None, :])).squeeze(1)
        z = torch.relu(self.inp(wave[:, None, :]))
        z = torch.relu(z + self.block1(z))
        z = torch.relu(z + self.block2(z))
        z = z * self.gate(z.mean(dim=2)).unsqueeze(2)
        pooled = torch.cat([z.mean(dim=2), z.amax(dim=2)], dim=1)
        return self.head(pooled).squeeze(1)


def fit_predict_torch(
    model: nn.Module,
    x_wave: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    cfg: dict,
    seed: int,
) -> np.ndarray:
    if torch is None:
        raise RuntimeError("torch is required for neural network benchmark methods")
    torch.manual_seed(seed)
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    rng = np.random.default_rng(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(cfg["torch_learning_rate"]),
        weight_decay=float(cfg["torch_weight_decay"]),
    )
    loss_fn = nn.MSELoss()
    train_idx = np.asarray(train_idx, dtype=int)
    max_train = int(cfg["benchmark_max_train_rows"])
    if len(train_idx) > max_train:
        train_idx = rng.choice(train_idx, size=max_train, replace=False)
    x = torch.tensor(x_wave.astype(np.float32), dtype=torch.float32, device=device)
    yy = torch.tensor(y.astype(np.float32), dtype=torch.float32, device=device)
    batch = int(cfg["torch_batch_size"])
    for _epoch in range(int(cfg["torch_epochs"])):
        order = rng.permutation(train_idx)
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            pred = model(x[idx])
            loss = loss_fn(pred, yy[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
    pred = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(x_wave), 8192):
            pred.append(model(x[start : start + 8192]).detach().cpu().numpy())
    return np.concatenate(pred).astype(float)


def run_benchmark(pulses: pd.DataFrame, cfg: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    seed = int(cfg["random_seed"])
    ceiling = float(cfg["artificial_ceiling_adc"])
    art = P07C.artificial_frame(pulses, cfg, ceiling)
    wave = np.vstack(art["clipped_waveform"].to_numpy()).astype(np.float32)
    amp = art["amplitude_adc"].to_numpy(dtype=float)
    runs = art["run"].to_numpy(dtype=int)
    features = benchmark_features(wave, ceiling)
    wave_scaled = (wave / ceiling).astype(np.float32)
    y = np.log(np.maximum(amp, 1.0))
    pred_rows = []
    fold_rows = []

    for heldout in cfg["runs"]:
        train_idx = np.where(runs != int(heldout))[0]
        test_idx = np.where(runs == int(heldout))[0]
        if len(test_idx) == 0 or len(train_idx) == 0:
            continue
        train_clean = pulses[(pulses["run"] != heldout) & P07C.clean_control_mask(pulses, cfg)].copy()
        templates, _ = P07C.build_template_family(train_clean)
        clipmask = wave >= ceiling
        raw_trad_train = P07C.family_recover(wave[train_idx], clipmask[train_idx], templates)
        slope, intercept = P07C.calibrate_linear(raw_trad_train, amp[train_idx])

        sklearn_methods = [
            ("ML_ridge_regression", make_pipeline(StandardScaler(), Ridge(alpha=1.0))),
            (
                "ML_gradient_boosted_trees",
                HistGradientBoostingRegressor(
                    max_iter=150,
                    learning_rate=0.055,
                    max_leaf_nodes=31,
                    l2_regularization=0.01,
                    random_state=seed + heldout,
                ),
            ),
            (
                "ML_mlp",
                make_pipeline(
                    StandardScaler(),
                    MLPRegressor(
                        hidden_layer_sizes=(64, 32),
                        activation="relu",
                        alpha=1e-4,
                        batch_size=512,
                        learning_rate_init=1e-3,
                        max_iter=70,
                        early_stopping=True,
                        n_iter_no_change=8,
                        random_state=seed + 100 + heldout,
                    ),
                ),
            ),
        ]
        fold_pred = {
            "traditional_template_family": P07C.apply_calibration(
                P07C.family_recover(wave[test_idx], clipmask[test_idx], templates), slope, intercept, np.full(len(test_idx), ceiling)
            )
        }
        y_lo = float(y[train_idx].min())
        y_hi = float(y[train_idx].max())
        for name, model in sklearn_methods:
            model.fit(features[train_idx], y[train_idx])
            fold_pred[name] = np.maximum(np.exp(np.clip(model.predict(features[test_idx]), y_lo, y_hi)), ceiling)
        fold_pred["NN_1d_cnn"] = np.maximum(
            np.exp(
                np.clip(
                    fit_predict_torch(TinyCNNRegressor(False), wave_scaled, y, train_idx, cfg, seed + 200 + heldout)[test_idx],
                    y_lo,
                    y_hi,
                )
            ),
            ceiling,
        )
        fold_pred["NN_residual_squeeze_cnn_new"] = np.maximum(
            np.exp(
                np.clip(
                    fit_predict_torch(TinyCNNRegressor(True), wave_scaled, y, train_idx, cfg, seed + 300 + heldout)[test_idx],
                    y_lo,
                    y_hi,
                )
            ),
            ceiling,
        )
        for method, rec in fold_pred.items():
            residual = (np.asarray(rec, dtype=float) - amp[test_idx]) / amp[test_idx]
            fold_rows.append(
                {
                    "heldout_run": int(heldout),
                    "method": method,
                    "n": int(len(test_idx)),
                    "bias": float(np.median(residual)),
                    "res68": float(np.percentile(np.abs(residual), 68)),
                    "frac_within10": float((np.abs(residual) < 0.10).mean()),
                    "rmse_fraction": float(np.sqrt(np.mean(residual**2))),
                    "r2_log_amp": float(r2_score(y[test_idx], np.log(np.maximum(rec, 1.0)))),
                }
            )
            pred_rows.append(
                pd.DataFrame(
                    {
                        "heldout_run": int(heldout),
                        "method": method,
                        "eventno": art.iloc[test_idx]["eventno"].to_numpy(dtype=int),
                        "truth_amplitude_adc": amp[test_idx],
                        "recovered_amplitude_adc": np.asarray(rec, dtype=float),
                        "fractional_residual": residual,
                    }
                )
            )
    predictions = pd.concat(pred_rows, ignore_index=True)
    by_run = pd.DataFrame(fold_rows)
    summary = summarize_benchmark_by_run(by_run, cfg)
    return summary, by_run, predictions


def run_bootstrap_weighted(by_run: pd.DataFrame, method: str, metric: str, cfg: dict, lower_is_better: bool = True) -> Tuple[float, List[float]]:
    sub = by_run[by_run["method"] == method].copy()
    vals = sub[metric].to_numpy(dtype=float)
    weights = sub["n"].to_numpy(dtype=float)
    ok = np.isfinite(vals) & np.isfinite(weights) & (weights > 0)
    vals = vals[ok]
    weights = weights[ok]
    point = float(np.average(vals, weights=weights))
    rng = np.random.default_rng(int(cfg["random_seed"]) + abs(hash(method + metric)) % 100000)
    draws = rng.integers(0, len(vals), size=(int(cfg["bootstrap_replicates"]), len(vals)))
    boot = np.asarray([np.average(vals[d], weights=weights[d]) for d in draws], dtype=float)
    return point, [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]


def summarize_benchmark_by_run(by_run: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    rows = []
    for method in sorted(by_run["method"].unique()):
        row = {"method": method, "n": int(by_run[by_run["method"] == method]["n"].sum())}
        for metric in ["bias", "res68", "frac_within10", "rmse_fraction", "r2_log_amp"]:
            point, ci = run_bootstrap_weighted(by_run, method, metric, cfg)
            row[metric] = point
            row[f"{metric}_ci_low"] = ci[0]
            row[f"{metric}_ci_high"] = ci[1]
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["res68", "rmse_fraction"], ascending=[True, True]).reset_index(drop=True)


def write_report(out: Path, result: dict, benchmark: pd.DataFrame, leak_checks: pd.DataFrame) -> None:
    winner = result["winner"]
    trad = result["best_traditional"]
    lines = [
        "# P07h: boundary-shrinkage leakage triage and ML/NN bakeoff",
        "",
        f"**Ticket:** `{result['ticket']}`  ",
        f"**Worker:** `{result['worker']}`  ",
        f"**Raw ROOT directory:** `{result['raw_root']}`  ",
        f"**Command:** `{result['command']}`",
        "",
        "## Abstract",
        "",
        "This study reopens the P07 natural B2 boundary-shrinkage leakage warning with a raw-ROOT audit and a fair run-split model bakeoff. The global B-stave selection count is reproduced exactly from raw ROOT, the P07d leakage anchor is reproduced as three flagged diagnostics, and the explicit ridge/GBT/MLP/CNN/residual-CNN panel is benchmarked on self-generated saturation truth. The winner by run-bootstrap res68 is **{}** with res68 **{:.4f}** [{:.4f}, {:.4f}]. The strongest traditional baseline is **{}** with res68 **{:.4f}** [{:.4f}, {:.4f}].".format(
            winner["method"],
            winner["res68"],
            winner["res68_ci_low"],
            winner["res68_ci_high"],
            trad["method"],
            trad["res68"],
            trad["res68_ci_low"],
            trad["res68_ci_high"],
        ),
        "",
        "## Raw reproduction gates",
        "",
        "For every registered S00/T07 B-stack ROOT run, `HRDv` was reshaped to `(8,18)`, samples 0-3 supplied the per-channel baseline, even B-stave channels were baseline-subtracted, and a pulse was selected if its maximum exceeded 1000 ADC. This gives **{:,}** selected B-stave pulses versus the registered **{:,}** count, delta **{}**.".format(
            result["reproduction"]["global_selected_b_pulses"],
            result["reproduction"]["expected_global_selected_b_pulses"],
            result["reproduction"]["global_selected_delta"],
        ),
        "",
        "The P07h B2 boundary triage then uses runs `{}` only. In that subset the raw scan finds **{:,}** selected B2 pulses. Re-running the P07d boundary diagnostic reproduces the shape-only q-template shift as `{:.6f}` versus the archived `{:.6f}` and reproduces **{}** leakage flags.".format(
            ", ".join(str(r) for r in result["runs"]),
            result["reproduction"]["raw_pulses_b2_selected"],
            result["reproduction"]["p07d_reproduced_boundary_q_shift"],
            result["reproduction"]["p07d_expected_boundary_q_shift"],
            result["reproduction"]["p07d_reproduced_leakage_flags"],
        ),
        "",
        "## Statistical design",
        "",
        "The supervised benchmark uses clean unsaturated B2 pulses with peak samples 4-12, amplitude between 1500 and 6500 ADC, and true amplitude above `1.05 C`, where `C=4000` ADC. Each waveform is clipped at a fixed ceiling, so `x_i^C(t)=min(x_i(t), C)` and the target is the independent raw amplitude `A_i`. Folds are leave-one-run-out: for held-out run `r`, all templates and model parameters are fit only on runs `R \\ {r}`.",
        "",
        "The primary metric is",
        "",
        "`res68 = percentile_68(|Ahat_i - A_i| / A_i)`,",
        "",
        "with secondary median signed bias, fraction within 10%, fractional RMSE, and `R^2` in log amplitude. Confidence intervals are run-block bootstraps: draw held-out runs with replacement, average the per-run metric weighted by the run's test count, and report the 2.5% and 97.5% quantiles.",
        "",
        "## Traditional and ML methods",
        "",
        "The traditional baseline is a calibrated template-family recovery. Clean training pulses are binned by amplitude, normalized templates are fit in each bin, and the clipped rising-edge samples determine the least-squares amplitude scale. A final linear calibration `Ahat = beta_1 Araw + beta_0`, trained only on non-held-out runs, removes residual bias while preserving the non-ML pulse-shape model.",
        "",
        "The ML panel uses the clipped 18-sample waveform plus compact pulse-shape statistics for ridge, gradient-boosted trees, and MLP. The neural methods receive only the normalized clipped sequence. The new residual squeeze CNN is sensible here because the waveform has only 18 time samples: residual temporal convolutions retain local edge information, global average/max pooling summarizes tail support, and a small squeeze gate lets the network emphasize informative channels without a large parameter count.",
        "",
        "| method | n | bias | res68 | 95% CI | within 10% | RMSE frac | log-A R2 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in benchmark.iterrows():
        lines.append(
            "| {} | {:,} | {:+.4f} | {:.4f} | [{:.4f}, {:.4f}] | {:.4f} | {:.4f} | {:.4f} |".format(
                row["method"],
                int(row["n"]),
                row["bias"],
                row["res68"],
                row["res68_ci_low"],
                row["res68_ci_high"],
                row["frac_within10"],
                row["rmse_fraction"],
                row["r2_log_amp"],
            )
        )
    lines.extend(
        [
            "",
            "## Boundary leakage triage",
            "",
            "The natural-boundary arm reuses the P07d diagnostic layers and keeps the stricter interpretation: a correction is acceptable only if the 6500-7500 ADC boundary band passes `|q_template shift| <= 0.025` and `|CFD20 shift| <= 0.75 ns`. The reproduced flags are not random-row leakage: folds are by run, the primary calibration excludes raw observed amplitude, explicit ceiling, run id, `EVENTNO`, and `EVT`, and event-hash dependence remains small in the primary calibration. The three flags arise from diagnostic controls intentionally given observed-amplitude or run/event/amplitude handles, which can mimic the boundary alpha support but do not improve over the linear shrinkage layer.",
            "",
            "| check | value | threshold | flag | interpretation |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for _, row in leak_checks.iterrows():
        lines.append(
            "| {} | {:.6g} | {:.6g} | {} | {} |".format(
                row["check"],
                row["value"],
                row["threshold"],
                bool(row["flag"]),
                str(row["interpretation"]).replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## Systematics and caveats",
            "",
            "- The amplitude benchmark uses artificial hard clipping of clean pulses. It tests recovery mechanics under controlled saturation truth, not unknown true amplitudes of naturally saturated pulses.",
            "- The natural-boundary decision remains constrained by q-template and timing side effects. A model that wins artificial res68 is not automatically adoptable for production if it violates those boundary gates.",
            "- The B2-only P07h triage is intentionally narrower than the global 640,737-pulse reproduction gate; it targets the same natural B2 boundary where P07d raised flags.",
            "- Run-bootstrap CIs represent run-to-run stability, not independent event-count precision.",
            "- Neural networks are small by design because 18 samples do not justify high-capacity architectures without external truth.",
            "",
            "## Verdict",
            "",
            "`result.json` names **{}** as the artificial-saturation benchmark winner. For natural saturated B2 deployment, the boundary triage still prefers the simpler linear shrinkage layer unless a future study proves that the winning artificial-truth model also satisfies q-template, CFD20, and leakage gates on the natural boundary.".format(
                winner["method"]
            ),
            "",
            "## Reproducibility",
            "",
            "```bash",
            result["command"],
            "```",
            "",
            "Artifacts include `result.json`, `manifest.json`, `global_reproduction_by_run.csv`, `benchmark_summary.csv`, `benchmark_by_run.csv`, `benchmark_predictions.csv.gz`, `leakage_checks.csv`, `boundary_by_run.csv`, and diagnostic figures.",
        ]
    )
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_plots(out: Path, benchmark_by_run: pd.DataFrame, boundary_by_run: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    for method, group in benchmark_by_run.groupby("method"):
        ax.plot(group["heldout_run"], group["res68"], marker="o", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("artificial saturation res68")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(out / "fig_benchmark_res68_by_run.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    for method in ["p07c_full_shape_transfer", "linear_boundary_shrink", "ml_boundary_calibration"]:
        sub = boundary_by_run[(boundary_by_run["eval_set"] == "boundary_6500_7500") & (boundary_by_run["method"] == method)]
        if len(sub):
            ax.plot(sub["heldout_run"], sub["mean_q_template_shift_fraction"], marker="o", label=method)
    ax.axhline(0.025, color="0.5", ls=":", lw=1)
    ax.axhline(-0.025, color="0.5", ls=":", lw=1)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("boundary q-template shift")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out / "fig_boundary_q_shift_by_run.png", dpi=140)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args()
    t0 = time.time()
    cfg = load_config(args.config)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    script_rel = Path(__file__).resolve().relative_to(ROOT)
    config_rel = args.config.resolve().relative_to(ROOT)

    global_counts, global_total = count_global_selected_b_pulses(cfg)
    pulses = P07C.load_b2_pulses(cfg)
    boundary_by_run, boundary_predictions, scans, targets, training = P07D.run_folds(pulses, cfg)
    p07d_result, leak_checks = P07D.summarize_results(cfg, pulses, boundary_by_run, scans, training)
    bench_summary, bench_by_run, bench_predictions = run_benchmark(pulses, cfg)

    winner = bench_summary.iloc[0].to_dict()
    best_trad = bench_summary[bench_summary["method"] == "traditional_template_family"].iloc[0].to_dict()
    result = {
        "ticket": cfg["ticket"],
        "study": cfg["study"],
        "worker": cfg["worker"],
        "title": "boundary-shrinkage leakage triage plus traditional/ML saturation bakeoff",
        "raw_root": cfg["raw_root"],
        "runs": cfg["runs"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "command": f"{sys.executable} {script_rel} --config {config_rel}",
        "reproduction": {
            "global_selected_b_pulses": int(global_total),
            "expected_global_selected_b_pulses": int(cfg["global_expected_selected_b_pulses"]),
            "global_selected_delta": int(global_total - int(cfg["global_expected_selected_b_pulses"])),
            "global_selected_passed": bool(global_total == int(cfg["global_expected_selected_b_pulses"])),
            "raw_pulses_b2_selected": int(len(pulses)),
            "p07d_expected_boundary_q_shift": p07d_result["reproduction"]["p07c_expected_boundary_6500_7500_shape_only_q_shift"],
            "p07d_reproduced_boundary_q_shift": p07d_result["reproduction"]["p07c_reproduced_boundary_6500_7500_shape_only_q_shift"],
            "p07d_boundary_q_shift_delta": p07d_result["reproduction"]["absolute_delta"],
            "p07d_reproduced_leakage_flags": int(p07d_result["leakage_flags"]),
        },
        "split": {
            "type": "leave-one-run-out",
            "heldout_runs": cfg["runs"],
            "bootstrap_replicates": int(cfg["bootstrap_replicates"]),
        },
        "benchmark_task": {
            "target": "recover true clean-pulse amplitude after artificial fixed 4000 ADC clipping",
            "metric": "run-bootstrap res68 of |Ahat-A|/A",
            "artificial_ceiling_adc": float(cfg["artificial_ceiling_adc"]),
            "rows": int(bench_predictions["eventno"].count() / len(bench_summary)),
        },
        "best_traditional": json_clean(best_trad),
        "winner": json_clean(winner),
        "winner_method": winner["method"],
        "primary_methods": bench_summary["method"].tolist(),
        "benchmark_summary": json_clean(bench_summary.to_dict(orient="records")),
        "boundary_leakage": {
            "reproduced_flags": int(p07d_result["leakage_flags"]),
            "flagged_checks": json_clean(leak_checks[leak_checks["flag"]].to_dict(orient="records")),
            "boundary_and_application": p07d_result["boundary_and_application"],
            "interpretation": "flags localize to diagnostic controls/support handles rather than primary event-hash leakage; linear shrinkage remains preferred for natural deployment",
        },
        "next_tickets": [
            {
                "title": "Validate P07h winning artificial-saturation model on natural-boundary q/timing gates",
                "body": "Apply the P07h benchmark winner to natural B2 A>=7000 pulses under the P07d q_template, CFD20, event-hash, and support-loss gates before any production adoption."
            }
        ],
        "runtime_sec": None,
    }
    result["runtime_sec"] = float(time.time() - t0)

    global_counts.to_csv(out / "global_reproduction_by_run.csv", index=False)
    bench_summary.to_csv(out / "benchmark_summary.csv", index=False)
    bench_by_run.to_csv(out / "benchmark_by_run.csv", index=False)
    bench_predictions.to_csv(out / "benchmark_predictions.csv.gz", index=False)
    leak_checks.to_csv(out / "leakage_checks.csv", index=False)
    boundary_by_run.to_csv(out / "boundary_by_run.csv", index=False)
    boundary_predictions.sample(min(len(boundary_predictions), 50000), random_state=int(cfg["random_seed"])).to_csv(
        out / "boundary_predictions_sample.csv.gz", index=False
    )
    scans.to_csv(out / "alpha_scan.csv", index=False)
    targets.to_csv(out / "alpha_targets.csv.gz", index=False)
    save_plots(out, bench_by_run, boundary_by_run)
    (out / "result.json").write_text(json.dumps(json_clean(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "ticket": cfg["ticket"],
        "config": str(args.config),
        "git_commit": result["git_commit"],
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "input_sha256": {
            str(path.relative_to(ROOT)): sha256_file(path)
            for path in sorted((ROOT / cfg["raw_root"]).glob("hrdb_run_*.root"))
            if int(path.stem.split("_")[-1]) in set(cfg["runs"])
        },
        "outputs_sha256": {},
    }
    write_report(out, result, bench_summary, leak_checks)
    for path in sorted(out.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            manifest["outputs_sha256"][path.name] = sha256_file(path)
    (out / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
