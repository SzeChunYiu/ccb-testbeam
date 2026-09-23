#!/bin/bash
# Test script for Phase 2 trigger volume addition
# Runs a 50k event simulation to verify T1/T2 trigger volumes work

set -e

LUNARC_BASE="/projects/hep/fs10/shared/nnbar/billy/HIBEAM/Detector_simulation"
WORKTREE="$HOME/ccb-wt-1045"

echo "=== Phase 2 Test Simulation ==="
echo "Date: $(date)"
echo ""

# Step 1: Patch GDML
echo "Step 1: Patching GDML file..."
cd "$LUNARC_BASE/hibeam_g4_build/geometry"
if [ ! -f hibeam_wasa_geom.gdml.backup ]; then
    cp hibeam_wasa_geom.gdml hibeam_wasa_geom.gdml.backup
    echo "  Backed up original GDML"
fi
python3 "$WORKTREE/scripts/trigger_phase2/patch_gdml_trigger_volumes.py" hibeam_wasa_geom.gdml
echo "  GDML patched successfully"
echo ""

# Step 2: Copy sensitive detector files
echo "Step 2: Copying trigger sensitive detector files..."
cp "$WORKTREE/scripts/trigger_phase2/TriggerSensitiveDetector.hh" \
   "$LUNARC_BASE/hibeam_g4-main/include/"
cp "$WORKTREE/scripts/trigger_phase2/TriggerSensitiveDetector.cc" \
   "$LUNARC_BASE/hibeam_g4-main/src/"
echo "  Files copied"
echo ""

# Step 3: Recompile
echo "Step 3: Recompiling HIBEAM simulation..."
cd "$LUNARC_BASE/hibeam_g4_build/build"
cmake .. > /dev/null
make -j4 > /tmp/hibeam_recompile_$(date +%Y%m%d_%H%M%S).log 2>&1
echo "  Compilation complete"
echo ""

# Step 4: Run test simulation (50k events)
echo "Step 4: Running 50k event test simulation..."
TEST_CONFIG="$LUNARC_BASE/hibeam_g4_build/configs/test_trigger_phase2.config"
cat > "$TEST_CONFIG" << EOFCONFIG
# Test config for Phase 2 trigger volume addition
Geometry_Namefile: hibeam_wasa_geom.gdml
CheckOverlaps: 1
N_events: 50000
RandomSeed: 1045
Output_Namefile: test_trigger_phase2_50k.root
EOFCONFIG

# Submit to LUNARC
cd "$LUNARC_BASE/hibeam_g4_build"
sbatch -p hep -t 01:00:00 -J trigger_phase2_test -o slurm_trigger_phase2_test_%j.out \
    --wrap="$PWD/hibeam_g4 $TEST_CONFIG"

echo "  Job submitted to LUNARC"
echo ""

echo "=== Test simulation submitted ==="
echo "Monitor with: squeue -u \$USER"
echo "Results will be in: $LUNARC_BASE/geant4/data/test_trigger_phase2_50k.root"
