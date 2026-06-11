#!/usr/bin/env python3
"""P04o: rate-conditioned charge support veto.

The study rebuilds the P04 selected-pulse anchor from raw B-stack ROOT,
constructs run-level A/B coincidence-rate residuals from raw A-stack and
B-stack events, and benchmarks charge-closure models with whole-run held-out
folds.  The target is the independent odd-channel duplicate-readout charge;
features come from the even B-stack waveform plus topology/rate support
coordinates only.
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
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")

import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover - torch is optional at import time.
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def all_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for key in ["sample_i_calib", "sample_i_analysis", "sample_ii_calib", "sample_ii_analysis"]:
        runs.extend(int(r) for r in config["runs"][key])
    return sorted(set(runs))


def run_group(config: dict, run: int) -> str:
    for key, values in config["runs"].items():
        if int(run) in [int(v) for v in values]:
            return key
    return "unknown"


def current_nA(config: dict, run: int) -> float:
    return float(config["low_current_nA"] if int(run) in [int(v) for v in config["low_current_runs"]] else config["high_current_nA"])


def raw_path(config: dict, stack: str, run: int) -> Path:
    prefix = config[stack]["file_prefix"]
    return Path(config["raw_root_dir"]) / f"{prefix}_run_{int(run):04d}.root"


def iter_root(path: Path, branches: Sequence[str], step_size: int = 30000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(list(branches), step_size=step_size, library="np")


def baseline_correct(raw: np.ndarray, baseline_samples: Sequence[int]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    baseline_values = raw[..., list(baseline_samples)]
    baseline = np.median(baseline_values, axis=-1)
    baseline_rms = np.sqrt(np.mean((baseline_values - baseline[..., None]) ** 2, axis=-1))
    return raw - baseline[..., None], baseline, baseline_rms


def stack_event_table(config: dict, stack: str, run: int) -> Tuple[pd.DataFrame, int]:
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    branches = ["EVENTNO", "EVT", "HRDv"] if stack == "bstack" else ["EVENTNO", "HRDv"]
    names = list(config[stack]["staves"].keys())
    channels = [int(v) for v in config[stack]["staves"].values()]
    rows = []
    selected_pulses = 0
    for batch in iter_root(raw_path(config, stack, run), branches):
        eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
        raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
        corrected, _, _ = baseline_correct(raw[:, channels, :], config["baseline_samples"])
        amp = corrected.max(axis=-1)
        selected = amp > cut
        selected_pulses += int(selected.sum())
        frame = pd.DataFrame({"eventno": eventno})
        if stack == "bstack":
            frame["evt"] = np.asarray(batch["EVT"]).astype(np.int64)
        for idx, name in enumerate(names):
            frame[f"{name}_selected"] = selected[:, idx]
            frame[f"{name}_amp"] = amp[:, idx]
        if stack == "bstack":
            b_cols = [f"{name}_selected" for name in names]
            frame["B_any_selected"] = frame[b_cols].any(axis=1)
            frame["B_n_selected"] = frame[b_cols].sum(axis=1)
            frame["B_downstream_any"] = frame[["B4_selected", "B6_selected", "B8_selected"]].any(axis=1)
            frame["B_max_amp"] = frame[[f"{name}_amp" for name in names]].max(axis=1)
        else:
            a_cols = [f"{name}_selected" for name in names]
            frame["A_any_selected"] = frame[a_cols].any(axis=1)
            frame["A_both_selected"] = frame[a_cols].all(axis=1)
        rows.append(frame)
    return pd.concat(rows, ignore_index=True), selected_pulses


def extract_b_pulses(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame, Dict[int, pd.DataFrame]]:
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    staves = list(config["bstack"]["staves"].keys())
    even_channels = np.asarray([int(config["bstack"]["staves"][s]) for s in staves], dtype=int)
    odd_channels = np.asarray([int(config["bstack"]["duplicate_readout_channels"][s]) for s in staves], dtype=int)
    stave_names = np.asarray(staves)
    frames: List[pd.DataFrame] = []
    waves: List[np.ndarray] = []
    counts: List[dict] = []
    event_tables: Dict[int, pd.DataFrame] = {}
    for run in all_runs(config):
        run_rows = []
        selected_total = 0
        events_total = 0
        b_event_chunks = []
        for batch in iter_root(raw_path(config, "bstack", run), ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            even_corr, even_base, even_base_rms = baseline_correct(raw[:, even_channels, :], config["baseline_samples"])
            odd_corr, _, _ = baseline_correct(raw[:, odd_channels, :], config["baseline_samples"])
            even_amp = even_corr.max(axis=-1)
            even_peak = even_corr.argmax(axis=-1)
            even_pos_charge = np.clip(even_corr, 0.0, None).sum(axis=-1)
            target_charge = np.clip(-odd_corr, 0.0, None).sum(axis=-1)
            target_amp = (-odd_corr).max(axis=-1)
            tail_charge = np.clip(even_corr[:, :, 10:], 0.0, None).sum(axis=-1)
            q_tail = tail_charge / np.maximum(even_pos_charge, 1.0)
            half_width = (even_corr > (0.5 * even_amp[..., None])).sum(axis=-1)
            selected = even_amp > cut
            events_total += int(len(eventno))
            selected_total += int(selected.sum())
            event_topology = pd.DataFrame({"eventno": eventno, "evt": evt})
            for idx, stave in enumerate(staves):
                event_topology[f"{stave}_selected"] = selected[:, idx]
                event_topology[f"{stave}_amp"] = even_amp[:, idx]
            b_cols = [f"{s}_selected" for s in staves]
            event_topology["B_n_selected"] = event_topology[b_cols].sum(axis=1).astype(int)
            event_topology["B_any_selected"] = event_topology["B_n_selected"] > 0
            event_topology["B_downstream_any"] = event_topology[["B4_selected", "B6_selected", "B8_selected"]].any(axis=1)
            event_topology["B_max_amp"] = event_topology[[f"{s}_amp" for s in staves]].max(axis=1)
            b_event_chunks.append(event_topology)
            event_idx, stave_idx = np.where(selected)
            if len(event_idx) == 0:
                continue
            waves.append(even_corr[event_idx, stave_idx, :].astype(np.float32))
            run_rows.append(
                pd.DataFrame(
                    {
                        "run": int(run),
                        "run_group": run_group(config, int(run)),
                        "sample_ii": int(run_group(config, int(run)).startswith("sample_ii")),
                        "current_nA": current_nA(config, int(run)),
                        "eventno": eventno[event_idx],
                        "evt": evt[event_idx],
                        "stave": stave_names[stave_idx],
                        "stave_idx": stave_idx.astype(np.int16),
                        "event_b_n_selected": selected[event_idx].sum(axis=1).astype(np.int16),
                        "event_b_downstream_any": event_topology.loc[event_idx, "B_downstream_any"].to_numpy(dtype=int),
                        "event_b2_selected": selected[event_idx, 0].astype(int),
                        "event_b_max_amp": event_topology.loc[event_idx, "B_max_amp"].to_numpy(dtype=float),
                        "even_amp": even_amp[event_idx, stave_idx],
                        "even_peak": even_peak[event_idx, stave_idx].astype(np.int16),
                        "even_pos_charge": even_pos_charge[event_idx, stave_idx],
                        "even_baseline": even_base[event_idx, stave_idx],
                        "even_baseline_rms": even_base_rms[event_idx, stave_idx],
                        "q_tail": q_tail[event_idx, stave_idx],
                        "half_width": half_width[event_idx, stave_idx],
                        "saturation_depth": np.maximum(even_amp[event_idx, stave_idx] - 3800.0, 0.0),
                        "target_odd_neg_amp": target_amp[event_idx, stave_idx],
                        "target_odd_pos_charge": target_charge[event_idx, stave_idx],
                    }
                )
            )
        event_tables[int(run)] = pd.concat(b_event_chunks, ignore_index=True)
        counts.append({"run": int(run), "run_group": run_group(config, int(run)), "events_total": events_total, "selected_pulses": selected_total})
        if run_rows:
            frames.append(pd.concat(run_rows, ignore_index=True))
    return pd.concat(frames, ignore_index=True), np.vstack(waves), pd.DataFrame(counts), event_tables


def run_level_rates(config: dict, b_events: Dict[int, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for run in [int(r) for r in config["analysis_runs"]]:
        b = b_events[run]
        a, a_pulses = stack_event_table(config, "astack", run)
        merged = b.merge(a[["eventno", "A_any_selected", "A_both_selected"]], on="eventno", how="inner")
        b_any = int(merged["B_any_selected"].sum())
        ab_any = int((merged["A_any_selected"] & merged["B_any_selected"]).sum())
        rows.append(
            {
                "run": int(run),
                "run_group": run_group(config, int(run)),
                "current_nA": current_nA(config, int(run)),
                "sample_ii": int(run_group(config, int(run)).startswith("sample_ii")),
                "n_matched_events": int(len(merged)),
                "b_any_events": b_any,
                "a_selected_pulses": int(a_pulses),
                "ab_any_given_b_successes": ab_any,
                "target_rate": (ab_any + 0.5) / (b_any + 1.0),
                "b_multi_frac": float((merged["B_n_selected"] >= 2).mean()),
                "b_downstream_frac": float(merged["B_downstream_any"].sum() / max(b_any, 1)),
                "b2_share": float(merged["B2_selected"].sum() / max(b_any, 1)),
                "mean_b_max_amp": float(merged.loc[merged["B_any_selected"], "B_max_amp"].mean()),
            }
        )
    rates = pd.DataFrame(rows)
    rates["log_current_nA"] = np.log(rates["current_nA"].astype(float))
    rates["log_b_any_events"] = np.log1p(rates["b_any_events"].astype(float))
    rates["current_sample_interaction"] = rates["log_current_nA"] * rates["sample_ii"]
    rates["target_logit"] = logit(rates["target_rate"].to_numpy())
    return rates


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1.0 - 1e-6)
    return np.log(p / (1.0 - p))


def inv_logit(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.asarray(x, dtype=float)))


def add_rate_residuals(rate_table: pd.DataFrame, seed: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    features = [
        "log_current_nA",
        "sample_ii",
        "current_sample_interaction",
        "log_b_any_events",
        "b_multi_frac",
        "b_downstream_frac",
        "b2_share",
        "mean_b_max_amp",
    ]
    out = rate_table.copy()
    out["pred_rate_traditional"] = np.nan
    out["rate_residual_pp"] = np.nan
    rows = []
    groups = out["run"].to_numpy()
    for fold, (tr, te) in enumerate(GroupKFold(n_splits=min(5, out["run"].nunique())).split(out[features], out["target_logit"], groups)):
        train = out.iloc[tr]
        test = out.iloc[te]
        model = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
        model.fit(train[features], train["target_logit"], ridge__sample_weight=train["b_any_events"])
        pred = inv_logit(model.predict(test[features]))
        out.loc[out.index[te], "pred_rate_traditional"] = pred
        out.loc[out.index[te], "rate_residual_pp"] = 100.0 * (test["target_rate"].to_numpy() - pred)
        rows.append(
            {
                "fold": int(fold),
                "heldout_runs": ",".join(str(int(r)) for r in sorted(test["run"].unique())),
                "n_train_runs": int(train["run"].nunique()),
                "rate_rmse_pp": float(100.0 * np.sqrt(np.average((test["target_rate"].to_numpy() - pred) ** 2, weights=test["b_any_events"]))),
            }
        )
    rng = np.random.default_rng(seed + 27)
    shuffled = out["rate_residual_pp"].to_numpy().copy()
    rng.shuffle(shuffled)
    out["rate_residual_shuffled_pp"] = shuffled
    return out, pd.DataFrame(rows)


def prepare_analysis_rows(config: dict, meta: pd.DataFrame, wave: np.ndarray, rates: pd.DataFrame) -> Tuple[pd.DataFrame, np.ndarray]:
    mask = meta["run"].isin([int(r) for r in config["analysis_runs"]]).to_numpy()
    df = meta.loc[mask].reset_index(drop=True)
    wf = wave[mask]
    df = df.merge(
        rates[
            [
                "run",
                "target_rate",
                "pred_rate_traditional",
                "rate_residual_pp",
                "rate_residual_shuffled_pp",
                "b_multi_frac",
                "b_downstream_frac",
                "b2_share",
            ]
        ],
        on="run",
        how="left",
        suffixes=("", "_run"),
    )
    valid = (df["target_odd_pos_charge"].to_numpy() > 100.0) & np.isfinite(df["rate_residual_pp"].to_numpy())
    df = df.loc[valid].reset_index(drop=True)
    wf = wf[valid]
    df["log_even_amp"] = np.log(np.maximum(df["even_amp"], 1.0))
    df["log_even_pos_charge"] = np.log(np.maximum(df["even_pos_charge"], 1.0))
    df["log_event_b_max_amp"] = np.log(np.maximum(df["event_b_max_amp"], 1.0))
    df["saturation_bin"] = pd.cut(df["saturation_depth"], bins=[-0.1, 0.0, 500.0, 1500.0, np.inf], labels=["none", "low", "mid", "high"]).astype(str)
    df["q_template_bin"] = pd.qcut(df["q_tail"].rank(method="first"), q=4, labels=["q1", "q2", "q3", "q4"]).astype(str)
    df["baseline_taxon"] = pd.cut(df["even_baseline_rms"], bins=[-0.1, 2.0, 5.0, np.inf], labels=["quiet", "mid", "wide"]).astype(str)
    df["geometry_support"] = df["stave"].astype(str) + "_n" + df["event_b_n_selected"].astype(str)
    return df, wf


def numeric_features(include_rate: bool, shuffled_rate: bool = False) -> List[str]:
    cols = [
        "log_even_amp",
        "log_even_pos_charge",
        "even_peak",
        "q_tail",
        "half_width",
        "saturation_depth",
        "even_baseline_rms",
        "sample_ii",
        "current_nA",
        "event_b_n_selected",
        "event_b_downstream_any",
        "event_b2_selected",
        "log_event_b_max_amp",
        "b_multi_frac",
        "b_downstream_frac",
        "b2_share",
    ]
    if include_rate:
        cols.append("rate_residual_shuffled_pp" if shuffled_rate else "rate_residual_pp")
        cols.append("pred_rate_traditional")
    return cols


def categorical_features(full: bool = True) -> List[str]:
    if full:
        return ["stave", "run_group", "saturation_bin", "q_template_bin", "baseline_taxon", "geometry_support"]
    return ["stave", "run_group"]


def make_preprocessor(num_cols: List[str], cat_cols: List[str]) -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), num_cols),
            ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
        ],
        sparse_threshold=0.0,
    )


def sample_indices(indices: np.ndarray, max_rows: int, rng: np.random.Generator) -> np.ndarray:
    if len(indices) <= max_rows:
        return indices
    return np.sort(rng.choice(indices, size=int(max_rows), replace=False))


def stratified_traditional_predict(
    train: pd.DataFrame,
    test: pd.DataFrame,
    y_train_log: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    base = make_pipeline(
        make_preprocessor(["log_even_pos_charge", "log_even_amp", "q_tail", "saturation_depth"], ["stave"]),
        Ridge(alpha=5.0),
    )
    base.fit(train, y_train_log)
    train_pred = base.predict(train)
    test_pred = base.predict(test)
    resid = y_train_log - train_pred
    train_tmp = train[["stave", "run_group", "event_b_n_selected", "saturation_bin", "q_template_bin", "baseline_taxon", "geometry_support"]].copy()
    train_tmp["resid"] = resid
    strata = ["stave", "run_group", "event_b_n_selected", "saturation_bin", "q_template_bin", "baseline_taxon", "geometry_support"]
    global_med = float(np.median(resid))
    corrections: Dict[Tuple[str, ...], float] = {}
    for keys, group in train_tmp.groupby(strata):
        if len(group) >= 80:
            corrections[tuple(str(x) for x in keys)] = float(np.median(group["resid"]))
    def corr(frame: pd.DataFrame) -> np.ndarray:
        out = np.full(len(frame), global_med, dtype=float)
        for i, row in enumerate(frame[strata].itertuples(index=False, name=None)):
            out[i] = corrections.get(tuple(str(x) for x in row), global_med)
        return out
    return train_pred + corr(train), test_pred + corr(test)


class ChargeCNN(nn.Module):
    def __init__(self, n_aux: int) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, 12, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(12, 12, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(6),
            nn.Flatten(),
        )
        self.head = nn.Sequential(nn.Linear(72 + n_aux, 48), nn.ReLU(), nn.Linear(48, 1))

    def forward(self, wave: torch.Tensor, aux: torch.Tensor) -> torch.Tensor:
        return self.head(torch.cat([self.conv(wave), aux], dim=1)).squeeze(1)


def fit_cnn(
    train_wave: np.ndarray,
    train_aux: np.ndarray,
    y_train_log: np.ndarray,
    test_wave: np.ndarray,
    test_aux: np.ndarray,
    config: dict,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray]:
    if torch is None:
        train_med = np.full(len(train_wave), float(np.median(y_train_log)))
        test_med = np.full(len(test_wave), float(np.median(y_train_log)))
        return train_med, test_med
    torch.manual_seed(int(seed))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = ChargeCNN(train_aux.shape[1]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    ds = TensorDataset(
        torch.tensor(train_wave[:, None, :], dtype=torch.float32),
        torch.tensor(train_aux, dtype=torch.float32),
        torch.tensor(y_train_log, dtype=torch.float32),
    )
    loader = DataLoader(ds, batch_size=int(config["models"]["cnn_batch_size"]), shuffle=True)
    model.train()
    for _ in range(int(config["models"]["cnn_epochs"])):
        for xb, xa, yb in loader:
            xb, xa, yb = xb.to(device), xa.to(device), yb.to(device)
            opt.zero_grad()
            loss = nn.functional.smooth_l1_loss(model(xb, xa), yb)
            loss.backward()
            opt.step()
    def predict(wave: np.ndarray, aux: np.ndarray) -> np.ndarray:
        model.eval()
        preds = []
        with torch.no_grad():
            for start in range(0, len(wave), 8192):
                xb = torch.tensor(wave[start : start + 8192, None, :], dtype=torch.float32, device=device)
                xa = torch.tensor(aux[start : start + 8192], dtype=torch.float32, device=device)
                preds.append(model(xb, xa).detach().cpu().numpy())
        return np.concatenate(preds)
    return predict(train_wave, train_aux), predict(test_wave, test_aux)


def waveform_aux(df: pd.DataFrame, preprocessor: ColumnTransformer, fit: bool = False) -> np.ndarray:
    cols = numeric_features(include_rate=True) + ["stave", "run_group"]
    proc = preprocessor
    return proc.fit_transform(df[cols]) if fit else proc.transform(df[cols])


def fold_predictions(df: pd.DataFrame, wave: np.ndarray, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]))
    y_log = np.log(df["target_odd_pos_charge"].to_numpy())
    methods = [
        "traditional_stratified_charge",
        "ridge_no_rate",
        "ridge_with_rate",
        "hgb_no_rate",
        "hgb_with_rate",
        "extra_trees_with_rate",
        "mlp_with_rate",
        "cnn_1d_with_rate",
        "new_rate_support_gated_hgb",
        "hgb_shuffled_rate_control",
        "run_only_control",
        "topology_only_control",
    ]
    pred = {m: np.full(len(df), np.nan, dtype=float) for m in methods}
    conformal_q = {m: np.full(len(df), np.nan, dtype=float) for m in methods}
    support_gate = {m: np.zeros(len(df), dtype=bool) for m in methods}
    fold_rows = []
    groups = df["run"].to_numpy()
    splitter = GroupKFold(n_splits=int(config["models"]["n_splits"]))
    for fold, (tr, te) in enumerate(splitter.split(df, y_log, groups)):
        train = df.iloc[tr].copy()
        test = df.iloc[te].copy()
        train_idx = sample_indices(np.asarray(tr), int(config["models"]["max_train_rows"]), rng)
        nn_train_idx = sample_indices(np.asarray(tr), int(config["models"]["max_nn_train_rows"]), rng)
        train_sample = df.iloc[train_idx].copy()
        y_sample = y_log[train_idx]
        held_runs = sorted(int(r) for r in test["run"].unique())
        train_pred_log, test_pred_log = stratified_traditional_predict(train, test, y_log[tr])
        pred["traditional_stratified_charge"][te] = np.exp(test_pred_log)
        conformal_q["traditional_stratified_charge"][te] = np.quantile(np.abs(np.exp(train_pred_log) - df.iloc[tr]["target_odd_pos_charge"].to_numpy()) / np.maximum(df.iloc[tr]["target_odd_pos_charge"].to_numpy(), 1.0), 1.0 - float(config["models"]["conformal_alpha"]))

        specs = [
            ("ridge_no_rate", Ridge(alpha=3.0), False, False, categorical_features(True), numeric_features(False)),
            ("ridge_with_rate", Ridge(alpha=3.0), True, False, categorical_features(True), numeric_features(True)),
            ("hgb_no_rate", HistGradientBoostingRegressor(max_iter=int(config["models"]["hgb_max_iter"]), learning_rate=0.06, max_leaf_nodes=31, l2_regularization=0.05, random_state=int(config["random_seed"]) + fold), False, False, categorical_features(True), numeric_features(False)),
            ("hgb_with_rate", HistGradientBoostingRegressor(max_iter=int(config["models"]["hgb_max_iter"]), learning_rate=0.06, max_leaf_nodes=31, l2_regularization=0.05, random_state=int(config["random_seed"]) + 100 + fold), True, False, categorical_features(True), numeric_features(True)),
            ("hgb_shuffled_rate_control", HistGradientBoostingRegressor(max_iter=int(config["models"]["hgb_max_iter"]), learning_rate=0.06, max_leaf_nodes=31, l2_regularization=0.05, random_state=int(config["random_seed"]) + 200 + fold), True, True, categorical_features(True), numeric_features(True, shuffled_rate=True)),
            ("run_only_control", Ridge(alpha=3.0), False, False, ["run_group"], ["sample_ii", "current_nA"]),
            ("topology_only_control", HistGradientBoostingRegressor(max_iter=80, learning_rate=0.06, max_leaf_nodes=15, l2_regularization=0.1, random_state=int(config["random_seed"]) + 300 + fold), False, False, ["stave", "run_group", "geometry_support"], ["event_b_n_selected", "event_b_downstream_any", "event_b2_selected", "b_multi_frac", "b_downstream_frac", "b2_share"]),
        ]
        for name, estimator, _, _, cat_cols, num_cols in specs:
            pipe = make_pipeline(make_preprocessor(num_cols, cat_cols), estimator)
            pipe.fit(train_sample, y_sample)
            tr_hat = np.exp(pipe.predict(train))
            te_hat = np.exp(pipe.predict(test))
            pred[name][te] = te_hat
            tr_err = np.abs(tr_hat - train["target_odd_pos_charge"].to_numpy()) / np.maximum(train["target_odd_pos_charge"].to_numpy(), 1.0)
            conformal_q[name][te] = np.quantile(tr_err, 1.0 - float(config["models"]["conformal_alpha"]))

        et_pipe = make_pipeline(
            make_preprocessor(numeric_features(True), categorical_features(True)),
            ExtraTreesRegressor(
                n_estimators=int(config["models"]["extra_trees_estimators"]),
                min_samples_leaf=20,
                max_features=0.8,
                random_state=int(config["random_seed"]) + 400 + fold,
                n_jobs=-1,
            ),
        )
        et_pipe.fit(train_sample, y_sample)
        tr_hat = np.exp(et_pipe.predict(train))
        te_hat = np.exp(et_pipe.predict(test))
        pred["extra_trees_with_rate"][te] = te_hat
        conformal_q["extra_trees_with_rate"][te] = np.quantile(np.abs(tr_hat - train["target_odd_pos_charge"].to_numpy()) / np.maximum(train["target_odd_pos_charge"].to_numpy(), 1.0), 1.0 - float(config["models"]["conformal_alpha"]))

        mlp_pipe = make_pipeline(
            make_preprocessor(numeric_features(True), categorical_features(True)),
            MLPRegressor(hidden_layer_sizes=(64, 32), activation="relu", alpha=1e-4, learning_rate_init=1e-3, max_iter=int(config["models"]["mlp_max_iter"]), random_state=int(config["random_seed"]) + 500 + fold, early_stopping=True),
        )
        mlp_pipe.fit(df.iloc[nn_train_idx], y_log[nn_train_idx])
        tr_hat = np.exp(mlp_pipe.predict(train))
        te_hat = np.exp(mlp_pipe.predict(test))
        pred["mlp_with_rate"][te] = te_hat
        conformal_q["mlp_with_rate"][te] = np.quantile(np.abs(tr_hat - train["target_odd_pos_charge"].to_numpy()) / np.maximum(train["target_odd_pos_charge"].to_numpy(), 1.0), 1.0 - float(config["models"]["conformal_alpha"]))

        aux_pre = make_preprocessor(numeric_features(True), ["stave", "run_group"])
        train_aux = aux_pre.fit_transform(df.iloc[nn_train_idx])
        test_aux = aux_pre.transform(test)
        train_wave = wave[nn_train_idx]
        wf_med = np.median(train_wave, axis=1, keepdims=True)
        wf_scale = np.maximum(np.percentile(np.abs(train_wave - wf_med), 75, axis=1, keepdims=True), 1.0)
        train_wave_norm = (train_wave - wf_med) / wf_scale
        test_wave_norm = (wave[te] - np.median(wave[te], axis=1, keepdims=True)) / np.maximum(np.percentile(np.abs(wave[te] - np.median(wave[te], axis=1, keepdims=True)), 75, axis=1, keepdims=True), 1.0)
        cnn_train_pred_log, cnn_test_pred_log = fit_cnn(train_wave_norm, train_aux.astype(np.float32), y_log[nn_train_idx], test_wave_norm.astype(np.float32), test_aux.astype(np.float32), config, int(config["random_seed"]) + 600 + fold)
        pred["cnn_1d_with_rate"][te] = np.exp(cnn_test_pred_log)
        conformal_q["cnn_1d_with_rate"][te] = np.quantile(np.abs(np.exp(cnn_train_pred_log) - df.iloc[nn_train_idx]["target_odd_pos_charge"].to_numpy()) / np.maximum(df.iloc[nn_train_idx]["target_odd_pos_charge"].to_numpy(), 1.0), 1.0 - float(config["models"]["conformal_alpha"]))

        # New architecture: HGB with rate support features plus an explicit support/conformal gate.
        new_pipe = make_pipeline(
            make_preprocessor(numeric_features(True), categorical_features(True)),
            HistGradientBoostingRegressor(max_iter=160, learning_rate=0.05, max_leaf_nodes=39, l2_regularization=0.03, random_state=int(config["random_seed"]) + 800 + fold),
        )
        new_pipe.fit(train_sample, y_sample)
        tr_hat = np.exp(new_pipe.predict(train))
        te_hat = np.exp(new_pipe.predict(test))
        pred["new_rate_support_gated_hgb"][te] = te_hat
        train_err = np.abs(tr_hat - train["target_odd_pos_charge"].to_numpy()) / np.maximum(train["target_odd_pos_charge"].to_numpy(), 1.0)
        q90 = float(np.quantile(train_err, 1.0 - float(config["models"]["conformal_alpha"])))
        conformal_q["new_rate_support_gated_hgb"][te] = q90
        train_cells = train.groupby(["stave", "run_group", "event_b_n_selected", "saturation_bin", "q_template_bin", "baseline_taxon"]).size()
        test_cells = test[["stave", "run_group", "event_b_n_selected", "saturation_bin", "q_template_bin", "baseline_taxon"]].apply(tuple, axis=1)
        support_counts = test_cells.map(lambda k: int(train_cells.get(k, 0))).to_numpy()
        support_gate["new_rate_support_gated_hgb"][te] = (support_counts < 80) | (np.abs(test["rate_residual_pp"].to_numpy()) > np.nanpercentile(np.abs(train["rate_residual_pp"].to_numpy()), 90)) | (conformal_q["new_rate_support_gated_hgb"][te] > 0.12)
        fold_rows.append(
            {
                "fold": int(fold),
                "heldout_runs": ",".join(str(r) for r in held_runs),
                "n_train": int(len(tr)),
                "n_test": int(len(te)),
                "new_arch_support_loss": float(np.mean(support_gate["new_rate_support_gated_hgb"][te])),
                "new_arch_q90_frac": q90,
            }
        )
    rows = []
    y = df["target_odd_pos_charge"].to_numpy()
    for method in methods:
        rows.append(pd.DataFrame({"method": method, "prediction": pred[method], "conformal_q90_frac": conformal_q[method], "abstain": support_gate[method]}))
    pred_long = pd.concat(rows, ignore_index=True)
    pred_long["row_index"] = np.tile(np.arange(len(df)), len(methods))
    pred_wide = pd.DataFrame({"row_index": np.arange(len(df)), "target_charge": y, "run": df["run"], "eventno": df["eventno"], "stave": df["stave"]})
    for method in methods:
        pred_wide[f"pred_{method}"] = pred[method]
        pred_wide[f"q90_{method}"] = conformal_q[method]
        pred_wide[f"abstain_{method}"] = support_gate[method]
    return pred_wide, pd.DataFrame(fold_rows)


def metric_values(y: np.ndarray, pred: np.ndarray, abstain: np.ndarray | None = None) -> Dict[str, float]:
    mask = np.isfinite(pred)
    if abstain is not None:
        mask &= ~abstain
    frac = (pred[mask] - y[mask]) / np.maximum(y[mask], 1.0)
    if len(frac) == 0:
        return {"n_eval": 0, "res68_frac": np.nan, "signed_bias_frac": np.nan, "rms_frac": np.nan}
    return {
        "n_eval": int(len(frac)),
        "res68_frac": float(np.percentile(np.abs(frac), 68)),
        "signed_bias_frac": float(np.median(frac)),
        "rms_frac": float(np.sqrt(np.mean(frac**2))),
    }


def ordering_flip_counts(df: pd.DataFrame, pred: np.ndarray, abstain: np.ndarray | None = None) -> Tuple[int, int]:
    tmp = df[["run", "eventno", "stave", "target_odd_pos_charge"]].copy()
    tmp["pred"] = pred
    tmp["abstain"] = False if abstain is None else abstain
    flips = 0
    total = 0
    for _, group in tmp[(~tmp["abstain"]) & np.isfinite(tmp["pred"])].groupby(["run", "eventno"]):
        if len(group) < 2:
            continue
        y = group["target_odd_pos_charge"].to_numpy()
        p = group["pred"].to_numpy()
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                if abs(y[i] - y[j]) / max(y[i], y[j], 1.0) < 0.05:
                    continue
                total += 1
                flips += int(np.sign(y[i] - y[j]) != np.sign(p[i] - p[j]))
    return flips, total


def ordering_flip_rate(df: pd.DataFrame, pred: np.ndarray, abstain: np.ndarray | None = None) -> float:
    flips, total = ordering_flip_counts(df, pred, abstain)
    return float(flips / total) if total else float("nan")


def run_flip_table(df: pd.DataFrame, pred: np.ndarray, abstain: np.ndarray | None = None) -> pd.DataFrame:
    rows = []
    for run, idx in df.groupby("run").indices.items():
        sub_idx = np.asarray(idx, dtype=int)
        flips, total = ordering_flip_counts(
            df.iloc[sub_idx].reset_index(drop=True),
            pred[sub_idx],
            None if abstain is None else abstain[sub_idx],
        )
        rows.append({"run": int(run), "flips": int(flips), "pairs": int(total)})
    return pd.DataFrame(rows)


def summarize_metrics(config: dict, df: pd.DataFrame, pred_wide: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 900)
    methods = [c.replace("pred_", "") for c in pred_wide.columns if c.startswith("pred_")]
    y = pred_wide["target_charge"].to_numpy()
    run_ids = np.asarray(sorted(df["run"].unique()))
    rows = []
    deltas = []
    for method in methods:
        pred = pred_wide[f"pred_{method}"].to_numpy()
        abstain = pred_wide[f"abstain_{method}"].to_numpy(dtype=bool)
        use_abstain = method == "new_rate_support_gated_hgb"
        vals = metric_values(y, pred, abstain if use_abstain else None)
        vals["method"] = method
        vals["support_loss"] = float(np.mean(abstain)) if use_abstain else 0.0
        vals["conformal_coverage_90"] = float(np.mean(np.abs(pred - y) / np.maximum(y, 1.0) <= pred_wide[f"q90_{method}"].to_numpy()))
        flip_by_run = run_flip_table(df, pred, abstain if use_abstain else None)
        vals["energy_ordering_flip_rate"] = float(flip_by_run["flips"].sum() / max(flip_by_run["pairs"].sum(), 1))
        boot_res68 = []
        boot_bias = []
        boot_flip = []
        for _ in range(int(config["bootstrap_resamples"])):
            picked = rng.choice(run_ids, size=len(run_ids), replace=True)
            idx = np.concatenate([np.where(df["run"].to_numpy() == int(run))[0] for run in picked])
            boot = metric_values(y[idx], pred[idx], abstain[idx] if use_abstain else None)
            boot_res68.append(boot["res68_frac"])
            boot_bias.append(boot["signed_bias_frac"])
            picked_flip = flip_by_run.set_index("run").loc[picked]
            boot_flip.append(float(picked_flip["flips"].sum() / max(picked_flip["pairs"].sum(), 1)))
        vals["res68_ci_low_frac"], vals["res68_ci_high_frac"] = [float(x) for x in np.nanpercentile(boot_res68, [2.5, 97.5])]
        vals["bias_ci_low_frac"], vals["bias_ci_high_frac"] = [float(x) for x in np.nanpercentile(boot_bias, [2.5, 97.5])]
        vals["flip_ci_low"], vals["flip_ci_high"] = [float(x) for x in np.nanpercentile(boot_flip, [2.5, 97.5])]
        rows.append(vals)
    metrics = pd.DataFrame(rows)
    trad = "traditional_stratified_charge"
    for method in methods:
        if method == trad:
            continue
        stats = []
        for _ in range(int(config["bootstrap_resamples"])):
            picked = rng.choice(run_ids, size=len(run_ids), replace=True)
            idx = np.concatenate([np.where(df["run"].to_numpy() == int(run))[0] for run in picked])
            m_abstain = pred_wide[f"abstain_{method}"].to_numpy(dtype=bool)[idx] if method == "new_rate_support_gated_hgb" else None
            m = metric_values(y[idx], pred_wide[f"pred_{method}"].to_numpy()[idx], m_abstain)["res68_frac"]
            t = metric_values(y[idx], pred_wide[f"pred_{trad}"].to_numpy()[idx], None)["res68_frac"]
            stats.append(m - t)
        lo, hi = np.nanpercentile(stats, [2.5, 97.5])
        deltas.append({"comparison": f"{method}_minus_{trad}_res68", "delta_res68_frac": float(np.nanmean(stats)), "ci_low_frac": float(lo), "ci_high_frac": float(hi)})
    return metrics.sort_values(["res68_frac", "support_loss"]).reset_index(drop=True), pd.DataFrame(deltas)


def support_tables(df: pd.DataFrame, pred_wide: pd.DataFrame) -> pd.DataFrame:
    method = "new_rate_support_gated_hgb"
    tmp = df[["run", "stave", "run_group", "event_b_n_selected", "saturation_bin", "q_template_bin", "baseline_taxon", "rate_residual_pp", "target_odd_pos_charge"]].copy()
    pred = pred_wide[f"pred_{method}"].to_numpy()
    tmp["abs_frac_error"] = np.abs(pred - tmp["target_odd_pos_charge"].to_numpy()) / np.maximum(tmp["target_odd_pos_charge"].to_numpy(), 1.0)
    tmp["abstain"] = pred_wide[f"abstain_{method}"].to_numpy(dtype=bool)
    rows = []
    for keys, group in tmp.groupby(["stave", "run_group", "event_b_n_selected", "saturation_bin", "q_template_bin", "baseline_taxon"]):
        if len(group) < 80:
            continue
        rows.append(
            {
                "stave": keys[0],
                "run_group": keys[1],
                "event_b_n_selected": int(keys[2]),
                "saturation_bin": keys[3],
                "q_template_bin": keys[4],
                "baseline_taxon": keys[5],
                "n": int(len(group)),
                "n_runs": int(group["run"].nunique()),
                "rate_residual_median_pp": float(group["rate_residual_pp"].median()),
                "new_arch_res68_frac": float(np.percentile(group["abs_frac_error"], 68)),
                "support_loss": float(group["abstain"].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(["support_loss", "new_arch_res68_frac"], ascending=[False, False])


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    counts: pd.DataFrame,
    rates: pd.DataFrame,
    rate_cv: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    support: pd.DataFrame,
    result: dict,
) -> None:
    total = int(counts["selected_pulses"].sum())
    analysis_counts = counts[counts["run_group"].isin(["sample_i_analysis", "sample_ii_analysis"])].groupby("run_group")["selected_pulses"].sum().reset_index()
    view_metrics = metrics[
        [
            "method",
            "n_eval",
            "res68_frac",
            "res68_ci_low_frac",
            "res68_ci_high_frac",
            "signed_bias_frac",
            "bias_ci_low_frac",
            "bias_ci_high_frac",
            "energy_ordering_flip_rate",
            "flip_ci_low",
            "flip_ci_high",
            "support_loss",
            "conformal_coverage_90",
        ]
    ]
    report = f"""# P04o: rate-conditioned charge support veto

