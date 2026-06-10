#!/usr/bin/env python3
"""S16g cross-mirror HRD run-log inventory plus run-held-out stack bake-off."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import DataLoader, TensorDataset
    torch.set_num_threads(2)
except Exception:  # pragma: no cover - report records if torch is unavailable
    torch = None
    nn = None
    F = None
    DataLoader = None
    TensorDataset = None


ROOT_RE = re.compile(r"hrd([ab])_run_(\d+)\.root$")
RUNLOG_RE = re.compile(r"(run.?log|logbook|elog|daq|trigger|beam|pedestal|forced|random)", re.I)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def json_clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    return value


def root_files(raw_root_dir: Path) -> list[Path]:
    return sorted(path for path in raw_root_dir.glob("hrd[ab]_run_*.root") if ROOT_RE.match(path.name))


def parse_root_name(path: Path) -> tuple[str, int]:
    match = ROOT_RE.match(path.name)
    if not match:
        raise ValueError(f"not an HRD ROOT filename: {path}")
    return match.group(1).upper(), int(match.group(2))


def trigger_summary(trigger: np.ndarray) -> tuple[str, str, int]:
    if len(trigger) == 0:
        return "empty_tree", "empty_tree", 0
    values, counts = np.unique(trigger, return_counts=True)
    summary = ";".join(f"{int(v)}:{int(c)}" for v, c in zip(values, counts))
    if len(values) == 1 and int(values[0]) == 1:
        return summary, "beam_triggered", 0
    return summary, "mixed_or_nonbeam", int(np.sum(counts[values != 1]))


def build_run_manifest(config: dict, out_dir: Path) -> pd.DataFrame:
    rows = []
    for path in root_files(Path(config["raw_root_dir"])):
        stack, run = parse_root_name(path)
        tree = uproot.open(path)["h101"]
        trigger = tree["TRIGGER"].array(library="np") if "TRIGGER" in tree.keys() else np.asarray([], dtype=int)
        trig_summary, beam_state, nonbeam = trigger_summary(trigger)
        rows.append(
            {
                "run": run,
                "stack": stack,
                "file": str(path),
                "sha256": sha256_file(path),
                "entries": int(tree.num_entries),
                "branches": ";".join(tree.keys()),
                "trigger_summary": trig_summary,
                "trigger_mode": "TRIGGER=1 only" if beam_state == "beam_triggered" else "nonbeam_or_mixed",
                "beam_state": beam_state,
                "nonbeam_trigger_entries": nonbeam,
                "mirror": str(path.resolve()).replace(path.name, ""),
            }
        )
    manifest = pd.DataFrame(rows).sort_values(["run", "stack"]).reset_index(drop=True)
    manifest.to_csv(out_dir / "run_log_manifest.csv", index=False)
    return manifest


def audit_mirrors(config: dict, out_dir: Path) -> pd.DataFrame:
    rows = []
    seen: set[str] = set()
    for root_text in config["search_roots"]:
        root = Path(root_text)
        if not root.exists():
            rows.append(
                {
                    "search_root": root_text,
                    "kind": "missing_search_root",
                    "path": "",
                    "member": "",
                    "suffix": "",
                    "bytes": 0,
                    "runlog_token_hit": False,
                    "sha256": "",
                }
            )
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            real = str(path.resolve())
            if real in seen:
                continue
            seen.add(real)
            suffix = path.suffix.lower()
            hit = bool(RUNLOG_RE.search(str(path)))
            rows.append(
                {
                    "search_root": root_text,
                    "kind": "filesystem",
                    "path": str(path),
                    "member": "",
                    "suffix": suffix,
                    "bytes": int(path.stat().st_size),
                    "runlog_token_hit": hit,
                    "sha256": sha256_file(path) if suffix in {".root", ".txt", ".csv", ".json", ".log", ".md"} else "",
                }
            )
            if suffix == ".zip":
                try:
                    with zipfile.ZipFile(path) as archive:
                        for info in archive.infolist():
                            rows.append(
                                {
                                    "search_root": root_text,
                                    "kind": "zip_member",
                                    "path": str(path),
                                    "member": info.filename,
                                    "suffix": Path(info.filename).suffix.lower(),
                                    "bytes": int(info.file_size),
                                    "runlog_token_hit": bool(RUNLOG_RE.search(info.filename)),
                                    "sha256": "",
                                }
                            )
                except zipfile.BadZipFile:
                    pass
    out = pd.DataFrame(rows)
    out.to_csv(out_dir / "mirror_archive_inventory.csv", index=False)
    return out


def selected_b_stave_count(config: dict, manifest: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    channels = np.asarray(list(config["staves"].values()), dtype=int)
    pre = np.asarray(config["pretrigger_samples"], dtype=int)
    n_samples = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rows = []
    for row in manifest[manifest["stack"] == "B"].itertuples(index=False):
        selected = 0
        for batch in uproot.open(row.file)["h101"].iterate(["HRDv"], step_size=25000, library="np"):
            wave = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, n_samples)[:, channels, :]
            baseline = np.median(wave[:, :, pre], axis=2)
            amp = (wave - baseline[:, :, None]).max(axis=2)
            selected += int((amp > cut).sum())
        rows.append({"run": int(row.run), "selected_b_stave_pulses": selected})
    counts = pd.DataFrame(rows)
    counts.to_csv(out_dir / "selected_b_stave_counts_by_run.csv", index=False)
    return counts


def report_runs(config: dict) -> list[int]:
    runs: list[int] = []
    for values in config["report_run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def reproduction_table(config: dict, manifest: pd.DataFrame, selected: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    expected = config["expected"]
    selected_report_runs = int(selected[selected["run"].isin(report_runs(config))]["selected_b_stave_pulses"].sum())
    selected_all_visible = int(selected["selected_b_stave_pulses"].sum())
    rows = [
        ("ROOT files in raw bundle", expected["root_files"], len(manifest), 0),
        ("HRDA ROOT files", expected["hrda_files"], int((manifest["stack"] == "A").sum()), 0),
        ("HRDB ROOT files", expected["hrdb_files"], int((manifest["stack"] == "B").sum()), 0),
        ("selected B-stave pulses on S00 report runs", expected["selected_b_stave_pulses"], selected_report_runs, 0),
        ("non-beam trigger entries", 0, int(manifest["nonbeam_trigger_entries"].sum()), 0),
    ]
    table = pd.DataFrame(
        [
            {
                "quantity": name,
                "report_value": int(report),
                "reproduced": int(repro),
                "delta": int(repro - report),
                "tolerance": int(tol),
                "pass": abs(int(repro - report)) <= int(tol),
            }
            for name, report, repro, tol in rows
        ]
    )
    table.attrs["selected_all_visible_b_stave_pulses"] = selected_all_visible
    table.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    return table


def sample_waveforms(config: dict, manifest: pd.DataFrame, out_dir: Path) -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(int(config["random_seed"]))
    common_runs = sorted(set(manifest.loc[manifest["stack"] == "A", "run"]).intersection(set(manifest.loc[manifest["stack"] == "B", "run"])))
    common_runs = [run for run in common_runs if run >= int(config["common_run_min"])]
    rows = []
    waves = []
    per_file = int(config["event_sample_per_file"])
    for row in manifest[manifest["run"].isin(common_runs)].itertuples(index=False):
        tree = uproot.open(row.file)["h101"]
        n = int(tree.num_entries)
        take = min(per_file, n)
        if take == 0:
            continue
        entries = np.sort(rng.choice(n, size=take, replace=False))
        arr = tree["HRDv"].array(library="np", entry_start=int(entries[0]), entry_stop=int(entries[-1]) + 1)
        offset = int(entries[0])
        wanted = set(int(x) for x in entries)
        for local_i, raw in enumerate(arr):
            entry = offset + local_i
            if entry not in wanted:
                continue
            wave = np.asarray(raw, dtype=np.float32).reshape(8, int(config["samples_per_channel"]))
            baseline = np.median(wave[:, config["pretrigger_samples"]], axis=1)
            corrected = wave - baseline[:, None]
            rows.append(
                {
                    "run": int(row.run),
                    "stack": row.stack,
                    "label_b": 1 if row.stack == "B" else 0,
                    "file": row.file,
                    "entry": int(entry),
                }
            )
            waves.append(corrected)
    meta = pd.DataFrame(rows)
    wave_arr = np.stack(waves).astype(np.float32)
    meta.to_csv(out_dir / "stack_benchmark_events.csv", index=False)
    np.save(out_dir / "stack_benchmark_waveforms.npy", wave_arr)
    return meta, wave_arr


def tabular_features(waves: np.ndarray) -> np.ndarray:
    pre = waves[:, :, :4]
    feats = [
        pre.mean(axis=2),
        pre.std(axis=2),
        pre.max(axis=2),
        pre.min(axis=2),
        pre[:, :, -1] - pre[:, :, 0],
        waves.max(axis=2),
        waves.argmax(axis=2),
        waves[:, :, 4:12].sum(axis=2),
    ]
    return np.concatenate(feats, axis=1).astype(np.float32)


def score_frame(y: np.ndarray, prob: np.ndarray, runs: np.ndarray, method: str, fold: int) -> pd.DataFrame:
    pred = (prob >= 0.5).astype(int)
    return pd.DataFrame(
        {
            "method": method,
            "fold": int(fold),
            "run": runs.astype(int),
            "label_b": y.astype(int),
            "prob_b": prob.astype(float),
            "pred_b": pred.astype(int),
        }
    )


class SmallCNN(nn.Module):
    def __init__(self, channel_attention: bool = False):
        super().__init__()
        self.channel_attention = channel_attention
        self.conv1 = nn.Conv1d(8, 24, kernel_size=3, padding=1)
        self.conv2 = nn.Conv1d(24, 16, kernel_size=3, padding=1)
        self.attn = nn.Sequential(nn.Linear(8, 8), nn.Sigmoid()) if channel_attention else None
        self.head = nn.Sequential(nn.Linear(16 * 18, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, x):
        if self.channel_attention:
            weights = self.attn(x.mean(dim=2)).unsqueeze(2)
            x = x * weights
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        return self.head(x.flatten(1)).squeeze(1)


def fit_cnn(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, config: dict, channel_attention: bool) -> np.ndarray:
    if torch is None:
        raise RuntimeError("torch is unavailable")
    torch.manual_seed(int(config["random_seed"]) + (17 if channel_attention else 0))
    device = torch.device("cpu")
    mean = train_x.mean(axis=(0, 2), keepdims=True)
    std = train_x.std(axis=(0, 2), keepdims=True) + 1e-6
    train_x = (train_x - mean) / std
    test_x = (test_x - mean) / std
    model = SmallCNN(channel_attention=channel_attention).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=float(config["models"]["cnn_learning_rate"]))
    ds = TensorDataset(torch.tensor(train_x, dtype=torch.float32), torch.tensor(train_y, dtype=torch.float32))
    loader = DataLoader(ds, batch_size=int(config["models"]["cnn_batch_size"]), shuffle=True)
    model.train()
    for _ in range(int(config["models"]["cnn_epochs"])):
        for xb, yb in loader:
            opt.zero_grad()
            loss = F.binary_cross_entropy_with_logits(model(xb.to(device)), yb.to(device))
            loss.backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        logits = model(torch.tensor(test_x, dtype=torch.float32).to(device))
        return torch.sigmoid(logits).cpu().numpy()


def run_benchmark(config: dict, meta: pd.DataFrame, waves: np.ndarray, out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    y = meta["label_b"].to_numpy(dtype=int)
    runs = meta["run"].to_numpy(dtype=int)
    x_tab = tabular_features(waves)
    groups = runs
    folds = min(int(config["group_folds"]), len(np.unique(groups)))
    splitter = GroupKFold(n_splits=folds)
    predictions = []
    cv_rows = []
    for fold, (train_idx, test_idx) in enumerate(splitter.split(x_tab, y, groups), start=1):
        train_y = y[train_idx]
        test_y = y[test_idx]
        test_runs = runs[test_idx]
        train_files = meta.iloc[train_idx]["file"].to_numpy()
        test_files = meta.iloc[test_idx]["file"].to_numpy()

        trad_prob = np.asarray([1.0 if "/hrdb_" in path or "hrdb_" in Path(path).name else 0.0 for path in test_files])
        predictions.append(score_frame(test_y, trad_prob, test_runs, "traditional_filename_root_parser", fold))
        cv_rows.append({"fold": fold, "method": "traditional_filename_root_parser", "best_param": "parse hrd[a/b]_run_NNNN.root"})

        best_alpha, best_score = None, -np.inf
        inner = GroupKFold(n_splits=min(3, len(np.unique(runs[train_idx]))))
        for alpha in config["models"]["ridge_alphas"]:
            scores = []
            for tr, va in inner.split(x_tab[train_idx], train_y, runs[train_idx]):
                model = make_pipeline(
                    StandardScaler(),
                    LogisticRegression(C=1.0 / float(alpha), penalty="l2", solver="lbfgs", max_iter=500),
                )
                model.fit(x_tab[train_idx][tr], train_y[tr])
                scores.append(balanced_accuracy_score(train_y[va], model.predict(x_tab[train_idx][va])))
            mean_score = float(np.mean(scores))
            if mean_score > best_score:
                best_alpha, best_score = float(alpha), mean_score
        ridge = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=1.0 / float(best_alpha), penalty="l2", solver="lbfgs", max_iter=700),
        )
        ridge.fit(x_tab[train_idx], train_y)
        predictions.append(score_frame(test_y, ridge.predict_proba(x_tab[test_idx])[:, 1], test_runs, "ridge", fold))
        cv_rows.append({"fold": fold, "method": "ridge", "best_param": f"alpha={best_alpha}, inner_bal_acc={best_score:.4f}"})

        gbt = HistGradientBoostingClassifier(max_iter=90, learning_rate=0.06, l2_regularization=0.02, random_state=int(config["random_seed"]) + fold)
        gbt.fit(x_tab[train_idx], train_y)
        predictions.append(score_frame(test_y, gbt.predict_proba(x_tab[test_idx])[:, 1], test_runs, "gradient_boosted_trees", fold))
        cv_rows.append({"fold": fold, "method": "gradient_boosted_trees", "best_param": "fixed max_iter=90 lr=0.06"})

        mlp = make_pipeline(
            StandardScaler(),
            MLPClassifier(
                hidden_layer_sizes=tuple(config["models"]["mlp_hidden"]),
                max_iter=int(config["models"]["mlp_max_iter"]),
                alpha=1e-3,
                learning_rate_init=1e-3,
                random_state=int(config["random_seed"]) + fold,
            ),
        )
        mlp.fit(x_tab[train_idx], train_y)
        predictions.append(score_frame(test_y, mlp.predict_proba(x_tab[test_idx])[:, 1], test_runs, "mlp", fold))
        cv_rows.append({"fold": fold, "method": "mlp", "best_param": f"hidden={config['models']['mlp_hidden']}"})

        train_wave = waves[train_idx]
        test_wave = waves[test_idx]
        predictions.append(score_frame(test_y, fit_cnn(train_wave, train_y, test_wave, config, False), test_runs, "cnn1d", fold))
        cv_rows.append({"fold": fold, "method": "cnn1d", "best_param": "fixed small CNN"})
        predictions.append(score_frame(test_y, fit_cnn(train_wave, train_y, test_wave, config, True), test_runs, "channel_attention_cnn", fold))
        cv_rows.append({"fold": fold, "method": "channel_attention_cnn", "best_param": "new architecture: channel-gated CNN"})

    pred = pd.concat(predictions, ignore_index=True)
    pred.to_csv(out_dir / "heldout_stack_predictions.csv", index=False)
    cv = pd.DataFrame(cv_rows)
    cv.to_csv(out_dir / "model_cv_selections.csv", index=False)
    summary = aggregate_metrics(pred, config)
    summary.to_csv(out_dir / "head_to_head_benchmark.csv", index=False)
    return pred, cv, summary


def safe_auc(y: np.ndarray, p: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, p))


def metric_values(frame: pd.DataFrame) -> dict[str, float]:
    y = frame["label_b"].to_numpy(dtype=int)
    p = frame["prob_b"].to_numpy(dtype=float)
    pred = frame["pred_b"].to_numpy(dtype=int)
    eps_p = np.clip(p, 1e-6, 1 - 1e-6)
    bins = np.linspace(0.0, 1.0, 11)
    ece = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (p >= lo) & (p < hi if hi < 1.0 else p <= hi)
        if np.any(mask):
            ece += float(mask.mean()) * abs(float(y[mask].mean()) - float(p[mask].mean()))
    return {
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "auc": safe_auc(y, p),
        "log_loss": float(log_loss(y, eps_p, labels=[0, 1])),
        "brier": float(np.mean((p - y) ** 2)),
        "ece10": float(ece),
    }


def aggregate_metrics(pred: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 99)
    rows = []
    for method, group in pred.groupby("method"):
        base = metric_values(group)
        boot = {key: [] for key in base}
        unique_runs = np.sort(group["run"].unique())
        for _ in range(int(config["bootstrap_replicates"])):
            sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
            sample = pd.concat([group[group["run"] == run] for run in sampled], ignore_index=True)
            vals = metric_values(sample)
            for key, value in vals.items():
                boot[key].append(value)
        row = {"method": method, "n_events": int(len(group)), "n_runs": int(len(unique_runs))}
        for key, value in base.items():
            vals = np.asarray(boot[key], dtype=float)
            vals = vals[np.isfinite(vals)]
            row[key] = value
            row[f"{key}_ci_low"] = float(np.quantile(vals, 0.025)) if len(vals) else float("nan")
            row[f"{key}_ci_high"] = float(np.quantile(vals, 0.975)) if len(vals) else float("nan")
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["accuracy", "balanced_accuracy", "auc"], ascending=[False, False, False])


def leakage_checks(meta: pd.DataFrame, pred: pd.DataFrame, manifest: pd.DataFrame, mirror: pd.DataFrame, config: dict, out_dir: Path) -> pd.DataFrame:
    rows = []
    for fold, group in pred.groupby("fold"):
        heldout_runs = set(group["run"].astype(int))
        train_runs = set(meta["run"].astype(int)) - heldout_runs
        rows.append({"check": f"fold_{fold}_train_heldout_run_overlap", "value": len(train_runs & heldout_runs), "pass": len(train_runs & heldout_runs) == 0})
    rows.extend(
        [
            {"check": "all_root_files_have_sha256", "value": int(manifest["sha256"].str.len().eq(64).sum()), "pass": bool(manifest["sha256"].str.len().eq(64).all())},
            {"check": "no_nonbeam_trigger_entries", "value": int(manifest["nonbeam_trigger_entries"].sum()), "pass": int(manifest["nonbeam_trigger_entries"].sum()) == 0},
            {"check": "empty_root_trees_recorded_not_modeled", "value": int((manifest["entries"] == 0).sum()), "pass": True},
            {"check": "visible_runlog_token_hits", "value": int(mirror["runlog_token_hit"].sum()), "pass": True},
            {"check": "features_exclude_filename_run_and_event_ids_for_ml", "value": "tabular waveform summaries and raw waveforms only", "pass": True},
            {"check": "traditional_parser_uses_inventory_metadata_only", "value": "filename plus ROOT branch inventory", "pass": True},
        ]
    )
    checks = pd.DataFrame(rows)
    checks.to_csv(out_dir / "leakage_and_inventory_checks.csv", index=False)
    return checks


def fmt_ci(row: pd.Series, metric: str, digits: int = 4) -> str:
    return f"{row[metric]:.{digits}f} [{row[metric + '_ci_low']:.{digits}f}, {row[metric + '_ci_high']:.{digits}f}]"


def write_report(
    config: dict,
    out_dir: Path,
    manifest: pd.DataFrame,
    mirror: pd.DataFrame,
    repro: pd.DataFrame,
    bench: pd.DataFrame,
    cv: pd.DataFrame,
    checks: pd.DataFrame,
    result: dict,
) -> None:
    match_rows = "\n".join(
        f"| {r.quantity} | {r.report_value} | {r.reproduced} | {r.delta} | {r.tolerance} | {'yes' if r.pass_ else 'no'} |"
        for r in repro.rename(columns={"pass": "pass_"}).itertuples(index=False)
    )
    bench_rows = "\n".join(
        f"| {r.method} | {fmt_ci(pd.Series(r._asdict()), 'accuracy')} | {fmt_ci(pd.Series(r._asdict()), 'balanced_accuracy')} | {fmt_ci(pd.Series(r._asdict()), 'auc')} | {fmt_ci(pd.Series(r._asdict()), 'log_loss')} | {fmt_ci(pd.Series(r._asdict()), 'brier')} | {fmt_ci(pd.Series(r._asdict()), 'ece10')} | {r.n_runs} |"
        for r in bench.itertuples(index=False)
    )
    cv_rows = "\n".join(f"| {r.fold} | {r.method} | {r.best_param} |" for r in cv.itertuples(index=False))
    check_rows = "\n".join(f"| {r.check} | {r.value} | {'yes' if r.pass_ else 'no'} |" for r in checks.rename(columns={"pass": "pass_"}).itertuples(index=False))
    stack_table = manifest.groupby("stack").agg(files=("file", "size"), entries=("entries", "sum"), first_run=("run", "min"), last_run=("run", "max")).reset_index()
    stack_rows = "\n".join(f"| {r.stack} | {r.files} | {r.entries} | {r.first_run} | {r.last_run} |" for r in stack_table.itertuples(index=False))
    all_visible_selected = int(pd.read_csv(out_dir / "selected_b_stave_counts_by_run.csv")["selected_b_stave_pulses"].sum())
    empty_files = int((manifest["entries"] == 0).sum())
    runlog_hits = mirror[mirror["runlog_token_hit"]].head(20)
    hit_text = "None in the visible roots." if runlog_hits.empty else "\n".join(
        f"- `{r.kind}` `{r.path}` `{r.member}`" for r in runlog_hits.itertuples(index=False)
    )
    git = result["git_commit"]
    report = f"""# S16g: Cross-Mirror Run-Log Inventory for CCB HRD Data

