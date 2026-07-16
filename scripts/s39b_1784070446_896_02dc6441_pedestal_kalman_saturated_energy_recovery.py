#!/usr/bin/env python3
"""S39b pedestal-state Kalman correction versus ML memory models.

This ticket-specific runner reuses the validated raw-ROOT reproduction,
controlled-injection, and model bakeoff machinery from the earlier S26b runner,
but writes a new artifact directory for the claimed S39b ticket and adds a
pedestal-state Kalman traditional baseline, memory-model diagnostics, and
feature-block ablations for pretrigger, tail, and saturation-mask inputs.
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
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.multioutput import MultiOutputRegressor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402
import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as base  # noqa: E402
import s26b_1783798536_2368_2ce12433_saturation_energy_recovery_architecture_bakeoff as prior  # noqa: E402


TICKET = "1784070446.896.02dc6441"
SLUG = "s39b_pedestal_kalman_saturated_energy_recovery"
WORKER = "testbeam-laptop-4"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/extracted/root/root")
CLAIMED_TICKET_BODY = (
    "Academic-grade study: model pretrigger pedestal memory and baseline drift as latent state "
    "variables, then measure their impact on clipped/saturated pulse energy recovery and timing. "
    "Compare a traditional Kalman/state-space pedestal tracker with analytic clipped-template charge "
    "reconstruction against ridge, gradient-boosted trees, MLP, 1D-CNN encoder, and transformer "
    "encoder using causal pretrigger plus pulse samples. Report run-block bootstrap CIs for energy "
    "response, saturation knee location, timing bias, pedestal high-minus-low contrast, pile-up "
    "leakage, and PID-conditioned residuals; include ablations removing pretrigger, tail, and "
    "saturation-mask inputs."
)


def markdown_table(df: pd.DataFrame, cols: list[str]) -> str:
    view = df.loc[:, cols].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    rows = [[str(x) for x in view.columns]]
    rows += [[str(x) for x in row] for row in view.to_numpy()]
    widths = [max(len(row[i]) for row in rows) for i in range(len(cols))]

    def fmt(row: list[str]) -> str:
        return "| " + " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) + " |"

    return "\n".join([fmt(rows[0]), fmt(["-" * w for w in widths]), *[fmt(row) for row in rows[1:]]])


prior.md_table = markdown_table


def load_config() -> dict:
    cfg = prior.load_config()
    cfg.update(
        {
            "ticket_id": TICKET,
            "title": "Pedestal-state Kalman correction versus ML baseline memory models for saturated energy recovery",
            "worker": WORKER,
            "output_dir": str(OUT),
            "random_seed": 2026071604,
        }
    )
    cfg["raw_root_dir"] = str(RAW_ROOT_DIR)
    return cfg


def masked_token_transformer_prediction(events: pd.DataFrame, waveforms: np.ndarray, cfg: dict) -> pd.DataFrame:
    """Supervised waveform transformer trained with random sample masking.

    This keeps the same targets as the rest of the method panel but forces the
    attention head to learn from censored/missing waveform tokens during
    training, matching the ticket's masked-token architecture request without
    introducing a different data split or external pretraining source.
    """

    if prior.torch is None:
        raise RuntimeError("torch is required for the masked-token transformer benchmark")
    seed = int(cfg["random_seed"]) + 260
    prior.torch.manual_seed(seed)
    prior.torch.set_num_threads(1)
    x_np = waveforms.astype(np.float32)
    x_np = x_np - np.median(x_np[:, :4], axis=1, keepdims=True)
    scale = np.maximum(np.percentile(np.abs(x_np), 95, axis=1, keepdims=True), 1.0)
    x_np = np.clip(x_np / scale, -4.0, 4.0).astype(np.float32)
    y_class = events["is_overlap"].to_numpy(dtype=np.float32)
    y_reg, max_amp = base.regression_targets(events, waveforms)
    y_reg = y_reg.astype(np.float32)
    train = events["split"].to_numpy() == "train"

    ds = prior.TensorDataset(
        prior.torch.from_numpy(x_np[train]),
        prior.torch.from_numpy(y_class[train]),
        prior.torch.from_numpy(y_reg[train]),
    )
    loader = prior.DataLoader(
        ds,
        batch_size=64,
        shuffle=True,
        generator=prior.torch.Generator().manual_seed(seed),
    )
    model = prior.TinySequenceTransformer(waveforms.shape[1])
    opt = prior.torch.optim.AdamW(model.parameters(), lr=1.5e-3, weight_decay=2e-3)
    bce = prior.nn.BCEWithLogitsLoss()
    mse = prior.nn.SmoothL1Loss()
    for _epoch in range(80):
        model.train()
        for xb, yc, yr in loader:
            token_mask = prior.torch.rand_like(xb) < 0.18
            xb_masked = xb.masked_fill(token_mask, 0.0)
            opt.zero_grad(set_to_none=True)
            logits, reg = model(xb_masked)
            loss = bce(logits, yc) + 1.8 * mse(reg, yr)
            loss.backward()
            opt.step()

    model.eval()
    probs = []
    regs = []
    with prior.torch.no_grad():
        for start in range(0, len(x_np), 512):
            xb = prior.torch.from_numpy(x_np[start : start + 512])
            logits, reg = model(xb)
            probs.append(prior.torch.sigmoid(logits).cpu().numpy())
            regs.append(reg.cpu().numpy())
    score = np.concatenate(probs)
    pred = np.vstack(regs)
    return base.as_prediction(events, score, pred, max_amp, "masked_token_waveform_transformer")


def kalman_state_features(waveforms: np.ndarray) -> pd.DataFrame:
    """Estimate causal pedestal memory features from the pretrigger samples.

    The model is a scalar local-level tracker with process noise q and
    measurement noise r.  It is intentionally simple and auditable because the
    traditional comparator should remain a transparent state-space correction,
    not a learned black-box model.
    """

    rows = []
    for wave in waveforms.astype(float):
        level = float(wave[0])
        var = 25.0
        q = 4.0
        r = max(float(np.var(wave[:4])), 1.0)
        innovations = []
        for sample in wave[:4]:
            pred = level
            var = var + q
            gain = var / (var + r)
            innovation = float(sample - pred)
            level = pred + gain * innovation
            var = (1.0 - gain) * var
            innovations.append(innovation)
        slope = float((wave[3] - wave[0]) / 3.0)
        pre_median = float(np.median(wave[:4]))
        pulse = wave - level
        peak = float(np.max(pulse))
        tail_area = float(np.sum(np.maximum(pulse[12:], 0.0)))
        saturation_mask = float(peak > 11000.0 or np.count_nonzero(pulse > 0.92 * max(peak, 1.0)) >= 3)
        rows.append(
            {
                "kalman_pedestal_adc": level,
                "pretrigger_median_adc": pre_median,
                "pretrigger_slope_adc_per_sample": slope,
                "kalman_innovation_rms_adc": float(np.sqrt(np.mean(np.square(innovations)))),
                "tail_area_adc": tail_area,
                "peak_adc": peak,
                "saturation_mask": saturation_mask,
            }
        )
    return pd.DataFrame(rows)


def kalman_clipped_template_prediction(trad: pd.DataFrame, waveforms: np.ndarray) -> pd.DataFrame:
    """Traditional Kalman/state-space pedestal plus clipped-template correction."""

    pred = base.template_prediction(trad).copy()
    pred["method"] = "kalman_clipped_template_traditional"
    state = kalman_state_features(waveforms)
    pedestal_memory = state["kalman_pedestal_adc"].to_numpy(float) - state["pretrigger_median_adc"].to_numpy(float)
    drift = state["pretrigger_slope_adc_per_sample"].to_numpy(float)
    tail = state["tail_area_adc"].to_numpy(float)
    peak = np.maximum(state["peak_adc"].to_numpy(float), 1.0)
    saturated = state["saturation_mask"].to_numpy(bool)

    total = pred["amp1_adc"].fillna(0.0).to_numpy(float) + pred["amp2_adc"].fillna(0.0).to_numpy(float)
    charge_correction = np.clip(0.18 * tail / peak + 0.0008 * np.maximum(peak - 11000.0, 0.0), 0.0, 0.18)
    pedestal_correction = np.clip(1.0 - 0.00005 * pedestal_memory + 0.00008 * drift, 0.92, 1.08)
    total_corrected = total * pedestal_correction * np.where(saturated, 1.0 + charge_correction, 1.0)
    scale = np.divide(total_corrected, np.maximum(total, 1.0))

    pred["amp1_adc"] = pred["amp1_adc"].fillna(0.0).to_numpy(float) * scale
    pred["amp2_adc"] = pred["amp2_adc"].fillna(0.0).to_numpy(float) * scale
    pred["score"] = np.clip(pred["score"].to_numpy(float) + 0.10 * saturated - 0.02 * np.abs(drift) / 20.0, 0.0, 1.0)
    pred["failed"] = pred["failed"].to_numpy(bool) | (pred["score"].to_numpy(float) < 0.5)
    return pred


def ablation_feature_matrix(waveforms: np.ndarray, state: pd.DataFrame, mode: str) -> np.ndarray:
    x = base.features(waveforms)
    aux = state[
        [
            "kalman_pedestal_adc",
            "pretrigger_median_adc",
            "pretrigger_slope_adc_per_sample",
            "kalman_innovation_rms_adc",
            "tail_area_adc",
            "peak_adc",
            "saturation_mask",
        ]
    ].to_numpy(float)
    if mode == "remove_pretrigger":
        aux[:, 0:4] = 0.0
        x[:, 0:4] = 0.0
    elif mode == "remove_tail":
        aux[:, 4] = 0.0
        x[:, 12:18] = 0.0
    elif mode == "remove_saturation_mask":
        aux[:, 6] = 0.0
    return np.hstack([x, aux])


def boosted_memory_prediction(events: pd.DataFrame, waveforms: np.ndarray, mode: str, seed: int) -> pd.DataFrame:
    state = kalman_state_features(waveforms)
    x = ablation_feature_matrix(waveforms, state, mode)
    y_class = events["is_overlap"].to_numpy(int)
    y_reg, max_amp = base.regression_targets(events, waveforms)
    train = events["split"].to_numpy() == "train"
    pos_train = train & (y_class == 1)
    clf = HistGradientBoostingClassifier(max_iter=80, learning_rate=0.06, l2_regularization=0.04, random_state=seed)
    reg = MultiOutputRegressor(
        HistGradientBoostingRegressor(max_iter=80, learning_rate=0.06, l2_regularization=0.04, random_state=seed + 1)
    )
    clf.fit(x[train], y_class[train])
    reg.fit(x[pos_train], y_reg[pos_train])
    pred = reg.predict(x)
    out = base.as_prediction(events, clf.predict_proba(x)[:, 1], pred, max_amp, f"ablation_{mode}")
    return out


def ablation_study(events: pd.DataFrame, waveforms: np.ndarray, rng: np.random.Generator, n_boot: int, seed: int) -> pd.DataFrame:
    preds = []
    for offset, mode in enumerate(["all_inputs", "remove_pretrigger", "remove_tail", "remove_saturation_mask"]):
        preds.append(boosted_memory_prediction(events, waveforms, mode, seed + 500 + offset))
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
    out = base.summarize(joined, rng, n_boot)
    out["ablation"] = out["method"].str.replace("ablation_", "", regex=False)
    baseline = out[out["ablation"] == "all_inputs"].iloc[0]
    out["delta_energy_sigma68_vs_all_inputs"] = out["energy_fractional_sigma68"] - float(baseline["energy_fractional_sigma68"])
    out["delta_time_sigma68_ns_vs_all_inputs"] = out["time_sigma68_ns"] - float(baseline["time_sigma68_ns"])
    return out.sort_values("ablation").reset_index(drop=True)


def source_unit_bootstrap(joined: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    """Bootstrap held-out metrics over run/stave/injection-source cells.

    The controlled benchmark does not preserve the integer index of the residual
    waveform sampled from the pool.  The finest auditable injection-source unit
    retained in the event table is therefore the run, stave, pulse-label, spacing
    bin, and ratio bin cell.  This is stricter than event bootstrap and
    complementary to the run-block intervals in method_metrics.csv.
    """

    held = joined[joined["split"] == "heldout"].copy()
    held["source_spacing_bin"] = pd.cut(
        held["true_sep_sample"].fillna(-1.0),
        bins=[-2.0, 0.0, 1.5, 3.5, 6.5],
        include_lowest=True,
    ).astype(str)
    held["source_ratio_bin"] = pd.cut(
        held["true_ratio"].fillna(0.0),
        bins=[-0.01, 0.01, 0.35, 0.625, 0.875, 1.05],
        include_lowest=True,
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

    rows: List[Dict[str, object]] = []
    metric_names = [
        "detection_ap",
        "time_sigma68_ns",
        "pileup_miss_rate",
        "false_split_rate",
        "energy_fractional_sigma68",
    ]
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
    return pd.DataFrame(rows).sort_values("energy_fractional_sigma68").reset_index(drop=True)


def ticket_diagnostics(joined: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    """Ticket-specific charge, saturation, and PID-proxy diagnostics.

    The controlled target has no external particle species label.  The retained
    proxy for PID migration is therefore the B-stave identity: a useful energy
    recovery method should not move the median energy residual differently across
    B2/B4/B6/B8.  The span of stave-wise median residuals is reported as a
    conservative migration/stability diagnostic rather than as a real PID claim.
    """

    held = joined[joined["split"] == "heldout"].copy()
    held["true_total_amp_adc"] = held["true_amp1_adc"] + held["true_amp2_adc"].fillna(0.0)
    held["pred_total_amp_adc"] = held["amp1_adc"] + held["amp2_adc"].fillna(0.0)
    held["true_saturated_proxy"] = held["true_total_amp_adc"] > 11000.0
    held["pred_saturated_proxy"] = held["pred_total_amp_adc"] > 11000.0

    def values(frame: pd.DataFrame) -> dict[str, float]:
        positives = frame[(frame["is_overlap"] == 1) & (~frame["failed"].astype(bool))].copy()
        if len(positives):
            err = (
                positives["pred_total_amp_adc"].to_numpy(float)
                - positives["true_total_amp_adc"].to_numpy(float)
            ) / np.maximum(positives["true_total_amp_adc"].to_numpy(float), 1.0)
            sig68 = float((np.percentile(err, 84) - np.percentile(err, 16)) / 2.0)
            bias = float(np.median(err))
            sat_true = positives["true_saturated_proxy"].to_numpy(bool)
            sat_pred = positives["pred_saturated_proxy"].to_numpy(bool)
            saturation_onset_accuracy = float(np.mean(sat_true == sat_pred))
            saturation_onset_calibration_abs = float(abs(np.mean(sat_pred) - np.mean(sat_true)))
            stave_bias = []
            for _stave, stave_group in positives.groupby("stave"):
                stave_err = (
                    stave_group["pred_total_amp_adc"].to_numpy(float)
                    - stave_group["true_total_amp_adc"].to_numpy(float)
                ) / np.maximum(stave_group["true_total_amp_adc"].to_numpy(float), 1.0)
                if len(stave_err):
                    stave_bias.append(float(np.median(stave_err)))
            pid_proxy_energy_bias_span = float(max(stave_bias) - min(stave_bias)) if stave_bias else float("nan")
        else:
            sig68 = bias = saturation_onset_accuracy = saturation_onset_calibration_abs = float("nan")
            pid_proxy_energy_bias_span = float("nan")

        positives_all = frame[frame["is_overlap"] == 1]
        negatives = frame[frame["is_overlap"] == 0]
        return {
            "charge_fractional_bias": bias,
            "charge_fractional_sigma68": sig68,
            "energy_proxy_bias": bias,
            "energy_proxy_sigma68": sig68,
            "pileup_merge_rate": float(positives_all["failed"].mean()) if len(positives_all) else float("nan"),
            "pileup_false_split_rate": float((negatives["score"] >= 0.5).mean()) if len(negatives) else float("nan"),
            "saturation_onset_accuracy": saturation_onset_accuracy,
            "saturation_onset_calibration_abs": saturation_onset_calibration_abs,
            "pid_proxy_energy_bias_span": pid_proxy_energy_bias_span,
        }

    rows: list[dict[str, object]] = []
    for method, group in held.groupby("method"):
        row: dict[str, object] = {"method": method, **values(group)}
        runs = np.asarray(sorted(group["source_run"].unique()))
        samples: dict[str, list[float]] = {}
        for _ in range(n_boot):
            take = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["source_run"] == run] for run in take], ignore_index=True)
            for key, value in values(boot).items():
                if np.isfinite(value):
                    samples.setdefault(key, []).append(float(value))
        for key, vals in samples.items():
            row[f"{key}_ci_low"] = float(np.percentile(vals, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(vals, 97.5))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["energy_proxy_sigma68", "pileup_merge_rate"]).reset_index(drop=True)


def s39b_systematics(joined: pd.DataFrame, events: pd.DataFrame, waveforms: np.ndarray, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    state = kalman_state_features(waveforms)
    event_state = pd.concat([events[["event_id"]].reset_index(drop=True), state], axis=1)
    held = joined.merge(event_state, on="event_id", how="left")
    held = held[held["split"] == "heldout"].copy()
    held["true_total_amp_adc"] = held["true_amp1_adc"] + held["true_amp2_adc"].fillna(0.0)
    held["pred_total_amp_adc"] = held["amp1_adc"].fillna(0.0) + held["amp2_adc"].fillna(0.0)
    held["energy_frac_error"] = (
        held["pred_total_amp_adc"].to_numpy(float) - held["true_total_amp_adc"].to_numpy(float)
    ) / np.maximum(held["true_total_amp_adc"].to_numpy(float), 1.0)
    held["timing_error_ns"] = 10.0 * (held["t1_sample"].fillna(0.0).to_numpy(float) - held["true_t1_sample"].to_numpy(float))
    held["pedestal_state"] = pd.qcut(
        held["kalman_pedestal_adc"].rank(method="first"),
        3,
        labels=["low", "mid", "high"],
    )
    held["saturation_truth"] = held["true_total_amp_adc"] > 11000.0

    def values(frame: pd.DataFrame) -> dict[str, float]:
        valid = frame[(frame["is_overlap"] == 1) & (~frame["failed"].astype(bool))].copy()
        if len(valid):
            e = valid["energy_frac_error"].to_numpy(float)
            t = valid["timing_error_ns"].to_numpy(float)
            energy_response = float(np.nanmedian(e))
            timing_bias = float(np.nanmedian(t))
            knee_truth = valid["saturation_truth"].to_numpy(bool)
            knee_pred = valid["pred_total_amp_adc"].to_numpy(float) > 11000.0
            saturation_knee_location_adc = float(np.nanmedian(valid.loc[knee_pred, "true_total_amp_adc"])) if np.any(knee_pred) else float("nan")
            saturation_knee_accuracy = float(np.mean(knee_truth == knee_pred))
            pid_residuals = [float(np.nanmedian(g["energy_frac_error"])) for _s, g in valid.groupby("stave") if len(g)]
            pid_conditioned_residual_span = float(max(pid_residuals) - min(pid_residuals)) if pid_residuals else float("nan")
        else:
            energy_response = timing_bias = saturation_knee_location_adc = saturation_knee_accuracy = float("nan")
            pid_conditioned_residual_span = float("nan")

        ped_bias = []
        for label in ["low", "high"]:
            g = frame[(frame["pedestal_state"].astype(str) == label) & (frame["is_overlap"] == 1) & (~frame["failed"].astype(bool))]
            ped_bias.append(float(np.nanmedian(g["energy_frac_error"])) if len(g) else float("nan"))
        pedestal_high_minus_low_contrast = float(ped_bias[1] - ped_bias[0]) if np.all(np.isfinite(ped_bias)) else float("nan")
        positives = frame[frame["is_overlap"] == 1]
        negatives = frame[frame["is_overlap"] == 0]
        return {
            "energy_response_median": energy_response,
            "timing_bias_ns": timing_bias,
            "saturation_knee_location_adc": saturation_knee_location_adc,
            "saturation_knee_accuracy": saturation_knee_accuracy,
            "pedestal_high_minus_low_contrast": pedestal_high_minus_low_contrast,
            "pileup_leakage_miss_rate": float(positives["failed"].mean()) if len(positives) else float("nan"),
            "pileup_leakage_false_split_rate": float((negatives["score"] >= 0.5).mean()) if len(negatives) else float("nan"),
            "pid_conditioned_residual_span": pid_conditioned_residual_span,
        }

    rows = []
    for method, group in held.groupby("method"):
        row: dict[str, object] = {"method": method, **values(group)}
        runs = np.asarray(sorted(group["source_run"].unique()))
        samples: dict[str, list[float]] = {}
        for _ in range(n_boot):
            take = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["source_run"] == run] for run in take], ignore_index=True)
            for key, value in values(boot).items():
                if np.isfinite(value):
                    samples.setdefault(key, []).append(float(value))
        for key, vals in samples.items():
            row[f"{key}_ci_low"] = float(np.percentile(vals, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(vals, 97.5))
        rows.append(row)
    return pd.DataFrame(rows).sort_values("energy_response_median").reset_index(drop=True)


def append_source_bootstrap_report(source_ci: pd.DataFrame) -> None:
    cols = [
        "method",
        "n_source_units",
        "energy_fractional_sigma68",
        "energy_fractional_sigma68_ci_low",
        "energy_fractional_sigma68_ci_high",
        "time_sigma68_ns",
        "time_sigma68_ns_ci_low",
        "time_sigma68_ns_ci_high",
        "detection_ap",
        "detection_ap_ci_low",
        "detection_ap_ci_high",
    ]
    section = f"""

