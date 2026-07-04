#!/usr/bin/env python3
"""
mc03_build_overlay_sample.py
============================
Truth-labelled two-pulse pile-up overlay production (Phase 3, deliverable 1).

Generates per-rate overlay samples by digitizing PAIRS of real truth
(event, stave) hit groups from the 1M GEANT4 truth file (loading/grouping
reuses mc02_build_mc_pulse_table.py), with the card-driven DigitizerPipeline
(per-stave tau_decay tuned to the data tails, hardware pedestal 6752 ADC,
per-record independent noise seeds; hit-time offsets verified to shift the
sampled pulse after the Phase-1 sampling fix, review C1).

Record recipe (per rate R in --rates, default 0.5/1.5/3.0 MHz):
  * overlap records (fraction --overlap-fraction, default 0.7):
      pulse 1 = one truth (event, stave) hit group, earliest hit at the
                nominal 50 ns trigger offset (mc02 convention);
      pulse 2 = an INDEPENDENT truth group from the SAME stave, earliest hit
                at 50 + dt with dt drawn CONTINUOUSLY from Exponential(1/R)
                truncated to the 180 ns window (dt <= 130 ns, inverse-CDF
                sampling — deliberately NO separation grid, review P8);
      amplitude pairing = independent draws from the truth population,
                NO ratio restriction (review P8).
  * single-pulse negatives (remaining fraction, default 0.3): pulse 1 only.

Split hygiene: truth groups are pooled per (stave, source-event parity);
records labelled split=train draw BOTH constituents from even source events,
split=eval from odd source events, so no truth pulse shape can appear on both
sides of the downstream ML benchmark (s24).

Selection: each constituent must have a noise-free nominal-placement digitized
amplitude > --min-true-amp-adc (default 1000 ADC) so the overlay population
mirrors the analysed data population (A>1000 net). NOTE the amplitude scale
uses the card's PLACEHOLDER gain (297 ADC/MeV, review P1/P2) — arbitrary units.

Stored per record: the 18-sample waveform (columns s00..s17), true dt, true
per-constituent noise-free amplitudes and truth edeps, rate label, split,
sample_I/II flags of both source events, stave/channel, source event ids.

Outputs (in --out):
  mc03_overlay_rate<R>MHz.csv.gz     one table per rate
  manifest.json                      counts, dt stats, pool provenance, seeds
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from ccb_mc_validation.constants import B_ARM, COINC_NS_DEFAULT
from ccb_mc_validation.digitizer.overlay import overlay_hits
from ccb_mc_validation.digitizer.pipeline import (
    DEFAULT_CARD_PATH,
    DigitizerPipeline,
    load_digitizer_card,
)
from ccb_mc_validation.digitizer.scintillation import exponential_kernel_cdf
from ccb_mc_validation.truth.trigger import process_chunk


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mc02 = _load_script("mc02_build_mc_pulse_table", ROOT_DIR / "scripts" / "mc02_build_mc_pulse_table.py")

STAVES = mc02.STAVES
T1_NS = mc02.TRIG_OFFSET_NS  # 50 ns nominal trigger offset (mc02 convention)
RATES_MHZ_DEFAULT = (0.5, 1.5, 3.0)
OVERLAP_FRACTION_DEFAULT = 0.7
MIN_TRUE_AMP_ADC_DEFAULT = 1000.0
MC03_SEED = 20260703
MC03_SEED_SALT = 2403  # mixed into the digitizer noise seed per rate
N_RECORDS_DEFAULT = 200_000
POOL_CAP_DEFAULT = 120_000  # per (stave, parity)

META_COLUMNS = (
    "record_id,rate_mhz,split,stave,channel,is_overlap,t1_true_ns,dt_true_ns,"
    "t2_true_ns,edep1_mev,edep2_mev,amp1_true_adc,amp2_true_adc,n_hits1,"
    "n_hits2,src_event1,src_event2,sample_I_1,sample_II_1,sample_I_2,"
    "sample_II_2,saturated,baseline_adc,amplitude_adc,peak_sample"
)


def stave_digitizer_params(card: dict) -> dict[str, dict]:
    """Per-stave analog kernel parameters from the calibration card."""
    dig = card["digitizer"]
    out = {}
    for stave in STAVES:
        over = dig.get("staves", {}).get(stave, {})
        out[stave] = {
            "tau_rise_ns": float(over.get("tau_rise_ns", dig["tau_rise_ns"])),
            "tau_decay_ns": float(over.get("tau_decay_ns", dig["tau_decay_ns"])),
            "gain_adc_per_mev": float(dig["gain_adc_per_mev"]),
            "n_samples": int(dig["n_samples"]),
            "sample_spacing_ns": float(dig["sample_spacing_ns"]),
        }
    return out


def analog_waveform_adc(edep_mev: np.ndarray, t_ns: np.ndarray, params: dict) -> np.ndarray:
    """Noise-free analog ADC waveform of a hit group (no pedestal, no transport
    smear): the card kernel integrated over the fixed acquisition grid."""
    edges = np.arange(params["n_samples"] + 1, dtype=np.float64) * params["sample_spacing_ns"]
    cdf = exponential_kernel_cdf(
        edges[None, :] - np.asarray(t_ns, dtype=np.float64)[:, None],
        params["tau_rise_ns"],
        params["tau_decay_ns"],
    )
    light = (np.asarray(edep_mev, dtype=np.float64)[:, None] * np.diff(cdf, axis=1)).sum(axis=0)
    return params["gain_adc_per_mev"] * light


def draw_truncated_exponential(
    rng: np.random.Generator,
    mean_ns: float,
    dt_max_ns: float,
    size: int | None = None,
) -> float | np.ndarray:
    """Exponential(mean_ns) truncated to (0, dt_max_ns] via inverse CDF.

    CONTINUOUS by construction — no separation grid anywhere (review P8).
    """
    u = rng.random(size)
    trunc = -np.expm1(-dt_max_ns / mean_ns)  # 1 - exp(-dt_max/mean)
    return -mean_ns * np.log1p(-u * trunc)


def collect_pool_chunk(
    arrays: dict,
    event_offset: int,
    mapping: str,
    coinc_ns: float,
    min_amp_adc: float,
    dig_params: dict[str, dict],
    pools: dict[str, list[list[dict]]],
    n_seen: dict[str, list[int]],
    rng: np.random.Generator,
    pool_cap: int,
) -> None:
    """Reservoir-sample truth (event, stave) hit groups from one jagged chunk.

    Grouping logic mirrors mc02.process_truth_chunk; instead of digitizing, the
    per-group hit arrays (edep, time relative to the group's earliest hit) are
    stored, keyed by (stave, source-event parity) for train/eval hygiene.
    """
    layer_j = np.asarray(arrays["Sci_bar_LayerID"], dtype=object)
    arm_j = np.asarray(arrays["Sci_bar_LayerID1"], dtype=object)
    pdg_j = np.asarray(arrays["Sci_bar_PDG"], dtype=object)
    edep_j = np.asarray(arrays["Sci_bar_EDep"], dtype=object)
    time_j = np.asarray(arrays["Sci_bar_Time"], dtype=object)
    track_j = np.asarray(arrays["Sci_bar_TrackID"], dtype=object)

    flags = process_chunk(layer_j, arm_j, pdg_j, time_j, coinc_ns)

    for i in range(len(layer_j)):
        lay = np.asarray(layer_j[i], dtype=np.int64).reshape(-1)
        if lay.size == 0:
            continue
        arm = np.asarray(arm_j[i], dtype=np.int64).reshape(-1)
        edep = np.asarray(edep_j[i], dtype=np.float64).reshape(-1)
        thit = np.asarray(time_j[i], dtype=np.float64).reshape(-1)
        trk = np.asarray(track_j[i], dtype=np.int64).reshape(-1)
        usable = min(lay.size, arm.size, edep.size, thit.size, trk.size)
        if usable == 0:
            continue
        b = arm[:usable] == B_ARM
        if not b.any():
            continue
        lay_b = lay[:usable][b]
        edep_b = edep[:usable][b]
        t_b = thit[:usable][b]
        deposit = edep_b > 0.0
        if not deposit.any():
            continue
        eventno = event_offset + i
        parity = eventno % 2
        sidx = mc02.stave_index_of(lay_b, mapping)
        for k, stave in enumerate(STAVES):
            in_stave = (sidx == k) & deposit
            if not in_stave.any():
                continue
            e_s = edep_b[in_stave]
            t_s = t_b[in_stave]
            trel = t_s - float(t_s.min())
            amp_nom = float(
                analog_waveform_adc(e_s, trel + T1_NS, dig_params[stave]).max()
            )
            if amp_nom <= min_amp_adc:
                continue
            group = {
                "src_event": int(eventno),
                "stave": stave,
                "edep": e_s.copy(),
                "trel": trel.copy(),
                "edep_tot_mev": float(e_s.sum()),
                "amp_nom_adc": amp_nom,
                "n_hits": int(in_stave.sum()),
                "sample_I": int(flags["sample_I"][i]),
                "sample_II": int(flags["sample_II"][i]),
            }
            n_seen[stave][parity] += 1
            bucket = pools[stave][parity]
            if len(bucket) < pool_cap:
                bucket.append(group)
            else:
                j = int(rng.integers(0, n_seen[stave][parity]))
                if j < pool_cap:
                    bucket[j] = group


def group_hits(group: dict, t_start_ns: float) -> list[dict]:
    return [
        {"edep_mev": float(e), "time_ns": float(t) + t_start_ns}
        for e, t in zip(group["edep"], group["trel"])
    ]


def digitize_record(
    pipeline: DigitizerPipeline,
    group1: dict,
    group2: dict | None,
    dt_ns: float,
    record_id: int,
    channel: int,
    seed_salt: int,
) -> dict:
    """Digitize one overlay record: pulse 1 at 50 ns, pulse 2 at 50 + dt."""
    hits = group_hits(group1, T1_NS)
    if group2 is not None:
        # overlay_hits shifts the secondary group's hits by dt on top of the
        # primary's window (both anchored at the 50 ns trigger offset).
        hits = overlay_hits(hits, group_hits(group2, T1_NS), dt_ns)
    return pipeline.run(hits, event_id=record_id, channel=channel, seed_salt=seed_salt)


def generate_rate_sample(
    rate_mhz: float,
    n_records: int,
    overlap_fraction: float,
    pools: dict[str, list[list[dict]]],
    stave_weights: dict[str, float],
    pipelines: dict[str, DigitizerPipeline],
    dig_params: dict[str, dict],
    out_path: Path,
    rate_index: int,
    dt_max_ns: float,
) -> dict:
    """Write one truth-labelled overlay CSV.gz for one rate scenario."""
    rng = np.random.default_rng(
        np.random.SeedSequence([MC03_SEED, MC03_SEED_SALT, int(round(rate_mhz * 1000))])
    )
    seed_salt = MC03_SEED_SALT + rate_index
    mean_ns = 1000.0 / rate_mhz  # MHz -> ns mean inter-arrival
    stave_names = list(STAVES)
    probs = np.asarray([stave_weights[s] for s in stave_names], dtype=np.float64)
    probs = probs / probs.sum()
    n_samples = pipelines[stave_names[0]].n_samples
    sample_cols = ",".join(f"s{j:02d}" for j in range(n_samples))

    n_overlap = 0
    n_saturated = 0
    stave_counts = {s: 0 for s in stave_names}
    dt_values: list[float] = []

    with gzip.open(out_path, "wt", encoding="utf-8") as handle:
        handle.write(META_COLUMNS + "," + sample_cols + "\n")
        for i in range(n_records):
            stave = stave_names[int(rng.choice(len(stave_names), p=probs))]
            k = stave_names.index(stave)
            parity = int(rng.integers(0, 2))
            split = "train" if parity == 0 else "eval"
            bucket = pools[stave][parity]
            group1 = bucket[int(rng.integers(0, len(bucket)))]
            is_overlap = int(rng.random() < overlap_fraction)
            group2 = None
            dt = float("nan")
            if is_overlap:
                group2 = bucket[int(rng.integers(0, len(bucket)))]
                dt = float(draw_truncated_exponential(rng, mean_ns, dt_max_ns))
                dt_values.append(dt)

            result = digitize_record(
                pipelines[stave], group1, group2, dt, record_id=i, channel=k, seed_salt=seed_salt
            )
            adc = np.asarray(result["adc"], dtype=np.float64)
            baseline, amplitude, peak_sample, _area = mc02.pulse_quantities(adc)
            saturated = int(np.asarray(result["saturated"]).any())
            n_saturated += saturated
            stave_counts[stave] += 1
            n_overlap += is_overlap

            amp1 = float(analog_waveform_adc(group1["edep"], group1["trel"] + T1_NS, dig_params[stave]).max())
            if group2 is not None:
                amp2 = float(
                    analog_waveform_adc(group2["edep"], group2["trel"] + T1_NS + dt, dig_params[stave]).max()
                )
                edep2, nh2, src2 = group2["edep_tot_mev"], group2["n_hits"], group2["src_event"]
                sI2, sII2 = group2["sample_I"], group2["sample_II"]
                dt_s, t2_s = f"{dt:.6f}", f"{T1_NS + dt:.6f}"
            else:
                amp2, edep2, nh2, src2, sI2, sII2 = 0.0, 0.0, 0, -1, 0, 0
                dt_s, t2_s = "", ""

            samples = ",".join(str(int(v)) for v in adc)
            handle.write(
                f"{i},{rate_mhz},{split},{stave},{2 * k},{is_overlap},{T1_NS:.1f},"
                f"{dt_s},{t2_s},{group1['edep_tot_mev']:.6f},{edep2:.6f},"
                f"{amp1:.1f},{amp2:.1f},{group1['n_hits']},{nh2},"
                f"{group1['src_event']},{src2},{group1['sample_I']},{group1['sample_II']},"
                f"{sI2},{sII2},{saturated},{baseline:.1f},{amplitude:.1f},{peak_sample},"
                f"{samples}\n"
            )

    dt_arr = np.asarray(dt_values, dtype=np.float64)
    return {
        "rate_mhz": rate_mhz,
        "path": str(out_path),
        "n_records": n_records,
        "n_overlap": int(n_overlap),
        "overlap_fraction_realized": float(n_overlap / max(n_records, 1)),
        "n_saturated": int(n_saturated),
        "records_by_stave": stave_counts,
        "dt_mean_ns": float(dt_arr.mean()) if dt_arr.size else None,
        "dt_median_ns": float(np.median(dt_arr)) if dt_arr.size else None,
        "dt_max_drawn_ns": float(dt_arr.max()) if dt_arr.size else None,
        "n_unique_dt": int(np.unique(dt_arr).size),
        "digitizer_seed_salt": seed_salt,
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
    ap.add_argument("--card", default=str(DEFAULT_CARD_PATH))
    ap.add_argument("--mapping", choices=("paired", "odd"), default="paired")
    ap.add_argument("--rates", type=float, nargs="+", default=list(RATES_MHZ_DEFAULT),
                    help="pile-up rates in MHz (dt ~ Exp(1/R) truncated to the window)")
    ap.add_argument("--n-records", type=int, default=N_RECORDS_DEFAULT, help="records per rate")
    ap.add_argument("--overlap-fraction", type=float, default=OVERLAP_FRACTION_DEFAULT)
    ap.add_argument("--min-true-amp-adc", type=float, default=MIN_TRUE_AMP_ADC_DEFAULT,
                    help="per-constituent noise-free amplitude selection (data A>1000 analogue)")
    ap.add_argument("--pool-cap", type=int, default=POOL_CAP_DEFAULT, help="reservoir cap per (stave, parity)")
    ap.add_argument("--max-events", type=int, default=0, help="0 = scan all truth events")
    ap.add_argument("--step-size", type=int, default=20000)
    ap.add_argument("--coinc-ns", type=float, default=COINC_NS_DEFAULT)
    args = ap.parse_args()

    import uproot

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    card = load_digitizer_card(args.card)
    pipelines = mc02.build_stave_pipelines(card)
    dig_params = stave_digitizer_params(card)
    n_samples = pipelines["B2"].n_samples
    window_ns = n_samples * pipelines["B2"].sample_spacing_ns
    dt_max_ns = window_ns - T1_NS  # second pulse onset stays inside the window

    t_start = time.time()
    pools = {s: [[], []] for s in STAVES}
    n_seen = {s: [0, 0] for s in STAVES}
    pool_rng = np.random.default_rng(np.random.SeedSequence([MC03_SEED, MC03_SEED_SALT, 0]))

    tree = uproot.open(args.mc)["hibeam"]
    n_entries = int(tree.num_entries)
    entry_stop = n_entries if args.max_events <= 0 else min(args.max_events, n_entries)
    n_events_scanned = 0
    for arrays in tree.iterate(
        list(mc02.TRUTH_BRANCHES), step_size=args.step_size, entry_stop=entry_stop, library="np"
    ):
        collect_pool_chunk(
            arrays,
            event_offset=n_events_scanned,
            mapping=args.mapping,
            coinc_ns=args.coinc_ns,
            min_amp_adc=args.min_true_amp_adc,
            dig_params=dig_params,
            pools=pools,
            n_seen=n_seen,
            rng=pool_rng,
            pool_cap=args.pool_cap,
        )
        n_events_scanned += len(arrays["Sci_bar_LayerID"])
        if n_events_scanned % 200000 < args.step_size:
            print(f"[mc03] pool scan {n_events_scanned}/{entry_stop} "
                  f"({time.time() - t_start:.0f}s)", flush=True)

    for stave in STAVES:
        for parity in (0, 1):
            if not pools[stave][parity]:
                raise RuntimeError(f"empty truth pool for {stave} parity {parity}")
    # stave weights = truth occupancy of selected groups (geometry-poisoned,
    # review P1/MV3 — recorded as a caveat, not corrected here)
    stave_weights = {s: float(sum(n_seen[s])) for s in STAVES}
    print(f"[mc03] pools ready in {time.time() - t_start:.0f}s: "
          f"{ {s: [len(p) for p in pools[s]] for s in STAVES} } seen={n_seen}", flush=True)

    per_rate = []
    for rate_index, rate in enumerate(args.rates):
        rate_tag = f"{rate:g}"
        out_path = out_dir / f"mc03_overlay_rate{rate_tag}MHz.csv.gz"
        meta = generate_rate_sample(
            rate_mhz=float(rate),
            n_records=args.n_records,
            overlap_fraction=args.overlap_fraction,
            pools=pools,
            stave_weights=stave_weights,
            pipelines=pipelines,
            dig_params=dig_params,
            out_path=out_path,
            rate_index=rate_index,
            dt_max_ns=dt_max_ns,
        )
        meta["sha256"] = sha256_file(out_path)
        per_rate.append(meta)
        print(f"[mc03] rate {rate_tag} MHz done: {meta['n_records']} records "
              f"({meta['overlap_fraction_realized']:.3f} overlap) "
              f"({time.time() - t_start:.0f}s)", flush=True)

    manifest = {
        "script": "scripts/mc03_build_overlay_sample.py",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
        "mc_file": str(Path(args.mc).resolve()),
        "n_events_scanned": n_events_scanned,
        "mapping": args.mapping,
        "trigger_offset_ns": T1_NS,
        "window_ns": window_ns,
        "dt_max_ns": dt_max_ns,
        "dt_law": "Exponential(mean=1000/R_MHz ns) truncated to (0, dt_max] via inverse CDF — CONTINUOUS, no grid (review P8)",
        "overlap_fraction": args.overlap_fraction,
        "min_true_amp_adc": args.min_true_amp_adc,
        "amplitude_pairing": "independent draws from the truth population, no ratio restriction",
        "split_hygiene": "train records use even source events, eval records odd source events (both constituents)",
        "pool_cap_per_stave_parity": args.pool_cap,
        "pools": {s: {"kept": [len(p) for p in pools[s]], "seen": n_seen[s]} for s in STAVES},
        "stave_weights": stave_weights,
        "seeds": {"master": MC03_SEED, "salt": MC03_SEED_SALT},
        "card": {
            "path": str(Path(args.card).resolve()),
            "sha256": sha256_file(Path(args.card)),
            "card_id": card.get("card_id"),
            "gain_adc_per_mev": card["digitizer"]["gain_adc_per_mev"],
            "gain_status": card["digitizer"].get("gain_status"),
            "tau_decay_ns_by_stave": {s: dig_params[s]["tau_decay_ns"] for s in STAVES},
        },
        "caveats": [
            "gain is an UNKNOWN placeholder (297 ADC/MeV) — all amplitudes in arbitrary scale (review P1/P2); Phase 2 attributes the MV3 discrepancy to the unsimulated two-arm coincidence trigger (not missing material) and prefers gain ~60 as the trigger-consistent estimate",
            "stave occupancy and amplitude-spectrum weights inherit the MV3 spectrum discrepancy (chi2/ndf=68269; Phase 2 root cause: unsimulated trigger)",
            "single-stave overlays only: both constituents land on the same stave/channel",
            "constituent selection amp>1000 evaluated at the nominal 50 ns placement (phase-locked)",
        ],
        "rates": per_rate,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"[mc03] done in {time.time() - t_start:.0f}s -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
