#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_mv3v5_trigprod
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 00:40:00
#SBATCH -o %x_%j.out
#SBATCH -e %x_%j.err
#
# B-M1 / STUDY_GAPS NEW-01 : REAL simulated two-arm trigger.
# Re-run the Krakow (CCB) hibeam_g4 production with the Trig_bar trigger-paddle
# volumes ADDED to the scored `Detectors` list, so the truth tree carries genuine
# GEANT4 sensitive-detector energy deposits in the A/B trigger paddles
# (branches Trig_bar_EDep / _Time / _LayerID1(arm) / _LayerID(paddle) / _PDG / ...).
# This replaces the truth-level A-HRD coincidence PROXY used in mv3 v4.
#
# Everything else (geometry file, scattering pd-elastic generator, beam energy,
# target thickness, physics list) is identical to the original 1M production,
# so the Sci_bar stopping profile must reproduce the 1M sample within Poisson
# statistics (validated in the v5 analysis) — the ONLY change is +Trig_bar scoring.
# NB: no `-u` — the conda activation scripts reference unbound vars (ADDR2LINE ...).
set -eo pipefail

REPO=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam
BIN=/projects/hep/fs10/shared/nnbar/billy/HIBEAM_Detector/hibeam_g4_build/hibeam_g4
VGM=/projects/hep/fs10/shared/nnbar/billy/packages/vgm_install/lib64
ENVDIR=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env
NEVENTS="${CCB_NEVENTS:-1000000}"

module load Anaconda3
source "${ENVDIR}/etc/profile.d/conda.sh" 2>/dev/null || true
conda activate "${ENVDIR}"
export LD_LIBRARY_PATH="${VGM}:${LD_LIBRARY_PATH:-}"
# The Feb-2026 LUNARC build's tasking-mode ntuple merge drops the master file
# ("delete empty file"); force Geant4's serial run manager -> single filled tree.
export G4RUN_MANAGER_TYPE=Serial

WORK="${REPO}/geant4/trig_prod"
mkdir -p "${WORK}"
cd "${WORK}"

# --- geometry (contains the Trig_bar logical volume) ---
cp -f "${REPO}/geant4/data/krakow_109_8-38deg_4-71deg.root" geom.root

# --- proton dE/dx in CD2 (only used for the sub-MeV beam-energy-loss correction
#     across the 1.15 mm target; PSTAR-style, rho(CD2)=1.06 g/cm3) ---
python3 "${REPO}/geant4/gen_dedx_cd2.py" > dedx_p_in_CD2.txt

# --- config: the 1M detector list PLUS Trig_bar ---
cat > krakow_trig.config <<CFG
Geo Wasa
Geometry_Namefile geom.root
Detectors TARGET,ProtoTPC,Sci_bar,Trig_bar
Source scattering
WriteHistograms 0
WriteTree 1
Threads 1
CFG

# --- macro: identical beam to run_krakow.mac ---
cat > run_trig.mac <<MAC
/run/initialize
/ElGen/E 190. MeV
/ElGen/TargetThickness 2.3 mm
/ElGen/Beamspot 10 mm
/run/beamOn ${NEVENTS}
MAC

OUT="${REPO}/geant4/data/output_krakow_1M_trig.root"
echo "[prologue] host=$(hostname) start=$(date -Is) nevents=${NEVENTS}"
echo "[prologue] binary=${BIN}"
"${BIN}" -c krakow_trig.config -m run_trig.mac "${OUT}"

echo "[epilogue] done=$(date -Is)"
ls -la "${OUT}"
md5sum "${OUT}" | tee "${OUT}.md5"
python3 - "${OUT}" <<'PY'
import sys, uproot
t = uproot.open(sys.argv[1])["hibeam"]
brs = [b for b in t.keys() if b.startswith("Trig_bar")]
print("[verify] entries:", t.num_entries, "| Trig_bar branches:", len(brs))
assert t.num_entries > 0 and brs, "empty tree or no Trig_bar branches"
print("[verify] OK")
PY
