#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_mc02_birks
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 03:00:00
#SBATCH -o %x_%j.out
#SBATCH -e %x_%j.err
# CCB Phase 4 (2026-07-04): rebuild the B-arm MC pulse table WITH Birks
# quenching (per-hit dE/dx; card apply_birks now true), then run the MV6
# honest redo (mv6b) against the unquenched Phase-1 twin
# reports/mc02_pulse_table_1783107862 (identical card/seeds; the only
# difference is the quench). Fixes review F2.2/F6.2.
set -euo pipefail
REPO=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam
PY=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3
export MPLCONFIGDIR=/local/slurmtmp.${SLURM_JOB_ID:-$$}/mpl; mkdir -p "$MPLCONFIGDIR"
STAMP=$(date +%s)
OUT=$REPO/reports/mc02_pulse_table_birks_${STAMP}
MV6B_OUT=$REPO/reports/mv6b_anomaly_quenching_${STAMP}
UNQUENCHED=$REPO/reports/mc02_pulse_table_1783107862
mkdir -p "$OUT" "$MV6B_OUT"
echo "[job] host=$(hostname) start=$(date -Is) out=$OUT mv6b=$MV6B_OUT"

"$PY" "$REPO/scripts/mc02_build_mc_pulse_table.py" \
    --mc "$REPO/geant4/data/output_krakow_1M.root" \
    --out "$OUT" \
    --card "$REPO/configs/mc_validation/digitizer_card.yaml" \
    --arm B \
    --apply-birks \
    --mapping paired \
    --max-events 0 \
    --select-a1000

"$PY" "$REPO/scripts/mc02_validate_pulse_table.py" \
    --report-dir "$OUT" \
    --card "$REPO/configs/mc_validation/digitizer_card.yaml"

"$PY" "$REPO/scripts/mv6b_anomaly_with_quenching.py" \
    --quenched "$OUT" \
    --unquenched "$UNQUENCHED" \
    --out "$MV6B_OUT" \
    --threshold-adc 1000 \
    --gain-native 297 \
    --gains 60 297

echo "[job] done=$(date -Is) -> $OUT , $MV6B_OUT"
find "$OUT" "$MV6B_OUT" -type f | sort