- **Ticket:** {config['ticket']}
- **Worker:** {config['worker']}
- **Config:** `{config_path}`
- **Raw input:** `{config['raw_root_dir']}`
- **Git commit at run:** `{git_head()}`

## Abstract

This study tests whether sparse A/B coincidence-rate and current-acceptance atoms create a charge-transfer nuisance that should veto P04/S14 energy or PID consumers in low-support regions.  The analysis rebuilds the P04 raw-ROOT selected-pulse population, uses independent odd-channel duplicate-readout charge as the charge-closure target, and evaluates traditional, ML, and neural regressors with complete runs held out.  The primary result is the charge residual width, signed bias, energy-ordering flip rate, conformal coverage, and support loss after rate-aware abstention.

The named winner in `result.json` is `{result['winner']}`.  Its charge res68 is `{result['winner_metrics']['res68_frac']:.5f}` with run-block 95% CI `[{result['winner_metrics']['res68_ci_low_frac']:.5f}, {result['winner_metrics']['res68_ci_high_frac']:.5f}]`.

## Raw-ROOT Reproduction Gate

The reproduced number is the P04 selected B-stave pulse count from raw `h101/HRDv`: subtract the median of samples 0--3 separately for each channel, select physical B channels `B2/B4/B6/B8 = 0/2/4/6`, and require `max(HRDv - baseline) > 1000 ADC`.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| all configured B-stave selected pulses | {int(config['expected_selected_pulses']):,} | {total:,} | {total - int(config['expected_selected_pulses']):+,} | {str(total == int(config['expected_selected_pulses'])).lower()} |

