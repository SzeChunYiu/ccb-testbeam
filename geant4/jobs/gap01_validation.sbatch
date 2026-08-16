#!/bin/bash
#SBATCH --job-name=gap01-mc
#SBATCH --account=hep2023-1-3
#SBATCH --partition=hep
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=/projects/hep/fs10/shared/nnbar/billy/ccb-wt-gap01/geant4/results/gap01_mc_%j.out
#SBATCH --error=/projects/hep/fs10/shared/nnbar/billy/ccb-wt-gap01/geant4/results/gap01_mc_%j.err

set -e
CE=/projects/hep/fs10/shared/nnbar/billy/hibeam_env
HG4BLD=/projects/hep/fs10/shared/nnbar/billy/hibeam_build_gap01
VGMINST=/projects/hep/fs10/shared/nnbar/billy/vgm_install_gap01
WT=/projects/hep/fs10/shared/nnbar/billy/ccb-wt-gap01

export PATH="$CE/bin:$PATH"
export LD_LIBRARY_PATH="$CE/lib:$VGMINST/lib64:$LD_LIBRARY_PATH"
export G4DATA=$CE/share/Geant4/data
export QT_QPA_PLATFORM=offscreen

cd $WT/geant4/configs
echo "=== GAP-01 validation MC: $(date) ==="
echo "Geometry: krakow_gap01.root (inter-stave dead material + 4 g/cm2 Al absorber)"
echo "Events: 100000, Source: scattering (190 MeV p + CD2)"
echo "Threads: 1 (required: ScatteringGenerator loads tables on event 0)"

$HG4BLD/hibeam_g4 -c krakow_gap01.config -m run_gap01_100k.mac \
  $WT/geant4/results/output_krakow_gap01_100k.root

echo "=== MC complete: $(date) ==="
ls -la $WT/geant4/results/output_krakow_gap01_100k.root
