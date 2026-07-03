#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_s23_data_mc
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 01:00:00
#SBATCH -o %x_%j.out
#SBATCH -e %x_%j.err
# DRY_RUN: sbatch --test-only geant4/jobs/s23_sample12_data_mc.sbatch
# CCB S23 — Sample I/II data-side closure: data per-stave spectra/occupancy
# (Matthias B2 hardness signature in DATA), three-way data-vs-MC trigger-mimic
# comparison, and the gain/geometry-robust between-sample double ratios.
set -euo pipefail

REPO=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam
PY=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3
DATA=$REPO/reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz
MC=$REPO/reports/mc02_pulse_table_1783107862/mc02_pulse_table_a1000.csv.gz
export MPLCONFIGDIR=/local/slurmtmp.${SLURM_JOB_ID:-$$}/mpl; mkdir -p "$MPLCONFIGDIR"

STAMP=$(date +%s)
OUT=$REPO/reports/s23_sample12_data_mc_${STAMP}
mkdir -p "$OUT"

echo "[job] host=$(hostname) start=$(date -Is)"
echo "[job] git_head=$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown)"
"$PY" --version

"$PY" "$REPO/scripts/s23_sample12_data_mc_comparison.py" \
    --data "$DATA" --mc "$MC" --high-adc 5000 --out "$OUT"

echo "[job] done=$(date -Is) -> $OUT"; find "$OUT" -type f | sort
