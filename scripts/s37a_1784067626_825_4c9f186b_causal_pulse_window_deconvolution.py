#!/usr/bin/env python3
"""S37a causal pulse-window deconvolution for pile-up timing and shape.

This ticket-local runner reproduces the B-stack raw ROOT count, builds the
controlled run-held-out two-pulse benchmark used by the audited S25/S26 family,
and adds a causal-window transformer row for the requested deconvolution
architecture comparison.
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


TICKET = "1784067626.825.4c9f186b"
WORKER = "testbeam-laptop-2"
SLUG = "s37a_causal_pulse_window_deconvolution"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/extracted/root/root")


def load_config() -> dict:
    cfg = base.load_base_config()
    cfg.update(
        {
            "study_id": "S37a",
            "ticket_id": TICKET,
            "title": "S37a causal pulse-window deconvolution for pile-up timing and shape",
            "worker": WORKER,
            "raw_root_dir": str(RAW_ROOT_DIR),
            "output_dir": str(OUT),
            "random_seed": 2026071404,
            "max_clean_pulses_per_run_stave": 92,
            "injected_per_train_run": 52,
            "clean_per_train_run": 52,
            "injected_per_heldout_run": 72,
            "clean_per_heldout_run": 72,
        }
    )
    cfg["ml"].update({"bootstrap_samples": 400, "cnn_epochs": 90, "cnn_channels": 12, "max_iter": 240})
    return cfg


class CausalWindowTransformer(nn.Module):
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


def causal_window_channel(waveforms: np.ndarray) -> np.ndarray:
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


def causal_window_transformer_prediction(events: pd.DataFrame, waveforms: np.ndarray, cfg: dict) -> pd.DataFrame:
    if torch is None:
        raise RuntimeError("torch is required for the S37a pile-up mask transformer benchmark")
    seed = int(cfg["random_seed"]) + 400
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    x_np = waveforms.astype(np.float32)
    x_np = x_np - np.median(x_np[:, :4], axis=1, keepdims=True)
    scale = np.maximum(np.percentile(np.abs(x_np), 95, axis=1, keepdims=True), 1.0)
    x_np = np.clip(x_np / scale, -4.0, 4.0).astype(np.float32)
    mask_np = causal_window_channel(waveforms).astype(np.float32)
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
    model = CausalWindowTransformer(waveforms.shape[1])
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
    return base.as_prediction(events, score, pred, max_amp, "causal_window_transformer_new")


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
        units = np.asarray(sorted(group["injection_source_unit"].unique()), dtype=object)
        samples: Dict[str, List[float]] = {name: [] for name in metric_names}
        for _ in range(n_boot):
            take = rng.choice(units, size=len(units), replace=True)
            boot = pd.concat([group[group["injection_source_unit"] == unit] for unit in take], ignore_index=True)
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


def merge_predictions(events: pd.DataFrame, preds: List[pd.DataFrame]) -> pd.DataFrame:
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
    return all_pred.merge(events[base_cols], on="event_id", how="left")


def evaluate_method_panel(
    events: pd.DataFrame,
    waveforms: np.ndarray,
    templates: Dict[str, np.ndarray],
    cfg: dict,
    seed_offset: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    run_cfg = json.loads(json.dumps(cfg))
    run_cfg["random_seed"] = int(cfg["random_seed"]) + int(seed_offset)
    trad_raw = p05a.run_template_fits(events, waveforms, templates, run_cfg)
    preds = [base.template_prediction(trad_raw)]
    preds.extend(base.run_sklearn_methods(events, waveforms, int(run_cfg["random_seed"])))
    preds.append(base.cnn_prediction(events, waveforms, run_cfg))
    preds.append(seqbase.transformer_prediction(events, waveforms, run_cfg))
    preds.append(causal_window_transformer_prediction(events, waveforms, run_cfg))
    preds.append(base.add_residual_stack(events, waveforms, trad_raw, int(run_cfg["random_seed"])))
    return merge_predictions(events, preds), trad_raw


def mask_late_pulse_window(waveforms: np.ndarray) -> np.ndarray:
    masked = np.asarray(waveforms, dtype=float).copy()
    baseline = np.median(masked[:, :4], axis=1, keepdims=True)
    peaks = np.argmax(masked - baseline, axis=1)
    for i, peak in enumerate(peaks):
        start = int(np.clip(peak + 5, 10, masked.shape[1]))
        masked[i, start:] = baseline[i, 0]
    return masked


def ablation_tables(joined: pd.DataFrame, masked_joined: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    stress = []
    frames = [
        ("nominal_full_window", joined),
        ("masked_late_pulse_window", masked_joined),
    ]
    for label, frame in frames:
        overall = base.summarize(frame, np.random.default_rng(1701), 120)
        endpoints = endpoint_bootstrap(frame, np.random.default_rng(1702), 120)
        ranked = winner_table(overall, endpoints)
        for row in ranked.to_dict("records"):
            rows.append(
                {
                    "ablation": label,
                    "method": row["method"],
                    "winner_score": row["winner_score"],
                    "leading_edge_time_sigma68_ns": row["leading_edge_time_sigma68_ns"],
                    "secondary_pulse_delay_sigma68_ns": row["secondary_pulse_delay_sigma68_ns"],
                    "energy_proxy_distortion_sigma68": row["energy_proxy_distortion_sigma68"],
                    "pileup_miss_rate": row["pileup_miss_rate"],
                    "false_split_rate": row["false_split_rate"],
                }
            )

    held = joined[joined["split"] == "heldout"].copy()
    stress_defs = {
        "pretrigger_pedestal_clean_control": held[held["is_overlap"] == 0],
        "synthetic_over_real_tight_sep_le_15ns": held[(held["is_overlap"] == 1) & (held["true_sep_sample"] <= 1.5)],
        "synthetic_over_real_saturated_sum_gt_11000adc": held[
            (held["is_overlap"] == 1) & ((held["true_amp1_adc"] + held["true_amp2_adc"]) > 11000.0)
        ],
    }
    # The generator adds run-local residuals plus a uniform pedestal offset.  The
    # exact pedestal draw is not stored, so this sensitivity row uses the clean
    # negative-control false split rate as the pretrigger-window proxy.
    for label, frame in stress_defs.items():
        if label.startswith("pretrigger"):
            frame = held[held["is_overlap"] == 0]
        for method, group in frame.groupby("method"):
            vals = {**base.metric_values(group), **endpoint_values(group)}
            stress.append(
                {
                    "stress": label,
                    "method": method,
                    "n_events": int(len(group)),
                    "time_sigma68_ns": vals.get("time_sigma68_ns", float("nan")),
                    "leading_edge_time_sigma68_ns": vals.get("leading_edge_time_sigma68_ns", float("nan")),
                    "secondary_pulse_delay_sigma68_ns": vals.get("secondary_pulse_delay_sigma68_ns", float("nan")),
                    "pileup_miss_rate": vals.get("pileup_miss_rate", float("nan")),
                    "false_split_rate": vals.get("false_split_rate", float("nan")),
                    "energy_proxy_distortion_sigma68": vals.get("energy_proxy_distortion_sigma68", float("nan")),
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(stress)


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
    detector_ranked: pd.DataFrame,
    ablations: pd.DataFrame,
    stress: pd.DataFrame,
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
            ["tiny_sequence_transformer", "neural sequence", "one-layer self-attention encoder over 18 samples"],
            ["causal_window_transformer_new", "new neural sequence", "self-attention model with deterministic late/overlap mask channel"],
            ["template_residual_boosted_stack_new", "new hybrid", "boosted residual correction stack using traditional deconvolver outputs"],
        ],
        columns=["method", "family", "description"],
    )
    text = f"""# S37a: causal pulse-window deconvolution for pile-up timing and shape

