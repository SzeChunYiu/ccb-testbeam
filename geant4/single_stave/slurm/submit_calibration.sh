#!/usr/bin/env bash
#SBATCH --job-name=ccb_stave_calib
#SBATCH --output=ccb_stave_calib_%A_%a.out
#SBATCH --error=ccb_stave_calib_%A_%a.err
#SBATCH --time=04:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --array=0-0            # override with --array on submit (one per point)
#
# submit_calibration.sh — full optical calibration mode over a grid of
# (particle, energy, hit_x) points. ONE immutable config per array task ->
# ONE output file (no BeamOn-loop overwrite). Provenance recorded per file.
#
# Usage:
#   sbatch --array=0-$((N-1)) slurm/submit_calibration.sh build/ points.csv out/
# points.csv columns (no header): particle,energy_MeV,hit_x_cm,hit_y_cm,seed,nevents
set -euo pipefail

BUILD="${1:?build dir}"
POINTS="${2:?points csv}"
OUTDIR="${3:?output dir}"
mkdir -p "${OUTDIR}"

EXE="${BUILD}/ccb_stave_sim"
OPTICAL="${BUILD}/optical"
IDX="${SLURM_ARRAY_TASK_ID:-0}"

# Read the IDX-th data line (skip blank/comment lines).
LINE="$(grep -vE '^\s*(#|$)' "${POINTS}" | sed -n "$((IDX+1))p")"
if [[ -z "${LINE}" ]]; then echo "no point at index ${IDX}"; exit 1; fi
IFS=',' read -r PART ENE HX HY SEED NEV <<< "${LINE}"
: "${SEED:=$((IDX+1))}"; : "${NEV:=2000}"; : "${HY:=0}"

export CCB_GIT_COMMIT="$(git -C "$(dirname "${EXE}")" rev-parse HEAD 2>/dev/null || echo unknown)"
OUT="${OUTDIR}/stave_${PART}_${ENE}MeV_x${HX}_s${SEED}.root"

echo "point idx=${IDX} part=${PART} E=${ENE} x=${HX} y=${HY} seed=${SEED} nev=${NEV}"
srun "${EXE}" \
  --mode optical \
  --particle "${PART}" --energy "${ENE}" \
  --hit-x "${HX}" --hit-y "${HY}" \
  --seed "${SEED}" --nevents "${NEV}" \
  --optical-dir "${OPTICAL}" \
  --output "${OUT}"

echo "wrote ${OUT} (+ ${OUT}.meta.json)"
