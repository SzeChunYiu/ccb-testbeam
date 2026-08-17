#!/bin/bash
#SBATCH --job-name=p2v3_10k
#SBATCH --partition=lu48
#SBATCH -A lu2026-2-51
#SBATCH --time=04:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --output=/projects/hep/fs10/shared/nnbar/billy/ccb_1045_v3/v3_10k_%j.out
#SBATCH --error=/projects/hep/fs10/shared/nnbar/billy/ccb_1045_v3/v3_10k_%j.err

# Phase 2 geometry v3 (#1045): instrumented BASELINE Trig stacks.
# T1 := Trig_stack_1 (B arm, -38 deg, node (-60.950,0,78.013), 2x PSci 20x8x1)
# T2 := Trig_stack_2 (A arm, +71.5 deg, node (93.884,0,31.413), 2x PSci 20x8x1)
# Geometry built by make_t1t2_v3.py from the baseline (sha a71c5cd7...)
# -> krakow_109_T1T2v3.root sha 657661c8bbae28e35bc9398e6752ed97f371e0939921770699df7d3dfb9c5eba
# v2 (r=30 antipodal paddles) RETRACTED: 0/554 two-arm triggers in 1M.
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
OUTDIR=/projects/hep/fs10/shared/nnbar/billy/ccb_1045_v3

cp ${P2WT}/geant4/configs/dedx_p_in_CD2.txt ${P2WT}/geant4/configs/sigma_pd_cm_190.txt .
cp ${OUTDIR}/krakow_109_T1T2v3.root .
cp ${OUTDIR}/krakow_phase2_v3.config .
cp ${OUTDIR}/run_krakow_10k.mac run.mac

mkdir -p ${OUTDIR}
{
  echo "generated_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "binary_sha256: $(sha256sum ${BIN} | cut -d' ' -f1)"
  echo "macro_sha256: $(sha256sum run.mac | cut -d' ' -f1)"
  echo "config_sha256: $(sha256sum krakow_phase2_v3.config | cut -d' ' -f1)"
  echo "geometry_v3_root_sha256: $(sha256sum krakow_109_T1T2v3.root | cut -d' ' -f1)"
  echo "sigma_table_sha256: $(sha256sum sigma_pd_cm_190.txt | cut -d' ' -f1)"
  echo "dedx_table_sha256: $(sha256sum dedx_p_in_CD2.txt | cut -d' ' -f1)"
  echo "events: 10000"
  echo "geometry: v3 instrumented baseline Trig stacks (T1=stack_1 B-arm -38deg, T2=stack_2 A-arm +71.5deg, r=99)"
  echo "supersedes: v2 1M (job 3506988) - RETRACTED, antipodal placement, 0/554"
} > ${OUTDIR}/provenance_v3_10k.txt

echo "Starting MC run (10k events, v3 instrumented Trig stacks)..."
${BIN} -c krakow_phase2_v3.config -m run.mac output_krakow_v3_10k.root

cp output_krakow_v3_10k.root ${OUTDIR}/
echo "Output written to ${OUTDIR}/output_krakow_v3_10k.root"
sha256sum ${OUTDIR}/output_krakow_v3_10k.root >> ${OUTDIR}/provenance_v3_10k.txt
echo "Job completed at $(date)"
cd /projects/hep/fs10/shared/nnbar/billy
rm -rf ${WORKDIR} || true
