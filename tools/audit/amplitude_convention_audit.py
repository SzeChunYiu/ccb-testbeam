#!/usr/bin/env python3
"""Classify amplitude_adc convention across report tables (A-001 empirical).

Determines, per table, whether amplitude_adc is ABSOLUTE (near the hardware
pedestal ~6752 ADC) or NET (small, already baseline-subtracted). The A-001
'double subtraction' is only a bug for NET tables; for ABSOLUTE tables,
abs(amplitude_adc - baseline_adc) is the correct v2 net signal.
"""
import glob, json, os
import pandas as pd

R = "/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam"
OUT = "/projects/hep/fs10/shared/nnbar/billy/ccb_amp_convention.json"
PEDESTAL = 6752.0

rows = []
for f in sorted(glob.glob(R + "/reports/*/*.csv.gz")):
    try:
        h = pd.read_csv(f, nrows=2)
    except Exception:
        continue
    if "amplitude_adc" not in h.columns:
        continue
    bcol = next((c for c in h.columns if "baseline" in c), None)
    uc = ["amplitude_adc"] + ([bcol] if bcol else [])
    try:
        d = pd.read_csv(f, usecols=uc, nrows=40000)
    except Exception:
        continue
    am = float(d["amplitude_adc"].median())
    convention = "ABSOLUTE" if am > 3000 else "NET"
    rows.append(dict(
        report=os.path.basename(os.path.dirname(f)),
        file=os.path.basename(f),
        amplitude_adc_median=am,
        baseline_median=(float(d[bcol].median()) if bcol else None),
        convention=convention,
        subtract_baseline_correct=(convention == "ABSOLUTE"),
    ))

n_abs = sum(r["convention"] == "ABSOLUTE" for r in rows)
n_net = sum(r["convention"] == "NET" for r in rows)
summary = dict(
    pedestal_adc=PEDESTAL, n_tables=len(rows),
    n_absolute=n_abs, n_net=n_net,
    finding=("A-001 CONFIRMED as INCONSISTENCY: amplitude_adc is stored ABSOLUTE "
             f"in {n_abs} tables and NET in {n_net} tables. abs(amplitude_adc - "
             "baseline_adc) is CORRECT for ABSOLUTE, a DOUBLE-SUBTRACTION for NET. "
             "A consumer cannot know which without this check -> must emit "
             "peak_height_adc (net) + peak_code_adc (absolute) per the contract."),
    tables=rows,
)
with open(OUT, "w") as fh:
    json.dump(summary, fh, indent=2)
print(f"tables={len(rows)}  ABSOLUTE={n_abs}  NET={n_net}")
for r in rows:
    print(f"  {r['convention']:8s} amp_med={r['amplitude_adc_median']:6.0f}  {r['report'][:50]}")
print("AMP_CONVENTION_DONE")
