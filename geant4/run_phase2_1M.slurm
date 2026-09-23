#!/bin/bash
#SBATCH --job-name=p2m1m_1045
#SBATCH --partition=lu48
#SBATCH --time=12:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --output=%j.out
#SBATCH --error=%j.err

# Phase 5 (#1045): 1M-event MC with Phase 2 T1/T2 trigger SD geometry.
# Binary: hibeam_g4_build_1045b (phase2-SD build, mtime 2026-08-17 00:15,
#         the exact binary that produced output_krakow_phase2_10k.root)
# Physics: identical to authorising 1M (190 MeV e- on 2.3mm CD2, Krakow sigma
#          table, 10mm beamspot); only the T1/T2 SD differs.
# Purpose: statistical backbone for the Phase 3/4 migration decision.
#          At 10k events: proxy fires 4/10000, hardware coincidence 0/10000,
#          T1/T2 hit populations disjoint -> migration M unresolvable.

set -euo pipefail
echo "Job started at $(date)"
WORKDIR=/local/slurmtmp.${SLURM_JOB_ID}
mkdir -p ${WORKDIR}
cd ${WORKDIR}

set +u
module load Anaconda3 || true
export CONDA_PREFIX=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env
conda activate ${CONDA_PREFIX}
for script in ${CONDA_PREFIX}/etc/conda/activate.d/activate-geant4-data-*.sh; do
    [ -f "${script}" ] && CONDA_PREFIX=${CONDA_PREFIX} CONDA_PROMPT_MODIFIER= bash ${script}
done
set -u
echo "G4NEUTRONHPDATA: ${G4NEUTRONHPDATA:-not set}"

P2WT=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/ccb-wt-1045-phase2
CFG=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/configs
BIN=/projects/hep/fs10/shared/nnbar/billy/HIBEAM/Detector_simulation/hibeam_g4_build_1045b/hibeam_g4
OUTDIR=/projects/hep/fs10/shared/nnbar/billy/ccb_1045_phase2_1M

cp ${CFG}/dedx_p_in_CD2.txt ${CFG}/sigma_pd_cm_190.txt ${CFG}/krakow.config .
cp ${P2WT}/geant4/macros/run_krakow_1M.mac run.mac
cp ${CFG}/krakow_109_8-38deg_4-71deg.root .

mkdir -p ${OUTDIR}
{
  echo "generated_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "binary_sha256: $(sha256sum ${BIN} | cut -d' ' -f1)"
  echo "macro_sha256: $(sha256sum run.mac | cut -d' ' -f1)"
  echo "krakow_config_sha256: $(sha256sum krakow.config | cut -d' ' -f1)"
  echo "sigma_table_sha256: $(sha256sum sigma_pd_cm_190.txt | cut -d' ' -f1)"
  echo "dedx_table_sha256: $(sha256sum dedx_p_in_CD2.txt | cut -d' ' -f1)"
  echo "geometry_root_sha256: $(sha256sum krakow_109_8-38deg_4-71deg.root | cut -d' ' -f1)"
  echo "events: 1000000"
  echo "validation_sample: output_krakow_phase2_10k.root (same binary, same physics)"
} > ${OUTDIR}/provenance_1m_phase2.txt

echo "Starting MC run (1M events, phase2 T1/T2 SD)..."
${BIN} -c krakow.config -m run.mac output_krakow_1M_phase2.root

cp output_krakow_1M_phase2.root ${OUTDIR}/
echo "Output written to ${OUTDIR}/output_krakow_1M_phase2.root"
sha256sum ${OUTDIR}/output_krakow_1M_phase2.root >> ${OUTDIR}/provenance_1m_phase2.txt
echo "Job completed at $(date)"
cd /projects/hep/fs10/shared/nnbar/billy
rm -rf ${WORKDIR}