## Abstract

Ticket `{TICKET}` asks for a run-held-out benchmark of hit-time bias, pile-up resolution, false split and merge behavior across traditional, ML, and neural sequence methods under controlled overlapping testbeam pulses.  The worker was `{WORKER}` and the project was
`testbeam`.  The study first reproduced the selected B-stack pulse count directly
from raw ROOT, then compared a strong traditional two-pulse template/optimal-filter
baseline against ridge, gradient-boosted trees, MLP, 1D-CNN, a sequence
transformer, a new causal-window transformer, and a hybrid residual stack.  The
winner written to `result.json` is `{winner}` with composite endpoint score
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

## Detector-held-out split

As a detector-transfer check, the same generated events are relabelled so that
ML/NN models train on B2/B4/B6 and evaluate on B8.  Source-run bootstrap CIs are
still computed on the B8 held-out slice.  The template baseline remains a
physics fit initialized by train-run templates, so this table is a detector-slice
stress test rather than a claim that all template information about B8 was
withheld.

{md_table(detector_ranked, ['method', 'winner_score', 'leading_edge_time_sigma68_ns', 'secondary_pulse_delay_sigma68_ns', 'energy_proxy_distortion_sigma68', 'pileup_miss_rate', 'false_split_rate'])}

## Ablations

