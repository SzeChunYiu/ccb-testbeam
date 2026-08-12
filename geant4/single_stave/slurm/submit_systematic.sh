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
#     BUILD KNOB POINTS_CSV OUTDIR CAMPAIGN_MANIFEST MANIFEST_SHA256 \
#     BUILD_RECEIPT BUILD_RECEIPT_SHA256
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
BUILD_RECEIPT_TOOL="${REPO_ROOT}/scripts/single_stave/sipm_build_receipt.py"

# Geant4 runtime: the build links G4 dynamically, so the build-time toolchain
# must be loaded on the compute node (not inherited from the login session).
module purge 2>/dev/null || true
module load ${CCB_CAMPASSIGN_MODULES:-GCC/12.3.0 Geant4/11.2.2}

BUILD="${1:?usage: submit_systematic.sh BUILD KNOB POINTS_CSV OUTDIR CAMPAIGN_MANIFEST MANIFEST_SHA256 BUILD_RECEIPT BUILD_RECEIPT_SHA256}"
KNOB="${2:?KNOB name (used for OUTDIR/KNOB)}"
POINTS="${3:?points csv}"
OUTROOT="${4:?output root dir}"
MANIFEST="${5:?campaign_intent.json required}"
MANIFEST_SHA256="${6:?frozen campaign manifest SHA-256 required}"
BUILD_RECEIPT="${7:?frozen build_receipt.json required}"
BUILD_RECEIPT_SHA256="${8:?frozen build receipt SHA-256 required}"
OUTDIR="${OUTROOT}/${KNOB}"
mkdir -p "${OUTDIR}"

EXE="${BUILD}/ccb_stave_sim"
OPTICAL="${BUILD}/optical"
IDX="${SLURM_ARRAY_TASK_ID:-0}"

# Common beam point for every sweep. The inherited value is not trusted until
# it matches the frozen manifest execution intent below.
BASE_CLI="${CCB_CAMPASSIGN_BASE_CLI:---particle proton --energy 100 --hit-x 0 --hit-y 0 --theta 0 --phi 0}"

# Read the IDX-th DATA row, but do not export row state or launch simulation
# until the whole grid and this execution intent are verified.
LINE="$(grep -vE '^\s*(#|$)' "${POINTS}" | grep -v '^label,' | sed -n "$((IDX+1))p")"
if [[ -z "${LINE}" ]]; then echo "no point at index ${IDX} in ${POINTS}"; exit 1; fi
IFS=',' read -r LABEL SEED NEVENTS CLI_ARGS ENV_VARS REPLICATE _REST <<< "${LINE}"
: "${SEED:=$((IDX+1))}"
: "${NEVENTS:=60}"
: "${CLI_ARGS:=}"
: "${ENV_VARS:=}"
: "${REPLICATE:=}"

# Fail before simulation if manifest bytes, recorded Git-object source binding,
# selected grid bytes, or runtime execution intent differ from submission.
EXPECTED_CORE_SHA="$(python3 "$MANIFEST_TOOL" verify \
  --repo-root "$REPO_ROOT" --manifest "$MANIFEST" \
  --expected-sha256 "$MANIFEST_SHA256" \
  --grid-knob "$KNOB" --grid-file "$POINTS" \
  --base-cli "$BASE_CLI" --nevents "$NEVENTS" --threads 1)"

# Re-hash the exact executable, configured toolchain/package sentinels and
# campaign-owned receipt, then execute the binary's pre-event self-hash probe.
# A stale or substituted executable therefore fails before event zero.
OBSERVED_BUILD_SHA256="$(python3 "$BUILD_RECEIPT_TOOL" verify \
  --receipt "$BUILD_RECEIPT" \
  --expected-sha256 "$BUILD_RECEIPT_SHA256" \
  --executable "$EXE" \
  --runtime-probe \
  --campaign-manifest "$MANIFEST" \
  --campaign-sha256 "$MANIFEST_SHA256" \
  --repo-root "$REPO_ROOT")"
if [[ "$OBSERVED_BUILD_SHA256" != "$BUILD_RECEIPT_SHA256" ]]; then
  echo "fatal: verified build receipt digest changed unexpectedly" >&2
  exit 3
fi
EXPECTED_ROOT_SHA="$(python3 - "$BUILD_RECEIPT" <<'PY'
import json, pathlib, sys
print(json.loads(pathlib.Path(sys.argv[1]).read_text())["source"]["superproject_commit"])
PY
)"
EXPECTED_EXE_SHA256="$(python3 - "$BUILD_RECEIPT" <<'PY'
import json, pathlib, sys
print(json.loads(pathlib.Path(sys.argv[1]).read_text())["executable"]["sha256"])
PY
)"

