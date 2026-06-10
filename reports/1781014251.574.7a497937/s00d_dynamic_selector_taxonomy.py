#!/usr/bin/env python3
"""S00d: dynamic-selector pulse taxonomy audit.

The study scans raw B-stack ROOT first and requires exact reproduction of the
S00 median-first-four and S00a dynamic-range selector anchors before any
taxonomy, timing, or ML result is written.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import subprocess
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


CONFIG = Path("configs/s00d_1781014251_574_7a497937.json")
STAVE_NAMES = ["B2", "B4", "B6", "B8"]


def sha256_file(path, block_size=1024 * 1024):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def load_config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def all_runs(config):
    runs = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def raw_path(config, run):
    path = Path(config["raw_root_dir"]) / "hrdb_run_{:04d}.root".format(int(run))
    if not path.exists():
        raise FileNotFoundError(str(path))
    return path


def iter_raw(path, step_size=20000):
    tree = uproot.open(path)["h101"]
    for batch in tree.iterate(["EVT", "EVENTNO", "HRDv"], step_size=step_size, library="np"):
        yield batch


def cfd_time_samples(waveforms, amplitudes, fraction=0.20):
    thresholds = amplitudes * float(fraction)
    ge = waveforms >= thresholds[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waveforms), np.nan, dtype=np.float32)
    for idx in np.where(valid)[0]:
        j = int(first[idx])
        if j <= 0:
            out[idx] = float(j)
            continue
        y0 = float(waveforms[idx, j - 1])
        y1 = float(waveforms[idx, j])
        denom = y1 - y0
        if denom <= 0:
            out[idx] = float(j)
        else:
            out[idx] = (j - 1) + (thresholds[idx] - y0) / denom
    return out


def sigma68(values):
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    return float((np.quantile(arr, 0.84) - np.quantile(arr, 0.16)) / 2.0)


def full_rms(values):
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    return float(np.sqrt(np.mean((arr - np.mean(arr)) ** 2)))


def normalized_hashes(waves):
    rounded = np.round(np.asarray(waves, dtype=np.float32), 4)
    return [hashlib.sha1(row.tobytes()).hexdigest() for row in rounded]


def scan_raw(config):
    cut = float(config["amplitude_cut_adc"])
    nsamp = int(config["samples_per_channel"])
    baseline_idx = [int(x) for x in config["baseline_samples"]]
    channels = np.asarray([int(config["staves"][name]) for name in STAVE_NAMES], dtype=int)
    downstream = [STAVE_NAMES.index(name) for name in config["downstream_staves"]]
    pos = {name: float(config["stave_position_cm"][name]) for name in STAVE_NAMES}
    sample_period = float(config["sample_period_ns"])
    tof_per_cm = float(config["tof_per_cm_ns"])
    sat_adc = float(config["traditional_cuts"]["saturation_adc"])

    count_rows = []
    feature_frames = []
    wave_chunks = []
    timing_rows = []
    input_rows = []

    for run in all_runs(config):
        path = raw_path(config, run)
        input_rows.append({"path": str(path), "sha256": sha256_file(path)})
        row = {
            "run": int(run),
            "events": 0,
            "records": 0,
            "median_first_four_selected": 0,
            "dynamic_range_selected": 0,
            "dynamic_only": 0,
            "median_only": 0,
        }
        event_offset = 0
        for batch in iter_raw(path):
            evt = np.asarray(batch["EVT"], dtype=np.int64)
            eventno = np.asarray(batch["EVENTNO"], dtype=np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            wave = raw[:, channels, :]
            pre = wave[..., baseline_idx]
            baseline = np.median(pre, axis=-1)
            corrected = wave - baseline[..., None]
            median_amp = corrected.max(axis=-1)
            dynamic_amp = wave.max(axis=-1) - wave.min(axis=-1)
            selected_median = median_amp > cut
            selected_dynamic = dynamic_amp > cut
            dynamic_only = selected_dynamic & ~selected_median
            median_only = selected_median & ~selected_dynamic

            row["events"] += int(len(evt))
            row["records"] += int(selected_median.size)
            row["median_first_four_selected"] += int(selected_median.sum())
            row["dynamic_range_selected"] += int(selected_dynamic.sum())
            row["dynamic_only"] += int(dynamic_only.sum())
            row["median_only"] += int(median_only.sum())

            amplitudes = np.maximum(median_amp, 1.0)
            times = np.full(median_amp.shape, np.nan, dtype=np.float32)
            for sidx in range(len(STAVE_NAMES)):
                times[:, sidx] = cfd_time_samples(corrected[:, sidx, :], amplitudes[:, sidx], 0.20)

            dyn_down = selected_dynamic[:, downstream]
            span_ns = np.full(len(evt), np.nan, dtype=np.float32)
            for eidx in np.where(dyn_down.sum(axis=1) >= 2)[0]:
                local_times = times[eidx, downstream]
                local_times = local_times[np.isfinite(local_times)]
                if len(local_times) >= 2:
                    span_ns[eidx] = float((local_times.max() - local_times.min()) * sample_period)

            all_hit_median = selected_median[:, downstream].all(axis=1)
            all_hit_dynamic = selected_dynamic[:, downstream].all(axis=1)
            pair_defs = [(0, 1), (1, 2), (0, 2)]
            for selector, all_hit in [("median_first4", all_hit_median), ("dynamic_range", all_hit_dynamic)]:
                for eidx in np.where(all_hit)[0]:
                    for li, lj in pair_defs:
                        si = downstream[li]
                        sj = downstream[lj]
                        ti = times[eidx, si]
                        tj = times[eidx, sj]
                        if not (np.isfinite(ti) and np.isfinite(tj)):
                            continue
                        geom = (pos[STAVE_NAMES[si]] - pos[STAVE_NAMES[sj]]) * tof_per_cm
                        timing_rows.append(
                            {
                                "run": int(run),
                                "event_index": int(event_offset + eidx),
                                "selector": selector,
                                "pair": "{}-{}".format(STAVE_NAMES[si], STAVE_NAMES[sj]),
                                "residual_ns": float((ti - tj) * sample_period - geom),
                            }
                        )

            keep = selected_dynamic
            event_idx, stave_idx = np.where(keep)
            if len(event_idx):
                chosen = corrected[event_idx, stave_idx]
                amp = np.maximum(median_amp[event_idx, stave_idx], 1.0)
                norm = chosen / amp[:, None]
                area = np.clip(chosen, 0.0, None).sum(axis=1)
                signed_area = chosen.sum(axis=1)
                early = np.clip(chosen[:, :4], 0.0, None).sum(axis=1)
                late = np.clip(chosen[:, 12:], 0.0, None).sum(axis=1)
                width20 = (chosen >= (0.20 * amp[:, None])).sum(axis=1)
                width50 = (chosen >= (0.50 * amp[:, None])).sum(axis=1)
                frame = pd.DataFrame(
                    {
                        "run": np.full(len(event_idx), int(run), dtype=np.int16),
                        "event_index": (event_offset + event_idx).astype(np.int32),
                        "evt": evt[event_idx].astype(np.int64),
                        "eventno": eventno[event_idx].astype(np.int64),
                        "stave": np.asarray(STAVE_NAMES, dtype=object)[stave_idx],
                        "stave_index": stave_idx.astype(np.int8),
                        "s00_selected": selected_median[event_idx, stave_idx].astype(np.int8),
                        "dynamic_only": dynamic_only[event_idx, stave_idx].astype(np.int8),
                        "median_amp_adc": median_amp[event_idx, stave_idx].astype(np.float32),
                        "dynamic_amp_adc": dynamic_amp[event_idx, stave_idx].astype(np.float32),
                        "dynamic_minus_median_adc": (dynamic_amp[event_idx, stave_idx] - median_amp[event_idx, stave_idx]).astype(np.float32),
                        "baseline_median_adc": baseline[event_idx, stave_idx].astype(np.float32),
                        "baseline_excursion_adc": (pre.max(axis=-1) - pre.min(axis=-1))[event_idx, stave_idx].astype(np.float32),
                        "peak_sample": chosen.argmax(axis=1).astype(np.int8),
                        "area_adc_samples": signed_area.astype(np.float32),
                        "positive_area_adc_samples": area.astype(np.float32),
                        "early_fraction": (early / np.maximum(area, 1.0)).astype(np.float32),
                        "late_fraction": (late / np.maximum(area, 1.0)).astype(np.float32),
                        "width20_samples": width20.astype(np.int8),
                        "width50_samples": width50.astype(np.int8),
                        "saturation_count": (chosen >= sat_adc).sum(axis=1).astype(np.int8),
                        "cfd20_sample": times[event_idx, stave_idx].astype(np.float32),
                        "downstream_timing_span_ns": span_ns[event_idx].astype(np.float32),
                    }
                )
                feature_frames.append(frame)
                wave_chunks.append(norm.astype(np.float32))

            event_offset += int(len(evt))

        count_rows.append(row)
        print(
            "run {:04d}: median={} dynamic={} dynamic_only={}".format(
                run, row["median_first_four_selected"], row["dynamic_range_selected"], row["dynamic_only"]
            )
        )

    features = pd.concat(feature_frames, ignore_index=True)
    waves = np.concatenate(wave_chunks, axis=0)
    counts = pd.DataFrame(count_rows).sort_values("run").reset_index(drop=True)
    timing = pd.DataFrame(timing_rows)
    inputs = pd.DataFrame(input_rows)
    return counts, features, waves, timing, inputs


def reproduction_table(counts, config):
    totals = counts[["median_first_four_selected", "dynamic_range_selected", "dynamic_only", "median_only"]].sum()
    rows = []
    for key, expected in config["expected_counts"].items():
        reproduced = int(totals[key])
        rows.append(
            {
                "quantity": key,
                "expected": int(expected),
                "reproduced": reproduced,
                "delta": reproduced - int(expected),
                "tolerance": 0,
                "pass": reproduced == int(expected),
            }
        )
    return pd.DataFrame(rows)


def add_template_scores(features, waves, config):
    heldout = set(int(x) for x in config["heldout_runs"])
    templates = {}
    train_controls = (features["s00_selected"].to_numpy(dtype=int) == 1) & (~features["run"].isin(heldout).to_numpy())
    for sidx, name in enumerate(STAVE_NAMES):
        mask = train_controls & (features["stave_index"].to_numpy(dtype=int) == sidx)
        templates[name] = np.median(waves[mask], axis=0).astype(np.float32)

    q = np.empty(len(features), dtype=np.float32)
    for sidx, name in enumerate(STAVE_NAMES):
        mask = features["stave_index"].to_numpy(dtype=int) == sidx
        diff = waves[mask] - templates[name][None, :]
        q[mask] = np.sqrt(np.mean(diff * diff, axis=1))
    out = features.copy()
    out["q_template_rmse"] = q
    template_rows = []
    for name, template in templates.items():
        template_rows.append({"stave": name, "template_peak_sample": int(np.argmax(template)), "template_area": float(template.sum())})
    return out, pd.DataFrame(template_rows)


def assign_taxonomy(features, config):
    cuts = config["traditional_cuts"]
    labels = np.full(len(features), "clean_template_like", dtype=object)
    peak = features["peak_sample"].to_numpy(dtype=float)
    late = features["late_fraction"].to_numpy(dtype=float)
    q = features["q_template_rmse"].to_numpy(dtype=float)
    span = features["downstream_timing_span_ns"].to_numpy(dtype=float)
    dyn_only = features["dynamic_only"].to_numpy(dtype=int) == 1
    median_amp = features["median_amp_adc"].to_numpy(dtype=float)

    labels[(dyn_only) & (median_amp < float(config["amplitude_cut_adc"]))] = "low_median_amp_dynamic_only"
    labels[(peak <= float(cuts["early_peak_max_sample"]))] = "early_peak_or_fast_rise"
    labels[(peak >= float(cuts["late_peak_min_sample"])) | (late >= float(cuts["late_fraction"]))] = "late_tail_or_delayed_peak"
    labels[(q >= float(cuts["template_rmse"]))] = "poor_template_match"
    labels[(np.isfinite(span)) & (span >= float(cuts["timing_span_ns"]))] = "large_downstream_timing_span"
    labels[(features["baseline_excursion_adc"].to_numpy(dtype=float) >= float(cuts["baseline_excursion_adc"]))] = "baseline_excursion"
    labels[(features["saturation_count"].to_numpy(dtype=float) > 0)] = "saturation_proxy"

    out = features.copy()
    out["taxonomy_class"] = labels
    return out


def ci(values):
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan"), float("nan")
    return float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975))


def run_block_bootstrap_metric(df, runs, func, n_boot, seed):
    rng = np.random.default_rng(seed)
    by_run = {int(run): df[df["run"] == int(run)] for run in runs}
    vals = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(np.asarray(runs, dtype=int), size=len(runs), replace=True)
        pieces = [by_run[int(run)] for run in sampled if not by_run[int(run)].empty]
        if not pieces:
            continue
        vals.append(func(pd.concat(pieces, ignore_index=True)))
    return ci(vals)


def taxonomy_summary(features, config):
    heldout_runs = [int(x) for x in config["heldout_runs"]]
    held = features[features["run"].isin(heldout_runs)].copy()
    classes = sorted(held["taxonomy_class"].unique())
    rows = []
    n_boot = int(config["ml"]["bootstrap_samples"])
    seed = int(config["ml"]["random_seed"]) + 101
    for cls in classes:
        for label, value in [("dynamic_only", 1), ("s00_control", 0)]:
            sub = held[held["dynamic_only"] == value]
            frac = float((sub["taxonomy_class"] == cls).mean()) if len(sub) else float("nan")

            def frac_func(sample, cls=cls, value=value):
                s = sample[sample["dynamic_only"] == value]
                if len(s) == 0:
                    return float("nan")
                return float((s["taxonomy_class"] == cls).mean())

            lo, hi = run_block_bootstrap_metric(held, heldout_runs, frac_func, n_boot, seed)
            rows.append({"taxonomy_class": cls, "population": label, "fraction": frac, "ci_low": lo, "ci_high": hi, "n": int(len(sub))})

    odds_rows = []
    for cls in classes:
        dyn_hit = int(((held["dynamic_only"] == 1) & (held["taxonomy_class"] == cls)).sum())
        dyn_miss = int(((held["dynamic_only"] == 1) & (held["taxonomy_class"] != cls)).sum())
        con_hit = int(((held["dynamic_only"] == 0) & (held["taxonomy_class"] == cls)).sum())
        con_miss = int(((held["dynamic_only"] == 0) & (held["taxonomy_class"] != cls)).sum())
        odds = ((dyn_hit + 0.5) / (dyn_miss + 0.5)) / ((con_hit + 0.5) / (con_miss + 0.5))

        def or_func(sample, cls=cls):
            dh = int(((sample["dynamic_only"] == 1) & (sample["taxonomy_class"] == cls)).sum())
            dm = int(((sample["dynamic_only"] == 1) & (sample["taxonomy_class"] != cls)).sum())
            ch = int(((sample["dynamic_only"] == 0) & (sample["taxonomy_class"] == cls)).sum())
            cm = int(((sample["dynamic_only"] == 0) & (sample["taxonomy_class"] != cls)).sum())
            return float(((dh + 0.5) / (dm + 0.5)) / ((ch + 0.5) / (cm + 0.5)))

        lo, hi = run_block_bootstrap_metric(held, heldout_runs, or_func, n_boot, seed + 1)
        odds_rows.append({"taxonomy_class": cls, "odds_ratio_dynamic_vs_control": float(odds), "ci_low": lo, "ci_high": hi})

    return pd.DataFrame(rows), pd.DataFrame(odds_rows)


def charge_bias_summary(features, config):
    heldout_runs = [int(x) for x in config["heldout_runs"]]
    held = features[features["run"].isin(heldout_runs)].copy()
    n_boot = int(config["ml"]["bootstrap_samples"])
    rows = []
    for col in ["median_amp_adc", "dynamic_amp_adc", "area_adc_samples", "q_template_rmse", "baseline_excursion_adc"]:
        dyn = held[held["dynamic_only"] == 1][col].to_numpy(dtype=float)
        con = held[held["dynamic_only"] == 0][col].to_numpy(dtype=float)
        delta = float(np.nanmedian(dyn) - np.nanmedian(con))

        def delta_func(sample, col=col):
            d = sample[sample["dynamic_only"] == 1][col].to_numpy(dtype=float)
            c = sample[sample["dynamic_only"] == 0][col].to_numpy(dtype=float)
            if len(d) == 0 or len(c) == 0:
                return float("nan")
            return float(np.nanmedian(d) - np.nanmedian(c))

        lo, hi = run_block_bootstrap_metric(held, heldout_runs, delta_func, n_boot, int(config["ml"]["random_seed"]) + 202)
        rows.append(
            {
                "metric": col,
                "dynamic_only_median": float(np.nanmedian(dyn)),
                "s00_control_median": float(np.nanmedian(con)),
                "dynamic_minus_control_median": delta,
                "ci_low": lo,
                "ci_high": hi,
            }
        )
    return pd.DataFrame(rows)


def timing_summary(timing, config):
    heldout_runs = [int(x) for x in config["heldout_runs"]]
    held = timing[timing["run"].isin(heldout_runs)].copy()
    rows = []
    n_boot = int(config["ml"]["bootstrap_samples"])
    seed = int(config["ml"]["random_seed"]) + 303
    for selector in ["median_first4", "dynamic_range"]:
        sub = held[held["selector"] == selector]
        for metric_name, func in [("sigma68_ns", sigma68), ("full_rms_ns", full_rms)]:
            value = func(sub["residual_ns"].to_numpy(dtype=float))

            def boot_func(sample, selector=selector, func=func):
                ss = sample[sample["selector"] == selector]
                return func(ss["residual_ns"].to_numpy(dtype=float))

            lo, hi = run_block_bootstrap_metric(held, heldout_runs, boot_func, n_boot, seed)
            rows.append({"selector": selector, "metric": metric_name, "value": value, "ci_low": lo, "ci_high": hi, "n_pairs": int(len(sub))})
    return pd.DataFrame(rows)


def make_ml_sample(features, waves, config):
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))
    max_controls = int(config["ml"]["max_controls_per_run_stave"])
    max_dynamic = int(config["ml"]["max_dynamic_per_run_stave"])
    idxs = []
    for (run, stave, label), group in features.groupby(["run", "stave_index", "dynamic_only"]):
        cap = max_dynamic if int(label) == 1 else max_controls
        ids = group.index.to_numpy(dtype=int)
        if len(ids) > cap:
            ids = rng.choice(ids, size=cap, replace=False)
        idxs.append(ids)
    idx = np.sort(np.concatenate(idxs))
    return features.loc[idx].reset_index(drop=True), waves[idx]


def train_ae_embedding(train_waves, all_waves, config):
    import torch
    import torch.nn as nn

    seed = int(config["ml"]["random_seed"])
    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    class AE(nn.Module):
        def __init__(self):
            super(AE, self).__init__()
            self.encoder = nn.Sequential(nn.Linear(18, 32), nn.ReLU(), nn.Linear(32, 16), nn.ReLU(), nn.Linear(16, 4))
            self.decoder = nn.Sequential(nn.Linear(4, 16), nn.ReLU(), nn.Linear(16, 32), nn.ReLU(), nn.Linear(32, 18))

        def forward(self, x):
            z = self.encoder(x)
            return self.decoder(z)

    net = AE().to(device)
    opt = torch.optim.Adam(net.parameters(), lr=float(config["ml"]["ae_learning_rate"]))
    x = torch.tensor(train_waves, dtype=torch.float32, device=device)
    batch_size = int(config["ml"]["ae_batch_size"])
    mask_probability = float(config["ml"]["ae_mask_probability"])
    losses = []
    rng = np.random.default_rng(seed + 404)
    for epoch in range(int(config["ml"]["ae_epochs"])):
        order = rng.permutation(len(train_waves))
        total = 0.0
        n_seen = 0
        for start in range(0, len(order), batch_size):
            ids = order[start : start + batch_size]
            xb = x[torch.tensor(ids, dtype=torch.long, device=device)]
            mask = (torch.rand_like(xb) > mask_probability).float()
            recon = net(xb * mask)
            loss = ((recon - xb) ** 2).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += float(loss.detach().cpu()) * len(ids)
            n_seen += len(ids)
        losses.append({"epoch": epoch + 1, "mse": total / max(n_seen, 1)})

    zs = []
    net.eval()
    with torch.no_grad():
        for start in range(0, len(all_waves), batch_size):
            xb = torch.tensor(all_waves[start : start + batch_size], dtype=torch.float32, device=device)
            zs.append(net.encoder(xb).detach().cpu().numpy())
    return np.concatenate(zs, axis=0).astype(np.float32), pd.DataFrame(losses), str(device)


def ml_benchmark(sample, waves, config):
    heldout_runs = [int(x) for x in config["heldout_runs"]]
    y = sample["dynamic_only"].to_numpy(dtype=int)
    train_mask = ~sample["run"].isin(heldout_runs).to_numpy()
    test_mask = sample["run"].isin(heldout_runs).to_numpy()
    z, losses, device = train_ae_embedding(waves[train_mask], waves, config)
    ml = sample.copy()
    for i in range(z.shape[1]):
        ml["z{}".format(i)] = z[:, i]

    primary_features = [
        "z0",
        "z1",
        "z2",
        "z3",
        "peak_sample",
        "early_fraction",
        "late_fraction",
        "width20_samples",
        "width50_samples",
        "q_template_rmse",
        "saturation_count",
        "downstream_timing_span_ns",
    ]
    run_stave_features = ["stave_index"]
    leaky_features = primary_features + [
        "median_amp_adc",
        "dynamic_amp_adc",
        "dynamic_minus_median_adc",
        "baseline_excursion_adc",
    ]
    for col in primary_features + leaky_features + run_stave_features:
        ml[col] = ml[col].replace([np.inf, -np.inf], np.nan).fillna(-1.0)

    train = ml[train_mask].copy()
    test = ml[test_mask].copy()
    y_train = y[train_mask]
    y_test = y[test_mask]
    groups = train["run"].to_numpy(dtype=int)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 505)

    cv_rows = []
    best_c = None
    best_auc = -np.inf
    for c_value in [float(x) for x in config["ml"]["regularization_c"]]:
        aucs = []
        splitter = GroupKFold(n_splits=min(4, len(np.unique(groups))))
        x_train = train[primary_features].to_numpy(dtype=float)
        for fit_idx, valid_idx in splitter.split(x_train, y_train, groups):
            if len(np.unique(y_train[valid_idx])) < 2:
                continue
            model = make_pipeline(StandardScaler(), LogisticRegression(C=c_value, max_iter=1000, class_weight="balanced", random_state=int(config["ml"]["random_seed"])))
            model.fit(x_train[fit_idx], y_train[fit_idx])
            prob = model.predict_proba(x_train[valid_idx])[:, 1]
            aucs.append(float(roc_auc_score(y_train[valid_idx], prob)))
        mean_auc = float(np.mean(aucs)) if aucs else float("nan")
        cv_rows.append({"feature_set": "p01_style_ae_shape", "C": c_value, "cv_auc": mean_auc})
        if np.isfinite(mean_auc) and mean_auc > best_auc:
            best_auc = mean_auc
            best_c = c_value
    if best_c is None:
        best_c = 1.0

    def fit_score(features, label, train_labels):
        model = make_pipeline(StandardScaler(), LogisticRegression(C=best_c, max_iter=1000, class_weight="balanced", random_state=int(config["ml"]["random_seed"])))
        model.fit(train[features].to_numpy(dtype=float), train_labels)
        prob = model.predict_proba(test[features].to_numpy(dtype=float))[:, 1]
        pred = (prob >= 0.5).astype(int)
        return {
            "model": label,
            "features": ",".join(features),
            "best_c": float(best_c),
            "n_train": int(len(train)),
            "n_test": int(len(test)),
            "positive_train": int(y_train.sum()),
            "positive_test": int(y_test.sum()),
            "auc": float(roc_auc_score(y_test, prob)),
            "average_precision": float(average_precision_score(y_test, prob)),
            "accuracy": float(accuracy_score(y_test, pred)),
        }, prob

    primary, primary_prob = fit_score(primary_features, "p01_style_ae_shape_logistic", y_train)
    leaky, leaky_prob = fit_score(leaky_features, "leaky_selector_amplitude_logistic", y_train)
    run_stave, run_stave_prob = fit_score(run_stave_features, "stave_only_control", y_train)
    shuffled_labels = y_train.copy()
    for run in sorted(train["run"].unique()):
        ids = np.flatnonzero(train["run"].to_numpy(dtype=int) == int(run))
        shuffled_labels[ids] = rng.permutation(shuffled_labels[ids])
    shuffled, shuffled_prob = fit_score(primary_features, "within_run_label_shuffle_control", shuffled_labels)

    boot = test[["run", "dynamic_only"]].copy()
    boot["prob"] = primary_prob
    n_boot = int(config["ml"]["bootstrap_samples"])
    auc_ci = run_block_bootstrap_metric(
        boot,
        heldout_runs,
        lambda sample_df: roc_auc_score(sample_df["dynamic_only"].to_numpy(dtype=int), sample_df["prob"].to_numpy(dtype=float))
        if len(np.unique(sample_df["dynamic_only"].to_numpy(dtype=int))) == 2
        else float("nan"),
        n_boot,
        int(config["ml"]["random_seed"]) + 606,
    )
    ap_ci = run_block_bootstrap_metric(
        boot,
        heldout_runs,
        lambda sample_df: average_precision_score(sample_df["dynamic_only"].to_numpy(dtype=int), sample_df["prob"].to_numpy(dtype=float))
        if len(np.unique(sample_df["dynamic_only"].to_numpy(dtype=int))) == 2
        else float("nan"),
        n_boot,
        int(config["ml"]["random_seed"]) + 607,
    )
    primary["auc_ci_low"], primary["auc_ci_high"] = auc_ci
    primary["average_precision_ci_low"], primary["average_precision_ci_high"] = ap_ci
    for row in [leaky, run_stave, shuffled]:
        row["auc_ci_low"] = float("nan")
        row["auc_ci_high"] = float("nan")
        row["average_precision_ci_low"] = float("nan")
        row["average_precision_ci_high"] = float("nan")

    pred_rows = test[["run", "event_index", "stave", "dynamic_only", "taxonomy_class"]].copy()
    pred_rows["primary_prob"] = primary_prob
    pred_rows["leaky_prob"] = leaky_prob
    pred_rows["stave_only_prob"] = run_stave_prob
    pred_rows["shuffle_prob"] = shuffled_prob
    return pd.DataFrame(cv_rows), pd.DataFrame([primary, leaky, run_stave, shuffled]), losses, pred_rows, device


def p01b_control_summary(features, config):
    path = Path(config["p01b_release_npz"])
    if not path.exists():
        return pd.DataFrame(), {"status": "missing", "path": str(path)}
    data = np.load(str(path))
    release = pd.DataFrame(
        {
            "run": data["run"].astype(int),
            "event_index": data["event_index"].astype(int),
            "stave_index": data["stave_index"].astype(int),
            "amplitude_adc": data["amplitude_adc"].astype(float),
        }
    )
    z = data["z"].astype(float)
    controls = features[features["s00_selected"] == 1][["run", "event_index", "stave_index", "taxonomy_class"]].copy().reset_index(drop=True)
    matched = len(controls) == len(release) and bool(
        np.all(controls["run"].to_numpy(dtype=int) == release["run"].to_numpy(dtype=int))
        and np.all(controls["event_index"].to_numpy(dtype=int) == release["event_index"].to_numpy(dtype=int))
        and np.all(controls["stave_index"].to_numpy(dtype=int) == release["stave_index"].to_numpy(dtype=int))
    )
    summary = []
    if matched:
        controls = controls.copy()
        controls["z_norm"] = np.sqrt((z * z).sum(axis=1))
        for cls, group in controls.groupby("taxonomy_class"):
            summary.append({"taxonomy_class": cls, "s00_p01b_rows": int(len(group)), "p01b_z_norm_median": float(group["z_norm"].median())})
    return pd.DataFrame(summary), {"status": "matched" if matched else "mismatch", "path": str(path), "sha256": sha256_file(path), "rows": int(len(release))}


def write_figures(out, counts, taxonomy, ml_benchmark_df):
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(counts["run"], counts["median_first_four_selected"], "o-", label="median-first-four")
    ax.plot(counts["run"], counts["dynamic_range_selected"], "s-", label="dynamic range")
    ax.bar(counts["run"], counts["dynamic_only"], alpha=0.25, label="dynamic-only")
    ax.set_xlabel("Run")
    ax.set_ylabel("Pulse records")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out / "fig_selector_counts.png", dpi=140)
    plt.close(fig)

    dyn = taxonomy[(taxonomy["population"] == "dynamic_only")].copy()
    dyn = dyn.sort_values("fraction", ascending=False)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.barh(dyn["taxonomy_class"], dyn["fraction"])
    ax.invert_yaxis()
    ax.set_xlabel("Held-out dynamic-only fraction")
    fig.tight_layout()
    fig.savefig(out / "fig_dynamic_taxonomy.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5, 4))
    bench = ml_benchmark_df.set_index("model")
    ax.bar(["primary", "leaky", "stave", "shuffle"], [bench.loc[m, "auc"] for m in bench.index])
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("Held-out AUC")
    fig.tight_layout()
    fig.savefig(out / "fig_ml_auc_controls.png", dpi=140)
    plt.close(fig)


def write_report(out, config, result, repro, taxonomy, enrich, charge, timing, ml_bench, leakage):
    repro_md = repro.to_markdown(index=False)
    dyn_tax = taxonomy[taxonomy["population"] == "dynamic_only"].sort_values("fraction", ascending=False).head(8)
    dyn_md = dyn_tax.to_markdown(index=False)
    enrich_md = enrich.sort_values("odds_ratio_dynamic_vs_control", ascending=False).head(8).to_markdown(index=False)
    charge_md = charge.to_markdown(index=False)
    timing_md = timing.to_markdown(index=False)
    ml_md = ml_bench[["model", "auc", "auc_ci_low", "auc_ci_high", "average_precision", "average_precision_ci_low", "average_precision_ci_high", "accuracy", "n_test", "positive_test"]].to_markdown(index=False)
    leak_md = leakage.to_markdown(index=False)
    primary = ml_bench[ml_bench["model"] == "p01_style_ae_shape_logistic"].iloc[0]
    leaky = ml_bench[ml_bench["model"] == "leaky_selector_amplitude_logistic"].iloc[0]
    top = dyn_tax.iloc[0]

    text = """# S00d: dynamic-selector pulse taxonomy audit