## Injection-source bootstrap

The run-block intervals above answer whether the ranking transfers across held-out
runs.  As a complementary stress test, `injection_source_bootstrap_ci.csv`
resamples retained source cells defined by
`source_run:stave:is_overlap:spacing_bin:ratio_bin`.  This unit preserves the
run-local residual source, detector stave/PID proxy, pile-up label, separation
family, and amplitude-ratio family rather than treating individual synthetic
events as independent draws.

{prior.md_table(source_ci, cols)}
"""
    report = OUT / "REPORT.md"
    report.write_text(report.read_text(encoding="utf-8") + section, encoding="utf-8")


def append_ticket_diagnostics_report(diagnostics: pd.DataFrame) -> None:
    cols = [
        "method",
        "charge_fractional_sigma68",
        "charge_fractional_sigma68_ci_low",
        "charge_fractional_sigma68_ci_high",
        "energy_proxy_bias",
        "saturation_onset_accuracy",
        "saturation_onset_calibration_abs",
        "pid_proxy_energy_bias_span",
        "pileup_merge_rate",
        "pileup_false_split_rate",
    ]
    section = f"""

## S39b energy, saturation, and PID-proxy diagnostics

The ticket asks for energy response, saturation knee behavior, timing shift,
pile-up leakage, and PID-conditioned residuals.  The first endpoints are direct
controlled-injection measurements.  Saturation onset is defined by the
predeclared high-amplitude proxy, `A_1 + A_2 > 11000 ADC`, and scored by
predicted-total-amplitude thresholding.  Because no external particle-identity
truth label is present in this raw ROOT benchmark, the PID diagnostic is the
span of median energy residuals across B2/B4/B6/B8; it is a support-stability
check, not a p/d classification claim.  Intervals are held-out run-block
percentile 95% CIs where available.

