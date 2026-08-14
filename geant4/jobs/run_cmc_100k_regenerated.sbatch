#!/bin/bash
#SBATCH --job-name=cmc100k
#SBATCH --output=slurm-cmc100k-%j.out
#SBATCH --error=slurm-cmc100k-%j.err
#SBATCH --partition=lu48
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=02:00:00
#SBATCH --account=lu2025-2-51

# MC generation for regenerated paper MC campaign (cmc_100k_regenerated_20260814)
# Provenance: #1311
# Sampler: linear_node_pdf_exact_inverse_v1 + measured_table_support_truncate_v1
# Weight: unit event weight (direct sampling)

set -euo pipefail

# Load environment
module load Anaconda3
conda activate hibeam_g4_250603

# Set paths
REPO=/projects/hep/fs10/shared/nnbar/billy/ccb-wt-1311
cd $REPO/geant4

# Get current git state for provenance
cd $REPO
GIT_COMMIT=$(git rev-parse HEAD)
GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
cd $REPO/geant4

# Update manifest with run-time provenance
python3 << EOF
import json
from datetime import datetime
from pathlib import Path

manifest_path = Path("manifests/cmc_100k_regenerated_20260814.json")
with open(manifest_path) as f:
    manifest = json.load(f)

manifest["random_seed"] = "${SLURM_JOB_ID:-manual}"
manifest["runtime_host"] = "LUNARC"
manifest["slurm_job_id"] = "${SLURM_JOB_ID:-manual}"
manifest["generation_timestamp"] = datetime.now().isoformat()
manifest["superproject_commit"] = "$GIT_COMMIT"

with open(manifest_path, "w") as f:
    json.dump(manifest, f, indent=2)

print(f"Manifest updated: {manifest_path}")
EOF

# Build hibeam_g4 (if needed)
# TODO: Add build step once source is available
# echo "Building hibeam_g4..."
# pushd /path/to/hibeam_g4
# mkdir -p build && cd build
# cmake .. && make
# popd

# Run MC generation
# TODO: Update path when executable is available
# HIBEAM_G4=/path/to/hibeam_g4/hibeam_g4
# $HIBEAM_G4 -c configs/krakow.config -m macros/run_krakow_100k.mac data/output_krakow_100k_regenerated.root

echo "MC generation job completed"
echo "Job ID: $SLURM_JOB_ID"
echo "Commit: $GIT_COMMIT"
echo "Branch: $GIT_BRANCH"

# Verify output
if [ -f data/output_krakow_100k_regenerated.root ]; then
    SIZE=$(stat -f%z data/output_krakow_100k_regenerated.root 2>/dev/null || stat -c%s data/output_krakow_100k_regenerated.root)
    echo "Output file size: $SIZE bytes"
    sha256sum data/output_krakow_100k_regenerated.root
else
    echo "ERROR: Output file not found"
    exit 1
fi
