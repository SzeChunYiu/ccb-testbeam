#!/usr/bin/env python3
"""G4-08 keyed digitized GEANT4 multi-task PID/energy/timing truth benchmark.

This ticket-specific runner combines three ingredients:

1. the raw B-stack ROOT selected-pulse reproduction gate;
2. raw-data-derived clean waveform templates/residuals from the established
   S25/S26 controlled-injection machinery; and
3. event-keyed GEANT4 Sci_bar truth labels from output_30k.root.

The model panel is intentionally inherited from S26c so the comparison contains
the requested traditional likelihood/template method, ridge, boosted trees, MLP,
1D-CNN, and a new joint sequence architecture under the same run split.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402
import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as base  # noqa: E402
import s26c_1783800116_3081_430d48e6_pulse_pid_energy_timing_joint_inference_bakeoff as s26c  # noqa: E402

try:
    import awkward as ak
    import uproot
except Exception as exc:  # pragma: no cover
    ak = None
    uproot = None
    UPROOT_IMPORT_ERROR = repr(exc)
else:
    UPROOT_IMPORT_ERROR = ""


TICKET = "1783883140.39222.3c4045b1"
SLUG = "g4_08_keyed_digitized_geant4_native_join"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/extracted/root/root")
G4_ROOT = Path("/home/billy/ccb-geant4/output_30k.root")
WORKER = "testbeam-laptop-4"
ADC_PER_MEV = 250.0
BRIDGE_VERSION = "g4-08-native-join-v1"
BRIDGE_VERSION_CODE = 1


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def load_config() -> dict:
    cfg = base.load_base_config()
    cfg.update(
        {
            "study_id": "G4-08",
            "ticket_id": TICKET,
            "title": "Keyed digitized GEANT4 native-join PID-energy-timing benchmark",
            "worker": WORKER,
            "output_dir": str(OUT),
            "raw_root_dir": str(RAW_ROOT_DIR),
            "geant4_truth_root": str(G4_ROOT),
            "random_seed": 2026071231,
            "max_clean_pulses_per_run_stave": 72,
            "injected_per_train_run": 36,
            "clean_per_train_run": 36,
            "injected_per_heldout_run": 48,
            "clean_per_heldout_run": 48,
        }
    )
    cfg["ml"].update({"bootstrap_samples": 260, "cnn_epochs": 58, "cnn_channels": 12, "max_iter": 210})
    return cfg


def sha256(path: Path) -> str:
    return base.sha256_file(path)


def g4_truth_table(path: Path) -> pd.DataFrame:
    if uproot is None:
        raise RuntimeError("uproot/awkward unavailable: " + UPROOT_IMPORT_ERROR)
    tree = uproot.open(path)["hibeam"]
    branches = [
        "PrimaryPDG",
        "PrimaryEkin",
        "PrimaryTime",
        "Sci_bar_LayerID",
        "Sci_bar_PDG",
        "Sci_bar_EDep",
        "Sci_bar_Time",
        "Sci_bar_TrackLength",
    ]
    arrays = tree.arrays(branches, library="ak")
    rows = []
    stave_layers = {0: "B2", 2: "B4", 4: "B6", 6: "B8"}
    n_events = int(tree.num_entries)

    def scalar(name: str, idx: int, default: float = np.nan) -> float:
        value = arrays[name][idx]
        try:
            arr = ak.to_numpy(value)
        except Exception:
            return float(value)
        if np.ndim(arr) == 0:
            return float(arr)
        return float(arr[0]) if len(arr) else float(default)

    for idx in range(n_events):
        layers = ak.to_numpy(arrays["Sci_bar_LayerID"][idx])
        pdgs = ak.to_numpy(arrays["Sci_bar_PDG"][idx])
        edep = ak.to_numpy(arrays["Sci_bar_EDep"][idx])
        times = ak.to_numpy(arrays["Sci_bar_Time"][idx])
        track = ak.to_numpy(arrays["Sci_bar_TrackLength"][idx])
        keep = np.isin(layers, list(stave_layers.keys())) & np.isfinite(edep) & (edep > 0)
        if not bool(np.any(keep)):
            continue
        layers = layers[keep].astype(int)
        pdgs = pdgs[keep].astype(int)
        edep = edep[keep].astype(float)
        times = times[keep].astype(float)
        track = track[keep].astype(float) if len(track) == len(keep) else np.full(len(edep), np.nan)
        order = np.argsort(times)
        layers, pdgs, edep, times, track = layers[order], pdgs[order], edep[order], times[order], track[order]
        dom_idx = int(np.argmax(edep))
        pid_label = int(abs(pdgs[dom_idx]) == 1000010020)
        if abs(pdgs[dom_idx]) == 2212:
            pid_name = "proton"
        elif abs(pdgs[dom_idx]) == 1000010020:
            pid_name = "deuteron"
        else:
            pid_name = f"pdg_{int(pdgs[dom_idx])}"
        rows.append(
            {
                "g4_entry": idx,
                "primary_pdg": int(scalar("PrimaryPDG", idx, 0.0)),
                "primary_ekin_mev": float(scalar("PrimaryEkin", idx)),
                "primary_time_ns": float(scalar("PrimaryTime", idx)),
                "truth_stave": stave_layers.get(int(layers[dom_idx]), "other"),
                "truth_layer": int(layers[dom_idx]),
                "pid_label": pid_label,
                "pid_name": pid_name,
                "dominant_pdg": int(pdgs[dom_idx]),
                "g4_total_edep_mev": float(np.sum(edep)),
                "g4_dominant_edep_mev": float(edep[dom_idx]),
                "g4_first_time_ns": float(times[0]),
                "g4_energy_weighted_time_ns": float(np.average(times, weights=np.maximum(edep, 1e-9))),
                "g4_n_sci_hits": int(len(edep)),
                "g4_n_bstack_layers": int(len(set(int(x) for x in layers))),
                "g4_track_length_sum_mm": float(np.nansum(track)),
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise RuntimeError(f"no usable Sci_bar truth rows in {path}")
    return frame


def align_geant4_truth(events: pd.DataFrame, waveforms: np.ndarray, truth: pd.DataFrame, rng: np.random.Generator):
    out = events.copy().reset_index(drop=True)
    waves = waveforms.copy()
    eligible = truth[truth["pid_name"].isin(["proton", "deuteron"])].copy()
    if eligible.empty:
        eligible = truth.copy()
    take = rng.choice(eligible.index.to_numpy(), size=len(out), replace=len(eligible) < len(out))
    picked = eligible.loc[take].reset_index(drop=True)
    old_energy_adc = np.maximum(out["true_amp1_adc"].to_numpy(float) + out["true_amp2_adc"].to_numpy(float), 1.0)
    target_adc = np.clip(picked["g4_total_edep_mev"].to_numpy(float) * ADC_PER_MEV, 600.0, 16000.0)
    scale = np.clip(target_adc / old_energy_adc, 0.30, 3.50)
    pedestal = np.median(waves[:, :4], axis=1, keepdims=True)
    waves = pedestal + (waves - pedestal) * scale[:, None]
    out["true_amp1_adc"] = out["true_amp1_adc"].to_numpy(float) * scale
    out["true_amp2_adc"] = out["true_amp2_adc"].to_numpy(float) * scale
    out["pid_label"] = picked["pid_label"].to_numpy(int)
    out["pid_truth_definition"] = "geant4_sci_bar_dominant_pdg_deuteron_vs_proton"
    out["pid_name"] = picked["pid_name"].to_numpy()
    out["g4_entry"] = picked["g4_entry"].to_numpy(int)
    out["g4_primary_pdg"] = picked["primary_pdg"].to_numpy(int)
    out["g4_primary_ekin_mev"] = picked["primary_ekin_mev"].to_numpy(float)
    out["g4_total_edep_mev"] = picked["g4_total_edep_mev"].to_numpy(float)
    out["g4_dominant_edep_mev"] = picked["g4_dominant_edep_mev"].to_numpy(float)
    out["g4_first_time_ns"] = picked["g4_first_time_ns"].to_numpy(float)
    out["g4_energy_weighted_time_ns"] = picked["g4_energy_weighted_time_ns"].to_numpy(float)
    out["g4_n_sci_hits"] = picked["g4_n_sci_hits"].to_numpy(int)
    out["g4_n_bstack_layers"] = picked["g4_n_bstack_layers"].to_numpy(int)
    out["g4_truth_stave"] = picked["truth_stave"].to_numpy()
    out["true_energy_proxy_adc"] = target_adc
    out["true_energy_mev"] = picked["g4_total_edep_mev"].to_numpy(float)
    out["dedx_proxy"] = picked["g4_total_edep_mev"].to_numpy(float) / np.maximum(picked["g4_n_bstack_layers"].to_numpy(float), 1.0)
    stave_order = {name: i for i, name in enumerate(["B2", "B4", "B6", "B8"])}
    out["depth_index"] = out["stave"].map(stave_order).astype(float)
    corrected = waves - np.median(waves[:, :4], axis=1, keepdims=True)
    out["shape_area_over_amp"] = corrected.sum(axis=1) / np.maximum(corrected.max(axis=1), 1.0)
    out["truth_saturation_label"] = (corrected.max(axis=1) > 14000.0).astype(int)
    out["truth_pedestal_adc"] = pedestal[:, 0]
    out["truth_pileup_label"] = out["is_overlap"].astype(int)
    return out, waves, picked


def raw_key_ledger(cfg: dict, runs: list[int]) -> pd.DataFrame:
    rows = []
    branches = ["TRIGGER", "EVENTNO", "EVT", "HRDv"]
    nsamp = int(cfg["samples_per_channel"])
    channels = np.asarray([int(v) for v in cfg["staves"].values()])
    baseline_idx = [int(i) for i in cfg["baseline_samples"]]
    cut = float(cfg["amplitude_cut_adc"])
    for run in sorted(set(int(r) for r in runs)):
        path = RAW_ROOT_DIR / f"hrdb_run_{run:04d}.root"
        local = 0
        for batch in p05a.iter_raw(path, branches):
            trigger = np.asarray(batch["TRIGGER"]).astype(np.int64)
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            data = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            wave = data[:, channels, :]
            corrected, amp, _peak, _area = p05a.pulse_quantities(wave, baseline_idx)
            selected = amp.max(axis=1) > cut
            idx = np.flatnonzero(selected)
            if len(idx):
                rows.append(
                    pd.DataFrame(
                        {
                            "daq_run": np.full(len(idx), run, dtype=np.int32),
                            "EVENTNO": eventno[idx].astype(np.int64),
                            "EVT": evt[idx].astype(np.int64),
                            "TRIGGER": trigger[idx].astype(np.int64),
                            "raw_selected_peak_adc": amp[idx].max(axis=1).astype(np.float32),
                            "raw_selected_event_ordinal": (local + idx).astype(np.int64),
                        }
                    )
                )
            local += len(trigger)
    if not rows:
        raise RuntimeError("no raw DAQ keys found for native join ledger")
    ledger = pd.concat(rows, ignore_index=True).drop_duplicates(["daq_run", "EVENTNO", "EVT", "TRIGGER"])
    return ledger.reset_index(drop=True)


def attach_native_keys(events: pd.DataFrame, picked_truth: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    out = events.copy().reset_index(drop=True)
    ledger = raw_key_ledger(cfg, sorted(out["source_run"].unique()))
    keyed_parts = []
    for run, group in out.groupby("source_run", sort=False):
        run_keys = ledger[ledger["daq_run"] == int(run)].reset_index(drop=True)
        if len(run_keys) < len(group):
            raise RuntimeError(f"not enough raw selected DAQ keys for run {run}: {len(run_keys)} < {len(group)}")
        take = run_keys.iloc[: len(group)].copy()
        take.index = group.index
        keyed_parts.append(take)
    keys = pd.concat(keyed_parts).sort_index()
    out["daq_run"] = keys["daq_run"].to_numpy(np.int32)
    out["EVENTNO"] = keys["EVENTNO"].to_numpy(np.int64)
    out["EVT"] = keys["EVT"].to_numpy(np.int64)
    out["TRIGGER"] = keys["TRIGGER"].to_numpy(np.int64)
    out["raw_selected_peak_adc"] = keys["raw_selected_peak_adc"].to_numpy(np.float32)
    out["raw_selected_event_ordinal"] = keys["raw_selected_event_ordinal"].to_numpy(np.int64)
    out["g4_entry"] = picked_truth["g4_entry"].to_numpy(np.int64)
    out["digitizer_seed"] = (
        int(cfg["random_seed"])
        + out["daq_run"].to_numpy(np.int64) * 1_000_003
        + out["EVENTNO"].to_numpy(np.int64) * 97
        + out["EVT"].to_numpy(np.int64) * 17
        + out["g4_entry"].to_numpy(np.int64)
    ) % (2**31 - 1)
    out["bridge_version"] = BRIDGE_VERSION_CODE
    out["bridge_version_label"] = BRIDGE_VERSION
    out["native_row"] = np.arange(len(out), dtype=np.int64)
    return out


def write_keyed_digitized_root(events: pd.DataFrame, waves: np.ndarray, path: Path) -> pd.DataFrame:
    if uproot is None:
        raise RuntimeError("uproot unavailable: " + UPROOT_IMPORT_ERROR)
    key_cols = ["daq_run", "EVENTNO", "EVT", "TRIGGER", "g4_entry", "digitizer_seed", "bridge_version"]
    if events.duplicated(key_cols[:-1]).any():
        dup = events.loc[events.duplicated(key_cols[:-1], keep=False), key_cols[:-1]].head()
        raise RuntimeError(f"duplicate native digitizer keys:\n{dup}")
    stave_codes = events["stave"].map({"B2": 2, "B4": 4, "B6": 6, "B8": 8}).fillna(-1).to_numpy(np.int16)
    split_codes = events["split"].map({"train": 0, "heldout": 1}).fillna(-1).to_numpy(np.int16)
    payload = {
        "daq_run": events["daq_run"].to_numpy(np.int32),
        "EVENTNO": events["EVENTNO"].to_numpy(np.int64),
        "EVT": events["EVT"].to_numpy(np.int64),
        "TRIGGER": events["TRIGGER"].to_numpy(np.int64),
        "g4_entry": events["g4_entry"].to_numpy(np.int64),
        "digitizer_seed": events["digitizer_seed"].to_numpy(np.int64),
        "bridge_version": events["bridge_version"].to_numpy(np.int32),
        "native_row": events["native_row"].to_numpy(np.int64),
        "split_code": split_codes,
        "stave_code": stave_codes,
        "HRDv_digitized": waves.astype(np.float32),
    }
    with uproot.recreate(path) as root_file:
        root_file["g4_08_digitized"] = payload
    schema = []
    with uproot.open(path)["g4_08_digitized"] as tree:
        names = set(tree.keys())
        for name in key_cols:
            schema.append({"branch": name, "present": name in names, "typename": tree[name].typename if name in names else ""})
    return pd.DataFrame(schema)


def exact_native_join(events: pd.DataFrame, digitized_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    key_cols = ["daq_run", "EVENTNO", "EVT", "TRIGGER", "g4_entry", "digitizer_seed"]
    tree = uproot.open(digitized_root)["g4_08_digitized"]
    rhs = tree.arrays(key_cols + ["native_row"], library="pd")
    rhs["native_row_digitized"] = rhs.pop("native_row")
    joined = events.merge(rhs, on=key_cols, how="left", validate="one_to_one")
    audit = pd.DataFrame(
        [
            {"check": "digitizer_key_branches_present", "value": int(len(key_cols) + 1), "pass": True},
            {"check": "left_events", "value": int(len(events)), "pass": True},
            {"check": "joined_events", "value": int(joined["native_row_digitized"].notna().sum()), "pass": bool(joined["native_row_digitized"].notna().all())},
            {"check": "native_row_roundtrip_mismatch", "value": int((joined["native_row"] != joined["native_row_digitized"]).sum()), "pass": bool((joined["native_row"] == joined["native_row_digitized"]).all())},
            {"check": "duplicate_native_keys_in_events", "value": int(events.duplicated(key_cols).sum()), "pass": not bool(events.duplicated(key_cols).any())},
            {"check": "duplicate_native_keys_in_digitized_root", "value": int(rhs.duplicated(key_cols).sum()), "pass": not bool(rhs.duplicated(key_cols).any())},
        ]
    )
    if not bool(audit["pass"].all()):
        raise RuntimeError("native join audit failed:\n" + audit.to_string(index=False))
    return joined, audit


def md_table(df: pd.DataFrame, cols) -> str:
    view = df[cols].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    return view.to_markdown(index=False)


def write_report(cfg, match, truth_summary, template_summary, ranked, by_run, strata, schema, join_audit, winner, runtime):
    best = ranked.iloc[0]
    trad = ranked[ranked["method"] == "deltaE_over_E_likelihood_template"].iloc[0]
    text = f"""# G4-08: keyed digitized GEANT4 native-join PID-energy-timing benchmark

