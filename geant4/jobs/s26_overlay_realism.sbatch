#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_s26_overlay_realism
#SBATCH -N 1 -n 1 -c 8
#SBATCH -t 04:00:00
#SBATCH -o %x_%j.out -e %x_%j.err
# B-M7: two-pulse overlay realism (trigger-phase jitter + cross-stave overlays).
set -euo pipefail
REPO=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam
PY=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3
export MPLCONFIGDIR=/local/slurmtmp.${SLURM_JOB_ID:-$$}/mpl; mkdir -p "$MPLCONFIGDIR"
STAMP=$(date +%s)
OUT=$REPO/reports/s26_overlay_realism_${STAMP}
mkdir -p "$OUT"
echo "[job] host=$(hostname) start=$(date -Is) out=$OUT"
"$PY" "$REPO/scripts/s26_overlay_realism.py" \
    --mc "$REPO/geant4/data/output_krakow_1M.root" \
    --card "$REPO/configs/mc_validation/digitizer_card.yaml" \
    --out "$OUT" 2>&1 | tee "$OUT/run.log"
echo "[job] done=$(date -Is) -> $OUT"
find "$OUT" -type f | sort