{prior.md_table(diagnostics, cols)}
"""
    report = OUT / "REPORT.md"
    report.write_text(report.read_text(encoding="utf-8") + section, encoding="utf-8")


def append_s39b_report_sections(systematics: pd.DataFrame, ablations: pd.DataFrame) -> None:
    sys_cols = [
        "method",
        "energy_response_median",
        "energy_response_median_ci_low",
        "energy_response_median_ci_high",
        "timing_bias_ns",
        "timing_bias_ns_ci_low",
        "timing_bias_ns_ci_high",
        "saturation_knee_location_adc",
        "pedestal_high_minus_low_contrast",
        "pileup_leakage_miss_rate",
        "pileup_leakage_false_split_rate",
        "pid_conditioned_residual_span",
    ]
    abl_cols = [
        "ablation",
        "energy_fractional_sigma68",
        "energy_fractional_sigma68_ci_low",
        "energy_fractional_sigma68_ci_high",
        "delta_energy_sigma68_vs_all_inputs",
        "time_sigma68_ns",
        "time_sigma68_ns_ci_low",
        "time_sigma68_ns_ci_high",
        "delta_time_sigma68_ns_vs_all_inputs",
        "pileup_miss_rate",
        "false_split_rate",
    ]
    section = f"""

## S39b pedestal-memory and saturation systematics

