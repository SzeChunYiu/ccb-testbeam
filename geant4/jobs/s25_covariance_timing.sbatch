#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_s25_covariance
#SBATCH -N 1 -n 1 -c 4
#SBATCH -t 02:00:00
#SBATCH -o %x_%j.out -e %x_%j.err
# B-M4: measured inter-stave timing covariance + covariance-correct combined
# resolution + confirmation-partition sign-off.
set -euo pipefail
REPO=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam
PY=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3
export MPLCONFIGDIR=/local/slurmtmp.${SLURM_JOB_ID:-$$}/mpl; mkdir -p "$MPLCONFIGDIR"
STAMP=$(date +%s)
OUT=$REPO/reports/s25_covariance_timing_${STAMP}
mkdir -p "$OUT"
echo "[job] host=$(hostname) start=$(date -Is) out=$OUT"
"$PY" "$REPO/scripts/s25_covariance_timing.py" \
    --raw-dir "$REPO/data/root/root" \
    --out "$OUT" 2>&1 | tee "$OUT/run.log"
echo "[job] done=$(date -Is) -> $OUT"
find "$OUT" -type f | sort
