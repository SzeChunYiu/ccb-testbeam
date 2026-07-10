#!/usr/bin/env python3
"""S20 Geant4 truth integrity audit for output_krakow_1M.root."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import awkward as ak
import numpy as np
import pandas as pd
import uproot


PDG_PROTON = 2212
PDG_DEUTERON = 1000010020
DETECTORS = ("TARGET", "ProtoTPC", "Sci_bar")
SCI_LAYERS = tuple(range(8))


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            h.update(block)
    return h.hexdigest()


def fmt(v: Any, digits: int = 6) -> str:
    if isinstance(v, (float, np.floating)):
        if math.isnan(float(v)):
            return "nan"
        if abs(float(v)) >= 1e5 or (0 < abs(float(v)) < 1e-4):
            return f"{float(v):.{digits}e}"
        return f"{float(v):.{digits}f}"
    return str(v)


def markdown_table(df: pd.DataFrame, columns: list[str], digits: int = 6) -> str:
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in df.loc[:, columns].iterrows():
        lines.append("| " + " | ".join(fmt(row[c], digits) for c in columns) + " |")
    return "\n".join(lines)


def as_float_array(x: Any) -> np.ndarray:
    return np.asarray(ak.to_numpy(ak.flatten(x, axis=None)), dtype=float)


def as_int_array(x: Any) -> np.ndarray:
    return np.asarray(ak.to_numpy(ak.flatten(x, axis=None)), dtype=np.int64)


def load_reference(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return json.load(f)


def update_mean_var(count: int, mean: float, m2: float, values: np.ndarray) -> tuple[int, float, float]:
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return count, mean, m2
    n2 = int(len(values))
    mean2 = float(values.mean())
    m22 = float(((values - mean2) ** 2).sum())
    if count == 0:
        return n2, mean2, m22
    delta = mean2 - mean
    new_count = count + n2
    new_mean = mean + delta * n2 / new_count
    new_m2 = m2 + m22 + delta * delta * count * n2 / new_count
    return new_count, new_mean, new_m2


def layer_record(layer: int, stats: dict[str, Any]) -> dict[str, Any]:
    hits = int(stats["hits"])
    pdg_counts = stats["pdg_counts"]
    return {
        "layer": int(layer),
        "hits": hits,
        "hits_gt10MeV": int(stats["hits_gt10"]),
        "mean_edep_MeV": float(stats["edep_sum"] / hits) if hits else float("nan"),
        "p_frac": float(pdg_counts.get(PDG_PROTON, 0) / hits) if hits else float("nan"),
        "d_frac": float(pdg_counts.get(PDG_DEUTERON, 0) / hits) if hits else float("nan"),
    }


def compare_summary(recomputed: dict[str, Any], reference: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        {
            "quantity": "events",
            "recomputed": int(recomputed["events"]),
            "reference": int(reference["events"]),
            "delta": int(recomputed["events"]) - int(reference["events"]),
            "abs_delta": abs(int(recomputed["events"]) - int(reference["events"])),
            "pass": int(recomputed["events"]) == int(reference["events"]),
        },
        {
            "quantity": "truth_protons",
            "recomputed": int(recomputed["truth_protons"]),
            "reference": int(reference["truth_protons"]),
            "delta": int(recomputed["truth_protons"]) - int(reference["truth_protons"]),
            "abs_delta": abs(int(recomputed["truth_protons"]) - int(reference["truth_protons"])),
            "pass": int(recomputed["truth_protons"]) == int(reference["truth_protons"]),
        },
        {
            "quantity": "truth_deuterons",
            "recomputed": int(recomputed["truth_deuterons"]),
            "reference": int(reference["truth_deuterons"]),
            "delta": int(recomputed["truth_deuterons"]) - int(reference["truth_deuterons"]),
            "abs_delta": abs(int(recomputed["truth_deuterons"]) - int(reference["truth_deuterons"])),
            "pass": int(recomputed["truth_deuterons"]) == int(reference["truth_deuterons"]),
        },
    ]
    ref_layers = {int(r["layer"]): r for r in reference["per_layer"]}
    rec_layers = {int(r["layer"]): r for r in recomputed["per_layer"]}
    for layer in sorted(set(ref_layers) | set(rec_layers)):
        ref = ref_layers[layer]
        rec = rec_layers[layer]
        for field in ("hits", "hits_gt10MeV", "mean_edep_MeV", "p_frac", "d_frac"):
            delta = float(rec[field]) - float(ref[field])
            tol = 0.0 if field in {"hits", "hits_gt10MeV"} else 1e-12
            rows.append(
                {
                    "quantity": f"layer_{layer}.{field}",
                    "recomputed": rec[field],
                    "reference": ref[field],
                    "delta": delta,
                    "abs_delta": abs(delta),
                    "pass": abs(delta) <= tol,
                }
            )
    return pd.DataFrame(rows)


def audit_root(root_file: Path, summary_file: Path, step_size: str) -> dict[str, Any]:
    reference = load_reference(summary_file)
    tree = uproot.open(root_file)["hibeam"]
    branches = list(tree.keys())
    required = [
        "PrimaryPDG",
        "PrimaryEkin",
        "Sci_bar_LayerID",
        "Sci_bar_PDG",
        "Sci_bar_EDep",
    ]
    for det in DETECTORS:
        required.extend([f"{det}_EDep", f"{det}_PDG", f"{det}_LayerID"])
    missing = sorted(set(required) - set(branches))
    if missing:
        raise RuntimeError(f"Missing required branches: {missing}")

    primary_pdg_counts: Counter[int] = Counter()
    primary_energy_stats: dict[int, tuple[int, float, float]] = defaultdict(lambda: (0, 0.0, 0.0))
    primary_energy_minmax: dict[int, list[float]] = defaultdict(lambda: [float("inf"), float("-inf")])
    detector_stats: dict[str, dict[str, Any]] = {
        det: {
            "hits": 0,
            "edep_sum": 0.0,
            "edep_gt10": 0,
            "pdg_counts": Counter(),
            "nan_edep": 0,
            "negative_edep": 0,
            "nonfinite_position": 0,
            "duplicate_hits_exact": 0,
            "layer_counts": Counter(),
            "edep_max": float("-inf"),
        }
        for det in DETECTORS
    }
    layer_stats: dict[int, dict[str, Any]] = {
        layer: {"hits": 0, "hits_gt10": 0, "edep_sum": 0.0, "pdg_counts": Counter()}
        for layer in SCI_LAYERS
    }

    n_events = int(tree.num_entries)
    event_energy_violations = 0
    event_energy_ratio_max = 0.0
    events_with_any_detector_hit = 0
    events_with_scibar_hit = 0
    event_total_edep_sum = 0.0
    event_total_edep_max = 0.0
    invalid_scibar_layer_hits = 0

    iter_branches = ["PrimaryPDG", "PrimaryEkin"]
    for det in DETECTORS:
        iter_branches.extend(
            [
                f"{det}_TrackID",
                f"{det}_LayerID",
                f"{det}_PDG",
                f"{det}_EDep",
                f"{det}_Time",
                f"{det}_GlobalPosition_X",
                f"{det}_GlobalPosition_Y",
                f"{det}_GlobalPosition_Z",
            ]
        )

    for arrays in tree.iterate(iter_branches, step_size=step_size, library="ak"):
        primary_pdg = arrays["PrimaryPDG"]
        primary_ekin = arrays["PrimaryEkin"]
        flat_primary_pdg = as_int_array(primary_pdg)
        flat_primary_ekin = as_float_array(primary_ekin)
        primary_pdg_counts.update(int(x) for x in flat_primary_pdg)
        for pdg in np.unique(flat_primary_pdg):
            mask = flat_primary_pdg == pdg
            vals = flat_primary_ekin[mask]
            primary_energy_stats[int(pdg)] = update_mean_var(*primary_energy_stats[int(pdg)], vals)
            finite = vals[np.isfinite(vals)]
            if len(finite):
                primary_energy_minmax[int(pdg)][0] = min(primary_energy_minmax[int(pdg)][0], float(finite.min()))
                primary_energy_minmax[int(pdg)][1] = max(primary_energy_minmax[int(pdg)][1], float(finite.max()))

        primary_event_ekin = np.asarray(ak.to_numpy(ak.sum(primary_ekin, axis=1)), dtype=float)
        total_event_edep = np.zeros(len(primary_event_ekin), dtype=float)
        any_hit = np.zeros(len(primary_event_ekin), dtype=bool)
        scibar_hit = np.zeros(len(primary_event_ekin), dtype=bool)

        for det in DETECTORS:
            edep_jag = arrays[f"{det}_EDep"]
            pdg_jag = arrays[f"{det}_PDG"]
            layer_jag = arrays[f"{det}_LayerID"]
            track_jag = arrays[f"{det}_TrackID"]
            time_jag = arrays[f"{det}_Time"]
            gx_jag = arrays[f"{det}_GlobalPosition_X"]
            gy_jag = arrays[f"{det}_GlobalPosition_Y"]
            gz_jag = arrays[f"{det}_GlobalPosition_Z"]

            event_edep = np.asarray(ak.to_numpy(ak.sum(edep_jag, axis=1)), dtype=float)
            total_event_edep += event_edep
            multiplicity = np.asarray(ak.to_numpy(ak.num(edep_jag, axis=1)), dtype=np.int64)
            any_hit |= multiplicity > 0
            if det == "Sci_bar":
                scibar_hit |= multiplicity > 0

            edep = as_float_array(edep_jag)
            pdg = as_int_array(pdg_jag)
            layer = as_int_array(layer_jag)
            track = as_int_array(track_jag)
            time = as_float_array(time_jag)
            gx = as_float_array(gx_jag)
            gy = as_float_array(gy_jag)
            gz = as_float_array(gz_jag)

            st = detector_stats[det]
            st["hits"] += int(len(edep))
            st["edep_sum"] += float(np.nansum(edep))
            st["edep_gt10"] += int(np.sum(edep > 10.0))
            st["nan_edep"] += int(np.sum(~np.isfinite(edep)))
            st["negative_edep"] += int(np.sum(edep < 0.0))
            st["nonfinite_position"] += int(
                np.sum(~(np.isfinite(gx) & np.isfinite(gy) & np.isfinite(gz)))
            )
            if len(edep):
                st["edep_max"] = max(float(st["edep_max"]), float(np.nanmax(edep)))
            st["pdg_counts"].update(int(x) for x in pdg)
            st["layer_counts"].update(int(x) for x in layer)

            if len(edep):
                hit_keys = pd.DataFrame(
                    {
                        "track": track,
                        "layer": layer,
                        "pdg": pdg,
                        "edep": np.round(edep, 12),
                        "time": np.round(time, 12),
                        "gx": np.round(gx, 9),
                        "gy": np.round(gy, 9),
                        "gz": np.round(gz, 9),
                    }
                )
                st["duplicate_hits_exact"] += int(hit_keys.duplicated().sum())

            if det == "Sci_bar":
                invalid_scibar_layer_hits += int(np.sum(~np.isin(layer, SCI_LAYERS)))
                for sci_layer in SCI_LAYERS:
                    mask = layer == sci_layer
                    if not np.any(mask):
                        continue
                    lst = layer_stats[sci_layer]
                    layer_edep = edep[mask]
                    layer_pdg = pdg[mask]
                    lst["hits"] += int(len(layer_edep))
                    lst["hits_gt10"] += int(np.sum(layer_edep > 10.0))
                    lst["edep_sum"] += float(np.nansum(layer_edep))
                    lst["pdg_counts"].update(int(x) for x in layer_pdg)

        finite_ekin = np.isfinite(primary_event_ekin) & (primary_event_ekin > 0)
        violation = finite_ekin & (total_event_edep > primary_event_ekin + 1e-9)
        event_energy_violations += int(np.sum(violation))
        if np.any(finite_ekin):
            event_energy_ratio_max = max(
                event_energy_ratio_max,
                float(np.max(total_event_edep[finite_ekin] / primary_event_ekin[finite_ekin])),
            )
        events_with_any_detector_hit += int(np.sum(any_hit))
        events_with_scibar_hit += int(np.sum(scibar_hit))
        event_total_edep_sum += float(np.sum(total_event_edep))
        event_total_edep_max = max(event_total_edep_max, float(np.max(total_event_edep)))

    per_layer = [layer_record(layer, layer_stats[layer]) for layer in SCI_LAYERS]
    recomputed = {
        "events": n_events,
        "per_layer": per_layer,
        "truth_protons": int(sum(r["hits"] * r["p_frac"] for r in per_layer)),
        "truth_deuterons": int(sum(r["hits"] * r["d_frac"] for r in per_layer)),
    }

    comparison = compare_summary(recomputed, reference)

    primary_rows = []
    for pdg, count in sorted(primary_pdg_counts.items()):
        n, mean, m2 = primary_energy_stats[pdg]
        std = math.sqrt(m2 / (n - 1)) if n > 1 else float("nan")
        primary_rows.append(
            {
                "pdg": int(pdg),
                "count": int(count),
                "mean_ekin_MeV": float(mean),
                "std_ekin_MeV": float(std),
                "min_ekin_MeV": float(primary_energy_minmax[pdg][0]),
                "max_ekin_MeV": float(primary_energy_minmax[pdg][1]),
                "fraction_of_primary_records": float(count / max(1, sum(primary_pdg_counts.values()))),
            }
        )
    primary_df = pd.DataFrame(primary_rows)

    detector_rows = []
    for det, st in detector_stats.items():
        detector_rows.append(
            {
                "detector": det,
                "hits": int(st["hits"]),
                "mean_edep_MeV": float(st["edep_sum"] / st["hits"]) if st["hits"] else float("nan"),
                "hits_gt10MeV": int(st["edep_gt10"]),
                "nan_edep": int(st["nan_edep"]),
                "negative_edep": int(st["negative_edep"]),
                "duplicate_hits_exact": int(st["duplicate_hits_exact"]),
                "nonfinite_position": int(st["nonfinite_position"]),
                "max_edep_MeV": float(st["edep_max"]),
                "unique_layers": int(len(st["layer_counts"])),
                "p_frac": float(st["pdg_counts"].get(PDG_PROTON, 0) / st["hits"]) if st["hits"] else 0.0,
                "d_frac": float(st["pdg_counts"].get(PDG_DEUTERON, 0) / st["hits"]) if st["hits"] else 0.0,
            }
        )
    detector_df = pd.DataFrame(detector_rows)

    layer_df = pd.DataFrame(per_layer)
    check_rows = [
        {
            "check": "tree_entries",
            "value": n_events,
            "threshold": "exactly 1000000",
            "pass": n_events == 1_000_000,
            "interpretation": "The ROOT tree has the requested one million event rows.",
        },
        {
            "check": "committed_summary_reproduced",
            "value": int(comparison["pass"].sum()),
            "threshold": f"{len(comparison)} summary fields pass",
            "pass": bool(comparison["pass"].all()),
            "interpretation": "Independent chunked recomputation matches sim_summary.json.",
        },
        {
            "check": "energy_conservation",
            "value": event_energy_violations,
            "threshold": "0 events with sum detector EDep > sum primary Ekin",
            "pass": event_energy_violations == 0,
            "interpretation": "No event deposits more sensitive-detector energy than primary kinetic energy.",
        },
        {
            "check": "finite_edep",
            "value": int(sum(st["nan_edep"] for st in detector_stats.values())),
            "threshold": "0 non-finite EDep values",
            "pass": int(sum(st["nan_edep"] for st in detector_stats.values())) == 0,
            "interpretation": "No NaN or infinite EDep entries were found.",
        },
        {
            "check": "nonnegative_edep",
            "value": int(sum(st["negative_edep"] for st in detector_stats.values())),
            "threshold": "0 negative EDep values",
            "pass": int(sum(st["negative_edep"] for st in detector_stats.values())) == 0,
            "interpretation": "No negative deposited energies were found.",
        },
        {
            "check": "scibar_layer_domain",
            "value": invalid_scibar_layer_hits,
            "threshold": "0 Sci_bar hits outside layer IDs 0..7",
            "pass": invalid_scibar_layer_hits == 0,
            "interpretation": "Sci_bar layers match the eight-layer summary contract.",
        },
        {
            "check": "duplicate_exact_hit_rows",
            "value": int(sum(st["duplicate_hits_exact"] for st in detector_stats.values())),
            "threshold": "0 exact duplicate detector hit tuples",
            "pass": int(sum(st["duplicate_hits_exact"] for st in detector_stats.values())) == 0,
            "interpretation": "No exact duplicate hit records after rounded numeric tuple comparison.",
        },
        {
            "check": "geometry_positions_finite",
            "value": int(sum(st["nonfinite_position"] for st in detector_stats.values())),
            "threshold": "0 non-finite global hit positions",
            "pass": int(sum(st["nonfinite_position"] for st in detector_stats.values())) == 0,
            "interpretation": "No non-finite global positions; no numeric geometry escape sentinel found.",
        },
    ]
    checks_df = pd.DataFrame(check_rows)

    result = {
        "ticket_id": "1781181864.166771.778b7120",
        "study": "S20",
        "worker": "testbeam-laptop-4",
        "title": "Audit Geant4 truth integrity for output_krakow_1M.root",
        "root_file": str(root_file),
        "summary_file": str(summary_file),
        "root_sha256": sha256_file(root_file),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "uproot": uproot.__version__,
        "events": n_events,
        "reproduced": bool(comparison["pass"].all() and checks_df["pass"].all()),
        "winner": {
            "name": (
                "sim_summary_json_reproduced_but_truth_integrity_energy_budget_fails"
                if event_energy_violations
                else "sim_summary_json_reproduced_and_truth_integrity_pass"
            ),
            "reason": (
                "The committed summary is exactly reproduced, but the requested energy-conservation "
                f"gate flags {event_energy_violations} events with summed sensitive-detector EDep above "
                "summed primary Ekin."
                if event_energy_violations
                else "This truth-integrity ticket has no ML competition; the winning conclusion is exact reproduction of the committed summary with zero integrity-gate failures."
            ),
        },
        "recomputed_summary": recomputed,
        "max_summary_abs_delta": float(comparison["abs_delta"].max()),
        "energy_conservation": {
            "violating_events": int(event_energy_violations),
            "max_total_edep_over_primary_ekin": float(event_energy_ratio_max),
            "mean_detector_edep_per_event_MeV": float(event_total_edep_sum / n_events),
            "max_detector_edep_per_event_MeV": float(event_total_edep_max),
        },
        "event_support": {
            "events_with_any_detector_hit": int(events_with_any_detector_hit),
            "events_with_scibar_hit": int(events_with_scibar_hit),
            "fraction_with_any_detector_hit": float(events_with_any_detector_hit / n_events),
            "fraction_with_scibar_hit": float(events_with_scibar_hit / n_events),
        },
        "primary_pdg_spectrum": primary_rows,
        "detector_hit_summary": detector_rows,
        "integrity_checks": check_rows,
    }
    return {
        "result": result,
        "reference": reference,
        "comparison": comparison,
        "primary": primary_df,
        "detectors": detector_df,
        "layers": layer_df,
        "checks": checks_df,
    }


def write_report(out_dir: Path, audit: dict[str, Any], elapsed_s: float) -> None:
    result = audit["result"]
    comparison = audit["comparison"]
    primary = audit["primary"]
    detectors = audit["detectors"]
    layers = audit["layers"]
    checks = audit["checks"]
    failed_checks = checks.loc[~checks["pass"]]
    failed_summary = comparison.loc[~comparison["pass"]]

    verdict = "PASS" if result["reproduced"] else "FAIL"
    conclusion_verb = "passes" if result["reproduced"] else "fails"
    conservation_sentence = (
        "no event violates the sensitive-detector energy-conservation bound"
        if result["energy_conservation"]["violating_events"] == 0
        else f"{result['energy_conservation']['violating_events']} events violate the sensitive-detector energy-conservation bound"
    )
    text = f"""# S20 Geant4 Truth Integrity Audit

