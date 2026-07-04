#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_mc02_aarm
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 02:00:00
#SBATCH -o %x_%j.out
#SBATCH -e %x_%j.err
# CCB Phase 4 (2026-07-04): A-arm digitized MC pulse table (S18 MC
# counterpart baseline). LayerID1==2, staves A1..A4 (direct LayerID 0-3
# mapping), Birks ON, tau_decay 50 ns DEFAULT for A staves (no A rows in the
# data template-fit CSV — documented caveat). Occupancy and amplitude medians
# land in manifest.json (amplitude_stats_by_stave).
set -euo pipefail
REPO=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam
PY=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3
export MPLCONFIGDIR=/local/slurmtmp.${SLURM_JOB_ID:-$$}/mpl; mkdir -p "$MPLCONFIGDIR"
STAMP=$(date +%s)
OUT=$REPO/reports/mc02_pulse_table_aarm_${STAMP}
mkdir -p "$OUT"
echo "[job] host=$(hostname) start=$(date -Is) out=$OUT"

"$PY" "$REPO/scripts/mc02_build_mc_pulse_table.py" \
    --mc "$REPO/geant4/data/output_krakow_1M.root" \
    --out "$OUT" \
    --card "$REPO/configs/mc_validation/digitizer_card.yaml" \
    --arm A \
    --apply-birks \
    --max-events 0 \
    --select-a1000

echo "[job] done=$(date -Is) -> $OUT"
find "$OUT" -type f | sort
