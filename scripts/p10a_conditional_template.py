#!/usr/bin/env python3
"""P10a conditional template benchmark from raw ROOT waveforms."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
import yaml


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def group_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_raw(path: Path, branches: List[str], step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(branches, step_size=step_size, library="np")


def cfd_position(norm_waveform: np.ndarray, fraction: float) -> float:
    peak = int(np.nanargmax(norm_waveform))
    if peak <= 0 or not np.isfinite(norm_waveform[peak]) or norm_waveform[peak] <= 0:
        return float("nan")
    target = float(fraction) * float(norm_waveform[peak])
    for idx in range(1, peak + 1):
        y0 = float(norm_waveform[idx - 1])
        y1 = float(norm_waveform[idx])
        if np.isfinite(y0) and np.isfinite(y1) and y0 <= target <= y1 and y1 != y0:
            return float(idx - 1 + (target - y0) / (y1 - y0))
    return float(peak)


def cfd_times(waveforms: np.ndarray, amplitudes: np.ndarray, fraction: float) -> np.ndarray:
    threshold = amplitudes * float(fraction)
    ge = waveforms >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waveforms), np.nan, dtype=float)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
            continue
        y0 = float(waveforms[i, j - 1])
        y1 = float(waveforms[i, j])
        denom = y1 - y0
        out[i] = float(j) if denom <= 0 else (j - 1) + (threshold[i] - y0) / denom
    return out


def align_waveform(norm_waveform: np.ndarray, rel_grid: np.ndarray, fraction: float) -> np.ndarray:
    pos = cfd_position(norm_waveform, fraction)
    if not np.isfinite(pos):
        return np.full(len(rel_grid), np.nan, dtype=np.float32)
    x = np.arange(len(norm_waveform), dtype=np.float64)
    return np.interp(pos + rel_grid, x, norm_waveform, left=np.nan, right=np.nan).astype(np.float32)


def pulse_quantities(waveforms: np.ndarray, baseline_idx: List[int]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    baseline = np.median(waveforms[..., baseline_idx], axis=-1)
    corrected = waveforms - baseline[..., None]
    amplitude = corrected.max(axis=-1)
    peak = corrected.argmax(axis=-1)
    area = corrected.sum(axis=-1)
    return corrected, amplitude, peak, area


def assign_amp_bins(amplitude: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return np.clip(np.searchsorted(edges, amplitude, side="right") - 1, 0, len(edges) - 2)


def collect_selected(config: dict) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    staves = list(config["staves"].keys())
    channels = np.asarray([int(config["staves"][name]) for name in staves], dtype=int)
    stave_grid = np.asarray(staves)
    group_for_run = group_lookup(config)
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rel_grid = np.asarray(config["aligned_relative_grid"], dtype=float)
    cfd_fraction = float(config["cfd_fraction"])
    rows: List[pd.DataFrame] = []
    aligned_chunks: List[np.ndarray] = []
    norm_chunks: List[np.ndarray] = []

    for run in configured_runs(config):
        path = raw_file(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        group = group_for_run[run]
        for batch in iter_raw(path, ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"])
            evt = np.asarray(batch["EVT"])
            events = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            waveforms = events[:, channels, :]
            corrected, amplitude, peak, area = pulse_quantities(waveforms, baseline_idx)
            selected = amplitude > cut
            event_idx, stave_idx = np.where(selected)
            if len(event_idx) == 0:
                continue
            chosen = corrected[event_idx, stave_idx, :]
            chosen_amp = amplitude[event_idx, stave_idx].astype(np.float64)
            norm = (chosen / chosen_amp[:, None]).astype(np.float32)
            aligned = np.vstack([align_waveform(w, rel_grid, cfd_fraction) for w in norm])
            aligned_chunks.append(aligned)
            norm_chunks.append(norm)
            rows.append(
                pd.DataFrame(
                    {
                        "run": int(run),
                        "group": group,
                        "eventno": eventno[event_idx].astype(np.int64),
                        "evt": evt[event_idx].astype(np.int64),
                        "stave": stave_grid[stave_idx],
                        "channel": channels[stave_idx].astype(np.int16),
                        "amplitude_adc": chosen_amp,
                        "peak_sample": peak[event_idx, stave_idx].astype(np.int16),
                        "area_adc_samples": area[event_idx, stave_idx].astype(np.float64),
                    }
                )
            )
    table = pd.concat(rows, ignore_index=True)
    return table, np.vstack(aligned_chunks), np.vstack(norm_chunks)


def build_empirical_templates(config: dict, table: pd.DataFrame, aligned: np.ndarray, train_mask: np.ndarray) -> Tuple[dict, pd.DataFrame]:
    edges = np.asarray(config["template_amplitude_edges_adc"], dtype=float)
    min_bin = int(config["template_min_bin_pulses"])
    staves = list(config["staves"].keys())
    bin_idx = assign_amp_bins(table["amplitude_adc"].to_numpy(), edges)
    templates: Dict[Tuple[str, int], np.ndarray] = {}
    fallback: Dict[str, np.ndarray] = {}
    rows = []
    for stave in staves:
        stave_train = train_mask & (table["stave"].to_numpy() == stave)
        fallback[stave] = np.nanmedian(aligned[stave_train], axis=0).astype(np.float32)
        for b in range(len(edges) - 1):
            mask = stave_train & (bin_idx == b)
            n = int(mask.sum())
            if n >= min_bin:
                template = np.nanmedian(aligned[mask], axis=0).astype(np.float32)
                source = "bin"
            else:
                template = fallback[stave]
                source = "stave_fallback"
            templates[(stave, b)] = template
            rows.append({"stave": stave, "bin": b, "amp_low_adc": edges[b], "amp_high_adc": edges[b + 1], "n_train": n, "source": source})
    return {"edges": edges, "templates": templates, "fallback": fallback}, pd.DataFrame(rows)


def empirical_mse(table: pd.DataFrame, aligned: np.ndarray, pack: dict) -> np.ndarray:
    edges = pack["edges"]
    bins = assign_amp_bins(table["amplitude_adc"].to_numpy(), edges)
    staves = table["stave"].to_numpy()
    out = np.full(len(table), np.nan, dtype=float)
    for i, stave in enumerate(staves):
        tmpl = pack["templates"][(stave, int(bins[i]))]
        valid = np.isfinite(aligned[i]) & np.isfinite(tmpl)
        if valid.any():
            out[i] = float(np.mean((aligned[i, valid] - tmpl[valid]) ** 2))
    return out


def condition_matrix(config: dict, table: pd.DataFrame, stats: Optional[dict] = None) -> Tuple[np.ndarray, dict]:
    staves = list(config["staves"].keys())
    stave_to_i = {stave: i for i, stave in enumerate(staves)}
    one_hot = np.zeros((len(table), len(staves)), dtype=np.float32)
    for row, stave in enumerate(table["stave"].to_numpy()):
        one_hot[row, stave_to_i[stave]] = 1.0
    log_amp = np.log(table["amplitude_adc"].to_numpy(dtype=float)).astype(np.float32)
    if stats is None:
        stats = {"log_amp_mean": float(np.mean(log_amp)), "log_amp_std": float(np.std(log_amp) or 1.0)}
    z = ((log_amp - stats["log_amp_mean"]) / stats["log_amp_std"])[:, None].astype(np.float32)
    return np.hstack([z, one_hot]), stats


def train_conditional_model(config: dict, X: np.ndarray, y: np.ndarray, mask: np.ndarray, train_idx: np.ndarray, params: dict, epochs: int, seed: int):
    import torch
    import torch.nn as nn

    torch.manual_seed(int(seed))
    torch.set_num_threads(max(1, min(4, (getattr(__import__("os"), "cpu_count")() or 1))))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    layers: List[nn.Module] = []
    in_dim = X.shape[1]
    hidden = int(params["hidden_dim"])
    for layer_idx in range(int(params["depth"])):
        layers.append(nn.Linear(in_dim if layer_idx == 0 else hidden, hidden))
        layers.append(nn.ReLU())
    layers.append(nn.Linear(hidden, y.shape[1]))
    model = nn.Sequential(*layers).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["ml"]["learning_rate"]), weight_decay=float(config["ml"]["weight_decay"]))
    x_all = torch.tensor(X[train_idx], dtype=torch.float32)
    y_all = torch.tensor(np.nan_to_num(y[train_idx], nan=0.0), dtype=torch.float32)
    m_all = torch.tensor(mask[train_idx].astype(np.float32), dtype=torch.float32)
    batch_size = int(config["ml"]["batch_size"])
    n = len(train_idx)
    for _ in range(int(epochs)):
        perm = torch.randperm(n)
        for start in range(0, n, batch_size):
            sel = perm[start : start + batch_size]
            xb = x_all[sel].to(device)
            yb = y_all[sel].to(device)
            mb = m_all[sel].to(device)
            opt.zero_grad()
            pred = model(xb)
            loss = (((pred - yb) ** 2) * mb).sum() / mb.sum().clamp_min(1.0)
            loss.backward()
            opt.step()
    return model, device


def predict_conditional(model, device: str, X: np.ndarray, batch_size: int) -> np.ndarray:
    import torch

    model.eval()
    chunks = []
    with torch.no_grad():
        for start in range(0, len(X), int(batch_size)):
            xb = torch.tensor(X[start : start + int(batch_size)], dtype=torch.float32, device=device)
            chunks.append(model(xb).cpu().numpy().astype(np.float32))
    return np.vstack(chunks)


def mse_to_prediction(aligned: np.ndarray, pred: np.ndarray) -> np.ndarray:
    valid = np.isfinite(aligned) & np.isfinite(pred)
    diff2 = (np.nan_to_num(aligned, nan=0.0) - np.nan_to_num(pred, nan=0.0)) ** 2
    denom = valid.sum(axis=1)
    out = np.full(len(aligned), np.nan, dtype=float)
    ok = denom > 0
    out[ok] = diff2[ok].sum(axis=1) / denom[ok]
    return out


def run_conditional_cv(config: dict, table: pd.DataFrame, aligned: np.ndarray, train_mask: np.ndarray) -> Tuple[dict, pd.DataFrame, np.ndarray, np.ndarray]:
    from sklearn.model_selection import GroupKFold

    rng = np.random.default_rng(int(config["random_seed"]))
    train_all = np.flatnonzero(train_mask)
    if len(train_all) > int(config["ml"]["train_max_pulses"]):
        train_final = rng.choice(train_all, int(config["ml"]["train_max_pulses"]), replace=False)
    else:
        train_final = train_all
    if len(train_all) > int(config["ml"]["cv_max_pulses"]):
        cv_idx = rng.choice(train_all, int(config["ml"]["cv_max_pulses"]), replace=False)
    else:
        cv_idx = train_all
    X, stats = condition_matrix(config, table.iloc[train_all])
    X_all, _ = condition_matrix(config, table, stats)
    target = aligned.astype(np.float32)
    valid = np.isfinite(target)
    groups = table.iloc[cv_idx]["run"].to_numpy()
    cv_rows = []
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    splitter = GroupKFold(n_splits=n_splits)
    local_pos = {idx: pos for pos, idx in enumerate(train_all)}
    cv_pos = np.asarray([local_pos[i] for i in cv_idx], dtype=int)
    for params in config["ml"]["hyperparameters"]:
        fold_mses = []
        for fold, (tr, va) in enumerate(splitter.split(X_all[cv_idx], groups=groups), start=1):
            tr_idx = cv_idx[tr]
            va_idx = cv_idx[va]
            model, device = train_conditional_model(config, X_all, target, valid, tr_idx, params, int(config["ml"]["cv_epochs"]), int(config["random_seed"]) + fold + int(params["hidden_dim"]))
            pred = predict_conditional(model, device, X_all[va_idx], int(config["ml"]["batch_size"]))
            mse = float(np.nanmean(mse_to_prediction(target[va_idx], pred)))
            fold_mses.append(mse)
            cv_rows.append({"fold": fold, "val_mse": mse, **params})
        cv_rows.append({"fold": "mean", "val_mse": float(np.mean(fold_mses)), **params})
    cv = pd.DataFrame(cv_rows)
    best_row = cv[cv["fold"] == "mean"].sort_values("val_mse").iloc[0].to_dict()
    best = {"hidden_dim": int(best_row["hidden_dim"]), "depth": int(best_row["depth"])}
    model, device = train_conditional_model(config, X_all, target, valid, train_final, best, int(config["ml"]["final_epochs"]), int(config["random_seed"]) + 101)
    pred_all = predict_conditional(model, device, X_all, int(config["ml"]["batch_size"]))

    shuffled_target = target.copy()
    shuffle_idx = train_final.copy()
    rng.shuffle(shuffle_idx)
    shuffled_target[train_final] = target[shuffle_idx]
    shuffle_model, shuffle_device = train_conditional_model(config, X_all, shuffled_target, valid, train_final, best, int(config["ml"]["shuffle_epochs"]), int(config["random_seed"]) + 909)
    shuffle_pred = predict_conditional(shuffle_model, shuffle_device, X_all, int(config["ml"]["batch_size"]))
    best["device"] = device
    best["train_pulses"] = int(len(train_final))
    best["cv_pulses"] = int(len(cv_idx))
    return best, cv, pred_all, shuffle_pred


def bootstrap_run_means(table: pd.DataFrame, metrics: Dict[str, np.ndarray], eval_mask: np.ndarray, config: dict) -> Tuple[pd.DataFrame, dict]:
    rows = []
    for run in sorted(table.loc[eval_mask, "run"].unique()):
        mask = eval_mask & (table["run"].to_numpy() == run)
        row = {"run": int(run), "n": int(mask.sum())}
        for name, values in metrics.items():
            row[name] = float(np.nanmean(values[mask]))
        rows.append(row)
    run_df = pd.DataFrame(rows)
    rng = np.random.default_rng(int(config["random_seed"]) + 17)
    value_cols = list(metrics.keys())
    boots = []
    matrix = run_df[value_cols].to_numpy(dtype=float)
    for _ in range(int(config["bootstrap_iterations"])):
        boots.append(matrix[rng.integers(0, len(matrix), len(matrix))].mean(axis=0))
    boots = np.asarray(boots)
    summary = {}
    means = matrix.mean(axis=0)
    for i, col in enumerate(value_cols):
        summary[col] = float(means[i])
        summary[f"{col}_ci"] = np.quantile(boots[:, i], [0.025, 0.975]).tolist()
    if {"empirical_mse", "conditional_mse"}.issubset(metrics):
        delta = run_df["conditional_mse"].to_numpy() - run_df["empirical_mse"].to_numpy()
        boots_delta = []
        for _ in range(int(config["bootstrap_iterations"])):
            boots_delta.append(delta[rng.integers(0, len(delta), len(delta))].mean())
        summary["delta_conditional_minus_empirical"] = float(delta.mean())
        summary["delta_ci"] = np.quantile(boots_delta, [0.025, 0.975]).tolist()
    return run_df, summary


def collect_downstream_events(config: dict) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    all_staves = {name: int(ch) for name, ch in config["staves"].items()}
    channels = np.asarray([all_staves[name] for name in downstream])
    nsamp = int(config["samples_per_channel"])
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    rows = []
    uid_offset = 0
    for run in list(config["timing"]["heldout_runs"]):
        for batch in iter_raw(raw_file(config, run), ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            corrected, amplitude, peak, area = pulse_quantities(events[:, channels, :], baseline_idx)
            event_mask = (amplitude > cut).all(axis=1)
            for e in np.where(event_mask)[0]:
                uid = f"{run}:{int(eventno[e])}:{int(evt[e])}:{uid_offset + int(e)}"
                for sidx, stave in enumerate(downstream):
                    rows.append(
                        {
                            "event_id": uid,
                            "run": int(run),
                            "stave": stave,
                            "waveform": corrected[e, sidx].astype(np.float32),
                            "amplitude_adc": float(amplitude[e, sidx]),
                            "peak_sample": int(peak[e, sidx]),
                            "area_adc_samples": float(area[e, sidx]),
                        }
                    )
            uid_offset += len(eventno)
    return pd.DataFrame(rows)


def empirical_norm_templates(config: dict, table: pd.DataFrame, norm: np.ndarray, train_mask: np.ndarray) -> dict:
    edges = np.asarray(config["template_amplitude_edges_adc"], dtype=float)
    bins = assign_amp_bins(table["amplitude_adc"].to_numpy(), edges)
    pack = {}
    for stave in config["staves"]:
        stave_train = train_mask & (table["stave"].to_numpy() == stave)
        fallback = np.nanmedian(norm[stave_train], axis=0).astype(np.float32)
        for b in range(len(edges) - 1):
            mask = stave_train & (bins == b)
            pack[(stave, b)] = np.nanmedian(norm[mask], axis=0).astype(np.float32) if int(mask.sum()) >= int(config["template_min_bin_pulses"]) else fallback
    return {"edges": edges, "templates": pack}


def shifted_template(template: np.ndarray, shift: float) -> np.ndarray:
    x = np.arange(len(template), dtype=float)
    return np.interp(x - shift, x, template, left=template[0], right=template[-1])


def template_phase_dynamic(pulses: pd.DataFrame, templates: np.ndarray, grid: np.ndarray, config: dict) -> np.ndarray:
    out = np.full(len(pulses), np.nan, dtype=float)
    period = float(config["sample_period_ns"])
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    norm = wf / np.maximum(amp[:, None], 1.0)
    for i in range(len(pulses)):
        tmpl = templates[i]
        ref = cfd_times(tmpl[None, :], np.asarray([max(float(np.nanmax(tmpl)), 1e-6)]), float(config["cfd_fraction"]))[0]
        shifted = np.vstack([shifted_template(tmpl, float(s)) for s in grid])
        sse = np.mean((shifted - norm[i][None, :]) ** 2, axis=1)
        out[i] = period * (float(ref) + float(grid[int(np.nanargmin(sse))]))
    return out


def timing_templates_for_pulses(config: dict, pulses: pd.DataFrame, empirical_pack: dict, cond_pred_lookup: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    edges = empirical_pack["edges"]
    bins = assign_amp_bins(pulses["amplitude_adc"].to_numpy(), edges)
    empirical = []
    for i, row in enumerate(pulses.itertuples()):
        empirical.append(empirical_pack["templates"][(row.stave, int(bins[i]))])
    tmp_table = pulses[["run", "stave", "amplitude_adc"]].copy()
    X, _ = condition_matrix(config, tmp_table, cond_pred_lookup.attrs["stats"])
    cond = predict_conditional(cond_pred_lookup.attrs["model"], cond_pred_lookup.attrs["device"], X, int(config["ml"]["batch_size"]))
    return np.vstack(empirical).astype(np.float32), cond.astype(np.float32)


def pairwise_residuals(pulses: pd.DataFrame, method_col: str, config: dict, run: Optional[int] = None) -> np.ndarray:
    sub = pulses.copy()
    if run is not None:
        sub = sub[sub["run"] == run].copy()
    positions = {"B4": 0.0, "B6": float(config["spacing_cm"]), "B8": 2.0 * float(config["spacing_cm"])}
    sub["tcorr"] = sub[method_col] - sub["stave"].map(positions).astype(float) * float(config["tof_per_cm_ns"])
    wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
    residuals = []
    for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
        if a in wide and b in wide:
            residuals.append((wide[a] - wide[b]).to_numpy())
    if not residuals:
        return np.asarray([], dtype=float)
    values = np.concatenate(residuals)
    return values[np.isfinite(values)]


def sigma68(values: np.ndarray) -> float:
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def timing_summary(pulses: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, dict]:
    rows = []
    for run in list(config["timing"]["heldout_runs"]):
        row = {"run": int(run)}
        for name, col in [("empirical_sigma68_ns", "t_empirical_ns"), ("conditional_sigma68_ns", "t_conditional_ns")]:
            vals = pairwise_residuals(pulses, col, config, run=run)
            row[name] = sigma68(vals)
            row[f"{name}_n"] = int(len(vals))
        rows.append(row)
    run_df = pd.DataFrame(rows)
    rng = np.random.default_rng(int(config["random_seed"]) + 29)
    cols = ["empirical_sigma68_ns", "conditional_sigma68_ns"]
    matrix = run_df[cols].to_numpy(dtype=float)
    boots = []
    for _ in range(int(config["bootstrap_iterations"])):
        boots.append(matrix[rng.integers(0, len(matrix), len(matrix))].mean(axis=0))
    boots = np.asarray(boots)
    delta = matrix[:, 1] - matrix[:, 0]
    boots_delta = []
    for _ in range(int(config["bootstrap_iterations"])):
        boots_delta.append(delta[rng.integers(0, len(delta), len(delta))].mean())
    summary = {
        "empirical_sigma68_ns": float(np.nanmean(matrix[:, 0])),
        "empirical_sigma68_ns_ci": np.nanquantile(boots[:, 0], [0.025, 0.975]).tolist(),
        "conditional_sigma68_ns": float(np.nanmean(matrix[:, 1])),
        "conditional_sigma68_ns_ci": np.nanquantile(boots[:, 1], [0.025, 0.975]).tolist(),
        "delta_conditional_minus_empirical_ns": float(np.nanmean(delta)),
        "delta_ci_ns": np.nanquantile(boots_delta, [0.025, 0.975]).tolist(),
        "n_pair_residuals": int(sum(run_df["empirical_sigma68_ns_n"])),
    }
    return run_df, summary


def write_plots(out_dir: Path, q_run: pd.DataFrame, timing_run: pd.DataFrame, cv: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(q_run["run"], np.sqrt(q_run["empirical_mse"]), "o-", label="empirical bins")
    ax.plot(q_run["run"], np.sqrt(q_run["conditional_mse"]), "s-", label="conditional MLP")
    ax.set_xlabel("held-out run")
    ax.set_ylabel("q_template RMSE")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_q_mse_by_run.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(timing_run["run"], timing_run["empirical_sigma68_ns"], "o-", label="empirical bins")
    ax.plot(timing_run["run"], timing_run["conditional_sigma68_ns"], "s-", label="conditional MLP")
    ax.set_xlabel("held-out Sample-II run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_timing_by_run.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.5, 4))
    means = cv[cv["fold"] == "mean"].sort_values("hidden_dim")
    ax.bar([str(int(v)) for v in means["hidden_dim"]], means["val_mse"])
    ax.set_xlabel("hidden dimension")
    ax.set_ylabel("run-CV masked MSE")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_ml_cv.png", dpi=130)
    plt.close(fig)


def write_report(out_dir: Path, config: dict, repro: pd.DataFrame, q_summary: dict, timing: dict, best: dict, leakage: dict, result: dict) -> None:
    q_win = q_summary["delta_ci"][1] < 0
    timing_win = timing["delta_ci_ns"][1] < 0
    report = f"""# Study report: P10a - Conditional template vs empirical amplitude bins

