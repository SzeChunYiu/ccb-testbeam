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
# CCB MC validation production wrapper.  Heavy work must run inside this SLURM
# allocation; failures are never swallowed or converted to success.
set -euo pipefail

if [[ -z "${SLURM_JOB_ID:-}" ]]; then
  echo "[fatal] mc_validation_pipeline.sbatch must run under SLURM_JOB_ID" >&2
  echo "[fatal] submit with: sbatch --parsable geant4/jobs/mc_validation_pipeline.sbatch" >&2
  exit 64
fi

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${CCB_MC_REPO:-$(git -C "${_SCRIPT_DIR}/../.." rev-parse --show-toplevel 2>/dev/null || echo "${_SCRIPT_DIR}/../..")}"
PY="${CCB_MC_PYTHON:-python3}"
CONFIG="${CCB_MC_CONFIG:-${REPO}/configs/mc_validation/execution.yaml}"
STAMP="$(date +%s)"
OUT="${CCB_MC_OUT:-${REPO}/reports/mc_validation/pipeline_${STAMP}}"
RUN_ID="${CCB_RUN_ID:-slurm_${SLURM_JOB_ID}}"

mkdir -p "${OUT}"

echo "[prologue] host=$(hostname) start=$(date -Is)"
echo "[prologue] slurm_job_id=${SLURM_JOB_ID}"
echo "[prologue] repo=${REPO}"
echo "[prologue] python=$("${PY}" --version 2>&1)"
echo "[prologue] git_head=$(git -C "${REPO}" rev-parse HEAD 2>/dev/null || echo unknown)"
echo "[prologue] git_branch=$(git -C "${REPO}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
echo "[prologue] config=${CONFIG}"
echo "[prologue] out=${OUT}"
echo "[prologue] run_id=${RUN_ID}"

run_step() {
  local label="$1"
  shift
  echo "[pipeline] ${label} start $(date -Is)"
  "$@"
  local rc=$?
  echo "[pipeline] ${label} done rc=${rc} $(date -Is)"
  return "${rc}"
}

export CCB_MC_CONFIG="${CONFIG}"
export CCB_ARTIFACT_ROOT="${CCB_ARTIFACT_ROOT:-${REPO}/reports/mc_validation/runs}"
export PYTHONPATH="${REPO}/src${PYTHONPATH:+:${PYTHONPATH}}"
echo "[prologue] pythonpath=${PYTHONPATH}"

run_step "preflight" "${PY}" "${REPO}/scripts/mc_validation/run_pipeline.py" \
  --run-id "${RUN_ID}" --profile production --config "${CONFIG}" preflight --allow-dirty
run_step "plan" "${PY}" "${REPO}/scripts/mc_validation/run_pipeline.py" \
  --run-id "${RUN_ID}" --profile production --config "${CONFIG}" plan --studies all --freeze
run_step "truth-build" "${PY}" -m ccb_mc_validation truth-build --config "${CONFIG}" --repo-root "${REPO}"
run_step "MV0 digitizer" "${PY}" -m ccb_mc_validation mv0 --config "${CONFIG}" --repo-root "${REPO}"
run_step "MV1 PID" "${PY}" -m ccb_mc_validation mv1 --config "${CONFIG}" --repo-root "${REPO}"
run_step "MV2 energy" "${PY}" -m ccb_mc_validation mv2 --config "${CONFIG}" --repo-root "${REPO}"
run_step "MV3 stopping" "${PY}" -m ccb_mc_validation mv3 --config "${CONFIG}" --repo-root "${REPO}"
run_step "MV9 synthesis" "${PY}" -m ccb_mc_validation synthesize --config "${CONFIG}" --repo-root "${REPO}"

RUN_ROOT="${CCB_ARTIFACT_ROOT}/${RUN_ID}"
mkdir -p "${RUN_ROOT}/reports" "${RUN_ROOT}/logs"
for rel in   reports/mc_validation/mv1_pid/study_result.json   reports/mc_validation/mv2_energy/study_result.json   reports/mc_validation/mv3_stopping_depth/study_result.json   reports/mc_validation/mv9_synthesis/MV9_SYNTHESIS.md   reports/mc_validation/mv9_synthesis/synthesis_scaffold.json; do
  if [[ -f "${REPO}/${rel}" ]]; then
    mkdir -p "${RUN_ROOT}/$(dirname "${rel}")"
    cp "${REPO}/${rel}" "${RUN_ROOT}/${rel}"
  else
    echo "[artifact] missing ${rel}" >&2
    exit 66
  fi
done
cp "${REPO}/ccb_mc_validation_${SLURM_JOB_ID}.out" "${RUN_ROOT}/logs/" 2>/dev/null || true
cp "${REPO}/ccb_mc_validation_${SLURM_JOB_ID}.err" "${RUN_ROOT}/logs/" 2>/dev/null || true
cat > "${RUN_ROOT}/JOB_STATE.json" <<JSON
{"job_id":"${SLURM_JOB_ID}","run_id":"${RUN_ID}","state":"COMPLETED","exit_code":"0:0","host":"$(hostname)","completed_at":"$(date -Is)"}
JSON

echo "[epilogue] artifacts=${RUN_ROOT}"
echo "[epilogue] complete $(date -Is)"