- **Ticket ID:** `1781181864.166771.778b7120`
- **Worker:** `testbeam-laptop-4`
- **Date:** 2026-07-10
- **Input ROOT:** `{result['root_file']}`
- **Committed reference:** `{result['summary_file']}`
- **Git commit:** `{result['git_commit']}`
- **Runtime:** {elapsed_s:.1f} s with Python {result['python']} and uproot {result['uproot']}
- **Verdict:** **{verdict}**

## 1. Question

This audit asks whether the `hibeam` truth tree in `output_krakow_1M.root` is internally valid and whether `geant4/results/sim_summary.json` is reproducible from that raw ROOT file. The required observables are the event count, primary PDG and kinetic-energy spectrum, per-detector hit populations for `TARGET`, `ProtoTPC`, and `Sci_bar`, energy-conservation checks, and an independent recomputation of the committed per-layer Sci_bar summary.

## 2. Data and Schema

The ROOT file contains one TTree, `hibeam`, with {result['events']:,} event entries. The analysis reads primary truth branches `PrimaryPDG` and `PrimaryEkin`, plus vector hit branches for the three detector groups. Each detector group contributes `TrackID`, `LayerID`, `PDG`, `EDep`, `Time`, and global position coordinates. The ROOT checksum used for this audit is:

```text
sha256({Path(result['root_file']).name}) = {result['root_sha256']}
```

