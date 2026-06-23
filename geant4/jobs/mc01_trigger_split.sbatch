#!/bin/bash
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -J ccb_trigsplit
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 00:25:00
#SBATCH -o %x_%j.out
#SBATCH -e %x_%j.err
# CCB test beam: full Sample I/II trigger-split pipeline (MC + DATA + comparison).
set -euo pipefail

REPO=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam
PY=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3
MC=$REPO/geant4/data/output_krakow_1M.root
DATA_TABLE=$REPO/reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz

STAMP=$(date +%s)
OUT=$REPO/reports/sampleI_II_trigger_split_${STAMP}
MCOUT=$OUT/mc; DAOUT=$OUT/data; CMPOUT=$OUT/compare
mkdir -p "$MCOUT" "$DAOUT" "$CMPOUT"

echo "[job] host=$(hostname) start=$(date -Is)"
"$PY" --version

echo "[1/3] MC trigger-split truth ..."
"$PY" "$REPO/scripts/mc01_trigger_split_truth.py" \
    --mc "$MC" --out "$MCOUT" --coinc-ns 15 --edep-large-mev 15.0

echo "[2/3] DATA sample split ..."
"$PY" "$REPO/scripts/data01_sample_split_staves.py" \
    --table "$DATA_TABLE" --out "$DAOUT" --large-adc 6000 --sat-adc 7000

echo "[3/3] DATA<->MC comparison ..."
"$PY" "$REPO/scripts/compare_data_mc.py" \
    --mc-dir "$MCOUT" --data-dir "$DAOUT" --out "$CMPOUT"

echo "[job] done=$(date -Is)  -> $OUT"
find "$OUT" -type f | sort
