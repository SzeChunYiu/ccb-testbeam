#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_mc03_overlay
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 04:00:00
#SBATCH -o %x_%j.out
#SBATCH -e %x_%j.err
# CCB mc03 (Phase 3): truth-labelled two-pulse pile-up overlays at
# 0.5/1.5/3.0 MHz (continuous exponential dt, 70% overlaps + 30% single-pulse
# negatives, 200k records/rate) from the full 1M truth file, followed by the
# S24 honest matched-coverage two-pulse benchmark (card-kernel template fit
# vs HGB on the 18 samples, single failure definition, risk-coverage curves)
# and the independent S10b-style MC tau_eff measurement.
set -euo pipefail
REPO=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam
PY=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3
export MPLCONFIGDIR=/local/slurmtmp.${SLURM_JOB_ID:-$$}/mpl; mkdir -p "$MPLCONFIGDIR"
STAMP=$(date +%s)
OUT=$REPO/reports/mc03_overlay_${STAMP}
OVERLAYS=$OUT/overlays
mkdir -p "$OVERLAYS"
echo "[job] host=$(hostname) start=$(date -Is) out=$OUT"

"$PY" "$REPO/scripts/mc03_build_overlay_sample.py" \
    --mc "$REPO/geant4/data/output_krakow_1M.root" \
    --out "$OVERLAYS" \
    --card "$REPO/configs/mc_validation/digitizer_card.yaml" \
    --mapping paired \
    --rates 0.5 1.5 3.0 \
    --n-records 200000 \
    --overlap-fraction 0.7 \
    --min-true-amp-adc 1000 \
    --max-events 0

"$PY" "$REPO/scripts/s24_two_pulse_honest_benchmark.py" \
    --overlay-dir "$OVERLAYS" \
    --out "$OUT" \
    --card "$REPO/configs/mc_validation/digitizer_card.yaml" \
    --n-boot 500 \
    --tau-boot 300

echo "[job] done=$(date -Is) -> $OUT"; find "$OUT" -maxdepth 1 -type f | sort
