#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_mv0_calib
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 00:30:00
#SBATCH -o %x_%j.out
#SBATCH -e %x_%j.err
# DRY_RUN: sbatch --test-only geant4/jobs/mv0_calibrate.sbatch
# CCB MC validation MV0 - data-driven ADC gain calibration.
set -euo pipefail
REPO=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam
PY=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3
DATA_CSV="$REPO/reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz"
TRUTH_NPZ="$REPO/reports/mv1_mv2_truth_pid_energy_1782220258/truth_tracks.npz"
export MPLCONFIGDIR=/local/slurmtmp.${SLURM_JOB_ID:-$$}/mpl; mkdir -p "$MPLCONFIGDIR"
STAMP=$(date +%s)
OUT=$REPO/reports/mv0_calibration_${STAMP}

echo "[prologue] host=$(hostname) start=$(date -Is)"
echo "[prologue] repo=${REPO}"
echo "[prologue] python=$("${PY}" --version 2>&1)"
echo "[prologue] git_head=$(git -C "${REPO}" rev-parse HEAD 2>/dev/null || echo unknown)"
echo "[prologue] git_branch=$(git -C "${REPO}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
echo "[prologue] data_csv=${DATA_CSV}"
echo "[prologue] truth_npz=${TRUTH_NPZ}"
echo "[prologue] out=${OUT}"
mkdir -p "$OUT"

cd "$REPO"
"$PY" "$REPO/scripts/mv0_calibrate_from_data.py" \
    --mc "$REPO/geant4/data/output_krakow_1M.root" \
    --data-csv "$DATA_CSV" \
    --truth-npz "$TRUTH_NPZ" \
    --out "$OUT" \
    --max-events 500000

echo "[job] done=$(date -Is) -> $OUT"
find "$OUT" -type f 2>/dev/null | sort || true
