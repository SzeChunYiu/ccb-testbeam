#!/bin/bash
#SBATCH --job-name=cmc100k_v2
#SBATCH --output=slurm-cmc100k-v2-%j.out
#SBATCH --error=slurm-cmc100k-v2-%j.err
#SBATCH --partition=lu48
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=06:00:00
#SBATCH --account=lu2026-2-51

# v2 (coordinator, 2026-08-14): fixes the ROOT-runtime mixing that SIGABRT'd job 3498168.
# The binary now resolves Geant4+ROOT+VGM from ONE stack (packages/hibeam_env, ROOT 6.32):
# v1 activated conda hibeam_g4_250603 (Geant4 built vs ROOT 6.34 in billy/hibeam_env) and
# VGM (vgm_install_gap01) was linked against that 6.34 ROOT while hibeam_g4 links 6.32
# directly -> two libCore runtimes in one process -> free(): invalid pointer.
# v2: no conda activation; packages/hibeam_env on PATH/LD_LIBRARY_PATH; VGM+binary
# rebuilt against that same env (vgm_install_632 / build_632).

set -euo pipefail

B=/projects/hep/fs10/shared/nnbar/billy
ENV=$B/packages/hibeam_env
REPO=$B/ccb-wt-1311
MAIN_REPO=$B/ccb-testbeam
HIBEAM_BUILD=$B/hibeam_src_scatter/build_632

export PATH=$ENV/bin:$PATH
export LD_LIBRARY_PATH=$ENV/lib:$ENV/lib64
# Geant4 datasets (conda env provides them via activate hooks; 3498629 crashed without)
export CONDA_PREFIX=$ENV
set +u
for f in $ENV/etc/conda/activate.d/activate-geant4-data-*.sh; do source "$f"; done
set -u
unset CONDA_PREFIX

cd $REPO
GIT_COMMIT=$(git rev-parse HEAD)
GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
cd $REPO/geant4

python3 << PYEOF
import json
from datetime import datetime
from pathlib import Path
manifest_path = Path("manifests/cmc_100k_regenerated_20260814.json")
manifest = json.loads(manifest_path.read_text())
manifest["random_seed"] = "${SLURM_JOB_ID:-manual}"
manifest["runtime_host"] = "LUNARC"
manifest["slurm_job_id"] = "${SLURM_JOB_ID:-manual}"
manifest["generation_timestamp"] = datetime.now().isoformat()
manifest["superproject_commit"] = "$GIT_COMMIT"
manifest["runtime_stack"] = "packages/hibeam_env ROOT-6.32 single-runtime v2 (fixes 3498168 double-libCore)"
manifest_path.write_text(json.dumps(manifest, indent=2))
print(f"Manifest updated: {manifest_path}")
PYEOF

mkdir -p data
cp ${MAIN_REPO}/geant4/configs/krakow_109_8-38deg_4-71deg.root .
cp ${REPO}/geant4/src_patch/sigma_pd_cm_190.txt .
cp ${MAIN_REPO}/geant4/configs/krakow.config krakow.config
# ScatteringGenerator::LoadELossTable opens this from cwd (exit(0) if missing)
cp ${MAIN_REPO}/geant4/configs/dedx_p_in_CD2.txt .
sed -i 's|Geometry_Namefile krakow_109_8-38deg_4-71deg.root|Geometry_Namefile ./krakow_109_8-38deg_4-71deg.root|' krakow.config
sed -i 's|/ElGen/CSFile sigma_pd_cm_190.txt|/ElGen/CSFile ./sigma_pd_cm_190.txt|' macros/run_krakow_100k.mac

HIBEAM_G4=${HIBEAM_BUILD}/hibeam_g4
echo "Running hibeam_g4 from: ${HIBEAM_G4}"
${HIBEAM_G4} -c krakow.config -m macros/run_krakow_100k.mac data/output_krakow_100k_regenerated.root

echo "MC generation job completed"
echo "Job ID: $SLURM_JOB_ID"
echo "Commit: $GIT_COMMIT"
echo "Branch: $GIT_BRANCH"

if [ -f data/output_krakow_100k_regenerated.root ]; then
    SIZE=$(stat -c%s data/output_krakow_100k_regenerated.root 2>/dev/null || stat -f%z data/output_krakow_100k_regenerated.root)
    echo "Output file size: $SIZE bytes"
    sha256sum data/output_krakow_100k_regenerated.root
else
    echo "ERROR: Output file not found"
    exit 1
fi
