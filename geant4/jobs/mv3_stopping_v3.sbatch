#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_mv3v3
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 01:00:00
#SBATCH -o %x_%j.out
#SBATCH -e %x_%j.err

set -euo pipefail
REPO="${CCB_MC_REPO:-/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam}"
PY="${CCB_MC_PYTHON:-/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3}"
DATA_CSV="/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz"
export MPLCONFIGDIR="${MPLCONFIGDIR:-${TMPDIR:-/tmp}/mplcfg_${SLURM_JOB_ID:-$$}}"
mkdir -p "${MPLCONFIGDIR}"

STAMP=$(date +%s)
OUT="${REPO}/reports/mv3_stopping_v3_${STAMP}"
mkdir -p "${OUT}"

echo "[prologue] host=$(hostname) start=$(date -Is)"
echo "[prologue] repo=${REPO}"
echo "[prologue] python=$("${PY}" --version 2>&1)"
echo "[prologue] out=${OUT}"

"${PY}" "${REPO}/scripts/mv3_stopping_v3.py" \
  --mc "${REPO}/geant4/data/output_krakow_1M.root" \
  --data "${DATA_CSV}" \
  --out "${OUT}" \
  --gain 92.0 \
  --net-threshold 1000.0 \
  --max-events 0

echo "[job] done=$(date -Is) -> ${OUT}"
ls "${OUT}"