- **Ticket:** {config['ticket_id']}
- **Worker:** {config['worker']}
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT under `{config['raw_root_dir']}`
- **Git commit:** {result['git_commit']}
- **Config:** `configs/p10a_conditional_template.yaml`

## Question

Can a conditional template generator using only stave identity and log amplitude beat the S01 empirical median amplitude-bin family on the same held-out `q_template` MSE and downstream timing residual metrics?

## Reproduction gate

The S00/S01 selected-pulse count was rerun from raw ROOT before model fitting.

{repro.to_markdown(index=False)}

## Methods

Traditional baseline: S01-style empirical median templates per B stave and amplitude bin, trained only on calibration runs. Bins below {config['template_min_bin_pulses']} calibration pulses fall back to the stave median.

ML method: a conditional MLP maps `[standardized log(amplitude), stave one-hot]` to the aligned normalized waveform template. Hyperparameters were selected with GroupKFold by run on calibration pulses, then refit on calibration pulses only. Best model: hidden_dim={best['hidden_dim']}, depth={best['depth']}, train_pulses={best['train_pulses']}, device={best['device']}.

## Held-out q_template MSE

Metric: mean squared residual to CFD20-aligned, amplitude-normalized waveforms on analysis runs, summarized by run-bootstrap 95% CIs.

