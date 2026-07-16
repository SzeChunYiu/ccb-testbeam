#!/usr/bin/env python3
"""S37c event-key hand-scan label join for real pile-up deconvolution."""

from __future__ import annotations

import ast
import hashlib
import json
import platform
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402
import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as base  # noqa: E402
import s26b_1783798536_2368_2ce12433_saturation_energy_recovery_architecture_bakeoff as seqbase  # noqa: E402


TICKET = "1784070153.1596.5f56213c"
TITLE = "S37c event-key hand-scan label join for real pile-up deconvolution"
WORKER = "testbeam-laptop-1"
SLUG = "s37c_event_key_handscan_label_join"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/extracted/root/root")
HANDSCAN_FILES = [
    ROOT / "reports/1781146783.955.745c6984__s11h_blinded_real_current_waveform_adjudication/blinded_gallery_adjudication.csv",
    ROOT / "reports/1781191650.1263.35bb131f__p05g_blinded_handscan_validation/blinded_candidate_ledger.csv",
    ROOT / "reports/1783605034.12126.04fe4a38__s01j_external_handscan_transfer/handscan_feature_table.csv",
]


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


def load_config() -> dict:
    cfg = base.load_base_config()
    cfg.update(
        {
            "study_id": "S37c",
            "ticket_id": TICKET,
            "title": TITLE,
            "worker": WORKER,
            "raw_root_dir": str(RAW_ROOT_DIR),
            "output_dir": str(OUT),
            "random_seed": 2026071601,
            "max_clean_pulses_per_run_stave": 100,
            "injected_per_train_run": 56,
            "clean_per_train_run": 56,
            "injected_per_heldout_run": 44,
            "clean_per_heldout_run": 44,
            "benchmark_runs": {
                "train": [46, 47, 50, 51, 52, 53, 54, 55],
                "heldout": [44, 45, 48, 49, 56, 57],
            },
        }
    )
    cfg["ml"].update({"bootstrap_samples": 500, "cnn_epochs": 85, "cnn_channels": 12, "max_iter": 260})
    return cfg


def norm_stave(value: object) -> str:
    text = str(value)
    if text in {"B2", "B4", "B6", "B8"}:
        return text
    if text.startswith("B"):
        return text
    return f"B{text}"


def load_handscan_labels() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    provenance = []
    for path in HANDSCAN_FILES:
        frame = pd.read_csv(path)
        source = path.parent.name
        provenance.append(
            {
                "source_file": str(path.relative_to(ROOT)),
                "rows": int(len(frame)),
                "columns": ",".join(frame.columns[:24]),
                "sha256": sha256_file(path),
            }
        )
        if "blinded_recoverable" in frame.columns:
            tmp = frame[["run", "eventno", "ref_stave", "blinded_recoverable", "adjudication_band", "pred_secondary_fraction", "pred_overlap_probability"]].copy()
            tmp = tmp.rename(columns={"ref_stave": "stave", "blinded_recoverable": "label"})
            tmp["reviewer_weight"] = tmp["adjudication_band"].map({"accept_clear": 1.0, "reject_clear": 1.0}).fillna(0.55)
            tmp["reviewer_disagreement"] = (tmp["reviewer_weight"] < 0.9).astype(int)
            tmp["source"] = source
            rows.append(tmp)
        elif "blind_consensus_recoverable" in frame.columns:
            tmp = frame[["run", "eventno", "ref_stave", "blind_consensus_recoverable", "blind_vote_count", "resid_late_max_frac", "one_sse_norm"]].copy()
            tmp = tmp.rename(columns={"ref_stave": "stave", "blind_consensus_recoverable": "label"})
            tmp["reviewer_weight"] = np.where(tmp["blind_vote_count"].isin([0, 3]), 1.0, 0.65)
            tmp["reviewer_disagreement"] = (tmp["reviewer_weight"] < 0.9).astype(int)
            tmp["source"] = source
            rows.append(tmp)
        elif "consensus_label" in frame.columns:
            tmp = frame[["run", "eventno", "stave", "consensus_target_any", "reviewers_agree", "review_secondary_sep", "review_late_fraction", "taxon"]].copy()
            tmp = tmp.rename(columns={"consensus_target_any": "label"})
            tmp["reviewer_weight"] = np.where(tmp["reviewers_agree"].astype(bool), 1.0, 0.6)
            tmp["reviewer_disagreement"] = (~tmp["reviewers_agree"].astype(bool)).astype(int)
            tmp["source"] = source
            rows.append(tmp)
    labels = pd.concat(rows, ignore_index=True)
    labels["run"] = labels["run"].astype(int)
    labels["eventno"] = labels["eventno"].astype(int)
    labels["stave"] = labels["stave"].map(norm_stave)
    labels["label"] = labels["label"].astype(float)
    labels["event_key"] = labels["run"].astype(str) + ":" + labels["eventno"].astype(str) + ":" + labels["stave"]
    agg = (
        labels.groupby(["run", "eventno", "stave", "event_key"], as_index=False)
        .agg(
            label_mean=("label", "mean"),
            label_votes=("label", "count"),
            label_min=("label", "min"),
            label_max=("label", "max"),
            reviewer_weight=("reviewer_weight", "mean"),
            reviewer_disagreement=("reviewer_disagreement", "max"),
            sources=("source", lambda x: ";".join(sorted(set(map(str, x))))),
            review_secondary_sep=("review_secondary_sep", "median") if "review_secondary_sep" in labels.columns else ("label", "mean"),
        )
    )
    agg["handscan_label"] = (agg["label_mean"] >= 0.5).astype(int)
    agg["label_interval_low"] = agg["label_min"].clip(0, 1)
    agg["label_interval_high"] = agg["label_max"].clip(0, 1)
    return agg, pd.DataFrame(provenance)


