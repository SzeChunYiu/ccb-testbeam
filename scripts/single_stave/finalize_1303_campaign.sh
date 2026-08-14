#!/usr/bin/env bash
# Final #1303/#1322 campaign bundle: run both producers over the COMPLETE
# regenerated 5-point grid and stage figures/tables for publication wiring.
set -euo pipefail
B=/projects/hep/fs10/shared/nnbar/billy
WT=$B/ccb-wt-1303
PY=$B/packages/hibeam_env/bin/python
GRID=$WT/geant4/results/1303_grid_regen_v2
TS=$(date -u +%Y%m%dT%H%MZ)
BUNDLE=$WT/reports/paper_1303_optical_campaign_${TS}
cd $WT

# 0) completeness gate: exactly 5 complete points, else abort
n_ok=0
for r in "$GRID"/stave_*.root; do
  m="$r.meta.json"
  [ -f "$m" ] || { echo "INCOMPLETE (no meta): $r"; continue; }
  n=$($PY -c "import uproot,sys; print(uproot.open(sys.argv[1])['events'].num_entries)" "$r" 2>/dev/null || echo 0)
  req=$($PY -c "import json,sys; print(json.load(open(sys.argv[1])).get('n_events_requested',0))" "$m")
  if [ "$n" -ge "$req" ] && [ "$req" -gt 0 ]; then n_ok=$((n_ok+1)); else echo "INCOMPLETE ($n/$req): $r"; fi
done
echo "complete points: $n_ok"
[ "$n_ok" -eq 5 ] || { echo "ABORT: need 5 complete points"; exit 2; }

# 1) stage accounting (#1303)
$PY scripts/single_stave/paper_1303_optical_stage_accounting.py \
  --grid-dir "$GRID" --output "$BUNDLE"

# 2) A09 held-out reconstruction (#1297/#1302 semantics, #1322 package)
$PY scripts/single_stave/paper_a09_heldout_edep_reconstruction.py \
  --grid-dir "$GRID" --output "$BUNDLE/a09" --estimand both
cp -r "$BUNDLE/a09"/* "$BUNDLE"/ 2>/dev/null || true   # flatten for MANIFEST paths

# 3) stage final figures + tables
PUB=$WT/publication
mkdir -p "$PUB/figures/final" "$PUB/tables/final"
for f in 1303_stage_accounting 1303_pe_per_mev 1303_edep_vs_pe \
         edep_reconstruction_heldout_E_vis edep_reconstruction_heldout_E_raw; do
  [ -f "$BUNDLE/figures/$f.pdf" ] && cp "$BUNDLE/figures/$f.pdf" "$PUB/figures/final/$f.pdf"
done
cp "$BUNDLE/tables/1303_stage_accounting.csv" "$BUNDLE/tables/1303_pe_per_mev.csv" "$PUB/tables/final/"
cp "$BUNDLE/a09/heldout_energy_reconstruction_summary_E_vis.csv" "$PUB/tables/final/heldout_energy_reconstruction_summary_E_vis.csv"
cp "$BUNDLE/a09/heldout_energy_reconstruction_summary_E_raw.csv" "$PUB/tables/final/heldout_energy_reconstruction_summary_E_raw.csv"

echo "BUNDLE=$BUNDLE"
echo "=== headline numbers for chapter wiring ==="
$PY - "$BUNDLE" <<'PYIN'
import json, sys
b = sys.argv[1]
s = json.load(open(f"{b}/1303_summary.json"))
print("pooled E_vis cal:", s["pooled_calibration_E_vis"])
for p in s["points"]:
    print(f"{p['species']:8s} {p['ke_MeV']:3d} MeV  PE/MeV_vis={p['pe_per_mev_E_vis']['mean']:.3f} "
          f"[{p['pe_per_mev_E_vis']['ci16']:.3f},{p['pe_per_mev_E_vis']['ci84']:.3f}]  "
          f"PE/MeV_raw={p['pe_per_mev_E_raw']['mean']:.3f}")
try:
    a = json.load(open(f"{b}/a09/result.json"))
    print("A09:", json.dumps(a)[:800])
except FileNotFoundError:
    print("A09 result.json missing")
PYIN
