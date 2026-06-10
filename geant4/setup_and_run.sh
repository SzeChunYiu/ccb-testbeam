#!/bin/bash
# Build + run the colleague's hibeam_g4 GEANT4 sim for the CCB (Krakow) test beam.
# Works on a stack MATCHING the one hibeam_g4 was written against (Geant4 >=11, ROOT 6.x, VGM 5.x,
# and an Arrow/Parquet version compatible with the source -- NOT Arrow 19). See REPRODUCTION_STATUS.md.
set -e
G4=/home/billy/nnbar/simulation/GEANT4_Packages/install/geant4-11.2.2
VGM=/home/billy/nnbar/simulation/GEANT4_Packages/install/vgm
SRC=/home/billy/HIBEAM/Detector_simulation/hibeam_g4-main
source "$G4/bin/geant4.sh"; source /home/billy/root/bin/thisroot.sh
export VGM_INSTALL="$VGM" VGM_DIR="$VGM/lib/VGM-5.4.0"
export LD_LIBRARY_PATH="$VGM_DIR:$VGM/lib:$LD_LIBRARY_PATH"
mkdir -p build && cd build
cmake -DVGM_DIR="$VGM_DIR" "$SRC"
make -j4
# run (1M events at 190 MeV p on CD2, p-d elastic generator -> truth tree)
./hibeam_g4 -c ../configs/krakow.config -m ../macros/run_krakow.mac output_krakow.root
