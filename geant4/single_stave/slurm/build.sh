#!/usr/bin/env bash
# build.sh — configure + build the CCB single-stave simulation on LUNARC.
# Headless (no Qt) by default, per issue #796. Run from geant4/single_stave/.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="${1:-${HERE}/build}"

# Expect Geant4 in the environment (module load or a sourced geant4.sh).
if ! command -v geant4-config >/dev/null 2>&1; then
  echo "error: geant4-config not on PATH. module load Geant4 or source geant4make.sh" >&2
  exit 1
fi
echo "geant4 version: $(geant4-config --version)"

cmake -S "${HERE}" -B "${BUILD}" \
      -DCMAKE_BUILD_TYPE=Release \
      -DCCB_ENABLE_VIS=OFF
cmake --build "${BUILD}" -j "$(nproc)"

echo "--- ctest (geometry + smoke) ---"
ctest --test-dir "${BUILD}" --output-on-failure
echo "build complete: ${BUILD}/ccb_stave_sim"