OUT="${OUTDIR}/${LABEL}.root"

# Export per-row SiPM-core env overrides (may be blank).
if [[ -n "${ENV_VARS}" ]]; then
  # At most one VAR=val per row (one-knob-at-a-time); safe under IFS=','.
  export "${ENV_VARS}"
fi

echo "[$(date -Is)] idx=${IDX} knob=${KNOB} label=${LABEL} seed=${SEED} nev=${NEVENTS} replicate=${REPLICATE}"
echo "  cli=[${BASE_CLI} ${CLI_ARGS}] env=[${ENV_VARS}]"
echo "  campaign_manifest_sha256=${MANIFEST_SHA256} expected_root=${EXPECTED_ROOT_SHA} expected_core=${EXPECTED_CORE_SHA}"
echo "  build_receipt_sha256=${BUILD_RECEIPT_SHA256} expected_executable_sha256=${EXPECTED_EXE_SHA256}"

# Legacy root sidecar field remains an environment bridge, but for this
# orchestrated path it is derived only after receipt/source/executable closure.
# The build receipt and point provenance, not this field alone, are authorising.
export CCB_GIT_COMMIT="$EXPECTED_ROOT_SHA"
export CCB_STRICT_OPTICAL="${CCB_STRICT_OPTICAL:-1}"

srun "${EXE}" \
  --mode optical \
  ${BASE_CLI} \
  ${CLI_ARGS} \
  --seed "${SEED}" --nevents "${NEVENTS}" --threads 1 \
  --optical-dir "${OPTICAL}" \
  --output "${OUT}"

# Producer-side core revision is compile-bound by #1280. Require the actual run
# sidecar plus a second post-run executable observation to match frozen source
# and build intent before this task can succeed.
python3 "$BUILD_RECEIPT_TOOL" verify \
  --receipt "$BUILD_RECEIPT" \
  --expected-sha256 "$BUILD_RECEIPT_SHA256" \
  --executable "$EXE" \
  --runtime-probe \
  --campaign-manifest "$MANIFEST" \
  --campaign-sha256 "$MANIFEST_SHA256" \
  --repo-root "$REPO_ROOT" >/dev/null

python3 - "$OUT" "$EXPECTED_ROOT_SHA" "$EXPECTED_CORE_SHA" "$EXPECTED_EXE_SHA256" "$MANIFEST_SHA256" "$BUILD_RECEIPT_SHA256" <<'PY'
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
expected_root = sys.argv[2]
expected_core = sys.argv[3]
expected_exe = sys.argv[4]
manifest_sha = sys.argv[5]
build_receipt_sha = sys.argv[6]
meta_path = pathlib.Path(str(root) + ".meta.json")
meta = json.loads(meta_path.read_text())
if meta.get("git_commit") != expected_root:
    raise SystemExit(
        f"fatal: {meta_path}: git_commit={meta.get('git_commit')!r} != campaign/build root {expected_root}"
    )
dig = meta.get("digitizer")
if not isinstance(dig, dict):
    raise SystemExit(f"fatal: {meta_path}: digitizer block missing")
actual_core = dig.get("ccb_sipm_core_commit")
if not isinstance(actual_core, str) or re.fullmatch(r"[0-9a-f]{40}", actual_core) is None:
    raise SystemExit(f"fatal: {meta_path}: invalid ccb_sipm_core_commit={actual_core!r}")
if actual_core != expected_core:
    raise SystemExit(
        f"fatal: {meta_path}: compiled core {actual_core} != campaign expected {expected_core}"
    )
point_prov = {
    "schema": "ccb-sipm-campaign-point/2",
    "campaign_manifest_sha256": manifest_sha,
    "build_receipt_sha256": build_receipt_sha,
    "expected_superproject_commit": expected_root,
    "observed_superproject_commit": meta.get("git_commit"),
    "expected_core_commit": expected_core,
    "observed_core_commit": actual_core,
    "expected_executable_sha256": expected_exe,
    "source_match": True,
    "core_match": True,
    "executable_match_pre_and_post_run": True,
    "scientific_scope": "CAMPAIGN_SOURCE_BUILD_EXECUTABLE_IDENTITY_ONLY",
}
pathlib.Path(str(root) + ".campaign.json").write_text(
    json.dumps(point_prov, sort_keys=True, separators=(",", ":")) + "\n"
)
PY

echo "wrote ${OUT} (+ ${OUT}.meta.json + ${OUT}.campaign.json)"
