#!/usr/bin/env bash
#SBATCH --job-name=ccb_regen
#SBATCH --output=ccb_regen_%A_%a.out
#SBATCH --error=ccb_regen_%A_%a.err
#SBATCH --time=04:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --array=0-0
#SBATCH --partition=hep
#SBATCH --account=hep2023-1-3
#
# regen_sample.sh -- regenerate the matched optical-calibration sample set
# (proton + deuteron over the calibration energy/position grid, optical mode)
# into a VERSIONED output directory, with per-file provenance + sha256 manifest.
# Produces the ROOT inputs the analyzer needs for the full plot set.
#
# Provenance: RunAction auto-writes <output>.meta.json (seed, particle, energy,
# scales, birks, sipm_n_cells, geometry_hash, optical-table sha256, git_commit).
# After the whole array completes, run make_sample_manifest.py on OUTDIR to
# assemble the per-file sha256 manifest (manifest.json + manifest.csv).
#
# Usage:
#   CCB_SAMPLE_VERSION=v1 sbatch --array=0-$((N-1)) \
#       slurm/regen_sample.sh <build_dir> <out_root> [points_csv]
#
# Defaults: points_csv = slurm/points_sample_regen.csv (48 points); per-point
# nevents taken from the CSV's nevents column (env CCB_REGEN_NEVENTS overrides
# blanks). Scale up by widening --array and/or editing the points file.
set -euo pipefail

# --- runtime env: self-contained (Geant4 libs are NOT on the default linker
# path; the binary needs GCC/12.3.0 + Geant4/11.2.2 loaded to run). ---
if [ -z "${MODULESHOME:-}" ]; then
  source /etc/profile.d/modules.sh 2>/dev/null || true
fi
module purge 2>/dev/null || true
module load GCC/12.3.0 Geant4/11.2.2

BUILD="${1:?build dir}"
OUTROOT="${2:?output root dir}"
# points csv: arg 3, else $CCB_POINTS_CSV, else next to this script.
# (Under sbatch, $0 is the spool copy, so dirname "$0" is NOT the script dir;
#  pass an absolute path or set CCB_POINTS_CSV when submitting via sbatch.)
POINTS="${3:-${CCB_POINTS_CSV:-}}"
if [[ -z "${POINTS}" ]]; then
  _cand="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)/points_sample_regen.csv"
  [[ -f "${_cand}" ]] && POINTS="${_cand}"
fi
[[ -z "${POINTS}" ]] && { echo "error: provide points csv (arg 3) or set CCB_POINTS_CSV" >&2; exit 2; }
VERSION="${CCB_SAMPLE_VERSION:-v1}"
OUTDIR="${OUTROOT}/sample_${VERSION}"
mkdir -p "${OUTDIR}"

EXE="${BUILD}/ccb_stave_sim"
OPTICAL="${BUILD}/optical"
IDX="${SLURM_ARRAY_TASK_ID:-0}"

LINE="$(grep -vE '^\s*(#|$)' "${POINTS}" | sed -n "$((IDX+1))p")"
if [[ -z "${LINE}" ]]; then echo "no sample point at index ${IDX} in ${POINTS}" >&2; exit 1; fi
IFS=',' read -r PART ENE HX HY SEED NEV <<< "${LINE}"
: "${SEED:=$((IDX+1))}"; : "${NEV:=${CCB_REGEN_NEVENTS:-2000}}"; : "${HY:=0}"

export G4FORCENUMBEROFTHREADS="${SLURM_CPUS_PER_TASK:-1}"
export CCB_GIT_COMMIT="$(git -C "$(dirname "${EXE}")" rev-parse HEAD 2>/dev/null || echo unknown)"

OUT="${OUTDIR}/sample_${PART}_${ENE}MeV_x${HX}_y${HY}_s${SEED}.root"
echo "regen idx=${IDX} ${PART} ${ENE}MeV x=${HX} y=${HY} seed=${SEED} nev=${NEV} -> ${OUT}"
srun "${EXE}" \
  --mode optical \
  --particle "${PART}" --energy "${ENE}" \
  --hit-x "${HX}" --hit-y "${HY}" \
  --seed "${SEED}" --nevents "${NEV}" \
  --optical-dir "${OPTICAL}" \
  --output "${OUT}"

echo "wrote ${OUT} (+ ${OUT}.meta.json)"
echo "After the array completes, build the manifest:"
echo "  python3 $(cd "$(dirname "$0")" && pwd)/make_sample_manifest.py ${OUTDIR}"
