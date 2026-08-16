#!/usr/bin/env python3
"""G4-08 native event-id bridge audit and run-keyed closure benchmark."""

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
import s29a_1783809265_5764_0f2a2dda_digitized_g4_multitask_truth_benchmark as s29a  # noqa: E402

try:
    import uproot
except Exception as exc:  # pragma: no cover
    uproot = None
    UPROOT_IMPORT_ERROR = repr(exc)
else:
    UPROOT_IMPORT_ERROR = ""


TICKET = "1783825724.33022.709b07a8"
SLUG = "g4_08_native_eventid_bridge"
WORKER = "testbeam-laptop-3"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/extracted/root/root")
G4_ROOT = Path("/home/billy/ccb-geant4/output_30k.root")


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def sha256(path: Path) -> str:
    return base.sha256_file(path)


def md_table(df: pd.DataFrame, cols: list[str]) -> str:
    view = df[cols].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    return view.to_markdown(index=False)


def load_config() -> dict:
    cfg = s29a.load_config()
    cfg.update(
        {
            "study_id": "G4-08",
            "ticket_id": TICKET,
            "title": "Native GEANT4-to-DAQ event-id bridge audit and run-keyed closure benchmark",
            "worker": WORKER,
            "output_dir": str(OUT),
            "raw_root_dir": str(RAW_ROOT_DIR),
            "geant4_truth_root": str(G4_ROOT),
            "random_seed": 2026071208,
        }
    )
    cfg["ml"].update({"bootstrap_samples": 320, "cnn_epochs": 78, "cnn_channels": 12, "max_iter": 230})
    return cfg


def raw_key_inventory(raw_dir: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(raw_dir.glob("hrdb_run_*.root")):
        run = int(path.stem.split("_run_")[-1])
        tree = uproot.open(path)["h101"]
        branches = set(tree.keys())
        cols = [c for c in ["EVENTNO", "EVT", "TRIGGER"] if c in branches]
        arrays = tree.arrays(cols, library="np") if cols else {}
        row = {
            "source": "daq_raw_root",
            "run": run,
            "path": str(path),
            "entries": int(tree.num_entries),
            "has_EVENTNO": "EVENTNO" in branches,
            "has_EVT": "EVT" in branches,
            "has_TRIGGER": "TRIGGER" in branches,
            "eventno_min": np.nan,
            "eventno_max": np.nan,
            "evt_min": np.nan,
            "evt_max": np.nan,
            "trigger_modes": "",
            "duplicate_EVENTNO": 0,
            "duplicate_EVT": 0,
        }
        if "EVENTNO" in arrays:
            eventno = np.asarray(arrays["EVENTNO"], dtype=np.int64)
            row["eventno_min"] = int(eventno.min()) if len(eventno) else np.nan
            row["eventno_max"] = int(eventno.max()) if len(eventno) else np.nan
            row["duplicate_EVENTNO"] = int(len(eventno) - len(np.unique(eventno)))
        if "EVT" in arrays:
            evt = np.asarray(arrays["EVT"], dtype=np.int64)
            row["evt_min"] = int(evt.min()) if len(evt) else np.nan
            row["evt_max"] = int(evt.max()) if len(evt) else np.nan
            row["duplicate_EVT"] = int(len(evt) - len(np.unique(evt)))
        if "TRIGGER" in arrays:
            trig = np.asarray(arrays["TRIGGER"], dtype=np.int64)
            vals, counts = np.unique(trig, return_counts=True)
            row["trigger_modes"] = ",".join(f"{int(v)}:{int(c)}" for v, c in zip(vals, counts))
        rows.append(row)
    return pd.DataFrame(rows)


def geant4_key_inventory(path: Path) -> pd.DataFrame:
    if uproot is None:
        raise RuntimeError("uproot unavailable: " + UPROOT_IMPORT_ERROR)
    tree = uproot.open(path)["hibeam"]
    branches = list(tree.keys())
    candidates = [b for b in branches if any(s in b.lower() for s in ["event", "evt", "trigger", "run", "spill"])]
    rows = [
        {
            "source": "geant4_root",
            "path": str(path),
            "tree": "hibeam",
            "entries": int(tree.num_entries),
            "branch_count": len(branches),
            "candidate_native_daq_key_branches": ",".join(candidates),
            "has_run": any(b.lower() == "run" for b in branches),
            "has_EVENTNO": "EVENTNO" in branches,
            "has_EVT": "EVT" in branches,
            "has_TRIGGER": "TRIGGER" in branches,
            "joinable_to_daq_native_keys": False,
        }
    ]
    return pd.DataFrame(rows)


def bridge_contract(raw_inv: pd.DataFrame, g4_inv: pd.DataFrame) -> pd.DataFrame:
    g4_row = g4_inv.iloc[0]
    checks = [
        ("run", True, bool(g4_row["has_run"]), "required to split by acquisition run"),
        ("EVENTNO", bool(raw_inv["has_EVENTNO"].all()), bool(g4_row["has_EVENTNO"]), "primary DAQ event counter"),
        ("EVT", bool(raw_inv["has_EVT"].all()), bool(g4_row["has_EVT"]), "secondary DAQ event or trigger key"),
        ("TRIGGER", bool(raw_inv["has_TRIGGER"].all()), bool(g4_row["has_TRIGGER"]), "DAQ trigger metadata"),
    ]
    rows = []
    for key, raw_ok, g4_ok, meaning in checks:
        rows.append(
            {
                "key": key,
                "daq_available": raw_ok,
                "geant4_available": g4_ok,
                "native_joinable": raw_ok and g4_ok,
                "meaning": meaning,
            }
        )
    return pd.DataFrame(rows)


def future_metadata_export_contract() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"field": "daq_run", "dtype": "int32", "required": True, "description": "HRD acquisition run number"},
            {"field": "EVENTNO", "dtype": "int64", "required": True, "description": "DAQ event counter copied from h101"},
            {"field": "EVT", "dtype": "int64", "required": True, "description": "DAQ event/trigger key copied from h101"},
            {"field": "TRIGGER", "dtype": "int32", "required": True, "description": "DAQ trigger word before any reduction"},
            {"field": "g4_entry", "dtype": "int64", "required": True, "description": "GEANT4 event index after simulation"},
            {"field": "digitizer_seed", "dtype": "uint64", "required": True, "description": "seed linking digitized windows to simulation event"},
            {"field": "bridge_version", "dtype": "string", "required": True, "description": "schema version for reproducible joins"},
        ]
    )


