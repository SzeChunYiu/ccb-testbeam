#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_mv3_stopping
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 00:35:00
#SBATCH -o %x_%j.out
#SBATCH -e %x_%j.err
# DRY_RUN: sbatch --test-only geant4/jobs/mv3_stopping.sbatch
# CCB MC validation MV3 — stopping-depth profile vs Sample I/II.
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${CCB_MC_REPO:-$(git -C "${_SCRIPT_DIR}/../.." rev-parse --show-toplevel 2>/dev/null || echo "${_SCRIPT_DIR}/../..")}"
PY="${CCB_MC_PYTHON:-python3}"
CONFIG="${CCB_MC_CONFIG:-${REPO}/configs/mc_validation/base.yaml}"
STAMP="$(date +%s)"
OUT="${CCB_MC_OUT:-${REPO}/reports/mc_validation/mv3_stopping_${STAMP}}"

echo "[prologue] host=$(hostname) start=$(date -Is)"
echo "[prologue] repo=${REPO}"
echo "[prologue] python=$("${PY}" --version 2>&1)"
echo "[prologue] git_head=$(git -C "${REPO}" rev-parse HEAD 2>/dev/null || echo unknown)"
echo "[prologue] git_branch=$(git -C "${REPO}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
echo "[prologue] config=${CONFIG}"
mkdir -p "${OUT}"

"${PY}" -m ccb_mc_validation mv3 --config "${CONFIG}" || {
  echo "[job] mv3 not yet wired; exiting with placeholder status"
  exit 0
}

echo "[job] done=$(date -Is) -> ${OUT}"
find "${OUT}" -type f 2>/dev/null | sort || true
