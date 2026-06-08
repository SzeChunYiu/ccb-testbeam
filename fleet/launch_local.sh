#!/bin/bash
# Launch N SANDBOXED, isolated ccb-testbeam workers on the laptop.
#
# Safety design (after the 2026-06-08 data-loss incident):
#  1. Each worker = its OWN full git CLONE at ~/.tb-workers/<label> (self-contained
#     .git inside the workspace, so the OS sandbox can confine the worker entirely
#     to that clone — a shared-.git worktree could not commit under the sandbox).
#  2. codex runs with `--sandbox workspace-write`: the OS BLOCKS any write/delete
#     outside the clone. Verified: out-of-workspace `rm -rf` is "Rejected by policy".
#  3. Data is OUTSIDE the repo at /home/billy/ccb-data (immutable, chattr +i),
#     mounted read-only into each clone as ./data. A worker cannot reach it to
#     write, and even if it could, the files are immutable.
# Net: a worker can only ever damage its own disposable clone.
#
# Usage: fleet/launch_local.sh [N]   (default 5)
set -uo pipefail
GH=https://github.com/SzeChunYiu/ccb-testbeam.git
DATA=/home/billy/ccb-data/extracted
WK="$HOME/.tb-workers"
PROMPTS="$HOME/.tb-prompts"
N="${1:-5}"
# sandboxed codex: confine writes to the clone, keep network for git/gh/tn-ticket
SANDBOXED_CODEX='codex --sandbox workspace-write --ask-for-approval never -c sandbox_workspace_write.network_access=true'
mkdir -p "$WK" "$PROMPTS"

[ -d "$DATA" ] || { echo "ERROR: data store $DATA missing — run data setup first"; exit 1; }

for n in $(seq 1 "$N"); do
  label="testbeam-laptop-$n"
  clone="$WK/$label"
  # fresh, self-contained clone (code only; data is external)
  rm -rf "$clone" 2>/dev/null
  git clone -q --depth 1 "$GH" "$clone" || { echo "[$label] clone failed"; continue; }
  ln -sfn "$DATA" "$clone/data"          # read-only data (immutable + outside sandbox)

  printf '/goal You are %s, fully sandboxed in your own clone (this dir; you cannot write outside it). Read fleet/WORKER_PROTOCOL.md + fleet/SCALING.md, then tn-ticket claim %s --project testbeam; reproduce-first, traditional AND ML, data is read-only at ./data, write only your reports/<id> dir, open a PR. One ticket, then stop.\n' \
    "$label" "$label" > "$PROMPTS/$label.txt"

  ( cd "$clone" && CODEX_SUPERVISOR_SESSION="tb$n" "$HOME/codex-supervisor.sh" stop >/dev/null 2>&1 )
  rm -f "$HOME/.codex-supervisor/run/tb$n.disabled"
  ( cd "$clone" && CODEX_SUPERVISOR_CEO=0 CODEX_SUPERVISOR_MANAGER=0 \
      CODEX_SUPERVISOR_CMD="$SANDBOXED_CODEX" \
      CODEX_SUPERVISOR_SESSION="tb$n" CODEX_SUPERVISOR_PROMPTS="$PROMPTS/$label.txt" \
      "$HOME/codex-supervisor.sh" start --no-attach ) 2>&1 \
      | grep -iE "running in background|error" | head -1 | sed "s/^/[$label] /"
done
echo "launched $N sandboxed workers. dashboard: http://127.0.0.1:7777"