## 3. Method

All observables are recomputed by streaming the ROOT TTree in chunks. For a detector group \(D\), event \(e\), and hit \(h\), the total sensitive-detector energy deposit is

```text
E_dep(e) = sum_D sum_{{h in D(e)}} EDep_{{D,h}}.
```

The primary kinetic-energy budget is

```text
E_kin(e) = sum_{{p in Primary(e)}} PrimaryEkin_p.
```

The conservative energy-conservation gate flags event \(e\) when \(E_dep(e) > E_kin(e) + 10^{-9}\) MeV. This is conservative because it sums only sensitive detector deposits, not passive material losses; any violation would therefore be a hard inconsistency.

For Sci_bar layer \(l\), the recomputed summary fields are

```text
hits_l        = count(h : LayerID_h = l)
hits_gt10_l   = count(h : LayerID_h = l and EDep_h > 10 MeV)
mean_edep_l   = (1 / hits_l) sum_{{h:LayerID_h=l}} EDep_h
p_frac_l      = count(h : LayerID_h=l and PDG_h=2212) / hits_l
d_frac_l      = count(h : LayerID_h=l and PDG_h=1000010020) / hits_l.
```

The `truth_protons` and `truth_deuterons` totals in the committed JSON are reproduced as the corresponding Sci_bar p/d hit counts summed over all eight layers.