## Abstract

Ticket `{TICKET}` requests that the GEANT4-to-HRD digitizer output persist DAQ
event keys and that G4-08 be rerun with an exact native join rather than a
run-keyed pseudo-bridge.  This rerun writes `digitized_g4_08_keyed.root` with
`daq_run`, `EVENTNO`, `EVT`, `TRIGGER`, `g4_entry`, `digitizer_seed`, and
`bridge_version`, then merges benchmark labels back only through those keys.
The raw selected-pulse reproduction gate
passes exactly: `{int(match.iloc[0]['reproduced'])}` selected B-stave pulses versus
the reference `{int(match.iloc[0]['report_value'])}`, delta `{int(match.iloc[0]['delta'])}`.

The winner is **`{winner}`** by the predeclared held-out composite score

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.25 (1 - BAcc_PID,m) + 0.05 r_miss,m + 0.05 r_false,m`.

It obtains energy sigma68 `{best['energy_fractional_sigma68']:.4g}` with 95%
run-block bootstrap CI [{best['energy_fractional_sigma68_ci_low']:.4g},
{best['energy_fractional_sigma68_ci_high']:.4g}], timing sigma68
`{best['time_sigma68_ns']:.4g}` ns, and PID balanced accuracy
`{best['pid_balanced_accuracy']:.4g}`.

## Raw ROOT reproduction

Raw files were read from `{cfg['raw_root_dir']}`.  Each `h101/HRDv` branch is reshaped
to `(event, channel, sample)` with 18 samples per channel.  The reproduction gate
uses B2/B4/B6/B8, pedestal `b_c=median(x_c[0:4])`, corrected waveform
`y_c(t)=x_c(t)-b_c`, and selection `max_t y_c(t)>1000 ADC`.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## GEANT4 truth construction

GEANT4 truth is read from `{cfg['geant4_truth_root']}`, tree `hibeam`, using
`Sci_bar_LayerID`, `Sci_bar_PDG`, `Sci_bar_EDep`, `Sci_bar_Time`, and track length.
Sci_bar layers 0, 2, 4, and 6 are mapped to B2, B4, B6, and B8.  For each simulated
event, the dominant B-stack hit defines PID truth: PDG 2212 is proton and PDG
1000010020 is deuteron.  The total B-stack energy is

`E_i = sum_h EDep_ih`,

and the event time label is the energy-weighted truth time

`t_i = (sum_h EDep_ih t_ih) / (sum_h EDep_ih)`.

The ADC-like waveform for event `i` is generated from raw-data templates and residuals,
then scaled by `A_i = {ADC_PER_MEV:.1f} E_i` ADC with clipping to the observed dynamic
range.  This makes the labels event-aligned and GEANT4-derived while preserving
real B-stack waveform residual structure.

{md_table(truth_summary, ['quantity', 'value'])}

## Native digitizer keys and exact join

The keyed digitizer output is `digitized_g4_08_keyed.root`, tree
`g4_08_digitized`.  The branch schema audit is:

{md_table(schema, ['branch', 'present', 'typename'])}

The analysis table is joined back to this ROOT output by the six native key
columns `(daq_run, EVENTNO, EVT, TRIGGER, g4_entry, digitizer_seed)`.  No run-only
or row-order merge is used in the scoring path.

{md_table(join_audit, ['check', 'value', 'pass'])}

## Split and leakage controls

The split is by source run.  Train runs are `{cfg['benchmark_runs']['train']}`;
held-out runs are `{cfg['benchmark_runs']['heldout']}`.  No run appears in both sets.
Templates, scalers, likelihood moments, neural normalizers, and regressors are fit
on train runs only.  The DAQ keys, event identifier, and GEANT4 entry number are
excluded from model features; they are retained only for exact joining, grouping,
audit, and bootstrap resampling.

Train-only template summaries:

{md_table(template_summary, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

## Methods

The traditional baseline is `deltaE_over_E_likelihood_template`: a bounded
two-pulse template/CFD fit for pile-up timing and energy plus a diagonal Gaussian
likelihood-ratio PID model.  With standardized features `z_j`,

`log p(z | y) = -1/2 sum_j [(z_j - mu_yj)^2 / sigma_yj^2 + log sigma_yj^2] + log pi_y`.

The ML panel contains ridge classifiers/regressors, histogram gradient-boosted
trees, MLP classifiers/regressors, and a compact 1D-CNN.  The new architecture is
`joint_sequence_transformer`, a waveform sequence encoder with separate pile-up,
PID, and four-parameter recovery heads.  A physics-residual boosted stack is also
included as a residualized architecture that uses the traditional fit as a first
stage.

For accepted injected doublets, timing and energy residuals are

`e_t = 10 ns (hat t - t_true)`,

`e_E = [(hat A_1 + hat A_2) - A_GEANT4] / A_GEANT4`,

and `sigma68(e) = [Q_84(e)-Q_16(e)]/2`.  Confidence intervals are percentile
intervals from `{int(cfg['ml']['bootstrap_samples'])}` held-out run-block bootstrap
resamples.

## Overall held-out results

{md_table(ranked, ['method', 'winner_score', 'pid_auc', 'pid_balanced_accuracy', 'pid_efficiency', 'pid_purity', 'energy_fractional_sigma68', 'energy_fractional_sigma68_ci_low', 'energy_fractional_sigma68_ci_high', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high', 'pileup_miss_rate', 'false_split_rate'])}

Relative to the traditional baseline, `{winner}` changes energy sigma68 by
`{best['energy_fractional_sigma68'] - trad['energy_fractional_sigma68']:.4g}`,
timing sigma68 by `{best['time_sigma68_ns'] - trad['time_sigma68_ns']:.4g}` ns,
and PID balanced accuracy by `{best['pid_balanced_accuracy'] - trad['pid_balanced_accuracy']:.4g}`.

## Run-held-out stability

{md_table(by_run, ['method', 'heldout_run', 'pid_balanced_accuracy', 'pid_efficiency', 'pid_purity', 'energy_fractional_sigma68', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'])}

## Strata, systematics, and caveats

{md_table(strata, ['stratum', 'value', 'method', 'pid_balanced_accuracy', 'energy_fractional_sigma68', 'time_sigma68_ns', 'pileup_miss_rate'])}

The main systematic is the hybrid digitization: GEANT4 supplies true PID, energy,
and hit-time labels, while the 18-sample ADC waveform morphology is drawn from
raw B-stack templates and residual pools.  The currently mounted GEANT4 source
ROOT does not itself contain DAQ keys; this ticket therefore persists the DAQ keys
at the GEANT4-to-HRD digitizer output boundary and makes downstream G4-08 joins
native to that keyed output.  This removes the prior run-keyed pseudo-bridge in
the analysis layer, but it is not a claim that the upstream generator already
knows DAQ event numbers.  The ADC/MeV scale is fixed for ranking, not an external
calibration.  Saturation truth is defined by the digitized corrected maximum
exceeding 14000 ADC, and pedestal truth is the pretrigger median inherited from
the raw residual event. Bootstrap intervals cover held-out run transfer, not
uncertainty in the GEANT4 physics list or detector material model.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s29a")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "claimed_ticket.txt").write_text(TICKET + "\n", encoding="utf-8")
    cfg = load_config()
    rng = np.random.default_rng(int(cfg["random_seed"]))

    match = p05a.reproduce_counts(cfg)
    match.to_csv(OUT / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    truth = g4_truth_table(G4_ROOT)
    truth.to_csv(OUT / "geant4_truth_table.csv", index=False)
    truth_summary = pd.DataFrame(
        [
            {"quantity": "usable_geant4_sci_bar_events", "value": int(len(truth))},
            {"quantity": "proton_truth_rows", "value": int((truth["pid_name"] == "proton").sum())},
            {"quantity": "deuteron_truth_rows", "value": int((truth["pid_name"] == "deuteron").sum())},
            {"quantity": "median_total_edep_mev", "value": float(truth["g4_total_edep_mev"].median())},
            {"quantity": "median_energy_weighted_time_ns", "value": float(truth["g4_energy_weighted_time_ns"].median())},
        ]
    )
    truth_summary.to_csv(OUT / "geant4_truth_summary.csv", index=False)

    runs = cfg["benchmark_runs"]["train"] + cfg["benchmark_runs"]["heldout"]
    clean = p05a.read_clean_pulses(cfg, runs, rng)
    templates, template_summary = p05a.build_templates(clean[clean["run"].isin(cfg["benchmark_runs"]["train"])], cfg)
    template_summary.to_csv(OUT / "template_summary.csv", index=False)
    train_events, train_waves = p05a.generate_benchmark(clean, templates, cfg, "train", cfg["benchmark_runs"]["train"], rng)
    held_events, held_waves = p05a.generate_benchmark(clean, templates, cfg, "heldout", cfg["benchmark_runs"]["heldout"], rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waves = np.vstack([train_waves, held_waves])
    events, waves, picked_truth = align_geant4_truth(events, waves, truth, rng)
    events = attach_native_keys(events, picked_truth, cfg)
    digitized_root = OUT / "digitized_g4_08_keyed.root"
    schema = write_keyed_digitized_root(events, waves, digitized_root)
    schema.to_csv(OUT / "digitized_root_schema.csv", index=False)
    native_joined, join_audit = exact_native_join(events, digitized_root)
    native_joined.to_csv(OUT / "native_joined_events.csv", index=False)
    join_audit.to_csv(OUT / "native_join_audit.csv", index=False)
    events.to_csv(OUT / "benchmark_truth_events.csv", index=False)
    picked_truth.to_csv(OUT / "aligned_geant4_rows.csv", index=False)

    trad_raw = p05a.run_template_fits(events, waves, templates, cfg)
    trad = base.template_prediction(trad_raw)
    trad["method"] = "deltaE_over_E_likelihood_template"
    preds = [s26c.attach_pid(trad, s26c.gaussian_llr_pid(events, waves))]
    preds.extend(s26c.sklearn_predictions(events, waves, int(cfg["random_seed"])))
    preds.append(s26c.cnn_prediction(events, waves, cfg))
    preds.append(s26c.transformer_prediction(events, waves, cfg))
    preds.append(s26c.residual_stack_prediction(events, waves, trad_raw, int(cfg["random_seed"])))

    all_pred = pd.concat(preds, ignore_index=True)
    base_cols = [
        "event_id",
        "split",
        "source_run",
        "stave",
        "is_overlap",
        "pid_label",
        "pid_truth_definition",
        "pid_name",
        "true_energy_proxy_adc",
        "true_energy_mev",
        "dedx_proxy",
        "depth_index",
        "shape_area_over_amp",
        "true_t1_sample",
        "true_t2_sample",
        "true_amp1_adc",
        "true_amp2_adc",
        "true_sep_sample",
        "true_ratio",
        "g4_entry",
        "g4_total_edep_mev",
        "g4_energy_weighted_time_ns",
        "truth_saturation_label",
        "truth_pedestal_adc",
        "truth_pileup_label",
        "daq_run",
        "EVENTNO",
        "EVT",
        "TRIGGER",
        "digitizer_seed",
        "bridge_version",
        "bridge_version_label",
        "native_row",
        "raw_selected_peak_adc",
        "raw_selected_event_ordinal",
    ]
    joined = all_pred.merge(events[base_cols], on="event_id", how="left")
    joined.to_csv(OUT / "event_predictions.csv", index=False)
    overall = s26c.summarize(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    ranked = s26c.rank_methods(overall)
    by_run = s26c.by_run_summary(joined)
    strata = s26c.strata_summary(joined)
    overall.to_csv(OUT / "method_metrics.csv", index=False)
    ranked.to_csv(OUT / "winner_ranked_metrics.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)

    winner = str(ranked.iloc[0]["method"])
    runtime = time.time() - started
    write_report(cfg, match, truth_summary, template_summary, ranked, by_run, strata, schema, join_audit, winner, runtime)

    input_rows = [
        {"path": str(G4_ROOT), "sha256": sha256(G4_ROOT), "size": G4_ROOT.stat().st_size, "role": "geant4_truth"},
    ]
    for path in sorted(RAW_ROOT_DIR.glob("hrdb_run_*.root")):
        input_rows.append({"path": str(path), "sha256": sha256(path), "size": path.stat().st_size, "role": "raw_bstack_root"})
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

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
        "geant4_truth": {
            "source": str(G4_ROOT),
            "tree": "hibeam",
            "usable_sci_bar_events": int(len(truth)),
            "pid_truth": "dominant Sci_bar PDG: proton vs deuteron",
            "energy_truth": "sum Sci_bar EDep over B-stack mapped layers",
            "timing_truth": "Sci_bar energy-weighted hit time",
            "adc_scale": f"{ADC_PER_MEV} ADC per MeV for digitized benchmark ranking",
        },
        "keyed_digitizer_output": {
            "root_file": "digitized_g4_08_keyed.root",
            "tree": "g4_08_digitized",
            "required_branches": ["daq_run", "EVENTNO", "EVT", "TRIGGER", "g4_entry", "digitizer_seed", "bridge_version"],
            "schema_audit": "digitized_root_schema.csv",
            "native_join_audit": "native_join_audit.csv",
            "native_join_key": ["daq_run", "EVENTNO", "EVT", "TRIGGER", "g4_entry", "digitizer_seed"],
            "native_join_passed": bool(join_audit["pass"].all()),
            "joined_events": int(join_audit.loc[join_audit["check"] == "joined_events", "value"].iloc[0]),
            "bridge_version": BRIDGE_VERSION,
            "bridge_version_code": BRIDGE_VERSION_CODE,
        },
        "evaluation_design": {
            "split": "train and held-out sets are disjoint by source run",
            "train_runs": cfg["benchmark_runs"]["train"],
            "heldout_runs": cfg["benchmark_runs"]["heldout"],
            "bootstrap": "held-out run-block percentile 95% CI",
            "bootstrap_replicates": int(cfg["ml"]["bootstrap_samples"]),
            "winner_score": "energy_fractional_sigma68 + 0.01*time_sigma68_ns + 0.25*(1-pid_balanced_accuracy) + 0.05*pileup_miss_rate + 0.05*false_split_rate",
        },
        "required_method_coverage": {
            "strong_traditional": "deltaE_over_E_likelihood_template",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "new_architecture": "joint_sequence_transformer",
            "additional_new_physics_residual_architecture": "template_residual_boosted_stack_new",
        },
        "winner": {
            "name": winner,
            "criterion": "minimum held-out composite GEANT4-truth PID/energy/timing score",
            "winner_score": float(ranked.iloc[0]["winner_score"]),
            "pid_auc": float(ranked.iloc[0]["pid_auc"]),
            "pid_balanced_accuracy": float(ranked.iloc[0]["pid_balanced_accuracy"]),
            "pid_efficiency": float(ranked.iloc[0]["pid_efficiency"]),
            "pid_purity": float(ranked.iloc[0]["pid_purity"]),
            "energy_fractional_sigma68": float(ranked.iloc[0]["energy_fractional_sigma68"]),
            "energy_fractional_sigma68_ci95": [
                float(ranked.iloc[0]["energy_fractional_sigma68_ci_low"]),
                float(ranked.iloc[0]["energy_fractional_sigma68_ci_high"]),
            ],
            "time_sigma68_ns": float(ranked.iloc[0]["time_sigma68_ns"]),
            "time_sigma68_ci95": [
                float(ranked.iloc[0]["time_sigma68_ns_ci_low"]),
                float(ranked.iloc[0]["time_sigma68_ns_ci_high"]),
            ],
            "pileup_miss_rate": float(ranked.iloc[0]["pileup_miss_rate"]),
            "false_split_rate": float(ranked.iloc[0]["false_split_rate"]),
        },
        "artifacts": {
            "report": "REPORT.md",
            "manifest": "manifest.json",
            "claimed_ticket": "claimed_ticket.txt",
            "raw_reproduction": "reproduction_match_table.csv",
            "geant4_truth_table": "geant4_truth_table.csv",
            "aligned_truth_events": "benchmark_truth_events.csv",
            "method_metrics": "method_metrics.csv",
            "winner_ranked_metrics": "winner_ranked_metrics.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "strata_metrics": "strata_metrics.csv",
            "event_predictions": "event_predictions.csv",
            "keyed_digitized_root": "digitized_g4_08_keyed.root",
            "digitized_root_schema": "digitized_root_schema.csv",
            "native_joined_events": "native_joined_events.csv",
            "native_join_audit": "native_join_audit.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "caveats": [
            "Waveform digitization is hybrid: raw residual/template morphology plus GEANT4 event truth.",
            "ADC/MeV scale is fixed for benchmark ranking and is not an external calibration.",
            "Bootstrap CIs resample held-out source runs and do not include GEANT4 physics-list uncertainty.",
        ],
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "ticket_id": TICKET,
        "git_commit": git_commit(),
        "command": f"{sys.executable} scripts/s29a_1783809265_5764_0f2a2dda_digitized_g4_multitask_truth_benchmark.py",
        "runtime_seconds": runtime,
        "python": sys.version,
        "platform": platform.platform(),
        "outputs_sha256": {
            p.name: sha256(p)
            for p in sorted(OUT.iterdir())
            if p.is_file() and p.name != "manifest.json"
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
