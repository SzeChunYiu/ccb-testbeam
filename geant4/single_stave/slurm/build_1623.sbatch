#!/usr/bin/env bash
#SBATCH --job-name=ccb1623_build
#SBATCH --output=%x_%j.out
#SBATCH --error=%x_%j.err
#SBATCH --time=01:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --partition=hep
#SBATCH --account=hep2023-1-3
set -euo pipefail
if [ -z "${MODULESHOME:-}" ]; then source /etc/profile.d/modules.sh 2>/dev/null || true; fi
module purge 2>/dev/null || true
module load GCC/12.3.0 Geant4/11.2.2
HERE=/projects/hep/fs10/shared/nnbar/billy/ccb-wt-1623/geant4/single_stave
BUILD=${CCB_BUILD:-$HERE/build}
geant4-config --version
cmake -S "$HERE" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release -DCCB_ENABLE_VIS=OFF
cmake --build "$BUILD" -j 16
echo "BUILD_OK $BUILD/ccb_stave_sim"
ls -la "$BUILD/ccb_stave_sim"