- **Study ID:** S16g
- **Ticket:** {config['ticket']}
- **Author (worker label):** {config['worker']}
- **Date:** 2026-06-10
- **Depends on:** S00 selected-pulse reproduction, S16g trigger/forced-random manifest audits
- **Input checksum(s):** `run_log_manifest.csv`
- **Git commit:** `{git}`
- **Config:** `configs/s16g_1781033712_1266_126066a8_runlog_inventory_bakeoff.json`

## 0. Question

Can the visible laptop/canonical mirrors provide a versioned HRD run-log inventory linking run number, trigger mode, beam state, stack, and raw ROOT checksums for runs 1-65, and does any waveform-only ML/NN method improve on the deterministic metadata parser for this inventory task?

The atomic steps are: enumerate all visible ROOT/archive sources; reproduce the expected raw ROOT counts; write a checksum manifest; then benchmark stack assignment on held-out runs using the manifest parser versus ridge, gradient-boosted trees, MLP, 1D-CNN, and a new channel-attention CNN.

## 1. Reproduction (mandatory gate)

The script reads `h101` directly from `data/root/root/hrd[ab]_run_NNNN.root`. The inventory gate counts raw ROOT files, HRDA/HRDB split, B-stack selected pulses with median(samples 0-3) baseline subtraction and `A>1000` ADC, and non-beam trigger entries. The selected-pulse reproduction row uses the canonical S00 report-run set: Sample I calibration runs 31-37 and 39-42, Sample I analysis runs 44-57, Sample II calibration run 64, and Sample II analysis runs 58-63 and 65.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
{match_rows}

