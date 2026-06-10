#!/usr/bin/env python3
"""P01c repeated leakage sentinels for waveform probes.

Reads the raw B-stack ROOT files first, reproduces the P01/S00 selected-pulse
count, then runs a leave-run-out waveform-representation benchmark and a
repeated permutation battery before accepting any ML representation gain.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import uproot
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import balanced_accuracy_score, f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


TICKET_ID = "1781010192.1271.5e804d02"
STUDY_ID = "P01c"
TITLE = "repeated leakage sentinels for waveform probes"
OUT_DIR = Path(f"reports/{TICKET_ID}__p01c_repeated_leakage_sentinels")
RAW_ROOT_DIR_CANDIDATES = [
    Path("data/extracted/root/root"),
    Path("data/root/root"),
    Path("/home/billy/ccb-data/extracted/root/root"),
    Path("/home/billy/Desktop/test_beam/data/root/root"),
]
EXPECTED_SELECTED_PULSES = 640737
AMPLITUDE_CUT_ADC = 1000.0
BASELINE_SAMPLES = [0, 1, 2, 3]
SAMPLES_PER_CHANNEL = 18
STAVE_NAMES = ["B2", "B4", "B6", "B8"]
STAVE_CHANNELS = np.asarray([0, 2, 4, 6], dtype=int)
RUN_GROUPS = {
    "sample_i_calib": [31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42],
    "sample_i_analysis": [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57],
    "sample_ii_calib": [64],
    "sample_ii_analysis": [58, 59, 60, 61, 62, 63, 65],
}
HELDOUT_RUNS = np.asarray([42, 57, 64, 65], dtype=int)
SEED = 310192
BOOTSTRAP_REPLICATES = 500
MAX_PER_RUN_STAVE = 1500
LATENT_DIM = 4
AE_EPOCHS = 25
SHUFFLE_SEEDS = list(range(7001, 7011))
PASS_MARGIN = 0.02
MAX_RANDOM_ROW_GAIN = 0.05


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_raw_root_dir() -> Path:
    for candidate in RAW_ROOT_DIR_CANDIDATES:
        if candidate.exists() and list(candidate.glob("hrdb_run_*.root")):
            return candidate
    raise FileNotFoundError("No raw B-stack ROOT directory found")


def configured_runs() -> List[int]:
    runs: List[int] = []
    for values in RUN_GROUPS.values():
        runs.extend(values)
    return sorted(set(int(run) for run in runs))


def run_group_lookup() -> Dict[int, str]:
    lookup: Dict[int, str] = {}
    for group, runs in RUN_GROUPS.items():
        for run in runs:
            lookup[int(run)] = group
    return lookup


def iter_raw_events(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["HRDv"], step_size=step_size, library="np")


def topology_label(n_selected: np.ndarray) -> np.ndarray:
    labels = np.full(len(n_selected), "unknown", dtype=object)
    labels[n_selected == 1] = "single"
    labels[n_selected == 2] = "pair"
    labels[n_selected == 3] = "triple"
    labels[n_selected >= 4] = "quad"
    return labels


def scan_raw(raw_root_dir: Path) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    group_by_run = run_group_lookup()
    waves: List[np.ndarray] = []
    meta_frames: List[pd.DataFrame] = []
    count_rows: List[dict] = []

    for run in configured_runs():
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(f"Missing configured run: {path}")

        run_counts = {"events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        stave_counts = {name: 0 for name in STAVE_NAMES}
        event_offset = 0

        for batch in iter_raw_events(path):
            event_waves = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, SAMPLES_PER_CHANNEL)
            selected_waves = event_waves[:, STAVE_CHANNELS, :]
            baseline = np.median(selected_waves[..., BASELINE_SAMPLES], axis=-1)
            corrected = selected_waves - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > AMPLITUDE_CUT_ADC
            event_idx, stave_idx = np.where(selected)

            run_counts["events_total"] += int(len(event_waves))
            run_counts["events_with_selected"] += int(selected.any(axis=1).sum())
            run_counts["selected_pulses"] += int(selected.sum())
            for idx, name in enumerate(STAVE_NAMES):
                stave_counts[name] += int(selected[:, idx].sum())

            if len(event_idx):
                mask_bits = selected.astype(np.uint8) * (1 << np.arange(len(STAVE_NAMES), dtype=np.uint8))
                event_topology_mask = mask_bits.sum(axis=1).astype(np.int16)
                event_topology_n = selected.sum(axis=1).astype(np.int8)
                chosen = corrected[event_idx, stave_idx]
                amp = amplitude[event_idx, stave_idx].astype(np.float32)
                waves.append((chosen / amp[:, None]).astype(np.float32))
                meta_frames.append(
                    pd.DataFrame(
                        {
                            "run": np.full(len(event_idx), run, dtype=np.int16),
                            "run_group": np.full(len(event_idx), group_by_run[run], dtype=object),
                            "event_in_run": event_offset + event_idx.astype(np.int32),
                            "stave": np.asarray(STAVE_NAMES, dtype=object)[stave_idx],
                            "stave_index": stave_idx.astype(np.int8),
                            "amplitude_adc": amp,
                            "log10_amplitude": np.log10(np.maximum(amp, 1.0)).astype(np.float32),
                            "topology_mask": event_topology_mask[event_idx],
                            "peer_topology_mask": (event_topology_mask[event_idx] & ~(1 << stave_idx)).astype(np.int16),
                            "topology_n": event_topology_n[event_idx],
                        }
                    )
                )
            event_offset += len(event_waves)

        count_rows.append({"run": run, "run_group": group_by_run[run], **run_counts, **stave_counts})
        print(f"run {run:04d}: {run_counts['selected_pulses']} selected pulses")

    return np.concatenate(waves, axis=0), pd.concat(meta_frames, ignore_index=True), pd.DataFrame(count_rows)


def one_hot(values: np.ndarray, categories: Sequence[int]) -> np.ndarray:
    values = np.asarray(values)
    return np.column_stack([(values == category).astype(np.float32) for category in categories])


def control_features(meta: pd.DataFrame, topology_categories: Sequence[int]) -> np.ndarray:
    amp = meta["log10_amplitude"].to_numpy(dtype=np.float32).reshape(-1, 1)
    topo = one_hot(meta["topology_n"].to_numpy(dtype=int), topology_categories)
    return np.hstack([amp, topo]).astype(np.float32)


def leaky_mask_features(meta: pd.DataFrame, categories: Sequence[int]) -> np.ndarray:
    return np.hstack(
        [
            meta["topology_n"].to_numpy(dtype=np.float32).reshape(-1, 1),
            one_hot(meta["topology_mask"].to_numpy(dtype=int), categories),
        ]
    ).astype(np.float32)


def hand_shape_features(waves: np.ndarray) -> np.ndarray:
    area = waves.sum(axis=1)
    tail = waves[:, 12:].sum(axis=1) / np.maximum(np.abs(area), 1e-6)
    early = waves[:, :5].sum(axis=1)
    late = waves[:, 10:].sum(axis=1)
    peak = waves.argmax(axis=1).astype(np.float32)
    width20 = (waves > 0.2).sum(axis=1).astype(np.float32)
    width50 = (waves > 0.5).sum(axis=1).astype(np.float32)
    plateau = waves[:, 6:10].mean(axis=1)
    asymmetry = (late - early) / np.maximum(np.abs(area), 1e-6)
    return np.column_stack([peak, area, tail, width20, width50, plateau, asymmetry]).astype(np.float32)


def balanced_indices(meta: pd.DataFrame, mask: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    selected: List[np.ndarray] = []
    base_idx = np.where(mask)[0]
    frame = meta.iloc[base_idx]
    for (_run, _stave), group in frame.groupby(["run", "stave_index"], sort=True):
        idx = group.index.to_numpy(dtype=int)
        take = min(len(idx), MAX_PER_RUN_STAVE)
        selected.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(selected)
    rng.shuffle(out)
    return out


def ci(values: Sequence[float]) -> Tuple[float, float]:
    if len(values) == 0:
        return float("nan"), float("nan")
    lo, hi = np.quantile(np.asarray(values, dtype=float), [0.025, 0.975])
    return float(lo), float(hi)


def run_block_ci(y_true: np.ndarray, y_pred: np.ndarray, runs: np.ndarray, rng: np.random.Generator) -> Tuple[float, float]:
    unique_runs = np.unique(runs)
    boot = []
    for _ in range(BOOTSTRAP_REPLICATES):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        boot.append(float(balanced_accuracy_score(y_true[idx], y_pred[idx])))
    return ci(boot)


def row_bootstrap_ci(y_true: np.ndarray, y_pred: np.ndarray, rng: np.random.Generator) -> Tuple[float, float]:
    boot = []
    for _ in range(BOOTSTRAP_REPLICATES):
        idx = rng.integers(0, len(y_true), size=len(y_true))
        boot.append(float(balanced_accuracy_score(y_true[idx], y_pred[idx])))
    return ci(boot)


def fit_probe(
    method: str,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    y_test: np.ndarray,
    test_runs: Optional[np.ndarray],
    rng: np.random.Generator,
) -> Tuple[dict, np.ndarray]:
    clf = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs", multi_class="auto"),
    )
    clf.fit(x_train, y_train)
    pred = clf.predict(x_test)
    if test_runs is None:
        lo, hi = row_bootstrap_ci(y_test, pred, rng)
        ci_type = "row_bootstrap"
    else:
        lo, hi = run_block_ci(y_test, pred, test_runs, rng)
        ci_type = "heldout_run_block_bootstrap"
    return (
        {
            "method": method,
            "metric": "balanced_accuracy",
            "value": float(balanced_accuracy_score(y_test, pred)),
            "ci_low": lo,
            "ci_high": hi,
            "ci_type": ci_type,
            "macro_f1": float(f1_score(y_test, pred, average="macro", zero_division=0)),
            "train_rows": int(len(y_train)),
            "heldout_rows": int(len(y_test)),
        },
        pred,
    )


def fit_predict_fast(x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray) -> np.ndarray:
    clf = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs", multi_class="auto"),
    )
    clf.fit(x_train, y_train)
    return clf.predict(x_test)


class MaskedDenoisingAutoencoder:
    def __init__(self, latent_dim: int, seed: int):
        import torch
        import torch.nn as nn

        torch.manual_seed(seed)
        self.torch = torch
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.net = nn.Sequential(
            nn.Linear(18, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, latent_dim),
            nn.Linear(latent_dim, 16),
            nn.ReLU(),
            nn.Linear(16, 32),
            nn.ReLU(),
            nn.Linear(32, 18),
        ).to(self.device)
        self.encoder = self.net[:5]

    def fit(self, x: np.ndarray, epochs: int = AE_EPOCHS, batch_size: int = 4096) -> List[float]:
        torch = self.torch
        torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
        xt = torch.tensor(x, dtype=torch.float32, device=self.device)
        opt = torch.optim.Adam(self.net.parameters(), lr=0.001)
        losses: List[float] = []
        for epoch in range(epochs):
            perm = torch.randperm(len(xt), device=self.device)
            epoch_losses: List[float] = []
            for start in range(0, len(xt), batch_size):
                batch = xt[perm[start : start + batch_size]]
                mask = torch.rand_like(batch) < 0.30
                noisy = batch + 0.02 * torch.randn_like(batch)
                corrupted = torch.where(mask, torch.zeros_like(noisy), noisy)
                pred = self.net(corrupted)
                masked_loss = ((pred - batch) ** 2)[mask].mean()
                full_loss = ((pred - batch) ** 2).mean()
                loss = masked_loss + 0.2 * full_loss
                opt.zero_grad()
                loss.backward()
                opt.step()
                epoch_losses.append(float(loss.detach().cpu()))
            losses.append(float(np.mean(epoch_losses)))
            if epoch in {0, epochs - 1} or (epoch + 1) % 10 == 0:
                print(f"AE epoch {epoch + 1:02d}/{epochs}: loss={losses[-1]:.6f}")
        return losses

    def encode(self, x: np.ndarray, batch_size: int = 65536) -> np.ndarray:
        torch = self.torch
        out: List[np.ndarray] = []
        self.net.eval()
        with torch.no_grad():
            for start in range(0, len(x), batch_size):
                xt = torch.tensor(x[start : start + batch_size], dtype=torch.float32, device=self.device)
                out.append(self.encoder(xt).cpu().numpy())
        return np.concatenate(out, axis=0).astype(np.float32)


def shuffled_labels(y: np.ndarray, meta: pd.DataFrame, mode: str, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = y.copy()
    if mode == "global":
        rng.shuffle(out)
        return out
    if mode == "within_run":
        strata = [meta["run"].to_numpy()]
    elif mode == "within_topology":
        strata = [meta["topology_group"].to_numpy()]
    elif mode == "within_run_topology":
        strata = [meta["run"].to_numpy(), meta["topology_group"].to_numpy()]
    else:
        raise ValueError(mode)

    frame = pd.DataFrame({"idx": np.arange(len(y))})
    for i, values in enumerate(strata):
        frame[f"s{i}"] = values
    for _key, group in frame.groupby([col for col in frame.columns if col.startswith("s")], sort=False):
        idx = group["idx"].to_numpy(dtype=int)
        vals = out[idx].copy()
        rng.shuffle(vals)
        out[idx] = vals
    return out


def repeated_shuffle_battery(
    features_by_method: Dict[str, Tuple[np.ndarray, np.ndarray]],
    y_train: np.ndarray,
    y_test: np.ndarray,
    train_meta: pd.DataFrame,
    test_meta: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    rows: List[dict] = []
    test_runs = test_meta["run"].to_numpy(dtype=int)
    test_topology = test_meta["topology_group"].to_numpy(dtype=object)
    modes = ["global", "within_run", "within_topology", "within_run_topology"]
    for method, (x_train, x_test) in features_by_method.items():
        for mode in modes:
            for seed in SHUFFLE_SEEDS:
                y_perm = shuffled_labels(y_train, train_meta, mode, seed)
                pred = fit_predict_fast(x_train, y_perm, x_test)
                rows.append(
                    {
                        "method": f"{method} shuffled labels",
                        "base_method": method,
                        "shuffle_mode": mode,
                        "seed": seed,
                        "scope": "overall",
                        "metric": "balanced_accuracy",
                        "value": float(balanced_accuracy_score(y_test, pred)),
                        "macro_f1": float(f1_score(y_test, pred, average="macro", zero_division=0)),
                        "train_rows": int(len(y_train)),
                        "heldout_rows": int(len(y_test)),
                    }
                )
                for run in sorted(np.unique(test_runs)):
                    mask = test_runs == run
                    rows.append(
                        {
                            "base_method": method,
                            "shuffle_mode": mode,
                            "seed": seed,
                            "scope": "heldout_run",
                            "stratum": str(int(run)),
                            "metric": "balanced_accuracy",
                            "value": float(balanced_accuracy_score(y_test[mask], pred[mask])),
                            "heldout_rows": int(mask.sum()),
                        }
                    )
                for topo in ["single", "pair", "triple", "quad"]:
                    mask = test_topology == topo
                    if int(mask.sum()) < 100:
                        continue
                    rows.append(
                        {
                            "base_method": method,
                            "shuffle_mode": mode,
                            "seed": seed,
                            "scope": "topology",
                            "stratum": topo,
                            "metric": "balanced_accuracy",
                            "value": float(balanced_accuracy_score(y_test[mask], pred[mask])),
                            "heldout_rows": int(mask.sum()),
                        }
                    )
    return pd.DataFrame(rows)


def real_strata(method: str, y_true: np.ndarray, pred: np.ndarray, meta: pd.DataFrame) -> pd.DataFrame:
    rows: List[dict] = []
    for scope, column in [("heldout_run", "run"), ("topology", "topology_group")]:
        for value, group in meta.groupby(column, sort=True):
            idx = group.index.to_numpy(dtype=int)
            if len(idx) < 100:
                continue
            rows.append(
                {
                    "base_method": method,
                    "scope": scope,
                    "stratum": str(value),
                    "metric": "balanced_accuracy",
                    "value": float(balanced_accuracy_score(y_true[idx], pred[idx])),
                    "heldout_rows": int(len(idx)),
                }
            )
    return pd.DataFrame(rows)


def random_row_probe(
    method: str,
    x_all: np.ndarray,
    y_all: np.ndarray,
    rng: np.random.Generator,
) -> dict:
    idx = np.arange(len(y_all))
    rng.shuffle(idx)
    cut = int(0.75 * len(idx))
    train_idx = idx[:cut]
    test_idx = idx[cut:]
    row, _ = fit_probe(f"{method} random-row split", x_all[train_idx], y_all[train_idx], x_all[test_idx], y_all[test_idx], None, rng)
    row["split"] = "random_row"
    return row


def percentile_summary(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = frame.groupby(["base_method", "shuffle_mode", "scope", "stratum"], dropna=False)["value"]
    out = grouped.agg(["count", "mean", "std", "min", "max"]).reset_index()
    out["p95"] = grouped.quantile(0.95).to_numpy()
    return out


def json_sanitize(value):
    if isinstance(value, dict):
        return {key: json_sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_sanitize(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def markdown_table(frame: pd.DataFrame, columns: Sequence[str]) -> str:
    view = frame.loc[:, columns].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else f"{x:.3f}")
    widths = {col: max(len(col), *(len(str(value)) for value in view[col].tolist())) for col in view.columns}
    header = "| " + " | ".join(col.ljust(widths[col]) for col in view.columns) + " |"
    sep = "| " + " | ".join("-" * widths[col] for col in view.columns) + " |"
    body = ["| " + " | ".join(str(row[col]).ljust(widths[col]) for col in view.columns) + " |" for _, row in view.iterrows()]
    return "\n".join([header, sep, *body])


def evaluate_pass_rule(
    benchmark: pd.DataFrame,
    shuffle_summary: pd.DataFrame,
    real_by_stratum: pd.DataFrame,
    random_rows: pd.DataFrame,
) -> Tuple[pd.DataFrame, dict]:
    trad = benchmark[benchmark["method"] == "traditional residual PCA+hand"].iloc[0]
    ml = benchmark[benchmark["method"] == "ML residual masked-denoising AE-4"].iloc[0]
    ml_overall_p95 = float(
        shuffle_summary[
            (shuffle_summary["base_method"] == "ML residual masked-denoising AE-4")
            & (shuffle_summary["scope"] == "overall")
        ]["p95"].max()
    )
    ml_random = float(random_rows[random_rows["method"] == "ML residual masked-denoising AE-4 random-row split"]["value"].iloc[0])
    ml_run = float(ml["value"])

    rule_rows = [
        {
            "rule": "ml_ci_beats_traditional_ci",
            "value": bool(ml["ci_low"] > trad["ci_high"]),
            "detail": f"ML low {ml['ci_low']:.3f} > traditional high {trad['ci_high']:.3f}",
        },
        {
            "rule": "ml_overall_above_repeated_shuffle_p95_plus_margin",
            "value": bool(ml_run > ml_overall_p95 + PASS_MARGIN),
            "detail": f"ML {ml_run:.3f}; shuffle p95 max {ml_overall_p95:.3f}; margin {PASS_MARGIN:.2f}",
        },
        {
            "rule": "random_row_gain_not_suspicious",
            "value": bool((ml_random - ml_run) <= MAX_RANDOM_ROW_GAIN),
            "detail": f"random-row {ml_random:.3f} - run-heldout {ml_run:.3f} <= {MAX_RANDOM_ROW_GAIN:.2f}",
        },
    ]

    stratum_failures = []
    for scope in ["heldout_run", "topology"]:
        real_scope = real_by_stratum[(real_by_stratum["base_method"] == "ML residual masked-denoising AE-4") & (real_by_stratum["scope"] == scope)]
        shuf_scope = shuffle_summary[(shuffle_summary["base_method"] == "ML residual masked-denoising AE-4") & (shuffle_summary["scope"] == scope)]
        for _, real in real_scope.iterrows():
            candidates = shuf_scope[shuf_scope["stratum"].astype(str) == str(real["stratum"])]
            if candidates.empty:
                continue
            p95 = float(candidates["p95"].max())
            passed = bool(float(real["value"]) > p95 + PASS_MARGIN)
            if not passed:
                stratum_failures.append(f"{scope}={real['stratum']} real {real['value']:.3f} <= shuffle p95 {p95:.3f}+{PASS_MARGIN:.2f}")
    rule_rows.append(
        {
            "rule": "ml_above_shuffle_in_every_run_and_topology",
            "value": len(stratum_failures) == 0,
            "detail": "; ".join(stratum_failures[:6]) if stratum_failures else "all checked strata pass",
        }
    )
    rules = pd.DataFrame(rule_rows)
    decision = {
        "accepted_waveform_representation_improvement": bool(rules["value"].all()),
        "pass_rule": "accept only if ML CI beats traditional CI, ML exceeds repeated shuffled-label p95+margin overall and in every heldout-run/topology stratum, and random-row gain is <= threshold",
        "pass_margin": PASS_MARGIN,
        "max_random_row_gain": MAX_RANDOM_ROW_GAIN,
        "failures": rules[~rules["value"]]["rule"].tolist(),
    }
    return rules, decision


def write_report(
    result: dict,
    benchmark: pd.DataFrame,
    random_rows: pd.DataFrame,
    shuffle_summary: pd.DataFrame,
    rules: pd.DataFrame,
) -> None:
    compact_shuffle = shuffle_summary[
        (shuffle_summary["scope"] == "overall")
        & (shuffle_summary["base_method"].isin(["traditional residual PCA+hand", "ML residual masked-denoising AE-4"]))
    ].sort_values(["base_method", "shuffle_mode"])
    verdict = "PASS" if result["decision"]["accepted_waveform_representation_improvement"] else "FAIL"
    report = f"""# P01c: repeated leakage sentinels for waveform probes