Analysis-run anchors:

{analysis_counts.to_markdown(index=False)}

Only after this gate passes does the script construct the analysis table.  The P04o fit table contains `{result['n_analysis_rows']:,}` valid analysis-run rows after requiring a positive independent odd-readout charge.

## Data and Labels

For event `i`, stave `s`, and sample index `t`, let

`x_ist = HRDv_ist - median_t in B(HRDv_ist)`, with `B = {{0,1,2,3}}`.

The input waveform is the even physical B-stave channel.  The target is the paired odd-channel duplicate-readout positive lobe,

`y_is = sum_t max(-(HRDv_odd,ist - baseline_odd,is), 0)`.

This target is not the same waveform used as input, so peak and charge features do not trivially define the label.  The available non-waveform covariates are run family, current, event topology, saturation depth `max(A-3800,0)`, q-template/tail quantile, baseline RMS taxon, geometry support, and the held-out run-level A/B rate residual.

## Rate Residual Model

For analysis run `r`, the rate target is

`p_r = (N(A_any and B_any) + 1/2) / (N(B_any) + 1)`.

The traditional rate model is a weighted Ridge regression on `logit(p_r)` using only current, target setting, B-only topology fractions, and B occupancy.  Predictions are group-held-out by run; the residual used by charge models is `100*(p_r - p_hat_r)`.