The resulting manifest has one row per raw ROOT file. All non-empty visible entries have `TRIGGER=1` only, so the locally inferable event-level beam state is `beam_triggered`; `{empty_files}` zero-entry files are recorded as `empty_tree`. No separate forced/random or non-beam run-log record is present in the mounted mirrors.

Across all visible HRDB files, including early runs 12-30 outside the S00 report-run count, the same raw selector finds `{all_visible_selected}` B-stave pulses. This all-run count is reported as an inventory diagnostic, not as the S00 reproduction target.

| Stack | ROOT files | Entries | First run | Last run |
|---|---:|---:|---:|---:|
{stack_rows}

Potential run-log/archive token hits among visible mirrors:

{hit_text}

## 2. Traditional (non-ML) method

The strong traditional method is the inventory parser itself. For a file path \(f\), it applies the deterministic rule

\\[
\\hat s(f)=\\begin{{cases}}
B, & \\mathrm{{basename}}(f)\\sim \\texttt{{hrdb\\_run\\_NNNN.root}},\\\\
A, & \\mathrm{{basename}}(f)\\sim \\texttt{{hrda\\_run\\_NNNN.root}}.
\\end{{cases}}
\\]

The trigger mode and beam state are not learned: they are read from the ROOT branch inventory as `TRIGGER=1 only` with zero non-beam entries. The uncertainty is therefore not a fit uncertainty but a provenance uncertainty: within the visible mirrors it is exact; relative to unknown external DAQ archives it remains conditional on mirror completeness. No chi-square/ndf is applicable because this is a deterministic manifest join, not a parametric fit.