def add_pseudo_runs(truth: pd.DataFrame, runs: list[int]) -> pd.DataFrame:
    out = truth.sort_values("g4_entry").reset_index(drop=True).copy()
    n = len(runs)
    out["g4_pseudo_run_index"] = np.floor(np.linspace(0, n, len(out), endpoint=False)).astype(int)
    out["g4_pseudo_run_index"] = np.clip(out["g4_pseudo_run_index"], 0, n - 1)
    out["g4_pseudo_run"] = [runs[i] for i in out["g4_pseudo_run_index"].to_numpy(int)]
    return out


def align_run_keyed(events: pd.DataFrame, waveforms: np.ndarray, truth: pd.DataFrame, rng: np.random.Generator):
    out = events.copy().reset_index(drop=True)
    waves = waveforms.copy()
    rows = []
    eligible = truth[truth["pid_name"].isin(["proton", "deuteron"])].copy()
    if eligible.empty:
        eligible = truth.copy()
    by_run = {int(k): v.index.to_numpy() for k, v in eligible.groupby("g4_pseudo_run")}
    all_idx = eligible.index.to_numpy()
    for source_run in out["source_run"].to_numpy(int):
        pool = by_run.get(int(source_run), all_idx)
        rows.append(int(rng.choice(pool)))
    picked = truth.loc[rows].reset_index(drop=True)
    old_energy_adc = np.maximum(out["true_amp1_adc"].to_numpy(float) + out["true_amp2_adc"].to_numpy(float), 1.0)
    target_adc = np.clip(picked["g4_total_edep_mev"].to_numpy(float) * s29a.ADC_PER_MEV, 600.0, 16000.0)
    scale = np.clip(target_adc / old_energy_adc, 0.30, 3.50)
    pedestal = np.median(waves[:, :4], axis=1, keepdims=True)
    waves = pedestal + (waves - pedestal) * scale[:, None]
    out["true_amp1_adc"] = out["true_amp1_adc"].to_numpy(float) * scale
    out["true_amp2_adc"] = out["true_amp2_adc"].to_numpy(float) * scale
    out["pid_label"] = picked["pid_label"].to_numpy(int)
    out["pid_truth_definition"] = "geant4_run_keyed_pseudo_bridge_dominant_sci_bar_pdg"
    out["pid_name"] = picked["pid_name"].to_numpy()
    out["g4_entry"] = picked["g4_entry"].to_numpy(int)
    out["g4_pseudo_run"] = picked["g4_pseudo_run"].to_numpy(int)
    out["g4_total_edep_mev"] = picked["g4_total_edep_mev"].to_numpy(float)
    out["g4_dominant_edep_mev"] = picked["g4_dominant_edep_mev"].to_numpy(float)
    out["g4_energy_weighted_time_ns"] = picked["g4_energy_weighted_time_ns"].to_numpy(float)
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


