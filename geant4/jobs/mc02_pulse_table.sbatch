#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_mc02_pulse
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 02:00:00
#SBATCH -o %x_%j.out
#SBATCH -e %x_%j.err
# CCB mc02: per-stave truth-labelled MC pulse table from the full 1M truth
# (card-driven digitizer, Phase 1), + 100k zero-signal pedestal sample,
# + MV7 pedestal validation, + physical validation REPORT.md.
set -euo pipefail
REPO=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam
PY=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3
export MPLCONFIGDIR=/local/slurmtmp.${SLURM_JOB_ID:-$$}/mpl; mkdir -p "$MPLCONFIGDIR"
STAMP=$(date +%s)
OUT=$REPO/reports/mc02_pulse_table_${STAMP}
mkdir -p "$OUT"
echo "[job] host=$(hostname) start=$(date -Is) out=$OUT"

"$PY" "$REPO/scripts/mc02_build_mc_pulse_table.py" \
    --mc "$REPO/geant4/data/output_krakow_1M.root" \
    --out "$OUT" \
    --card "$REPO/configs/mc_validation/digitizer_card.yaml" \
    --mapping paired \
    --max-events 0 \
    --select-a1000 \
    --zero-signal 100000

"$PY" "$REPO/scripts/mv7_pedestal_validation.py" \
    --zero-signal "$OUT/mc02_zero_signal.csv.gz" \
    --out "$OUT"

"$PY" "$REPO/scripts/mc02_validate_pulse_table.py" \
    --report-dir "$OUT" \
    --card "$REPO/configs/mc_validation/digitizer_card.yaml"

echo "[job] done=$(date -Is) -> $OUT"; find "$OUT" -type f | sort
