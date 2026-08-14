#!/usr/bin/env bash
# regen_grid_1303.sh — submit the 5-point optical calibration grid regeneration for issue #1303
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${HERE}/../.." && pwd)"
BUILD="${REPO_ROOT}/geant4/single_stave/build"
POINTS="${HERE}/grid_5point.csv"
OUTDIR="${REPO_ROOT}/results/1303_grid_regen"

# Create output directory with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTDIR="${OUTDIR}/${TIMESTAMP}"
mkdir -p "${OUTDIR}"

echo "=== Issue #1303 Grid Regeneration ==="
echo "Repo: ${REPO_ROOT}"
echo "Build: ${BUILD}"
echo "Points: ${POINTS}"
echo "Output: ${OUTDIR}"
echo ""

# Verify build exists
if [[ ! -f "${BUILD}/ccb_stave_sim" ]]; then
  echo "Error: ccb_stave_sim not found at ${BUILD}/ccb_stave_sim"
  echo "Please build first with:"
  echo "  cd ${REPO_ROOT}/geant4/single_stave && mkdir -p build && cd build && cmake .. && cmake --build . -j"
  exit 1
fi

# Count points (skip comments)
N=$(grep -vE '^\s*(#|$)' "${POINTS}" | wc -l)
echo "Found ${N} calibration points"

# Submit array job
echo "Submitting SLURM array job..."
cd "${HERE}"
JOBID=$(sbatch --array=0-$((N-1)) \
  --partition=hep \
  --account=lu2025-2-51 \
  --cpus-per-task=4 \
  --time=04:00:00 \
  submit_calibration_1303.sh "${BUILD}" "${POINTS}" "${OUTDIR}" | awk '{print $NF}')

echo ""
echo "Submitted job ${JOBID}"
echo ""
echo "Monitor with:"
echo "  squeue -j ${JOBID}"
echo "  watch -n 5 squeue -j ${JOBID}"
echo ""
echo "Output files will appear in:"
echo "  ${OUTDIR}"
echo ""
echo "When complete, analyze results with:"
echo "  python3 ${REPO_ROOT}/scripts/single_stave/analyze_single_stave.py ${OUTDIR}/*.root"
