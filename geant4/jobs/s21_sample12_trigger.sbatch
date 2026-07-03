#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_s21_sample12
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 02:00:00
#SBATCH -o %x_%j.out
#SBATCH -e %x_%j.err
# DRY_RUN: sbatch --test-only geant4/jobs/s21_sample12_trigger.sbatch
# CCB S21 — Sample I vs Sample II truth-level B-arm comparison (inclusive
# trigger definitions; tests Matthias' Sample-I deuteron-enrichment
# prediction in B2) on the full 1M MC.
set -euo pipefail

REPO=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam
PY=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3
MC=$REPO/geant4/data/output_krakow_1M.root
export MPLCONFIGDIR=/local/slurmtmp.${SLURM_JOB_ID:-$$}/mpl; mkdir -p "$MPLCONFIGDIR"

STAMP=$(date +%s)
OUT=$REPO/reports/s21_sample12_trigger_truth_${STAMP}
mkdir -p "$OUT"

echo "[job] host=$(hostname) start=$(date -Is)"
echo "[job] git_head=$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown)"
"$PY" --version

"$PY" "$REPO/scripts/s21_sample12_trigger_truth_comparison.py" \
    --mc "$MC" --out "$OUT" --coinc-ns 15 --max-events 0

echo "[job] done=$(date -Is) -> $OUT"; find "$OUT" -type f | sort