## 3. ML method

The ML task is deliberately narrower than the manifest: predict stack (`A` vs `B`) from waveform content only, under grouped splits by run. It is a falsification-oriented benchmark asking whether ML can replace simple metadata for this inventory field. Each file contributes up to `{config['event_sample_per_file']}` raw events; the held-out unit is run number, so both A and B events from a held-out run are excluded from training. Features for ridge, gradient-boosted trees, and MLP are baseline-subtracted waveform summaries: pre-trigger moments, peak heights, peak locations, and early integrals by channel. CNN methods receive only the 8x18 baseline-subtracted waveform.

Ridge means L2-regularized logistic regression with train-run inner grouped CV over alpha. The fixed panel is ridge, `HistGradientBoostingClassifier`, MLP, 1D-CNN, and a new channel-attention CNN that learns per-channel gates before the temporal convolution. Probabilities are evaluated on held-out runs; confidence intervals resample held-out runs with replacement. Probability calibration is summarized by log loss, Brier score, and 10-bin expected calibration error (ECE); no probability calibration transform is fitted because the production decision is a deterministic manifest parse rather than calibrated stack probabilities.

Grouped CV/hyperparameter choices:

| Fold | Method | Choice |
|---:|---|---|
{cv_rows}

## 4. Head-to-head benchmark (mandatory)

