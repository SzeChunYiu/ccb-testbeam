#!/usr/bin/env bash
#SBATCH --job-name=ccb_stave_1303
#SBATCH --output=ccb_stave_1303_%A_%a.out
#SBATCH --error=ccb_stave_1303_%A_%a.err
#SBATCH --time=04:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=hep
#SBATCH --account=lu2025-2-51
#SBATCH --array=0-0            # override with --array on submit (one per point)
#
# submit_calibration_1303.sh — issue #1303 grid regeneration with current source
# Updated to include required options for physics-list and neutron-timecut-policy-id
#
set -euo pipefail

# --- runtime env ---
if [ -z "${MODULESHOME:-}" ]; then
  source /etc/profile.d/modules.sh 2>/dev/null || true
fi
module purge 2>/dev/null || true
set +u
module load Anaconda3
conda activate hibeam_g4_250603
set -u

BUILD="${1:?build dir (contains ccb_stave_sim + optical/)}"
POINTS="${2:?points csv}"
OUTDIR="${3:?output dir}"
mkdir -p "${OUTDIR}"

EXE="${BUILD}/ccb_stave_sim"
OPTICAL="${BUILD}/optical"
IDX="${SLURM_ARRAY_TASK_ID:-0}"

# Read the IDX-th data line (skip blank/comment lines)
LINE="$(grep -vE '^\s*(#|$)' "${POINTS}" | sed -n "$((IDX+1))p")"
if [[ -z "${LINE}" ]]; then echo "no point at index ${IDX}" >&2; exit 1; fi
IFS=',' read -r PART ENE HX HY SEED NEV THETA PHI <<< "${LINE}"
: "${SEED:=$((IDX+1))}"
: "${HY:=0}"
: "${NEV:=${CCB_NEVENTS:-2000}}"
: "${THETA:=0}"
: "${PHI:=0}"
THREADS="${CCB_THREADS:-${SLURM_CPUS_PER_TASK:-1}}"

export CCB_GIT_COMMIT="$(git -C "$(dirname "${EXE}")" rev-parse HEAD 2>/dev/null || echo unknown)"
OUT="${OUTDIR}/stave_${PART}_${ENE}MeV_x${HX}_y${HY}_th${THETA}_ph${PHI}_s${SEED}.root"

echo "point idx=${IDX} part=${PART} E=${ENE} MeV x=${HX} y=${HY} theta=${THETA} phi=${PHI} seed=${SEED} nev=${NEV} threads=${THREADS}"
srun "${EXE}" \
  --physics-list QGSP_BIC \
  --neutron-timecut-policy-id pin_qgsp_bic_default_10us \
  --mode optical \
  --particle "${PART}" --energy "${ENE}" \
  --hit-x "${HX}" --hit-y "${HY}" \
  --theta "${THETA}" --phi "${PHI}" \
  --seed "${SEED}" --nevents "${NEV}" --threads "${THREADS}" \
  --optical-dir "${OPTICAL}" --strict-optical \
  --output "${OUT}"

echo "wrote ${OUT} (+ ${OUT}.meta.json)"
