#!/usr/bin/env bash
#SBATCH --job-name=ccb_sipm_sens
#SBATCH --output=ccb_sipm_sens_%A_%a.out
#SBATCH --error=ccb_sipm_sens_%A_%a.err
#SBATCH --time=00:30:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --array=0-0
#
# submit_systematic.sh — generic one-knob-at-a-time sensitivity driver.
# Each array task runs ONE immutable config -> ONE .root (+ .meta.json) under
# OUTDIR/KNOB/<label>.root. The per-row spec comes from a points CSV emitted by
# grids/generate_points.py, so this script is fully knob-agnostic.
#
# Usage:
#   sbatch --array=0-$((N-1))%CAP slurm/submit_systematic.sh \
#     BUILD KNOB POINTS_CSV OUTDIR CAMPAIGN_MANIFEST MANIFEST_SHA256
# Columns (points CSV, after the header):
#   label,seed,nevents,cli_args,env_vars[,replicate]
#   - cli_args: extra flags appended to ccb_stave_sim (e.g. "--pde-scale 1.2")
#   - env_vars: "VAR=val" (or blank) exported before the run, e.g.
#               "CCB_SIPM_CROSSTALK_PROB=0.06"
#   - replicate: optional paired-seed replicate index (issue #984)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${HERE}/../../.." && pwd)"
MANIFEST_TOOL="${REPO_ROOT}/scripts/single_stave/sipm_campaign_manifest.py"

# Geant4 runtime: the build links G4 dynamically, so the build-time toolchain
# must be loaded on the compute node (not inherited from the login session).
module purge 2>/dev/null || true
module load ${CCB_CAMPASSIGN_MODULES:-GCC/12.3.0 Geant4/11.2.2}

BUILD="${1:?usage: submit_systematic.sh BUILD KNOB POINTS_CSV OUTDIR CAMPAIGN_MANIFEST MANIFEST_SHA256}"
KNOB="${2:?KNOB name (used for OUTDIR/KNOB)}"
POINTS="${3:?points csv}"
OUTROOT="${4:?output root dir}"
MANIFEST="${5:?campaign_intent.json required}"
MANIFEST_SHA256="${6:?frozen campaign manifest SHA-256 required}"
OUTDIR="${OUTROOT}/${KNOB}"
mkdir -p "${OUTDIR}"

# Fail before simulation if campaign intent or this knob's points grid changed
# after submission.  The expected core revision is derived from the verified
# superproject-gitlink manifest, not from caller memory or a mutable env label.
EXPECTED_CORE_SHA="$(python3 "$MANIFEST_TOOL" verify \
  --manifest "$MANIFEST" --expected-sha256 "$MANIFEST_SHA256" \
  --grid-knob "$KNOB" --grid-file "$POINTS")"

EXE="${BUILD}/ccb_stave_sim"
OPTICAL="${BUILD}/optical"
IDX="${SLURM_ARRAY_TASK_ID:-0}"

# Common beam point for every sweep (env-overridable). Proton 100 MeV, normal
# incidence, centred — the representative operating point.
BASE_CLI="${CCB_CAMPASSIGN_BASE_CLI:---particle proton --energy 100 --hit-x 0 --hit-y 0 --theta 0 --phi 0}"

# Read the IDX-th DATA row: skip blanks, comments, and the header line.
LINE="$(grep -vE '^\s*(#|$)' "${POINTS}" | grep -v '^label,' | sed -n "$((IDX+1))p")"
if [[ -z "${LINE}" ]]; then echo "no point at index ${IDX} in ${POINTS}"; exit 1; fi
IFS=',' read -r LABEL SEED NEVENTS CLI_ARGS ENV_VARS REPLICATE _REST <<< "${LINE}"
: "${SEED:=$((IDX+1))}"
: "${NEVENTS:=60}"
: "${CLI_ARGS:=}"
: "${ENV_VARS:=}"
: "${REPLICATE:=}"

OUT="${OUTDIR}/${LABEL}.root"

# Export per-row SiPM-core env overrides (may be blank).
if [[ -n "${ENV_VARS}" ]]; then
  # At most one VAR=val per row (one-knob-at-a-time); safe under IFS=','.
  export "${ENV_VARS}"
fi

echo "[$(date -Is)] idx=${IDX} knob=${KNOB} label=${LABEL} seed=${SEED} nev=${NEVENTS} replicate=${REPLICATE}"
echo "  cli=[${BASE_CLI} ${CLI_ARGS}] env=[${ENV_VARS}]"
echo "  campaign_manifest_sha256=${MANIFEST_SHA256} expected_core=${EXPECTED_CORE_SHA}"

export CCB_GIT_COMMIT="$(git -C "${BUILD}" rev-parse HEAD 2>/dev/null || echo unknown)"
export CCB_STRICT_OPTICAL="${CCB_STRICT_OPTICAL:-1}"

srun "${EXE}" \
  --mode optical \
  ${BASE_CLI} \
  ${CLI_ARGS} \
  --seed "${SEED}" --nevents "${NEVENTS}" --threads 1 \
  --optical-dir "${OPTICAL}" \
  --output "${OUT}"

# Producer-side source revision is compile-bound by #1280.  Require the actual
# run sidecar to match frozen campaign intent before this task can succeed.
python3 - "$OUT" "$EXPECTED_CORE_SHA" "$MANIFEST_SHA256" <<'PY'
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
expected = sys.argv[2]
manifest_sha = sys.argv[3]
meta_path = pathlib.Path(str(root) + ".meta.json")
meta = json.loads(meta_path.read_text())
dig = meta.get("digitizer")
if not isinstance(dig, dict):
    raise SystemExit(f"fatal: {meta_path}: digitizer block missing")
actual = dig.get("ccb_sipm_core_commit")
if not isinstance(actual, str) or re.fullmatch(r"[0-9a-f]{40}", actual) is None:
    raise SystemExit(f"fatal: {meta_path}: invalid ccb_sipm_core_commit={actual!r}")
if actual != expected:
    raise SystemExit(
        f"fatal: {meta_path}: compiled core {actual} != campaign expected {expected}"
    )
point_prov = {
    "schema": "ccb-sipm-campaign-point/1",
    "campaign_manifest_sha256": manifest_sha,
    "expected_core_commit": expected,
    "observed_core_commit": actual,
    "core_match": True,
}
pathlib.Path(str(root) + ".campaign.json").write_text(
    json.dumps(point_prov, sort_keys=True, separators=(",", ":")) + "\n"
)
PY

echo "wrote ${OUT} (+ ${OUT}.meta.json + ${OUT}.campaign.json)"