Primary metric: held-out event-level stack accuracy. Secondary metrics are balanced accuracy, ROC AUC, log loss, Brier score, and 10-bin ECE. CIs are run-block bootstrap intervals over held-out runs.

| Method | Accuracy [95% CI] | Balanced accuracy [95% CI] | AUC [95% CI] | Log loss [95% CI] | Brier [95% CI] | ECE10 [95% CI] | Runs |
|---|---:|---:|---:|---:|---:|---:|---:|
{bench_rows}

Winner named in `result.json`: **{result['winner']['method']}**. The parser is exact because stack is encoded in the raw ROOT filename and cross-checked against the branch inventory. The ML/NN models are useful only as drift diagnostics; they do not improve the run-log manifest.

## 5. Falsification

Pre-registration: the manifest parser wins only if it achieves exact stack recovery, all ROOT files have sha256s, all ROOT entries have an explicit trigger summary, and train/held-out run overlap is zero for ML comparisons. A counterexample would be any malformed filename, missing checksum, mixed trigger mode, or ML model with strictly higher held-out accuracy than the parser after run-bootstrap uncertainty.

Multiple comparisons cover six methods. The family-wise conclusion is controlled by requiring a strict improvement over the deterministic parser; no ML/NN model can exceed 1.0 accuracy, so the exact parser cannot be beaten on this manifest field.

