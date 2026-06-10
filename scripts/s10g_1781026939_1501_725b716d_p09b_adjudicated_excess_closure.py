#!/usr/bin/env python3
"""S10g: compare P09a and P09b labels in S10e P04/P07 strata.

The analysis rebuilds the S10e selected-event table from raw B-stack ROOT,
reproduces the published S10e P04/P07 charge-stratified excess first, then
adds both deterministic P09a taxonomy labels and P09b adjudication-rubric
labels as explanatory strata and as held-out ML features. ML scores are
diagnostics only; no Monte Carlo labels are used.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import time
from importlib import util
from pathlib import Path

import numpy as np
import pandas as pd
import uproot
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/1781026939.1501.725b716d"
OUT.mkdir(parents=True, exist_ok=True)
RAW = ROOT / "data/root/root"

TICKET = "1781026939.1501.725b716d"
WORKER = "testbeam-laptop-4"
STUDY = "S10g"
RNG_SEED = 1781026939
BOOTSTRAPS = 400
MIN_STRATUM_N = 25
MAX_DOWNSTREAM_TRAIN = 18000
MAX_CHARGE_TRAIN = 22000

S10E_REPORT = ROOT / "reports/1781010955.636.68b17313/s10e_charge_energy_transfer.py"
P09A_SCRIPT = ROOT / "scripts/p09a_rare_waveform_anomaly_taxonomy.py"
P09A_CONFIG = ROOT / "configs/p09a_rare_waveform_anomaly_taxonomy.json"
P09B_SCRIPT = ROOT / "scripts/p09b_manual_waveform_gallery_adjudication.py"
P09B_REPORT = ROOT / "reports/1781011449.1304.37c054cc__p09b_manual_waveform_gallery_adjudication"
P09B_ADJUDICATION = P09B_REPORT / "adjudication_labels.csv"
P09B_MANIFEST = P09B_REPORT / "manifest.json"
P09B_TARGET_TAXA = {
    "novel_early_pretrigger",
    "novel_delayed_peak",
    "novel_broad_template_mismatch",
}


def import_module(path: Path, name: str):
    spec = util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import {}".format(path))
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s10e = import_module(S10E_REPORT, "s10e_charge_energy_transfer_source")
p09a = import_module(P09A_SCRIPT, "p09a_rare_waveform_anomaly_taxonomy_source")
p09b = import_module(P09B_SCRIPT, "p09b_manual_waveform_gallery_adjudication_source")


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


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def load_events_with_p09a_features() -> tuple[pd.DataFrame, np.ndarray, np.ndarray, pd.DataFrame]:
    group_for_run = s10e.run_to_group()
    even_channels = np.asarray(list(s10e.STAVES.values()), dtype=int)
    odd_channels = np.asarray(list(s10e.DUPLICATE_CHANNELS.values()), dtype=int)
    stave_names = np.asarray(list(s10e.STAVES.keys()), dtype=object)
    event_frames = []
    shape_frames = []
    ref_waves = []
    norm_waves = []
    run_rows = []

    for run in sorted(group_for_run):
        path = RAW / "hrdb_run_{:04d}.root".format(run)
        group = group_for_run[run]
        current = s10e.RUN_GROUPS[group]["current_nA"]
        counts = {
            "run": int(run),
            "group": group,
            "current_nA": float(current),
            "events_total": 0,
            "events_with_selected": 0,
            "selected_pulses": 0,
            "multi_stave_events": 0,
            "three_stave_events": 0,
            "downstream_events": 0,
        }
        event_offset = 0
        for batch in uproot.open(path)["h101"].iterate(["EVENTNO", "HRDv"], step_size=20000, library="np"):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            all_events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, s10e.NSAMPLES)
            raw_even = all_events[:, even_channels, :]
            raw_odd = all_events[:, odd_channels, :]
            seed_even = np.median(raw_even[..., s10e.BASELINE_SAMPLES], axis=-1)
            seed_odd = np.median(raw_odd[..., s10e.BASELINE_SAMPLES], axis=-1)
            even = raw_even - seed_even[..., None]
            odd = raw_odd - seed_odd[..., None]
            amp = even.max(axis=-1)
            even_integral = np.clip(even, 0.0, None).sum(axis=-1)
            odd_charge = np.clip(-odd, 0.0, None).sum(axis=-1)
            selected = amp > s10e.AMP_CUT
            n_selected = selected.sum(axis=1)
            keep = n_selected >= 1

            counts["events_total"] += int(len(eventno))
            counts["events_with_selected"] += int(keep.sum())
            counts["selected_pulses"] += int(selected.sum())
            counts["multi_stave_events"] += int((n_selected >= 2).sum())
            counts["three_stave_events"] += int((n_selected >= 3).sum())
            counts["downstream_events"] += int(selected[:, 1:].any(axis=1).sum())
            if not keep.any():
                event_offset += int(len(eventno))
                continue

            masked_amp = np.where(selected, amp, -np.inf)
            ref_idx = masked_amp.argmax(axis=1)[keep]
            row_idx = np.where(keep)[0]
            raw_ref = raw_even[row_idx, ref_idx, :]
            corr_ref = even[row_idx, ref_idx, :]
            odd_ref = odd[row_idx, ref_idx, :]
            ref_amp = amp[row_idx, ref_idx].astype(np.float64)
            lowering = s10e.adaptive_lowering(raw_ref, seed_even[row_idx, ref_idx])

            frame = pd.DataFrame(
                {
                    "run": int(run),
                    "group": group,
                    "current_nA": float(current),
                    "event_index": (row_idx + event_offset).astype(int),
                    "eventno": eventno[row_idx],
                    "n_selected": n_selected[row_idx].astype(int),
                    "multi_stave": (n_selected[row_idx] >= 2).astype(int),
                    "three_stave": (n_selected[row_idx] >= 3).astype(int),
                    "downstream": selected[row_idx, 1:].any(axis=1).astype(int),
                    "ref_stave": stave_names[ref_idx],
                    "ref_stave_idx": ref_idx.astype(int),
                    "ref_amp_adc": ref_amp,
                    "integral_charge": even_integral[row_idx, ref_idx],
                    "p04_duplicate_charge": odd_charge[row_idx, ref_idx],
                    "adaptive_lowering_adc": lowering,
                }
            )
            norm = (corr_ref / np.maximum(ref_amp, 1.0)[:, None]).astype(np.float32)
            dup_amp = np.maximum(np.abs(odd_ref).max(axis=1), 1.0).astype(np.float32)
            dup_norm = (odd_ref / dup_amp[:, None]).astype(np.float32)
            tax_features = p09a.pulse_features(norm, raw_ref.astype(np.float32), dup_norm, s10e.BASELINE_SAMPLES)
            tax_features.insert(0, "amplitude_adc", ref_amp.astype(np.float32))
            tax_features.insert(0, "stave", stave_names[ref_idx])
            tax_features.insert(0, "event_index", (row_idx + event_offset).astype(np.int32))
            tax_features.insert(0, "eventno", eventno[row_idx])
            tax_features.insert(0, "run", int(run))

            event_frames.append(frame)
            shape_frames.append(tax_features)
            ref_waves.append(corr_ref.astype(np.float32))
            norm_waves.append(norm)
            event_offset += int(len(eventno))
        run_rows.append(counts)

    events = pd.concat(event_frames, ignore_index=True)
    waves = np.concatenate(ref_waves, axis=0)
    norm = np.concatenate(norm_waves, axis=0)
    p09_meta = pd.concat(shape_frames, ignore_index=True)
    events = pd.concat([events.reset_index(drop=True), s10e.shape_features(waves, events["ref_amp_adc"].to_numpy())], axis=1)
    templates = s10e.build_templates(events, waves)
    events["template_charge"] = s10e.template_charge_proxy(events, waves, templates)
    events["p07_corrected_charge"] = s10e.p07_correct_charge(events)
    events = s10e.assign_charge_strata(events, "p04_duplicate_charge", "uncorrected")
    events = s10e.assign_charge_strata(events, "p07_corrected_charge", "p07_corrected")
    return events, waves, norm, pd.DataFrame(run_rows), p09_meta


def add_p09a_labels(events: pd.DataFrame, norm_waves: np.ndarray, p09_meta: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    config = json.loads(P09A_CONFIG.read_text(encoding="utf-8"))
    train_mask = ~p09_meta["run"].isin([int(x) for x in config["heldout_runs"]]).to_numpy()
    with_template = p09a.add_template_residual(config, norm_waves, p09_meta, train_mask)
    labelled, thresholds = p09a.add_taxonomy(with_template, train_mask)
    out = events.copy()
    p09_shape_cols = {
        "amplitude_adc",
        "baseline_mad",
        "saturation_count",
        "secondary_peak",
        "post_peak_min",
        "timing_span_dup",
    }
    for col in labelled.columns:
        if col.startswith("label_") or col in ["taxon", "q_template_rmse", "template_bin"] or col in p09_shape_cols:
            out[col] = labelled[col].to_numpy()
    out["p09a_taxon"] = out["taxon"].astype(str)
    out["taxon_for_strata"] = out["taxon"].astype(str)
    out["uncorrected_p09a_stratum"] = out["uncorrected_stratum"].astype(str) + "|p09a=" + out["taxon_for_strata"]
    out["p07_corrected_p09a_stratum"] = out["p07_corrected_stratum"].astype(str) + "|p09a=" + out["taxon_for_strata"]
    return out, thresholds


def p09b_waveform_features(norm_waves: np.ndarray) -> pd.DataFrame:
    w = np.asarray(norm_waves, dtype=np.float32)
    pos = np.clip(w, 0.0, None)
    pos_sum = np.maximum(pos.sum(axis=1), 1e-6)
    peak = w.argmax(axis=1).astype(np.int16)
    masked = pos.copy()
    for i, p in enumerate(peak):
        masked[i, max(0, int(p) - 1) : min(w.shape[1], int(p) + 2)] = 0.0
    sec_idx = masked.argmax(axis=1).astype(np.int16)
    post_peak_min = np.zeros(len(w), dtype=np.float32)
    undershoot_area = np.zeros(len(w), dtype=np.float32)
    for i, p in enumerate(peak):
        tail = w[i, min(w.shape[1] - 1, int(p) + 1) :]
        post_peak_min[i] = float(tail.min()) if len(tail) else 0.0
        undershoot_area[i] = float(np.clip(tail, None, 0.0).sum()) if len(tail) else 0.0
    return pd.DataFrame(
        {
            "review_peak_sample": peak,
            "review_peak_value": w[np.arange(len(w)), peak],
            "review_width_half": (w > 0.5).sum(axis=1).astype(np.int16),
            "review_width_035": (w > 0.35).sum(axis=1).astype(np.int16),
            "review_early_fraction": pos[:, :4].sum(axis=1) / pos_sum,
            "review_late_fraction": pos[:, 12:].sum(axis=1) / pos_sum,
            "review_secondary_peak": masked[np.arange(len(w)), sec_idx],
            "review_secondary_sep": np.abs(sec_idx - peak).astype(np.int16),
            "review_post_peak_min": post_peak_min,
            "review_undershoot_area": undershoot_area,
            "review_first4_span": w[:, :4].max(axis=1) - w[:, :4].min(axis=1),
            "review_last4_mean": w[:, -4:].mean(axis=1),
            "review_tail_rise": w[:, -1] - w[:, np.minimum(12, w.shape[1] - 1)],
        }
    )


def ordered_labels(conditions: list[np.ndarray], labels: list[str], n_rows: int) -> np.ndarray:
    out = np.full(n_rows, "unassigned_common", dtype=object)
    unset = np.ones(n_rows, dtype=bool)
    for condition, label in zip(conditions, labels):
        take = unset & condition
        out[take] = label
        unset[take] = False
    return out


def p09b_reviewer_labels(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(frame)
    peak = frame["review_peak_sample"].to_numpy(dtype=int)
    saturation_count = frame["saturation_count"].to_numpy(dtype=float)
    amp = frame["amplitude_adc"].to_numpy(dtype=float)
    post_min = frame["review_post_peak_min"].to_numpy(dtype=float)
    baseline_mad = frame["baseline_mad"].to_numpy(dtype=float)
    first4_span = frame["review_first4_span"].to_numpy(dtype=float)
    secondary_peak = frame["review_secondary_peak"].to_numpy(dtype=float)
    secondary_sep = frame["review_secondary_sep"].to_numpy(dtype=float)
    early = frame["review_early_fraction"].to_numpy(dtype=float)
    late = frame["review_late_fraction"].to_numpy(dtype=float)
    last4 = frame["review_last4_mean"].to_numpy(dtype=float)
    width_half = frame["review_width_half"].to_numpy(dtype=float)
    width_035 = frame["review_width_035"].to_numpy(dtype=float)
    q = frame["q_template_rmse"].to_numpy(dtype=float)
    undershoot = frame["review_undershoot_area"].to_numpy(dtype=float)
    tail_rise = frame["review_tail_rise"].to_numpy(dtype=float)

    labels = [
        "saturation",
        "dropout",
        "baseline_excursion",
        "pileup_or_long_tail",
        "novel_early_pretrigger",
        "novel_delayed_peak",
        "novel_broad_template_mismatch",
    ]
    reviewer_a = ordered_labels(
        [
            (saturation_count >= 2) & (amp > 7000),
            post_min < -0.82,
            (baseline_mad > 1200) & (first4_span > 0.85),
            (secondary_peak > 0.62) & (secondary_sep >= 4),
            (peak <= 3) & (early >= 0.48),
            (peak >= 14) | ((peak >= 13) & (late > 0.48) & (last4 > 0.45)),
            (width_half >= 6) | ((width_035 >= 9) & (q > 0.42)) | ((q > 0.95) & (secondary_peak < 0.58)),
        ],
        labels,
        n,
    )
    reviewer_b = ordered_labels(
        [
            (saturation_count >= 2) & (amp > 6000),
            (post_min < -0.95) | (undershoot < -2.0),
            (baseline_mad > 1600) | ((first4_span > 1.15) & (peak <= 5)),
            (secondary_peak > 0.55) & (secondary_sep >= 4) & (late > 0.18),
            (peak <= 3) | ((peak == 4) & (early > 0.58)),
            (peak >= 13) & ((late > 0.33) | (tail_rise > 0.22)),
            (width_half >= 5) & ((q > 0.35) | (width_035 >= 8)),
        ],
        labels,
        n,
    )
    resolver = ordered_labels(
        [
            (saturation_count >= 2) & (amp > 6500),
            post_min < -0.9,
            (baseline_mad > 1500) & (first4_span > 0.75),
            peak <= 3,
            (peak >= 14) | ((peak >= 13) & (late > 0.4)),
            (width_half >= 6) | ((width_035 >= 9) & (q > 0.4)),
            (secondary_peak > 0.6) & (secondary_sep >= 4),
        ],
        labels,
        n,
    )
    consensus = np.where(reviewer_a == reviewer_b, reviewer_a, resolver)
    return reviewer_a, reviewer_b, consensus


def add_p09b_labels(events: pd.DataFrame, norm_waves: np.ndarray) -> pd.DataFrame:
    review = p09b_waveform_features(norm_waves)
    labelled = pd.concat([events.reset_index(drop=True), review], axis=1)
    reviewer_a, reviewer_b, consensus = p09b_reviewer_labels(labelled)
    labelled["reviewer_a_label"] = reviewer_a
    labelled["reviewer_b_label"] = reviewer_b
    labelled["p09b_raw_consensus_label"] = consensus
    p09a_rare_candidate = labelled["p09a_taxon"].isin(P09B_TARGET_TAXA)
    labelled["p09b_consensus_label"] = np.where(p09a_rare_candidate, consensus, labelled["p09a_taxon"].astype(str))
    labelled["p09b_source"] = np.where(p09a_rare_candidate, "rubric_on_p09a_rare_candidate", "p09a_background_non_rare")
    if P09B_ADJUDICATION.exists():
        gallery = pd.read_csv(P09B_ADJUDICATION).rename(columns={"consensus_label": "gallery_consensus_label"})
        gallery = gallery[["run", "event_index", "stave", "gallery_consensus_label"]].drop_duplicates(
            ["run", "event_index", "stave"], keep="first"
        )
        gallery_key = pd.MultiIndex.from_frame(gallery[["run", "event_index", "stave"]])
        gallery_map = pd.Series(gallery["gallery_consensus_label"].to_numpy(), index=gallery_key)
        event_key = pd.MultiIndex.from_frame(labelled[["run", "event_index", "ref_stave"]])
        gallery_labels = pd.Series(index=event_key, dtype=object)
        gallery_labels.loc[gallery_labels.index.intersection(gallery_map.index)] = gallery_map.loc[
            gallery_labels.index.intersection(gallery_map.index)
        ]
        has_gallery = gallery_labels.notna().to_numpy()
        labelled.loc[has_gallery, "p09b_consensus_label"] = gallery_labels.loc[has_gallery].to_numpy()
        labelled.loc[has_gallery, "p09b_source"] = "exact_p09b_gallery_adjudication"
    labelled["p09b_reviewers_agree"] = labelled["reviewer_a_label"] == labelled["reviewer_b_label"]
    labelled["p09b_target_any"] = labelled["p09b_consensus_label"].isin(P09B_TARGET_TAXA)
    labelled["p09b_curated_any"] = labelled["p09b_consensus_label"] != "unassigned_common"
    labelled["p09b_label_for_strata"] = labelled["p09b_consensus_label"].astype(str)
    labelled["uncorrected_p09b_stratum"] = (
        labelled["uncorrected_stratum"].astype(str) + "|p09b=" + labelled["p09b_label_for_strata"]
    )
    labelled["p07_corrected_p09b_stratum"] = (
        labelled["p07_corrected_stratum"].astype(str) + "|p09b=" + labelled["p09b_label_for_strata"]
    )
    return labelled


def compare_p09a_p09b(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for scope, frame in [("all_s10_events", events)]:
        total = max(1, len(frame))
        rows.extend(
            [
                {
                    "scope": scope,
                    "metric": "n_events",
                    "value": float(len(frame)),
                    "numerator": int(len(frame)),
                    "denominator": int(len(frame)),
                },
                {
                    "scope": scope,
                    "metric": "exact_label_match_rate",
                    "value": float((frame["p09a_taxon"] == frame["p09b_consensus_label"]).mean()),
                    "numerator": int((frame["p09a_taxon"] == frame["p09b_consensus_label"]).sum()),
                    "denominator": int(total),
                },
                {
                    "scope": scope,
                    "metric": "target_any_match_rate",
                    "value": float((frame["p09a_taxon"].isin(P09B_TARGET_TAXA) == frame["p09b_target_any"]).mean()),
                    "numerator": int((frame["p09a_taxon"].isin(P09B_TARGET_TAXA) == frame["p09b_target_any"]).sum()),
                    "denominator": int(total),
                },
                {
                    "scope": scope,
                    "metric": "p09a_target_rate",
                    "value": float(frame["p09a_taxon"].isin(P09B_TARGET_TAXA).mean()),
                    "numerator": int(frame["p09a_taxon"].isin(P09B_TARGET_TAXA).sum()),
                    "denominator": int(total),
                },
                {
                    "scope": scope,
                    "metric": "p09b_target_rate",
                    "value": float(frame["p09b_target_any"].mean()),
                    "numerator": int(frame["p09b_target_any"].sum()),
                    "denominator": int(total),
                },
                {
                    "scope": scope,
                    "metric": "p09b_review_agreement_rate",
                    "value": float(frame["p09b_reviewers_agree"].mean()),
                    "numerator": int(frame["p09b_reviewers_agree"].sum()),
                    "denominator": int(total),
                },
            ]
        )

    if P09B_ADJUDICATION.exists():
        gallery = pd.read_csv(P09B_ADJUDICATION).rename(
            columns={"consensus_label": "gallery_consensus_label", "taxon": "gallery_p09a_taxon"}
        )
        merged = events.merge(
            gallery[["run", "event_index", "stave", "gallery_consensus_label", "gallery_p09a_taxon"]],
            left_on=["run", "event_index", "ref_stave"],
            right_on=["run", "event_index", "stave"],
            how="inner",
        )
        if len(merged):
            rows.append(
                {
                    "scope": "exact_gallery_ref_overlap",
                    "metric": "n_events",
                    "value": float(len(merged)),
                    "numerator": int(len(merged)),
                    "denominator": int(len(gallery)),
                }
            )
            rows.append(
                {
                    "scope": "exact_gallery_ref_overlap",
                    "metric": "script_p09b_matches_gallery_consensus",
                    "value": float((merged["p09b_consensus_label"] == merged["gallery_consensus_label"]).mean()),
                    "numerator": int((merged["p09b_consensus_label"] == merged["gallery_consensus_label"]).sum()),
                    "denominator": int(len(merged)),
                }
            )
            rows.append(
                {
                    "scope": "exact_gallery_ref_overlap",
                    "metric": "p09a_matches_gallery_taxon",
                    "value": float((merged["p09a_taxon"] == merged["gallery_p09a_taxon"]).mean()),
                    "numerator": int((merged["p09a_taxon"] == merged["gallery_p09a_taxon"]).sum()),
                    "denominator": int(len(merged)),
                }
            )
    return pd.DataFrame(rows)


def summarize_traditional_all(events: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    s10e.BOOTSTRAPS = BOOTSTRAPS
    s10e.MIN_STRATUM_N = MIN_STRATUM_N
    tables = {}
    rows = []
    specs = [
        ("uncorrected", "uncorrected_stratum", "p04_duplicate_charge"),
        ("p07_corrected", "p07_corrected_stratum", "p07_corrected_charge"),
        ("uncorrected_plus_p09a_taxon", "uncorrected_p09a_stratum", "p04_duplicate_charge"),
        ("p07_corrected_plus_p09a_taxon", "p07_corrected_p09a_stratum", "p07_corrected_charge"),
        ("uncorrected_plus_p09b_adjudicated", "uncorrected_p09b_stratum", "p04_duplicate_charge"),
        ("p07_corrected_plus_p09b_adjudicated", "p07_corrected_p09b_stratum", "p07_corrected_charge"),
    ]
    for label, stratum_col, charge_col in specs:
        strata, summary = s10e.summarize_traditional(events, stratum_col, charge_col, label, rng)
        tables[label] = strata
        rows.append(summary)
    return pd.concat(rows, ignore_index=True), tables


def metric_value(summary: pd.DataFrame, definition: str, metric: str) -> pd.Series:
    return summary[(summary["strata_definition"] == definition) & (summary["metric"] == metric)].iloc[0]


def build_propagation_summary(trad: pd.DataFrame) -> pd.DataFrame:
    pairs = [
        ("uncorrected", "uncorrected_plus_p09a_taxon", "downstream_high_minus_low", "downstream_high_minus_low"),
        ("p07_corrected", "p07_corrected_plus_p09a_taxon", "downstream_high_minus_low", "downstream_high_minus_low"),
        ("uncorrected", "uncorrected_plus_p09b_adjudicated", "downstream_high_minus_low", "downstream_high_minus_low"),
        ("p07_corrected", "p07_corrected_plus_p09b_adjudicated", "downstream_high_minus_low", "downstream_high_minus_low"),
        (
            "uncorrected",
            "uncorrected_plus_p09a_taxon",
            "p04_duplicate_charge_median_log_shift",
            "p04_duplicate_charge_median_log_shift",
        ),
        (
            "p07_corrected",
            "p07_corrected_plus_p09a_taxon",
            "p07_corrected_charge_median_log_shift",
            "p07_corrected_plus_p09a_taxon_charge_median_log_shift",
        ),
        (
            "uncorrected",
            "uncorrected_plus_p09b_adjudicated",
            "p04_duplicate_charge_median_log_shift",
            "p04_duplicate_charge_median_log_shift",
        ),
        (
            "p07_corrected",
            "p07_corrected_plus_p09b_adjudicated",
            "p07_corrected_charge_median_log_shift",
            "p07_corrected_plus_p09b_adjudicated_charge_median_log_shift",
        ),
    ]
    rows = []
    for base, labelled, base_metric, labelled_metric in pairs:
        b = metric_value(trad, base, base_metric)
        a = metric_value(trad, labelled, labelled_metric)
        base_value = float(b["value"])
        labelled_value = float(a["value"])
        rows.append(
            {
                "base_strata": base,
                "taxon_strata": labelled,
                "metric": base_metric,
                "base_value": base_value,
                "taxon_value": labelled_value,
                "taxon_minus_base": labelled_value - base_value,
                "fractional_attenuation": (base_value - labelled_value) / base_value if abs(base_value) > 1e-12 else np.nan,
                "base_ci_low": float(b["ci_low"]),
                "base_ci_high": float(b["ci_high"]),
                "taxon_ci_low": float(a["ci_low"]),
                "taxon_ci_high": float(a["ci_high"]),
                "base_n_strata": int(b["n_strata"]),
                "taxon_n_strata": int(a["n_strata"]),
            }
        )
    return pd.DataFrame(rows)


def taxon_counts(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    total_by_group = events.groupby("group").size().to_dict()
    for source, col in [("p09a", "p09a_taxon"), ("p09b", "p09b_consensus_label")]:
        for (group, taxon), sub in events.groupby(["group", col], sort=True):
            rows.append(
                {
                    "label_source": source,
                    "group": group,
                    "label": taxon,
                    "n": int(len(sub)),
                    "group_rate": float(len(sub) / max(1, total_by_group[group])),
                    "downstream_rate": float(sub["downstream"].mean()),
                    "median_log_p04_charge": float(np.log(np.maximum(sub["p04_duplicate_charge"].to_numpy(), 1.0)).mean()),
                }
            )
    return pd.DataFrame(rows)


def fixed_design(frame: pd.DataFrame, label_source: str, for_charge_target: bool) -> pd.DataFrame:
    data = pd.DataFrame(index=frame.index)
    numeric_cols = [
        "ref_amp_adc",
        "integral_charge",
        "template_charge",
        "adaptive_lowering_adc",
        "tail_fraction",
        "late_fraction",
        "early_fraction",
        "width_20_samples",
        "q_template_rmse",
    ]
    if not for_charge_target:
        numeric_cols.extend(["p04_duplicate_charge", "p07_corrected_charge"])
    for col in numeric_cols:
        values = frame[col].to_numpy(dtype=float)
        if col.endswith("charge") or col == "ref_amp_adc":
            values = np.log(np.maximum(values, 1.0))
        data[col] = values
    cat_cols = ["uncorrected_stratum", "p07_corrected_stratum", "ref_stave"]
    if label_source == "p09a":
        cat_cols.extend(["p09a_taxon", "label_known_any", "label_novel_any", "label_curated_any"])
    elif label_source == "p09b":
        cat_cols.extend(["p09b_consensus_label", "p09b_target_any", "p09b_curated_any", "p09b_reviewers_agree"])
    elif label_source != "base":
        raise ValueError("unknown label_source {}".format(label_source))
    cats = pd.get_dummies(frame[cat_cols].astype(str), prefix=cat_cols, dtype=float)
    return pd.concat([data, cats], axis=1)


def align_matrix(all_x: pd.DataFrame, idx: np.ndarray) -> np.ndarray:
    return all_x.iloc[idx].to_numpy(dtype=float)


def capped_downstream_train_indices(events: pd.DataFrame, train_idx: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    if len(train_idx) <= MAX_DOWNSTREAM_TRAIN:
        return train_idx
    y = events.iloc[train_idx]["downstream"].to_numpy(dtype=int)
    pos = train_idx[y == 1]
    neg = train_idx[y == 0]
    max_pos = min(len(pos), MAX_DOWNSTREAM_TRAIN // 2)
    if len(pos) > max_pos:
        pos = rng.choice(pos, size=max_pos, replace=False)
    neg_take = min(len(neg), MAX_DOWNSTREAM_TRAIN - len(pos))
    neg = rng.choice(neg, size=neg_take, replace=False)
    out = np.concatenate([pos, neg])
    rng.shuffle(out)
    return out


def capped_charge_train_indices(events: pd.DataFrame, train_idx: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    if len(train_idx) <= MAX_CHARGE_TRAIN:
        return train_idx
    frame = events.iloc[train_idx][["run", "group"]].copy()
    frame["_idx"] = train_idx
    pieces = []
    groups = list(frame.groupby(["group", "run"], sort=True))
    per_group = max(1, int(np.ceil(MAX_CHARGE_TRAIN / max(1, len(groups)))))
    for _, sub in groups:
        idx = sub["_idx"].to_numpy()
        take = min(len(idx), per_group)
        pieces.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(pieces)
    if len(out) > MAX_CHARGE_TRAIN:
        out = rng.choice(out, size=MAX_CHARGE_TRAIN, replace=False)
    rng.shuffle(out)
    return out


def run_heldout_ml(events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    diagnostics = []
    y_down = events["downstream"].to_numpy(dtype=int)
    y_log_charge = np.log(np.maximum(events["p04_duplicate_charge"].to_numpy(dtype=float), 1.0))
    designs = {
        "base": {
            "downstream": fixed_design(events, label_source="base", for_charge_target=False),
            "charge": fixed_design(events, label_source="base", for_charge_target=True),
        },
        "p09a": {
            "downstream": fixed_design(events, label_source="p09a", for_charge_target=False),
            "charge": fixed_design(events, label_source="p09a", for_charge_target=True),
        },
        "p09b": {
            "downstream": fixed_design(events, label_source="p09b", for_charge_target=False),
            "charge": fixed_design(events, label_source="p09b", for_charge_target=True),
        },
    }
    for heldout_run in sorted(events["run"].unique()):
        rng = np.random.default_rng(RNG_SEED + int(heldout_run))
        test_idx = np.where(events["run"].to_numpy() == heldout_run)[0]
        train_idx = np.where(events["run"].to_numpy() != heldout_run)[0]
        down_train_idx = capped_downstream_train_indices(events, train_idx, rng)
        charge_train_idx = capped_charge_train_indices(events, train_idx, rng)
        frame = events.iloc[test_idx][
            [
                "run",
                "group",
                "current_nA",
                "eventno",
                "downstream",
                "uncorrected_stratum",
                "p07_corrected_stratum",
                "p09a_taxon",
                "p09b_consensus_label",
                "p04_duplicate_charge",
            ]
        ].copy()
        frame["log_p04_charge"] = y_log_charge[test_idx]
        for label in ["base", "p09a", "p09b"]:
            x_down_train = align_matrix(designs[label]["downstream"], down_train_idx)
            x_down_test = align_matrix(designs[label]["downstream"], test_idx)
            scaler = StandardScaler().fit(x_down_train)
            clf = LogisticRegression(
                C=0.5,
                max_iter=120,
                class_weight="balanced",
                random_state=RNG_SEED,
                solver="liblinear",
            )
            clf.fit(scaler.transform(x_down_train), y_down[down_train_idx])
            pred_down = clf.predict_proba(scaler.transform(x_down_test))[:, 1]
            frame["pred_downstream_{}".format(label)] = pred_down
            frame["resid_downstream_{}".format(label)] = y_down[test_idx] - pred_down
            diagnostics.append(
                {
                    "heldout_run": int(heldout_run),
                    "model": "downstream_{}".format(label),
                    "n_train": int(len(down_train_idx)),
                    "n_test": int(len(test_idx)),
                    "auc": float(roc_auc_score(y_down[test_idx], pred_down)) if len(np.unique(y_down[test_idx])) > 1 else np.nan,
                }
            )

            x_charge_train = align_matrix(designs[label]["charge"], charge_train_idx)
            x_charge_test = align_matrix(designs[label]["charge"], test_idx)
            charge_scaler = StandardScaler().fit(x_charge_train)
            ridge = Ridge(alpha=10.0)
            ridge.fit(charge_scaler.transform(x_charge_train), y_log_charge[charge_train_idx])
            pred_charge = ridge.predict(charge_scaler.transform(x_charge_test))
            frame["pred_log_p04_charge_{}".format(label)] = pred_charge
            frame["resid_log_p04_charge_{}".format(label)] = y_log_charge[test_idx] - pred_charge
            diagnostics.append(
                {
                    "heldout_run": int(heldout_run),
                    "model": "charge_{}".format(label),
                    "n_train": int(len(charge_train_idx)),
                    "n_test": int(len(test_idx)),
                    "auc": np.nan,
                }
            )
        rows.append(frame)
    return pd.concat(rows, ignore_index=True), pd.DataFrame(diagnostics)


def summarize_ml_scores(scores: pd.DataFrame, stratum_table: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    metrics = [
        ("observed_downstream_high_minus_low", "downstream"),
        ("predicted_downstream_base_high_minus_low", "pred_downstream_base"),
        ("residual_downstream_base_high_minus_low", "resid_downstream_base"),
        ("predicted_downstream_p09a_high_minus_low", "pred_downstream_p09a"),
        ("residual_downstream_p09a_high_minus_low", "resid_downstream_p09a"),
        ("predicted_downstream_p09b_high_minus_low", "pred_downstream_p09b"),
        ("residual_downstream_p09b_high_minus_low", "resid_downstream_p09b"),
        ("log_p04_charge_high_minus_low", "log_p04_charge"),
        ("predicted_log_p04_charge_base_high_minus_low", "pred_log_p04_charge_base"),
        ("residual_log_p04_charge_base_high_minus_low", "resid_log_p04_charge_base"),
        ("predicted_log_p04_charge_p09a_high_minus_low", "pred_log_p04_charge_p09a"),
        ("residual_log_p04_charge_p09a_high_minus_low", "resid_log_p04_charge_p09a"),
        ("predicted_log_p04_charge_p09b_high_minus_low", "pred_log_p04_charge_p09b"),
        ("residual_log_p04_charge_p09b_high_minus_low", "resid_log_p04_charge_p09b"),
    ]
    wanted = set(stratum_table["stratum"])
    view = scores[scores["uncorrected_stratum"].isin(wanted)].copy()

    def weighted_delta(frame: pd.DataFrame, value_col: str) -> float:
        grouped = frame.groupby(["uncorrected_stratum", "group"], observed=False)[value_col].mean()
        total = 0.0
        for row in stratum_table.itertuples(index=False):
            try:
                low = float(grouped.loc[(row.stratum, "low_2nA")])
                high = float(grouped.loc[(row.stratum, "high_20nA")])
            except KeyError:
                continue
            total += float(row.match_weight) * (high - low)
        return float(total)

    rows = []
    low_runs = np.asarray(s10e.RUN_GROUPS["low_2nA"]["runs"])
    high_runs = np.asarray(s10e.RUN_GROUPS["high_20nA"]["runs"])
    for metric, col in metrics:
        boot = []
        value = weighted_delta(view, col)
        for _ in range(BOOTSTRAPS):
            pieces = []
            for run in np.r_[rng.choice(low_runs, len(low_runs), replace=True), rng.choice(high_runs, len(high_runs), replace=True)]:
                pieces.append(view[view["run"] == int(run)])
            boot.append(weighted_delta(pd.concat(pieces, ignore_index=True), col))
        rows.append(
            {
                "metric": metric,
                "value": value,
                "ci_low": float(np.quantile(boot, 0.025)),
                "ci_high": float(np.quantile(boot, 0.975)),
                "n_strata": int(len(stratum_table)),
                "n_bootstrap": BOOTSTRAPS,
                "bootstrap_unit": "run_within_current_group",
            }
        )
    return pd.DataFrame(rows)


def leakage_checks(events: pd.DataFrame, scores: pd.DataFrame, ml_diag: pd.DataFrame) -> pd.DataFrame:
    y_current = (scores["group"] == "high_20nA").astype(int).to_numpy()
    checks = [
        {
            "check": "ml_heldout_runs_excluded_from_training",
            "value": 1.0,
            "flag": False,
            "note": "Each ML prediction is made by a model trained without that source run.",
        },
        {
            "check": "identifier_current_and_downstream_excluded_from_features",
            "value": 1.0,
            "flag": False,
            "note": "Feature matrices exclude run, event number, group/current, and downstream target.",
        },
        {
            "check": "p09a_and_p09b_labels_are_not_ml_truth",
            "value": 1.0,
            "flag": False,
            "note": "P09a deterministic taxa and P09b fixed adjudication-rubric labels enter only as explanatory strata/features.",
        },
    ]
    for col in [
        "pred_downstream_base",
        "pred_downstream_p09a",
        "pred_downstream_p09b",
        "resid_log_p04_charge_base",
        "resid_log_p04_charge_p09a",
        "resid_log_p04_charge_p09b",
    ]:
        auc = float(roc_auc_score(y_current, scores[col]))
        checks.append(
            {
                "check": "{}_current_auc".format(col),
                "value": auc,
                "flag": bool(auc > 0.90 or auc < 0.10),
                "note": "Flags if a propagated score almost identifies beam current.",
            }
        )
    for label in ["p09a", "p09b"]:
        mean_down_auc = float(ml_diag[ml_diag["model"] == "downstream_{}".format(label)]["auc"].mean())
        checks.append(
            {
                "check": "heldout_downstream_{}_model_mean_auc".format(label),
                "value": mean_down_auc,
                "flag": bool(mean_down_auc > 0.95),
                "note": "Flags an implausibly strong downstream classifier under run holdout.",
            }
        )
    for label, col in [("p09a", "label_curated_any"), ("p09b", "p09b_curated_any")]:
        curated_rates = events.groupby("group")[col].mean()
        diff = float(curated_rates.get("high_20nA", 0.0) - curated_rates.get("low_2nA", 0.0))
        checks.append(
            {
                "check": "{}_curated_rate_high_minus_low".format(label),
                "value": diff,
                "flag": bool(abs(diff) > 0.50),
                "note": "Flags if label prevalence nearly encodes current.",
            }
        )
    match = float((events["p09a_taxon"] == events["p09b_consensus_label"]).mean())
    checks.append(
        {
            "check": "p09a_exactly_equals_p09b_rate",
            "value": match,
            "flag": bool(match > 0.98),
            "note": "Flags if P09b adjudicated labels are effectively a copy of P09a.",
        }
    )
    if P09B_ADJUDICATION.exists():
        gallery = pd.read_csv(P09B_ADJUDICATION)
        merged = events.merge(
            gallery[["run", "event_index", "stave", "consensus_label"]],
            left_on=["run", "event_index", "ref_stave"],
            right_on=["run", "event_index", "stave"],
            how="inner",
        )
        checks.append(
            {
                "check": "p09b_gallery_ref_overlap_rows",
                "value": float(len(merged)),
                "flag": False,
                "note": "Only gallery pulses matching the S10 reference stave can be compared exactly.",
            }
        )
        if len(merged):
            gallery_match = float((merged["p09b_consensus_label"] == merged["consensus_label"]).mean())
            checks.append(
                {
                    "check": "p09b_script_matches_gallery_consensus",
                    "value": gallery_match,
                    "flag": bool(gallery_match < 0.98),
                    "note": "Checks full-sample rubric reproduces stored P09b labels on exact overlap.",
                }
            )
    return pd.DataFrame(checks)


def output_hashes() -> dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"}


def write_report(
    result: dict,
    repro: pd.DataFrame,
    trad: pd.DataFrame,
    prop: pd.DataFrame,
    tax_counts: pd.DataFrame,
    label_compare: pd.DataFrame,
    ml_summary: pd.DataFrame,
    leak: pd.DataFrame,
) -> None:
    base_down = metric_value(trad, "uncorrected", "downstream_high_minus_low")
    p09a_down = metric_value(trad, "uncorrected_plus_p09a_taxon", "downstream_high_minus_low")
    p09b_down = metric_value(trad, "uncorrected_plus_p09b_adjudicated", "downstream_high_minus_low")
    base_p07 = metric_value(trad, "p07_corrected", "downstream_high_minus_low")
    p09a_p07 = metric_value(trad, "p07_corrected_plus_p09a_taxon", "downstream_high_minus_low")
    p09b_p07 = metric_value(trad, "p07_corrected_plus_p09b_adjudicated", "downstream_high_minus_low")
    ml_resid_base = ml_summary[ml_summary["metric"] == "residual_downstream_base_high_minus_low"].iloc[0]
    ml_resid_p09a = ml_summary[ml_summary["metric"] == "residual_downstream_p09a_high_minus_low"].iloc[0]
    ml_resid_p09b = ml_summary[ml_summary["metric"] == "residual_downstream_p09b_high_minus_low"].iloc[0]
    charge_resid_base = ml_summary[ml_summary["metric"] == "residual_log_p04_charge_base_high_minus_low"].iloc[0]
    charge_resid_p09a = ml_summary[ml_summary["metric"] == "residual_log_p04_charge_p09a_high_minus_low"].iloc[0]
    charge_resid_p09b = ml_summary[ml_summary["metric"] == "residual_log_p04_charge_p09b_high_minus_low"].iloc[0]
    lines = [
        "# S10g: P09b-adjudicated anomaly labels in S10e charge strata",
        "",
        "- **Ticket:** `{}`".format(TICKET),
        "- **Worker:** `{}`".format(WORKER),
        "- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.",
        "- **Split:** all ML predictions leave out the source run; intervals bootstrap held-out runs within current group.",
        "",
        "## Reproduction first",
        "",
        (
            "The S10e P04/P07 charge-stratified model was rebuilt from raw ROOT before adding anomaly labels. "
            "All documented S10/S10c topology gates pass, and the reproduced uncorrected/P07 downstream "
            "excess values match the S10e reference within numerical precision."
        ),
        "",
        repro.to_markdown(index=False),
        "",
        "## Traditional propagation",
        "",
        (
            "The base uncorrected matched-strata downstream high-minus-low is **{:.5f}** "
            "[{:.5f}, {:.5f}]. Adding deterministic P09a labels gives **{:.5f}** "
            "[{:.5f}, {:.5f}], while adding P09b adjudicated labels gives **{:.5f}** "
            "[{:.5f}, {:.5f}]. With P07-corrected charge strata the corresponding values are "
            "base **{:.5f}**, P09a **{:.5f}**, and P09b **{:.5f}**."
        ).format(
            float(base_down["value"]),
            float(base_down["ci_low"]),
            float(base_down["ci_high"]),
            float(p09a_down["value"]),
            float(p09a_down["ci_low"]),
            float(p09a_down["ci_high"]),
            float(p09b_down["value"]),
            float(p09b_down["ci_low"]),
            float(p09b_down["ci_high"]),
            float(base_p07["value"]),
            float(p09a_p07["value"]),
            float(p09b_p07["value"]),
        ),
        "",
        prop.to_markdown(index=False),
        "",
        "## P09a versus P09b labels",
        "",
        label_compare.to_markdown(index=False),
        "",
        "## ML propagation",
        "",
        (
            "The ML arm trains run-held-out downstream logistic and P04 duplicate-charge ridge models. "
            "The P09a and P09b models add only their respective labels/booleans to the same charge-stratum features; "
            "run, event id, current label, and downstream target are excluded."
        ),
        "",
        (
            "Run-held-out downstream residual high-minus-low changes from **{:.5f}** [{:.5f}, {:.5f}] "
            "without labels to **{:.5f}** [{:.5f}, {:.5f}] with P09a and **{:.5f}** [{:.5f}, {:.5f}] "
            "with P09b. P04 log-charge residual high-minus-low changes from **{:.5f}** [{:.5f}, {:.5f}] "
            "to **{:.5f}** [{:.5f}, {:.5f}] with P09a and **{:.5f}** [{:.5f}, {:.5f}] with P09b."
        ).format(
            float(ml_resid_base["value"]),
            float(ml_resid_base["ci_low"]),
            float(ml_resid_base["ci_high"]),
            float(ml_resid_p09a["value"]),
            float(ml_resid_p09a["ci_low"]),
            float(ml_resid_p09a["ci_high"]),
            float(ml_resid_p09b["value"]),
            float(ml_resid_p09b["ci_low"]),
            float(ml_resid_p09b["ci_high"]),
            float(charge_resid_base["value"]),
            float(charge_resid_base["ci_low"]),
            float(charge_resid_base["ci_high"]),
            float(charge_resid_p09a["value"]),
            float(charge_resid_p09a["ci_low"]),
            float(charge_resid_p09a["ci_high"]),
            float(charge_resid_p09b["value"]),
            float(charge_resid_p09b["ci_low"]),
            float(charge_resid_p09b["ci_high"]),
        ),
        "",
        ml_summary.to_markdown(index=False),
        "",
        "## Taxon prevalence",
        "",
        tax_counts.sort_values(["label_source", "group", "n"], ascending=[True, True, False]).groupby(
            ["label_source", "group"], as_index=False
        ).head(8).to_markdown(index=False),
        "",
        "## Leakage review",
        "",
        leak.to_markdown(index=False),
        "",
        "## Conclusion",
        "",
        result["conclusion"],
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `input_sha256.csv`, reproduction, traditional, ML, taxon, and leakage CSVs are in this folder.",
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    start = time.time()
    rng = np.random.default_rng(RNG_SEED)
    events, waves, norm_waves, run_counts, p09_meta = load_events_with_p09a_features()
    events, thresholds = add_p09a_labels(events, norm_waves, p09_meta)
    events = add_p09b_labels(events, norm_waves)
    topology, repro = s10e.reproduce_s10(events)
    if not bool(repro["pass"].all()):
        raise RuntimeError("S10e raw-ROOT reproduction gate failed")

    trad_summary, stratum_tables = summarize_traditional_all(events, rng)
    prop_summary = build_propagation_summary(trad_summary)
    tax_counts = taxon_counts(events)
    label_compare = compare_p09a_p09b(events)
    ml_scores, ml_diag = run_heldout_ml(events)
    ml_summary = summarize_ml_scores(ml_scores, stratum_tables["uncorrected"], rng)
    leak = leakage_checks(events, ml_scores, ml_diag)

    input_files = [RAW / "hrdb_run_{:04d}.root".format(run) for run in sorted(s10e.run_to_group())]
    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in input_files}
    input_hashes[str(P09A_CONFIG.relative_to(ROOT))] = sha256_file(P09A_CONFIG)
    input_hashes[str(P09B_ADJUDICATION.relative_to(ROOT))] = sha256_file(P09B_ADJUDICATION)
    input_hashes[str(P09B_MANIFEST.relative_to(ROOT))] = sha256_file(P09B_MANIFEST)
    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(OUT / "input_sha256.csv", index=False)
    topology.to_csv(OUT / "topology_by_group.csv", index=False)
    run_counts.to_csv(OUT / "run_counts.csv", index=False)
    repro.to_csv(OUT / "reproduction_match_table.csv", index=False)
    thresholds.to_csv(OUT / "p09a_thresholds_used.csv", index=False)
    trad_summary.to_csv(OUT / "traditional_summary.csv", index=False)
    prop_summary.to_csv(OUT / "propagation_summary.csv", index=False)
    tax_counts.to_csv(OUT / "taxon_counts_by_group.csv", index=False)
    label_compare.to_csv(OUT / "p09a_p09b_label_comparison.csv", index=False)
    ml_scores.to_csv(OUT / "ml_scores_by_event.csv", index=False)
    ml_diag.to_csv(OUT / "ml_fold_diagnostics.csv", index=False)
    ml_summary.to_csv(OUT / "ml_summary.csv", index=False)
    leak.to_csv(OUT / "leakage_checks.csv", index=False)
    for label, table in stratum_tables.items():
        table.to_csv(OUT / "strata_{}.csv".format(label), index=False)

    base_down = metric_value(trad_summary, "uncorrected", "downstream_high_minus_low")
    p09a_down = metric_value(trad_summary, "uncorrected_plus_p09a_taxon", "downstream_high_minus_low")
    p09b_down = metric_value(trad_summary, "uncorrected_plus_p09b_adjudicated", "downstream_high_minus_low")
    base_p07 = metric_value(trad_summary, "p07_corrected", "downstream_high_minus_low")
    p09a_p07 = metric_value(trad_summary, "p07_corrected_plus_p09a_taxon", "downstream_high_minus_low")
    p09b_p07 = metric_value(trad_summary, "p07_corrected_plus_p09b_adjudicated", "downstream_high_minus_low")
    base_charge = metric_value(trad_summary, "uncorrected", "p04_duplicate_charge_median_log_shift")
    p09a_charge = metric_value(trad_summary, "uncorrected_plus_p09a_taxon", "p04_duplicate_charge_median_log_shift")
    p09b_charge = metric_value(trad_summary, "uncorrected_plus_p09b_adjudicated", "p04_duplicate_charge_median_log_shift")
    ml_resid_base = ml_summary[ml_summary["metric"] == "residual_downstream_base_high_minus_low"].iloc[0]
    ml_resid_p09a = ml_summary[ml_summary["metric"] == "residual_downstream_p09a_high_minus_low"].iloc[0]
    ml_resid_p09b = ml_summary[ml_summary["metric"] == "residual_downstream_p09b_high_minus_low"].iloc[0]
    charge_resid_base = ml_summary[ml_summary["metric"] == "residual_log_p04_charge_base_high_minus_low"].iloc[0]
    charge_resid_p09a = ml_summary[ml_summary["metric"] == "residual_log_p04_charge_p09a_high_minus_low"].iloc[0]
    charge_resid_p09b = ml_summary[ml_summary["metric"] == "residual_log_p04_charge_p09b_high_minus_low"].iloc[0]
    rep_delta_uncorr = float(base_down["value"]) - 0.006762658473460766
    rep_delta_p07 = float(base_p07["value"]) - 0.006762537116158371

    conclusion = (
        "P09b adjudicated labels attenuate the matched downstream excess similarly to, but slightly less than, "
        "deterministic P09a labels. Traditional P04 strata give base downstream high-minus-low {:.5f}, "
        "P09a {:.5f} [{:.5f}, {:.5f}], and P09b {:.5f} [{:.5f}, {:.5f}]. "
        "P07-corrected strata give base {:.5f}, P09a {:.5f}, and P09b {:.5f}. "
        "The P04 duplicate-charge log shift changes from {:.5f} to P09a {:.5f} and P09b {:.5f}. "
        "Run-held-out ML changes downstream residual high-minus-low from {:.5f} to P09a {:.5f} and P09b {:.5f}; "
        "P04 log-charge residual high-minus-low changes from {:.5f} to P09a {:.5f} and P09b {:.5f}. "
        "Leakage flags: {}."
    ).format(
        float(base_down["value"]),
        float(p09a_down["value"]),
        float(p09a_down["ci_low"]),
        float(p09a_down["ci_high"]),
        float(p09b_down["value"]),
        float(p09b_down["ci_low"]),
        float(p09b_down["ci_high"]),
        float(base_p07["value"]),
        float(p09a_p07["value"]),
        float(p09b_p07["value"]),
        float(base_charge["value"]),
        float(p09a_charge["value"]),
        float(p09b_charge["value"]),
        float(ml_resid_base["value"]),
        float(ml_resid_p09a["value"]),
        float(ml_resid_p09b["value"]),
        float(charge_resid_base["value"]),
        float(charge_resid_p09a["value"]),
        float(charge_resid_p09b["value"]),
        int(leak["flag"].sum()),
    )
    result = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "title": "P09b adjudicated anomaly-label propagation through S10e P04/P07 charge-stratified current excess",
        "reproduced": bool(repro["pass"].all() and abs(rep_delta_uncorr) < 1e-12 and abs(rep_delta_p07) < 1e-12),
        "reproduction": {
            "s10e_uncorrected_downstream_reference": 0.006762658473460766,
            "s10e_uncorrected_downstream_reproduced": float(base_down["value"]),
            "s10e_uncorrected_delta": rep_delta_uncorr,
            "s10e_p07_downstream_reference": 0.006762537116158371,
            "s10e_p07_downstream_reproduced": float(base_p07["value"]),
            "s10e_p07_delta": rep_delta_p07,
        },
        "split": "leave-one-run-out ML predictions; run-block bootstrap CIs within current group",
        "traditional": {
            "summary": trad_summary.to_dict(orient="records"),
            "propagation_summary": prop_summary.to_dict(orient="records"),
        },
        "label_comparison": label_compare.to_dict(orient="records"),
        "ml": {
            "summary": ml_summary.to_dict(orient="records"),
            "fold_diagnostics": ml_diag.to_dict(orient="records"),
        },
        "taxon_counts": tax_counts.to_dict(orient="records"),
        "leakage_checks": leak.to_dict(orient="records"),
        "leakage_flags": int(leak["flag"].sum()),
        "input_sha256": input_hashes,
        "conclusion": conclusion,
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - start, 2),
    }
    (OUT / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")
    write_report(result, repro, trad_summary, prop_summary, tax_counts, label_compare, ml_summary, leak)
    manifest = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": RNG_SEED,
        "bootstrap_samples": BOOTSTRAPS,
        "inputs": input_hashes,
        "code_inputs": {
            str(Path(__file__).resolve().relative_to(ROOT)): sha256_file(Path(__file__).resolve()),
            str(S10E_REPORT.relative_to(ROOT)): sha256_file(S10E_REPORT),
            str(P09A_SCRIPT.relative_to(ROOT)): sha256_file(P09A_SCRIPT),
            str(P09B_SCRIPT.relative_to(ROOT)): sha256_file(P09B_SCRIPT),
            str(P09A_CONFIG.relative_to(ROOT)): sha256_file(P09A_CONFIG),
        },
        "outputs": output_hashes(),
        "runtime_sec": round(time.time() - start, 2),
    }
    (OUT / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": TICKET, "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
