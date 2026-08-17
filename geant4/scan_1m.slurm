#!/bin/bash
#SBATCH --job-name=p3scan1m
#SBATCH --partition=lu48
#SBATCH -A lu2026-2-51
#SBATCH --time=04:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --output=/projects/hep/fs10/shared/nnbar/billy/ccb_1045_phase2_1M/scan_1m_%j.out
#SBATCH --error=/projects/hep/fs10/shared/nnbar/billy/ccb_1045_phase2_1M/scan_1m_%j.err

# Phase 3/4 on the 1M phase2 file (issue #1045, job 3506983 output).
set -euo pipefail
PY=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python
WT=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/ccb-wt-1045-p3
IN=/projects/hep/fs10/shared/nnbar/billy/ccb_1045_phase2_1M/output_krakow_1M_phase2.root
cd ${WT}
echo "=== hardware scan (1M) $(date) ==="
${PY} scripts/trigger_threshold_scan.py --input ${IN} \
  --output research/trigger_migration_study/phase3/hardware_scan_1m.json \
  --repo-root . --mode hardware
echo "=== proxy scan (1M) $(date) ==="
${PY} scripts/trigger_threshold_scan.py --input ${IN} \
  --output research/trigger_migration_study/phase3/baseline_proxy_scan_1m.json \
  --repo-root . --mode proxy
echo "=== phase 4 matrix (1M) $(date) ==="
${PY} scripts/trigger_migration_matrix.py \
  --proxy-json research/trigger_migration_study/phase3/baseline_proxy_scan_1m.json \
  --hardware-json research/trigger_migration_study/phase3/hardware_scan_1m.json \
  --output research/trigger_migration_study/phase4/migration_matrix_1m.json
echo "=== DONE $(date) ==="
