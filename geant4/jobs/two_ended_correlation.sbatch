#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_two_ended_correlation
#SBATCH -N 1 -n 1 -c 2
#SBATCH -t 00:15:00
#SBATCH -o %x_%j.out -e %x_%j.err
set -euo pipefail
REPO="/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam"
PY="/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3"
STAMP=$(date +%s)
OUT="${REPO}/reports/two_ended_correlation_${STAMP}"
mkdir -p "${OUT}"
export CCB_OUTDIR="${OUT}"
echo "[prologue] host=$(hostname) start=$(date -Is) out=${OUT}"
echo "[prologue] python=$("${PY}" --version 2>&1)"
"${PY}" "${REPO}/scripts/two_ended_correlation.py" 2>&1 | tee "${OUT}/run.log"
echo "[job] done=$(date -Is)"
ls "${OUT}"
