#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_s27_earlypeak
#SBATCH -N 1 -n 1 -c 4
#SBATCH -t 02:00:00
#SBATCH -o %x_%j.out -e %x_%j.err
# B-M8: early-peak class (peak_sample<=3) leakage budget for timing/tau_eff/pile-up.
set -euo pipefail
REPO=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam
PY=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3
export MPLCONFIGDIR=/local/slurmtmp.${SLURM_JOB_ID:-$$}/mpl; mkdir -p "$MPLCONFIGDIR"
STAMP=$(date +%s)
OUT=$REPO/reports/s27_earlypeak_budget_${STAMP}
S00=$REPO/reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz
mkdir -p "$OUT"
echo "[job] host=$(hostname) start=$(date -Is) out=$OUT"
"$PY" "$REPO/scripts/s27_earlypeak_budget.py" \
    --raw-dir "$REPO/data/root/root" \
    --s00-table "$S00" \
    --out "$OUT" 2>&1 | tee "$OUT/run.log"
echo "[job] done=$(date -Is) -> $OUT"
find "$OUT" -type f | sort
