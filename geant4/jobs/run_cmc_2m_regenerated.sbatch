#!/bin/bash
#SBATCH --job-name=cmc2m_618
#SBATCH --output=slurm-cmc2m-618-%j.out
#SBATCH --error=slurm-cmc2m-618-%j.err
#SBATCH --partition=lu48
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --account=lu2026-2-51

# 2M-event scale-up of the authorising regenerated campaign (cmc_100k_regenerated,
# #1311) for #618 species/penetration statistics. Identical sampler, stack and inputs:
# hibeam_src_scatter/build_632 + packages/hibeam_env ROOT-6.32 single runtime (v2
# convention that fixed the 3498168 double-libCore SIGABRT). No /random/seed: default
# engine seed, sequential stream -> first 100k events replicate cmc_100k_regenerated
# by construction (prefix-consistency property, documented in the manifest).

set -euo pipefail

B=/projects/hep/fs10/shared/nnbar/billy
ENV=$B/packages/hibeam_env
REPO=$B/ccb-coord-1350
MAIN_REPO=$B/ccb-testbeam
HIBEAM_BUILD=$B/hibeam_src_scatter/build_632

export PATH=$ENV/bin:$PATH
export LD_LIBRARY_PATH=$ENV/lib:$ENV/lib64
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
manifest_path = Path("manifests/cmc_2m_regenerated_20260814.json")
manifest = json.loads(manifest_path.read_text())
manifest["random_seed"] = "${SLURM_JOB_ID:-manual}"
manifest["runtime_host"] = "LUNARC"
manifest["slurm_job_id"] = "${SLURM_JOB_ID:-manual}"
manifest["generation_timestamp"] = datetime.now().isoformat()
manifest["superproject_commit"] = "$GIT_COMMIT"
manifest["runtime_stack"] = "packages/hibeam_env ROOT-6.32 single-runtime v2 (same as cmc_100k_regenerated)"
manifest_path.write_text(json.dumps(manifest, indent=2))
print(f"Manifest updated: {manifest_path}")
PYEOF

mkdir -p data
cp ${MAIN_REPO}/geant4/configs/krakow_109_8-38deg_4-71deg.root .
cp ${REPO}/geant4/src_patch/sigma_pd_cm_190.txt .
cp ${MAIN_REPO}/geant4/configs/krakow.config krakow.config
cp ${MAIN_REPO}/geant4/configs/dedx_p_in_CD2.txt .
sed -i 's|Geometry_Namefile krakow_109_8-38deg_4-71deg.root|Geometry_Namefile ./krakow_109_8-38deg_4-71deg.root|' krakow.config

HIBEAM_G4=${HIBEAM_BUILD}/hibeam_g4
echo "Running hibeam_g4 from: ${HIBEAM_G4}"
${HIBEAM_G4} -c krakow.config -m macros/run_krakow_2m.mac data/output_krakow_2m_regenerated.root

echo "MC generation job completed"
echo "Job ID: $SLURM_JOB_ID"
echo "Commit: $GIT_COMMIT"
echo "Branch: $GIT_BRANCH"

if [ -f data/output_krakow_2m_regenerated.root ]; then
    SIZE=$(stat -c%s data/output_krakow_2m_regenerated.root 2>/dev/null || stat -f%z data/output_krakow_2m_regenerated.root)
    echo "Output file size: $SIZE bytes"
    sha256sum data/output_krakow_2m_regenerated.root
else
    echo "ERROR: Output file not found"
    exit 1
fi
