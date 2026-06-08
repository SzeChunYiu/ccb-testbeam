#!/bin/bash
# Launch N isolated ccb-testbeam workers on the laptop.
# Each worker = one supervisor session launched FROM ITS OWN git worktree, so the
# codex pane's cwd is the worktree (panes inherit the invoking shell's cwd). This
# guarantees physical isolation — no worker can ever touch the shared main checkout.
# Usage: fleet/launch_local.sh [N]   (default 5)
set -uo pipefail
REPO=/home/billy/Desktop/test_beam
WT="$HOME/.tb-worktrees"
PROMPTS="$HOME/.tb-prompts"
N="${1:-5}"
mkdir -p "$WT" "$PROMPTS"
git -C "$REPO" fetch -q origin

for n in $(seq 1 "$N"); do
  label="testbeam-laptop-$n"
  path="$WT/$label"
  # ensure a clean worktree at origin/main
  if [ ! -d "$path/.git" ] && ! git -C "$REPO" worktree list | grep -q "$path"; then
    git -C "$REPO" worktree add --detach -q "$path" origin/main
  fi
  git -C "$path" checkout -q --detach origin/main 2>/dev/null
  git -C "$path" reset --hard -q origin/main
  git -C "$path" clean -fdq -e data 2>/dev/null
  ln -sfn "$REPO/data" "$path/data"   # gitignored; lets relative data paths resolve

  # one-line worker prompt (<=50 words). cwd is already the worktree -> no cd needed.
  printf '/goal You are %s, isolated in your own git worktree on ccb-testbeam (cwd here). First run: git checkout -B work-%s origin/main. Read fleet/WORKER_PROTOCOL.md + fleet/SCALING.md, then tn-ticket claim %s --project testbeam; reproduce-first, traditional AND ML, write only your reports/<id> dir, open a PR. One ticket, then stop.\n' \
    "$label" "$n" "$label" > "$PROMPTS/$label.txt"

  # (re)start this worker's session FROM its worktree so the pane cwd = worktree
  ( cd "$path" && CODEX_SUPERVISOR_SESSION="tb$n" "$HOME/codex-supervisor.sh" stop >/dev/null 2>&1 )
  rm -f "$HOME/.codex-supervisor/run/tb$n.disabled"
  ( cd "$path" && CODEX_SUPERVISOR_CEO=0 CODEX_SUPERVISOR_MANAGER=0 \
      CODEX_SUPERVISOR_SESSION="tb$n" CODEX_SUPERVISOR_PROMPTS="$PROMPTS/$label.txt" \
      "$HOME/codex-supervisor.sh" start --no-attach ) 2>&1 | grep -iE "running in background|error" | head -1 | sed "s/^/[$label] /"
done
echo "launched $N workers. dashboard: http://127.0.0.1:7777"
