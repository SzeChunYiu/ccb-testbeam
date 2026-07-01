#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_mv4b_tw
#SBATCH -N 1 -n 1 -c 4
#SBATCH -t 00:30:00
#SBATCH -o %x_%j.out -e %x_%j.err
set -euo pipefail
REPO="${CCB_MC_REPO:-/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam}"
PY="${CCB_MC_PYTHON:-/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3}"
STAMP=$(date +%s)
OUT="${REPO}/reports/mv4b_timewalk_${STAMP}"
mkdir -p "${OUT}"
echo "[prologue] host=$(hostname) start=$(date -Is) out=${OUT}"
"${PY}" "${REPO}/scripts/mv4b_timewalk_model.py" --outdir "${OUT}" 2>&1 | tee "${OUT}/run.log"
echo "[job] done=$(date -Is)"
ls "${OUT}"
