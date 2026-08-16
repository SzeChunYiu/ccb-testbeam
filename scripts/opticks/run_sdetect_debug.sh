#!/bin/bash -l
#SBATCH --account=lu2026-2-51 --partition=gpua40 --gres=gpu:1 --time=00:20:00 --job-name=ccb-sd-dbg
set +e
SPIKE=/projects/hep/fs10/shared/nnbar/billy/opticks-spike
LOG=$SPIKE/logs/sdetect_debug.log

module purge >/dev/null 2>&1
module load GCC/12.3.0 Geant4/11.2.2 >/dev/null 2>&1
export CUDA_HOME=/sw/easybuild_milan/software/CUDA/12.6.0
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}
export OPTICKS_HOME=$SPIKE/src/opticks
export OPTICKS_PREFIX=$SPIKE/opticks-install
export OPTICKS_CUDA_PREFIX=$CUDA_HOME
export OPTICKS_OPTIX_PREFIX=$SPIKE/optix-install
unset CMAKE_PREFIX_PATH PKG_CONFIG_PATH
opticks-(){  [ -r $OPTICKS_HOME/opticks.bash ] && . $OPTICKS_HOME/opticks.bash && opticks-env "$@" ; }
opticks- >/dev/null 2>&1
opticks-prepend-prefix /sw/easybuild_milan/software/CLHEP/2.4.7.1-GCC-12.3.0 >/dev/null 2>&1
opticks-prepend-prefix /sw/easybuild_milan/software/Xerces-C++/3.2.4-GCCcore-12.3.0 >/dev/null 2>&1
opticks-prepend-prefix /sw/easybuild_milan/software/Geant4/11.2.2-GCC-12.3.0 >/dev/null 2>&1
opticks-prepend-prefix /sw/easybuild_milan/software/X11/20230603-GCCcore-12.3.0 >/dev/null 2>&1
opticks-prepend-prefix /sw/easybuild_milan/software/Mesa/23.1.4-GCCcore-14.3.0 >/dev/null 2>&1
opticks-prepend-prefix /sw/easybuild_milan/software/OpenGL/2025.09-GCCcore-14.3.0 >/dev/null 2>&1

GEOMHOME=$SPIKE/home_sdetect
export HOME=$GEOMHOME
export GEOM=CCBStave
export CCBStave_GDMLPathFromGEOM=$GEOMHOME/.opticks/GEOM/CCBStave/origin.gdml
export CCBStave_CFBaseFromGEOM=$GEOMHOME/.opticks/GEOM/CCBStave

BLD=$SPIKE/opticks-install/build/g4cx

# Photon at sensor center, PIDX=0 for kernel debug printf
export PIDX=0
export storch_FillGenstep_pos=260.06,-10,0
export storch_FillGenstep_wavelength=500
export storch_FillGenstep_n=10000
export QSim=INFO SEvt=INFO SEventConfig=INFO
export OPTICKS_RUNNING_MODE=SRM_TORCH
export OPTICKS_NUM_EVENT=1 OPTICKS_NUM_GENSTEP=1
export OPTICKS_MAX_PHOTON=100000000
export OPTICKS_NUM_PHOTON=10000 OPTICKS_MAX_SLOT=10000

echo "=== SDETECT-DEBUG START $(date) host=$(hostname) ===" > $LOG
nvidia-smi -L >> $LOG 2>&1

"$BLD/tests/ccb_hit_debug" >> $LOG 2>&1
echo "rc=$?" >> $LOG

echo "" >> $LOG
echo "=== KERNEL DEBUG (qsim.propagate) ===" >> $LOG
grep "//qsim\.\|//qbnd\." $LOG | head -50 >> $LOG
echo "" >> $LOG
echo "=== HIT SUMMARY ===" >> $LOG
grep -E "num_hit|hit_total|gather_components|CCB_DBG|SURFACE_DETECT|EFFICIENCY" $LOG | tail -20 >> $LOG
echo "=== SDETECT-DEBUG END $(date) ===" >> $LOG