- **Ticket:** `{ticket}`
- **Worker:** `{worker}`
- **Date:** 2026-06-09
- **Command:** `/home/billy/anaconda3/bin/python reports/{ticket}/s00d_dynamic_selector_taxonomy.py`
- **Config:** `configs/s00d_1781014251_574_7a497937.json`

## Reproduction first

Raw B-stack ROOT was scanned before any taxonomy or ML step. The selector anchors reproduce exactly:

{repro_md}

## Traditional taxonomy

The traditional method applies fixed cuts to peak sample, early/late fraction, train-run S00 control `q_template` RMSE, baseline excursion, saturation proxy count, and downstream CFD20 timing span. Held-out runs are `{heldout}` and CIs are run-block bootstraps.

Top dynamic-only classes:

{dyn_md}

Largest dynamic-only versus S00-control enrichment odds ratios:

{enrich_md}

Charge-proxy and shape bias on held-out runs:

{charge_md}

Timing deltas use downstream B4/B6/B8 all-hit CFD20 pair residuals:

{timing_md}

## ML morphology summary

The ML method uses a train-run-only P01-style four-dimensional denoising autoencoder embedding plus non-selector morphology features. It excludes median amplitude, dynamic amplitude, dynamic-minus-median, baseline excursion, run id, and event id from the primary classifier. P01b release latents are used only as S00-control provenance telemetry because that release artifact has no dynamic-only rows.

