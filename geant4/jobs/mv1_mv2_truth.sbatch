#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_mv1mv2
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 00:30:00
#SBATCH -o %x_%j.out
#SBATCH -e %x_%j.err
# CCB MV1 (PID) + MV2 (energy/range) truth-level study on the full 1M MC.
set -euo pipefail
REPO=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam
PY=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3
export MPLCONFIGDIR=/local/slurmtmp.${SLURM_JOB_ID:-$$}/mpl; mkdir -p "$MPLCONFIGDIR"
STAMP=$(date +%s)
OUT=$REPO/reports/mv1_mv2_truth_pid_energy_${STAMP}
mkdir -p "$OUT"
echo "[job] host=$(hostname) start=$(date -Is)"
"$PY" "$REPO/scripts/mv1_mv2_truth_pid_energy.py" \
    --mc "$REPO/geant4/data/output_krakow_1M.root" --out "$OUT"
echo "[job] done=$(date -Is) -> $OUT"; find "$OUT" -type f | sort
