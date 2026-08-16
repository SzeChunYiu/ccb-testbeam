#!/usr/bin/env bash
# Reproducer for the Cluster D campaign aggregation + MV studies.
# Run on LUNARC. See SUMMARY.md for the full status table.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
export MPLCONFIGDIR=/projects/hep/fs10/shared/nnbar/billy/.mplcache
export PYTHONNOUSERSITE=1
PY=/projects/hep/fs10/shared/nnbar/billy/ccb-py/bin/python
MC=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root
DATA=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz
OUT=reports/studies/clusterD/mv_runs
FIG=reports/studies/clusterD/figures
mkdir -p "$OUT" "$FIG"

echo "[clusterD] MV1+MV2"
$PY scripts/mv1_mv2_truth_pid_energy.py --mc "$MC" --out "$OUT/mv1_mv2" --max-events 200000
echo "[clusterD] MV3"
$PY scripts/mv3_stopping_v3.py --mc "$MC" --data "$DATA" --out "$OUT/mv3" \
    --max-events 200000 --gain 92 --peak-frac 0.75 --net-threshold 100
echo "[clusterD] MV0"
$PY scripts/mv0_calibrate_from_data.py --mc "$MC" --data-csv "$DATA" \
    --truth-npz "$OUT/mv1_mv2/truth_tracks.npz" --out "$OUT/mv0" --max-events 200000
echo "[clusterD] MV4 (toy)"
$PY scripts/mv4_timing_study.py --out "$OUT/mv4" --mc "$MC" \
    --calibration "$OUT/mv0/calibration.json" --synthetic 5000 --max-tracks 5000 --max-events 50000
echo "[clusterD] MV5"
$PY scripts/mv5_pileup_study.py --truth "$OUT/mv1_mv2/truth_tracks.npz" --out "$OUT/mv5" \
    --n-spill 5000 --n-overlap 4
echo "[clusterD] MV6"
$PY scripts/mv6_representation_study.py --mc "$MC" --out "$OUT/mv6" --max-events 50000 --max-tracks 5000

echo "[clusterD] campaign aggregation"
$PY scripts/single_stave/campaign_plots/plot_i885_campaign.py "$FIG"
$PY scripts/single_stave/campaign_plots/analyze_birks_suppression.py "$FIG"
$PY scripts/single_stave/campaign_plots/sipm_sensitivity.py "$FIG"

echo "[clusterD] VIS-MC diagnostics"
$PY scripts/single_stave/campaign_plots/single_stave_diagnostics.py "$FIG"
$PY scripts/single_stave/campaign_plots/vis_mc_002_transport.py "$FIG"

echo "[clusterD] ALL DONE"