def read_joined_raw_windows(labels: pd.DataFrame, cfg: dict, max_per_run: int = 260) -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    staves = {name: int(ch) for name, ch in cfg["staves"].items()}
    nsamp = int(cfg["samples_per_channel"])
    baseline_idx = [int(i) for i in cfg["baseline_samples"]]
    labels = labels[labels["stave"].isin(staves)].copy()
    labels = labels.sort_values(["reviewer_weight", "label_votes"], ascending=False)
    labels = labels.groupby(["run", "eventno", "stave"], as_index=False).head(1)
    wanted: Dict[int, pd.DataFrame] = {}
    for run, group in labels.groupby("run"):
        wanted[int(run)] = group.head(max_per_run).copy()

    rows = []
    waves = []
    audit = []
    for run, group in wanted.items():
        path = p05a.raw_file(cfg, run)
        key_to_rows = defaultdict(list)
        for rec in group.to_dict("records"):
            key_to_rows[int(rec["eventno"])].append(rec)
        found = 0
        total = int(len(group))
        for batch in p05a.iter_raw(path, ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            mask = np.isin(eventno, list(key_to_rows.keys()))
            if not mask.any():
                continue
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            for idx in np.flatnonzero(mask):
                for rec in key_to_rows[int(eventno[idx])]:
                    stave = str(rec["stave"])
                    raw = events[idx, staves[stave], :]
                    baseline = float(np.median(raw[baseline_idx]))
                    wf = raw - baseline
                    amp = float(np.max(wf))
                    if amp <= 0:
                        continue
                    waves.append(wf.astype(float))
                    sep = rec.get("review_secondary_sep", np.nan)
                    rows.append(
                        {
                            "event_id": f"real:{run}:{int(eventno[idx])}:{stave}:{len(rows)}",
                            "split": "heldout",
                            "source_run": int(run),
                            "eventno": int(eventno[idx]),
                            "evt": int(evt[idx]),
                            "stave": stave,
                            "is_overlap": int(rec["handscan_label"]),
                            "handscan_label": int(rec["handscan_label"]),
                            "reviewer_weight": float(rec["reviewer_weight"]),
                            "reviewer_disagreement": int(rec["reviewer_disagreement"]),
                            "label_interval_low": float(rec["label_interval_low"]),
                            "label_interval_high": float(rec["label_interval_high"]),
                            "review_secondary_sep": float(sep) if np.isfinite(sep) else np.nan,
                            "raw_amp_adc": amp,
                            "raw_peak_sample": int(np.argmax(wf)),
                            "true_t1_sample": p05a.cfd_time_one(wf, 0.2),
                            "true_t2_sample": np.nan,
                            "true_amp1_adc": amp,
                            "true_amp2_adc": 0.0,
                            "true_sep_sample": float(sep) if np.isfinite(sep) else np.nan,
                            "true_ratio": 0.0,
                            "event_key": rec["event_key"],
                            "label_sources": rec["sources"],
                        }
                    )
                    found += 1
            if found >= total:
                break
        audit.append({"run": run, "requested_keys": total, "joined_raw_windows": found, "join_efficiency": found / max(total, 1)})
    if not rows:
        raise RuntimeError("no hand-scan labels joined to raw ROOT windows")
    return pd.DataFrame(rows), np.vstack(waves), pd.DataFrame(audit)


def template_prediction_from_trad(trad: pd.DataFrame) -> pd.DataFrame:
    out = base.template_prediction(trad)
    out["method"] = "traditional_template_cfd"
    return out


def delay_tail_rate(group: pd.DataFrame) -> float:
    accepted = group[group["score"].to_numpy(float) >= 0.5].copy()
    if accepted.empty:
        return float("nan")
    pred_delay = (accepted["t2_sample"].to_numpy(float) - accepted["t1_sample"].to_numpy(float)) * 10.0
    review = accepted["review_secondary_sep"].to_numpy(float) * 10.0
    ok = np.isfinite(review)
    if ok.any():
        return float((np.abs(pred_delay[ok] - review[ok]) > 15.0).mean())
    return float(((pred_delay < 5.0) | (pred_delay > 80.0)).mean())


def real_metric_values(frame: pd.DataFrame) -> dict:
    y = frame["handscan_label"].to_numpy(int)
    score = np.nan_to_num(frame["score"].to_numpy(float), nan=0.0)
    pred = score >= 0.5
    has_both = len(np.unique(y)) == 2
    pos = y == 1
    neg = y == 0
    energy_bias = (frame["amp1_adc"].fillna(0).to_numpy(float) + frame["amp2_adc"].fillna(0).to_numpy(float) - frame["raw_amp_adc"].to_numpy(float)) / np.maximum(frame["raw_amp_adc"].to_numpy(float), 1.0)
    by_stave = frame.assign(_pred=pred.astype(float)).groupby("stave")["_pred"].mean()
    return {
        "real_label_ap": float(average_precision_score(y, score)) if has_both else float("nan"),
        "real_label_auc": float(roc_auc_score(y, score)) if has_both else float("nan"),
        "pileup_miss_rate": float((~pred[pos]).mean()) if pos.any() else float("nan"),
        "false_split_rate": float(pred[neg].mean()) if neg.any() else float("nan"),
        "accepted_secondary_fraction": float(pred.mean()),
        "timing_tail_rate_abs_gt_15ns": delay_tail_rate(frame),
        "energy_bias_median": float(np.nanmedian(energy_bias)),
        "energy_bias_sigma68": float((np.nanpercentile(energy_bias, 84) - np.nanpercentile(energy_bias, 16)) / 2.0),
        "stave_pid_proxy_drift_span": float(by_stave.max() - by_stave.min()) if len(by_stave) else float("nan"),
        "reviewer_disagreement_rate": float(frame["reviewer_disagreement"].mean()),
    }


def real_bootstrap(joined: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    for method, group in joined.groupby("method"):
        row = {"method": method, **real_metric_values(group)}
        runs = sorted(group["source_run"].unique())
        samples: Dict[str, List[float]] = {}
        for _ in range(n_boot):
            take = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["source_run"] == run] for run in take], ignore_index=True)
            for key, value in real_metric_values(boot).items():
                if np.isfinite(value):
                    samples.setdefault(key, []).append(float(value))
        for key, values in samples.items():
            row[f"{key}_ci_low"] = float(np.percentile(values, 2.5)) if values else float("nan")
            row[f"{key}_ci_high"] = float(np.percentile(values, 97.5)) if values else float("nan")
        rows.append(row)
    out = pd.DataFrame(rows)
    out["winner_score"] = (
        (1.0 - out["real_label_ap"])
        + 0.7 * out["pileup_miss_rate"]
        + 0.7 * out["false_split_rate"]
        + 0.25 * out["accepted_secondary_fraction"].sub(out["handscan_positive_rate"] if "handscan_positive_rate" in out else 0).abs()
        + 0.25 * out["timing_tail_rate_abs_gt_15ns"].fillna(0.5)
        + 0.20 * out["energy_bias_median"].abs()
        + 0.30 * out["stave_pid_proxy_drift_span"].fillna(0.0)
    )
    return out.sort_values(["winner_score", "real_label_ap"], ascending=[True, False]).reset_index(drop=True)


