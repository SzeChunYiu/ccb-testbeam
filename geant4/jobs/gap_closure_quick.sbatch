#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_gap_closure_quick
#SBATCH -N 1 -n 1 -c 2
#SBATCH -t 00:15:00
#SBATCH -o %x_%j.out -e %x_%j.err
set -euo pipefail
REPO="/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam"
PY="/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3"
STAMP=$(date +%s)
OUT="${REPO}/reports/gap_closure_quick_${STAMP}"
mkdir -p "${OUT}"
export CCB_OUTDIR="${OUT}"
echo "[prologue] host=$(hostname) start=$(date -Is) out=${OUT}"
echo "[prologue] python=$("${PY}" --version 2>&1)"
"${PY}" "${REPO}/scripts/gap_closure_quick.py" 2>&1 | tee "${OUT}/run.log"
echo "[job] done=$(date -Is)"
ls "${OUT}"
