#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_mv3v5
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 00:20:00
#SBATCH -o %x_%j.out
#SBATCH -e %x_%j.err
#
# B-M1 / STUDY_GAPS NEW-01 : re-fit MV3 stopping profile with the REAL simulated
# two-arm trigger (Trig_bar SD deposits) produced by mv3_v5_trigger_production.sbatch.
set -eo pipefail
REPO=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam
PY=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3
DATA_CSV="${REPO}/reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz"
MC="${CCB_MC:-${REPO}/geant4/data/output_krakow_1M_trig.root}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-${TMPDIR:-/tmp}/mplcfg_${SLURM_JOB_ID:-$$}}"
mkdir -p "${MPLCONFIGDIR}"

STAMP=$(date +%s)
OUT="${REPO}/reports/mv3_v5_realtrigger_${STAMP}"
mkdir -p "${OUT}"

echo "[prologue] host=$(hostname) start=$(date -Is)"
echo "[prologue] mc=${MC}"
"${PY}" --version
md5sum "${MC}" | tee "${OUT}/mc.md5"

"${PY}" "${REPO}/scripts/mv3_stopping_v5_realtrigger.py" \
  --mc "${MC}" \
  --data "${DATA_CSV}" \
  --out "${OUT}" \
  --trig-thresh 0.5 --trig-window 20.0

echo "[job] done=$(date -Is) -> ${OUT}"
ls "${OUT}"
