#!/usr/bin/env bash
#SBATCH --job-name=ccb1623
#SBATCH --output=logs/ccb1623_%A_%a.out
#SBATCH --error=logs/ccb1623_%A_%a.err
#SBATCH --time=08:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --partition=hep
#SBATCH --account=hep2023-1-3
#SBATCH --array=0-0
#
# submit_1623.sh -- issue #1623 light-vs-energy campaign.
# ONE immutable configuration per array task -> ONE ROOT file + one sidecar.
#
# Usage:
#   mkdir -p logs
#   sbatch --array=0-$((N-1)) slurm/submit_1623.sh BUILD POINTS OUTDIR
# points csv columns (no header):
#   particle,energy_MeV,sample,x_min,x_max,y_min,y_max,theta_spread,seed,nevents
set -euo pipefail

if [ -z "${MODULESHOME:-}" ]; then source /etc/profile.d/modules.sh 2>/dev/null || true; fi
module purge 2>/dev/null || true
module load GCC/12.3.0 Geant4/11.2.2

BUILD="${1:?build dir (contains ccb_stave_sim + optical/)}"
POINTS="${2:?points csv}"
OUTDIR="${3:?output dir}"
mkdir -p "${OUTDIR}"

EXE="${BUILD}/ccb_stave_sim"
OPTICAL="${BUILD}/optical"
IDX="${SLURM_ARRAY_TASK_ID:-0}"

LINE="$(grep -vE '^\s*(#|$)' "${POINTS}" | sed -n "$((IDX+1))p")"
if [[ -z "${LINE}" ]]; then echo "no point at index ${IDX}" >&2; exit 1; fi
IFS=',' read -r PART ENE SAMPLE XMIN XMAX YMIN YMAX TSPREAD SEED NEV <<< "${LINE}"
THREADS="${CCB_THREADS:-${SLURM_CPUS_PER_TASK:-1}}"

export CCB_GIT_COMMIT="$(/usr/bin/git -C "${BUILD}/.." rev-parse HEAD 2>/dev/null || echo unknown)"
SAFE_PART="${PART//+/plus}"; SAFE_PART="${SAFE_PART//-/minus}"
OUT="${OUTDIR}/stave_${SAFE_PART}_${ENE}MeV_${SAMPLE}_s${SEED}.root"

# Optical transport cost guards (#1623). A handful of photons per 10^7 get
# trapped bouncing on a thin-layer boundary (the 10 um end-face air gap and the
# cladding shells, both UNKNOWN_EXTERNAL per #1083) and cost minutes of CPU each.
# Measured on 300 events of 20 and 60 MeV protons with the per-photon ntuple on:
#   * the LATEST arrival at the readout is 222 ns, so a 1000 ns tracking-time cut
#     removes exactly zero recorded arrivals (the SiPM response window is
#     [-20,250] ns and discards later arrivals in any case);
#   * the 200k-step cut truncates 5e-8 of generated optical photons.
# Every kill is counted per event (n_optical_killed_time / n_optical_killed_steps)
# and totalled in the sidecar, so a run states what it truncated.
GUARD=(--optical-max-time-ns 1000 --optical-max-steps 200000)

# Optional ADC-range override (#1623). The shipped placeholder gain leaves only
# ~39 pe of PEAK headroom, so the whole CCB deposit band clips and adc_* is a
# constant. Setting CCB_1623_ADC_LSB_PE widens the range so the ADC becomes a
# usable RELATIVE observable. It is NOT a calibration: the sidecar still records
# adc_gain_provenance=PLACEHOLDER_NOT_DAQ_MEASURED.
ADC_ARGS=()
if [[ -n "${CCB_1623_ADC_LSB_PE:-}" ]]; then
  ADC_ARGS=(--adc-lsb-pe "${CCB_1623_ADC_LSB_PE}")
fi

COMMON=(--physics-list QGSP_BIC
        --neutron-timecut-policy-id pin_qgsp_bic_default_10us
        --mode optical --strict-optical --no-photon-ntuple
        "${GUARD[@]}"
        "${ADC_ARGS[@]}"
        --optical-dir "${OPTICAL}")

echo "point idx=${IDX} part=${PART} E=${ENE} sample=${SAMPLE} seed=${SEED} nev=${NEV} threads=${THREADS}"
if [[ "${SAMPLE}" == "A" ]]; then
  srun "${EXE}" "${COMMON[@]}" \
    --particle "${PART}" --energy "${ENE}" \
    --hit-x-range "${XMIN}:${XMAX}" --hit-y-range "${YMIN}:${YMAX}" \
    --theta-spread "${TSPREAD}" \
    --seed "${SEED}" --nevents "${NEV}" --threads "${THREADS}" \
    --output "${OUT}"
else
  srun "${EXE}" "${COMMON[@]}" \
    --particle "${PART}" --energy "${ENE}" \
    --hit-x 0 --hit-y 0 --theta 0 --phi 0 \
    --seed "${SEED}" --nevents "${NEV}" --threads "${THREADS}" \
    --output "${OUT}"
fi

echo "wrote ${OUT} (+ ${OUT}.meta.json)"
