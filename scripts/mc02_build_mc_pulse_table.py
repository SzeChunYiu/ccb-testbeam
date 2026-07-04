#!/usr/bin/env python3
"""
mc02_build_mc_pulse_table.py
============================
Per-stave truth-labelled MC pulse table (Phase 1 flagship deliverable).

Reads the 1M-event GEANT4 truth ROOT (tree ``hibeam``) in chunks, groups
B-arm hits per (event, stave), digitizes each (event, stave) channel with the
card-driven ``DigitizerPipeline`` (configs/mc_validation/digitizer_card.yaml:
per-stave tau_decay tuned to the data tail decays, data hardware pedestal
6752 ADC, measured noise scale), and writes an s00-schema pulse table PLUS
truth columns, so every data-side script can run unchanged on MC.

Schema (one row per (event, stave) channel with any selected-arm deposit — NO
selection applied; ``--select-a1000`` writes a filtered companion):
  run=0, group='mc', eventno, evt, stave, channel,
  baseline_adc, amplitude_adc, peak_sample, area_adc_samples   [s00 columns]
  pdg (dominant-by-edep in the stave), edep_tot_mev (stave sum),
  stop_layer (event-level deepest layer with edep>0 in the selected arm),
  sample_I, sample_II (truth/trigger.py process_chunk),
  n_tracks (unique TrackIDs depositing in the stave),
  contained (event-level: stop_layer < last layer of the arm),
  dedx_max_mev_per_cm (Phase 4: max per-hit truth dE/dx in the stave — the
  Birks-quench driver; see per_hit_dedx)

Phase 4 (2026-07-04): Birks quenching (card ``apply_birks``, CLI override
--apply-birks / --no-birks) with per-hit dE/dx passed to the pipeline through
the hit dicts (keys pdg / ekin_mev / dedx_mev_per_cm — absent keys degrade
gracefully, so old fixtures keep working). --arm A digitizes the A arm
(LayerID1==2, staves A1..A4, direct LayerID 0-3 mapping, tau_decay 50 ns
DEFAULT — no data fit exists for A staves).

Sign convention: the pipeline emits positive-going waveforms on the 6752 ADC
pedestal, and pulse quantities use the DATA s00 estimator exactly —
baseline = median(samples 0-3), amplitude = max(waveform - baseline),
peak_sample = argmax(waveform - baseline), area = sum(waveform - baseline).

Timing: hits are placed at their truth times relative to the event's earliest
B-arm hit plus a trigger offset (--trigger-offset-ns). DEFAULT 50 ns, a
DELIBERATE CORRECTION of the historical 20 ns toy convention (mv6): 20 ns
puts the pulse peak at sample 2-3, INSIDE the s00 baseline window (median of
samples 0-3), which poisons the baseline estimate (negative areas, amplitude
biased low) and classifies ~100% of MC pulses as "early-peak" anomalies where
data has 4.4% (P02 taxonomy: peak_sample<=3). 50 ns places the peak at sample
~5, the data's nominal peak phase, leaving samples 0-4 as clean pre-pulse.

Seeding: per-channel noise seed = (eventno, stave_index) via
DigitizerPipeline.run(event_id=eventno, channel=stave_index) — independent
noise per channel and reproducible across chunkings.

Mapping (--mapping, default 'paired'; UNDER REVIEW, see review P4):
  paired: LayerID {0,1}->B2, {2,3}->B4, {4,5}->B6, {6,7}->B8 (pair-summed)
  odd:    odd layers unread; {0}->B2, {2}->B4, {4}->B6, {6}->B8

--zero-signal N additionally emits N pure pedestal+noise records (no hits)
for the MV7 pedestal study, with per-record true pedestal jittered uniformly
over the observed data baseline range [6737, 7029] ADC and the full 18
samples stored (columns s00..s17 + pedestal_true_adc).

Outputs (in --out):
  mc02_pulse_table.csv.gz            full unselected table
  mc02_pulse_table_a1000.csv.gz      A>1000 companion (with --select-a1000)
  mc02_zero_signal.csv.gz            zero-signal sample (with --zero-signal N)
  mc02_waveform_means.npz            per-stave mean/count of baseline-subtracted
                                     waveforms (for tail-decay validation)
  manifest.json                      row counts + card provenance
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from ccb_mc_validation.constants import A_ARM, B_ARM, COINC_NS_DEFAULT, NB_LAYERS
from ccb_mc_validation.digitizer.birks import KB_CM_PER_MEV, dedx_polystyrene_mev_per_cm
from ccb_mc_validation.digitizer.pipeline import (
    DEFAULT_CARD_PATH,
    DigitizerPipeline,
    load_digitizer_card,
)
from ccb_mc_validation.truth.pdg import mass_of
from ccb_mc_validation.truth.trigger import process_chunk

# Default trigger offset: earliest B-arm hit lands at 50 ns = start of sample
# 5 (data nominal peak phase; see docstring — 20 ns would poison the s00
# baseline window).
TRIG_OFFSET_NS = 50.0
STAVES = ("B2", "B4", "B6", "B8")
A_STAVES = ("A1", "A2", "A3", "A4")
NA_LAYERS = 4  # A-arm truth LayerID is 0-3 (verified on output_krakow_1M)
BASELINE_SAMPLES = (0, 1, 2, 3)
ZERO_SIGNAL_SEED_SALT = 777
# Observed data baseline range across channels/runs (mv0_calibration REPORT.md).
ZERO_SIGNAL_PED_RANGE = (6737.0, 7029.0)

# --- per-hit dE/dx from truth (Phase 4, Birks) -------------------------------
# Sci_bar_TrackLength is CUMULATIVE track length in cm (verified 2026-07-04:
# ~112 cm at B-arm entry for target primaries = flight path; ~20 um for in-bar
# alpha recoils = their range). Step length per hit = difference of
# consecutive TrackLength values of the same TrackID; the first hit of a track
# uses the raw TrackLength only when the track was born locally
# (TrackLength <= FIRST_STEP_MAX_CM). Anything invalid falls back to the
# PSTAR/ASTAR-anchored species+energy lookup in digitizer/birks.py.
FIRST_STEP_MAX_CM = 5.0
MIN_STEP_CM = 1e-4          # 1 um: below G4 step resolution -> unreliable ratio
DEDX_MAX_MEV_PER_CM = 3.0e4  # above any physical stopping power in polystyrene

TRUTH_BRANCHES = (
    "Sci_bar_LayerID",
    "Sci_bar_LayerID1",
    "Sci_bar_PDG",
    "Sci_bar_EDep",
    "Sci_bar_Time",
    "Sci_bar_TrackID",
)
# Optional branches consumed when present (per-hit dE/dx and hit energy for
# Birks). Missing branches degrade gracefully to the species lookup.
OPTIONAL_TRUTH_BRANCHES = (
    "Sci_bar_TrackLength",
    "Sci_bar_Momentum_X",
    "Sci_bar_Momentum_Y",
    "Sci_bar_Momentum_Z",
)

CSV_COLUMNS = (
    "run,group,eventno,evt,stave,channel,baseline_adc,amplitude_adc,"
    "peak_sample,area_adc_samples,pdg,edep_tot_mev,stop_layer,"
    "sample_I,sample_II,n_tracks,contained,dedx_max_mev_per_cm"
)


def stave_index_of(layer: np.ndarray, mapping: str, arm: str = "B") -> np.ndarray:
    """Map truth LayerID to stave index (0-3); -1 = unread.

    B arm: LayerID 0-7, 'paired' pair-sums {0,1}->B2 ... {6,7}->B8, 'odd'
    drops odd layers. A arm: LayerID 0-3 maps DIRECTLY 0->A1 ... 3->A4
    (no pair-summing; ``mapping`` is ignored for A).
    """
    if arm == "A":
        return np.where(layer < NA_LAYERS, layer, -1).astype(np.int64)
    idx = layer // 2
    if mapping == "paired":
        return idx.astype(np.int64)
    if mapping == "odd":
        out = np.where(layer % 2 == 0, idx, -1)
        return out.astype(np.int64)
    raise ValueError(f"unknown mapping {mapping!r} (expected 'paired' or 'odd')")


def build_stave_pipelines(card: dict, staves: tuple[str, ...] = STAVES) -> dict[str, DigitizerPipeline]:
    return {stave: DigitizerPipeline.from_config(card, stave=stave) for stave in staves}


def per_hit_dedx(
    trk: np.ndarray,
    tracklen_cm: np.ndarray | None,
    edep: np.ndarray,
    pdg: np.ndarray,
    ekin: np.ndarray | None,
) -> np.ndarray:
    """Per-hit dE/dx [MeV/cm] for one event's arm-selected hits (Phase 4).

    Primary estimator: edep_hit / step_length with step lengths from
    consecutive-hit TrackLength differences (see module comment). Fallback:
    species+energy lookup (per-hit ekin from the momentum branches when
    available, else documented testbeam-typical defaults).
    """
    n = int(edep.size)
    dedx = np.full(n, np.nan, dtype=np.float64)
    if tracklen_cm is not None and tracklen_cm.size == n:
        for tid in np.unique(trk):
            idx = np.where(trk == tid)[0]
            order = idx[np.argsort(tracklen_cm[idx], kind="stable")]
            tl_sorted = tracklen_cm[order]
            steps = np.empty(order.size, dtype=np.float64)
            steps[1:] = np.diff(tl_sorted)
            # first hit: raw cumulative length is a step only for locally
            # created tracks (recoils born inside the bar)
            steps[0] = tl_sorted[0] if 0.0 < tl_sorted[0] <= FIRST_STEP_MAX_CM else np.nan
            with np.errstate(divide="ignore", invalid="ignore"):
                vals = edep[order] / steps
            ok = (
                np.isfinite(vals)
                & (steps >= MIN_STEP_CM)
                & (vals > 0.0)
                & (vals <= DEDX_MAX_MEV_PER_CM)
            )
            dedx[order[ok]] = vals[ok]
    for i in range(n):
        if not np.isfinite(dedx[i]):
            ek = None
            if ekin is not None and np.isfinite(ekin[i]) and ekin[i] > 0.0:
                ek = float(ekin[i])
            dedx[i] = dedx_polystyrene_mev_per_cm(int(pdg[i]), ek)
    return dedx


def pulse_quantities(adc: np.ndarray) -> tuple[float, float, int, float]:
    """DATA s00 estimator: baseline median(samples 0-3), positive net amplitude."""
    baseline = float(np.median(adc[list(BASELINE_SAMPLES)]))
    corrected = adc.astype(np.float64) - baseline
    return baseline, float(corrected.max()), int(corrected.argmax()), float(corrected.sum())


def process_truth_chunk(
    arrays: dict,
    event_offset: int,
    pipelines: dict[str, DigitizerPipeline],
    mapping: str,
    coinc_ns: float = COINC_NS_DEFAULT,
    waveform_accum: dict | None = None,
    trigger_offset_ns: float = TRIG_OFFSET_NS,
    arm: str = "B",
) -> list[tuple]:
    """Digitize one jagged truth chunk into per-(event, stave) table rows.

    ``arm`` selects the detector arm: "B" (LayerID1==1, staves B2..B8, paired
    or odd LayerID mapping) or "A" (LayerID1==2, staves A1..A4, direct
    mapping). Per-hit dE/dx (Phase 4 Birks input) is derived from the
    optional TrackLength/Momentum branches when present; hit dicts always
    carry pdg/ekin_mev/dedx_mev_per_cm so the pipeline's Birks stage can
    quench correctly, and degrade gracefully when the branches are absent.
    """
    staves = A_STAVES if arm == "A" else STAVES
    arm_id = A_ARM if arm == "A" else B_ARM
    n_layers = NA_LAYERS if arm == "A" else NB_LAYERS

    layer_j = np.asarray(arrays["Sci_bar_LayerID"], dtype=object)
    arm_j = np.asarray(arrays["Sci_bar_LayerID1"], dtype=object)
    pdg_j = np.asarray(arrays["Sci_bar_PDG"], dtype=object)
    edep_j = np.asarray(arrays["Sci_bar_EDep"], dtype=object)
    time_j = np.asarray(arrays["Sci_bar_Time"], dtype=object)
    track_j = np.asarray(arrays["Sci_bar_TrackID"], dtype=object)
    tl_j = arrays.get("Sci_bar_TrackLength")
    px_j = arrays.get("Sci_bar_Momentum_X")
    py_j = arrays.get("Sci_bar_Momentum_Y")
    pz_j = arrays.get("Sci_bar_Momentum_Z")

    flags = process_chunk(layer_j, arm_j, pdg_j, time_j, coinc_ns)
    rows: list[tuple] = []

    for i in range(len(layer_j)):
        lay = np.asarray(layer_j[i], dtype=np.int64).reshape(-1)
        if lay.size == 0:
            continue
        arm_i = np.asarray(arm_j[i], dtype=np.int64).reshape(-1)
        pdg = np.asarray(pdg_j[i], dtype=np.int64).reshape(-1)
        edep = np.asarray(edep_j[i], dtype=np.float64).reshape(-1)
        thit = np.asarray(time_j[i], dtype=np.float64).reshape(-1)
        trk = np.asarray(track_j[i], dtype=np.int64).reshape(-1)

        usable = min(lay.size, arm_i.size, pdg.size, edep.size, thit.size, trk.size)
        if usable == 0:
            continue
        b = arm_i[:usable] == arm_id
        if not b.any():
            continue
        lay_b = lay[:usable][b]
        pdg_b = pdg[:usable][b]
        edep_b = edep[:usable][b]
        t_b = thit[:usable][b]
        trk_b = trk[:usable][b]

        # optional per-hit truth for Birks dE/dx
        tl_b = None
        if tl_j is not None:
            tl = np.asarray(tl_j[i], dtype=np.float64).reshape(-1)
            if tl.size >= usable:
                tl_b = tl[:usable][b]
        ekin_b = None
        if px_j is not None and py_j is not None and pz_j is not None:
            px = np.asarray(px_j[i], dtype=np.float64).reshape(-1)
            py = np.asarray(py_j[i], dtype=np.float64).reshape(-1)
            pz = np.asarray(pz_j[i], dtype=np.float64).reshape(-1)
            if min(px.size, py.size, pz.size) >= usable:
                pmag_b = (
                    np.sqrt(px[:usable][b] ** 2 + py[:usable][b] ** 2 + pz[:usable][b] ** 2)
                    * 1000.0  # GeV/c -> MeV/c
                )
                mass_b = np.array([mass_of(int(p)) for p in pdg_b])
                ekin_b = np.sqrt(pmag_b * pmag_b + mass_b * mass_b) - mass_b

        deposit = edep_b > 0.0
        if not deposit.any():
            continue
        eventno = event_offset + i
        stop_layer = int(lay_b[deposit].max())
        contained = bool(stop_layer < n_layers - 1)
        t0 = float(t_b[deposit].min())
        sidx = stave_index_of(lay_b, mapping, arm=arm)
        dedx_b = per_hit_dedx(trk_b, tl_b, edep_b, pdg_b, ekin_b)

        for k, stave in enumerate(staves):
            in_stave = (sidx == k) & deposit
            if not in_stave.any():
                continue
            e_s = edep_b[in_stave]
            p_s = pdg_b[in_stave]
            t_s = t_b[in_stave]
            d_s = dedx_b[in_stave]
            ek_s = ekin_b[in_stave] if ekin_b is not None else None
            hits = [
                {
                    "edep_mev": float(e_s[j]),
                    "time_ns": float(t_s[j]) - t0 + trigger_offset_ns,
                    "pdg": int(p_s[j]),
                    "ekin_mev": (
                        float(ek_s[j])
                        if ek_s is not None and np.isfinite(ek_s[j]) and ek_s[j] > 0.0
                        else None
                    ),
                    "dedx_mev_per_cm": float(d_s[j]),
                }
                for j in range(int(in_stave.sum()))
            ]
            result = pipelines[stave].run(hits, event_id=eventno, channel=k)
            adc = np.asarray(result["adc"], dtype=np.float64)
            baseline, amplitude, peak_sample, area = pulse_quantities(adc)

            # dominant species by summed stave edep
            dom_pdg, dom_e = 0, -1.0
            for species in np.unique(p_s):
                s = float(e_s[p_s == species].sum())
                if s > dom_e:
                    dom_e, dom_pdg = s, int(species)

            rows.append(
                (
                    0,
                    "mc",
                    eventno,
                    eventno,
                    stave,
                    2 * k,
                    baseline,
                    amplitude,
                    peak_sample,
                    area,
                    dom_pdg,
                    float(e_s.sum()),
                    stop_layer,
                    int(flags["sample_I"][i]),
                    int(flags["sample_II"][i]),
                    int(np.unique(trk_b[in_stave]).size),
                    int(contained),
                    float(d_s.max()),
                )
            )
            if waveform_accum is not None:
                waveform_accum[stave]["sum"] += adc - baseline
                waveform_accum[stave]["n"] += 1
    return rows


def write_rows(handle, rows: list[tuple]) -> None:
    for r in rows:
        handle.write(
            f"{r[0]},{r[1]},{r[2]},{r[3]},{r[4]},{r[5]},{r[6]:.1f},{r[7]:.1f},"
            f"{r[8]},{r[9]:.1f},{r[10]},{r[11]:.6f},{r[12]},{r[13]},{r[14]},{r[15]},{r[16]},{r[17]:.1f}\n"
        )


def generate_zero_signal(
    card: dict,
    n_records: int,
    out_path: Path,
    n_samples: int,
) -> dict:
    """Emit pure pedestal+noise records (no hits) for the MV7 pedestal study.

    The true pedestal is jittered per record over the observed data baseline
    range so a learned estimator has non-trivial structure to regress; the
    jitter value is recorded as ``pedestal_true_adc`` (the KNOWN truth that
    real data never provides — this closes the 'no true pedestal sample' gap
    at MC LEVEL ONLY).
    """
    rng = np.random.default_rng(np.random.SeedSequence([20260703, ZERO_SIGNAL_SEED_SALT]))
    base_pipe = DigitizerPipeline.from_config(card)
    lo, hi = ZERO_SIGNAL_PED_RANGE
    sample_cols = ",".join(f"s{j:02d}" for j in range(n_samples))
    with gzip.open(out_path, "wt", encoding="utf-8") as handle:
        handle.write(f"record_id,stave,channel,pedestal_true_adc,baseline_adc,amplitude_adc,{sample_cols}\n")
        for i in range(n_records):
            k = i % len(STAVES)
            ped_true = float(rng.uniform(lo, hi))
            base_pipe.electronics.pedestal_adc = ped_true
            result = base_pipe.run(
                [], event_id=i, channel=k, seed_salt=ZERO_SIGNAL_SEED_SALT
            )
            adc = np.asarray(result["adc"], dtype=np.float64)
            baseline, amplitude, _, _ = pulse_quantities(adc)
            samples = ",".join(str(int(v)) for v in adc)
            handle.write(
                f"{i},{STAVES[k]},{2 * k},{ped_true:.3f},{baseline:.1f},{amplitude:.1f},{samples}\n"
            )
    return {
        "n_records": n_records,
        "pedestal_true_range_adc": list(ZERO_SIGNAL_PED_RANGE),
        "seed_salt": ZERO_SIGNAL_SEED_SALT,
        "path": str(out_path),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mc", required=True, help="truth ROOT file (tree hibeam)")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--card", default=str(DEFAULT_CARD_PATH), help="digitizer calibration card YAML")
    ap.add_argument("--arm", choices=("B", "A"), default="B",
                    help="detector arm: B (LayerID1==1, staves B2..B8) or "
                         "A (LayerID1==2, staves A1..A4, direct LayerID mapping)")
    birks_group = ap.add_mutually_exclusive_group()
    birks_group.add_argument("--apply-birks", action="store_true",
                             help="force Birks quenching ON (overrides the card)")
    birks_group.add_argument("--no-birks", action="store_true",
                             help="force Birks quenching OFF (overrides the card; "
                                  "legacy unquenched twin)")
    ap.add_argument("--mapping", choices=("paired", "odd"), default="paired",
                    help="B-arm LayerID->stave mapping (default paired; UNDER "
                         "REVIEW; ignored for --arm A)")
    ap.add_argument("--max-events", type=int, default=0, help="0 = all events")
    ap.add_argument("--step-size", type=int, default=20000, help="uproot chunk size")
    ap.add_argument("--select-a1000", action="store_true",
                    help="also write an amplitude>1000 filtered companion CSV")
    ap.add_argument("--zero-signal", type=int, default=0, metavar="N",
                    help="also emit N pure pedestal+noise records for MV7")
    ap.add_argument("--coinc-ns", type=float, default=COINC_NS_DEFAULT)
    ap.add_argument("--trigger-offset-ns", type=float, default=TRIG_OFFSET_NS,
                    help="window time of the earliest B-arm hit (default 50; "
                         "20 would poison the samples-0-3 baseline window)")
    args = ap.parse_args()

    import uproot

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    card = load_digitizer_card(args.card)
    if args.apply_birks:
        card["digitizer"]["apply_birks"] = True
    elif args.no_birks:
        card["digitizer"]["apply_birks"] = False
    apply_birks = bool(card["digitizer"].get("apply_birks", False))
    staves = A_STAVES if args.arm == "A" else STAVES
    pipelines = build_stave_pipelines(card, staves)
    n_samples = pipelines[staves[0]].n_samples

    table_path = out_dir / "mc02_pulse_table.csv.gz"
    a1000_path = out_dir / "mc02_pulse_table_a1000.csv.gz"
    waveform_accum = {
        s: {"sum": np.zeros(n_samples, dtype=np.float64), "n": 0} for s in staves
    }

    t_start = time.time()
    n_rows = 0
    n_rows_a1000 = 0
    n_events_scanned = 0
    stave_counts: dict[str, int] = defaultdict(int)
    amp_accum: dict[str, list] = {s: [] for s in staves}
    sample_counts = {"sample_I": 0, "sample_II": 0}

    tree = uproot.open(args.mc)["hibeam"]
    n_entries = int(tree.num_entries)
    entry_stop = n_entries if args.max_events <= 0 else min(args.max_events, n_entries)
    available = set(tree.keys())
    branches = list(TRUTH_BRANCHES) + [b for b in OPTIONAL_TRUTH_BRANCHES if b in available]
    missing_optional = [b for b in OPTIONAL_TRUTH_BRANCHES if b not in available]
    if missing_optional:
        print(f"[mc02] WARNING optional branches missing (species-lookup dE/dx "
              f"fallback in effect): {missing_optional}", flush=True)

    a1000_handle = None
    with gzip.open(table_path, "wt", encoding="utf-8") as handle:
        handle.write(CSV_COLUMNS + "\n")
        if args.select_a1000:
            a1000_handle = gzip.open(a1000_path, "wt", encoding="utf-8")
            a1000_handle.write(CSV_COLUMNS + "\n")
        try:
            for arrays in tree.iterate(
                branches,
                step_size=args.step_size,
                entry_stop=entry_stop,
                library="np",
            ):
                rows = process_truth_chunk(
                    arrays,
                    event_offset=n_events_scanned,
                    pipelines=pipelines,
                    mapping=args.mapping,
                    coinc_ns=args.coinc_ns,
                    waveform_accum=waveform_accum,
                    trigger_offset_ns=args.trigger_offset_ns,
                    arm=args.arm,
                )
                write_rows(handle, rows)
                n_rows += len(rows)
                seen_events = set()
                for r in rows:
                    stave_counts[r[4]] += 1
                    amp_accum[r[4]].append(r[7])
                    if r[2] not in seen_events:
                        seen_events.add(r[2])
                        sample_counts["sample_I"] += r[13]
                        sample_counts["sample_II"] += r[14]
                if a1000_handle is not None:
                    a_rows = [r for r in rows if r[7] > 1000.0]
                    write_rows(a1000_handle, a_rows)
                    n_rows_a1000 += len(a_rows)
                n_events_scanned += len(arrays["Sci_bar_LayerID"])
                print(
                    f"[mc02] events {n_events_scanned}/{entry_stop} rows {n_rows} "
                    f"({time.time() - t_start:.0f}s)",
                    flush=True,
                )
        finally:
            if a1000_handle is not None:
                a1000_handle.close()

    np.savez_compressed(
        out_dir / "mc02_waveform_means.npz",
        **{f"{s}_sum": waveform_accum[s]["sum"] for s in staves},
        **{f"{s}_n": np.asarray(waveform_accum[s]["n"]) for s in staves},
        sample_spacing_ns=np.asarray(pipelines[staves[0]].sample_spacing_ns),
    )

    amplitude_stats: dict[str, dict] = {}
    for s in staves:
        a = np.asarray(amp_accum[s], dtype=np.float64)
        a1k = a[a > 1000.0]
        amplitude_stats[s] = {
            "n": int(a.size),
            "median_adc": float(np.median(a)) if a.size else None,
            "p10_adc": float(np.percentile(a, 10)) if a.size else None,
            "p90_adc": float(np.percentile(a, 90)) if a.size else None,
            "n_a1000": int(a1k.size),
            "median_a1000_adc": float(np.median(a1k)) if a1k.size else None,
        }

    zero_signal_meta = None
    if args.zero_signal > 0:
        zero_signal_meta = generate_zero_signal(
            card, args.zero_signal, out_dir / "mc02_zero_signal.csv.gz", n_samples
        )

    manifest = {
        "script": "scripts/mc02_build_mc_pulse_table.py",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
        "mc_file": str(Path(args.mc).resolve()),
        "tree": "hibeam",
        "n_entries_in_tree": n_entries,
        "n_events_scanned": n_events_scanned,
        "n_rows": n_rows,
        "n_rows_a1000": n_rows_a1000 if args.select_a1000 else None,
        "rows_by_stave": dict(stave_counts),
        "amplitude_stats_by_stave": amplitude_stats,
        "events_sample_I": sample_counts["sample_I"],
        "events_sample_II": sample_counts["sample_II"],
        "arm": args.arm,
        "apply_birks": apply_birks,
        "birks": {
            "enabled": apply_birks,
            "law": "light = edep / (1 + kB * dEdx)",
            "kb_cm_per_mev": KB_CM_PER_MEV,
            "kb_source": "0.0126 g/(MeV cm^2) (Craun & Smith 1970 / GEANT4 polystyrene) / rho 1.06 g/cm^3",
            "dedx_source": (
                "per-hit edep/step_length from consecutive-hit differences of the "
                "cumulative Sci_bar_TrackLength (cm); fallback PSTAR/ASTAR-anchored "
                "species+energy lookup (digitizer/birks.py) with per-hit ekin from "
                "the momentum branches"
            ),
            "optional_branches_missing": missing_optional,
        },
        "mapping": args.mapping if args.arm == "B" else "direct (A arm: LayerID 0-3 -> A1..A4)",
        "trigger_offset_ns": args.trigger_offset_ns,
        "trigger_offset_note": (
            "50 ns default corrects the historical 20 ns toy convention, which "
            "would place the pulse peak inside the s00 baseline window "
            "(samples 0-3) and poison baseline/amplitude/area"
        ),
        "coinc_ns": args.coinc_ns,
        "selection": (
            f"NONE (all channels with any {args.arm}-arm deposit); companion a1000 filtered"
        ),
        "card": {
            "path": str(Path(args.card).resolve()),
            "sha256": sha256_file(Path(args.card)),
            "card_id": card.get("card_id"),
            "card_version": card.get("card_version"),
            "gain_adc_per_mev": card["digitizer"]["gain_adc_per_mev"],
            "gain_status": card["digitizer"].get("gain_status"),
            "pedestal_adc": card["digitizer"]["pedestal_adc"],
            "noise_adc_rms": card["digitizer"]["noise_adc_rms"],
            "tau_rise_ns": card["digitizer"]["tau_rise_ns"],
            "tau_decay_ns_by_stave": {
                s: card["digitizer"]["staves"][s]["tau_decay_ns"] for s in staves
            },
        },
        "zero_signal": zero_signal_meta,
        "caveats": [
            "gain_adc_per_mev is an UNKNOWN placeholder (geometry-poisoned MC anchor, review P1/P2); amplitude scale is not calibrated. Phase 2 grid: trigger-consistent scan prefers ~60 ADC/MeV",
            "per-stave occupancy/spectrum weights inherit the geometry defect (MV3 chi2/ndf=68269; Phase 2: dominated by the unsimulated two-arm coincidence trigger)",
            "LayerID->stave mapping is UNDER REVIEW (paired vs odd, review P4)",
        ]
        + (
            [
                "A-arm tau_decay 50 ns is a DEFAULT (no A-stave rows in the template-fit CSV), not a data measurement",
                "A2/A4 have no selected data pulses (docs/08_astack.md); their MC rows have no data counterpart",
            ]
            if args.arm == "A"
            else []
        ),
        "outputs": {
            "pulse_table": str(table_path),
            "pulse_table_sha256": sha256_file(table_path),
            "a1000_table": str(a1000_path) if args.select_a1000 else None,
            "waveform_means": str(out_dir / "mc02_waveform_means.npz"),
        },
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("n_events_scanned", "n_rows", "rows_by_stave")}, indent=2))
    print(f"[mc02] done in {time.time() - t_start:.0f}s -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
