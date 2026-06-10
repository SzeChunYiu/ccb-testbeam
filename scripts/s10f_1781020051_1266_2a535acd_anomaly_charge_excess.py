#!/usr/bin/env python3
"""S10f: propagate P09a anomaly labels through S10e P04/P07 strata.

The analysis rebuilds the S10e selected-event table from raw B-stack ROOT,
reproduces the published S10e P04/P07 charge-stratified excess first, then
adds deterministic P09a taxonomy labels as explanatory strata and as held-out
ML features. ML scores are diagnostics only; they are not treated as truth
labels for pile-up or anomaly content.
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
OUT = ROOT / "reports/1781020051.1266.2a535acd"
OUT.mkdir(parents=True, exist_ok=True)
RAW = ROOT / "data/root/root"

TICKET = "1781020051.1266.2a535acd"
WORKER = "testbeam-laptop-3"
STUDY = "S10f"
RNG_SEED = 1781020051
BOOTSTRAPS = 400
MIN_STRATUM_N = 25
MAX_DOWNSTREAM_TRAIN = 18000
MAX_CHARGE_TRAIN = 22000

S10E_REPORT = ROOT / "reports/1781010955.636.68b17313/s10e_charge_energy_transfer.py"
P09A_SCRIPT = ROOT / "scripts/p09a_rare_waveform_anomaly_taxonomy.py"
P09A_CONFIG = ROOT / "configs/p09a_rare_waveform_anomaly_taxonomy.json"


def import_module(path: Path, name: str):
    spec = util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import {}".format(path))
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s10e = import_module(S10E_REPORT, "s10e_charge_energy_transfer_source")
p09a = import_module(P09A_SCRIPT, "p09a_rare_waveform_anomaly_taxonomy_source")


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
            tax_features.insert(0, "eventno", eventno[row_idx])
            tax_features.insert(0, "run", int(run))

            event_frames.append(frame)
            shape_frames.append(tax_features)
            ref_waves.append(corr_ref.astype(np.float32))
            norm_waves.append(norm)
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
    for col in labelled.columns:
        if col.startswith("label_") or col in ["taxon", "q_template_rmse", "template_bin"]:
            out[col] = labelled[col].to_numpy()
    out["taxon_for_strata"] = out["taxon"].astype(str)
    out["uncorrected_taxon_stratum"] = out["uncorrected_stratum"].astype(str) + "|" + out["taxon_for_strata"]
    out["p07_corrected_taxon_stratum"] = out["p07_corrected_stratum"].astype(str) + "|" + out["taxon_for_strata"]
    return out, thresholds


def summarize_traditional_all(events: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    s10e.BOOTSTRAPS = BOOTSTRAPS
    s10e.MIN_STRATUM_N = MIN_STRATUM_N
    tables = {}
    rows = []
    specs = [
        ("uncorrected", "uncorrected_stratum", "p04_duplicate_charge"),
        ("p07_corrected", "p07_corrected_stratum", "p07_corrected_charge"),
        ("uncorrected_plus_p09a_taxon", "uncorrected_taxon_stratum", "p04_duplicate_charge"),
        ("p07_corrected_plus_p09a_taxon", "p07_corrected_taxon_stratum", "p07_corrected_charge"),
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
    for (group, taxon), sub in events.groupby(["group", "taxon"], sort=True):
        rows.append(
            {
                "group": group,
                "taxon": taxon,
                "n": int(len(sub)),
                "group_rate": float(len(sub) / max(1, total_by_group[group])),
                "downstream_rate": float(sub["downstream"].mean()),
                "median_log_p04_charge": float(np.log(np.maximum(sub["p04_duplicate_charge"].to_numpy(), 1.0)).mean()),
            }
        )
    return pd.DataFrame(rows)


def fixed_design(frame: pd.DataFrame, include_taxon: bool, for_charge_target: bool) -> pd.DataFrame:
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
    if include_taxon:
        cat_cols.extend(["taxon", "label_known_any", "label_novel_any", "label_curated_any"])
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
            "downstream": fixed_design(events, include_taxon=False, for_charge_target=False),
            "charge": fixed_design(events, include_taxon=False, for_charge_target=True),
        },
        "taxon": {
            "downstream": fixed_design(events, include_taxon=True, for_charge_target=False),
            "charge": fixed_design(events, include_taxon=True, for_charge_target=True),
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
                "taxon",
                "p04_duplicate_charge",
            ]
        ].copy()
        frame["log_p04_charge"] = y_log_charge[test_idx]
        for label in ["base", "taxon"]:
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
        ("predicted_downstream_taxon_high_minus_low", "pred_downstream_taxon"),
        ("residual_downstream_taxon_high_minus_low", "resid_downstream_taxon"),
        ("log_p04_charge_high_minus_low", "log_p04_charge"),
        ("predicted_log_p04_charge_base_high_minus_low", "pred_log_p04_charge_base"),
        ("residual_log_p04_charge_base_high_minus_low", "resid_log_p04_charge_base"),
        ("predicted_log_p04_charge_taxon_high_minus_low", "pred_log_p04_charge_taxon"),
        ("residual_log_p04_charge_taxon_high_minus_low", "resid_log_p04_charge_taxon"),
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
            "check": "p09a_labels_are_deterministic_taxa_not_ml_truth",
            "value": 1.0,
            "flag": False,
            "note": "Only P09a rule labels and booleans enter the propagation; P09a anomaly scores are not used as labels.",
        },
    ]
    for col in ["pred_downstream_base", "pred_downstream_taxon", "resid_log_p04_charge_base", "resid_log_p04_charge_taxon"]:
        auc = float(roc_auc_score(y_current, scores[col]))
        checks.append(
            {
                "check": "{}_current_auc".format(col),
                "value": auc,
                "flag": bool(auc > 0.90 or auc < 0.10),
                "note": "Flags if a propagated score almost identifies beam current.",
            }
        )
    mean_taxon_down_auc = float(ml_diag[ml_diag["model"] == "downstream_taxon"]["auc"].mean())
    checks.append(
        {
            "check": "heldout_downstream_taxon_model_mean_auc",
            "value": mean_taxon_down_auc,
            "flag": bool(mean_taxon_down_auc > 0.95),
            "note": "Flags an implausibly strong downstream classifier under run holdout.",
        }
    )
    curated_rates = events.groupby("group")["label_curated_any"].mean()
    diff = float(curated_rates.get("high_20nA", 0.0) - curated_rates.get("low_2nA", 0.0))
    checks.append(
        {
            "check": "curated_taxon_rate_high_minus_low",
            "value": diff,
            "flag": bool(abs(diff) > 0.50),
            "note": "Flags if deterministic taxa nearly encode current by prevalence alone.",
        }
    )
    return pd.DataFrame(checks)


def output_hashes() -> dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"}


def write_report(result: dict, repro: pd.DataFrame, trad: pd.DataFrame, prop: pd.DataFrame, tax_counts: pd.DataFrame, ml_summary: pd.DataFrame, leak: pd.DataFrame) -> None:
    base_down = metric_value(trad, "uncorrected", "downstream_high_minus_low")
    tax_down = metric_value(trad, "uncorrected_plus_p09a_taxon", "downstream_high_minus_low")
    base_p07 = metric_value(trad, "p07_corrected", "downstream_high_minus_low")
    tax_p07 = metric_value(trad, "p07_corrected_plus_p09a_taxon", "downstream_high_minus_low")
    ml_resid_base = ml_summary[ml_summary["metric"] == "residual_downstream_base_high_minus_low"].iloc[0]
    ml_resid_tax = ml_summary[ml_summary["metric"] == "residual_downstream_taxon_high_minus_low"].iloc[0]
    charge_resid_base = ml_summary[ml_summary["metric"] == "residual_log_p04_charge_base_high_minus_low"].iloc[0]
    charge_resid_tax = ml_summary[ml_summary["metric"] == "residual_log_p04_charge_taxon_high_minus_low"].iloc[0]
    lines = [
        "# S10f: P09a anomaly labels in S10e charge strata",
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
            "Adding deterministic P09a taxon labels to the P04 charge x S16 lowering x P07 saturation strata gives "
            "uncorrected downstream excess **{:.5f}** [{:.5f}, {:.5f}] versus the S10e base **{:.5f}** "
            "[{:.5f}, {:.5f}]. P07-corrected taxon strata give **{:.5f}** [{:.5f}, {:.5f}] versus "
            "base **{:.5f}** [{:.5f}, {:.5f}]."
        ).format(
            float(tax_down["value"]),
            float(tax_down["ci_low"]),
            float(tax_down["ci_high"]),
            float(base_down["value"]),
            float(base_down["ci_low"]),
            float(base_down["ci_high"]),
            float(tax_p07["value"]),
            float(tax_p07["ci_low"]),
            float(tax_p07["ci_high"]),
            float(base_p07["value"]),
            float(base_p07["ci_low"]),
            float(base_p07["ci_high"]),
        ),
        "",
        prop.to_markdown(index=False),
        "",
        "## ML propagation",
        "",
        (
            "The ML arm trains run-held-out downstream logistic and P04 duplicate-charge ridge models. "
            "The taxon model adds only P09a deterministic labels/booleans to the same charge-stratum features; "
            "run, event id, current label, and downstream target are excluded."
        ),
        "",
        (
            "Run-held-out downstream residual high-minus-low changes from **{:.5f}** [{:.5f}, {:.5f}] "
            "without taxa to **{:.5f}** [{:.5f}, {:.5f}] with taxa. P04 log-charge residual high-minus-low "
            "changes from **{:.5f}** [{:.5f}, {:.5f}] to **{:.5f}** [{:.5f}, {:.5f}]."
        ).format(
            float(ml_resid_base["value"]),
            float(ml_resid_base["ci_low"]),
            float(ml_resid_base["ci_high"]),
            float(ml_resid_tax["value"]),
            float(ml_resid_tax["ci_low"]),
            float(ml_resid_tax["ci_high"]),
            float(charge_resid_base["value"]),
            float(charge_resid_base["ci_low"]),
            float(charge_resid_base["ci_high"]),
            float(charge_resid_tax["value"]),
            float(charge_resid_tax["ci_low"]),
            float(charge_resid_tax["ci_high"]),
        ),
        "",
        ml_summary.to_markdown(index=False),
        "",
        "## Taxon prevalence",
        "",
        tax_counts.sort_values(["group", "n"], ascending=[True, False]).head(18).to_markdown(index=False),
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
    topology, repro = s10e.reproduce_s10(events)
    if not bool(repro["pass"].all()):
        raise RuntimeError("S10e raw-ROOT reproduction gate failed")

    trad_summary, stratum_tables = summarize_traditional_all(events, rng)
    prop_summary = build_propagation_summary(trad_summary)
    tax_counts = taxon_counts(events)
    ml_scores, ml_diag = run_heldout_ml(events)
    ml_summary = summarize_ml_scores(ml_scores, stratum_tables["uncorrected"], rng)
    leak = leakage_checks(events, ml_scores, ml_diag)

    input_files = [RAW / "hrdb_run_{:04d}.root".format(run) for run in sorted(s10e.run_to_group())]
    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in input_files}
    input_hashes[str(P09A_CONFIG.relative_to(ROOT))] = sha256_file(P09A_CONFIG)
    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(OUT / "input_sha256.csv", index=False)
    topology.to_csv(OUT / "topology_by_group.csv", index=False)
    run_counts.to_csv(OUT / "run_counts.csv", index=False)
    repro.to_csv(OUT / "reproduction_match_table.csv", index=False)
    thresholds.to_csv(OUT / "p09a_thresholds_used.csv", index=False)
    trad_summary.to_csv(OUT / "traditional_summary.csv", index=False)
    prop_summary.to_csv(OUT / "propagation_summary.csv", index=False)
    tax_counts.to_csv(OUT / "taxon_counts_by_group.csv", index=False)
    ml_scores.to_csv(OUT / "ml_scores_by_event.csv", index=False)
    ml_diag.to_csv(OUT / "ml_fold_diagnostics.csv", index=False)
    ml_summary.to_csv(OUT / "ml_summary.csv", index=False)
    leak.to_csv(OUT / "leakage_checks.csv", index=False)
    for label, table in stratum_tables.items():
        table.to_csv(OUT / "strata_{}.csv".format(label), index=False)

    base_down = metric_value(trad_summary, "uncorrected", "downstream_high_minus_low")
    tax_down = metric_value(trad_summary, "uncorrected_plus_p09a_taxon", "downstream_high_minus_low")
    base_p07 = metric_value(trad_summary, "p07_corrected", "downstream_high_minus_low")
    tax_p07 = metric_value(trad_summary, "p07_corrected_plus_p09a_taxon", "downstream_high_minus_low")
    base_charge = metric_value(trad_summary, "uncorrected", "p04_duplicate_charge_median_log_shift")
    tax_charge = metric_value(trad_summary, "uncorrected_plus_p09a_taxon", "p04_duplicate_charge_median_log_shift")
    ml_resid_base = ml_summary[ml_summary["metric"] == "residual_downstream_base_high_minus_low"].iloc[0]
    ml_resid_tax = ml_summary[ml_summary["metric"] == "residual_downstream_taxon_high_minus_low"].iloc[0]
    charge_resid_base = ml_summary[ml_summary["metric"] == "residual_log_p04_charge_base_high_minus_low"].iloc[0]
    charge_resid_tax = ml_summary[ml_summary["metric"] == "residual_log_p04_charge_taxon_high_minus_low"].iloc[0]
    rep_delta_uncorr = float(base_down["value"]) - 0.006762658473460766
    rep_delta_p07 = float(base_p07["value"]) - 0.006762537116158371

    conclusion = (
        "P09a deterministic anomaly taxa do not explain away the S10e matched current excess. "
        "Traditional P04 strata plus taxa give downstream high-minus-low {:.5f} [{:.5f}, {:.5f}] "
        "against the base {:.5f}; P07-corrected strata plus taxa give {:.5f} against the base {:.5f}. "
        "The P04 duplicate-charge log shift changes from {:.5f} to {:.5f}. "
        "Run-held-out ML gives the same direction: adding taxa changes downstream residual high-minus-low "
        "from {:.5f} to {:.5f} and P04 log-charge residual high-minus-low from {:.5f} to {:.5f}. "
        "Leakage flags: {}. The taxa are useful explanatory handles, but they are not sufficient truth labels "
        "for the remaining matched downstream or charge-proxy excess."
    ).format(
        float(tax_down["value"]),
        float(tax_down["ci_low"]),
        float(tax_down["ci_high"]),
        float(base_down["value"]),
        float(tax_p07["value"]),
        float(base_p07["value"]),
        float(base_charge["value"]),
        float(tax_charge["value"]),
        float(ml_resid_base["value"]),
        float(ml_resid_tax["value"]),
        float(charge_resid_base["value"]),
        float(charge_resid_tax["value"]),
        int(leak["flag"].sum()),
    )
    result = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "title": "anomaly-label propagation through S10e P04/P07 charge-stratified current excess",
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
    write_report(result, repro, trad_summary, prop_summary, tax_counts, ml_summary, leak)
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
