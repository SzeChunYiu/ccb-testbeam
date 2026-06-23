#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_mc_validation
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 8
#SBATCH -t 02:00:00
#SBATCH -o %x_%j.out
#SBATCH -e %x_%j.err
# DRY_RUN: sbatch --test-only geant4/jobs/mc_validation_pipeline.sbatch
# CCB MC validation end-to-end pipeline: MV0 -> MV1-MV3 -> synthesis.
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${CCB_MC_REPO:-$(git -C "${_SCRIPT_DIR}/../.." rev-parse --show-toplevel 2>/dev/null || echo "${_SCRIPT_DIR}/../..")}"
PY="${CCB_MC_PYTHON:-python3}"
CONFIG="${CCB_MC_CONFIG:-${REPO}/configs/mc_validation/base.yaml}"
STAMP="$(date +%s)"
OUT="${CCB_MC_OUT:-${REPO}/reports/mc_validation/pipeline_${STAMP}}"

echo "[prologue] host=$(hostname) start=$(date -Is)"
echo "[prologue] repo=${REPO}"
echo "[prologue] python=$("${PY}" --version 2>&1)"
echo "[prologue] git_head=$(git -C "${REPO}" rev-parse HEAD 2>/dev/null || echo unknown)"
echo "[prologue] git_branch=$(git -C "${REPO}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
echo "[prologue] config=${CONFIG}"
mkdir -p "${OUT}"

run_step() {
  local label="$1"
  shift
  echo "[pipeline] ${label} ..."
  "$@" || echo "[pipeline] ${label} skipped (not yet wired)"
}

run_step "MV0 digitizer" "${PY}" -m ccb_mc_validation mv0-digitize --config "${CONFIG}"
run_step "MV1 PID" "${PY}" -m ccb_mc_validation mv1 --config "${CONFIG}"
run_step "MV2 energy" "${PY}" -m ccb_mc_validation mv2 --config "${CONFIG}"
run_step "MV3 stopping" "${PY}" -m ccb_mc_validation mv3 --config "${CONFIG}"
run_step "MV9 synthesis" "${PY}" -m ccb_mc_validation synthesize --config "${CONFIG}"

echo "[job] done=$(date -Is) -> ${OUT}"
find "${OUT}" -type f 2>/dev/null | sort || true
