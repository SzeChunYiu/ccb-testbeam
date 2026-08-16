#!/bin/bash
#SBATCH -A hep2023-1-3
#SBATCH -p hep
#SBATCH -J mc01_1046_2m
#SBATCH -t 04:00:00
#SBATCH --mem=16G
#SBATCH -o /projects/hep/fs10/shared/nnbar/billy/ccb-wt-plots/reports/issue_1046_entering_species/slurm_%j.out

module load Anaconda3
eval "$(conda shell.bash hook)"
conda activate /projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env
cd /projects/hep/fs10/shared/nnbar/billy/ccb-wt-plots
python scripts/mc01_trigger_split_truth.py \
  --mc /projects/hep/fs10/shared/nnbar/billy/ccb-coord-1350/geant4/data/output_krakow_2m_regenerated.root \
  --out reports/issue_1046_entering_species/cmc_2m_regenerated_20260814
echo "EXIT_CODE=$?"
