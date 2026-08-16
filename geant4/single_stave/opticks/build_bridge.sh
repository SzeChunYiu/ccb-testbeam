#!/bin/bash -l
# Build the CCB Opticks GPU bridge (ccb_opticks_gpu). The bridge links against
# the out-of-tree Opticks install; Opticks source is NOT vendored into
# ccb-testbeam (the two canonical repo sources are injected into the configured
# Opticks g4cx build tree by env/path, exactly how Opticks' own tests build).
#
# Env replicated from opticks-spike/build_opticks.sh (module GCC only + the
# opticks-prepend-prefix foreign externals, which is what Opticks' FindG4 needs).
set +e
SPIKE=${SPIKE:-/projects/hep/fs10/shared/nnbar/billy/opticks-spike}
WT=${WT:-/projects/hep/fs10/shared/nnbar/billy/ccb-wt-opticks}
SRC=$WT/geant4/single_stave/opticks

module purge >/dev/null 2>&1
module load GCC/12.3.0 >/dev/null 2>&1
export HOME=$SPIKE/home
export CUDA_HOME=/sw/easybuild_milan/software/CUDA/12.6.0
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}
export OPTICKS_HOME=$SPIKE/src/opticks
export OPTICKS_PREFIX=$SPIKE/opticks-install
export OPTICKS_CUDA_PREFIX=$CUDA_HOME
export OPTICKS_OPTIX_PREFIX=$SPIKE/optix-install
export OPTICKS_COMPUTE_CAPABILITY=86
export OPTICKS_CONFIG=Release
unset CMAKE_PREFIX_PATH PKG_CONFIG_PATH
opticks-(){  [ -r $OPTICKS_HOME/opticks.bash ] && . $OPTICKS_HOME/opticks.bash && opticks-env "$@" ; }
opticks- >/dev/null 2>&1
opticks-prepend-prefix /sw/easybuild_milan/software/CLHEP/2.4.7.1-GCC-12.3.0 >/dev/null 2>&1
opticks-prepend-prefix /sw/easybuild_milan/software/Xerces-C++/3.2.4-GCCcore-12.3.0 >/dev/null 2>&1
opticks-prepend-prefix /sw/easybuild_milan/software/Geant4/11.2.2-GCC-12.3.0 >/dev/null 2>&1
opticks-prepend-prefix /sw/easybuild_milan/software/X11/20230603-GCCcore-12.3.0 >/dev/null 2>&1
opticks-prepend-prefix /sw/easybuild_milan/software/Mesa/23.1.4-GCCcore-14.3.0 >/dev/null 2>&1
opticks-prepend-prefix /sw/easybuild_milan/software/OpenGL/2025.09-GCCcore-14.3.0 >/dev/null 2>&1

OPTDIR=$OPTICKS_HOME/g4cx/tests
BLD=$SPIKE/opticks-install/build/g4cx
BIN=$BLD/tests/ccb_opticks_gpu
mkdir -p "$HOME"
cp "$SRC/ccb_opticks_gpu.cc" "$OPTDIR/ccb_opticks_gpu.cc"
cp "$SRC/ccb_setGeometry.cc" "$OPTDIR/ccb_setGeometry.cc"
cp "$SRC/CCBSensorIdentifier.h" "$OPTDIR/CCBSensorIdentifier.h"
CL=$OPTDIR/CMakeLists.txt
grep -q 'ccb_opticks_gpu.cc' "$CL" || sed -i '/G4CXOpticks_SetGeometry_GetInputPhoton_Test.cc/a\   ccb_opticks_gpu.cc' "$CL"

cmake -S "$OPTICKS_HOME/g4cx" -B "$BLD" >/tmp/ccb_bridge_cfg.log 2>&1
echo "cmake rc=$?"
cmake --build "$BLD" --target ccb_opticks_gpu ccb_setGeometry -j "$(nproc)" 2>&1 | tail -22
echo "build rc=${PIPESTATUS[0]}"
ls -la "$BIN" 2>&1