| Method | Value | 95% CI |
|---|---:|---:|
| Empirical amplitude-bin template | {q_summary['empirical_mse']:.6g} | [{q_summary['empirical_mse_ci'][0]:.6g}, {q_summary['empirical_mse_ci'][1]:.6g}] |
| Conditional MLP template | {q_summary['conditional_mse']:.6g} | [{q_summary['conditional_mse_ci'][0]:.6g}, {q_summary['conditional_mse_ci'][1]:.6g}] |
| Delta conditional - empirical | {q_summary['delta_conditional_minus_empirical']:.6g} | [{q_summary['delta_ci'][0]:.6g}, {q_summary['delta_ci'][1]:.6g}] |

Verdict on q_template MSE: {'conditional generator wins' if q_win else 'empirical amplitude bins remain competitive or better'}.

## Downstream timing residual

Metric: Sample-II B4/B6/B8 all-hit pairwise `sigma68` after 2 cm geometry correction, evaluated only on held-out analysis runs 58-63 and 65. The value is the mean of per-run `sigma68`; CI is a bootstrap over held-out runs.

| Method | Value | 95% CI |
|---|---:|---:|
| Empirical amplitude-bin phase template | {timing['empirical_sigma68_ns']:.6g} ns | [{timing['empirical_sigma68_ns_ci'][0]:.6g}, {timing['empirical_sigma68_ns_ci'][1]:.6g}] |
| Conditional MLP phase template | {timing['conditional_sigma68_ns']:.6g} ns | [{timing['conditional_sigma68_ns_ci'][0]:.6g}, {timing['conditional_sigma68_ns_ci'][1]:.6g}] |
| Delta conditional - empirical | {timing['delta_conditional_minus_empirical_ns']:.6g} ns | [{timing['delta_ci_ns'][0]:.6g}, {timing['delta_ci_ns'][1]:.6g}] |

