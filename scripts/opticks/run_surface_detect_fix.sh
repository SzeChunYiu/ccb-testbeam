#!/bin/bash -l
#SBATCH --account=lu2026-2-51 --partition=gpua40 --gres=gpu:1 --time=00:30:00 --job-name=ccb-sdetect
#
# fix/opticks-surface-detect: add EFFICIENCY=1.0 skin surfaces to CCB sensors,
# re-ingest, verify num_hit > 0.
set +e
SPIKE=/projects/hep/fs10/shared/nnbar/billy/opticks-spike
LOG=$SPIKE/logs/sdetect_fix.log
WT=/projects/hep/fs10/shared/nnbar/billy/ccb-wt-sdetect
echo "=== SDETECT-FIX START $(date) host=$(hostname) ===" > $LOG
nvidia-smi -L >> $LOG 2>&1

# --- env ---
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

BLD=$SPIKE/opticks-install/build/g4cx

# --- [0] fresh GEOMHOME from the original GDML ---
GEOMHOME=$SPIKE/home_sdetect
rm -rf $GEOMHOME; mkdir -p $GEOMHOME/.opticks/GEOM/CCBStave
cp $SPIKE/home/.opticks/GEOM/CCBStave/origin.gdml $GEOMHOME/.opticks/GEOM/CCBStave/origin.gdml
GDML=$GEOMHOME/.opticks/GEOM/CCBStave/origin.gdml

echo "##### [1] PATCH GDML: add EFFICIENCY=1.0 skin surfaces #####" >> $LOG
python3 $WT/scripts/opticks/patch_gdml_sdetect.py "$GDML" >> $LOG 2>&1
echo "patch rc=$?" >> $LOG
echo "--- verify skinsurface in patched GDML ---" >> $LOG
grep -c "skinsurface" "$GDML" >> $LOG 2>&1
grep -c "EFFICIENCY" "$GDML" >> $LOG 2>&1

# --- [2] INGEST patched GDML via ccb_setGeometry ---
echo "##### [2] INGEST patched GDML (ccb_setGeometry) #####" >> $LOG
export HOME=$GEOMHOME
export GEOM=CCBStave
export CCBStave_GDMLPathFromGEOM=$GDML
unset CCBStave_CFBaseFromGEOM
export stree=INFO G4CXOpticks=INFO U4Tree=INFO U4SensorIdentifier=INFO
"$BLD/tests/ccb_setGeometry" >> $LOG 2>&1
echo "setGeometry rc=$?" >> $LOG

echo "--- post-ingest boundary check ---" >> $LOG
CF=$GEOMHOME/.opticks/GEOM/CCBStave/CSGFoundry
if [ -f "$CF/SSim/stree/desc/bd.txt" ]; then
    echo "=== bd.txt (boundaries) ===" >> $LOG
    cat "$CF/SSim/stree/desc/bd.txt" >> $LOG 2>&1
    echo "=== surface.txt (surface fold) ===" >> $LOG
    head -50 "$CF/SSim/stree/desc/surface.txt" >> $LOG 2>&1
    echo "=== EFFICIENCY surfaces? ===" >> $LOG
    grep -rl "EFFICIENCY" "$CF/SSim/stree/surface/" >> $LOG 2>&1
    # Check num surfaces
    echo "=== num surface files ===" >> $LOG
    find "$CF/SSim/stree/surface" -type d >> $LOG 2>&1
else
    echo "ERROR: CSGFoundry not found at $CF" >> $LOG
fi

# --- [3] TORCH SIMULATE + GATHER via ccb_hit_debug ---
echo "##### [3] ccb_hit_debug (torch + gather + num_hit check) #####" >> $LOG
export OPTICKS_RUNNING_MODE=SRM_TORCH
export SEventConfig__RunningMode=SRM_TORCH
export SEventConfig__EventMode=HitPhoton
export SEventConfig__HitMask="SD,EC"
export QSim=INFO SEvt=INFO SEventConfig=INFO
export OPTICKS_NUM_EVENT=1 OPTICKS_NUM_GENSTEP=1
export OPTICKS_MAX_PHOTON=100000000
export OPTICKS_NUM_PHOTON=1000000 OPTICKS_MAX_SLOT=1000000
export storch_FillGenstep_pos=0,0,0
export storch_FillGenstep_wavelength=500
"$BLD/tests/ccb_hit_debug" >> $LOG 2>&1
echo "hit_debug rc=$?" >> $LOG

echo "##### [4] RESULT SUMMARY #####" >> $LOG
echo "--- CCB_DBG lines ---" >> $LOG
grep "CCB_DBG" $LOG >> $LOG 2>&1
echo "--- gather_components / hit_total ---" >> $LOG
grep -E "gather_components|hit_total|num_hit|num_comp" $LOG | tail -10 >> $LOG 2>&1
echo "=== SDETECT-FIX END $(date) ===" >> $LOG
