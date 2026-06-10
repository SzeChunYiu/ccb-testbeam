#!/bin/bash
# Build + run the HIBEAM hibeam_g4 GEANT4 sim for the CCB (Krakow) test beam.  VERIFIED WORKING
# on billy 2026-06-10.  THE KEY: use the conda env `nnbar_env` (its compiler + ROOT 6.32) — the
# system gcc-13 / ROOT 6.24 do NOT compile or run it (struct/class + libCling mismatch).
set -e
G4=/home/billy/nnbar/simulation/GEANT4_Packages/install/geant4-11.2.2
VGM=/home/billy/nnbar/simulation/GEANT4_Packages/install/vgm
unset LD_LIBRARY_PATH
source /home/billy/anaconda3/etc/profile.d/conda.sh && conda activate nnbar_env
source "$G4/bin/geant4.sh"
export VGM_INSTALL="$VGM" VGM_DIR="$VGM/lib/VGM-5.4.0"
export LD_LIBRARY_PATH="$VGM_DIR:$VGM/lib:$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"
SRC=/home/billy/ccb-geant4/hibeam_g4_github
[ -d "$SRC" ] || git clone https://github.com/HIBEAM-NNBAR/hibeam_g4.git "$SRC"
cd "$SRC"; mkdir -p build_conda && cd build_conda
cmake -DVGM_DIR="$VGM_DIR" .. && make -j4
cp /home/billy/ccb-geant4/{krakow.config,krakow.geoconf,run_krakow.mac,sigma_pd_cm_190.txt,dedx_p_in_CD2.txt,krakow_109_8-38deg_4-71deg.root} .
./hibeam_g4 -c krakow.config -m run_krakow.mac output_krakow.root