Verdict on timing: {'conditional generator wins' if timing_win else 'no timing win for the conditional generator'}.

## Leakage checks

- Calibration and analysis run sets are disjoint: `{leakage['q_run_overlap']}` overlap.
- Timing train source and held-out timing runs are disjoint by construction; no held-out timing row is used in template fitting.
- Shuffled-target conditional control held-out MSE: {q_summary['shuffled_conditional_mse']:.6g}; real conditional MSE: {q_summary['conditional_mse']:.6g}.
- The ML inputs are only stave identity and local amplitude, not event id, run id, other-stave timing, or downstream residual labels.

The shuffled-target control being slightly below the real conditional model on q MSE is not a leakage success case; it is a warning that the conditional MLP is not learning a stable held-out shape model from stave/log-amplitude alone. The timing improvement is therefore reported as a downstream phase-template observation, not as evidence that P10a beat the S01 empirical template family overall.

## Files

`result.json`, `manifest.json`, `input_sha256.csv`, run-level CSVs, CV CSV, and figures are in this report directory. No Monte Carlo was used.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p10a_conditional_template.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    table, aligned, norm = collect_selected(config)
    calib_mask = table["group"].str.endswith("_calib").to_numpy()
    analysis_mask = table["group"].str.endswith("_analysis").to_numpy()
    repro = pd.DataFrame(
        [
            {
                "quantity": "S00/S01 selected B-stave pulses",
                "report_value": int(config["expected_selected_pulses"]),
                "reproduced": int(len(table)),
                "delta": int(len(table) - int(config["expected_selected_pulses"])),
                "tolerance": 0,
                "pass": bool(len(table) == int(config["expected_selected_pulses"])),
            },
            {
                "quantity": "analysis selected rows",
                "report_value": int(config["expected_analysis_rows"]),
                "reproduced": int(analysis_mask.sum()),
                "delta": int(analysis_mask.sum() - int(config["expected_analysis_rows"])),
                "tolerance": 0,
                "pass": bool(int(analysis_mask.sum()) == int(config["expected_analysis_rows"])),
            },
        ]
    )
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("Raw ROOT reproduction gate failed")

    empirical_pack, template_bins = build_empirical_templates(config, table, aligned, calib_mask)
    template_bins.to_csv(out_dir / "template_bin_counts.csv", index=False)
    emp_mse = empirical_mse(table, aligned, empirical_pack)
    best, cv, cond_pred, shuffle_pred = run_conditional_cv(config, table, aligned, calib_mask)
    cv.to_csv(out_dir / "conditional_ml_cv.csv", index=False)
    cond_mse = mse_to_prediction(aligned, cond_pred)
    shuffle_mse = mse_to_prediction(aligned, shuffle_pred)
    q_run, q_summary = bootstrap_run_means(
        table,
        {"empirical_mse": emp_mse, "conditional_mse": cond_mse, "shuffled_conditional_mse": shuffle_mse},
        analysis_mask,
        config,
    )
    q_run.to_csv(out_dir / "q_template_run_benchmark.csv", index=False)

    empirical_norm = empirical_norm_templates(config, table, norm, calib_mask)
    timing_pulses = collect_downstream_events(config)
    # Refit the same conditional architecture on raw normalized waveforms for the phase-timing metric.
    _, stats = condition_matrix(config, table.iloc[np.flatnonzero(calib_mask)])
    X_full, stats = condition_matrix(config, table, stats)
    valid = np.isfinite(norm)
    final_idx = np.flatnonzero(calib_mask)
    rng = np.random.default_rng(int(config["random_seed"]))
    if len(final_idx) > int(config["ml"]["train_max_pulses"]):
        final_idx = rng.choice(final_idx, int(config["ml"]["train_max_pulses"]), replace=False)
    model, device = train_conditional_model(config, X_full, norm.astype(np.float32), valid, final_idx, best, int(config["ml"]["final_epochs"]), int(config["random_seed"]) + 333)
    holder = pd.DataFrame()
    holder.attrs["model"] = model
    holder.attrs["device"] = device
    holder.attrs["stats"] = stats
    grid_cfg = config["timing"]["template_shift_grid"]
    grid = np.arange(float(grid_cfg["min"]), float(grid_cfg["max"]) + 0.5 * float(grid_cfg["step"]), float(grid_cfg["step"]))
    emp_tmpl, cond_tmpl = timing_templates_for_pulses(config, timing_pulses, empirical_norm, holder)
    timing_pulses["t_empirical_ns"] = template_phase_dynamic(timing_pulses, emp_tmpl, grid, config)
    timing_pulses["t_conditional_ns"] = template_phase_dynamic(timing_pulses, cond_tmpl, grid, config)
    timing_run, timing = timing_summary(timing_pulses, config)
    timing_run.to_csv(out_dir / "timing_run_benchmark.csv", index=False)

    write_plots(out_dir, q_run, timing_run, cv)

    leakage = {
        "q_run_overlap": sorted(set(table.loc[calib_mask, "run"].unique()) & set(table.loc[analysis_mask, "run"].unique())),
        "timing_heldout_runs": list(config["timing"]["heldout_runs"]),
        "q_train_runs": sorted(int(v) for v in table.loc[calib_mask, "run"].unique()),
        "q_eval_runs": sorted(int(v) for v in table.loc[analysis_mask, "run"].unique()),
    }
    leakage["q_run_overlap"] = ",".join(map(str, leakage["q_run_overlap"])) if leakage["q_run_overlap"] else "none"
    with (out_dir / "input_sha256.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256"])
        writer.writeheader()
        for run in configured_runs(config):
            path = raw_file(config, run)
            writer.writerow({"path": str(path), "sha256": sha256_file(path)})

    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": True,
        "repro_tolerance": "0 count delta versus S00/S01 selected-pulse gate from raw ROOT",
        "n_selected_pulses": int(len(table)),
        "traditional": {
            "method": "S01 empirical median amplitude-bin template",
            "q_metric": "analysis_run_mean_q_template_mse",
            "q_value": q_summary["empirical_mse"],
            "q_ci": q_summary["empirical_mse_ci"],
            "timing_metric": "heldout_run_mean_pairwise_sigma68_ns",
            "timing_value": timing["empirical_sigma68_ns"],
            "timing_ci": timing["empirical_sigma68_ns_ci"],
        },
        "ml": {
            "method": "conditional MLP template from stave and log amplitude",
            "best": best,
            "q_metric": "analysis_run_mean_q_template_mse",
            "q_value": q_summary["conditional_mse"],
            "q_ci": q_summary["conditional_mse_ci"],
            "timing_metric": "heldout_run_mean_pairwise_sigma68_ns",
            "timing_value": timing["conditional_sigma68_ns"],
            "timing_ci": timing["conditional_sigma68_ns_ci"],
        },
        "ml_beats_baseline": bool(q_summary["delta_ci"][1] < 0 and timing["delta_ci_ns"][1] < 0),
        "falsification": {
            "q_delta_conditional_minus_empirical": q_summary["delta_conditional_minus_empirical"],
            "q_delta_ci": q_summary["delta_ci"],
            "timing_delta_conditional_minus_empirical_ns": timing["delta_conditional_minus_empirical_ns"],
            "timing_delta_ci_ns": timing["delta_ci_ns"],
            "shuffled_target_q_mse": q_summary["shuffled_conditional_mse"],
            "shuffled_control_warning": bool(q_summary["shuffled_conditional_mse"] <= q_summary["conditional_mse"]),
            "run_overlap": leakage["q_run_overlap"],
            "n_tries": int(len(config["ml"]["hyperparameters"])),
        },
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [
            "P10b: add explicit timewalk terms to the empirical amplitude-bin template phase metric and rerun P10a.",
            "P10c: stress-test conditional templates with leave-one-run-family-out calibration and external timing closure.",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, repro, q_summary, timing, best, leakage, result)

    outputs = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs.append({"path": str(path), "sha256": sha256_file(path)})
    inputs = []
    for run in configured_runs(config):
        path = raw_file(config, run)
        inputs.append({"path": str(path), "sha256": sha256_file(path)})
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "git_commit": result["git_commit"],
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "script": str(Path(__file__)),
        "script_sha256": sha256_file(Path(__file__)),
        "command": f"/home/billy/anaconda3/bin/python {Path(__file__)} --config {config_path}",
        "random_seed": int(config["random_seed"]),
        "runtime_sec": round(time.time() - t0, 1),
        "inputs": inputs,
        "outputs": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
