#!/bin/bash
#SBATCH --job-name=ccb-clusterB-timing
#SBATCH --account=hep2023-1-3
#SBATCH --partition=hep
#SBATCH --time=01:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --output=/projects/hep/fs10/shared/nnbar/billy/ccb-wt-clB/reports/studies/clusterB/slurm_%j.out
#SBATCH --error=/projects/hep/fs10/shared/nnbar/billy/ccb-wt-clB/reports/studies/clusterB/slurm_%j.err
# Reproducible Slurm runner for the CCB test-beam timing-chain study (cluster B).
set -euo pipefail
REPO=/projects/hep/fs10/shared/nnbar/billy/ccb-wt-clB
PY=/projects/hep/fs10/shared/nnbar/billy/ccb-py/bin/python
export MPLCONFIGDIR=/projects/hep/fs10/shared/nnbar/billy/.mplcache
cd "$REPO"
echo "[$(date -u)] clusterB timing-chain study on $SLURM_JOB_NODELIST"
"$PY" scripts/clusterB/clusterB_timing_study.py --max-events 400
echo "[$(date -u)] done"