The Kalman/state-space endpoint uses only causal pretrigger information to
estimate the latent pedestal level and drift.  The table reports the requested
run-block bootstrap quantities: energy response, saturation-knee location,
timing bias, pedestal high-minus-low contrast, pile-up leakage, and
PID-conditioned residual span.

{prior.md_table(systematics, sys_cols)}

## Input-block ablations

The ablation rows refit the same boosted memory learner under the same run split.
`all_inputs` includes waveform samples plus causal Kalman pretrigger state,
tail-area, and saturation-mask features.  The other rows remove one block before
training and evaluation, so the deltas are measured on held-out runs rather than
post-hoc feature importances.

{prior.md_table(ablations, abl_cols)}
"""
    report = OUT / "REPORT.md"
    report.write_text(report.read_text(encoding="utf-8") + section, encoding="utf-8")


def normalize_ticket_report() -> None:
    report = OUT / "REPORT.md"
    text = report.read_text(encoding="utf-8")
    text = text.replace(
        "# S26b: saturation energy recovery architecture bakeoff",
        "# S39b: pedestal-state Kalman correction vs ML baseline memory models",
        1,
    )
    text = text.replace("`tiny_sequence_transformer`", "`masked_token_waveform_transformer`")
    text = text.replace(
        "a one-layer self-attention encoder over the 18-sample\nwaveform",
        "a one-layer self-attention encoder over the 18-sample\n"
        "waveform trained with random sample-token masking",
    )
    text = text.replace(
        """The traditional method is `two_pulse_template_cfd_baseline`, a bounded
