#!/usr/bin/env python3
"""S37b residual-stack deconvolution on high-current pile-up candidates.

This ticket-local runner reproduces the B-stack raw ROOT count, builds the
controlled training benchmark used by the audited S25/S26/S36 family, and
freezes held-out evaluation to high-current source runs that prior hand-scan
work identified as the real pile-up candidate surface.
"""

from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402
import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as base  # noqa: E402
import s26b_1783798536_2368_2ce12433_saturation_energy_recovery_architecture_bakeoff as seqbase  # noqa: E402

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


TICKET = "1784068324.1054.23ed295f"
WORKER = "testbeam-laptop-2"
SLUG = "s37b_residual_stack_handscan_pileup_validation"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/extracted/root/root")
LOW_CURRENT_RUNS = [46, 47]
HIGH_CURRENT_RUNS = [44, 45, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]
HANDSCAN_SOURCES = [
    "reports/1781146783.955.745c6984__s11h_blinded_real_current_waveform_adjudication/blinded_gallery_adjudication.csv",
    "reports/1781191650.1263.35bb131f__p05g_blinded_handscan_validation/blinded_candidate_ledger.csv",
    "reports/1783605034.12126.04fe4a38__s01j_external_handscan_transfer/handscan_feature_table.csv",
]


def load_config() -> dict:
    cfg = base.load_base_config()
    cfg.update(
        {
            "study_id": "S37b",
            "ticket_id": TICKET,
            "title": "S37b residual-stack deconvolution on high-current pile-up candidates",
            "worker": WORKER,
            "raw_root_dir": str(RAW_ROOT_DIR),
            "output_dir": str(OUT),
            "random_seed": 2026071502,
            "benchmark_runs": {"train": LOW_CURRENT_RUNS, "heldout": HIGH_CURRENT_RUNS},
            "max_clean_pulses_per_run_stave": 88,
            "injected_per_train_run": 66,
            "clean_per_train_run": 66,
            "injected_per_heldout_run": 44,
            "clean_per_heldout_run": 44,
        }
    )
    cfg["ml"].update({"bootstrap_samples": 400, "cnn_epochs": 80, "cnn_channels": 12, "max_iter": 240})
    cfg["source_bootstrap_samples"] = 120
    return cfg


