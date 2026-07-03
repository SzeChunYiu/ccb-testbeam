#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_mv4_timing
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 00:30:00
#SBATCH -o %x_%j.out
#SBATCH -e %x_%j.err
# CCB MV4 timing rerun (2026-07-03, post external review):
#   - rising-edge-constrained CFD20 (backward scan from peak)
#   - 1/A timewalk form (MV4b fix)
#   - data anchor corrected to true raw CFD20 pair-diff sigma68 = 2.993 ns
#   - sqrt(2) pair-equivalent conversion; ratio-only report (no pull verdicts)
# NOTE: all digitizer gains retracted (EXTERNAL_REVIEW_2026-07-02.md); the
# calib gain only sets the toy amplitude/noise scale.
set -euo pipefail
REPO=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam
PY=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3
export MPLCONFIGDIR=/local/slurmtmp.${SLURM_JOB_ID:-$$}/mpl; mkdir -p "$MPLCONFIGDIR"
CALIB=$REPO/reports/mv0_calibration_1782677847/calibration.json
STAMP=$(date +%s)
OUT=$REPO/reports/mv4_timing_${STAMP}
mkdir -p "$OUT"
echo "[prologue] host=$(hostname) start=$(date -Is)"
echo "[prologue] repo=$REPO"
echo "[prologue] python=$("$PY" --version 2>&1)"
echo "[prologue] calib=$CALIB"
echo "[prologue] out=$OUT"
"$PY" "$REPO/scripts/mv4_timing_study.py" \
    --mc "$REPO/geant4/data/output_krakow_1M.root" \
    --out "$OUT" \
    --calib "$CALIB" \
    --max-events 0
echo "[job] done=$(date -Is) -> $OUT"; find "$OUT" -type f | sort
