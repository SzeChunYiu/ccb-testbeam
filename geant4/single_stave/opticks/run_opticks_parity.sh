#!/bin/bash -l
# End-to-end GPU-vs-CPU optical-photon parity driver (see opticks_parity.py).
# Runs (1) the CPU Geant4 reference, (2) the GPU-optical scintillation capture,
# (3) the ccb_opticks_gpu bridge on a GPU node, (4) the parity plot+SUMMARY.
#
# Usage: run_opticks_parity.sh <N_EVENTS> <SEED> <OUT_BASE>
# Env:   SPIKE (opticks-spike dir), CCB_BUILD (ccb_stave_sim build dir),
#        SLURM account/partition (defaults below).
set +e
N=${1:-2}; SEED=${2:-1}
BASE=${3:-/projects/hep/fs10/shared/nnbar/billy/ccb-wt-opticks/build/parity}
WT=${WT:-/projects/hep/fs10/shared/nnbar/billy/ccb-wt-opticks}
CCB_BUILD=${CCB_BUILD:-$WT/build}
SPIKE=${SPIKE:-/projects/hep/fs10/shared/nnbar/billy/opticks-spike}
ACCOUNT=${ACCOUNT:-lu2026-2-51}; PART=${PART:-gpua40}
mkdir -p $BASE/cpu_arrivals $BASE/optical_gpu $BASE/gpu_hits

echo "[1/4] CPU reference (seed=$SEED, $N events) -> cpu_arrivals/"
$CCB_BUILD/ccb_stave_sim --particle proton --energy 100 --nevents $N --seed $SEED \
  --optical-dir $CCB_BUILD/optical --output $BASE/cpu_ref.root \
  --optical-out $BASE/cpu_arrivals

echo "[2/4] GPU-optical scintillation capture (same seed) -> optical_gpu/"
$CCB_BUILD/ccb_stave_sim --particle proton --energy 100 --nevents $N --seed $SEED \
  --optical-dir $CCB_BUILD/optical --output $BASE/gpu_capture.root \
  --optical-out $BASE/optical_gpu
# CCB_GPU_OPTICAL=1 also works as the flag:
CCB_GPU_OPTICAL=1 $CCB_BUILD/ccb_stave_sim --particle proton --energy 100 --nevents $N --seed $SEED \
  --optical-dir $CCB_BUILD/optical --output $BASE/gpu_capture.root \
  --optical-out $BASE/optical_gpu

echo "[3/4] GPU bridge (sbatch -> $PART) -> gpu_hits/  (opticks env + geometry ingest)"
cat > $BASE/_bridge.sbatch <<SB
#!/bin/bash -l
#SBATCH --account=$ACCOUNT --partition=$PART --gres=gpu:1 --time=00:20:00 --job-name=ccb-parity
source $SPIKE/env.sh
export HOME=$BASE/opticks_home
export GEOM=CCBStave
mkdir -p \$HOME/.opticks/GEOM/CCBStave
CCB_GPU_GEOM=1 $CCB_BUILD/ccb_stave_sim --dump-gdml \$HOME/.opticks/GEOM/CCBStave/origin.gdml \
  --optical-dir $CCB_BUILD/optical --output $BASE/_gdml.root --nevents 1
export CCBStave_GDMLPathFromGEOM=\$HOME/.opticks/GEOM/CCBStave/origin.gdml
unset CCBStave_CFBaseFromGEOM
export G4CXOpticks__setGeometry_saveGeometry=\$HOME/.opticks/GEOM/CCBStave
# Sensor-annotated ingest (CCBSensorIdentifier -> sensor_count=4) BEFORE the bridge runs.
$SPIKE/opticks-install/build/g4cx/tests/ccb_setGeometry
export OPTICKS_RUNNING_MODE=SRM_INPUT_PHOTON OPTICKS_NUM_EVENT=1
export OPTICKS_EVENT_MODE=HitPhoton
export OPTICKS_MAX_PHOTON=100000000 OPTICKS_MAX_SLOT=2000000
$SPIKE/opticks-install/build/g4cx/tests/ccb_opticks_gpu $BASE/optical_gpu $BASE/gpu_hits
SB
sbatch --wait $BASE/_bridge.sbatch

echo "[4/4] parity plot + SUMMARY"
module load Anaconda3 2>/dev/null
source activate /projects/hep/fs10/shared/nnbar/billy/packages/GNN_GPU 2>/dev/null
python3 $WT/geant4/single_stave/opticks/opticks_parity.py \
  --cpu $BASE/cpu_arrivals --gpu-input $BASE/optical_gpu \
  --gpu-hits $BASE/gpu_hits --out $WT/figures/opticks