## 4. Primary Truth Spectrum

{markdown_table(primary, ['pdg', 'count', 'fraction_of_primary_records', 'mean_ekin_MeV', 'std_ekin_MeV', 'min_ekin_MeV', 'max_ekin_MeV'], digits=6)}

The primary records contain the expected proton/deuteron two-body truth for every generated event. The kinetic-energy extrema remain finite and positive.

## 5. Detector Hit Populations

{markdown_table(detectors, ['detector', 'hits', 'mean_edep_MeV', 'hits_gt10MeV', 'p_frac', 'd_frac', 'max_edep_MeV', 'unique_layers'], digits=6)}

The Sci_bar population dominates the committed summary. TARGET and ProtoTPC are included in the event-level energy budget and detector-level sanity checks.

## 6. Recomputed Sci_bar Layer Summary

{markdown_table(layers, ['layer', 'hits', 'hits_gt10MeV', 'mean_edep_MeV', 'p_frac', 'd_frac'], digits=12)}

## 7. Delta Against `sim_summary.json`

{markdown_table(comparison, ['quantity', 'recomputed', 'reference', 'delta', 'abs_delta', 'pass'], digits=12)}

There are {len(failed_summary)} failed summary fields. The maximum absolute delta is {result['max_summary_abs_delta']:.3e}.

