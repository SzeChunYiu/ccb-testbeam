#!/usr/bin/env python3
"""Per-event JOINT proxy/hardware trigger migration matrix (issue #1045 Phase 4 fix).

The aggregate matrix (trigger_migration_matrix.py joining two scan JSONs) assumes
hardware-pass ⊆ proxy sample. That assumption is false: hardware n_pass is gated
on enter_B (B-arm charged entry), not sample_I (two-arm). This script classifies
each event JOINTLY in one pass, producing exact quadrants:

  both         = sample_I AND hardware coincidence
  proxy_only   = sample_I AND NOT hardware
  hardware_only= hardware AND NOT sample_I   (can be > 0)
  neither      = neither

Species attribution mirrors trigger_threshold_scan.py (first charged PDG in
Sci_bar_PDG). Grid: same thresholds x coincidence windows as the scan harness.
"""
import json
import sys

import numpy as np
import uproot

IN = sys.argv[1]
OUT = sys.argv[2]

A_ARM, B_ARM = 2, 1
CHARGED_PDG = {
    2212, 1000010020, 1000010030, 1000020030, 1000020040,
    11, -11, 13, -13, 211, -211, 321, -321,
    1000060120, 1000060130, 1000060140,
}
SPECIES = {
    2212: "proton", 1000010020: "deuteron", 1000010030: "triton",
    1000020030: "he3", 1000020040: "alpha", 1000060120: "C12",
    1000060130: "C13", 1000060140: "C14", 11: "electron", -11: "positron",
    13: "muon_minus", -13: "muon_plus",
}
THRESHOLDS = [0.5, 1.0, 2.0, 5.0]
COINCS = [5.0, 10.0, 15.0, 20.0, 30.0]
BR = [
    "T1_trigger_log_EDep", "T1_trigger_log_Time",
    "T2_trigger_log_EDep", "T2_trigger_log_Time",
    "Sci_bar_LayerID", "Sci_bar_LayerID1", "Sci_bar_PDG", "Sci_bar_Time",
]

# precompute proxy flags per (coinc): sample_I, enter_B, species
# hardware pass per (thr, coinc)
results = {t: {c: {"n": 0, "both": 0, "proxy_only": 0, "hardware_only": 0,
                   "neither": 0,
                   "species": {}}
               for c in COINCS} for t in THRESHOLDS}

with uproot.open(IN) as f:
    tree = f["hibeam"]
    n_total = int(tree.num_entries)
    ev = 0
    for chunk in tree.iterate(BR, step_size=20000, library="np"):
        t1e_all = chunk["T1_trigger_log_EDep"]
        t1t_all = chunk["T1_trigger_log_Time"]
        t2e_all = chunk["T2_trigger_log_EDep"]
        t2t_all = chunk["T2_trigger_log_Time"]
        lay_all = chunk["Sci_bar_LayerID"]
        l1_all = chunk["Sci_bar_LayerID1"]
        pdg_all = chunk["Sci_bar_PDG"]
        tm_all = chunk["Sci_bar_Time"]

        # --- proxy flags once per event (per coinc) ---
        n = len(lay_all)
        sampleI = {c: np.zeros(n, dtype=bool) for c in COINCS}
        enterB = np.zeros(n, dtype=bool)
        species = [None] * n
        for i in range(n):
            lay = np.asarray(lay_all[i]).astype(np.int64)
            l1 = np.asarray(l1_all[i]).astype(np.int64)
            pdg = np.asarray(pdg_all[i]).astype(np.int64)
            tm = np.asarray(tm_all[i]).astype(np.float64)
            prim = None
            for p in pdg:
                if int(p) in CHARGED_PDG:
                    prim = int(p)
                    break
            species[i] = prim
            if len(lay) == 0:
                continue
            ch = np.isin(pdg, list(CHARGED_PDG))
            fb = (l1 == B_ARM) & (lay == 0) & ch
            fa = (l1 == A_ARM) & (lay == 0) & ch
            enterB[i] = fb.any()
            if enterB[i] and fa.any():
                dt = abs(tm[fa].min() - tm[fb].min())
                for c in COINCS:
                    sampleI[c][i] = dt < c

        # --- hardware pass per (thr, coinc) ---
        hw = {(t, c): np.zeros(n, dtype=bool) for t in THRESHOLDS for c in COINCS}
        for i in range(n):
            t1e = np.asarray(t1e_all[i], dtype=np.float64)
            t2e = np.asarray(t2e_all[i], dtype=np.float64)
            for t in THRESHOLDS:
                m1 = t1e >= t
                m2 = t2e >= t
                if not (m1.any() and m2.any()):
                    continue
                dt1 = float(np.asarray(t1t_all[i], dtype=np.float64)[m1].min())
                dt2 = float(np.asarray(t2t_all[i], dtype=np.float64)[m2].min())
                if np.isfinite(dt1) and np.isfinite(dt2):
                    d = abs(dt1 - dt2)
                    for c in COINCS:
                        hw[(t, c)][i] = d < c

        # --- joint quadrants ---
        for t in THRESHOLDS:
            for c in COINCS:
                r = results[t][c]
                h = hw[(t, c)]
                p = sampleI[c]
                r["n"] += n
                both = h & p
                r["both"] += int(both.sum())
                r["proxy_only"] += int((p & ~h).sum())
                r["hardware_only"] += int((h & ~p).sum())
                r["neither"] += int((~h & ~p).sum())
                sp = r["species"]
                for i in range(n):
                    if species[i] is None:
                        continue
                    name = SPECIES.get(species[i], f"PDG_{species[i]}")
                    if name not in sp:
                        sp[name] = {"proxy_n": 0, "both": 0, "hardware_only": 0}
                    if p[i]:
                        sp[name]["proxy_n"] += 1
                        if h[i]:
                            sp[name]["both"] += 1
                    elif h[i]:
                        sp[name]["hardware_only"] += 1
        ev += n
        if ev % 100000 < 20000:
            print(f"  {ev}/{n_total} events", flush=True)

out = {
    "script": "joint_matrix.py (per-event joint classification)",
    "input_file": IN,
    "n_events": n_total,
    "method": "per-event joint: proxy=classify_event_proxy sample_I; "
              "hardware=classify_event_hardware_response coincidence; "
              "quadrants exact, hardware_only NOT forced to 0",
    "reference": {"threshold_mev": 1.0, "coinc_ns": 15.0},
    "grid": results,
    "notes": "supersedes aggregate matrix: aggregate 'both' counted "
             "hardware_pass AND enter_B (not sample_I), inflating both and "
             "forcing hardware_only=0",
}
with open(OUT, "w") as fh:
    json.dump(out, fh, indent=2)
print(f"WROTE {OUT}")
ref = results[1.0][15.0]
print(f"REF 1.0MeV/15ns: both={ref['both']} proxy_only={ref['proxy_only']} "
      f"hardware_only={ref['hardware_only']} "
      f"(proxy_total={ref['both']+ref['proxy_only']})")
