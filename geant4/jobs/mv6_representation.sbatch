#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_mv6_repr
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 01:30:00
#SBATCH -o %x_%j.out
#SBATCH -e %x_%j.err
# DRY_RUN: sbatch --test-only geant4/jobs/mv6_representation.sbatch
# CCB MC validation MV6 -- representation & anomaly species ID.
set -euo pipefail
REPO="${CCB_MC_REPO:-/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam}"
PY="${CCB_MC_PYTHON:-/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-${TMPDIR:-/tmp}/mplcfg_${SLURM_JOB_ID:-$$}}"
mkdir -p "${MPLCONFIGDIR}"
echo "[prologue] host=$(hostname) start=$(date -Is)"
echo "[prologue] repo=${REPO}"
echo "[prologue] python=$("${PY}" --version 2>&1)"
cd "${REPO}"
"${PY}" scripts/mv6_representation_study.py \
  --mc geant4/data/output_krakow_1M.root \
  --max-events 300000 --max-tracks 80000
echo "[epilogue] done=$(date -Is)"