saturation-knee two-template fit.  For one or two constituents it minimizes

`SSE_k = sum_t [w(t) - b - sum_{j=1}^k A_j T_s(t-t_j)]^2`,

with positive amplitudes, bounded baseline, constrained separations, and a
template-derived CFD initialization.  Its classification score is the fractional
improvement `(SSE_1-SSE_2)/SSE_1`.""",
        """The S39b traditional comparator is `kalman_clipped_template_traditional`, a
causal scalar Kalman/local-level pretrigger pedestal tracker layered on the
bounded clipped-template two-pulse fit.  From the four pretrigger samples it
estimates a latent pedestal level `z_t` and drift proxy, then applies an
analytic clipped-charge correction when the pulse peak and plateau mask indicate
the amplitude-ceiling regime.  The transparent reference fit
`two_pulse_template_cfd_baseline` is retained in the table to separate the
state-space correction from the underlying template fit.  For one or two
constituents the template fit minimizes

`SSE_k = sum_t [w(t) - b - sum_{j=1}^k A_j T_s(t-t_j)]^2`,

with positive amplitudes, bounded baseline, constrained separations, and a
template-derived CFD initialization.  Its classification score is the fractional
improvement `(SSE_1-SSE_2)/SSE_1`.""",
    )
    ticket_context = f"""## Ticket context and pre-registration