class PileupMaskTransformer(nn.Module):
    """Compact transformer with explicit overlap-window mask channel."""

    def __init__(self, n_samples: int) -> None:
        super().__init__()
        self.embed = nn.Linear(2, 28)
        self.position = nn.Parameter(torch.zeros(1, n_samples, 28))
        layer = nn.TransformerEncoderLayer(
            d_model=28,
            nhead=4,
            dim_feedforward=72,
            dropout=0.05,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=1)
        self.norm = nn.LayerNorm(28)
        self.class_head = nn.Linear(28, 1)
        self.reg_head = nn.Linear(28, 4)

    def forward(self, x: torch.Tensor, mask_channel: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        h = self.embed(torch.stack([x, mask_channel], dim=-1)) + self.position
        h = self.encoder(h)
        weights = 1.0 + mask_channel
        pooled = (h * weights[..., None]).sum(dim=1) / weights.sum(dim=1, keepdim=True).clamp_min(1.0)
        pooled = self.norm(pooled)
        return self.class_head(pooled).squeeze(-1), self.reg_head(pooled)


class TemporalConvNet(nn.Module):
    """Small dilated TCN for overlap classification and deconvolution regression."""

    def __init__(self, n_samples: int) -> None:
        super().__init__()
        self.input = nn.Conv1d(1, 18, kernel_size=3, padding=1)
        self.blocks = nn.ModuleList(
            [
                nn.Sequential(
                    nn.Conv1d(18, 18, kernel_size=3, padding=dilation, dilation=dilation),
                    nn.GELU(),
                    nn.Conv1d(18, 18, kernel_size=1),
                )
                for dilation in (1, 2, 4)
            ]
        )
        self.norm = nn.LayerNorm(18)
        self.class_head = nn.Linear(18, 1)
        self.reg_head = nn.Linear(18, 4)
        self.uncertainty_head = nn.Linear(18, 2)
        self.n_samples = n_samples

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        h = self.input(x[:, None, :])
        for block in self.blocks:
            h = h + block(h)
        pooled = self.norm(h.mean(dim=-1))
        return self.class_head(pooled).squeeze(-1), self.reg_head(pooled), self.uncertainty_head(pooled)


def pileup_mask_channel(waveforms: np.ndarray) -> np.ndarray:
    """Return a deterministic mask for samples likely to contain second-pulse evidence.

    The mask is not derived from truth labels.  It starts at the observed primary
    peak plus one sample and covers the late rising edge and tail where unresolved
    second pulses alter curvature.
    """

    centered = waveforms - np.median(waveforms[:, :4], axis=1, keepdims=True)
    peaks = np.argmax(centered, axis=1)
    mask = np.zeros_like(centered, dtype=np.float32)
    n = centered.shape[1]
    for i, peak in enumerate(peaks):
        start = int(np.clip(peak + 1, 5, n - 1))
        mask[i, start:n] = 1.0
        mask[i, max(0, start - 2) : start] = 0.35
    return mask


def pileup_mask_transformer_prediction(events: pd.DataFrame, waveforms: np.ndarray, cfg: dict) -> pd.DataFrame:
    if torch is None:
        raise RuntimeError("torch is required for the S37b pile-up mask transformer benchmark")
    seed = int(cfg["random_seed"]) + 400
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    x_np = waveforms.astype(np.float32)
    x_np = x_np - np.median(x_np[:, :4], axis=1, keepdims=True)
    scale = np.maximum(np.percentile(np.abs(x_np), 95, axis=1, keepdims=True), 1.0)
    x_np = np.clip(x_np / scale, -4.0, 4.0).astype(np.float32)
    mask_np = pileup_mask_channel(waveforms).astype(np.float32)
    y_class = events["is_overlap"].to_numpy(dtype=np.float32)
    y_reg, max_amp = base.regression_targets(events, waveforms)
    y_reg = y_reg.astype(np.float32)
    train = events["split"].to_numpy() == "train"

    ds = TensorDataset(
        torch.from_numpy(x_np[train]),
        torch.from_numpy(mask_np[train]),
        torch.from_numpy(y_class[train]),
        torch.from_numpy(y_reg[train]),
    )
    loader = DataLoader(ds, batch_size=64, shuffle=True, generator=torch.Generator().manual_seed(seed))
    model = PileupMaskTransformer(waveforms.shape[1])
    opt = torch.optim.AdamW(model.parameters(), lr=1.4e-3, weight_decay=2e-3)
    bce = nn.BCEWithLogitsLoss()
    mse = nn.SmoothL1Loss()
    for _epoch in range(85):
        model.train()
        for xb, mb, yc, yr in loader:
            opt.zero_grad(set_to_none=True)
            logits, reg = model(xb, mb)
            loss = bce(logits, yc) + 1.9 * mse(reg, yr)
            loss.backward()
            opt.step()

    model.eval()
    probs: List[np.ndarray] = []
    regs: List[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(x_np), 512):
            xb = torch.from_numpy(x_np[start : start + 512])
            mb = torch.from_numpy(mask_np[start : start + 512])
            logits, reg = model(xb, mb)
            probs.append(torch.sigmoid(logits).cpu().numpy())
            regs.append(reg.cpu().numpy())
    score = np.concatenate(probs)
    pred = np.vstack(regs)
    return base.as_prediction(events, score, pred, max_amp, "pileup_mask_transformer_new")


def tcn_prediction(events: pd.DataFrame, waveforms: np.ndarray, cfg: dict) -> pd.DataFrame:
    if torch is None:
        raise RuntimeError("torch is required for the S37b temporal convolution benchmark")
    seed = int(cfg["random_seed"]) + 360
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    x_np = waveforms.astype(np.float32)
    x_np = x_np - np.median(x_np[:, :4], axis=1, keepdims=True)
    scale = np.maximum(np.percentile(np.abs(x_np), 95, axis=1, keepdims=True), 1.0)
    x_np = np.clip(x_np / scale, -4.0, 4.0).astype(np.float32)
    y_class = events["is_overlap"].to_numpy(dtype=np.float32)
    y_reg, max_amp = base.regression_targets(events, waveforms)
    y_reg = y_reg.astype(np.float32)
    train = events["split"].to_numpy() == "train"

    ds = TensorDataset(torch.from_numpy(x_np[train]), torch.from_numpy(y_class[train]), torch.from_numpy(y_reg[train]))
    loader = DataLoader(ds, batch_size=64, shuffle=True, generator=torch.Generator().manual_seed(seed))
    model = TemporalConvNet(waveforms.shape[1])
    opt = torch.optim.AdamW(model.parameters(), lr=1.6e-3, weight_decay=2e-3)
    bce = nn.BCEWithLogitsLoss()
    mse = nn.SmoothL1Loss()
    for _epoch in range(82):
        model.train()
        for xb, yc, yr in loader:
            opt.zero_grad(set_to_none=True)
            logits, reg, unc = model(xb)
            residual = torch.abs(reg[:, :2] - yr[:, :2]).detach()
            loss = bce(logits, yc) + 1.8 * mse(reg, yr) + 0.12 * mse(torch.nn.functional.softplus(unc), residual)
            loss.backward()
            opt.step()

    model.eval()
    probs: List[np.ndarray] = []
    regs: List[np.ndarray] = []
    uncs: List[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(x_np), 512):
            xb = torch.from_numpy(x_np[start : start + 512])
            logits, reg, unc = model(xb)
            probs.append(torch.sigmoid(logits).cpu().numpy())
            regs.append(reg.cpu().numpy())
            uncs.append(torch.nn.functional.softplus(unc).cpu().numpy())
    score = np.concatenate(probs)
    pred = np.vstack(regs)
    out = base.as_prediction(events, score, pred, max_amp, "temporal_convolution_tcn")
    unc = np.vstack(uncs)
    out["t1_uncertainty_sample"] = unc[:, 0]
    out["t2_uncertainty_sample"] = unc[:, 1]
    return out


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    return float((np.percentile(values, 84) - np.percentile(values, 16)) / 2.0)


def endpoint_values(frame: pd.DataFrame) -> Dict[str, float]:
    positives = frame[frame["is_overlap"] == 1].copy()
    valid = positives[~positives["failed"].astype(bool)].copy()
    clean = frame[frame["is_overlap"] == 0].copy()
    if len(valid):
        t1_err = (valid["t1_sample"].to_numpy(float) - valid["true_t1_sample"].to_numpy(float)) * 10.0
        pred_delay = (valid["t2_sample"].to_numpy(float) - valid["t1_sample"].to_numpy(float)) * 10.0
        true_delay = valid["true_sep_sample"].to_numpy(float) * 10.0
        delay_err = pred_delay - true_delay
        true_e = valid[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
        pred_e = valid[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
        energy_err = (pred_e - true_e) / np.maximum(true_e, 1.0)
        t2_err = (valid["t2_sample"].to_numpy(float) - valid["true_t2_sample"].to_numpy(float)) * 10.0
        shape_proxy = np.sqrt((t1_err / 20.0) ** 2 + (t2_err / 20.0) ** 2 + (energy_err / 0.20) ** 2)
        saturated = valid[(valid["true_amp1_adc"] + valid["true_amp2_adc"]) > 11000.0]
        if len(saturated):
            sat_true_e = saturated[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
            sat_pred_e = saturated[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
            sat_err = (sat_pred_e - sat_true_e) / np.maximum(sat_true_e, 1.0)
        else:
            sat_err = np.asarray([])
        stave_bias = []
        for _stave, group in valid.groupby("stave"):
            true_g = group[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
            pred_g = group[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
            stave_bias.append(float(np.median((pred_g - true_g) / np.maximum(true_g, 1.0))))
    else:
        t1_err = delay_err = energy_err = shape_proxy = sat_err = np.asarray([])
        stave_bias = []

    clean_false = float((clean["score"].to_numpy(float) >= 0.5).mean()) if len(clean) else float("nan")
    return {
        "leading_edge_time_sigma68_ns": sigma68(t1_err),
        "secondary_pulse_delay_sigma68_ns": sigma68(delay_err),
        "shape_residual_proxy_median": float(np.median(shape_proxy)) if len(shape_proxy) else float("nan"),
        "saturation_interaction_energy_sigma68": sigma68(sat_err),
        "pedestal_shift_false_split_rate": clean_false,
        "energy_proxy_distortion_sigma68": sigma68(energy_err),
        "pid_confusion_stave_bias_span": float(np.max(stave_bias) - np.min(stave_bias)) if len(stave_bias) else float("nan"),
    }


def uncertainty_calibration(joined: pd.DataFrame) -> pd.DataFrame:
    held = joined[(joined["split"] == "heldout") & (joined["is_overlap"] == 1) & (~joined["failed"].astype(bool))].copy()
    rows = []
    for method, group in held.groupby("method"):
        t1_err = np.abs((group["t1_sample"].to_numpy(float) - group["true_t1_sample"].to_numpy(float)) * 10.0)
        t2_err = np.abs((group["t2_sample"].to_numpy(float) - group["true_t2_sample"].to_numpy(float)) * 10.0)
        if "t1_uncertainty_sample" in group.columns and group[["t1_uncertainty_sample", "t2_uncertainty_sample"]].notna().any().any():
            s1 = np.nan_to_num(group["t1_uncertainty_sample"].to_numpy(float), nan=np.nanmedian(t1_err) / 10.0) * 10.0
            s2 = np.nan_to_num(group["t2_uncertainty_sample"].to_numpy(float), nan=np.nanmedian(t2_err) / 10.0) * 10.0
        else:
            s1 = np.full(len(group), np.nanmedian(t1_err) if len(group) else np.nan)
            s2 = np.full(len(group), np.nanmedian(t2_err) if len(group) else np.nan)
        nominal68 = np.concatenate([t1_err <= s1, t2_err <= s2])
        nominal95 = np.concatenate([t1_err <= 2.0 * s1, t2_err <= 2.0 * s2])
        rows.append(
            {
                "method": method,
                "n_detected_overlap": int(len(group)),
                "median_predicted_timing_uncertainty_ns": float(np.nanmedian(np.concatenate([s1, s2]))),
                "empirical_coverage_1sigma": float(np.mean(nominal68)) if len(nominal68) else float("nan"),
                "empirical_coverage_2sigma": float(np.mean(nominal95)) if len(nominal95) else float("nan"),
                "mean_abs_timing_error_ns": float(np.mean(np.concatenate([t1_err, t2_err]))) if len(group) else float("nan"),
            }
        )
    return pd.DataFrame(rows).sort_values(["empirical_coverage_1sigma", "mean_abs_timing_error_ns"], ascending=[False, True])


def endpoint_bootstrap(joined: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    held = joined[joined["split"] == "heldout"].copy()
    rows = []
    for method, group in held.groupby("method"):
        row: Dict[str, object] = {"method": method, **endpoint_values(group)}
        runs = sorted(group["source_run"].unique())
        samples: Dict[str, List[float]] = {}
        for _ in range(n_boot):
            take = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["source_run"] == run] for run in take], ignore_index=True)
            vals = endpoint_values(boot)
            for key, value in vals.items():
                if np.isfinite(value):
                    samples.setdefault(key, []).append(float(value))
        for key, values in samples.items():
            row[f"{key}_ci_low"] = float(np.percentile(values, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(values, 97.5))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["leading_edge_time_sigma68_ns", "secondary_pulse_delay_sigma68_ns"])


def source_unit_bootstrap(joined: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    held = joined[joined["split"] == "heldout"].copy()
    held["source_spacing_bin"] = pd.cut(
        held["true_sep_sample"].fillna(-1.0), bins=[-2.0, 0.0, 1.5, 3.5, 6.5], include_lowest=True
    ).astype(str)
    held["source_ratio_bin"] = pd.cut(
        held["true_ratio"].fillna(0.0), bins=[-0.01, 0.01, 0.35, 0.625, 0.875, 1.05], include_lowest=True
    ).astype(str)
    held["injection_source_unit"] = (
        held["source_run"].astype(str)
        + ":"
        + held["stave"].astype(str)
        + ":"
        + held["is_overlap"].astype(str)
        + ":"
        + held["source_spacing_bin"]
        + ":"
        + held["source_ratio_bin"]
    )
    rows = []
    metric_names = ["detection_ap", "time_sigma68_ns", "pileup_miss_rate", "false_split_rate", "energy_fractional_sigma68"]
    for method, group in held.groupby("method"):
        group = group.reset_index(drop=True)
        units = np.asarray(sorted(group["injection_source_unit"].unique()), dtype=object)
        unit_indices = {
            unit: idx.to_numpy(dtype=int)
            for unit, idx in group.groupby("injection_source_unit", sort=False).groups.items()
        }
        samples: Dict[str, List[float]] = {name: [] for name in metric_names}
        for _ in range(n_boot):
            take = rng.choice(units, size=len(units), replace=True)
            boot = group.iloc[np.concatenate([unit_indices[unit] for unit in take])]
            vals = base.metric_values(boot)
            for name in metric_names:
                value = float(vals[name])
                if np.isfinite(value):
                    samples[name].append(value)
        row: Dict[str, object] = {
            "method": method,
            "bootstrap_unit": "source_run:stave:is_overlap:spacing_bin:ratio_bin",
            "n_source_units": int(len(units)),
            "bootstrap_replicates": int(n_boot),
        }
        for name, values in samples.items():
            row[name] = float(base.metric_values(group)[name])
            row[f"{name}_ci_low"] = float(np.percentile(values, 2.5)) if values else float("nan")
            row[f"{name}_ci_high"] = float(np.percentile(values, 97.5)) if values else float("nan")
        rows.append(row)
    return pd.DataFrame(rows).sort_values("time_sigma68_ns").reset_index(drop=True)


def candidate_set_audit(events: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "item": "training_current_surface",
            "value": "low_2nA",
            "n": int(events[(events["split"] == "train") & (events["source_run"].isin(LOW_CURRENT_RUNS))].event_id.nunique()),
            "notes": f"runs {LOW_CURRENT_RUNS}; labels are controlled overlays for supervised fitting",
        },
        {
            "item": "frozen_candidate_surface",
            "value": "high_20nA",
            "n": int(events[(events["split"] == "heldout") & (events["source_run"].isin(HIGH_CURRENT_RUNS))].event_id.nunique()),
            "notes": f"runs {HIGH_CURRENT_RUNS}; high-current candidate-like held-out evaluation",
        },
        {
            "item": "heldout_overlap_proxy_positive",
            "value": "controlled_overlap_on_high_current_residual",
            "n": int(
                events[
                    (events["split"] == "heldout")
                    & (events["source_run"].isin(HIGH_CURRENT_RUNS))
                    & (events["is_overlap"] == 1)
                ].event_id.nunique()
            ),
            "notes": "proxy positives preserve exact timing/energy truth while using high-current raw residual morphology",
        },
        {
            "item": "heldout_clean_proxy_negative",
            "value": "single_pulse_high_current_control",
            "n": int(
                events[
                    (events["split"] == "heldout")
                    & (events["source_run"].isin(HIGH_CURRENT_RUNS))
                    & (events["is_overlap"] == 0)
                ].event_id.nunique()
            ),
            "notes": "false-split denominator on high-current raw residual morphology",
        },
    ]
    for source in HANDSCAN_SOURCES:
        path = ROOT / source
        rows.append(
            {
                "item": "handscan_provenance_file",
                "value": source,
                "n": int(path.stat().st_size) if path.exists() else 0,
                "notes": "existing blinded/reviewer candidate ledger; used to freeze high-current surface, not as an event-level truth join",
            }
        )
    return pd.DataFrame(rows)


def winner_table(overall: pd.DataFrame, endpoints: pd.DataFrame) -> pd.DataFrame:
    merged = overall.merge(endpoints, on="method", how="left")
    merged["winner_score"] = (
        merged["leading_edge_time_sigma68_ns"] / 20.0
        + merged["secondary_pulse_delay_sigma68_ns"] / 25.0
        + merged["shape_residual_proxy_median"]
        + 3.0 * merged["energy_proxy_distortion_sigma68"]
        + 0.6 * merged["pileup_miss_rate"]
        + 0.6 * merged["false_split_rate"]
        + 2.0 * merged["pid_confusion_stave_bias_span"].fillna(0.0)
    )
    return merged.sort_values(["winner_score", "leading_edge_time_sigma68_ns", "time_sigma68_ns"]).reset_index(drop=True)


def md_table(df: pd.DataFrame, cols: List[str]) -> str:
    view = df[cols].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    text = view.astype(str)
    widths = {
        col: max(len(str(col)), int(text[col].map(len).max()) if len(text) else 0)
        for col in text.columns
    }

    def row(values: List[str]) -> str:
        return "| " + " | ".join(str(v).ljust(widths[col]) for v, col in zip(values, text.columns)) + " |"

    header = row([str(col) for col in text.columns])
    sep = "| " + " | ".join("-" * widths[col] for col in text.columns) + " |"
    body = [row([str(rec[col]) for col in text.columns]) for rec in text.to_dict("records")]
    return "\n".join([header, sep, *body])


def write_report(
    cfg: dict,
    match: pd.DataFrame,
    templates: pd.DataFrame,
    overall: pd.DataFrame,
    endpoints: pd.DataFrame,
    ranked: pd.DataFrame,
    by_run: pd.DataFrame,
    strata: pd.DataFrame,
    source_ci: pd.DataFrame,
    calibration: pd.DataFrame,
    candidate_audit: pd.DataFrame,
    winner: str,
    runtime: float,
) -> None:
    best = ranked.iloc[0]
    trad = ranked[ranked["method"] == "two_pulse_template_cfd_baseline"].iloc[0]
    methods = pd.DataFrame(
        [
            ["two_pulse_template_cfd_baseline", "traditional", "bounded two-pulse template deconvolution with CFD/optimal-filter initialization"],
            ["ridge", "linear ML", "ridge classifier plus multi-output ridge regression on waveform features"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted classifier/regressors"],
            ["mlp", "neural network", "tabular multilayer perceptron classifier/regressor pair"],
            ["1d_cnn", "neural network", "compact one-dimensional convolutional waveform model"],
            ["temporal_convolution_tcn", "neural sequence", "dilated residual temporal convolutional network with timing uncertainty head"],
            ["tiny_sequence_transformer", "neural sequence", "one-layer self-attention encoder over 18 samples"],
            ["pileup_mask_transformer_new", "new neural sequence", "self-attention model with deterministic late/overlap mask channel"],
            ["template_residual_boosted_stack_new", "new hybrid", "boosted residual correction stack using traditional deconvolver outputs"],
        ],
        columns=["method", "family", "description"],
    )
    text = f"""# S37b: residual-stack deconvolution on high-current pile-up candidates

## Abstract

Ticket `{TICKET}` asks whether the S37a/S36 residual-stack deconvolution remains
superior on a frozen real pile-up candidate surface rather than only on generic
synthetic-over-real doublets.  The worker was `{WORKER}` and the project was
`testbeam`.  The study first reproduced the selected B-stack pulse count directly
from raw ROOT.  It then trained on low-current raw-residual overlays and evaluated
only on high-current source runs previously used by blinded hand-scan candidate
studies.  A strong traditional two-pulse template/optimal-filter baseline is
compared against ridge, gradient-boosted trees, MLP, 1D-CNN, a sequence
transformer, a temporal convolutional network, a new pile-up-mask transformer,
and a hybrid residual stack.  The winner written to `result.json` is `{winner}`
with composite endpoint score
`{best['winner_score']:.4g}`.

## Raw ROOT reproduction

The input files are `{cfg['raw_root_dir']}/hrdb_run_*.root`.  For each file the
analysis opens `h101/HRDv`, reshapes the waveform branch to
`(event, channel, sample)`, and uses the project-standard B2/B4/B6/B8 channels.
For channel `c`, the pedestal is `b_c = median_t x_c(t), t in {{0,1,2,3}}`, and a
selected pulse satisfies

`max_t [x_c(t)-b_c] > 1000 ADC`.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

This gate is deliberately before model fitting so that the benchmark is anchored
to raw ROOT semantics rather than a derived cache.

## Frozen Candidate Surface

The repository contains blinded/reviewer high-current candidate ledgers, but no
event-level hand-scan table with constituent hit times and amplitudes that can be
joined to all raw HRD windows.  S37b therefore uses those ledgers to freeze the
evaluation surface to the same high-current run family and keeps exact
constituent truth by overlaying controlled second pulses on raw high-current
residuals.  This is a robustness test against real beam-current morphology and
label uncertainty, not a claim that the hand-scan labels provide exact timing
truth.

{md_table(candidate_audit, ['item', 'value', 'n', 'notes'])}

## Split, injections, and bootstrap

The train/held-out split is by source run.  Train runs are
`{cfg['benchmark_runs']['train']}` and held-out runs are
`{cfg['benchmark_runs']['heldout']}`.  Clean templates are estimated only from
train runs:

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

{md_table(templates, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

Controlled doublets are generated as

`w(t)=A_1 T_s(t-t_1)+r A_1 T_s(t-t_1-Delta)+epsilon_r(t)+p`,

where `epsilon_r(t)` is a run-local residual from real raw-ROOT pulses and `p` is
a pedestal excursion.  Negative controls use the same residual and amplitude
spectrum with no second pulse.  Confidence intervals are percentile 95% intervals
from `{int(cfg['ml']['bootstrap_samples'])}` held-out run-block resamples:

`CI_95(theta) = [q_0.025(theta_b), q_0.975(theta_b)]`, with runs sampled with
replacement.

## Methods

{md_table(methods, ['method', 'family', 'description'])}

The traditional method is not a strawman.  It fits one-pulse and two-pulse
template hypotheses and uses the fractional optimal-filter improvement

`I = (SSE_1 - SSE_2) / SSE_1`,

where

`SSE_k = sum_t [w(t)-b-sum_{{j=1}}^k A_j T_s(t-t_j)]^2`.

The mask transformer adds a second input channel `m(t)`: `m(t)=1` after the
observed primary peak plus one sample, `m(t)=0.35` for the two samples before
that boundary, and `m(t)=0` elsewhere.  It is label-free and encodes where late
curvature from unresolved second pulses can appear.

The TCN uses three residual dilated convolutions with dilations 1, 2, and 4.
Besides the overlap logit and four deconvolution coordinates, it predicts
per-constituent timing scales `s_1,s_2`.  The calibration table below compares
`|hat t-t| <= s` and `|hat t-t| <= 2s` with empirical held-out coverage.

## Primary held-out method metrics

{md_table(overall, ['method', 'detection_ap', 'detection_auc', 'time_bias_ns', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high', 'pileup_miss_rate', 'false_split_rate', 'energy_fractional_sigma68'])}

## Registered endpoint table

The endpoint table maps the ticket language to measured quantities.  Leading-edge
time uses the first constituent error.  Secondary-pulse delay uses
`10 ns * [(hat t_2-hat t_1)-Delta]`.  Shape residual is a dimensionless proxy that
combines first-time, second-time, and energy residuals.  Saturation interaction is
the energy width for injected total amplitude above 11000 ADC.  Pedestal shift is
the false split rate on clean controls.  PID confusion is a cross-stave energy
bias span, treating stave as the available PID-boundary proxy.

{md_table(endpoints, ['method', 'leading_edge_time_sigma68_ns', 'leading_edge_time_sigma68_ns_ci_low', 'leading_edge_time_sigma68_ns_ci_high', 'secondary_pulse_delay_sigma68_ns', 'secondary_pulse_delay_sigma68_ns_ci_low', 'secondary_pulse_delay_sigma68_ns_ci_high', 'shape_residual_proxy_median', 'saturation_interaction_energy_sigma68', 'pedestal_shift_false_split_rate', 'energy_proxy_distortion_sigma68', 'pid_confusion_stave_bias_span'])}

## Winner rule

The winner minimizes

`C_m = sigma_lead/20 + sigma_delay/25 + R_shape + 3 sigma_E + 0.6 r_miss + 0.6 r_false + 2 B_stave`,

where `B_stave` is the cross-stave median energy-bias span.  This score favors
timing and secondary-delay recovery but penalizes models that obtain narrow timing
only by rejecting overlaps, splitting clean pulses, distorting energy, or moving
stave/PID boundaries.

{md_table(ranked, ['method', 'winner_score', 'leading_edge_time_sigma68_ns', 'secondary_pulse_delay_sigma68_ns', 'shape_residual_proxy_median', 'energy_proxy_distortion_sigma68', 'pileup_miss_rate', 'false_split_rate', 'pid_confusion_stave_bias_span'])}

The traditional baseline has score `{trad['winner_score']:.4g}` and leading-edge
sigma68 `{trad['leading_edge_time_sigma68_ns']:.4g}` ns.  The selected winner
`{winner}` has score `{best['winner_score']:.4g}` and leading-edge sigma68
`{best['leading_edge_time_sigma68_ns']:.4g}` ns.

## Run-held-out stability

{md_table(by_run, ['method', 'heldout_run', 'time_bias_ns', 'time_sigma68_ns', 'late_tail_rate_abs_gt_15ns', 'pileup_miss_rate', 'false_split_rate', 'energy_fractional_sigma68'])}

## Injection-source bootstrap stress test

As a second uncertainty check, source units are
`source_run:stave:is_overlap:spacing_bin:ratio_bin`.  This is stricter than an
event bootstrap because it preserves run-local residual source, stave/PID proxy,
pile-up label, delay family, and amplitude-ratio family.

{md_table(source_ci, ['method', 'n_source_units', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high', 'detection_ap', 'detection_ap_ci_low', 'detection_ap_ci_high', 'energy_fractional_sigma68', 'energy_fractional_sigma68_ci_low', 'energy_fractional_sigma68_ci_high'])}

## Timing Uncertainty Calibration

{md_table(calibration, ['method', 'n_detected_overlap', 'median_predicted_timing_uncertainty_ns', 'empirical_coverage_1sigma', 'empirical_coverage_2sigma', 'mean_abs_timing_error_ns'])}

## Systematics and caveats

The benchmark uses controlled injections into raw-ROOT-derived high-current
candidate-surface residuals, so truth is exact for delay and amplitude but the
absolute real beam pile-up frequency is not measured.  The hand-scan ledgers are
used to define the candidate surface, not as constituent timing labels.  The
saturation endpoint is an amplitude-knee proxy, not electronics metadata.
Pedestal shift is represented by clean-control false splitting and run-local
residuals, not an independent pedestal trigger stream.  PID confusion is
therefore a stave-conditioned boundary proxy rather than a particle-ID truth
confusion matrix.  The 18-sample waveform limits sub-sample deconvolution below
roughly one digitizer tick; all models inherit that sampling floor.  Finally, the
run-block bootstrap has only the finite held-out run set, so its CIs quantify
run-transfer uncertainty rather than asymptotic event uncertainty.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.

## Proposed next experiment

S37c should perform a direct event-key join between reviewer hand-scan candidate
rows and raw HRD windows, then score deconvolution outputs against reviewer
labels with explicit disagreement intervals.  The expected information gain is a
separation between architecture robustness and hand-scan label uncertainty on
actual real beam pile-up candidates.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "claimed_ticket.txt").write_text(TICKET + "\n", encoding="utf-8")
    (OUT / "claimed_ticket_body.txt").write_text(
        "# S37b: validate residual-stack deconvolution on hand-scanned real pile-up candidates\n\n"
        "Question: does the S37a template-residual boosted stack remain superior when evaluated on "
        "hand-scanned real pile-up-like windows rather than synthetic-over-real doublets? Compare the "
        "S37a traditional template/CFD baseline, ridge, gradient-boosted trees, MLP, 1D-CNN, "
        "causal-window transformer, and residual stack on a frozen hand-scan or high-current candidate "
        "set, split by source run with bootstrap CIs for timing tails, false splits, energy bias, and "
        "stave/PID-proxy drift. Expected information gain: separates architecture performance on "
        "exact-truth injected closures from robustness to real beam pile-up morphology and hand-scan "
        "label uncertainty.\n",
        encoding="utf-8",
    )
    cfg = load_config()
    rng = np.random.default_rng(int(cfg["random_seed"]))

    match = p05a.reproduce_counts(cfg)
    match.to_csv(OUT / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    runs = cfg["benchmark_runs"]["train"] + cfg["benchmark_runs"]["heldout"]
    clean = p05a.read_clean_pulses(cfg, runs, rng)
    templates, template_summary = p05a.build_templates(clean[clean["run"].isin(cfg["benchmark_runs"]["train"])], cfg)
    template_summary.to_csv(OUT / "template_summary.csv", index=False)

    train_events, train_waves = p05a.generate_benchmark(clean, templates, cfg, "train", cfg["benchmark_runs"]["train"], rng)
    held_events, held_waves = p05a.generate_benchmark(clean, templates, cfg, "heldout", cfg["benchmark_runs"]["heldout"], rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waves = np.vstack([train_waves, held_waves])
    candidate_audit = candidate_set_audit(events)

    trad_raw = p05a.run_template_fits(events, waves, templates, cfg)
    preds = [base.template_prediction(trad_raw)]
    preds.extend(base.run_sklearn_methods(events, waves, int(cfg["random_seed"])))
    preds.append(base.cnn_prediction(events, waves, cfg))
    preds.append(tcn_prediction(events, waves, cfg))
    preds.append(seqbase.transformer_prediction(events, waves, cfg))
    preds.append(pileup_mask_transformer_prediction(events, waves, cfg))
    preds.append(base.add_residual_stack(events, waves, trad_raw, int(cfg["random_seed"])))

    all_pred = pd.concat(preds, ignore_index=True)
    base_cols = [
        "event_id",
        "split",
        "source_run",
        "stave",
        "is_overlap",
        "true_t1_sample",
        "true_t2_sample",
        "true_amp1_adc",
        "true_amp2_adc",
        "true_sep_sample",
        "true_ratio",
    ]
    joined = all_pred.merge(events[base_cols], on="event_id", how="left")
    joined.to_csv(OUT / "event_predictions.csv", index=False)

    overall = base.summarize(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    endpoints = endpoint_bootstrap(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    ranked = winner_table(overall, endpoints)
    by_run = base.by_run_summary(joined)
    strata = base.strata_summary(joined)
    source_ci = source_unit_bootstrap(joined, rng, int(cfg["source_bootstrap_samples"]))
    calibration = uncertainty_calibration(joined)

    overall.to_csv(OUT / "method_metrics.csv", index=False)
    endpoints.to_csv(OUT / "endpoint_metrics_ci.csv", index=False)
    ranked.to_csv(OUT / "winner_ranked_metrics.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)
    source_ci.to_csv(OUT / "injection_source_bootstrap_ci.csv", index=False)
    calibration.to_csv(OUT / "uncertainty_calibration.csv", index=False)
    candidate_audit.to_csv(OUT / "candidate_surface_audit.csv", index=False)

    input_rows = [
        {"path": str(path), "sha256": base.sha256_file(path), "size": path.stat().st_size}
        for path in sorted(RAW_ROOT_DIR.glob("hrdb_run_*.root"))
    ]
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

    winner = str(ranked.iloc[0]["method"])
    runtime = time.time() - started
    write_report(
        cfg,
        match,
        template_summary,
        overall,
        endpoints,
        ranked,
        by_run,
        strata,
        source_ci,
        calibration,
        candidate_audit,
        winner,
        runtime,
    )

    result = {
        "ticket_id": TICKET,
        "project": "testbeam",
        "worker": WORKER,
        "title": cfg["title"],
        "status": "complete",
        "claimed_once": True,
        "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
        "raw_root_reproduction": {
            "passed": bool(match["pass"].all()),
            "raw_root_glob": str(RAW_ROOT_DIR / "hrdb_run_*.root"),
            "expected_selected_pulses": int(match.iloc[0]["report_value"]),
            "reproduced_selected_pulses": int(match.iloc[0]["reproduced"]),
            "delta": int(match.iloc[0]["delta"]),
            "evidence_table": "reproduction_match_table.csv",
        },
        "evaluation_design": {
            "split": "train and held-out sets are disjoint by source run; held-out is frozen to high-current candidate-source runs",
            "train_runs": cfg["benchmark_runs"]["train"],
            "heldout_runs": cfg["benchmark_runs"]["heldout"],
            "candidate_surface": "high_20nA source runs used by prior blinded hand-scan candidate studies",
            "handscan_provenance_sources": HANDSCAN_SOURCES,
            "label_policy": "hand-scan ledgers define the candidate surface; exact timing/energy labels come from controlled overlays on raw high-current residuals",
            "run_block_bootstrap": "held-out source_run percentile 95% CI",
            "injection_source_bootstrap": "held-out source_run:stave:is_overlap:spacing_bin:ratio_bin percentile 95% CI",
            "bootstrap_replicates": int(cfg["ml"]["bootstrap_samples"]),
            "source_unit_bootstrap_replicates": int(cfg["source_bootstrap_samples"]),
            "negative_control": "clean single-pulse controls with matched source-run distribution",
            "winner_score": "registered S37b composite endpoint score",
        },
        "required_method_coverage": {
            "traditional": "two_pulse_template_cfd_baseline",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "temporal_convolution_tcn": "temporal_convolution_tcn",
            "sequence_transformer": "tiny_sequence_transformer",
            "transformer_with_pileup_masks": "pileup_mask_transformer_new",
            "new_architecture": "pileup_mask_transformer_new",
            "hybrid_new_architecture": "template_residual_boosted_stack_new",
        },
        "winner": {
            "name": winner,
            "criterion": "minimum registered S37b composite endpoint score with run-block bootstrap CIs",
            "winner_score": float(ranked.iloc[0]["winner_score"]),
            "leading_edge_time_sigma68_ns": float(ranked.iloc[0]["leading_edge_time_sigma68_ns"]),
            "leading_edge_time_sigma68_ci95": [
                float(ranked.iloc[0]["leading_edge_time_sigma68_ns_ci_low"]),
                float(ranked.iloc[0]["leading_edge_time_sigma68_ns_ci_high"]),
            ],
            "secondary_pulse_delay_sigma68_ns": float(ranked.iloc[0]["secondary_pulse_delay_sigma68_ns"]),
            "secondary_pulse_delay_sigma68_ci95": [
                float(ranked.iloc[0]["secondary_pulse_delay_sigma68_ns_ci_low"]),
                float(ranked.iloc[0]["secondary_pulse_delay_sigma68_ns_ci_high"]),
            ],
            "time_sigma68_ns": float(ranked.iloc[0]["time_sigma68_ns"]),
            "energy_proxy_distortion_sigma68": float(ranked.iloc[0]["energy_proxy_distortion_sigma68"]),
            "pileup_miss_rate": float(ranked.iloc[0]["pileup_miss_rate"]),
            "false_split_rate": float(ranked.iloc[0]["false_split_rate"]),
        },
        "artifacts": {
            "report": "REPORT.md",
            "manifest": "manifest.json",
            "claimed_ticket": "claimed_ticket.txt",
            "raw_reproduction": "reproduction_match_table.csv",
            "method_metrics": "method_metrics.csv",
            "endpoint_metrics_ci": "endpoint_metrics_ci.csv",
            "winner_ranked_metrics": "winner_ranked_metrics.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "injection_source_bootstrap_ci": "injection_source_bootstrap_ci.csv",
            "uncertainty_calibration": "uncertainty_calibration.csv",
            "candidate_surface_audit": "candidate_surface_audit.csv",
            "strata_metrics": "strata_metrics.csv",
            "event_predictions": "event_predictions.csv",
            "input_sha256": "input_sha256.csv",
        },
        "next_tickets": [
            {
                "title": "S37c: event-key hand-scan label join for real pile-up deconvolution",
                "body": (
                    "Question: can reviewer hand-scan candidate rows be joined by event key to raw HRD windows "
                    "well enough to score S37b deconvolution outputs against real pile-up labels with explicit "
                    "reviewer-disagreement intervals? Build the join, freeze train/held-out source runs, compare "
                    "traditional template/CFD, gradient-boosted trees, transformer, and residual stack, and report "
                    "timing-tail, false-split, accepted-secondary-fraction, energy-bias, and stave/PID-proxy drift "
                    "CIs. Expected information gain: separates architecture robustness from hand-scan label "
                    "uncertainty on actual real beam pile-up candidates."
                ),
            }
        ],
        "novel_tickets_appended": ["S37c: event-key hand-scan label join for real pile-up deconvolution"],
        "caveats": [
            "Truth comes from controlled injections into raw-ROOT-derived high-current candidate-surface residuals.",
            "Hand-scan ledgers define the candidate-source surface but are not an event-level timing truth join.",
            "Saturation is represented by an amplitude-ceiling proxy rather than electronics saturation flags.",
            "PID confusion is a stave-conditioned energy-bias proxy, not particle truth.",
        ],
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "ticket_id": TICKET,
        "git_commit": base.git_commit(),
        "command": f"{sys.executable} scripts/{Path(__file__).name}",
        "runtime_seconds": runtime,
        "python": sys.version,
        "platform": platform.platform(),
        "outputs_sha256": {
            p.name: base.sha256_file(p)
            for p in sorted(OUT.iterdir())
            if p.is_file() and p.name != "manifest.json"
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
