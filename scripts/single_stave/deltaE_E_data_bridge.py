#!/usr/bin/env python3
"""ΔE-E rerun with the COMPOSITE key on real data (A-002 CCB-DELTAE-FIX).

Builds the wide ΔE-E data table from the real per-hit pulse table using the
composite key (source_file_id, run, evt) instead of eventno alone, per
scripts/single_stave/deltaE_E.py contract, and quantifies exactly how many events
the old eventno-only join would have corrupted.
"""
import glob, json, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = "/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam"
SRC = R + "/reports/1781014251.574.7a497937/pulse_taxonomy_table.csv.gz"
OUT = "/projects/hep/fs10/shared/nnbar/billy/ccb_deltae_rerun"
os.makedirs(OUT, exist_ok=True)
SOURCE_FILE_ID = os.path.basename(os.path.dirname(SRC))  # provenance id

df = pd.read_csv(SRC)
ampcol = "median_amp_adc" if "median_amp_adc" in df.columns else "amplitude_adc"
df = df[["run", "evt", "eventno", "stave", ampcol]].copy()
df["stave"] = df["stave"].astype(str)
# aggregate multi-hit: take max amplitude per (run,evt,stave)
agg = df.groupby(["run", "evt", "eventno", "stave"])[ampcol].max().reset_index()

# --- A-002 core: composite key vs eventno-only collision count ---
# unique physical events under the SAFE composite key:
comp = agg[["run", "evt"]].drop_duplicates()
n_comp = len(comp)
# eventno-only would merge events sharing eventno across different (run,evt):
by_eventno = agg.groupby("eventno")[["run", "evt"]].apply(
    lambda g: g.drop_duplicates().shape[0])
collide = int((by_eventno > 1).sum())
collide_events = int(by_eventno[by_eventno > 1].sum())

# --- wide event table (composite key), per deltaE_E contract ---
wide = agg.pivot_table(index=["run", "evt", "eventno"], columns="stave",
                       values=ampcol, aggfunc="max").reset_index()
wide["source_file_id"] = SOURCE_FILE_ID
for b in ("B2", "B4", "B6", "B8"):
    col = b
    wide["amp_" + b] = wide[col].fillna(0.0) if col in wide.columns else 0.0
# ΔE-E definitions (ADC; never relabel MeV)
wide["deltaE_data_adc"] = wide["amp_B2"]
wide["E_data_adc"] = wide["amp_B4"] + wide["amp_B6"] + wide["amp_B8"]
# stopping layer by threshold (deepest B-layer passing threshold)
THR = 200.0
def stopping(row):
    passed = [b for b in ("B2", "B4", "B6", "B8") if row["amp_" + b] > THR]
    return passed[-1] if passed else "none"
wide["stopping_layer"] = wide.apply(stopping, axis=1)
wide["category"] = np.where(wide["E_data_adc"] + wide["deltaE_data_adc"] <= 0,
                            "all_zero", "ok")

result = dict(
    source=SRC, source_file_id=SOURCE_FILE_ID,
    key=["source_file_id", "run", "evt"],
    n_events_composite_key=int(n_comp),
    n_eventno_values=int(agg["eventno"].nunique()),
    eventno_values_spanning_multiple_events=collide,
    events_that_eventno_only_join_would_corrupt=collide_events,
    threshold_adc=THR,
    stopping_distribution={k: int(v) for k, v in
                           wide["stopping_layer"].value_counts().items()},
    staves_present=sorted(set(agg["stave"])),
    units="ADC (data); never relabeled MeV",
    note="B6 absent in this table -> amp_B6=0 (module fills missing bars to 0 "
         "AFTER composite-key validation).",
)
with open(OUT + "/result.json", "w") as fh:
    json.dump(result, fh, indent=2)
wide.to_csv(OUT + "/deltaE_E_events_data.csv", index=False)

# ΔE-E 2D density (the penetration/PID plot, composite-key events)
ok = wide[wide["category"] == "ok"]
plt.figure(figsize=(6, 4.5))
plt.hexbin(ok["E_data_adc"], ok["deltaE_data_adc"], gridsize=40, mincnt=1,
           bins="log", cmap="viridis")
plt.colorbar(label="log count")
plt.xlabel("E = amp(B4+B6+B8) [ADC]")
plt.ylabel("ΔE = amp(B2) [ADC]")
plt.title(f"ΔE-E (composite key, {n_comp} events)")
plt.tight_layout()
plt.savefig(OUT + "/DE-01_deltaE_E_data.png", dpi=130)

print(json.dumps(result, indent=2))
print("DELTAE_RERUN_DONE")
