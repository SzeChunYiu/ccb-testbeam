#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_s22_timing_amp
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 02:00:00
#SBATCH -o %x_%j.out
#SBATCH -e %x_%j.err
# DRY_RUN: sbatch --test-only geant4/jobs/s22_timing_vs_amplitude.sbatch
# CCB S22 — per-stave timing resolution vs amplitude (raw CFD20 rising-edge
# constrained + LORO amp-only timewalk; per-pair-centered sigma68 in bins of
# the min pair amplitude; Sample I and Sample II separately; B2 flagged).
set -euo pipefail

REPO=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam
PY=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3
RAW=$REPO/data/root/root
export MPLCONFIGDIR=/local/slurmtmp.${SLURM_JOB_ID:-$$}/mpl; mkdir -p "$MPLCONFIGDIR"

STAMP=$(date +%s)
OUT=$REPO/reports/s22_timing_vs_amplitude_${STAMP}
mkdir -p "$OUT"

echo "[job] host=$(hostname) start=$(date -Is)"
echo "[job] git_head=$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown)"
"$PY" --version

cd "$REPO"
"$PY" "$REPO/scripts/s22_timing_vs_amplitude.py" \
    --raw-dir "$RAW" --out "$OUT"

echo "[job] done=$(date -Is) -> $OUT"; find "$OUT" -type f | sort
