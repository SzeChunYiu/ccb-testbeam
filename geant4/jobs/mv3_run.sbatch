#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_mv3_run
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 00:35:00
#SBATCH -o %x_%j.out
#SBATCH -e %x_%j.err
# DRY_RUN: sbatch --test-only geant4/jobs/mv3_run.sbatch
# CCB MC validation MV3 - stopping-depth profile vs Sample I/II (data-driven cfg).
set -euo pipefail
REPO=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam
PY=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3
export MPLCONFIGDIR=/local/slurmtmp.${SLURM_JOB_ID:-$$}/mpl; mkdir -p "$MPLCONFIGDIR"
STAMP=$(date +%s)
OUT=$REPO/reports/mv3_stopping_${STAMP}

echo "[prologue] host=$(hostname) start=$(date -Is)"
echo "[prologue] repo=${REPO}"
echo "[prologue] python=$("${PY}" --version 2>&1)"
echo "[prologue] git_head=$(git -C "${REPO}" rev-parse HEAD 2>/dev/null || echo unknown)"
echo "[prologue] git_branch=$(git -C "${REPO}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
echo "[prologue] config=${REPO}/configs/mc_validation/mv3.yaml"
echo "[prologue] out=${OUT}"
mkdir -p "$OUT"

cd "$REPO"
"$PY" "$REPO/scripts/mv3_stopping_depth.py" \
    --mc "$REPO/geant4/data/output_krakow_1M.root" \
    --config "$REPO/configs/mc_validation/mv3.yaml" \
    --out "$OUT"

echo "[job] done=$(date -Is) -> $OUT"
find "$OUT" -type f 2>/dev/null | sort || true