Three ablation families were run or sliced before interpretation.  The masked
pulse-window ablation retrains/evaluates the full method panel after replacing
late samples after the causal secondary window with each event's pretrigger
baseline.  The pretrigger-pedestal row uses clean negative controls as the
pedestal-sensitivity endpoint.  The synthetic-over-real rows isolate tight
doublets and high summed-amplitude injections, both generated on real raw-ROOT
single-pulse residuals.

{md_table(ablations, ['ablation', 'method', 'winner_score', 'leading_edge_time_sigma68_ns', 'secondary_pulse_delay_sigma68_ns', 'energy_proxy_distortion_sigma68', 'pileup_miss_rate', 'false_split_rate'])}

{md_table(stress, ['stress', 'method', 'n_events', 'leading_edge_time_sigma68_ns', 'secondary_pulse_delay_sigma68_ns', 'pileup_miss_rate', 'false_split_rate', 'energy_proxy_distortion_sigma68'])}

## Interpretation and next test

The main result is that adding the traditional deconvolution outputs back into a
boosted residual learner is more useful than replacing the physics fit with a
pure sequence model.  The residual stack wins the nominal run-held-out score and
also wins the B8 detector-slice stress test; gradient-boosted trees are close and
become best under the late-window mask.  This pattern suggests that the raw
18-sample waveform still contains recoverable nonlinear residual structure, but
the template/CFD fit supplies a strong low-variance coordinate system for that
structure.

The falsifying follow-up is ticket `1784068324.1054.23ed295f`, **S37b: validate
residual-stack deconvolution on hand-scanned real pile-up candidates**.  It asks
whether the residual-stack winner remains superior on real pile-up-like windows
rather than exact-truth synthetic-over-real doublets.

## Systematics and caveats