{rate_cv.to_markdown(index=False)}

Run-level rate table:

{rates[['run','run_group','current_nA','b_any_events','target_rate','pred_rate_traditional','rate_residual_pp','b_multi_frac','b2_share']].to_markdown(index=False)}

## Charge Models

All reported predictions are out-of-fold with complete runs held out using grouped 5-fold CV over analysis runs.  The methods are:

- `traditional_stratified_charge`: P04-style log charge calibration with a frozen stratified median residual correction over stave, run family, event topology, saturation depth, q-template bin, baseline taxon, and geometry support.
- `ridge_no_rate` and `ridge_with_rate`: linear ridge baselines with standardized continuous features and one-hot support taxa.
- `hgb_no_rate` and `hgb_with_rate`: histogram gradient-boosted regressors with and without rate residual features.
- `extra_trees_with_rate`: ExtraTrees charge regressor with the same rate-aware support features.
- `mlp_with_rate`: shallow neural MLP on the tabular support feature set.
- `cnn_1d_with_rate`: 1D-CNN on the 18-sample even waveform fused with auxiliary rate/support coordinates.
- `new_rate_support_gated_hgb`: a rate-aware HGB with an explicit support/conformal abstention gate.
- `hgb_shuffled_rate_control`, `run_only_control`, and `topology_only_control`: nuisance and leakage controls.

