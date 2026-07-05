#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_mv3_gain_quenched
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 02:00:00
#SBATCH -o %x_%j.out
#SBATCH -e %x_%j.err
# CCB improvement item B-M5 (reviewer M5): re-run the MV3 stopping-depth gain
# scan with Birks quenching ON (per-hit light = edep/(1+kB*dE/dx)), event
# basis, species-inclusive, paired map, A-arm trigger proxy. The gain ~60 was
# fitted UNQUENCHED; with Birks the trigger-consistent gain must rise (~70-80).
set -euo pipefail
REPO="${CCB_MC_REPO:-/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam}"
PY="${CCB_MC_PYTHON:-/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3}"
DATA_CSV="${REPO}/reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz"
export MPLCONFIGDIR="${MPLCONFIGDIR:-${TMPDIR:-/tmp}/mplcfg_${SLURM_JOB_ID:-$$}}"
mkdir -p "${MPLCONFIGDIR}"

STAMP=$(date +%s)
OUT="${REPO}/reports/mv3_gain_quenched_${STAMP}"
mkdir -p "${OUT}"

echo "[prologue] host=$(hostname) start=$(date -Is)"
echo "[prologue] repo=${REPO}"
echo "[prologue] python=$("${PY}" --version 2>&1)"
echo "[prologue] out=${OUT}"

"${PY}" "${REPO}/scripts/mv3_gain_scan_quenched.py" \
  --mc "${REPO}/geant4/data/output_krakow_1M.root" \
  --data "${DATA_CSV}" \
  --out "${OUT}" \
  --max-events 0

echo "[job] done=$(date -Is) -> ${OUT}"
ls -la "${OUT}"