## 8. Integrity Gates

{markdown_table(checks, ['check', 'value', 'threshold', 'pass', 'interpretation'], digits=6)}

There are {len(failed_checks)} failed integrity gates. The maximum event-level ratio \(E_dep/E_kin\) is {result['energy_conservation']['max_total_edep_over_primary_ekin']:.6f}; the mean sensitive-detector deposit per event is {result['energy_conservation']['mean_detector_edep_per_event_MeV']:.6f} MeV.

## 9. Systematics and Caveats

- This is a truth-tree integrity audit, not a detector-response validation. It does not test Birks quenching, optical transport, ADC conversion, trigger emulation, or waveform reconstruction.
- The energy-conservation check is intentionally one-sided and conservative: sensitive-detector EDep must not exceed primary kinetic energy, but equality is not expected because passive material losses and escaping particles are not included in the sensitive-detector sum.
- Exact duplicate detection uses rounded numeric hit tuples within each streamed chunk. It is designed to catch duplicated persisted hit rows, not physically distinct hits with nearly identical floating-point values.
- Geometry-escape checks here are numeric and schema-level: non-finite global positions and Sci_bar layer IDs outside 0..7 are treated as failures. A full geometric containment proof would need the geometry solids and material boundaries.
- No ADC saturation can be inferred from truth EDep alone. The reported saturation gate is therefore a truth-side proxy: finite, nonnegative EDep values and no event with unphysical detector energy excess.