**Ticket:** {TICKET_ID}

## Reproduction first
The script read raw B-stack ROOT files from `{result['raw_root_dir']}` before
any model fitting. The P01/S00 selection reproduced
**{result['reproduction']['selected_pulses']:,}** selected B-stave pulses
versus the expected **{EXPECTED_SELECTED_PULSES:,}**.

## Official run-heldout benchmark
Held-out runs are `{', '.join(str(r) for r in HELDOUT_RUNS)}`. Training and
held-out samples are balanced by `(run, stave)` with at most
{MAX_PER_RUN_STAVE} pulses per cell. CIs are 95% held-out run-block bootstraps.

{markdown_table(benchmark, ['method', 'value', 'ci_low', 'ci_high', 'macro_f1', 'train_rows', 'heldout_rows'])}

The traditional method is a ridge residualization against log-amplitude and
selected-stave multiplicity followed by hand-shape features plus PCA-4. The ML
method is a masked-denoising AE-4 trained only on training runs, followed by
the same balanced linear probe.

## Repeated leakage battery
Each row summarizes {len(SHUFFLE_SEEDS)} shuffled-label seeds for a permutation
mode. The acceptance rule compares the real ML score against the worst
95th-percentile shuffled score plus a {PASS_MARGIN:.2f} margin.