def write_report(cfg, match, raw_inv, g4_inv, contract, export_contract, truth_summary, template_summary, ranked, by_run, strata, alignment, winner, runtime):
    best = ranked.iloc[0]
    trad = ranked[ranked["method"] == "deltaE_over_E_likelihood_template"].iloc[0]
    text = f"""# G4-08: native GEANT4-to-DAQ event-id bridge audit and run-keyed closure benchmark

## Abstract

Ticket `{TICKET}` asked for a native event-id bridge or trigger metadata export pairing
GEANT4 digitized windows to DAQ `EVENTNO`/`EVT`/`TRIGGER` keys, followed by a
run-keyed closure benchmark that separates deterministic-overlay alignment uncertainty
from electronics-transfer residuals. The raw ROOT reproduction gate passes exactly:
`{int(match.iloc[0]['reproduced'])}` selected B-stave pulses versus the reference
`{int(match.iloc[0]['report_value'])}`, delta `{int(match.iloc[0]['delta'])}`.

The visible inputs do **not** contain a positive native event-id bridge: DAQ ROOT files
contain `EVENTNO`, `EVT`, and `TRIGGER`, but the GEANT4 `hibeam` tree contains no run,
event, EVT, or trigger branch. This report therefore builds the missing bridge contract
as a machine-readable metadata export specification and reruns the closure benchmark
with the strongest currently possible non-deterministic substitute: a run-keyed
GEANT4 pseudo-bridge that samples truth rows only within source-run-matched simulation
blocks rather than assigning exact deterministic event overlays.

The benchmark winner is **`{winner}`** by the predeclared composite score

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.25 (1 - BAcc_PID,m) + 0.05 r_miss,m + 0.05 r_false,m`.

It obtains energy sigma68 `{best['energy_fractional_sigma68']:.4g}` with 95% run-block
bootstrap CI [{best['energy_fractional_sigma68_ci_low']:.4g},
{best['energy_fractional_sigma68_ci_high']:.4g}], timing sigma68
`{best['time_sigma68_ns']:.4g}` ns, and PID balanced accuracy
`{best['pid_balanced_accuracy']:.4g}`.

## Raw ROOT reproduction

The gate reads `{cfg['raw_root_dir']}/hrdb_run_*.root`, reshapes `h101/HRDv` to
event-channel-sample tensors, subtracts `b_c=median(x_c[0:4])`, and counts B2/B4/B6/B8
channels satisfying `max_t (x_c(t)-b_c)>1000 ADC`.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Native key audit

The DAQ-side reduced ROOT stream exposes the required event-key columns; all non-empty
visible B-stack entries have `TRIGGER=1`. The simulation-side tree does not expose any
DAQ join key. The necessary condition for a native bridge,

`K_DAQ = (run, EVENTNO, EVT, TRIGGER) == K_G4`,

therefore has zero satisfiable fields on the GEANT4 side.

{md_table(contract, ['key', 'daq_available', 'geant4_available', 'native_joinable', 'meaning'])}

GEANT4 branch inventory summary:

{md_table(g4_inv, ['tree', 'entries', 'branch_count', 'candidate_native_daq_key_branches', 'joinable_to_daq_native_keys'])}

The metadata export contract written in `future_metadata_export_contract.csv` is the
minimal native bridge that the digitizer should emit in the next production:

{md_table(export_contract, ['field', 'dtype', 'required', 'description'])}

## Run-keyed pseudo-bridge

Because a positive native bridge is impossible with the mounted files, this study
uses a conservative pseudo-bridge. GEANT4 truth rows are partitioned into contiguous
simulation blocks whose labels are mapped one-to-one to source runs. Raw-template
benchmark events from a given source run sample only from the matching GEANT4 block.
This removes exact deterministic event-overlay alignment while retaining run-level
composition constraints. The matched table records `(source_run, g4_pseudo_run, g4_entry)`.

{md_table(alignment, ['quantity', 'value'])}

GEANT4 truth summary:

{md_table(truth_summary, ['quantity', 'value'])}

## Methods

The traditional comparator is `deltaE_over_E_likelihood_template`, a bounded
two-pulse template/CFD reconstruction plus diagonal Gaussian PID likelihood. With
standardized features `z_j`,

`log p(z | y) = -1/2 sum_j [(z_j - mu_yj)^2 / sigma_yj^2 + log sigma_yj^2] + log pi_y`.

The required ML/NN panel is ridge, histogram gradient-boosted trees, MLP, and a
compact 1D-CNN. The new architecture is `joint_sequence_transformer`, and the
ticket also retains `template_residual_boosted_stack_new`, a physics-residual
stack that learns corrections to the traditional template output.

For event `i`, the GEANT4 energy target is

`E_i = sum_h EDep_ih`,

the timing target is

`t_i = (sum_h EDep_ih t_ih) / (sum_h EDep_ih)`,

and the reported robust residual widths are

`sigma68(e) = [Q_84(e)-Q_16(e)]/2`.

All scalers, templates, likelihood moments, and models are trained only on train
runs `{cfg['benchmark_runs']['train']}` and evaluated on held-out runs
`{cfg['benchmark_runs']['heldout']}`. Confidence intervals are percentile intervals
over `{int(cfg['ml']['bootstrap_samples'])}` held-out run-block bootstrap resamples.
Run id, DAQ event keys, and GEANT4 entry number are excluded from model features.

Train-only template summaries:

{md_table(template_summary, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

## Overall held-out results

{md_table(ranked, ['method', 'winner_score', 'pid_auc', 'pid_balanced_accuracy', 'pid_efficiency', 'pid_purity', 'energy_fractional_sigma68', 'energy_fractional_sigma68_ci_low', 'energy_fractional_sigma68_ci_high', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high', 'pileup_miss_rate', 'false_split_rate'])}

Relative to the traditional baseline, `{winner}` changes energy sigma68 by
`{best['energy_fractional_sigma68'] - trad['energy_fractional_sigma68']:.4g}`,
timing sigma68 by `{best['time_sigma68_ns'] - trad['time_sigma68_ns']:.4g}` ns,
and PID balanced accuracy by `{best['pid_balanced_accuracy'] - trad['pid_balanced_accuracy']:.4g}`.

## Run-held-out stability

{md_table(by_run, ['method', 'heldout_run', 'pid_balanced_accuracy', 'pid_efficiency', 'pid_purity', 'energy_fractional_sigma68', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'])}

## Strata and systematics

{md_table(strata, ['stratum', 'value', 'method', 'pid_balanced_accuracy', 'energy_fractional_sigma68', 'time_sigma68_ns', 'pileup_miss_rate'])}

Dominant systematics:

- Native bridge absence is a provenance limitation, not a modeling failure. The
  current GEANT4 file cannot prove event-by-event DAQ alignment.
- The run-keyed pseudo-bridge quantifies electronics-transfer residuals under
  run-composition constraints but still contains within-run GEANT4 assignment
  uncertainty.
- ADC/MeV conversion is fixed for ranking and should not be interpreted as an
  external energy calibration.
- Bootstrap CIs cover held-out run variation, not GEANT4 physics-list, material,
  light-yield, or trigger-emulation uncertainty.
- A future positive bridge must persist `daq_run`, `EVENTNO`, `EVT`, `TRIGGER`,
  `g4_entry`, `digitizer_seed`, and `bridge_version` before digitization.

## Conclusion

G4-08 is a negative native-bridge result with a concrete export path. The visible
DAQ ROOT files provide the needed event keys, but the visible GEANT4 ROOT file does
not. The report therefore writes a bridge contract and reruns the benchmark using
the best available non-deterministic run-keyed pseudo-bridge. Under that design,
`{winner}` is the named winner in `result.json`; the residuals should be interpreted
as run-keyed electronics-transfer performance plus remaining within-run alignment
uncertainty, not as a completed event-by-event GEANT4-to-DAQ closure.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    if uproot is None:
        raise RuntimeError("uproot unavailable: " + UPROOT_IMPORT_ERROR)
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-g4-08")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "claimed_ticket.txt").write_text(TICKET + "\n", encoding="utf-8")
    cfg = load_config()
    rng = np.random.default_rng(int(cfg["random_seed"]))

    match = p05a.reproduce_counts(cfg)
    match.to_csv(OUT / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    raw_inv = raw_key_inventory(RAW_ROOT_DIR)
    g4_inv = geant4_key_inventory(G4_ROOT)
    contract = bridge_contract(raw_inv, g4_inv)
    export_contract = future_metadata_export_contract()
    raw_inv.to_csv(OUT / "daq_event_key_inventory.csv", index=False)
    g4_inv.to_csv(OUT / "geant4_event_key_inventory.csv", index=False)
    contract.to_csv(OUT / "native_bridge_contract.csv", index=False)
    export_contract.to_csv(OUT / "future_metadata_export_contract.csv", index=False)

    truth = s29a.g4_truth_table(G4_ROOT)
    runs = cfg["benchmark_runs"]["train"] + cfg["benchmark_runs"]["heldout"]
    truth = add_pseudo_runs(truth, runs)
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

    clean = p05a.read_clean_pulses(cfg, runs, rng)
    templates, template_summary = p05a.build_templates(clean[clean["run"].isin(cfg["benchmark_runs"]["train"])], cfg)
    template_summary.to_csv(OUT / "template_summary.csv", index=False)
    train_events, train_waves = p05a.generate_benchmark(clean, templates, cfg, "train", cfg["benchmark_runs"]["train"], rng)
    held_events, held_waves = p05a.generate_benchmark(clean, templates, cfg, "heldout", cfg["benchmark_runs"]["heldout"], rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waves = np.vstack([train_waves, held_waves])
    events, waves, picked_truth = align_run_keyed(events, waves, truth, rng)
    events.to_csv(OUT / "benchmark_truth_events.csv", index=False)
    picked_truth.to_csv(OUT / "run_keyed_geant4_rows.csv", index=False)
    alignment = pd.DataFrame(
        [
            {"quantity": "alignment_policy", "value": "run_keyed_geant4_pseudo_bridge"},
            {"quantity": "exact_native_event_matches", "value": 0},
            {"quantity": "source_runs", "value": len(runs)},
            {"quantity": "matched_benchmark_events", "value": int(len(events))},
            {"quantity": "unique_geant4_entries_sampled", "value": int(picked_truth["g4_entry"].nunique())},
            {"quantity": "source_run_equals_g4_pseudo_run_fraction", "value": float((events["source_run"].to_numpy(int) == events["g4_pseudo_run"].to_numpy(int)).mean())},
        ]
    )
    alignment.to_csv(OUT / "alignment_policy_summary.csv", index=False)

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
        "g4_pseudo_run",
        "g4_total_edep_mev",
        "g4_energy_weighted_time_ns",
        "truth_saturation_label",
        "truth_pedestal_adc",
        "truth_pileup_label",
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
    write_report(cfg, match, raw_inv, g4_inv, contract, export_contract, truth_summary, template_summary, ranked, by_run, strata, alignment, winner, runtime)

    input_rows = [{"path": str(G4_ROOT), "sha256": sha256(G4_ROOT), "size": G4_ROOT.stat().st_size, "role": "geant4_truth"}]
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
        "native_bridge": {
            "positive_native_eventid_bridge_available": False,
            "reason": "GEANT4 hibeam tree has no run, EVENTNO, EVT, or TRIGGER branch.",
            "daq_key_inventory": "daq_event_key_inventory.csv",
            "geant4_key_inventory": "geant4_event_key_inventory.csv",
            "bridge_contract": "native_bridge_contract.csv",
            "future_metadata_export_contract": "future_metadata_export_contract.csv",
            "exact_native_event_matches": 0,
        },
        "alignment_policy": {
            "name": "run_keyed_geant4_pseudo_bridge",
            "description": "GEANT4 truth rows are sampled only within source-run-matched contiguous simulation blocks; no exact deterministic event overlay is used.",
            "summary_file": "alignment_policy_summary.csv",
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
            "method_metrics": "method_metrics.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "event_predictions": "event_predictions.csv",
            "bridge_contract": "native_bridge_contract.csv",
            "future_metadata_export_contract": "future_metadata_export_contract.csv",
        },
        "novel_tickets_appended": [
            {
                "ticket_id": "1783883140.39222.3c4045b1",
                "title": "Persist DAQ event keys in GEANT4 digitizer output",
                "body": "Add daq_run, EVENTNO, EVT, TRIGGER, g4_entry, digitizer_seed, and bridge_version branches to the GEANT4-to-HRD digitizer output, then rerun G4-08 as an exact native join rather than a run-keyed pseudo-bridge.",
            }
        ],
        "caveats": [
            "No visible GEANT4 ROOT branch stores DAQ event keys, so exact event-by-event closure is blocked.",
            "Run-keyed pseudo-bridge removes exact deterministic overlay but leaves within-run truth assignment uncertainty.",
            "Bootstrap CIs resample held-out source runs and do not include GEANT4 physics-list uncertainty.",
        ],
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "ticket_id": TICKET,
        "git_commit": git_commit(),
        "command": f"{sys.executable} scripts/g4_08_1783825724_33022_709b07a8_native_eventid_bridge.py",
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
    print(json.dumps({"report_dir": str(OUT), "winner": winner, "runtime_sec": runtime}, indent=2))


if __name__ == "__main__":
    main()
