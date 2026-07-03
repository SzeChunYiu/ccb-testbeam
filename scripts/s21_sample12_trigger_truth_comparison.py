#!/usr/bin/env python3
"""
s21_sample12_trigger_truth_comparison.py
========================================
Truth-level Sample I vs Sample II comparison of the B-arm HRD stack for the
CCB (Krakow) test beam, using the INCLUSIVE trigger definitions.

Setup (physics brief, experiment owner):
  190 MeV protons on CD2. Two independent HRD scintillator stacks at conjugate
  angles (~100 cm from target): Stack A (TPC in front) and Stack B. They see
  DIFFERENT particles: pd-elastic sends the proton into one arm and the
  correlated deuteron into the other.

Trigger mimicry (via ccb_mc_validation.truth.trigger.process_chunk):
  Sample II (single-B trigger, INCLUSIVE): a charged particle enters the first
      B layer (Sci_bar_LayerID1==1, LayerID==0).
  Sample I  (A.B coincidence): additionally a charged particle enters the
      first A layer within |t_A - t_B| < 15 ns.
  NOTE: Sample I is a SUBSET of Sample II by construction.

Prediction under test (Matthias' earlier MC): Sample I should be
deuteron-ENRICHED relative to Sample II in the B stack -- large pulses
(high-dE/dx deuterons stopping early) in the first B stave (B2) for Sample I,
absent in Sample II -- because the A.B coincidence tags kinematically
correlated pd-elastic pairs.

Layer -> stave mapping (repo convention, UNDER REVIEW -- per-LayerID tables
are therefore reported alongside per-stave tables):
  B-arm LayerID {0,1}->B2, {2,3}->B4, {4,5}->B6, {6,7}->B8.

Outputs (one directory):
  s21_summary.json   -- all tables with n's
  s21_overview.png   -- multi-panel figure (occupancy, B2 spectra, deuteron
                        fraction per stave, Delta-E vs E, penetration depth)
  REPORT.md          -- tables, explicit verdict line, caveats

Usage:
  python3 s21_sample12_trigger_truth_comparison.py \
      --mc geant4/data/output_krakow_1M.root [--out DIR] [--max-events 0]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from ccb_mc_validation.truth.pdg import is_charged, mass_of, species_label  # noqa: E402
from ccb_mc_validation.truth.trigger import process_chunk, summarize_chunk  # noqa: E402

# ---------------------------------------------------------------------------
# Constants (kept local so the script only imports truth.trigger / truth.pdg)
# ---------------------------------------------------------------------------
B_ARM = 1  # Sci_bar_LayerID1 == 1 -> B stack
A_ARM = 2  # Sci_bar_LayerID1 == 2 -> A stack
N_B_LAYERS = 8
STAVES = ("B2", "B4", "B6", "B8")  # stave s covers LayerID {2s, 2s+1} -- UNDER REVIEW
SPECIES = ("p", "d", "other")  # proton 2212, deuteron 1000010020, other-charged
COINC_NS_DEFAULT = 15.0
MOMENTUM_GEV_TO_MEV = 1000.0  # Sci_bar_Momentum_* are GeV/c; masses are MeV
CONTAINMENT_FRAC = 0.8  # edep_tot >= 0.8 * entry ekin -> "contained"

# Histogram binning (per-track stave EDep, MeV)
EDEP_MAX_MEV = 300.0
N_EDEP_BINS = 600  # 0.5 MeV bins
# Delta-E (first B stave, l0+l1) vs E (total B edep) 2D histogram
DEE_X_MAX = 300.0
DEE_X_BINS = 60
DEE_Y_MAX = 150.0
DEE_Y_BINS = 50
SCATTER_CAP = 5000  # deterministic first-N reservoir per (sample, species) for plotting

BRANCHES = (
    "Sci_bar_LayerID",
    "Sci_bar_LayerID1",
    "Sci_bar_PDG",
    "Sci_bar_EDep",
    "Sci_bar_Time",
    "Sci_bar_TrackID",
    "Sci_bar_Momentum_X",
    "Sci_bar_Momentum_Y",
    "Sci_bar_Momentum_Z",
)


def species_class(pdg: int) -> str:
    """Collapse a (charged) PDG code into the p / d / other-charged classes."""
    pdg = int(pdg)
    if pdg == 2212:
        return "p"
    if pdg == 1000010020:
        return "d"
    return "other"


# ---------------------------------------------------------------------------
# Per-event track building (per-(event, track) grouping as in mv1_mv2)
# ---------------------------------------------------------------------------
def build_b_tracks(
    lay: np.ndarray,
    arm: np.ndarray,
    pdg: np.ndarray,
    edep: np.ndarray,
    tid: np.ndarray,
    px: np.ndarray,
    py: np.ndarray,
    pz: np.ndarray,
) -> list[dict]:
    """Per-track records for B-arm charged tracks of ONE event.

    Entry kinetic energy uses the momentum at the lowest-LayerID hit of the
    track, converted GeV/c -> MeV/c before mixing with MeV masses (the C3
    momentum-unit fix from EXTERNAL_REVIEW_2026-07-02.md).
    """
    records: list[dict] = []
    lay = np.asarray(lay).reshape(-1)
    arm = np.asarray(arm).reshape(-1)
    pdg = np.asarray(pdg).reshape(-1)
    edep = np.asarray(edep, dtype=np.float64).reshape(-1)
    tid = np.asarray(tid).reshape(-1)
    px = np.asarray(px, dtype=np.float64).reshape(-1)
    py = np.asarray(py, dtype=np.float64).reshape(-1)
    pz = np.asarray(pz, dtype=np.float64).reshape(-1)

    is_b = arm == B_ARM
    if not is_b.any():
        return records

    for tr in np.unique(tid[is_b]):
        m = is_b & (tid == tr)
        p0 = int(pdg[m][0])
        if not is_charged(p0):
            continue
        layers = lay[m].astype(np.int64)
        eds = edep[m]
        # entry hit = lowest LayerID; its momentum defines the entry ekin
        order = np.argsort(layers, kind="stable")
        entry_idx = int(np.where(m)[0][order[0]])
        pmag = (
            math.sqrt(px[entry_idx] ** 2 + py[entry_idx] ** 2 + pz[entry_idx] ** 2)
            * MOMENTUM_GEV_TO_MEV
        )
        mass = mass_of(p0)
        ekin = math.sqrt(pmag * pmag + mass * mass) - mass

        per_layer = np.zeros(N_B_LAYERS, dtype=np.float64)
        for l, e in zip(layers, eds):
            if 0 <= l < N_B_LAYERS:
                per_layer[int(l)] += float(e)
        edep_tot = float(eds.sum())
        hit_layers = np.nonzero(per_layer > 0.0)[0]
        deepest = int(hit_layers.max()) if hit_layers.size else -1
        contained = bool(ekin > 0.0 and edep_tot >= CONTAINMENT_FRAC * ekin)

        records.append(
            {
                "pdg": p0,
                "species": species_class(p0),
                "per_layer": per_layer,
                "edep_tot": edep_tot,
                "ekin": float(ekin),
                "deepest": deepest,
                "contained": contained,
            }
        )
    return records


def arm_entry_species(
    lay: np.ndarray,
    arm: np.ndarray,
    pdg: np.ndarray,
    tm: np.ndarray,
) -> dict:
    """Truth PID of first-layer charged entries into A and B for ONE event.

    Returns per-arm species-label lists (one per entering hit) plus the
    earliest-in-time entering species per arm ('none' when no entry) -- the
    latter drives the pd-pair mechanism table.
    """
    lay = np.asarray(lay).reshape(-1)
    arm = np.asarray(arm).reshape(-1)
    pdg = np.asarray(pdg).reshape(-1)
    tm = np.asarray(tm, dtype=np.float64).reshape(-1)
    charged = np.fromiter((is_charged(int(p)) for p in pdg), dtype=bool, count=len(pdg))
    out: dict = {}
    for name, arm_id in (("B", B_ARM), ("A", A_ARM)):
        entry = (arm == arm_id) & (lay == 0) & charged
        labels = [species_label(int(p)) for p in pdg[entry]]
        out[f"enter_{name}"] = labels
        if entry.any():
            first = int(np.where(entry)[0][np.argmin(tm[entry])])
            out[f"{name.lower()}_first"] = species_label(int(pdg[first]))
        else:
            out[f"{name.lower()}_first"] = "none"
    return out


# ---------------------------------------------------------------------------
# Accumulator (one per sample; Sample I events feed BOTH accumulators)
# ---------------------------------------------------------------------------
class SampleAccumulator:
    def __init__(self) -> None:
        self.n_events = 0
        self.n_tracks = {sp: 0 for sp in SPECIES}
        self.n_contained = {sp: 0 for sp in SPECIES}
        self.layer_occ = {sp: np.zeros(N_B_LAYERS, dtype=np.int64) for sp in SPECIES}
        self.stave_occ = {sp: np.zeros(len(STAVES), dtype=np.int64) for sp in SPECIES}
        self.deepest = {sp: np.zeros(N_B_LAYERS, dtype=np.int64) for sp in SPECIES}
        self.stave_edep_hist = {
            sp: np.zeros((len(STAVES), N_EDEP_BINS), dtype=np.int64) for sp in SPECIES
        }
        self.stave_edep_overflow = {sp: np.zeros(len(STAVES), dtype=np.int64) for sp in SPECIES}
        self.dee_hist = {
            sp: np.zeros((DEE_X_BINS, DEE_Y_BINS), dtype=np.int64) for sp in SPECIES
        }
        self.dee_scatter: dict[str, list[tuple[float, float]]] = {sp: [] for sp in SPECIES}
        self.enter_a_pid: Counter = Counter()
        self.enter_b_pid: Counter = Counter()
        self.pair_table: Counter = Counter()  # "b_first|a_first"

    def add_event(self, tracks: list[dict], entries: dict) -> None:
        self.n_events += 1
        for sp in entries["enter_A"]:
            self.enter_a_pid[sp] += 1
        for sp in entries["enter_B"]:
            self.enter_b_pid[sp] += 1
        self.pair_table[f"{entries['b_first']}|{entries['a_first']}"] += 1

        for t in tracks:
            sp = t["species"]
            self.n_tracks[sp] += 1
            self.n_contained[sp] += int(t["contained"])
            per_layer = t["per_layer"]
            hit = per_layer > 0.0
            self.layer_occ[sp][hit] += 1
            if t["deepest"] >= 0:
                self.deepest[sp][t["deepest"]] += 1
            for s in range(len(STAVES)):
                e = float(per_layer[2 * s] + per_layer[2 * s + 1])
                if e <= 0.0:
                    continue
                self.stave_occ[sp][s] += 1
                b = int(e / EDEP_MAX_MEV * N_EDEP_BINS)
                if b >= N_EDEP_BINS:
                    self.stave_edep_overflow[sp][s] += 1
                else:
                    self.stave_edep_hist[sp][s, b] += 1
            # Delta-E vs E: y = first-stave (l0+l1) edep, x = total B edep
            x = t["edep_tot"]
            y = float(per_layer[0] + per_layer[1])
            bx = min(int(x / DEE_X_MAX * DEE_X_BINS), DEE_X_BINS - 1)
            by = min(int(y / DEE_Y_MAX * DEE_Y_BINS), DEE_Y_BINS - 1)
            self.dee_hist[sp][bx, by] += 1  # top bins include overflow (clipped)
            if len(self.dee_scatter[sp]) < SCATTER_CAP:
                self.dee_scatter[sp].append((x, y))


def process_chunk_events(
    chunk: dict,
    flags: dict,
    acc_i: SampleAccumulator,
    acc_ii: SampleAccumulator,
) -> None:
    """Route each triggered event of a jagged chunk into the sample accumulators.

    Sample II is the superset: every Sample-II event is accumulated there, and
    Sample-I events are ADDITIONALLY accumulated into acc_i (inclusive samples).
    """
    L = chunk["Sci_bar_LayerID"]
    L1 = chunk["Sci_bar_LayerID1"]
    PD = chunk["Sci_bar_PDG"]
    ED = chunk["Sci_bar_EDep"]
    TM = chunk["Sci_bar_Time"]
    TID = chunk["Sci_bar_TrackID"]
    PX = chunk["Sci_bar_Momentum_X"]
    PY = chunk["Sci_bar_Momentum_Y"]
    PZ = chunk["Sci_bar_Momentum_Z"]
    sample_i = flags["sample_I"]
    sample_ii = flags["sample_II"]
    for i in range(len(L)):
        if not sample_ii[i]:
            continue
        tracks = build_b_tracks(L[i], L1[i], PD[i], ED[i], TID[i], PX[i], PY[i], PZ[i])
        entries = arm_entry_species(L[i], L1[i], PD[i], TM[i])
        acc_ii.add_event(tracks, entries)
        if sample_i[i]:
            acc_i.add_event(tracks, entries)


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------
Z95 = 1.959963984540054


def wilson_ci(k: int, n: int, z: float = Z95) -> tuple[float, float, float]:
    """(fraction, ci_low, ci_high) -- Wilson score interval."""
    if n <= 0:
        return float("nan"), float("nan"), float("nan")
    phat = k / n
    denom = 1.0 + z * z / n
    centre = (phat + z * z / (2.0 * n)) / denom
    half = z * math.sqrt(phat * (1.0 - phat) / n + z * z / (4.0 * n * n)) / denom
    return phat, max(0.0, centre - half), min(1.0, centre + half)


def enrichment_ratio(k1: int, n1: int, k2: int, n2: int) -> dict:
    """Ratio (k1/n1)/(k2/n2) with a log-normal binomial 95% CI.

    var(ln f) ~= (1-f)/(n f) per binomial fraction; the two fractions are
    treated as independent, which is only approximate when sample 1 is a
    subset of sample 2 (flagged by the caller in the caveats).
    """
    out = {"k1": int(k1), "n1": int(n1), "k2": int(k2), "n2": int(n2)}
    if n1 <= 0 or n2 <= 0 or k1 <= 0 or k2 <= 0:
        out.update({"ratio": float("nan"), "ci_low": float("nan"), "ci_high": float("nan")})
        return out
    f1, f2 = k1 / n1, k2 / n2
    r = f1 / f2
    se_ln = math.sqrt((1.0 - f1) / k1 + (1.0 - f2) / k2)
    out.update(
        {
            "f1": f1,
            "f2": f2,
            "ratio": r,
            "ci_low": r * math.exp(-Z95 * se_ln),
            "ci_high": r * math.exp(Z95 * se_ln),
        }
    )
    return out


def quantile_from_hist(counts: np.ndarray, bin_width: float, q: float) -> float:
    """Linear-interpolated quantile from equal-width histogram counts."""
    counts = np.asarray(counts, dtype=np.float64)
    total = counts.sum()
    if total <= 0:
        return float("nan")
    target = q * total
    cum = np.cumsum(counts)
    b = int(np.searchsorted(cum, target))
    if b >= len(counts):
        return len(counts) * bin_width
    prev = cum[b - 1] if b > 0 else 0.0
    frac = (target - prev) / max(counts[b], 1e-12)
    return (b + frac) * bin_width


def hist_stats(counts: np.ndarray, overflow: int, bin_width: float) -> dict:
    n = int(np.asarray(counts).sum()) + int(overflow)
    med = quantile_from_hist(counts, bin_width, 0.5)
    q16 = quantile_from_hist(counts, bin_width, 0.16)
    q84 = quantile_from_hist(counts, bin_width, 0.84)
    return {
        "n": n,
        "n_overflow": int(overflow),
        "median_MeV": med,
        "q16_MeV": q16,
        "q84_MeV": q84,
        "sigma68_MeV": (q84 - q16) / 2.0 if not (math.isnan(q84) or math.isnan(q16)) else float("nan"),
    }


# ---------------------------------------------------------------------------
# Summary / report construction
# ---------------------------------------------------------------------------
def summarize_sample(acc: SampleAccumulator) -> dict:
    n_charged = sum(acc.n_tracks.values())
    bin_width = EDEP_MAX_MEV / N_EDEP_BINS
    out: dict = {
        "n_events": acc.n_events,
        "n_charged_b_tracks": n_charged,
        "n_tracks": dict(acc.n_tracks),
        "contained_fraction": {
            sp: (acc.n_contained[sp] / acc.n_tracks[sp] if acc.n_tracks[sp] else float("nan"))
            for sp in SPECIES
        },
    }
    # per-layer occupancy (tracks with edep>0 in that LayerID)
    layer_tab = {}
    for l in range(N_B_LAYERS):
        counts = {sp: int(acc.layer_occ[sp][l]) for sp in SPECIES}
        tot = sum(counts.values())
        layer_tab[l] = {
            "counts": counts,
            "n_total": tot,
            "fractions": {sp: (counts[sp] / tot if tot else float("nan")) for sp in SPECIES},
        }
    out["layer_occupancy"] = layer_tab
    # per-stave occupancy + edep stats + deuteron fraction
    stave_tab = {}
    for s, name in enumerate(STAVES):
        counts = {sp: int(acc.stave_occ[sp][s]) for sp in SPECIES}
        tot = sum(counts.values())
        frac_d, lo_d, hi_d = wilson_ci(counts["d"], tot)
        stave_tab[name] = {
            "counts": counts,
            "n_total": tot,
            "fractions": {sp: (counts[sp] / tot if tot else float("nan")) for sp in SPECIES},
            "deuteron_fraction": frac_d,
            "deuteron_fraction_ci95": [lo_d, hi_d],
            "edep_stats": {
                sp: hist_stats(acc.stave_edep_hist[sp][s], acc.stave_edep_overflow[sp][s], bin_width)
                for sp in SPECIES
            },
        }
    out["stave_occupancy"] = stave_tab
    # penetration depth (deepest layer with edep>0)
    out["penetration_depth"] = {
        sp: {
            "counts": acc.deepest[sp].tolist(),
            "fractions": (
                (acc.deepest[sp] / acc.deepest[sp].sum()).tolist()
                if acc.deepest[sp].sum()
                else [float("nan")] * N_B_LAYERS
            ),
        }
        for sp in SPECIES
    }
    # entering-arm truth PID
    for arm_name, ctr in (("A", acc.enter_a_pid), ("B", acc.enter_b_pid)):
        tot = sum(ctr.values())
        out[f"enter_{arm_name}_pid"] = {
            "counts": dict(sorted(ctr.items(), key=lambda kv: -kv[1])),
            "fractions": {
                k: v / tot for k, v in sorted(ctr.items(), key=lambda kv: -kv[1])
            }
            if tot
            else {},
        }
    # pd-pair mechanism table (earliest entering species per arm)
    tot_pairs = sum(acc.pair_table.values())
    out["entry_pair_table"] = {
        "counts": dict(sorted(acc.pair_table.items(), key=lambda kv: -kv[1])),
        "fractions": {
            k: v / tot_pairs for k, v in sorted(acc.pair_table.items(), key=lambda kv: -kv[1])
        }
        if tot_pairs
        else {},
    }
    # Delta-E vs E 2D histograms
    out["dee_hist"] = {
        "x_edges_MeV": np.linspace(0.0, DEE_X_MAX, DEE_X_BINS + 1).tolist(),
        "y_edges_MeV": np.linspace(0.0, DEE_Y_MAX, DEE_Y_BINS + 1).tolist(),
        "note": "x = total B-arm track EDep, y = first-stave (LayerID 0+1) EDep; top bins include clipped overflow",
        "counts": {sp: acc.dee_hist[sp].tolist() for sp in SPECIES},
    }
    # per-stave edep histograms (for replotting)
    out["stave_edep_hist"] = {
        "bin_edges_MeV": np.linspace(0.0, EDEP_MAX_MEV, N_EDEP_BINS + 1).tolist(),
        "counts": {
            name: {sp: acc.stave_edep_hist[sp][s].tolist() for sp in SPECIES}
            for s, name in enumerate(STAVES)
        },
        "overflow": {
            name: {sp: int(acc.stave_edep_overflow[sp][s]) for sp in SPECIES}
            for s, name in enumerate(STAVES)
        },
    }
    return out


def build_key_table(acc_i: SampleAccumulator, acc_ii: SampleAccumulator) -> dict:
    """Deuteron fraction per stave, Sample I vs II, plus enrichment ratios.

    Because Sample I is a subset of Sample II the inclusive ratio's binomial
    errors are correlated; the exclusive comparison (I vs II-minus-I) uses
    disjoint events and is statistically independent -- both are reported.
    """
    key: dict = {"staves": {}}
    for s, name in enumerate(STAVES):
        k_i = int(acc_i.stave_occ["d"][s])
        n_i = int(sum(acc_i.stave_occ[sp][s] for sp in SPECIES))
        k_ii = int(acc_ii.stave_occ["d"][s])
        n_ii = int(sum(acc_ii.stave_occ[sp][s] for sp in SPECIES))
        f_i, lo_i, hi_i = wilson_ci(k_i, n_i)
        f_ii, lo_ii, hi_ii = wilson_ci(k_ii, n_ii)
        # exclusive complement II\I (valid because Sample-I events contribute
        # identical track records to both accumulators)
        k_ex, n_ex = k_ii - k_i, n_ii - n_i
        f_ex, lo_ex, hi_ex = wilson_ci(k_ex, n_ex)
        key["staves"][name] = {
            "sample_I": {"k_d": k_i, "n": n_i, "fraction": f_i, "ci95": [lo_i, hi_i]},
            "sample_II": {"k_d": k_ii, "n": n_ii, "fraction": f_ii, "ci95": [lo_ii, hi_ii]},
            "sample_II_excl_I": {"k_d": k_ex, "n": n_ex, "fraction": f_ex, "ci95": [lo_ex, hi_ex]},
            "enrichment_I_over_II_inclusive": enrichment_ratio(k_i, n_i, k_ii, n_ii),
            "enrichment_I_over_II_exclusive": enrichment_ratio(k_i, n_i, k_ex, n_ex),
        }
    b2 = key["staves"]["B2"]
    r = b2["enrichment_I_over_II_inclusive"]
    enriched = (not math.isnan(r.get("ci_low", float("nan")))) and r["ci_low"] > 1.0
    key["verdict_B2"] = {
        "enriched": bool(enriched),
        "ratio": r.get("ratio", float("nan")),
        "ci95": [r.get("ci_low", float("nan")), r.get("ci_high", float("nan"))],
        "exclusive_ratio": b2["enrichment_I_over_II_exclusive"].get("ratio", float("nan")),
        "exclusive_ci95": [
            b2["enrichment_I_over_II_exclusive"].get("ci_low", float("nan")),
            b2["enrichment_I_over_II_exclusive"].get("ci_high", float("nan")),
        ],
    }
    return key


CAVEATS = [
    "Truth-level only: EDep is used as the pulse-amplitude proxy; no digitizer, "
    "no threshold, no saturation, no Birks quenching. Data-facing amplitudes will differ.",
    "The LayerID->stave mapping ({0,1}->B2, {2,3}->B4, {4,5}->B6, {6,7}->B8) is a repo "
    "convention UNDER REVIEW; per-LayerID (0-7) tables are reported so conclusions can be "
    "re-derived under an alternative mapping (e.g. odd-layers-unread).",
    "Upstream beamline material is missing from the geometry (MV3/MV3b): absolute "
    "penetration depths and stave energies are biased toward deeper/through-going tracks. "
    "Enrichment RATIOS between Sample I and Sample II (same geometry, same bias) are more "
    "robust than any absolute fraction quoted here.",
    "Sample I is a subset of Sample II (inclusive definitions), so the inclusive "
    "enrichment ratio's binomial errors are positively correlated (CI conservative in the "
    "usual direction but not exact); the exclusive I vs II-minus-I comparison uses disjoint "
    "events and is reported alongside.",
    "Entry kinetic energy converts GeV/c momenta to MeV/c (C3 fix); containment is a "
    "heuristic flag (edep_tot >= 0.8*ekin) and punch-through tracks make 'deepest layer' "
    "an underestimate of true range.",
]


def render_report(summary: dict, out_dir: Path) -> str:
    s_i = summary["samples"]["I"]
    s_ii = summary["samples"]["II"]
    key = summary["key_table"]
    v = key["verdict_B2"]
    lines: list[str] = []
    lines.append("# S21 — Sample I vs Sample II trigger-truth comparison (B arm)")
    lines.append("")
    lines.append(f"- MC file: `{summary['mc_file']}` (tree `{summary['tree']}`)")
    lines.append(f"- Events read: {summary['n_events_read']:,}; coincidence window {summary['coinc_ns']} ns")
    tc = summary["trigger_counts"]
    lines.append(
        f"- Trigger counts: enter_B={tc['enter_B']:,}, enter_A={tc['enter_A']:,}, "
        f"Sample I={tc['sample_I']:,}, Sample II={tc['sample_II']:,} "
        f"(inclusive; Sample I ⊂ Sample II)"
    )
    lines.append(f"- Generated: {summary['generated_utc']} by `scripts/s21_sample12_trigger_truth_comparison.py`")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    verdict = "YES" if v["enriched"] else "NO"
    lines.append(
        f"**Sample I deuteron-enriched in B2: {verdict} "
        f"(ratio {v['ratio']:.3f}, 95% CI [{v['ci95'][0]:.3f}, {v['ci95'][1]:.3f}]; "
        f"exclusive I vs II\\I ratio {v['exclusive_ratio']:.3f}, "
        f"95% CI [{v['exclusive_ci95'][0]:.3f}, {v['exclusive_ci95'][1]:.3f}])**"
    )
    lines.append("")
    lines.append("## Key table — deuteron fraction per stave (charged B-arm tracks occupying the stave)")
    lines.append("")
    lines.append(
        "| Stave | f_d Sample I (95% CI) | n_I | f_d Sample II (95% CI) | n_II | "
        "ratio I/II (95% CI) | ratio I/(II\\I) (95% CI) |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for name in STAVES:
        st = key["staves"][name]
        si, sii = st["sample_I"], st["sample_II"]
        ri = st["enrichment_I_over_II_inclusive"]
        rx = st["enrichment_I_over_II_exclusive"]

        def _fmt_ratio(r: dict) -> str:
            if math.isnan(r.get("ratio", float("nan"))):
                return "n/a"
            return f"{r['ratio']:.3f} [{r['ci_low']:.3f}, {r['ci_high']:.3f}]"

        lines.append(
            f"| {name} | {si['fraction']:.4f} [{si['ci95'][0]:.4f}, {si['ci95'][1]:.4f}] | {si['n']:,} "
            f"| {sii['fraction']:.4f} [{sii['ci95'][0]:.4f}, {sii['ci95'][1]:.4f}] | {sii['n']:,} "
            f"| {_fmt_ratio(ri)} | {_fmt_ratio(rx)} |"
        )
    lines.append("")

    for sname, s in (("I", s_i), ("II", s_ii)):
        lines.append(f"## Sample {sname} (inclusive) — n_events = {s['n_events']:,}, charged B tracks = {s['n_charged_b_tracks']:,}")
        lines.append("")
        lines.append("### Per-stave occupancy by species")
        lines.append("")
        lines.append("| Stave | n_p | n_d | n_other | f_p | f_d | f_other | d EDep med [MeV] | d σ68 | p EDep med [MeV] | p σ68 |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for name in STAVES:
            st = s["stave_occupancy"][name]
            c, f = st["counts"], st["fractions"]
            ed, ep = st["edep_stats"]["d"], st["edep_stats"]["p"]
            lines.append(
                f"| {name} | {c['p']:,} | {c['d']:,} | {c['other']:,} "
                f"| {f['p']:.4f} | {f['d']:.4f} | {f['other']:.4f} "
                f"| {ed['median_MeV']:.1f} | {ed['sigma68_MeV']:.1f} "
                f"| {ep['median_MeV']:.1f} | {ep['sigma68_MeV']:.1f} |"
            )
        lines.append("")
        lines.append("### Per-LayerID occupancy by species (mapping-independent)")
        lines.append("")
        lines.append("| LayerID | n_p | n_d | n_other | f_p | f_d | f_other |")
        lines.append("|---|---|---|---|---|---|---|")
        for l in range(N_B_LAYERS):
            row = s["layer_occupancy"][l]
            c, f = row["counts"], row["fractions"]
            lines.append(
                f"| {l} | {c['p']:,} | {c['d']:,} | {c['other']:,} "
                f"| {f['p']:.4f} | {f['d']:.4f} | {f['other']:.4f} |"
            )
        lines.append("")
        lines.append("### Penetration depth (deepest LayerID with EDep>0), fraction of tracks")
        lines.append("")
        lines.append("| Species | " + " | ".join(f"L{l}" for l in range(N_B_LAYERS)) + " |")
        lines.append("|---|" + "---|" * N_B_LAYERS)
        for sp in SPECIES:
            fr = s["penetration_depth"][sp]["fractions"]
            lines.append(
                f"| {sp} | " + " | ".join(("n/a" if math.isnan(x) else f"{x:.4f}") for x in fr) + " |"
            )
        lines.append("")
        lines.append("### Truth PID entering each arm (first-layer charged entries)")
        lines.append("")
        for arm_name in ("B", "A"):
            pid = s[f"enter_{arm_name}_pid"]
            top = list(pid["counts"].items())[:8]
            row = ", ".join(f"{k}: {v:,} ({pid['fractions'][k]:.4f})" for k, v in top)
            lines.append(f"- enter {arm_name}: {row if row else 'none'}")
        lines.append("")
        lines.append("### Entry-pair table (earliest entering species: B | A)")
        lines.append("")
        lines.append("| B entry | A entry | n | fraction |")
        lines.append("|---|---|---|---|")
        pt = s["entry_pair_table"]
        for k, n in list(pt["counts"].items())[:10]:
            bsp, asp = k.split("|")
            lines.append(f"| {bsp} | {asp} | {n:,} | {pt['fractions'][k]:.4f} |")
        lines.append("")
        cf = s["contained_fraction"]
        lines.append(
            f"Containment (edep_tot ≥ {CONTAINMENT_FRAC}·ekin): "
            + ", ".join(
                f"{sp}: {cf[sp]:.4f}" if not math.isnan(cf[sp]) else f"{sp}: n/a" for sp in SPECIES
            )
        )
        lines.append("")

    lines.append("## Mechanism check (pd-pair tagging)")
    lines.append("")
    pt_i = s_i["entry_pair_table"]["fractions"]
    d_p = pt_i.get("d|p", 0.0)
    p_d = pt_i.get("p|d", 0.0)
    lines.append(
        f"In Sample I, the fraction of events with a deuteron entering B and a proton "
        f"entering A is {d_p:.4f}; proton-into-B with deuteron-into-A is {p_d:.4f}. "
        f"A dominant d|p (or p|d) population is the direct signature of the "
        f"kinematically correlated pd-elastic pair that the A·B coincidence tags."
    )
    lines.append("")
    lines.append("## Caveats")
    lines.append("")
    for c in CAVEATS:
        lines.append(f"- {c}")
    lines.append("")
    lines.append("## Artifacts")
    lines.append("")
    lines.append("- `s21_summary.json` — all tables with counts")
    lines.append("- `s21_overview.png` — multi-panel overview figure")
    lines.append("")
    lines.append("Reproduce:")
    lines.append("```")
    lines.append(
        "python3 scripts/s21_sample12_trigger_truth_comparison.py "
        f"--mc {summary['mc_file']} --max-events 0 --out {out_dir}"
    )
    lines.append("```")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------
def render_figure(acc: dict[str, SampleAccumulator], summary: dict, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    sp_color = {"p": "C0", "d": "C3", "other": "C7"}
    samp_style = {"I": "-", "II": "--"}

    # (0,0) per-stave occupancy fractions by species, I vs II
    ax = axes[0, 0]
    x = np.arange(len(STAVES))
    width = 0.12
    for j, sname in enumerate(("I", "II")):
        st = summary["samples"][sname]["stave_occupancy"]
        for k, sp in enumerate(SPECIES):
            vals = [st[name]["fractions"][sp] for name in STAVES]
            off = (j * len(SPECIES) + k - 2.5) * width
            ax.bar(
                x + off,
                vals,
                width=width,
                color=sp_color[sp],
                alpha=1.0 if sname == "I" else 0.45,
                label=f"{sp} (S{sname})",
            )
    ax.set_xticks(x)
    ax.set_xticklabels(STAVES)
    ax.set_ylabel("species fraction of stave occupancy")
    ax.set_title("Per-stave occupancy by species (solid=I, faded=II)")
    ax.legend(fontsize=7, ncol=2)

    # (0,1) B2 per-track EDep spectra, I vs II (the Matthias signature)
    ax = axes[0, 1]
    edges = np.linspace(0.0, EDEP_MAX_MEV, N_EDEP_BINS + 1)
    centers = 0.5 * (edges[:-1] + edges[1:])
    rebin = 4  # 2 MeV bins for display
    for sname in ("I", "II"):
        a = acc[sname]
        for sp in ("p", "d"):
            c = a.stave_edep_hist[sp][0].astype(float)
            c = c[: (len(c) // rebin) * rebin].reshape(-1, rebin).sum(axis=1)
            cc = centers[: len(centers) // rebin * rebin].reshape(-1, rebin).mean(axis=1)
            n = c.sum()
            if n > 0:
                ax.step(
                    cc,
                    c / n / (rebin * (edges[1] - edges[0])),
                    where="mid",
                    color=sp_color[sp],
                    linestyle=samp_style[sname],
                    label=f"{sp} S{sname} (n={int(n):,})",
                )
    ax.set_yscale("log")
    ax.set_xlabel("per-track EDep in B2 [MeV]")
    ax.set_ylabel("normalized density [1/MeV]")
    ax.set_title("B2 EDep spectra (large-pulse deuteron signature)")
    ax.legend(fontsize=7)

    # (0,2) deuteron fraction per stave with CIs
    ax = axes[0, 2]
    key = summary["key_table"]["staves"]
    for j, (sname, color) in enumerate((("I", "C3"), ("II", "C0"))):
        fr = [key[name][f"sample_{sname}"]["fraction"] for name in STAVES]
        lo = [key[name][f"sample_{sname}"]["ci95"][0] for name in STAVES]
        hi = [key[name][f"sample_{sname}"]["ci95"][1] for name in STAVES]
        xo = x + (j - 0.5) * 0.1
        ax.errorbar(
            xo,
            fr,
            yerr=[np.array(fr) - np.array(lo), np.array(hi) - np.array(fr)],
            fmt="o",
            color=color,
            capsize=3,
            label=f"Sample {sname}",
        )
    ax.set_xticks(x)
    ax.set_xticklabels(STAVES)
    ax.set_ylabel("deuteron fraction (95% CI)")
    ax.set_title("Deuteron fraction per stave — KEY comparison")
    ax.legend()

    # (1,0)/(1,1) Delta-E vs E per sample (hist2d of all charged + species scatter)
    xedges = np.linspace(0.0, DEE_X_MAX, DEE_X_BINS + 1)
    yedges = np.linspace(0.0, DEE_Y_MAX, DEE_Y_BINS + 1)
    for ax, sname in ((axes[1, 0], "I"), (axes[1, 1], "II")):
        a = acc[sname]
        total = sum(a.dee_hist[sp] for sp in SPECIES).astype(float)
        if total.sum() > 0:
            ax.pcolormesh(
                xedges, yedges, total.T, norm=LogNorm(vmin=1, vmax=max(total.max(), 1)), cmap="Greys"
            )
        for sp in ("p", "d"):
            pts = a.dee_scatter[sp]
            if pts:
                arr = np.asarray(pts)
                ax.scatter(arr[:, 0], arr[:, 1], s=2, alpha=0.25, color=sp_color[sp], label=sp)
        ax.set_xlabel("total B-arm EDep [MeV]")
        ax.set_ylabel("EDep first B stave (L0+L1) [MeV]")
        ax.set_title(f"ΔE vs E — Sample {sname}")
        ax.legend(fontsize=8, markerscale=4)

    # (1,2) penetration depth profiles
    ax = axes[1, 2]
    for sname in ("I", "II"):
        a = acc[sname]
        for sp in ("p", "d"):
            c = a.deepest[sp].astype(float)
            if c.sum() > 0:
                ax.plot(
                    range(N_B_LAYERS),
                    c / c.sum(),
                    marker="o",
                    color=sp_color[sp],
                    linestyle=samp_style[sname],
                    label=f"{sp} S{sname}",
                )
    ax.set_xlabel("deepest LayerID with EDep>0")
    ax.set_ylabel("fraction of tracks")
    ax.set_title("Penetration depth by species")
    ax.legend(fontsize=8)

    v = summary["key_table"]["verdict_B2"]
    fig.suptitle(
        f"S21 Sample I vs II (truth, inclusive) — B2 deuteron enrichment ratio "
        f"{v['ratio']:.2f} [{v['ci95'][0]:.2f}, {v['ci95'][1]:.2f}]",
        fontsize=13,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(path, dpi=140)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument(
        "--mc",
        default=str(ROOT / "geant4" / "data" / "output_krakow_1M.root"),
        help="MC truth ROOT file (tree 'hibeam')",
    )
    ap.add_argument("--out", default=None, help="output directory (default reports/s21_..._<stamp>)")
    ap.add_argument("--tree", default="hibeam")
    ap.add_argument("--coinc-ns", type=float, default=COINC_NS_DEFAULT)
    ap.add_argument("--max-events", type=int, default=0, help="0 = all events")
    ap.add_argument("--step-size", default="200 MB", help="uproot iterate step size")
    args = ap.parse_args()

    stamp = int(time.time())
    out_dir = Path(args.out) if args.out else ROOT / "reports" / f"s21_sample12_trigger_truth_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    import uproot  # deferred so the module imports without ROOT deps (tests)

    acc = {"I": SampleAccumulator(), "II": SampleAccumulator()}
    n_read = 0
    trig = Counter()
    t0 = time.time()
    stop = args.max_events if args.max_events > 0 else None

    with uproot.open(args.mc) as fobj:
        tree = fobj[args.tree]
        n_target = int(tree.num_entries) if stop is None else min(stop, int(tree.num_entries))
        for ichunk, chunk in enumerate(
            tree.iterate(list(BRANCHES), step_size=args.step_size, library="np", entry_stop=stop)
        ):
            flags = process_chunk(
                chunk["Sci_bar_LayerID"],
                chunk["Sci_bar_LayerID1"],
                chunk["Sci_bar_PDG"],
                chunk["Sci_bar_Time"],
                args.coinc_ns,
            )
            for k, v in summarize_chunk(flags).items():
                trig[k] += v
            process_chunk_events(chunk, flags, acc["I"], acc["II"])
            n_read += len(chunk["Sci_bar_LayerID"])
            print(
                f"[chunk {ichunk}] events={n_read:,}/{n_target:,} "
                f"sampleI={acc['I'].n_events:,} sampleII={acc['II'].n_events:,} "
                f"elapsed={time.time() - t0:.0f}s",
                flush=True,
            )

    summary = {
        "study": "s21_sample12_trigger_truth_comparison",
        "mc_file": str(Path(args.mc).resolve()),
        "tree": args.tree,
        "coinc_ns": args.coinc_ns,
        "max_events": args.max_events,
        "n_events_read": n_read,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "layer_to_stave_mapping": {str(l): STAVES[l // 2] for l in range(N_B_LAYERS)},
        "mapping_note": "LayerID->stave mapping is UNDER REVIEW; per-LayerID tables included",
        "trigger_counts": {
            "enter_B": int(trig["n_enter_B"]),
            "enter_A": int(trig["n_enter_A"]),
            "sample_I": int(trig["n_sample_I"]),
            "sample_II": int(trig["n_sample_II"]),
            "inclusive_definitions": True,
        },
        "samples": {sname: summarize_sample(acc[sname]) for sname in ("I", "II")},
        "key_table": build_key_table(acc["I"], acc["II"]),
        "caveats": CAVEATS,
    }

    json_path = out_dir / "s21_summary.json"
    with open(json_path, "w") as fh:
        json.dump(summary, fh, indent=2)

    fig_path = out_dir / "s21_overview.png"
    try:
        render_figure(acc, summary, fig_path)
    except Exception as exc:  # keep JSON/report even if plotting fails
        summary["_plot_error"] = str(exc)
        with open(json_path, "w") as fh:
            json.dump(summary, fh, indent=2)
        print(f"[warn] figure failed: {exc}")

    report_path = out_dir / "REPORT.md"
    report_path.write_text(render_report(summary, out_dir))

    v = summary["key_table"]["verdict_B2"]
    print(
        json.dumps(
            {
                "n_events_read": n_read,
                "n_sample_I": acc["I"].n_events,
                "n_sample_II": acc["II"].n_events,
                "B2_deuteron_fraction_I": summary["key_table"]["staves"]["B2"]["sample_I"]["fraction"],
                "B2_deuteron_fraction_II": summary["key_table"]["staves"]["B2"]["sample_II"]["fraction"],
                "B2_enrichment_ratio": v["ratio"],
                "B2_enrichment_ci95": v["ci95"],
                "verdict_enriched": v["enriched"],
            },
            indent=2,
        )
    )
    print(f"[ok] wrote {json_path}")
    print(f"[ok] wrote {report_path}")
    if fig_path.exists():
        print(f"[ok] wrote {fig_path}")


if __name__ == "__main__":
    main()
