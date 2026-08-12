#!/usr/bin/env bash
# run_sensitivity_campaign.sh — orchestrate the SiPM one-knob sensitivity sweep.
#
# Generates the per-knob points CSVs, freezes a source-bound campaign-intent
# manifest, submits one Slurm array per knob (with a concurrency cap), and
# records every job id. Run the analyzer afterwards with `--analyze` (waits for
# all jobs first) or by hand once the jobs drain.
#
# All sizing knobs are env-overridable (no magic numbers):
#   CCB_CAMPASSIGN_NEVENTS      events per point        (default 60)
#   CCB_CAMPASSIGN_CONCURRENCY  max parallel array tasks (default 8)
#   CCB_CAMPASSIGN_TIME         wall time per task HH:MM:SS (default 00:25:00)
#   CCB_CAMPASSIGN_BASE_CLI     common beam CLI          (see generate_points.py)
#   CCB_CAMPASSIGN_KNOBS        space-list of knobs      (default: all)
#   CCB_CAMPASSIGN_OUTDIR       output root              (required)
#   CCB_CAMPASSIGN_BUILD        build dir with ccb_stave_sim (required)
#
# Usage:
#   CCB_CAMPASSIGN_BUILD=.../build CCB_CAMPASSIGN_OUTDIR=.../ccb-runs/sipm-p2-001 \
#     bash run_sensitivity_campaign.sh            # submit only
#   ... CCB_CAMPASSIGN_ANALYZE=1 ...              # submit, wait, analyze
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${HERE}/../../.." && pwd)"
GRIDS="${HERE}/grids"
MANIFEST_TOOL="${REPO_ROOT}/scripts/single_stave/sipm_campaign_manifest.py"

BUILD="${CCB_CAMPASSIGN_BUILD:?set CCB_CAMPASSIGN_BUILD to the single_stave build dir}"
OUTDIR="${CCB_CAMPASSIGN_OUTDIR:?set CCB_CAMPASSIGN_OUTDIR}"
NEVENTS="${CCB_CAMPASSIGN_NEVENTS:-60}"
CONCURRENCY="${CCB_CAMPASSIGN_CONCURRENCY:-8}"
TIME="${CCB_CAMPASSIGN_TIME:-00:25:00}"
KNOBS="${CCB_CAMPASSIGN_KNOBS:-}"
BASE_CLI="${CCB_CAMPASSIGN_BASE_CLI:---particle proton --energy 100 --hit-x 0 --hit-y 0 --theta 0 --phi 0}"

export CCB_CAMPASSIGN_NEVENTS="$NEVENTS"
export CCB_CAMPASSIGN_BASE_CLI="$BASE_CLI"

mkdir -p "$OUTDIR"

echo "== SiPM sensitivity campaign (SIPM-P2-001) =="
echo "   build : $BUILD"
echo "   out   : $OUTDIR"
echo "   ev/pt : $NEVENTS   concurrency: $CONCURRENCY   time/task: $TIME"
echo "   base  : $BASE_CLI"

# 1) (Re)generate the per-knob grids from the documented catalogue.
python3 "${GRIDS}/generate_points.py" --outdir "$GRIDS" ${KNOBS:+--knobs $KNOBS}

# 2) Freeze campaign intent from exact repository bytes.  The expected core SHA
# is derived only from the superproject gitlink; there is no operator-supplied
# expected-core override.  Existing OUTDIR intent may only be reused byte-for-
# byte; changed intent requires a new campaign output directory.
MANIFEST="${OUTDIR}/campaign_intent.json"
MANIFEST_DIGEST="${OUTDIR}/campaign_intent.sha256"
manifest_args=(
  create
  --repo-root "$REPO_ROOT"
  --grids-dir "$GRIDS"
  --manifest "$MANIFEST"
  --digest-file "$MANIFEST_DIGEST"
  --base-cli "$BASE_CLI"
  --nevents "$NEVENTS"
)
if [[ -n "$KNOBS" ]]; then
  read -r -a selected_knobs <<< "$KNOBS"
  manifest_args+=(--knobs "${selected_knobs[@]}")