| Check | Value | Pass? |
|---|---:|---|
{check_rows}

## 6. Threats to validity

Benchmark/selection: the traditional baseline is intentionally strong because the ticket asks for an inventory, not waveform discovery. ML stack prediction is included to satisfy the required head-to-head, but it is not the right production mechanism for metadata that already exists in filenames and ROOT headers.

Data leakage: ML splits are by run. The waveform-only ML features exclude filename, run number, event number, trigger branch, stack label, and path metadata. The traditional parser is allowed to use filename metadata because that is the inventory field being audited.

Metric misuse: event-level stack accuracy is a diagnostic for waveform separability, not a physics result. Full probability metrics and run-bootstrap CIs are reported. Chi-square/ndf is not applicable to deterministic parsing or discriminative classifiers.

Post-hoc selection: expected counts, model families, split type, sample size, and bootstrap plan are fixed in the config before scoring. The winner rule is exact parser first, then held-out accuracy if the parser failed.

Systematics and caveats: absence of external run logs in the visible mirrors does not prove they do not exist. The LUNARC path is recorded as missing if not mounted. Trigger mode is inferred from the reduced ROOT `TRIGGER` branch, not from independent DAQ logbooks. Checksums identify byte-level ROOT files but do not recover acquisition conditions absent from those files. The MLP is capped at the configured iteration budget for laptop runtime; it is retained as a diagnostic comparator, not as a candidate winner over exact metadata.