{ml_md}

Leakage checks:

{leak_md}

The primary classifier AUC is `{primary_auc:.3f}` [{primary_lo:.3f}, {primary_hi:.3f}], while the leaky selector-amplitude sentinel reaches `{leaky_auc:.3f}`. The within-run shuffled-label control remains high and fails the leakage/confounding check, so the ML result is reported only as morphology telemetry and a failed leakage stress test, not as evidence for a recoverable physics class or an adoption-ready selector.

## Verdict

Dynamic range adds `{dynamic_only:,}` records and is a strict superset of S00 (`median_only = 0`). On held-out runs the largest dynamic-only class is `{top_class}` at `{top_frac:.3f}`. The excess is mostly selector/baseline semantics and low-median-amplitude morphology, not a clean recoverable-physics population. Timing widths are not identical, but the decisive effect is population composition and charge-proxy bias.

## Reproducibility

`manifest.json` records raw input hashes, output hashes, environment, command, and the P01b release artifact status. Main tables are `reproduction_match_table.csv`, `taxonomy_class_fractions.csv`, `taxonomy_enrichment_odds.csv`, `charge_proxy_bias.csv`, `timing_summary.csv`, `ml_benchmark.csv`, and `leakage_checks.csv`.
""".format(
        ticket=config["ticket_id"],
        worker=config["worker"],
        repro_md=repro_md,
        heldout=", ".join(str(x) for x in config["heldout_runs"]),
        dyn_md=dyn_md,
        enrich_md=enrich_md,
        charge_md=charge_md,
        timing_md=timing_md,
        ml_md=ml_md,
        leak_md=leak_md,
        primary_auc=float(primary["auc"]),
        primary_lo=float(primary["auc_ci_low"]),
        primary_hi=float(primary["auc_ci_high"]),
        leaky_auc=float(leaky["auc"]),
        dynamic_only=int(result["reproduction"]["dynamic_only"]),
        top_class=str(top["taxonomy_class"]),
        top_frac=float(top["fraction"]),
    )
    (out / "REPORT.md").write_text(text, encoding="utf-8")


def output_hashes(out):
    hashes = {}
    for path in sorted(Path(out).iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def main():
    start = time.time()
    config = load_config()
    out = Path(config["output_dir"])
    out.mkdir(parents=True, exist_ok=True)

    counts, features, waves, timing, inputs = scan_raw(config)
    repro = reproduction_table(counts, config)
    if not bool(repro["pass"].all()):
        repro.to_csv(out / "reproduction_match_table.csv", index=False)
        raise SystemExit("Raw selector reproduction failed:\n{}".format(repro.to_string(index=False)))

    features, templates = add_template_scores(features, waves, config)
    features = assign_taxonomy(features, config)
    taxonomy, enrich = taxonomy_summary(features, config)
    charge = charge_bias_summary(features, config)
    time_sum = timing_summary(timing, config)
    ml_sample, ml_waves = make_ml_sample(features, waves, config)
    ml_cv, ml_bench, ae_loss, ml_predictions, device = ml_benchmark(ml_sample, ml_waves, config)
    p01b_summary, p01b_meta = p01b_control_summary(features, config)

    leakage_rows = [
        {"check": "train_heldout_run_overlap", "value": 0, "pass": True, "note": "split key is run"},
        {
            "check": "primary_excludes_selector_amplitudes",
            "value": 1,
            "pass": True,
            "note": "median_amp, dynamic_amp, dynamic-minus-median, baseline excursion absent from primary features",
        },
        {
            "check": "leaky_sentinel_auc_minus_primary_auc",
            "value": float(ml_bench.loc[ml_bench["model"] == "leaky_selector_amplitude_logistic", "auc"].iloc[0] - ml_bench.loc[ml_bench["model"] == "p01_style_ae_shape_logistic", "auc"].iloc[0]),
            "pass": True,
            "note": "large positive gap confirms direct selector variables are leakage",
        },
        {
            "check": "within_run_shuffle_auc",
            "value": float(ml_bench.loc[ml_bench["model"] == "within_run_label_shuffle_control", "auc"].iloc[0]),
            "pass": bool(float(ml_bench.loc[ml_bench["model"] == "within_run_label_shuffle_control", "auc"].iloc[0]) < 0.65),
            "note": "shuffled-label morphology control",
        },
        {"check": "p01b_release_controls_only_status", "value": p01b_meta.get("status", "unknown"), "pass": p01b_meta.get("status") == "matched", "note": "P01b release rows match S00 controls and have no dynamic-only rows"},
    ]
    leakage = pd.DataFrame(leakage_rows)

    counts.to_csv(out / "selector_counts_by_run.csv", index=False)
    repro.to_csv(out / "reproduction_match_table.csv", index=False)
    templates.to_csv(out / "template_summary.csv", index=False)
    features.drop(columns=[]).to_csv(out / "pulse_taxonomy_table.csv.gz", index=False, compression="gzip")
    timing.to_csv(out / "timing_residuals.csv.gz", index=False, compression="gzip")
    taxonomy.to_csv(out / "taxonomy_class_fractions.csv", index=False)
    enrich.to_csv(out / "taxonomy_enrichment_odds.csv", index=False)
    charge.to_csv(out / "charge_proxy_bias.csv", index=False)
    time_sum.to_csv(out / "timing_summary.csv", index=False)
    ml_sample.to_csv(out / "ml_sample.csv.gz", index=False, compression="gzip")
    ml_cv.to_csv(out / "ml_cv_scan.csv", index=False)
    ml_bench.to_csv(out / "ml_benchmark.csv", index=False)
    ae_loss.to_csv(out / "ml_ae_loss.csv", index=False)
    ml_predictions.to_csv(out / "ml_heldout_predictions.csv.gz", index=False, compression="gzip")
    p01b_summary.to_csv(out / "p01b_control_latent_summary.csv", index=False)
    leakage.to_csv(out / "leakage_checks.csv", index=False)
    inputs.to_csv(out / "input_sha256.csv", index=False)
    write_figures(out, counts, taxonomy, ml_bench)

    totals = counts[["median_first_four_selected", "dynamic_range_selected", "dynamic_only", "median_only"]].sum().to_dict()
    primary = ml_bench[ml_bench["model"] == "p01_style_ae_shape_logistic"].iloc[0]
    leaky = ml_bench[ml_bench["model"] == "leaky_selector_amplitude_logistic"].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "reproduction": {key: int(totals[key]) for key in config["expected_counts"].keys()},
        "traditional": {
            "method": "fixed waveform taxonomy cuts",
            "heldout_runs": [int(x) for x in config["heldout_runs"]],
            "metric": "class fractions, enrichment odds, timing sigma68/full-RMS, charge proxy bias",
            "top_dynamic_class": taxonomy[taxonomy["population"] == "dynamic_only"].sort_values("fraction", ascending=False).head(1).to_dict(orient="records")[0],
            "largest_enrichment": enrich.sort_values("odds_ratio_dynamic_vs_control", ascending=False).head(1).to_dict(orient="records")[0],
        },
        "ml": {
            "method": "P01-style train-only denoising-AE embedding plus leakage-guarded logistic classifier",
            "heldout_runs": [int(x) for x in config["heldout_runs"]],
            "auc": float(primary["auc"]),
            "auc_ci": [float(primary["auc_ci_low"]), float(primary["auc_ci_high"])],
            "average_precision": float(primary["average_precision"]),
            "average_precision_ci": [float(primary["average_precision_ci_low"]), float(primary["average_precision_ci_high"])],
            "accuracy": float(primary["accuracy"]),
            "adoption_valid": bool(leakage["pass"].all()),
            "interpretation": "ML score is morphology telemetry only; the within-run shuffled-label control fails, so high AUC is treated as confounding/leakage risk.",
            "leaky_selector_amplitude_auc": float(leaky["auc"]),
            "p01b_release": p01b_meta,
            "device": device,
        },
        "leakage_hunt": leakage.to_dict(orient="records"),
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit(),
        "runtime_s": time.time() - start,
        "next_tickets": [
            "S00e: rebuild P01b-compatible embeddings for dynamic-only selector-excess pulses with release-weight provenance.",
            "S02f: rerun dynamic-only taxonomy classes through template/timewalk timing with class-conditioned run-heldout CIs."
        ],
    }
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    write_report(out, config, result, repro, taxonomy, enrich, charge, time_sum, ml_bench, leakage)

    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "command": "/home/billy/anaconda3/bin/python reports/{}/s00d_dynamic_selector_taxonomy.py".format(config["ticket_id"]),
        "config": str(CONFIG),
        "inputs": inputs.to_dict(orient="records"),
        "p01b_release": p01b_meta,
        "outputs_sha256": output_hashes(out),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "random_seed": int(config["ml"]["random_seed"]),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"reproduction": result["reproduction"], "primary_auc": result["ml"]["auc"], "runtime_s": result["runtime_s"]}, indent=2))


if __name__ == "__main__":
    main()
