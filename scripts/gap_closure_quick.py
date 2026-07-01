#!/usr/bin/env python3
"""GAP-07 and Methodology 3.5: Chi-squared/NDF + Tau_eff Cross-Check

GAP-07: Add chi2/ndf and tail fraction to all timing residual fits
GAP-08: Cross-check TOF against TPC/trigger
Methodology 3.5: Alternative tau_eff measurement methods
"""
import json, os, sys, numpy as np
from pathlib import Path

OUT = Path(os.environ.get("CCB_OUTDIR", "/tmp/gap_closure_quick"))
OUT.mkdir(parents=True, exist_ok=True)

results = {}

# GAP-07: Chi-squared/ndf framework
results["GAP-07_chi2ndf"] = {
    "study": "Add chi2/ndf to all timing residual fits",
    "description": "All Gaussian-core fits should report chi2/ndf and tail fraction",
    "current_state": "sigma68 is robust but Gaussian-core fits lack chi2/ndf",
    "recommended_reporting": {
        "sigma68": "robust half-width (already reported)",
        "gaussian_sigma": "fitted sigma of Gaussian core",
        "chi2_ndf": "goodness-of-fit for Gaussian-core hypothesis",
        "tail_fraction": "fraction of residuals beyond +-2.5 sigma",
        "anderson_darling": "Anderson-Darling statistic for normality test"
    },
    "implementation": "Add to scripts/s02_timing_pickoff.py output section",
    "gap_closure": "Requires code change to timing script. Framework defined here."
}

# Methodology 3.5: Alternative tau_eff measurement
results["methodology_tau_eff_crosscheck"] = {
    "study": "Alternative tau_eff measurement methods",
    "description": "Cross-validate the 10% tail-crossing method with alternatives",
    "methods": {
        "current": {
            "name": "10% tail-crossing",
            "value_ns": 124.79,
            "ci_ns": [123.33, 126.36]
        },
        "alternative_1": {
            "name": "Exponential fit to pulse tail",
            "description": "Fit exp(-t/tau) to samples 8-17 of high-SNR pulses",
            "expected_tau_ns": "~120-130 (from scintillator decay time + WLS smearing)"
        },
        "alternative_2": {
            "name": "CFD threshold scan",
            "description": "Vary CFD threshold 10-90%; measure time-shift slope",
            "expected_tau_ns": "~120-130 (from timing walk vs threshold)"
        },
        "alternative_3": {
            "name": "MV5 MC self-consistency",
            "description": "MC tau_eff from truth-level overlap rejection",
            "value_ns": 124.8,
            "agreement": "0.2% with data"
        }
    },
    "recommendation": "MV5 already provides independent MC confirmation. "
                       "Add at least one data-only alternative (exponential tail fit) "
                       "as a cross-check.",
    "gap_closure": "Partially closed. MV5 cross-check exists. Data-only alternative still needed."
}

# GAP-08: TOF scale
results["GAP-08_tof_scale"] = {
    "study": "Absolute TOF scale validation",
    "description": "Cross-check absolute time-of-flight against independent reference",
    "methods": {
        "tpc_track_length": "Use TPC track length + expected velocity for protons",
        "trigger_scintillator": "Use trigger coincidence as t0 reference",
        "expected_tof": "For 190 MeV protons over 100 cm: ~2.3 ns (beta ~ 0.57)"
    },
    "status": "Not yet implemented. Requires TPC track reconstruction output.",
    "gap_closure": "Depends on TPC data availability"
}

with open(OUT / "gap_closure_quick_report.json", "w") as f:
    json.dump(results, f, indent=2)

print(json.dumps(results, indent=2))
print(f"report -> {OUT}/gap_closure_quick_report.json")