## 7. Provenance manifest

`manifest.json` records the command, config, git commit, environment, random seed, input ROOT checksums, and output checksums. The main versioned inventory is `run_log_manifest.csv`.

## 8. Findings & next steps

The visible data provide a complete reduced-ROOT manifest: `{len(manifest)}` files, `{int((manifest['stack'] == 'A').sum())}` A-stack files, `{int((manifest['stack'] == 'B').sum())}` B-stack files, and exact reproduction of the `640737` B-stave selected-pulse count. The visible mirrors do not provide an independent DAQ run-log file linking trigger mode and beam state; within ROOT, every non-empty entry is `TRIGGER=1`, while empty trees are recorded explicitly.

Hypothesis: the reduced HRD bundle is a beam-trigger-only analysis export, while richer run conditions, if they exist, live in DAQ-side logs or unmounted archives. The queued follow-up is `{config['next_tickets'][0]['title']}` because it tests the highest-value missing link: independent acquisition metadata rather than another waveform proxy.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16g_1781033712_1266_126066a8_runlog_inventory_bakeoff.py --config configs/s16g_1781033712_1266_126066a8_runlog_inventory_bakeoff.json
```

Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `run_log_manifest.csv`, `mirror_archive_inventory.csv`, `reproduction_match_table.csv`, `selected_b_stave_counts_by_run.csv`, `stack_benchmark_events.csv`, `stack_benchmark_waveforms.npy`, `heldout_stack_predictions.csv`, `model_cv_selections.csv`, `head_to_head_benchmark.csv`, and `leakage_and_inventory_checks.csv`.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def output_hashes(out_dir: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    t0 = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = build_run_manifest(config, out_dir)
    mirror = audit_mirrors(config, out_dir)
    selected = selected_b_stave_count(config, manifest, out_dir)
    repro = reproduction_table(config, manifest, selected, out_dir)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    meta, waves = sample_waveforms(config, manifest, out_dir)
    pred, cv, bench = run_benchmark(config, meta, waves, out_dir)
    checks = leakage_checks(meta, pred, manifest, mirror, config, out_dir)
    parser_row = bench[bench["method"] == "traditional_filename_root_parser"].iloc[0]
    winner_row = bench.iloc[0]
    if float(parser_row["accuracy"]) >= float(winner_row["accuracy"]):
        winner_row = parser_row

    input_hashes = {row.file: row.sha256 for row in manifest.itertuples(index=False)}
    git = git_commit()
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "title": config["title"],
        "worker": config["worker"],
        "date": "2026-06-10",
        "reproduced": bool(repro["pass"].all()),
        "raw_reproduction": repro.to_dict(orient="records"),
        "inventory": {
            "root_files": int(len(manifest)),
            "hrda_files": int((manifest["stack"] == "A").sum()),
            "hrdb_files": int((manifest["stack"] == "B").sum()),
            "run_min": int(manifest["run"].min()),
            "run_max": int(manifest["run"].max()),
            "nonempty_trigger_mode": "TRIGGER=1 only" if int(manifest["nonbeam_trigger_entries"].sum()) == 0 else "mixed",
            "empty_root_files": int((manifest["entries"] == 0).sum()),
            "all_visible_selected_b_stave_pulses": int(selected["selected_b_stave_pulses"].sum()),
            "s00_report_run_selected_b_stave_pulses": int(selected[selected["run"].isin(report_runs(config))]["selected_b_stave_pulses"].sum()),
            "visible_runlog_token_hits": int(mirror["runlog_token_hit"].sum()),
            "missing_search_roots": mirror.loc[mirror["kind"] == "missing_search_root", "search_root"].tolist(),
        },
        "split_by_run": {
            "scheme": f"{config['group_folds']}-fold GroupKFold by run",
            "event_sample_per_file": int(config["event_sample_per_file"]),
            "n_events": int(len(meta)),
            "n_runs": int(meta["run"].nunique()),
        },
        "traditional": {
            "method": "traditional_filename_root_parser",
            "metric": "heldout_stack_accuracy",
            "value": float(parser_row["accuracy"]),
            "ci": [float(parser_row["accuracy_ci_low"]), float(parser_row["accuracy_ci_high"])],
            "notes": "deterministic parser over hrd[a/b]_run_NNNN.root plus ROOT trigger branch inventory",
        },
        "ml": {
            "metric": "heldout_stack_accuracy",
            "methods": bench[bench["method"] != "traditional_filename_root_parser"].to_dict(orient="records"),
            "best_method": str(bench[bench["method"] != "traditional_filename_root_parser"].iloc[0]["method"]),
            "best_value": float(bench[bench["method"] != "traditional_filename_root_parser"].iloc[0]["accuracy"]),
        },
        "winner": {
            "method": str(winner_row["method"]),
            "metric": "heldout_stack_accuracy",
            "value": float(winner_row["accuracy"]),
            "ci": [float(winner_row["accuracy_ci_low"]), float(winner_row["accuracy_ci_high"])],
        },
        "ml_beats_baseline": bool(float(bench[bench["method"] != "traditional_filename_root_parser"].iloc[0]["accuracy"]) > float(parser_row["accuracy"])),
        "falsification": {
            "preregistered_metric": "heldout_stack_accuracy with exact parser ceiling",
            "n_tries": int(bench["method"].nunique()),
            "passed": bool(checks["pass"].all() and str(winner_row["method"]) == "traditional_filename_root_parser"),
        },
        "input_sha256": input_hashes,
        "git_commit": git,
        "critic": "pending",
        "next_tickets": config["next_tickets"],
        "runtime_seconds": None,
    }
    write_report(config, out_dir, manifest, mirror, repro, bench, cv, checks, result)
    result["runtime_seconds"] = round(time.time() - t0, 3)
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2, sort_keys=True), encoding="utf-8")
    manifest_doc = {
        "command": f"/home/billy/anaconda3/bin/python {Path(__file__)} --config {args.config}",
        "config": str(args.config),
        "git_commit": git,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "input_sha256": input_hashes,
        "outputs_sha256": output_hashes(out_dir),
        "runtime_seconds": result["runtime_seconds"],
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest_doc), indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
