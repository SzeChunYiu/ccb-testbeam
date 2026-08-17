#!/bin/bash
#SBATCH --job-name=p2m1m_1045v2
#SBATCH --partition=lu48
#SBATCH -A lu2026-2-51
#SBATCH --time=12:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --output=/projects/hep/fs10/shared/nnbar/billy/ccb_1045_phase2_1M/1m_v2_%j.out
#SBATCH --error=/projects/hep/fs10/shared/nnbar/billy/ccb_1045_phase2_1M/1m_v2_%j.err

# Phase 5 v2 (#1045): 1M events WITH T1/T2 trigger SD. v1 (job 3506983) ran
# the BASE config (no T1_trigger_log/T2_trigger_log detectors, plain geometry)
# -> output had 62 branches, no T1/T2. v2 uses krakow_phase2.config + the
# T1T2 geometry, exactly as the 10k validation run did.
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
BIN=/projects/hep/fs10/shared/nnbar/billy/HIBEAM/Detector_simulation/hibeam_g4_build_1045b/hibeam_g4
OUTDIR=/projects/hep/fs10/shared/nnbar/billy/ccb_1045_phase2_1M

cp ${P2WT}/geant4/configs/dedx_p_in_CD2.txt ${P2WT}/geant4/configs/sigma_pd_cm_190.txt .
cp ${P2WT}/geant4/configs/krakow_phase2.config .
cp ${P2WT}/geant4/configs/krakow_109_8-38deg_4-71deg_T1T2.root .
cp ${P2WT}/geant4/macros/run_krakow_1M.mac run.mac

mkdir -p ${OUTDIR}
{
  echo "generated_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "binary_sha256: $(sha256sum ${BIN} | cut -d' ' -f1)"
  echo "macro_sha256: $(sha256sum run.mac | cut -d' ' -f1)"
  echo "krakow_phase2_config_sha256: $(sha256sum krakow_phase2.config | cut -d' ' -f1)"
  echo "geometry_t1t2_root_sha256: $(sha256sum krakow_109_8-38deg_4-71deg_T1T2.root | cut -d' ' -f1)"
  echo "sigma_table_sha256: $(sha256sum sigma_pd_cm_190.txt | cut -d' ' -f1)"
  echo "dedx_table_sha256: $(sha256sum dedx_p_in_CD2.txt | cut -d' ' -f1)"
  echo "events: 1000000"
  echo "config: krakow_phase2.config (Detectors ...,T1_trigger_log,T2_trigger_log; T1T2 geometry)"
  echo "validation_sample: output_krakow_phase2_10k.root (same binary, same config family)"
  echo "supersedes: job 3506983 output (wrong geometry, no T1/T2 branches, quarantined as .wronggeom)"
} > ${OUTDIR}/provenance_1m_phase2_v2.txt

echo "Starting MC run (1M events, phase2 T1/T2 SD)..."
${BIN} -c krakow_phase2.config -m run.mac output_krakow_1M_phase2.root

cp output_krakow_1M_phase2.root ${OUTDIR}/
echo "Output written to ${OUTDIR}/output_krakow_1M_phase2.root"
sha256sum ${OUTDIR}/output_krakow_1M_phase2.root >> ${OUTDIR}/provenance_1m_phase2_v2.txt
echo "Job completed at $(date)"
cd /projects/hep/fs10/shared/nnbar/billy
rm -rf ${WORKDIR} || true
