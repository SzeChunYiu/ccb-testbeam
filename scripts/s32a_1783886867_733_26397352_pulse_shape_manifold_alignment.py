#!/usr/bin/env python3
"""S32a pulse-shape manifold alignment transfer benchmark.

This runner reuses the audited S29a raw-ROOT extraction and compact model panel,
then adds ticket-local transfer diagnostics for timing, PID, and energy.  All
models are fit on calibration runs and scored on complete held-out runs.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import HuberRegressor, LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, mean_absolute_error, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s29a_1783809165_2703_494a356d_pedestal_shape_timing_frontier as base  # noqa: E402


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def fmt(value: object) -> str:
    try:
        x = float(value)
    except Exception:
        return str(value)
    return f"{x:.5g}" if np.isfinite(x) else "nan"


def ci_text(value: object) -> str:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return value
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return f"[{fmt(value[0])}, {fmt(value[1])}]"
    return str(value)


def md_table(frame: pd.DataFrame, columns: list[str]) -> str:
    view = frame.loc[:, columns].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(fmt)
        if col.endswith("_ci95"):
            view[col] = view[col].map(ci_text)
    return view.to_markdown(index=False)


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def ece_score(y: np.ndarray, prob: np.ndarray, bins: int = 10) -> float:
    y = np.asarray(y, dtype=int)
    prob = np.asarray(prob, dtype=float)
    keep = np.isfinite(prob)
    y = y[keep]
    prob = np.clip(prob[keep], 0.0, 1.0)
    if len(y) == 0:
        return float("nan")
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (prob >= lo) & (prob < hi if hi < 1.0 else prob <= hi)
        if mask.any():
            total += float(mask.mean()) * abs(float(prob[mask].mean()) - float(y[mask].mean()))
    return total


def percentile_ci(values: list[float]) -> list[float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return [float("nan"), float("nan")]
    return [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))]


def block_transfer_bootstrap(
    events: pd.DataFrame,
    mask: np.ndarray,
    timing_y: np.ndarray,
    timing_pred: np.ndarray,
    energy_y: np.ndarray,
    energy_pred: np.ndarray,
    pid_y: np.ndarray,
    pid_prob: np.ndarray,
    reps: int,
    seed: int,
) -> dict:
    rng = np.random.default_rng(seed)
    idx0 = np.flatnonzero(mask)
    blocks = [g.index.to_numpy(dtype=int) for _, g in pd.DataFrame({"run": events["run"]}).iloc[idx0].groupby("run")]
    vals = {k: [] for k in ["timing_res68", "energy_bias", "energy_res68", "pid_auc", "pid_ece"]}
    for _ in range(reps):
        idx = np.concatenate([blocks[i] for i in rng.integers(0, len(blocks), size=len(blocks))])
        vals["timing_res68"].append(base.res68(timing_y[idx], timing_pred[idx]))
        vals["energy_bias"].append(float(np.median(energy_pred[idx] - energy_y[idx])))
        vals["energy_res68"].append(base.res68(energy_y[idx], energy_pred[idx]))
        if len(np.unique(pid_y[idx])) == 2:
            vals["pid_auc"].append(float(roc_auc_score(pid_y[idx], pid_prob[idx])))
        vals["pid_ece"].append(ece_score(pid_y[idx], pid_prob[idx]))
    return {f"{key}_ci95": percentile_ci(value) for key, value in vals.items()}


def fit_all_predictions(config: dict, events: pd.DataFrame, waves: np.ndarray, x: np.ndarray, y: np.ndarray, train: np.ndarray) -> tuple[dict[str, np.ndarray], dict[str, str]]:
    idx = base.train_subset(train, int(config["ml_max_train_events"]), int(config["random_seed"]))
    y_cal = y[idx]
    preds: dict[str, np.ndarray] = {}
    torch_status: dict[str, str] = {}

    trad_x = x[:, [1, 3, 4, 5, 7, 8, 9]]
    trad = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, alpha=0.002, max_iter=400)).fit(trad_x[idx], y_cal)
    preds["traditional_cfd_timewalk_deltae_lookup"] = base.bounded_predict(trad, trad_x, y_cal)

    ridge = make_pipeline(StandardScaler(), Ridge(alpha=2.0)).fit(x[idx], y[idx])
    preds["ridge"] = ridge.predict(x)

    gbt = GradientBoostingRegressor(
        n_estimators=80,
        max_depth=3,
        learning_rate=0.04,
        subsample=0.75,
        random_state=int(config["random_seed"]) + 2,
    ).fit(x[idx], y[idx])
    preds["gradient_boosted_trees"] = gbt.predict(x)

    if base.torch is not None:
        for name, trainer in [
            ("mlp", lambda: (base.fit_torch_tab(x, y, train, config), None)),
            ("1d_cnn", lambda: (base.fit_torch_wave(base.SmallCNN, waves, x, y, train, config, 40), waves)),
            ("manifold_gated_residual_cnn_new", lambda: (base.fit_torch_wave(base.GatedResidualCNN, waves, x, y, train, config, 60), waves)),
            ("compact_waveform_transformer", lambda: (base.fit_torch_wave(base.WaveformTransformer, waves, x, y, train, config, 80), waves)),
        ]:
            try:
                (model, scaler), wave_arg = trainer()
                preds[name] = base.predict_torch(model, scaler, x, wave_arg)
                torch_status[name] = "trained"
            except Exception as exc:  # pragma: no cover - status is persisted for audit.
                preds[name] = np.full(len(y), np.nan)
                torch_status[name] = f"failed: {exc}"
    else:
        torch_status["torch"] = "unavailable"
    return preds, torch_status


def transfer_metrics(events: pd.DataFrame, y: np.ndarray, preds: dict[str, np.ndarray], train: np.ndarray, held: np.ndarray, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    pred_frames = []
    pid_y = events["pid_label"].to_numpy(dtype=int)
    energy_y = events["charge_loss"].to_numpy(dtype=float)
    for method, pred in preds.items():
        ok_train = train & np.isfinite(pred)
        ok_held = held & np.isfinite(pred)
        if ok_train.sum() < 100 or ok_held.sum() < 100:
            continue
        e_model = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, alpha=0.001, max_iter=300)).fit(pred[ok_train, None], energy_y[ok_train])
        energy_pred = np.asarray(e_model.predict(pred[:, None]), dtype=float)
        if len(np.unique(pid_y[ok_train])) == 2:
            p_model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=300, class_weight="balanced")).fit(pred[ok_train, None], pid_y[ok_train])
            pid_prob = np.asarray(p_model.predict_proba(pred[:, None])[:, 1], dtype=float)
        else:
            pid_prob = np.full(len(pred), np.nan)
        m = ok_held
        row = {
            "method": method,
            "n": int(m.sum()),
            "timing_res68": base.res68(y[m], pred[m]),
            "timing_bias": float(np.median(pred[m] - y[m])),
            "shape_mae": float(mean_absolute_error(y[m], pred[m])),
            "energy_bias": float(np.median(energy_pred[m] - energy_y[m])),
            "energy_res68": base.res68(energy_y[m], energy_pred[m]),
            "pid_auc": float(roc_auc_score(pid_y[m], pid_prob[m])) if len(np.unique(pid_y[m])) == 2 else float("nan"),
            "pid_average_precision": float(average_precision_score(pid_y[m], pid_prob[m])) if len(np.unique(pid_y[m])) == 2 else float("nan"),
            "pid_ece": ece_score(pid_y[m], pid_prob[m]),
        }
        row.update(block_transfer_bootstrap(events, m, y, pred, energy_y, energy_pred, pid_y, pid_prob, int(config["bootstrap_reps"]), int(config["random_seed"]) + len(method)))
        rows.append(row)
        pred_frames.append(
            pd.DataFrame(
                {
                    "event_id": events["event_id"],
                    "run": events["run"],
                    "group": events["group"],
                    "split": np.where(train, "train", "heldout"),
                    "method": method,
                    "timing_target": y,
                    "timing_prediction": pred,
                    "energy_target_charge_loss": energy_y,
                    "energy_prediction": energy_pred,
                    "pid_label": pid_y,
                    "pid_probability": pid_prob,
                    "multiplicity": events["multiplicity"],
                    "saturated_count": events["saturated_count"],
                    "recovery_tail": events["recovery_tail"],
                    "pedestal_iqr_adc": events["pedestal_iqr_adc"],
                }
            )
        )
    summary = pd.DataFrame(rows)
    summary["winner_score"] = (
        summary["timing_res68"].rank(method="min")
        + summary["energy_res68"].rank(method="min")
        + (1.0 - summary["pid_auc"]).rank(method="min")
        + summary["pid_ece"].rank(method="min")
    )
    summary = summary.sort_values(["winner_score", "timing_res68", "energy_res68", "pid_ece"]).reset_index(drop=True)
    return summary, pd.concat(pred_frames, ignore_index=True)


def stratum_metrics(events: pd.DataFrame, predictions: pd.DataFrame, config: dict) -> pd.DataFrame:
    held = predictions["split"].eq("heldout")
    train_events = events[~events["run"].isin(base.heldout_runs(config))]
    strata = {
        "all_heldout": np.ones(len(predictions), dtype=bool),
        "pileup_multiplicity_ge2": predictions["multiplicity"].to_numpy() >= 2,
        "hard_saturated": predictions["saturated_count"].to_numpy() > 0,
        "high_recovery_tail": predictions["recovery_tail"].to_numpy() >= float(train_events["recovery_tail"].quantile(0.75)),
        "high_pedestal_drift": predictions["pedestal_iqr_adc"].to_numpy() >= float(train_events["pedestal_iqr_adc"].quantile(0.75)),
    }
    rows = []
    for stratum, smask in strata.items():
        for method, group in predictions[held & smask].groupby("method"):
            if len(group) < 50:
                continue
            y = group["timing_target"].to_numpy()
            p = group["timing_prediction"].to_numpy()
            e = group["energy_target_charge_loss"].to_numpy()
            ep = group["energy_prediction"].to_numpy()
            pid = group["pid_label"].to_numpy(dtype=int)
            pp = group["pid_probability"].to_numpy()
            rows.append(
                {
                    "stratum": stratum,
                    "method": method,
                    "n": int(len(group)),
                    "timing_res68": base.res68(y, p),
                    "energy_res68": base.res68(e, ep),
                    "pid_auc": float(roc_auc_score(pid, pp)) if len(np.unique(pid)) == 2 else float("nan"),
                    "pid_ece": ece_score(pid, pp),
                }
            )
    return pd.DataFrame(rows).sort_values(["stratum", "timing_res68", "energy_res68"])


def write_report(out: Path, config: dict, result: dict, counts: pd.DataFrame, summary: pd.DataFrame, strata: pd.DataFrame) -> None:
    winner = result["winner"]["method"]
    win = summary.iloc[0]
    trad_name = "traditional_cfd_timewalk_deltae_lookup"
    trad = summary[summary["method"] == trad_name].iloc[0]
    report = [
        "# S32a: Pulse-Shape Manifold Alignment for Timing, PID, and Energy Transfer",
        "",
        "## Abstract",
        "",
        f"Ticket `{config['ticket_id']}` tests whether aligned 18-sample B-stave pulse-shape manifolds explain timing, PID, and energy transfer beyond charge-depth summaries when pile-up, saturation, and pedestal strata are held fixed. The selected winner in `result.json` is **{winner}**. Its held-out timing res68 is {fmt(win['timing_res68'])} with run-bootstrap 95% CI {ci_text(win['timing_res68_ci95'])}; energy-transfer res68 is {fmt(win['energy_res68'])} with CI {ci_text(win['energy_res68_ci95'])}; PID AUC is {fmt(win['pid_auc'])} with CI {ci_text(win['pid_auc_ci95'])}. The traditional CFD/timewalk plus DeltaE-E lookup comparator has timing res68 {fmt(trad['timing_res68'])}, energy res68 {fmt(trad['energy_res68'])}, and PID AUC {fmt(trad['pid_auc'])}.",
        "",
        "## Raw ROOT Reproduction",
        "",
        "The analysis reads raw B-stack ROOT files from `/home/billy/ccb-data/extracted/root/root`. Each `h101/HRDv` vector is reshaped to eight channels by 18 samples. For channel `c`, the pedestal is",
        "",
        "\\[ b_{ec}=\\operatorname{median}\\{x_{ec0},x_{ec1},x_{ec2},x_{ec3}\\}. \\]",
        "",
        "B2/B4/B6/B8 even channels are selected when `max_s(x_ecs-b_ec)>1000 ADC`. This direct raw-ROOT reproduction is performed before any model fit.",
        "",
        md_table(counts, ["run", "group", "events_total", "events_selected", "selected_pulses"]),
        "",
        f"Total reproduced selected pulses: **{result['raw_reproduction']['reproduced_selected_pulses']}**; registered expectation: **{result['raw_reproduction']['expected_selected_pulses']}**; delta: **{result['raw_reproduction']['delta']}**.",
        "",
        "## Estimands",
        "",
        "Let `w_ejs` be the baseline-corrected waveform for event `e`, B-stave `j`, and sample `s`; `Q_ej=sum_s max(w_ejs,0)`; and `Q'_ej` the independent odd-channel duplicate charge. The timing/manifold target is",
        "",
        "\\[ h_e = \\operatorname{clip}_{[-4,4]}\\left(1-\\frac{\\sum_j Q_{ej}}{\\max(\\sum_j Q'_{ej},1)}\\right)+0.18\\frac{\\sum_{j,s\\ge9}\\max(w_{ejs},0)}{\\max(\\sum_j Q_{ej},1)}+0.015(\\bar{s}_{peak,e}-5). \\]",
        "",
        "The first term is duplicate-readout charge closure, the second is late-tail/pile-up recovery, and the third is a sample-level timing displacement. The energy-transfer target is the charge-closure component `c_e=clip(1-sum_j Q_ej/max(sum_j Q'_ej,1),-4,4)`. PID transfer uses the duplicate-readout high-amplitude or multi-hit proxy already used by frontier studies; PID probabilities are calibrated from each method's training-run manifold score by a one-dimensional logistic calibrator, then scored on held-out runs.",
        "",
        "The main robust scales are",
        "",
        "\\[ R_{68}(a,b)=Q_{0.68}(|a-b|), \\quad \\operatorname{ECE}=\\sum_k \\frac{n_k}{n}|\\bar p_k-\\bar y_k|. \\]",
        "",
        "## Methods",
        "",
        "The traditional comparator is a pedestal-subtracted CFD/timewalk plus DeltaE-E charge-depth lookup proxy: a Huber-calibrated model on log charge, saturation count, ADC knee count, late recovery fraction, onset sharpness, and pedestal sidebands. It is deliberately bounded to the calibrated target range. The ML/NN panel consists of ridge regression, gradient-boosted trees, a tabular MLP, a 1D-CNN over the four aligned B-stave waveforms, a compact waveform transformer with attention across 18 sample tokens, and a new manifold-gated residual CNN. The new architecture is sensible here because manifold alignment can be locally morphological: convolutional channels are gated by pooled waveform context before the residual head.",
        "",
        "## Split and Confidence Intervals",
        "",
        "Runs `31--42` and `64` are calibration/training. Runs `44--63` and `65` are held out as complete runs. Confidence intervals resample held-out runs with replacement, preserving run-block correlations, current-family shifts, and event multiplicity structure.",
        "",
        "## Head-to-Head Transfer Table",
        "",
        md_table(summary, ["method", "n", "timing_res68", "timing_res68_ci95", "shape_mae", "energy_bias", "energy_bias_ci95", "energy_res68", "energy_res68_ci95", "pid_auc", "pid_auc_ci95", "pid_ece", "pid_ece_ci95", "winner_score"]),
        "",
        "Lower timing/energy res68 and ECE are better; higher PID AUC is better. `winner_score` is the rank sum of timing res68, energy res68, `1-PID AUC`, and PID ECE.",
        "",
        "## Strata and Systematics",
        "",
        md_table(strata, ["stratum", "method", "n", "timing_res68", "energy_res68", "pid_auc", "pid_ece"]),
        "",
        "Pile-up is proxied by selected B-stave multiplicity, saturation by ADC knee crossings, and pedestal drift by the pretrigger IQR sideband. These are held fixed in the sense that every method is scored in identical strata after the run-heldout split. The bootstrap covers observed run-to-run variation but not unobserved electronics modes. The PID label is a detector proxy rather than external particle truth. The energy target is duplicate-readout charge closure, not an absolute MeV calibration. Neural models are compact and subsampled for worker reproducibility; a neural win should therefore be interpreted as evidence for waveform-context transfer, not final deployment without a broader electronics systematic campaign.",
        "",
        "## Recommendation",
        "",
        f"`{winner}` is the S32a winner. Use it for pulse-shape manifold transfer studies only with run-block uncertainty propagation and explicit high-tail/high-pedestal sideband reporting. The traditional `{trad_name}` baseline remains the interpretable fallback when bounded extrapolation is more important than the multimetric rank gain.",
        "",
        "## Artifact Index",
        "",
    "`result.json`, `REPORT.md`, `transfer_summary.csv`, `strata_summary.csv`, `event_prediction_sample.csv`, `run_counts.csv`, `input_sha256.csv`, `manifest.json`, and `claimed_ticket.txt` are written in this report directory.",
    ]
    (out / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs/s32a_1783886867_733_26397352_pulse_shape_manifold_alignment.yaml")
    args = parser.parse_args()
    config = load_config(args.config)
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)

    events, waves, counts = base.extract_dataset(config)
    x, feature_names = base.feature_matrix(events, waves)
    y = events["target_hysteresis"].to_numpy(dtype=float)
    train = ~events["run"].isin(base.heldout_runs(config)).to_numpy()
    held = ~train
    preds, torch_status = fit_all_predictions(config, events, waves, x, y, train)
    summary, pred_table = transfer_metrics(events, y, preds, train, held, config)
    strata = stratum_metrics(events, pred_table, config)

    counts.to_csv(out / "run_counts.csv", index=False)
    summary.to_csv(out / "transfer_summary.csv", index=False)
    strata.to_csv(out / "strata_summary.csv", index=False)
    pred_table.head(20000).to_csv(out / "event_prediction_sample.csv", index=False)

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
        "split": {
            "train_runs": sorted(set(events.loc[train, "run"].astype(int))),
            "heldout_runs": sorted(set(events.loc[held, "run"].astype(int))),
            "split_type": "complete run held-out",
        },
        "bootstrap": {"unit": "held-out run block", "replicates": int(config["bootstrap_reps"]), "interval": "95% percentile"},
        "winner": summary.iloc[0].to_dict(),
        "all_metrics": summary.to_dict(orient="records"),
        "torch_status": torch_status,
        "feature_names": feature_names,
        "input_sha256": [{"path": str(base.raw_path(config, r)), "sha256": base.sha256_file(base.raw_path(config, r))} for r in base.runs(config)],
        "environment": {"git_commit": git_commit(), "python": platform.python_version(), "platform": platform.platform(), "torch_available": base.torch is not None},
        "claimed_ticket_text": config.get("claimed_ticket_text", config["title"]),
        "next_tickets": [],
    }
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (out / "claimed_ticket.txt").write_text(config["ticket_id"] + f"\n# {config.get('claimed_ticket_text', config['title'])}\n", encoding="utf-8")
    pd.DataFrame(result["input_sha256"]).to_csv(out / "input_sha256.csv", index=False)
    manifest = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "command": config["command"],
        "artifacts": ["REPORT.md", "result.json", "transfer_summary.csv", "strata_summary.csv", "event_prediction_sample.csv", "run_counts.csv", "input_sha256.csv", "claimed_ticket.txt"],
        "raw_reproduction_passed": repro["pass"],
        "winner": result["winner"]["method"],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_report(out, config, result, counts, summary, strata)
    print(json.dumps({"out": str(out), "reproduction": repro, "winner": result["winner"]["method"]}, indent=2))


if __name__ == "__main__":
    main()
