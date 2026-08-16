#!/usr/bin/env bash
#SBATCH --job-name=ccb_stave_calib
#SBATCH --output=ccb_stave_calib_%A_%a.out
#SBATCH --error=ccb_stave_calib_%A_%a.err
#SBATCH --time=04:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=hep
#SBATCH --account=hep2023-1-3
#SBATCH --array=0-0            # override with --array on submit (one per point)
#
# submit_calibration.sh — full optical calibration mode over a grid of
# (particle, energy, hit_x) points. ONE immutable config per array task ->
# ONE output file (no BeamOn-loop overwrite). Provenance recorded per file.
#
# Scientific production is fail-closed on optical inputs. Missing/malformed
# required optical tables abort before event generation; permissive fallback is
# reserved for explicitly non-authorising development runs outside this script.
#
# Self-contained at runtime: the ccb_stave_sim binary needs GCC/12.3.0 +
# Geant4/11.2.2 on the linker path, so we (re)load the modules inside the job.
# MT threading: the sim parses --threads; we default it to the allocation.
#
# Usage:
#   sbatch --array=0-$((N-1)) --cpus-per-task=4 slurm/submit_calibration.sh build/ points.csv out/
# points.csv columns (no header):
#   particle,energy_MeV,hit_x_cm,hit_y_cm,seed,nevents[,theta_deg,phi_deg]
# Env overrides:
#   CCB_NEVENTS  default nevents when the CSV cell is blank (default 2000)
#   CCB_THREADS  worker threads passed to --threads (default = SLURM_CPUS_PER_TASK)
set -euo pipefail

# --- runtime env: self-contained (Geant4 libs are NOT on the default linker
# path; the binary needs GCC/12.3.0 + Geant4/11.2.2 loaded to run). ---
if [ -z "${MODULESHOME:-}" ]; then
  source /etc/profile.d/modules.sh 2>/dev/null || true
fi
module purge 2>/dev/null || true
module load GCC/12.3.0 Geant4/11.2.2

BUILD="${1:?build dir (contains ccb_stave_sim + optical/)}"
POINTS="${2:?points csv}"
OUTDIR="${3:?output dir}"
mkdir -p "${OUTDIR}"

EXE="${BUILD}/ccb_stave_sim"
OPTICAL="${BUILD}/optical"
IDX="${SLURM_ARRAY_TASK_ID:-0}"

# Read the IDX-th data line (skip blank/comment lines).
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
  --mode optical \
  --particle "${PART}" --energy "${ENE}" \
  --hit-x "${HX}" --hit-y "${HY}" \
  --theta "${THETA}" --phi "${PHI}" \
  --seed "${SEED}" --nevents "${NEV}" --threads "${THREADS}" \
  --optical-dir "${OPTICAL}" --strict-optical \
  --output "${OUT}"

echo "wrote ${OUT} (+ ${OUT}.meta.json)"