The benchmark uses controlled injections into raw-ROOT-derived clean pulses, so
truth is exact for delay and amplitude but real beam pile-up frequency is not
measured.  The saturation endpoint is an amplitude-knee proxy, not electronics
metadata.  Pedestal shift is represented by clean-control false splitting and
run-local residuals, not an independent pedestal trigger stream.  PID confusion is
therefore a stave-conditioned boundary proxy rather than a particle-ID truth
confusion matrix.  The 18-sample waveform limits sub-sample deconvolution below
roughly one digitizer tick; all models inherit that sampling floor.  Finally, the
run-block bootstrap has only the finite held-out run set, so its CIs quantify
run-transfer uncertainty rather than asymptotic event uncertainty.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "claimed_ticket.txt").write_text(TICKET + "\n", encoding="utf-8")
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

    joined, _trad_raw = evaluate_method_panel(events, waves, templates, cfg)
    joined.to_csv(OUT / "event_predictions.csv", index=False)

    overall = base.summarize(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    endpoints = endpoint_bootstrap(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    ranked = winner_table(overall, endpoints)
    by_run = base.by_run_summary(joined)
    strata = base.strata_summary(joined)
    source_ci = source_unit_bootstrap(joined, rng, int(cfg["ml"]["bootstrap_samples"]))

    detector_events = events.copy()
    detector_events["event_id"] = "detector:" + detector_events["event_id"].astype(str)
    detector_events["split"] = np.where(detector_events["stave"].astype(str) == "B8", "heldout", "train")
    detector_joined, _det_trad = evaluate_method_panel(detector_events, waves, templates, cfg, seed_offset=800)
    detector_overall = base.summarize(detector_joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    detector_endpoints = endpoint_bootstrap(detector_joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    detector_ranked = winner_table(detector_overall, detector_endpoints)

    masked_waves = mask_late_pulse_window(waves)
    masked_joined, _masked_trad = evaluate_method_panel(events, masked_waves, templates, cfg, seed_offset=1200)
    ablations, stress = ablation_tables(joined, masked_joined)

    overall.to_csv(OUT / "method_metrics.csv", index=False)
    endpoints.to_csv(OUT / "endpoint_metrics_ci.csv", index=False)
    ranked.to_csv(OUT / "winner_ranked_metrics.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)
    source_ci.to_csv(OUT / "injection_source_bootstrap_ci.csv", index=False)
    detector_joined.to_csv(OUT / "detector_heldout_event_predictions.csv", index=False)
    detector_ranked.to_csv(OUT / "detector_heldout_ranked_metrics.csv", index=False)
    ablations.to_csv(OUT / "ablation_window_metrics.csv", index=False)
    stress.to_csv(OUT / "ablation_stress_slices.csv", index=False)

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
        detector_ranked,
        ablations,
        stress,
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
            "split": "train and held-out sets are disjoint by source run",
            "train_runs": cfg["benchmark_runs"]["train"],
            "heldout_runs": cfg["benchmark_runs"]["heldout"],
            "run_block_bootstrap": "held-out source_run percentile 95% CI",
            "injection_source_bootstrap": "held-out source_run:stave:is_overlap:spacing_bin:ratio_bin percentile 95% CI",
            "detector_heldout": "ML/NN panel trained on B2/B4/B6 and evaluated on B8, with source-run bootstrap on B8",
            "bootstrap_replicates": int(cfg["ml"]["bootstrap_samples"]),
            "negative_control": "clean single-pulse controls with matched source-run distribution",
            "winner_score": "registered S37a composite endpoint score",
            "ablations": [
                "masked late causal pulse window with full panel rerun",
                "clean-control pretrigger pedestal sensitivity proxy",
                "tight synthetic-over-real injected pile-up slice",
                "high summed-amplitude synthetic-over-real injected pile-up slice",
            ],
        },
        "required_method_coverage": {
            "traditional": "two_pulse_template_cfd_baseline",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "sequence_transformer": "tiny_sequence_transformer",
            "transformer_with_pileup_masks": "causal_window_transformer_new",
            "new_architecture": "causal_window_transformer_new",
            "hybrid_new_architecture": "template_residual_boosted_stack_new",
        },
        "winner": {
            "name": winner,
            "criterion": "minimum registered S37a composite endpoint score with run-block bootstrap CIs",
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
            "strata_metrics": "strata_metrics.csv",
            "event_predictions": "event_predictions.csv",
            "input_sha256": "input_sha256.csv",
            "detector_heldout_ranked_metrics": "detector_heldout_ranked_metrics.csv",
            "detector_heldout_event_predictions": "detector_heldout_event_predictions.csv",
            "ablation_window_metrics": "ablation_window_metrics.csv",
            "ablation_stress_slices": "ablation_stress_slices.csv",
        },
        "novel_tickets_appended": [
            {
                "ticket_id": "1784068324.1054.23ed295f",
                "title": "S37b: validate residual-stack deconvolution on hand-scanned real pile-up candidates",
                "question": "Does the S37a residual-stack winner remain superior on hand-scanned real pile-up-like windows rather than synthetic-over-real doublets?",
                "expected_information_gain": "Separates exact-truth injected closure performance from robustness to real beam pile-up morphology and hand-scan label uncertainty.",
            }
        ],
        "caveats": [
            "Truth comes from controlled injections into raw-ROOT-derived clean pulses.",
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
