#!/usr/bin/env bash
#SBATCH --job-name=ccb_sys
#SBATCH --output=ccb_sys_%A_%a.out
#SBATCH --error=ccb_sys_%A_%a.err
#SBATCH --time=02:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --array=0-0
#SBATCH --partition=hep
#SBATCH --account=hep2023-1-3
#
# submit_systematic.sh -- ONE-physics-knob Slurm-array sweep.
#
# Sweeps a single detector/optical knob over a grid CSV (columns:
# value,label,seed), holding the base beam config fixed. ONE array task ->
# ONE immutable config -> ONE output file + auto-written .meta.json sidecar.
# Provenance (RunAction): seed, particle, energy, birks, reflectivity/attenuation/
# pde scales, coupling, sipm_n_cells, geometry_hash, optical-table sha256,
# git_commit (from $CCB_GIT_COMMIT). Mirrors submit_calibration.sh discipline.
#
# No hardcoded sweep values: every evaluated point lives in the grid CSV under
# slurm/grids/ with a justified-default comment; base beam defaults below are
# the AppConfig documented defaults and are all env-overridable.
#
# Usage:
#   CCB_KNOB=birks sbatch --array=0-4 \
#       slurm/submit_systematic.sh <build_dir> slurm/grids/points_birks_kB.csv out/
#
# Knob -> CLI flag map:
#   birks        -> --birks-kB          (nominal 0.126 mm/MeV)
#   reflectivity -> --reflectivity-scale(nominal 1.0)
#   attenuation  -> --attenuation-scale (nominal 1.0, attenuation LENGTH scale)
#   pde          -> --pde-scale         (nominal 1.0)
#   coupling     -> --coupling          (nominal 1.0, range [0,1])
#   far_end      -> --far-end absorb|mirror (nominal absorb)
#   sipm_cells   -> --sipm-n-cells      (nominal 3600; PENDING sim flag, see below)
#
# Base beam (env-overridable): CCB_BASE_PARTICLE (proton), CCB_BASE_ENERGY (100),
# CCB_BASE_HIT_X (0), CCB_BASE_HIT_Y (0), CCB_BASE_NEVENTS (2000).
set -euo pipefail

# --- runtime env: self-contained (Geant4 libs are NOT on the default linker
# path; the binary needs GCC/12.3.0 + Geant4/11.2.2 loaded to run). ---
if [ -z "${MODULESHOME:-}" ]; then
  source /etc/profile.d/modules.sh 2>/dev/null || true
fi
module purge 2>/dev/null || true
module load GCC/12.3.0 Geant4/11.2.2

BUILD="${1:?build dir (contains ccb_stave_sim + optical/)}"
GRID="${2:?grid csv (columns: value,label,seed)}"
OUTDIR="${3:?output dir}"
KNOB="${CCB_KNOB:?set CCB_KNOB: birks|reflectivity|attenuation|pde|coupling|far_end|sipm_cells}"

mkdir -p "${OUTDIR}"
EXE="${BUILD}/ccb_stave_sim"
OPTICAL="${BUILD}/optical"
IDX="${SLURM_ARRAY_TASK_ID:-0}"

case "${KNOB}" in
  birks)        FLAG="--birks-kB" ;;
  reflectivity) FLAG="--reflectivity-scale" ;;
  attenuation)  FLAG="--attenuation-scale" ;;
  pde)          FLAG="--pde-scale" ;;
  coupling)     FLAG="--coupling" ;;
  far_end)      FLAG="--far-end" ;;
  sipm_cells)   FLAG="--sipm-n-cells" ;;
  *) echo "error: unknown CCB_KNOB '${KNOB}'" >&2; exit 2 ;;
esac

# Read the IDX-th data line (skip blank/comment lines).
LINE="$(grep -vE '^\s*(#|$)' "${GRID}" | sed -n "$((IDX+1))p")"
if [[ -z "${LINE}" ]]; then echo "no grid point at index ${IDX} in ${GRID}" >&2; exit 1; fi
IFS=',' read -r VALUE LABEL SEED <<< "${LINE}"

PART="${CCB_BASE_PARTICLE:-proton}"
ENE="${CCB_BASE_ENERGY:-100}"
HX="${CCB_BASE_HIT_X:-0}"
HY="${CCB_BASE_HIT_Y:-0}"
NEV="${CCB_BASE_NEVENTS:-2000}"
: "${SEED:=$((IDX+1))}"

# Threading: no --threads CLI exists; force the Geant4 MT thread count to match
# the allocation. RunAction enables MT ntuple merging -> a single output file.
export G4FORCENUMBEROFTHREADS="${SLURM_CPUS_PER_TASK:-1}"
export CCB_GIT_COMMIT="$(git -C "$(dirname "${EXE}")" rev-parse HEAD 2>/dev/null || echo unknown)"

OUT="${OUTDIR}/sys_${KNOB}_${LABEL}_s${SEED}.root"

# SiPM cell-count knob needs a --sipm-n-cells CLI flag that AppConfig.cc does
# not yet parse (sipm_n_cells is only a header default). Fail loudly with
# guidance instead of silently running an unchanged geometry.
if [[ "${KNOB}" == "sipm_cells" ]]; then
  if ! "${EXE}" --help 2>&1 | grep -q -- "--sipm-n-cells"; then
    echo "BLOCKER: KNOB=sipm_cells requires a '--sipm-n-cells' flag in AppConfig.cc" >&2
    echo "(sipm_n_cells is currently only a header default, not parsed). Add the" >&2
    echo "flag and this driver passes ${FLAG} ${VALUE} unchanged." >&2
    exit 3
  fi
fi

echo "knob=${KNOB} flag=${FLAG} value=${VALUE} label=${LABEL} seed=${SEED} base=${PART}/${ENE}MeV/x${HX} nev=${NEV}"
srun "${EXE}" \
  --mode optical \
  --particle "${PART}" --energy "${ENE}" \
  --hit-x "${HX}" --hit-y "${HY}" \
  --seed "${SEED}" --nevents "${NEV}" \
  --optical-dir "${OPTICAL}" \
  "${FLAG}" "${VALUE}" \
  --output "${OUT}"

echo "wrote ${OUT} (+ ${OUT}.meta.json)"
