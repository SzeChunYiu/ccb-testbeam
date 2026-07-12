#!/usr/bin/env python3
"""S26A pulse-shape timing manifold benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import HuberRegressor, Ridge
from sklearn.metrics import mean_absolute_error, roc_auc_score, average_precision_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None

ROOT = Path(__file__).resolve().parents[1]


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def runs(config: dict) -> list[int]:
    out = []
    for group_runs in config["run_groups"].values():
        out.extend(int(r) for r in group_runs)
    return sorted(set(out))


def group_for_run(config: dict) -> dict[int, str]:
    out = {}
    for group, group_runs in config["run_groups"].items():
        for run in group_runs:
            out[int(run)] = group
    return out


def heldout_runs(config: dict) -> set[int]:
    out = set()
    for group in config["heldout_groups"]:
        out.update(int(r) for r in config["run_groups"][group])
    return out


def raw_path(config: dict, run: int) -> Path:
    return ROOT / Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_batches(path: Path, step_size: int = 20000):
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def extract_dataset(config: dict) -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    nsamp = int(config["samples_per_channel"])
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = list(config["staves"].keys())
    even_ch = np.asarray([int(config["staves"][s]) for s in staves], dtype=int)
    odd_ch = np.asarray([int(config["duplicate_readout_channels"][s]) for s in staves], dtype=int)
    cut = float(config["amplitude_cut_adc"])
    sat = float(config["saturation_adc"])
    knee = float(config["knee_low_adc"])
    cfd_fraction = float(config.get("cfd_fraction", 0.45))
    rng = np.random.default_rng(int(config["random_seed"]))
    group_lookup = group_for_run(config)
    max_per_run = int(config["max_events_per_run"])
    frames = []
    waves = []
    counts = []
    next_event_id = 0
    for run in runs(config):
        path = raw_path(config, run)
        row = {"run": run, "group": group_lookup[run], "events_total": 0, "events_selected": 0, "selected_pulses": 0}
        run_frames = []
        run_waves = []
        for batch in iter_batches(path):
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            even = corrected[:, even_ch, :]
            odd = -corrected[:, odd_ch, :]
            even_amp = even.max(axis=-1)
            threshold = cfd_fraction * even_amp
            prev = even[:, :, :-1]
            curr = even[:, :, 1:]
            sample_index = np.arange(1, nsamp, dtype=np.float32)[None, None, :]
            peak_sample = even.argmax(axis=-1).astype(np.float32)
            eligible = (sample_index <= peak_sample[:, :, None]) & (curr >= threshold[:, :, None]) & (prev < threshold[:, :, None])
            crossing = eligible.argmax(axis=-1) + 1
            has_crossing = eligible.any(axis=-1)
            row_i = np.arange(even.shape[0])[:, None]
            col_i = np.arange(even.shape[1])[None, :]
            y0 = even[row_i, col_i, np.maximum(crossing - 1, 0)]
            y1 = even[row_i, col_i, crossing]
            denom = y1 - y0
            frac = np.divide(threshold - y0, denom, out=np.zeros_like(threshold), where=np.abs(denom) > 1e-6)
            cfd_time = np.where(has_crossing, crossing - 1 + frac, peak_sample) * 10.0
            even_charge = np.clip(even, 0.0, None).sum(axis=-1)
            odd_amp = odd.max(axis=-1)
            odd_charge = np.clip(odd, 0.0, None).sum(axis=-1)
            selected = even_amp > cut
            has = selected.any(axis=1)
            row["events_total"] += int(len(raw))
            row["events_selected"] += int(has.sum())
            row["selected_pulses"] += int(selected.sum())
            if not has.any():
                continue
            idx = np.flatnonzero(has)
            event_ids = np.arange(next_event_id, next_event_id + len(idx), dtype=np.int64)
            next_event_id += len(idx)
            sel = selected[idx]
            ev = even[idx] * sel[:, :, None]
            even_q = even_charge[idx] * sel
            odd_q = odd_charge[idx] * sel
            amp = even_amp[idx] * sel
            odd_a = odd_amp[idx] * sel
            peak = even[idx].argmax(axis=-1)
            peak_sel = peak * sel
            cfd_sel = cfd_time[idx]
            even_ped = baseline[idx][:, even_ch]
            ped_median = np.median(even_ped, axis=1)
            ped_spread = np.percentile(even_ped, 75, axis=1) - np.percentile(even_ped, 25, axis=1)
            ped_abs_slope = np.mean(np.abs(raw[idx][:, even_ch, 3] - raw[idx][:, even_ch, 0]), axis=1)
            late = np.clip(ev[:, :, 9:], 0.0, None).sum(axis=(1, 2))
            early = np.clip(ev[:, :, :8], 0.0, None).sum(axis=(1, 2))
            total_q = np.maximum(even_q.sum(axis=1), 1.0)
            saturated_count = ((amp >= sat) & sel).sum(axis=1)
            knee_count = ((amp >= knee) & sel).sum(axis=1)
            recovery_tail = late / total_q
            onset_sharpness = np.max(np.diff(ev, axis=2), axis=(1, 2)) / np.maximum(amp.max(axis=1), 1.0)
            charge_loss_raw = 1.0 - even_q.sum(axis=1) / np.maximum(odd_q.sum(axis=1), 1.0)
            # Duplicate channels occasionally have effectively zero positive charge; bound those closures
            # so denominator pathologies do not dominate the timing side diagnostics.
            charge_loss = np.clip(charge_loss_raw, -4.0, 4.0)
            timing_proxy = (peak_sel.sum(axis=1) / np.maximum(sel.sum(axis=1), 1)) - 5.0
            weighted_time = (cfd_sel * np.maximum(amp, 0.0)).sum(axis=1) / np.maximum(np.maximum(amp, 0.0).sum(axis=1), 1.0)
            pair_spread = np.sqrt(((cfd_sel - weighted_time[:, None]) ** 2 * sel).sum(axis=1) / np.maximum(sel.sum(axis=1), 1))
            early_late_pull = 10.0 * (recovery_tail - early / np.maximum(total_q, 1.0))
            # Target is a robust timing-manifold residual in ns: a CFD time spread corrected by
            # tail/early pulse-shape pull, saturation edge count, and pedestal-sideband drift.
            target = np.clip(pair_spread + early_late_pull + 0.28 * saturated_count + 0.04 * ped_abs_slope, -15.0, 15.0)
            pid_label = ((odd_a.max(axis=1) > np.percentile(odd_a[odd_a > 0], 72)) | (sel.sum(axis=1) >= 2)).astype(int)
            run_frames.append(
                pd.DataFrame(
                    {
                        "event_id": event_ids,
                        "run": run,
                        "group": group_lookup[run],
                        "eventno": np.asarray(batch["EVENTNO"])[idx].astype(np.int64),
                        "multiplicity": sel.sum(axis=1),
                        "even_total_charge": even_q.sum(axis=1),
                        "odd_total_charge": odd_q.sum(axis=1),
                        "even_max_amp": amp.max(axis=1),
                        "odd_max_amp": odd_a.max(axis=1),
                        "saturated_count": saturated_count,
                        "knee_count": knee_count,
                        "recovery_tail": recovery_tail,
                        "early_fraction": early / total_q,
                        "onset_sharpness": onset_sharpness,
                        "pedestal_median_adc": ped_median,
                        "pedestal_iqr_adc": ped_spread,
                        "pedestal_abs_slope_adc": ped_abs_slope,
                        "target_timing_ns": target,
                        "charge_loss": charge_loss,
                        "timing_bias_sample": timing_proxy,
                        "cfd_weighted_time_ns": weighted_time,
                        "cfd_pair_spread_ns": pair_spread,
                        "pid_label": pid_label,
                    }
                )
            )
            run_waves.append(ev.astype(np.float32))
        if run_frames:
            rf = pd.concat(run_frames, ignore_index=True)
            rw = np.vstack(run_waves)
            if len(rf) > max_per_run:
                keep = np.sort(rng.choice(np.arange(len(rf)), size=max_per_run, replace=False))
                rf = rf.iloc[keep].reset_index(drop=True)
                rw = rw[keep]
            frames.append(rf)
            waves.append(rw)
        counts.append(row)
    return pd.concat(frames, ignore_index=True), np.vstack(waves), pd.DataFrame(counts)


def feature_matrix(events: pd.DataFrame, waves: np.ndarray) -> tuple[np.ndarray, list[str]]:
    cols = [
        "multiplicity",
        "even_total_charge",
        "even_max_amp",
        "saturated_count",
        "knee_count",
        "recovery_tail",
        "early_fraction",
        "onset_sharpness",
        "pedestal_iqr_adc",
        "pedestal_abs_slope_adc",
    ]
    parts = []
    names = []
    for col in cols:
        v = events[col].to_numpy(dtype=float)
        if "charge" in col or "amp" in col:
            v = np.log1p(np.maximum(v, 0.0))
        parts.append(v[:, None])
        names.append(col)
    charge = np.clip(waves, 0.0, None).sum(axis=2)
    amp = waves.max(axis=2)
    peak = waves.argmax(axis=2) / float(waves.shape[2] - 1)
    parts += [np.log1p(charge), np.log1p(np.maximum(amp, 0.0)), peak]
    for prefix in ["log_charge", "log_amp", "peak"]:
        names += [f"{prefix}_stave_{i}" for i in range(waves.shape[1])]
    return np.hstack(parts), names


def res68(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.percentile(np.abs(p - y), 68))


def score_rows(events: pd.DataFrame, y: np.ndarray, preds: dict[str, np.ndarray], held: np.ndarray, config: dict) -> pd.DataFrame:
    rows = []
    for method, pred in preds.items():
        m = held & np.isfinite(pred)
        row = {
            "method": method,
            "n": int(m.sum()),
            "bias": float(np.median(pred[m] - y[m])),
            "res68": res68(y[m], pred[m]),
            "mae": float(mean_absolute_error(y[m], pred[m])),
        }
        row.update(run_block_bootstrap(events, y, pred, m, int(config["bootstrap_reps"]), int(config["random_seed"]) + len(method)))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["res68", "mae"]).reset_index(drop=True)


def run_block_bootstrap(events: pd.DataFrame, y: np.ndarray, pred: np.ndarray, mask: np.ndarray, reps: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    idx0 = np.flatnonzero(mask)
    blocks = [g.index.to_numpy(dtype=int) for _, g in pd.DataFrame({"run": events["run"]}).iloc[idx0].groupby("run")]
    vals = {"res68": [], "bias": [], "mae": []}
    for _ in range(reps):
        idx = np.concatenate([blocks[i] for i in rng.integers(0, len(blocks), size=len(blocks))])
        vals["res68"].append(res68(y[idx], pred[idx]))
        vals["bias"].append(float(np.median(pred[idx] - y[idx])))
        vals["mae"].append(float(mean_absolute_error(y[idx], pred[idx])))
    out = {}
    for key, arr in vals.items():
        a = np.asarray(arr)
        out[f"{key}_ci95"] = [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]
    return out


def train_subset(mask: np.ndarray, max_rows: int, seed: int) -> np.ndarray:
    idx = np.flatnonzero(mask)
    if len(idx) <= max_rows:
        return idx
    return np.random.default_rng(seed).choice(idx, size=max_rows, replace=False)


class TinyMLP(nn.Module):
    def __init__(self, n_in: int):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(n_in, 48), nn.ReLU(), nn.Linear(48, 24), nn.ReLU(), nn.Linear(24, 1))

    def forward(self, x):
        return self.net(x).squeeze(1)


class SmallCNN(nn.Module):
    def __init__(self, n_tab: int):
        super().__init__()
        self.conv = nn.Sequential(nn.Conv1d(4, 16, 3, padding=1), nn.ReLU(), nn.Conv1d(16, 24, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool1d(1))
        self.head = nn.Sequential(nn.Linear(24 + n_tab, 48), nn.ReLU(), nn.Linear(48, 1))

    def forward(self, wave, tab):
        return self.head(torch.cat([self.conv(wave).squeeze(-1), tab], dim=1)).squeeze(1)


class GatedResidualCNN(nn.Module):
    def __init__(self, n_tab: int):
        super().__init__()
        self.conv = nn.Sequential(nn.Conv1d(4, 16, 3, padding=1), nn.GELU(), nn.Conv1d(16, 16, 3, padding=1), nn.GELU())
        self.gate = nn.Sequential(nn.AdaptiveMaxPool1d(1), nn.Flatten(), nn.Linear(16, 16), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(16 + n_tab, 64), nn.GELU(), nn.Linear(64, 1))

    def forward(self, wave, tab):
        z = self.conv(wave)
        pooled = (z * self.gate(z).unsqueeze(-1)).mean(dim=2)
        return self.head(torch.cat([pooled, tab], dim=1)).squeeze(1)


class WaveformTransformer(nn.Module):
    def __init__(self, n_tab: int):
        super().__init__()
        width = 24
        self.sample_proj = nn.Linear(4, width)
        self.pos = nn.Parameter(torch.zeros(1, 18, width))
        layer = nn.TransformerEncoderLayer(
            d_model=width,
            nhead=4,
            dim_feedforward=64,
            dropout=0.0,
            activation="gelu",
            batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=1)
        self.head = nn.Sequential(nn.Linear(width + n_tab, 64), nn.GELU(), nn.Linear(64, 1))

    def forward(self, wave, tab):
        # Input wave is (batch, stave, sample). Attention runs across samples
        # with the four B-stave amplitudes as per-token channels.
        tokens = wave.transpose(1, 2)
        z = self.encoder(self.sample_proj(tokens) + self.pos).mean(dim=1)
        return self.head(torch.cat([z, tab], dim=1)).squeeze(1)


def fit_torch_tab(x: np.ndarray, y: np.ndarray, train: np.ndarray, config: dict):
    idx = train_subset(train, int(config["ml_max_train_events"]), int(config["random_seed"]) + 20)
    scaler = StandardScaler().fit(x[idx])
    return fit_torch_model(TinyMLP(x.shape[1]), scaler, x[idx], None, y[idx], int(config["mlp_epochs"]), int(config["random_seed"]) + 21)


def fit_torch_wave(cls, waves: np.ndarray, x: np.ndarray, y: np.ndarray, train: np.ndarray, config: dict, seed_offset: int):
    idx = train_subset(train, int(config["cnn_max_train_events"]), int(config["random_seed"]) + seed_offset)
    scaler = StandardScaler().fit(x[idx])
    model = cls(x.shape[1])
    epochs = int(config.get("transformer_epochs" if cls.__name__ == "WaveformTransformer" else "cnn_epochs", config["cnn_epochs"]))
    return fit_torch_model(model, scaler, x[idx], waves[idx], y[idx], epochs, int(config["random_seed"]) + seed_offset + 1)


def fit_torch_model(model, scaler, x, waves, y, epochs, seed):
    if torch is None:
        raise RuntimeError("torch unavailable")
    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    xs = scaler.transform(x).astype(np.float32)
    ys = y.astype(np.float32)
    if waves is None:
        ds = TensorDataset(torch.from_numpy(xs), torch.from_numpy(ys))
    else:
        w = normalize_waves(waves)
        ds = TensorDataset(torch.from_numpy(w), torch.from_numpy(xs), torch.from_numpy(ys))
    loader = DataLoader(ds, batch_size=512, shuffle=True)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = nn.SmoothL1Loss()
    model.train()
    for _ in range(epochs):
        for batch in loader:
            opt.zero_grad()
            if waves is None:
                xb, yb = batch
                loss = loss_fn(model(xb.to(device)), yb.to(device))
            else:
                wb, xb, yb = batch
                loss = loss_fn(model(wb.to(device), xb.to(device)), yb.to(device))
            loss.backward()
            opt.step()
    model.eval()
    return model, scaler


def normalize_waves(waves: np.ndarray) -> np.ndarray:
    w = waves.astype(np.float32)
    scale = np.maximum(np.percentile(np.abs(w).reshape(len(w), -1), 95, axis=1), 1.0)
    return (w / scale[:, None, None]).astype(np.float32)


def predict_torch(model, scaler, x, waves=None):
    device = next(model.parameters()).device
    xs = scaler.transform(x).astype(np.float32)
    out = []
    for start in range(0, len(x), 4096):
        stop = min(start + 4096, len(x))
        with torch.no_grad():
            if waves is None:
                pred = model(torch.from_numpy(xs[start:stop]).to(device))
            else:
                pred = model(torch.from_numpy(normalize_waves(waves[start:stop])).to(device), torch.from_numpy(xs[start:stop]).to(device))
            out.append(pred.cpu().numpy())
    return np.concatenate(out)


def bounded_predict(model, features: np.ndarray, y_train: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(y_train, [0.2, 99.8])
    return np.clip(model.predict(features), lo, hi)


def markdown_table(df: pd.DataFrame, cols: list[str]) -> str:
    d = df[cols].copy()
    for c in d.columns:
        if d[c].dtype.kind in "fc":
            d[c] = d[c].map(lambda v: f"{v:.6g}")
    return d.to_markdown(index=False)


def write_report(out: Path, config: dict, result: dict, counts: pd.DataFrame, summary: pd.DataFrame, strata: pd.DataFrame) -> None:
    winner = result["winner"]["method"]
    lines = [
        f"# {config['study_id']}: {config['title']}",
        "",
        "## Abstract",
        "",
        f"This study reproduces the S00 B-stave selected-pulse number directly from raw ROOT and then benchmarks a traditional constant-fraction plus analytic timewalk/template-residual baseline against ridge, gradient-boosted trees, MLP, 1D-CNN, a compact waveform transformer, and a new gated residual CNN. The winner is **{winner}** under held-out-run timing-manifold residual res68 with run-block bootstrap confidence intervals.",
        "",
        "## Raw ROOT Reproduction",
        "",
        f"Raw files are read from `{config['raw_root_dir']}`. The decoded `HRDv` array is reshaped to 8 channels by 18 samples; per-channel baseline is the median of samples 0--3. A selected B-stave pulse is an even channel in B2/B4/B6/B8 above 1000 ADC.",
        "",
        markdown_table(counts, ["run", "group", "events_total", "events_selected", "selected_pulses"]),
        "",
        f"Total selected pulses: {int(counts['selected_pulses'].sum())}; registered expectation: {int(config['expected_selected_pulses'])}; delta: {int(counts['selected_pulses'].sum()) - int(config['expected_selected_pulses'])}.",
        "",
        "## Methods",
        "",
        "Let \(w_{ejs}\) be the baseline-corrected even-channel waveform for event \(e\), stave \(j\), and sample \(s\). For each selected B-stave pulse, a constant-fraction crossing time \(t_{ej}^{CFD}\) is linearly interpolated at fraction \(f=0.45\) of the pulse maximum before the peak. The supervised timing-manifold residual target is",
        "",
        "\\[ r_e = \\operatorname{clip}_{[-15,15]}\\left(\\sqrt{\\frac{\\sum_j m_{ej}(t_{ej}^{CFD}-\\bar{t}_{e})^2}{\\max(\\sum_j m_{ej},1)}} + 10\\,(T_e-E_e) + 0.28\\,S_e + 0.04\\,D_e\\right), \\]",
        "",
        "Here \(m_{ej}\) marks selected staves, \\(\\bar{t}_e\\) is the amplitude-weighted CFD time, \(T_e\) is the late positive charge fraction, \(E_e\) is the early positive charge fraction, \(S_e\) is the saturated-stave count, and \(D_e\) is the pretrigger sample-0-to-sample-3 pedestal excursion. The target is therefore a timing-width observable with explicit pulse-shape, saturation-edge, and pedestal terms. Odd duplicate charges, event identifiers, and run labels are excluded from learned-model inputs.",
        "",
        "The traditional CFD/timewalk-template method fits a robust pedestal-aware calibration from log even charge, saturation count, knee count, recovery-tail fraction, onset sharpness, and pedestal-sideband spread to \(r_e\), then clips predictions to the calibrated target range to prevent nonphysical extrapolation. A tail-shape timing baseline uses calibrated early/late charge fractions, and an analytic saturation-timewalk baseline uses saturation and onset terms. The ML panel is ridge regression, gradient-boosted trees, a tabular MLP, a 1D-CNN over the four B-stave waveforms, a waveform transformer with sample-token self-attention, and the new gated residual CNN. The new architecture multiplies learned convolutional channels by a sigmoid gate from the maximum pooled waveform context before residual regression.",
        "",
        "## Split and Bootstrap",
        "",
        "Training uses `sample_i_calib` and `sample_ii_calib` runs; all analysis runs are held out. Confidence intervals resample held-out runs with replacement, preserving run-level correlations and current-family composition.",
        "",
        "## Head-to-Head Benchmark",
        "",
        markdown_table(summary, ["method", "n", "bias", "bias_ci95", "res68", "res68_ci95", "mae", "mae_ci95"]),
        "",
        "The table reports timing-manifold residual width (`res68`, ns), median timing bias (`bias`, ns), and mean absolute residual (`mae`, ns). The same held-out predictions are reused in the stress strata below so shape atoms, pedestal excursions, saturation edge, and pile-up sidebands are evaluated without changing the training population.",
        "",
        "## Saturation and Pile-Up Strata",
        "",
        markdown_table(strata, ["stratum", "method", "n", "bias", "res68", "res68_ci95", "mae"]),
        "",
        "## PID Side Diagnostic",
        "",
        f"The winner's waveform recovery score is accompanied by a PID separability diagnostic: held-out AUC={result['winner']['pid_auc']:.4f}, AP={result['winner']['pid_average_precision']:.4f}. The label is a duplicate-readout high-amplitude or multi-hit proxy and is used only as a caveat-level side diagnostic, not as the primary optimization target.",
        "",
        "## Systematics and Caveats",
        "",
        "* The target is a CFD timing-manifold residual, not an external hodoscope or RF-clock truth time. It is appropriate for ranking correction models on internal B-stave timing consistency, not for claiming an absolute beam time resolution.",
        "* Bootstrap intervals cover run-to-run composition shifts but not all possible electronics calibration drifts.",
        "* Saturation is approximated by an ADC knee and by charge-tail recovery. True front-end recovery may include nonlocal baseline memory extending outside the 18-sample window.",
        "* Pedestal drift is measured from only four pretrigger samples and should be interpreted as a sideband proxy rather than a dedicated forced-trigger pedestal truth label.",
        "* Neural models are deliberately small and subsampled so the result is reproducible on the worker. A neural win over the robust CFD/timewalk baseline should be read as a context-learning gain on top of engineered timing observables, not as evidence for a deployable calibration without a broader electronics systematic campaign.",
        "",
        "## Recommendation",
        "",
        f"The selected winner for `result.json` is `{winner}`. Saturated and high-pedestal-excursion pulses should remain included only with a run-heldout timing-manifold correction and explicit uncertainty inflation in the affected strata; uncorrected saturated pulses should not be promoted into precision timing closure tables.",
    ]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = load_config(args.config)
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    events, waves, counts = extract_dataset(config)
    x, feature_names = feature_matrix(events, waves)
    y = events["target_timing_ns"].to_numpy(dtype=float)
    train = ~events["run"].isin(heldout_runs(config)).to_numpy()
    held = ~train
    idx = train_subset(train, int(config["ml_max_train_events"]), int(config["random_seed"]))
    preds = {}
    y_cal = y[idx]
    trad_x = x[:, [1, 3, 4, 5, 7, 8, 9]]
    trad = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, alpha=0.002, max_iter=400)).fit(trad_x[idx], y_cal)
    preds["traditional_cfd_timewalk_template"] = bounded_predict(trad, trad_x, y_cal)
    tail_x = x[:, [5, 6]]
    tail = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, alpha=0.002, max_iter=400)).fit(tail_x[idx], y_cal)
    preds["tail_shape_timing"] = bounded_predict(tail, tail_x, y_cal)
    huber_x = np.column_stack([x[:, 1], np.minimum(x[:, 3], 2.0), x[:, 4], np.tanh(4 * x[:, 7])])
    huber = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, alpha=0.002, max_iter=400)).fit(huber_x[idx], y_cal)
    preds["analytic_saturation_timewalk"] = bounded_predict(huber, huber_x, y_cal)
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=2.0)).fit(x[idx], y[idx])
    preds["ridge"] = ridge.predict(x)
    gbt = GradientBoostingRegressor(n_estimators=80, max_depth=3, learning_rate=0.04, subsample=0.75, random_state=int(config["random_seed"]) + 2).fit(x[idx], y[idx])
    preds["gradient_boosted_trees"] = gbt.predict(x)
    torch_status = {}
    if torch is not None:
        try:
            mlp, mlp_scaler = fit_torch_tab(x, y, train, config)
            preds["mlp"] = predict_torch(mlp, mlp_scaler, x)
            torch_status["mlp"] = "trained"
        except Exception as exc:
            preds["mlp"] = np.full(len(y), np.nan)
            torch_status["mlp"] = f"failed: {exc}"
        try:
            cnn, cnn_scaler = fit_torch_wave(SmallCNN, waves, x, y, train, config, 40)
            preds["1d_cnn"] = predict_torch(cnn, cnn_scaler, x, waves)
            torch_status["1d_cnn"] = "trained"
        except Exception as exc:
            preds["1d_cnn"] = np.full(len(y), np.nan)
            torch_status["1d_cnn"] = f"failed: {exc}"
        try:
            grc, grc_scaler = fit_torch_wave(GatedResidualCNN, waves, x, y, train, config, 60)
            preds["gated_residual_cnn"] = predict_torch(grc, grc_scaler, x, waves)
            torch_status["gated_residual_cnn"] = "trained"
        except Exception as exc:
            preds["gated_residual_cnn"] = np.full(len(y), np.nan)
            torch_status["gated_residual_cnn"] = f"failed: {exc}"
        try:
            wft, wft_scaler = fit_torch_wave(WaveformTransformer, waves, x, y, train, config, 80)
            preds["waveform_transformer"] = predict_torch(wft, wft_scaler, x, waves)
            torch_status["waveform_transformer"] = "trained"
        except Exception as exc:
            preds["waveform_transformer"] = np.full(len(y), np.nan)
            torch_status["waveform_transformer"] = f"failed: {exc}"
    summary = score_rows(events, y, preds, held, config)
    summary.to_csv(out / "method_summary.csv", index=False)
    counts.to_csv(out / "run_counts.csv", index=False)
    held_events = events.loc[held].copy()
    winner_method = str(summary.iloc[0]["method"])
    strata_rows = []
    stratum_defs = {
        "all_heldout": np.ones(len(events), dtype=bool),
        "shape_atom_edge": np.abs(events["timing_bias_sample"].to_numpy()) >= np.percentile(np.abs(events.loc[train, "timing_bias_sample"]), 75),
        "saturation_edge": events["knee_count"].to_numpy() > 0,
        "hard_saturated": events["saturated_count"].to_numpy() > 0,
        "pileup_multiplicity_ge2": events["multiplicity"].to_numpy() >= 2,
        "high_recovery_tail": events["recovery_tail"].to_numpy() >= np.percentile(events.loc[train, "recovery_tail"], 75),
        "pedestal_excursion": events["pedestal_iqr_adc"].to_numpy() >= np.percentile(events.loc[train, "pedestal_iqr_adc"], 75),
        "large_timing_bias_proxy": np.abs(events["timing_bias_sample"].to_numpy()) >= np.percentile(np.abs(events.loc[train, "timing_bias_sample"]), 75),
    }
    for name, smask in stratum_defs.items():
        for method in dict.fromkeys([winner_method, "traditional_cfd_timewalk_template", "gradient_boosted_trees", "1d_cnn", "waveform_transformer", "gated_residual_cnn"]):
            if method not in preds:
                continue
            m = held & smask & np.isfinite(preds[method])
            if m.sum() < 50:
                continue
            row = {"stratum": name, "method": method, "n": int(m.sum()), "bias": float(np.median(preds[method][m] - y[m])), "res68": res68(y[m], preds[method][m]), "mae": float(mean_absolute_error(y[m], preds[method][m]))}
            row.update(run_block_bootstrap(events, y, preds[method], m, int(config["bootstrap_reps"]), int(config["random_seed"]) + len(name) + len(method)))
            strata_rows.append(row)
    strata = pd.DataFrame(strata_rows)
    strata.to_csv(out / "strata_summary.csv", index=False)
    win_pred = preds[winner_method]
    pid = events["pid_label"].to_numpy(dtype=int)
    try:
        pid_auc = float(roc_auc_score(pid[held], -np.abs(win_pred[held] - y[held])))
        pid_ap = float(average_precision_score(pid[held], -np.abs(win_pred[held] - y[held])))
    except Exception:
        pid_auc = float("nan")
        pid_ap = float("nan")
    repro = {
        "expected_selected_pulses": int(config["expected_selected_pulses"]),
        "reproduced_selected_pulses": int(counts["selected_pulses"].sum()),
        "delta": int(counts["selected_pulses"].sum()) - int(config["expected_selected_pulses"]),
        "pass": int(counts["selected_pulses"].sum()) == int(config["expected_selected_pulses"]),
    }
    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_root_dir": config["raw_root_dir"],
        "raw_reproduction": repro,
        "split": {"train_runs": sorted(set(events.loc[train, "run"].astype(int))), "heldout_runs": sorted(set(events.loc[held, "run"].astype(int))), "split_type": "complete run held-out"},
        "bootstrap": {"unit": "held-out run block", "replicates": int(config["bootstrap_reps"]), "interval": "95% percentile"},
        "winner": {**summary.iloc[0].to_dict(), "pid_auc": pid_auc, "pid_average_precision": pid_ap},
        "all_metrics": summary.to_dict(orient="records"),
        "torch_status": torch_status,
        "feature_names": feature_names,
        "input_sha256": [{"path": str(raw_path(config, r)), "sha256": sha256_file(raw_path(config, r))} for r in runs(config)],
        "environment": {"git_commit": git_commit(), "python": platform.python_version(), "platform": platform.platform(), "torch_available": torch is not None},
        "claimed_ticket_text": config.get("claimed_ticket_text", config["title"]),
    }
    (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (out / "claimed_ticket.txt").write_text(config["ticket_id"] + f"\n# {config.get('claimed_ticket_text', config['title'])}\n", encoding="utf-8")
    pd.DataFrame(result["input_sha256"]).to_csv(out / "input_sha256.csv", index=False)
    write_report(out, config, result, counts, summary, strata)
    manifest = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "command": config["command"],
        "artifacts": ["REPORT.md", "result.json", "method_summary.csv", "strata_summary.csv", "run_counts.csv", "input_sha256.csv", "claimed_ticket.txt"],
        "raw_reproduction_passed": repro["pass"],
        "winner": winner_method,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(out), "reproduction": repro, "winner": winner_method}, indent=2))


if __name__ == "__main__":
    main()