def by_run_metrics(joined: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (method, run), group in joined.groupby(["method", "source_run"]):
        rows.append({"method": method, "heldout_run": int(run), **real_metric_values(group)})
    return pd.DataFrame(rows).sort_values(["method", "heldout_run"]).reset_index(drop=True)


def md_table(df: pd.DataFrame, cols: List[str], limit: int | None = None) -> str:
    view = df.loc[:, cols].copy()
    if limit is not None:
        view = view.head(limit)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    text = view.astype(str)
    widths = [max(len(str(c)), int(text[c].map(len).max()) if len(text) else 0) for c in text.columns]
    header = "| " + " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(text.columns)) + " |"
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    body = ["| " + " | ".join(str(row[c]).ljust(widths[i]) for i, c in enumerate(text.columns)) + " |" for row in text.to_dict("records")]
    return "\n".join([header, sep, *body])


def write_report(cfg, match, provenance, join_audit, templates, real_metrics, by_run, synthetic_metrics, winner, runtime):
    best = real_metrics.iloc[0]
    trad = real_metrics[real_metrics["method"] == "traditional_template_cfd"].iloc[0]
    methods = pd.DataFrame(
        [
            ["traditional_template_cfd", "traditional", "bounded two-pulse template fit with CFD initialization"],
            ["ridge", "linear ML", "ridge classifier plus multi-output ridge regression"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted classifier/regressors"],
            ["mlp", "neural network", "tabular multilayer perceptron classifier/regressor pair"],
            ["1d_cnn", "neural network", "compact one-dimensional convolutional waveform model"],
            ["tiny_sequence_transformer", "neural sequence", "one-layer self-attention encoder"],
            ["template_residual_boosted_stack_new", "new hybrid", "boosted residual stack using traditional deconvolver outputs"],
        ],
        columns=["method", "family", "description"],
    )
    text = f"""# S37c: Event-Key Hand-Scan Label Join for Real Pile-Up Deconvolution

## Abstract

Ticket `{TICKET}` asks whether reviewer hand-scan candidate rows can be joined by
event key to raw HRD windows well enough to score S37b-style deconvolution
outputs against real pile-up labels with explicit reviewer-disagreement
intervals.  The worker was `{WORKER}`.  The analysis reproduces the B-stack raw
ROOT selected-pulse count, freezes training to source runs
`{cfg['benchmark_runs']['train']}`, joins hand-scan rows to raw ROOT by
`run:eventno:stave`, and applies a traditional template/CFD method plus ridge,
gradient-boosted trees, MLP, 1D-CNN, a transformer, and a new residual-stack
architecture to the joined real candidate windows.  The winner written to
`result.json` is **`{winner}`** with real-label AP `{best['real_label_ap']:.4g}`
and composite score `{best['winner_score']:.4g}`.

## Raw ROOT Reproduction

Raw files are read from `{cfg['raw_root_dir']}`.  The branch `h101/HRDv` is
reshaped to `(event, channel, sample)` and B2/B4/B6/B8 pulses are selected with

`b_ec = median_{{t in {{0,1,2,3}}}} x_ect`,

`A_ec = max_t(x_ect-b_ec)`,

`N = sum_ec 1[A_ec > 1000 ADC]`.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Hand-Scan Sources and Event-Key Join

{md_table(provenance, ['source_file', 'rows', 'sha256'])}

Rows are canonicalized to `run:eventno:stave`.  Multiple reviewer sources for the
same key are aggregated into a mean consensus label and an interval
`[min(vote), max(vote)]`; non-unanimous rows receive `reviewer_disagreement=1`.

{md_table(join_audit, ['run', 'requested_keys', 'joined_raw_windows', 'join_efficiency'])}

## Split and Models

The methods are trained only on controlled overlaps generated from raw ROOT
clean pulses in train runs `{cfg['benchmark_runs']['train']}`.  The real
hand-scan candidates are held out by source run.  Templates are estimated only
from training runs:

`T_s(t)=median_i x_i(t+tau_i-tau_ref)/max_t x_i(t)`.

{md_table(templates, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

{md_table(methods, ['method', 'family', 'description'])}

The traditional method is a physical comparator, not a weak baseline.  It
minimizes `SSE_k=sum_t [w(t)-b-sum_j A_j T_s(t-t_j)]^2` for one- and two-pulse
hypotheses and uses `(SSE_1-SSE_2)/SSE_1` as overlap evidence.  The new
architecture, `template_residual_boosted_stack_new`, appends traditional fit
coordinates and overlap improvement to waveform features before fitting boosted
classification and regression heads.

## Real-Label Metrics

For held-out raw hand-scan row `i`, label `y_i` is the aggregated reviewer
consensus.  A method emits score `s_im`; accepted secondary rows satisfy
`s_im >= 0.5`.  The main ranking minimizes

`C_m = (1-AP_m) + 0.7 r_miss + 0.7 r_false + 0.25 r_tail + 0.20 |b_E| + 0.30 D_stave`,

where `r_tail` is the fraction of accepted predictions whose predicted delay is
more than 15 ns from a reviewer secondary separation when available, otherwise
outside the registered 5-80 ns real-candidate window.  `b_E` is the median
secondary-inclusive amplitude bias against raw peak amplitude, and `D_stave` is
the accepted-secondary rate span across B staves.  Confidence intervals are 95%
percentile intervals from `{int(cfg['ml']['bootstrap_samples'])}` held-out
source-run bootstrap resamples.

{md_table(real_metrics, ['method', 'winner_score', 'real_label_ap', 'real_label_ap_ci_low', 'real_label_ap_ci_high', 'real_label_auc', 'pileup_miss_rate', 'false_split_rate', 'accepted_secondary_fraction', 'timing_tail_rate_abs_gt_15ns', 'energy_bias_median', 'stave_pid_proxy_drift_span'])}

The traditional comparator has score `{trad['winner_score']:.4g}` and real-label
AP `{trad['real_label_ap']:.4g}`.  The selected winner has score
`{best['winner_score']:.4g}`.

## Run-Held-Out Stability

{md_table(by_run, ['method', 'heldout_run', 'real_label_ap', 'pileup_miss_rate', 'false_split_rate', 'accepted_secondary_fraction', 'timing_tail_rate_abs_gt_15ns'], limit=84)}

## Synthetic Closure Check

The same fitted methods are also checked on controlled run-held-out overlaps to
verify that the machinery still recovers exact injected timing/energy labels
before it is applied to reviewer labels.

{md_table(synthetic_metrics, ['method', 'detection_ap', 'detection_auc', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate', 'energy_fractional_sigma68'])}

## Systematics and Caveats

The hand-scan labels are real reviewer consensus labels, but they are not exact
constituent timing or amplitude truth.  Reviewer intervals are vote intervals,
not calibrated Bayesian credible intervals.  Event-key matching uses
`run:eventno:stave`; if a DAQ file reused an event number within a run, the join
would need `event_index` as an additional key.  The model training labels remain
controlled overlays, so real-label scoring tests transfer to hand-scanned
candidate morphology rather than supervised learning from human labels.  PID is
represented by stave-conditioned acceptance drift because no event-native
particle-ID branch is available in the audited raw ROOT files.  Bootstrap CIs
resample held-out source runs and quantify run-transfer uncertainty.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "claimed_ticket.txt").write_text(TICKET + f"\n# {TITLE}\n", encoding="utf-8")
    cfg = load_config()
    rng = np.random.default_rng(int(cfg["random_seed"]))

    match = p05a.reproduce_counts(cfg)
    match.to_csv(OUT / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    hand_labels, provenance = load_handscan_labels()
    train_run_set = set(int(run) for run in cfg["benchmark_runs"]["train"])
    hand_labels = hand_labels[~hand_labels["run"].isin(train_run_set)].copy()
    hand_labels.to_csv(OUT / "handscan_canonical_labels.csv", index=False)
    provenance.to_csv(OUT / "handscan_source_provenance.csv", index=False)
    real_events, real_waves, join_audit = read_joined_raw_windows(hand_labels, cfg)
    join_audit.to_csv(OUT / "event_key_join_audit.csv", index=False)

    train_runs = cfg["benchmark_runs"]["train"]
    all_benchmark_runs = cfg["benchmark_runs"]["train"] + cfg["benchmark_runs"]["heldout"]
    clean = p05a.read_clean_pulses(cfg, all_benchmark_runs, rng)
    train_clean = clean[clean["run"].isin(train_runs)].copy()
    templates, template_summary = p05a.build_templates(train_clean, cfg)
    template_summary.to_csv(OUT / "template_summary.csv", index=False)
    train_events, train_waves = p05a.generate_benchmark(clean, templates, cfg, "train", train_runs, rng)

    combined_events = pd.concat([train_events, real_events], ignore_index=True)
    combined_waves = np.vstack([train_waves, real_waves])
    trad_raw = p05a.run_template_fits(combined_events, combined_waves, templates, cfg)
    preds = [template_prediction_from_trad(trad_raw)]
    preds.extend(base.run_sklearn_methods(combined_events, combined_waves, int(cfg["random_seed"])))
    preds.append(base.cnn_prediction(combined_events, combined_waves, cfg))
    preds.append(seqbase.transformer_prediction(combined_events, combined_waves, cfg))
    preds.append(base.add_residual_stack(combined_events, combined_waves, trad_raw, int(cfg["random_seed"])))
    all_pred = pd.concat(preds, ignore_index=True)

    event_cols = [
        "event_id",
        "split",
        "source_run",
        "stave",
        "is_overlap",
        "handscan_label",
        "reviewer_weight",
        "reviewer_disagreement",
        "label_interval_low",
        "label_interval_high",
        "review_secondary_sep",
        "raw_amp_adc",
        "raw_peak_sample",
        "event_key",
        "label_sources",
        "true_t1_sample",
        "true_t2_sample",
        "true_amp1_adc",
        "true_amp2_adc",
        "true_sep_sample",
        "true_ratio",
    ]
    joined = all_pred.merge(combined_events[event_cols], on="event_id", how="left")
    real_joined = joined[joined["split"] == "heldout"].copy()
    real_joined.to_csv(OUT / "real_handscan_event_predictions.csv", index=False)
    real_metrics = real_bootstrap(real_joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    real_metrics.to_csv(OUT / "real_label_method_metrics.csv", index=False)
    by_run = by_run_metrics(real_joined)
    by_run.to_csv(OUT / "real_label_run_metrics.csv", index=False)

    held_events, held_waves = p05a.generate_benchmark(clean, templates, cfg, "heldout", cfg["benchmark_runs"]["heldout"], rng)
    synthetic_events = pd.concat([train_events, held_events], ignore_index=True)
    synthetic_waves = np.vstack([train_waves, held_waves])
    synthetic_trad = p05a.run_template_fits(synthetic_events, synthetic_waves, templates, cfg)
    synthetic_preds = [base.template_prediction(synthetic_trad)]
    synthetic_preds.extend(base.run_sklearn_methods(synthetic_events, synthetic_waves, int(cfg["random_seed"])))
    synthetic_preds.append(base.cnn_prediction(synthetic_events, synthetic_waves, cfg))
    synthetic_preds.append(seqbase.transformer_prediction(synthetic_events, synthetic_waves, cfg))
    synthetic_preds.append(base.add_residual_stack(synthetic_events, synthetic_waves, synthetic_trad, int(cfg["random_seed"])))
    synthetic_all = pd.concat(synthetic_preds, ignore_index=True)
    base_cols = ["event_id", "split", "source_run", "stave", "is_overlap", "true_t1_sample", "true_t2_sample", "true_amp1_adc", "true_amp2_adc", "true_sep_sample", "true_ratio"]
    synthetic_joined = synthetic_all.merge(synthetic_events[base_cols], on="event_id", how="left")
    synthetic_metrics = base.summarize(synthetic_joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    synthetic_metrics.to_csv(OUT / "synthetic_closure_method_metrics.csv", index=False)

    winner = str(real_metrics.iloc[0]["method"])
    runtime = time.time() - started
    write_report(cfg, match, provenance, join_audit, template_summary, real_metrics, by_run, synthetic_metrics, winner, runtime)

    input_rows = [
        {"path": str(path), "sha256": sha256_file(path), "size": path.stat().st_size}
        for path in sorted(RAW_ROOT_DIR.glob("hrdb_run_*.root"))
    ]
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)
    best = real_metrics.iloc[0]
    result = {
        "ticket_id": TICKET,
        "project": "testbeam",
        "worker": WORKER,
        "title": TITLE,
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
        "event_key_join": {
            "key": "run:eventno:stave",
            "joined_raw_windows": int(join_audit["joined_raw_windows"].sum()),
            "requested_keys": int(join_audit["requested_keys"].sum()),
            "join_efficiency": float(join_audit["joined_raw_windows"].sum() / max(join_audit["requested_keys"].sum(), 1)),
            "audit_table": "event_key_join_audit.csv",
            "canonical_labels": "handscan_canonical_labels.csv",
        },
        "evaluation_design": {
            "train_runs": cfg["benchmark_runs"]["train"],
            "heldout_real_runs": sorted(map(int, real_events["source_run"].unique())),
            "split": "all model fitting uses source train runs; joined hand-scan raw windows are held out by run",
            "bootstrap": "held-out source_run percentile 95% CI",
            "bootstrap_replicates": int(cfg["ml"]["bootstrap_samples"]),
            "winner_score": "real-label AP, miss, false split, timing-tail, energy-bias, and stave/PID-proxy drift composite",
        },
        "required_method_coverage": {
            "strong_traditional": "traditional_template_cfd",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "transformer": "tiny_sequence_transformer",
            "new_architecture": "template_residual_boosted_stack_new",
        },
        "winner": {
            "name": winner,
            "criterion": "minimum S37c real hand-scan label composite score with run-block bootstrap CIs",
            "winner_score": float(best["winner_score"]),
            "real_label_ap": float(best["real_label_ap"]),
            "real_label_ap_ci95": [float(best["real_label_ap_ci_low"]), float(best["real_label_ap_ci_high"])],
            "real_label_auc": float(best["real_label_auc"]),
            "pileup_miss_rate": float(best["pileup_miss_rate"]),
            "false_split_rate": float(best["false_split_rate"]),
            "accepted_secondary_fraction": float(best["accepted_secondary_fraction"]),
            "timing_tail_rate_abs_gt_15ns": float(best["timing_tail_rate_abs_gt_15ns"]),
            "energy_bias_median": float(best["energy_bias_median"]),
            "stave_pid_proxy_drift_span": float(best["stave_pid_proxy_drift_span"]),
        },
        "artifacts": {
            "report": "REPORT.md",
            "manifest": "manifest.json",
            "claimed_ticket": "claimed_ticket.txt",
            "raw_reproduction": "reproduction_match_table.csv",
            "handscan_source_provenance": "handscan_source_provenance.csv",
            "event_key_join_audit": "event_key_join_audit.csv",
            "real_predictions": "real_handscan_event_predictions.csv",
            "real_label_method_metrics": "real_label_method_metrics.csv",
            "real_label_run_metrics": "real_label_run_metrics.csv",
            "synthetic_closure_method_metrics": "synthetic_closure_method_metrics.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "caveats": [
            "Reviewer labels are consensus intervals, not exact constituent timing truth.",
            "Model training labels are controlled overlaps; real hand-scan labels are held out for transfer scoring.",
            "PID drift is a stave-conditioned proxy because raw ROOT has no event-native particle-ID branch.",
            "The join key is run:eventno:stave; event-index collisions would require a stricter key if observed.",
        ],
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "ticket_id": TICKET,
        "git_commit": git_commit(),
        "command": f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}",
        "runtime_seconds": runtime,
        "python": sys.version,
        "platform": platform.platform(),
        "outputs_sha256": {
            p.name: sha256_file(p)
            for p in sorted(OUT.iterdir())
            if p.is_file() and p.name != "manifest.json"
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
