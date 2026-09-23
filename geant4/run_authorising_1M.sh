#!/bin/bash

#SBATCH --job-name=cmc1m_1045b
#SBATCH --partition=lu48
#SBATCH --time=08:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=%j.out
#SBATCH --error=%j.err

# Authorising MC run for Phase 1B issue #1045
# Source: hibeam_g4 commit b73ea2a1bd2419e7c4a25a3bf23a419ad619234c + scatter patch
# Build: hibeam_g4_build_1045b with ROOT 6.32, VGM 5.4

echo "Job started at $(date)"

# Create job directory
WORKDIR=/local/slurmtmp.${SLURM_JOB_ID}
echo "Creating workdir: ${WORKDIR}"
mkdir -p ${WORKDIR}
cd ${WORKDIR} || exit 1

# Activate environment properly - this sets G4 data paths
echo "Activating conda environment..."
set +u
module load Anaconda3 || true
export CONDA_PREFIX=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env
conda activate ${CONDA_PREFIX} || exit 2
# Source the geant4 data activation scripts
for script in ${CONDA_PREFIX}/etc/conda/activate.d/activate-geant4-data-*.sh; do
    if [ -f "${script}" ]; then
        CONDA_PREFIX=${CONDA_PREFIX} CONDA_PROMPT_MODIFIER= bash ${script}
    fi
done
set -u

echo "G4NEUTRONHPDATA: ${G4NEUTRONHPDATA:-not set}"
echo "G4ENSDFSTATEDATA: ${G4ENSDFSTATEDATA:-not set}"

# Copy input files to job cwd
echo "Copying input files..."
cp /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/configs/dedx_p_in_CD2.txt . || exit 3
cp /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/configs/sigma_pd_cm_190.txt . || exit 3
cp /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/configs/krakow.config . || exit 3
cp /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/ccb-wt-1045b/geant4/macros/run_krakow_1M.mac run.mac || exit 3
cp /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/configs/krakow_109_8-38deg_4-71deg.root . || exit 3

# Run
echo "Starting MC run..."
export HIBEAM_EXE=/projects/hep/fs10/shared/nnbar/billy/HIBEAM/Detector_simulation/hibeam_g4_build_1045b/hibeam_g4
${HIBEAM_EXE} -c krakow.config -m run.mac output_krakow_1M_authorising.root || exit 4

# Copy output to persistent storage
echo "Copying output..."
OUTPUT_DIR=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data
mkdir -p ${OUTPUT_DIR}
cp output_krakow_1M_authorising.root ${OUTPUT_DIR}/
echo "Output written to ${OUTPUT_DIR}/output_krakow_1M_authorising.root"

# Cleanup
echo "Cleaning up..."
cd /projects/hep/fs10/shared/nnbar/billy
rm -rf ${WORKDIR}

echo "Job completed at $(date)"
exit 0