fi
EXPECTED_CORE_SHA="$(python3 "$MANIFEST_TOOL" "${manifest_args[@]}")"
MANIFEST_SHA256="$(tr -d '[:space:]' < "$MANIFEST_DIGEST")"
# Independent verify catches any unexpected write/formatting drift before job submission
# and proves that the declared expected core is the gitlink at the recorded commit.
VERIFY_CORE_SHA="$(python3 "$MANIFEST_TOOL" verify \
  --repo-root "$REPO_ROOT" --manifest "$MANIFEST" \
  --expected-sha256 "$MANIFEST_SHA256")"
if [[ "$VERIFY_CORE_SHA" != "$EXPECTED_CORE_SHA" ]]; then
  echo "fatal: campaign manifest core mismatch after create" >&2
  exit 3
fi
echo "   intent: $MANIFEST"
echo "   intent sha256: $MANIFEST_SHA256"
echo "   expected core: $EXPECTED_CORE_SHA (superproject gitlink)"

# 3) Submit one array per knob.  The manifest digest is copied into each Slurm
# job's immutable argv so editing campaign_intent.json after submission causes
# the job to fail before simulation.
JOBIDS_FILE="${OUTDIR}/submitted_job_ids.txt"
: > "$JOBIDS_FILE"

shopt -s nullglob
submitted=0
for csv in "$GRIDS"/points_*.csv; do
  knob="$(basename "$csv" .csv | sed 's/^points_//')"
  if [[ -n "$KNOBS" ]]; then
    case " $KNOBS " in *" $knob "*) ;; *) continue;; esac
  fi
  ndata=$(grep -vE '^\s*(#|$)' "$csv" | grep -vc '^label,')
  if (( ndata == 0 )); then echo "  skip $knob (no points)"; continue; fi
  last=$((ndata - 1))
  echo "  submit $knob : $ndata points  (array 0-${last}%${CONCURRENCY})"
  jid=$(sbatch --array=0-${last}%${CONCURRENCY} --time="$TIME" \
        --account="${CCB_CAMPASSIGN_ACCOUNT:-hep2023-1-3}" \
        --partition="${CCB_CAMPASSIGN_PARTITION:-hep}" \
        "${HERE}/submit_systematic.sh" "$BUILD" "$knob" "$csv" "$OUTDIR" \
        "$MANIFEST" "$MANIFEST_SHA256" \
        | awk '{print $NF}')
  echo "$knob $jid" >> "$JOBIDS_FILE"
  submitted=$((submitted+1))
done
echo "submitted $submitted knob arrays; ids in ${JOBIDS_FILE}"
cat "$JOBIDS_FILE"

# 4) Optionally wait for all to finish, then analyze.  The expected core SHA is
# always re-derived from the frozen manifest, never typed as an operator token.
if [[ "${CCB_CAMPASSIGN_ANALYZE:-0}" == "1" ]]; then
  echo "== waiting for all jobs to drain =="
  while true; do
    pending=0
    while read -r knob jid; do
      [[ -z "$jid" ]] && continue
      state=$(sacct -j "$jid" --format=State --noheader -n 2>/dev/null | \
              awk '{print $1}' | sort -u)
      # Still running / queued if any state is PENDING/RUNNING.
      if echo "$state" | grep -qE 'PENDING|RUNNING|REQUEUE'; then
        pending=$((pending+1))
      fi
    done < "$JOBIDS_FILE"
    if (( pending == 0 )); then break; fi
    echo "  $(date -Is) $pending array(s) still active; sleeping 60s"
    sleep 60
  done
  echo "== running analyzer =="
  export MPLCONFIGDIR="${MPLCONFIGDIR:-/projects/hep/fs10/shared/nnbar/billy/.mplcache}"
  PY="${CCB_CAMPASSIGN_PY:-python3}"
  EXPECTED_CORE_SHA="$("$PY" "$MANIFEST_TOOL" verify \
    --repo-root "$REPO_ROOT" --manifest "$MANIFEST" \
    --expected-sha256 "$MANIFEST_SHA256")"
  "$PY" "${REPO_ROOT}/scripts/single_stave/sipm_sensitivity.py" "$OUTDIR" \
       --grids-dir "$GRIDS" --expected-core-sha "$EXPECTED_CORE_SHA"
fi
echo "campaign submission complete."
