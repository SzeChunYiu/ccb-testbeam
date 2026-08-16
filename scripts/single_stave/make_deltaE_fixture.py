#!/usr/bin/env python3
"""
Deterministic synthetic fixture for ``deltaE_E.py`` (fully offline).

Emits a DATA wide event table and an MC wide event table that share the
COMPOSITE key ``(source_file_id, run_id, event_id)``, engineered so the unit
tests can exercise every guarantee in the dE-E contract:

  * TWO runs ("runA", "runB") in the same source file reuse event numbers, so
    ``event_id == 5`` exists in both runs -- a bare-``event_id`` join would
    cross-contaminate them; the composite key must keep them separate.
  * At least one KNOWN all-zero-downstream event (an empty / noise event) whose
    stopping category must resolve to ``no_layer_passes``.
  * Sample I is constructed as a strict subset of Sample II.
  * Saturation flags are set on the highest-amplitude events.

Same ``--seed`` reproduces byte-identical tables.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

RUNS = ("runA", "runB")
SOURCE_FILE_ID = "sf0"
SAT_CEILING_ADC = 3500.0  # amp values at/above this are flagged saturated


def build_tables(n_per_run: int, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    data_rows, mc_rows = [], []

    for run in RUNS:
        for eid in range(n_per_run):
            # A small, KNOWN empty/noise event: event_id 0 in runA is all-zero.
            empty = (run == "runA" and eid == 0)

            # Range-out depth: how deep the particle punches (0..len layers).
            depth = int(rng.integers(1, 5))  # 1..4 layers reached on the E side
            # Delta-E (thin B2) energy deposit [MeV] -- large, dE/dx peak. The
            # upper tail (> ~2.9 MeV) drives the amplifier into ADC saturation.
            edep_b2 = 0.0 if empty else float(rng.uniform(0.8, 3.4))
            # Downstream E layers deposit decreasing energy until the particle stops.
            e_layers = ["B4", "B6", "B8", "B10", "B12"]
            edeps = {}
            for i, b in enumerate(e_layers):
                if empty or i >= depth:
                    edeps[b] = 0.0
                else:
                    edeps[b] = float(rng.uniform(0.3, 1.5))

            gain = 1200.0  # ADC per MeV (data amp ~ gain * edep + noise)

            def to_adc(mev: float) -> float:
                if mev <= 0:
                    return float(max(0.0, rng.normal(4.0, 3.0)))  # pedestal noise
                adc = gain * mev + rng.normal(0, 40)
                return float(min(adc, SAT_CEILING_ADC))  # ADC clips at the ceiling

            amp_b2 = to_adc(edep_b2)
            amp_b4 = to_adc(edeps["B4"])
            amp_b6 = to_adc(edeps["B6"])
            amp_b8 = to_adc(edeps["B8"])

            sat = {b: (v >= SAT_CEILING_ADC) for b, v in
                   {"B2": amp_b2, "B4": amp_b4, "B6": amp_b6, "B8": amp_b8}.items()}
            thr = {b: (v >= 20.0) for b, v in
                   {"B2": amp_b2, "B4": amp_b4, "B6": amp_b6, "B8": amp_b8}.items()}

            # Sample assignment: Sample II ~ 60% of non-empty events; Sample I is
            # a STRICT SUBSET of Sample II (half of the II events).
            r = rng.random()
            if empty:
                sample = ""
            elif r < 0.30:
                sample = "I;II"   # in both -> guarantees I subset of II
            elif r < 0.60:
                sample = "II"     # II only
            else:
                sample = ""       # neither

            data_rows.append({
                "source_file_id": SOURCE_FILE_ID,
                "run_id": run,
                "event_id": eid,
                "amp_B2": amp_b2, "amp_B4": amp_b4, "amp_B6": amp_b6, "amp_B8": amp_b8,
                "saturation_B2": sat["B2"], "saturation_B4": sat["B4"],
                "saturation_B6": sat["B6"], "saturation_B8": sat["B8"],
                "threshold_pass_B2": thr["B2"], "threshold_pass_B4": thr["B4"],
                "threshold_pass_B6": thr["B6"], "threshold_pass_B8": thr["B8"],
                "sample": sample,
                "trigger_definition": "beam_coincidence_v1",
            })
            # Unit PrimaryWeight by default; unequal-weight tests override (#1022).
            mc_rows.append({
                "source_file_id": SOURCE_FILE_ID,
                "run_id": run,
                "event_id": eid,
                "edep_B2": edep_b2,
                "edep_B4": edeps["B4"], "edep_B6": edeps["B6"], "edep_B8": edeps["B8"],
                "edep_B10": edeps["B10"], "edep_B12": edeps["B12"],
                "PrimaryWeight": 1.0,
                "sample": sample,
                "trigger_definition": "beam_coincidence_v1",
            })

    return pd.DataFrame(data_rows), pd.DataFrame(mc_rows)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Synthetic dE-E fixture (data + MC).")
    p.add_argument("--out-dir", required=True, type=Path)
    p.add_argument("--n-per-run", type=int, default=1500,
                   help="Events per run (two runs are emitted).")
    p.add_argument("--seed", type=int, default=20260720)
    p.add_argument("--format", choices=["parquet", "csv"], default="parquet")
    a = p.parse_args(argv)

    a.out_dir.mkdir(parents=True, exist_ok=True)
    data, mc = build_tables(a.n_per_run, a.seed)

    ext = "parquet" if a.format == "parquet" else "csv"
    data_path = a.out_dir / f"deltaE_data.{ext}"
    mc_path = a.out_dir / f"deltaE_mc.{ext}"
    if a.format == "parquet":
        data.to_parquet(data_path, index=False)
        mc.to_parquet(mc_path, index=False)
    else:
        data.to_csv(data_path, index=False)
        mc.to_csv(mc_path, index=False)

    print(f"data: {data_path}  ({len(data)} rows)")
    print(f"mc:   {mc_path}  ({len(mc)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
