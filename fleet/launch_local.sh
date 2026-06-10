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
# Sandboxed codex via EXTERNAL bubblewrap jail (~/.tb-bwrap-codex.sh).
# codex 0.129-alpha's internal Landlock sandbox is broken on this kernel (5.15): it grants write
# ONLY to the workspace cwd — not .git, not any --add-dir root — so workers could not commit, PR,
# or claim tickets. The bwrap wrapper bypasses that broken sandbox and confines codex itself:
#   rw = this clone (incl .git) + tn-ticket queue + caches + gh config + CODEX_HOME
#   ro = canonical repo, immutable data store, all other clones.
# Proven: git commit + ticket claim work; data/repo/other-clone writes are EROFS. See the wrapper
# header and fleet/LESSONS.md. (Old broken line kept for reference:)
#   codex --sandbox workspace-write --ask-for-approval never -c sandbox_workspace_write.network_access=true --add-dir /home/billy/.config/tn --add-dir /home/billy/.cache --add-dir /home/billy/.config/gh
SANDBOXED_CODEX="$HOME/.tb-bwrap-codex.sh"
mkdir -p "$WK" "$PROMPTS"

[ -d "$DATA" ] || { echo "ERROR: data store $DATA missing — run data setup first"; exit 1; }

for n in $(seq 1 "$N"); do
  label="testbeam-laptop-$n"
  clone="$WK/$label"
  # fresh, self-contained clone (code only; data is external)
  rm -rf "$clone" 2>/dev/null
  git clone -q --depth 1 "$GH" "$clone" || { echo "[$label] clone failed"; continue; }
  ln -sfn "$DATA" "$clone/data"          # read-only data (immutable + outside sandbox)

  # SHORT, SELF-CONTAINED, SLASH-FREE prompt. Rules learned the hard way:
  #  * Only the leading /goal may contain a slash — codex's TUI slash-menu EATS any other "/"
  #    (a path like fleet/X.md injected mid-prompt loses its slash, and a long blob injected
  #    before the composer is ready mis-resolves /goal -> /model). So NO paths, NO extra slashes.
  #  * Keep it short and don't tell the worker to read long docs — reading docs/ wastes turns and
  #    can freeze the pane. The worker is a capable agent; the essentials are inline here.
  #  * Keep /goal — it drives the auto-cycle (Pursuing goal -> auto-resend -> next ticket).
  printf '/goal Take ONE ccb-testbeam study: run "tn-ticket claim %s --project testbeam". Reproduce its number from raw ROOT, then a traditional AND an ML method split by run with held-out CIs, write a short report, run "tn-ticket done <id>", open a PR, then stop.\n' \
    "$label" > "$PROMPTS/$label.txt"

  ( cd "$clone" && CODEX_SUPERVISOR_SESSION="tb$n" "$HOME/codex-supervisor.sh" stop >/dev/null 2>&1 )
  rm -f "$HOME/.codex-supervisor/run/tb$n.disabled"
  ( cd "$clone" && CODEX_SUPERVISOR_CEO=0 CODEX_SUPERVISOR_MANAGER=0 \
      CODEX_SUPERVISOR_CMD="$SANDBOXED_CODEX" \
      CODEX_SUPERVISOR_SESSION="tb$n" CODEX_SUPERVISOR_PROMPTS="$PROMPTS/$label.txt" \
      "$HOME/codex-supervisor.sh" start --no-attach ) 2>&1 \
      | grep -iE "running in background|error" | head -1 | sed "s/^/[$label] /"
done
echo "launched $N sandboxed workers. dashboard: http://127.0.0.1:7777"