The claimed local-queue item was `{TICKET}` with title `S39b pedestal-state
Kalman correction vs ML baseline memory models for saturated energy recovery`
and an explicit body asking whether pretrigger pedestal memory and baseline
drift should be modeled as latent states for clipped/saturated energy recovery
and timing.  The pre-registered target is: reproduce the raw selected-pulse
count from ROOT, then compare a Kalman/state-space pedestal tracker with
analytic clipped-template charge reconstruction against ridge, gradient-boosted
trees, MLP, 1D-CNN, and a masked-token transformer on identical run-heldout
controlled-injection data.  The primary ranking metric is the declared
composite score

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.05 r_miss,m + 0.05 r_false,m`.

This caveat is material: the result is an architecture benchmark under raw-ROOT
controlled truth.  Charge and energy are ADC-amplitude proxies; saturation is an
amplitude-ceiling proxy; PID migration is tested only through stave support
stability because no external particle species truth is available.  The
ticket-specific systematics section separately reports energy response,
saturation-knee location, timing bias, pedestal high-minus-low contrast,
pile-up leakage, PID-conditioned residuals, and feature-block ablations.

"""
    text = text.replace("## Abstract\n\n", ticket_context + "## Abstract\n\n", 1)
    text += """

## Falsification and post-hoc controls

The falsification condition was defined before the ticket-local run: if the raw
ROOT reproduction gate failed, the benchmark would stop and the mismatch would
be the finding.  If an ML/NN method won only by increasing pile-up misses or
false splits relative to the traditional fit, it would not be promoted because
the composite score explicitly penalizes both failure modes.  Multiple
comparisons are limited to the named model panel; no additional cut was selected
after observing the score table.

## Next-experiment policy

No novel ticket was appended from this worker.  The most useful next study would
require a concrete new truth handle, for example hardware saturation flags or
independent hand-scanned pile-up labels, rather than adding another generic
architecture bakeoff.
"""
    report.write_text(text, encoding="utf-8")


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

    trad_raw = p05a.run_template_fits(events, waves, templates, cfg)
    preds = [kalman_clipped_template_prediction(trad_raw, waves), base.template_prediction(trad_raw)]
    preds.extend(base.run_sklearn_methods(events, waves, int(cfg["random_seed"])))
    preds.append(base.cnn_prediction(events, waves, cfg))
    preds.append(masked_token_transformer_prediction(events, waves, cfg))
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
    ranked = prior.winner_table(overall)
    by_run = base.by_run_summary(joined)
    strata = base.strata_summary(joined)
    source_ci = source_unit_bootstrap(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    diagnostics = ticket_diagnostics(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    systematics = s39b_systematics(joined, events, waves, rng, int(cfg["ml"]["bootstrap_samples"]))
    ablations = ablation_study(events, waves, rng, int(cfg["ml"]["bootstrap_samples"]), int(cfg["random_seed"]))

    overall.to_csv(OUT / "method_metrics.csv", index=False)
    ranked.to_csv(OUT / "winner_ranked_metrics.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)
    source_ci.to_csv(OUT / "injection_source_bootstrap_ci.csv", index=False)
    diagnostics.to_csv(OUT / "ticket_diagnostics.csv", index=False)
    systematics.to_csv(OUT / "s39b_pedestal_memory_systematics.csv", index=False)
    ablations.to_csv(OUT / "s39b_input_ablation_metrics.csv", index=False)

    winner = str(ranked.iloc[0]["method"])
    runtime = time.time() - started
    prior.TICKET = TICKET
    prior.WORKER = WORKER
    prior.OUT = OUT
    prior.write_report(cfg, match, overall, ranked, by_run, strata, template_summary, winner, runtime)
    normalize_ticket_report()
    append_ticket_diagnostics_report(diagnostics)
    append_s39b_report_sections(systematics, ablations)
    append_source_bootstrap_report(source_ci)

    input_rows = [
        {"path": str(path), "sha256": base.sha256_file(path), "size": path.stat().st_size}
        for path in sorted(RAW_ROOT_DIR.glob("hrdb_run_*.root"))
    ]
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

    result = {
        "ticket_id": TICKET,
        "project": "testbeam",
        "worker": WORKER,
        "title": cfg["title"],
        "claimed_ticket_title": "S39b pedestal-state Kalman correction vs ML baseline memory models for saturated energy recovery",
        "claimed_ticket_body": CLAIMED_TICKET_BODY,
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
            "bootstrap_replicates": int(cfg["ml"]["bootstrap_samples"]),
            "negative_control": "clean single-pulse controls with matched source-run distribution",
            "saturation_onset_proxy": "true_amp1_adc + true_amp2_adc > 11000 ADC",
            "pedestal_state_proxy": "causal scalar Kalman local-level estimate from the four pretrigger samples",
            "pid_proxy_migration": "span of median energy residual across B2/B4/B6/B8 staves",
            "input_ablations": "boosted memory learner refit after removing pretrigger, tail, or saturation-mask feature blocks",
            "winner_score": "energy_fractional_sigma68 + 0.01*time_sigma68_ns + 0.05*pileup_miss_rate + 0.05*false_split_rate",
        },
        "required_method_coverage": {
            "traditional": "kalman_clipped_template_traditional",
            "traditional_reference": "two_pulse_template_cfd_baseline",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "masked_token_waveform_transformer": "masked_token_waveform_transformer",
            "new_architecture": "template_residual_boosted_stack_new",
        },
        "winner": {
            "name": winner,
            "criterion": "minimum held-out composite saturation-energy/timing score with run-block and injection-source bootstrap CIs reported",
            "winner_score": float(ranked.iloc[0]["winner_score"]),
            "energy_fractional_sigma68": float(ranked.iloc[0]["energy_fractional_sigma68"]),
            "energy_fractional_sigma68_run_block_ci95": [
                float(ranked.iloc[0]["energy_fractional_sigma68_ci_low"]),
                float(ranked.iloc[0]["energy_fractional_sigma68_ci_high"]),
            ],
            "energy_fractional_sigma68_injection_source_ci95": [
                float(source_ci[source_ci["method"] == winner].iloc[0]["energy_fractional_sigma68_ci_low"]),
                float(source_ci[source_ci["method"] == winner].iloc[0]["energy_fractional_sigma68_ci_high"]),
            ],
            "time_sigma68_ns": float(ranked.iloc[0]["time_sigma68_ns"]),
            "time_sigma68_run_block_ci95": [
                float(ranked.iloc[0]["time_sigma68_ns_ci_low"]),
                float(ranked.iloc[0]["time_sigma68_ns_ci_high"]),
            ],
            "time_sigma68_injection_source_ci95": [
                float(source_ci[source_ci["method"] == winner].iloc[0]["time_sigma68_ns_ci_low"]),
                float(source_ci[source_ci["method"] == winner].iloc[0]["time_sigma68_ns_ci_high"]),
            ],
            "pileup_miss_rate": float(ranked.iloc[0]["pileup_miss_rate"]),
            "false_split_rate": float(ranked.iloc[0]["false_split_rate"]),
            "ticket_diagnostics": {
                "charge_fractional_sigma68": float(
                    diagnostics[diagnostics["method"] == winner].iloc[0]["charge_fractional_sigma68"]
                ),
                "charge_fractional_sigma68_ci95": [
                    float(diagnostics[diagnostics["method"] == winner].iloc[0]["charge_fractional_sigma68_ci_low"]),
                    float(diagnostics[diagnostics["method"] == winner].iloc[0]["charge_fractional_sigma68_ci_high"]),
                ],
                "energy_proxy_bias": float(diagnostics[diagnostics["method"] == winner].iloc[0]["energy_proxy_bias"]),
                "saturation_onset_accuracy": float(
                    diagnostics[diagnostics["method"] == winner].iloc[0]["saturation_onset_accuracy"]
                ),
                "saturation_onset_calibration_abs": float(
                    diagnostics[diagnostics["method"] == winner].iloc[0]["saturation_onset_calibration_abs"]
                ),
                "pid_proxy_energy_bias_span": float(
                    diagnostics[diagnostics["method"] == winner].iloc[0]["pid_proxy_energy_bias_span"]
                ),
                "pileup_merge_rate": float(diagnostics[diagnostics["method"] == winner].iloc[0]["pileup_merge_rate"]),
                "pileup_false_split_rate": float(
                    diagnostics[diagnostics["method"] == winner].iloc[0]["pileup_false_split_rate"]
                ),
                "pedestal_high_minus_low_contrast": float(
                    systematics[systematics["method"] == winner].iloc[0]["pedestal_high_minus_low_contrast"]
                ),
                "saturation_knee_location_adc": float(
                    systematics[systematics["method"] == winner].iloc[0]["saturation_knee_location_adc"]
                ),
                "pid_conditioned_residual_span": float(
                    systematics[systematics["method"] == winner].iloc[0]["pid_conditioned_residual_span"]
                ),
            },
        },
        "artifacts": {
            "report": "REPORT.md",
            "manifest": "manifest.json",
            "claimed_ticket": "claimed_ticket.txt",
            "raw_reproduction": "reproduction_match_table.csv",
            "method_metrics": "method_metrics.csv",
            "winner_ranked_metrics": "winner_ranked_metrics.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "injection_source_bootstrap_ci": "injection_source_bootstrap_ci.csv",
            "ticket_diagnostics": "ticket_diagnostics.csv",
            "s39b_pedestal_memory_systematics": "s39b_pedestal_memory_systematics.csv",
            "s39b_input_ablation_metrics": "s39b_input_ablation_metrics.csv",
            "strata_metrics": "strata_metrics.csv",
            "event_predictions": "event_predictions.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "caveats": [
            "Truth comes from controlled injections into raw-ROOT-derived clean pulses.",
            "Saturation is represented by an amplitude-ceiling proxy rather than electronics saturation flags.",
            "Injection-source cells are retained provenance units, not exact residual waveform indices.",
            "The Kalman pedestal state is inferred only from the four causal pretrigger samples.",
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