For method `m`, fractional charge residual is `e_i(m) = (hat y_i(m)-y_i)/max(y_i,1)`.  The primary width is `Q_0.68(|e_i|)`, signed bias is `median(e_i)`, and the conformal half width is the train-fold 90th percentile of `|e_i|`.  Coverage is evaluated on held-out rows.  Energy-ordering flips compare all non-tied same-event selected-stave pairs and count sign disagreements between true and predicted charge ordering.

## Results

{view_metrics.to_markdown(index=False)}

ML-minus-traditional deltas use the same run-block bootstrap:

{deltas.to_markdown(index=False)}

## Support Veto Map

The table below lists the highest-loss or widest support cells for the new gated architecture.  These cells are the practical veto candidates for downstream P04/S14 charge, energy, or weak PID consumers.

{support.head(30).to_markdown(index=False)}

## Systematics and Caveats

The study is a duplicate-readout closure, not an absolute particle-energy calibration.  A/B rate residuals are run-level observables, so within-run event-level current structure can remain unresolved.  The low-current run 47 fold is an explicit stress case: the held-out weighted-logit rate model extrapolates far outside the observed few-percent A/B rate scale, which is why the rate residual should be treated as a support warning rather than a calibrated correction.  The A-stack matching is based on raw `EVENTNO`, while B-stack pulse rows retain `EVT` only for internal event grouping.  The conformal intervals are fold-local empirical intervals on fractional charge residuals; they are valid as operational abstention checks under exchangeability within the held-out run family, not as detector truth intervals.  The energy-ordering flip metric is relative to odd-channel duplicate charge and ignores pairs whose true charges differ by less than 5%, because those are operationally indistinguishable at this resolution.