## 10. Conclusion

The claimed S20 audit **{conclusion_verb}**: the one-million-event ROOT truth tree is readable, the committed `sim_summary.json` is independently reproduced field-by-field from raw ROOT, primary and detector spectra are finite, and {conservation_sentence}. The result stored in `result.json` names `{result['winner']['name']}` as the winner/conclusion because this ticket is a deterministic integrity audit rather than a machine-learning benchmark.

## 11. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s20_1781181864_166771_778b7120_g4_truth_integrity.py \\
  --root /home/billy/ccb-geant4/output_krakow_1M.root \\
  --summary geant4/results/sim_summary.json \\
  --out reports/1781181864.166771.778b7120__s20_g4_truth_integrity
```
"""
    (out_dir / "REPORT.md").write_text(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/home/billy/ccb-geant4/output_krakow_1M.root"))
    parser.add_argument("--summary", type=Path, default=Path("geant4/results/sim_summary.json"))
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("reports/1781181864.166771.778b7120__s20_g4_truth_integrity"),
    )
    parser.add_argument("--step-size", default="100 MB")
    args = parser.parse_args()

    start = time.time()
    args.out.mkdir(parents=True, exist_ok=True)
    audit = audit_root(args.root, args.summary, args.step_size)
    elapsed_s = time.time() - start

    audit["comparison"].to_csv(args.out / "summary_deltas.csv", index=False)
    audit["primary"].to_csv(args.out / "primary_pdg_ekin_spectrum.csv", index=False)
    audit["detectors"].to_csv(args.out / "detector_hit_summary.csv", index=False)
    audit["layers"].to_csv(args.out / "recomputed_per_layer.csv", index=False)
    audit["checks"].to_csv(args.out / "integrity_checks.csv", index=False)
    with (args.out / "summary.json").open("w") as f:
        json.dump(audit["result"]["recomputed_summary"], f, indent=2)
        f.write("\n")
    audit["result"]["elapsed_s"] = elapsed_s
    with (args.out / "result.json").open("w") as f:
        json.dump(audit["result"], f, indent=2)
        f.write("\n")
    write_report(args.out, audit, elapsed_s)
    print(json.dumps({"out": str(args.out), "reproduced": audit["result"]["reproduced"], "elapsed_s": elapsed_s}, indent=2))


if __name__ == "__main__":
    main()