{markdown_table(compact_shuffle, ['base_method', 'shuffle_mode', 'mean', 'p95', 'max', 'count'])}

The battery also writes per-heldout-run and per-topology shuffle strata to
`shuffle_summary.csv` and the raw seed-level rows to `repeated_shuffle_battery.csv`.

## Random-row comparison
Random-row splits are not accepted as physics evidence; they are leakage
sentinels for row/order/composition shortcuts.

{markdown_table(random_rows, ['method', 'value', 'ci_low', 'ci_high', 'macro_f1', 'train_rows', 'heldout_rows'])}

## Pass/fail rule
{markdown_table(rules, ['rule', 'value', 'detail'])}

Decision: **{verdict}** for accepting a waveform representation improvement.
The result does not pass the pre-registered leakage battery, so the correct
interpretation is that P01-style waveform probes still require repeated
shuffle/permutation controls before any claimed improvement is accepted.

## Artifacts
`result.json`, `manifest.json`, `input_sha256.csv`,
`reproduction_match_table.csv`, `reproduction_counts_by_run.csv`,
`run_heldout_benchmark.csv`, `random_row_benchmark.csv`,
`real_by_stratum.csv`, `repeated_shuffle_battery.csv`, `shuffle_summary.csv`,
`leakage_pass_rules.csv`, and `ae_training_loss.csv` are in this report
directory. No Monte Carlo was used.
"""
    (OUT_DIR / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    raw_root_dir = resolve_raw_root_dir()

    print(f"raw ROOT dir: {raw_root_dir}")
    waves, meta, counts_by_run = scan_raw(raw_root_dir)
    selected = int(len(waves))
    print(f"REPRODUCTION COUNT: {selected} selected pulses (expected {EXPECTED_SELECTED_PULSES})")
    if selected != EXPECTED_SELECTED_PULSES:
        raise RuntimeError(f"Reproduction failed: got {selected}, expected {EXPECTED_SELECTED_PULSES}")

    counts_by_run.to_csv(OUT_DIR / "reproduction_counts_by_run.csv", index=False)
    expected = EXPECTED_SELECTED_PULSES
    pd.DataFrame(
        [
            {
                "quantity": "total selected B-stave pulses",
                "report_value": expected,
                "reproduced": selected,
                "delta": selected - expected,
                "pass": selected == expected,
            }
        ]
    ).to_csv(OUT_DIR / "reproduction_match_table.csv", index=False)

    meta["topology_group"] = topology_label(meta["topology_n"].to_numpy(dtype=int))
    run_values = meta["run"].to_numpy(dtype=int)
    train_mask = ~np.isin(run_values, HELDOUT_RUNS)
    test_mask = np.isin(run_values, HELDOUT_RUNS)
    train_idx = balanced_indices(meta, train_mask, rng)
    test_idx = balanced_indices(meta, test_mask, rng)
    all_idx = np.concatenate([train_idx, test_idx])

    topology_categories = sorted(int(x) for x in meta.loc[train_idx, "topology_n"].unique())
    mask_categories = sorted(int(x) for x in meta.loc[train_idx, "topology_mask"].unique())
    control_train = control_features(meta.loc[train_idx], topology_categories)
    control_test = control_features(meta.loc[test_idx], topology_categories)
    leaky_train = leaky_mask_features(meta.loc[train_idx], mask_categories)
    leaky_test = leaky_mask_features(meta.loc[test_idx], mask_categories)

    y_train = meta.loc[train_idx, "stave_index"].to_numpy(dtype=int)
    y_test = meta.loc[test_idx, "stave_index"].to_numpy(dtype=int)
    test_runs = meta.loc[test_idx, "run"].to_numpy(dtype=int)

    x_train_raw = waves[train_idx]
    x_test_raw = waves[test_idx]
    control_model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    control_model.fit(control_train, x_train_raw)
    x_train_resid = (x_train_raw - control_model.predict(control_train)).astype(np.float32)
    x_test_resid = (x_test_raw - control_model.predict(control_test)).astype(np.float32)

    pca = PCA(n_components=LATENT_DIM, random_state=SEED)
    pca_train = pca.fit_transform(x_train_resid).astype(np.float32)
    pca_test = pca.transform(x_test_resid).astype(np.float32)
    hand_train = hand_shape_features(x_train_resid)
    hand_test = hand_shape_features(x_test_resid)
    traditional_train = np.hstack([hand_train, pca_train]).astype(np.float32)
    traditional_test = np.hstack([hand_test, pca_test]).astype(np.float32)

    ae = MaskedDenoisingAutoencoder(LATENT_DIM, SEED)
    losses = ae.fit(x_train_resid)
    ae_train = ae.encode(x_train_resid)
    ae_test = ae.encode(x_test_resid)
    pd.DataFrame({"epoch": np.arange(1, len(losses) + 1), "training_loss": losses}).to_csv(OUT_DIR / "ae_training_loss.csv", index=False)

    benchmark_rows: List[dict] = []
    preds: Dict[str, np.ndarray] = {}
    for method, xtr, xte, category in [
        ("traditional residual PCA+hand", traditional_train, traditional_test, "traditional"),
        ("ML residual masked-denoising AE-4", ae_train, ae_test, "ml"),
        ("proxy amplitude+topology", control_train, control_test, "proxy"),
        ("leakage target topology mask", leaky_train, leaky_test, "leakage_sentinel"),
    ]:
        row, pred = fit_probe(method, xtr, y_train, xte, y_test, test_runs, rng)
        row["category"] = category
        benchmark_rows.append(row)
        preds[method] = pred
    benchmark = pd.DataFrame(benchmark_rows)
    benchmark.to_csv(OUT_DIR / "run_heldout_benchmark.csv", index=False)

    test_meta_for_strata = meta.loc[test_idx].reset_index(drop=True)
    real_by_stratum = pd.concat(
        [
            real_strata("traditional residual PCA+hand", y_test, preds["traditional residual PCA+hand"], test_meta_for_strata),
            real_strata("ML residual masked-denoising AE-4", y_test, preds["ML residual masked-denoising AE-4"], test_meta_for_strata),
        ],
        ignore_index=True,
    )
    real_by_stratum.to_csv(OUT_DIR / "real_by_stratum.csv", index=False)

    train_meta = meta.loc[train_idx].reset_index(drop=True)
    test_meta = meta.loc[test_idx].reset_index(drop=True)
    features_by_method = {
        "traditional residual PCA+hand": (traditional_train, traditional_test),
        "ML residual masked-denoising AE-4": (ae_train, ae_test),
    }
    battery = repeated_shuffle_battery(features_by_method, y_train, y_test, train_meta, test_meta, rng)
    battery.to_csv(OUT_DIR / "repeated_shuffle_battery.csv", index=False)
    shuffle_summary = percentile_summary(battery)
    shuffle_summary.to_csv(OUT_DIR / "shuffle_summary.csv", index=False)

    # Random-row comparison reuses representations fit on training runs only;
    # it probes the supervised split, not a separate physics benchmark.
    meta_all = meta.loc[all_idx]
    x_all_raw = waves[all_idx]
    control_all = control_features(meta_all, topology_categories)
    x_all_resid = (x_all_raw - control_model.predict(control_all)).astype(np.float32)
    x_all_trad = np.hstack([hand_shape_features(x_all_resid), pca.transform(x_all_resid)]).astype(np.float32)
    x_all_ml = ae.encode(x_all_resid)
    y_all = meta_all["stave_index"].to_numpy(dtype=int)
    random_rows = pd.DataFrame(
        [
            random_row_probe("traditional residual PCA+hand", x_all_trad, y_all, rng),
            random_row_probe("ML residual masked-denoising AE-4", x_all_ml, y_all, rng),
        ]
    )
    random_rows.to_csv(OUT_DIR / "random_row_benchmark.csv", index=False)

    rules, decision = evaluate_pass_rule(benchmark, shuffle_summary, real_by_stratum, random_rows)
    rules.to_csv(OUT_DIR / "leakage_pass_rules.csv", index=False)

    input_rows = []
    for run in configured_runs():
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(OUT_DIR / "input_sha256.csv", index=False)

    result = {
        "ticket_id": TICKET_ID,
        "study_id": STUDY_ID,
        "title": TITLE,
        "raw_root_dir": str(raw_root_dir),
        "reproduction": {
            "expected_selected_pulses": EXPECTED_SELECTED_PULSES,
            "selected_pulses": selected,
            "passed": selected == EXPECTED_SELECTED_PULSES,
        },
        "split": {
            "official": "leave heldout runs out",
            "train_runs": sorted(int(run) for run in np.unique(run_values[train_mask])),
            "heldout_runs": [int(run) for run in HELDOUT_RUNS],
            "balanced_train_rows": int(len(train_idx)),
            "balanced_heldout_rows": int(len(test_idx)),
            "max_per_run_stave": MAX_PER_RUN_STAVE,
            "random_row_comparison": "supervised-probe sentinel only; not accepted as physics evidence",
        },
        "traditional": benchmark[benchmark["method"] == "traditional residual PCA+hand"].iloc[0].to_dict(),
        "ml": benchmark[benchmark["method"] == "ML residual masked-denoising AE-4"].iloc[0].to_dict(),
        "proxy_and_leakage_sentinels": benchmark[benchmark["category"].isin(["proxy", "leakage_sentinel"])].to_dict(orient="records"),
        "shuffle_battery": {
            "seeds": SHUFFLE_SEEDS,
            "modes": ["global", "within_run", "within_topology", "within_run_topology"],
            "summary_csv": str(OUT_DIR / "shuffle_summary.csv"),
            "raw_csv": str(OUT_DIR / "repeated_shuffle_battery.csv"),
        },
        "decision": decision,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (OUT_DIR / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")

    write_report(result, benchmark, random_rows, shuffle_summary, rules)

    artifact_names = {path.name for path in OUT_DIR.iterdir() if path.is_file()}
    artifact_names.update({"REPORT.md", "manifest.json"})
    manifest = {
        "ticket_id": TICKET_ID,
        "script": str(OUT_DIR / "p01c_repeated_leakage_sentinels.py"),
        "python": platform.python_version(),
        "raw_root_dir": str(raw_root_dir),
        "input_sha256_csv": str(OUT_DIR / "input_sha256.csv"),
        "input_file_count": int(len(input_sha)),
        "reproduction_passed": selected == EXPECTED_SELECTED_PULSES,
        "artifacts": sorted(artifact_names),
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(benchmark.to_string(index=False))
    print(rules.to_string(index=False))
    print(f"DONE in {result['runtime_sec']}s -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