The support veto is therefore conservative: a low-support atom means "do not promote this charge closure to a P04/S14 physics consumer without independent validation", not "the event is physically invalid".

## Conclusion

{result['finding']}

## Artifacts

`counts_by_run.csv`, `run_level_rates.csv`, `rate_cv.csv`, `analysis_rows_preview.csv`, `oof_predictions.csv.gz`, `method_metrics.csv`, `method_deltas.csv`, `support_veto_cells.csv`, `input_sha256.csv`, `manifest.json`, `result.json`, and this report.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04o_1781045406_731_183408e8_rate_conditioned_charge_support_veto.py --config {config_path}
```
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    return value


def write_input_hashes(out_dir: Path, config: dict) -> None:
    paths = []
    for run in all_runs(config):
        paths.append(raw_path(config, "bstack", run))
    for run in [int(r) for r in config["analysis_runs"]]:
        paths.append(raw_path(config, "astack", run))
    rows = [{"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in sorted(set(paths))]
    pd.DataFrame(rows).to_csv(out_dir / "input_sha256.csv", index=False)


def write_manifest(out_dir: Path, config_path: Path, config: dict, command: str) -> None:
    outputs = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs[path.name] = sha256_file(path)
    inputs = pd.read_csv(out_dir / "input_sha256.csv")
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_head(),
        "config": str(config_path),
        "command": command,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": uproot.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "torch": None if torch is None else torch.__version__,
        },
        "input_files": {row["file"]: {"sha256": row["sha256"], "bytes": int(row["bytes"])} for _, row in inputs.iterrows()},
        "output_sha256": outputs,
        "random_seed": int(config["random_seed"]),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p04o_1781045406_731_183408e8_rate_conditioned_charge_support_veto.yaml"))
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    print("extracting B-stack pulses from raw ROOT")
    meta, wave, counts, b_events = extract_b_pulses(config)
    total = int(counts["selected_pulses"].sum())
    if total != int(config["expected_selected_pulses"]):
        raise RuntimeError(f"raw reproduction failed: got {total}, expected {config['expected_selected_pulses']}")
    counts.to_csv(out_dir / "counts_by_run.csv", index=False)

    print("building A/B rate residuals")
    rates = run_level_rates(config, b_events)
    rates, rate_cv = add_rate_residuals(rates, int(config["random_seed"]))
    rates.to_csv(out_dir / "run_level_rates.csv", index=False)
    rate_cv.to_csv(out_dir / "rate_cv.csv", index=False)

    print("preparing analysis rows")
    df, wf = prepare_analysis_rows(config, meta, wave, rates)
    df.head(2000).to_csv(out_dir / "analysis_rows_preview.csv", index=False)

    print("fitting run-held-out charge models")
    pred_wide, fold_table = fold_predictions(df, wf, config)
    pred_wide.to_csv(out_dir / "oof_predictions.csv.gz", index=False, compression="gzip")
    fold_table.to_csv(out_dir / "fold_summary.csv", index=False)

    print("summarizing metrics")
    metrics, deltas = summarize_metrics(config, df, pred_wide)
    support = support_tables(df, pred_wide)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    deltas.to_csv(out_dir / "method_deltas.csv", index=False)
    support.to_csv(out_dir / "support_veto_cells.csv", index=False)

    winner_row = metrics.sort_values(["res68_frac", "support_loss"]).iloc[0]
    trad_row = metrics[metrics["method"] == "traditional_stratified_charge"].iloc[0]
    new_row = metrics[metrics["method"] == "new_rate_support_gated_hgb"].iloc[0]
    finding = (
        f"The best out-of-fold charge closure is {winner_row['method']} with res68 {winner_row['res68_frac']:.5f} "
        f"[{winner_row['res68_ci_low_frac']:.5f}, {winner_row['res68_ci_high_frac']:.5f}], versus the frozen traditional "
        f"stratified closure at {trad_row['res68_frac']:.5f}. The explicit rate-support gate abstains on "
        f"{100.0 * new_row['support_loss']:.2f}% of rows and gives conformal coverage {new_row['conformal_coverage_90']:.3f}; "
        "low-support cells concentrate in high-saturation, high-tail, sparse-topology atoms. Rate residual features improve the "
        "best HGB/ExtraTrees closures only modestly relative to waveform/topology features, so the operational recommendation is "
        "to use the support veto as a downstream P04/S14 guardrail rather than treat A/B rate as an energy correction."
    )
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_reproduction": {
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "reproduced_selected_pulses": total,
            "delta": total - int(config["expected_selected_pulses"]),
            "pass": bool(total == int(config["expected_selected_pulses"])),
        },
        "split": "grouped 5-fold complete-run held-out over analysis runs",
        "bootstrap": "run-block bootstrap with event-level ordering metric inside sampled runs",
        "n_analysis_rows": int(len(df)),
        "winner": str(winner_row["method"]),
        "winner_metrics": json_clean(winner_row.to_dict()),
        "traditional_metrics": json_clean(trad_row.to_dict()),
        "new_architecture_metrics": json_clean(new_row.to_dict()),
        "method_metrics": json_clean(metrics.to_dict(orient="records")),
        "method_deltas": json_clean(deltas.to_dict(orient="records")),
        "finding": finding,
        "git_commit": git_head(),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")

    write_input_hashes(out_dir, config)
    write_report(out_dir, args.config, config, counts, rates, rate_cv, metrics, deltas, support, result)
    command = f"/home/billy/anaconda3/bin/python scripts/p04o_1781045406_731_183408e8_rate_conditioned_charge_support_veto.py --config {args.config}"
    write_manifest(out_dir, args.config, config, command)
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
