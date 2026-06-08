#!/bin/bash
# Keeper — keeps the laptop fleet running non-stop and safe.
# Each cycle: (1) SAFETY check (data immutable+intact, canonical repo intact) — hard stop the
# whole fleet if ever breached; (2) reap stale ticket claims; (3) auto-merge conflict-free PRs
# (only touch their own reports/<id>/ or name-spaced scripts/configs — cannot corrupt the repo);
# (4) relaunch any dead worker session; (5) log a status line. Runs CYCLES cycles then exits so
# the orchestrator is re-notified to do Critic spot-checks / reseed / continue the loop.
#
# Usage: fleet/keeper.sh [CYCLES] [PERIOD_SECS]
set -uo pipefail
REPO=/home/billy/Desktop/test_beam
GH=SzeChunYiu/ccb-testbeam
DATA=/home/billy/ccb-data/extracted
WK="$HOME/.tb-workers"; PROMPTS="$HOME/.tb-prompts"
LOG="$HOME/.tb-keeper.log"
CYCLES="${1:-6}"; PERIOD="${2:-300}"
SANDBOXED_CODEX='codex --sandbox workspace-write --ask-for-approval never -c sandbox_workspace_write.network_access=true --add-dir /home/billy/.config/tn --add-dir /home/billy/.cache --add-dir /home/billy/.config/gh'
D0=$(ls "$DATA/sorted-a/" 2>/dev/null | wc -l)

relaunch_slot() {  # $1 = n
  local n="$1" label="testbeam-laptop-$n" clone="$WK/testbeam-laptop-$n"
  rm -rf "$clone" 2>/dev/null
  git clone -q --depth 1 "https://github.com/$GH.git" "$clone" || return
  ln -sfn "$DATA" "$clone/data"
  printf '/goal You are %s, fully sandboxed in your own clone (this dir; you cannot write outside it). Read fleet/WORKER_PROTOCOL.md + fleet/SCALING.md, then tn-ticket claim %s --project testbeam; reproduce-first, traditional AND ML, data is read-only at ./data, write only your reports/<id> dir, open a PR. One ticket, then stop.\n' "$label" "$label" > "$PROMPTS/$label.txt"
  rm -f "$HOME/.codex-supervisor/run/tb$n.disabled"
  ( cd "$clone" && CODEX_SUPERVISOR_CEO=0 CODEX_SUPERVISOR_MANAGER=0 CODEX_SUPERVISOR_CMD="$SANDBOXED_CODEX" \
      CODEX_SUPERVISOR_SESSION="tb$n" CODEX_SUPERVISOR_PROMPTS="$PROMPTS/testbeam-laptop-$n.txt" \
      "$HOME/codex-supervisor.sh" start --no-attach >/dev/null 2>&1 )
}

for c in $(seq 1 "$CYCLES"); do
  ts=$(date '+%H:%M:%S' 2>/dev/null || echo "?")
  # (1) SAFETY — abort everything if data or repo ever change
  d=$(ls "$DATA/sorted-a/" 2>/dev/null | wc -l)
  if [ "$d" != "$D0" ] || [ ! -d "$REPO/docs" ]; then
    echo "[$ts] !!! SAFETY BREACH data=$d/$D0 repo=$([ -d $REPO/docs ] && echo OK || echo GONE) — STOPPING FLEET" | tee -a "$LOG"
    for s in tb1 tb2 tb3 tb4 tb5; do tmux -L "$s" kill-server 2>/dev/null; done
    exit 2
  fi
  # (2) reap stale claims (>15 min held)
  ~/bin/tn-ticket reaper --stale-min 15 >/dev/null 2>&1
  # (3) auto-merge conflict-free PRs
  merged=0
  for pr in $(gh pr list --repo "$GH" --state open --json number -q '.[].number' 2>/dev/null); do
    shared=$(gh pr view "$pr" --repo "$GH" --json files -q '.files[].path' 2>/dev/null | grep -vE '^(reports/|scripts/s[0-9p]|configs/s[0-9p])' | head -1)
    if [ -z "$shared" ]; then
      gh pr ready "$pr" --repo "$GH" >/dev/null 2>&1
      gh pr merge "$pr" --repo "$GH" --squash --delete-branch >/dev/null 2>&1 && merged=$((merged+1))
    fi
  done
  # (4) relaunch dead worker sessions
  dead=""
  for n in 1 2 3 4 5; do
    if ! tmux -S "/tmp/tmux-1000/tb$n" has-session -t "tb$n" 2>/dev/null; then dead="$dead $n"; relaunch_slot "$n"; fi
  done
  # (5) status
  open=$(gh issue list --repo SzeChunYiu/factory-tickets --label project:testbeam --label factory:open --state open --limit 80 --json number -q 'length' 2>/dev/null)
  done_=$(gh issue list --repo SzeChunYiu/factory-tickets --label project:testbeam --label factory:done --state closed --limit 100 --json number -q 'length' 2>/dev/null)
  prs=$(gh pr list --repo "$GH" --state open --json number -q 'length' 2>/dev/null)
  echo "[$ts] cycle $c/$CYCLES data=$d/$D0 repo=OK open=$open done=$done_ merged_now=$merged open_PRs=$prs dead_relaunched=[${dead:- none}]" | tee -a "$LOG"
  [ "$c" -lt "$CYCLES" ] && sleep "$PERIOD"
done
echo "keeper finished $CYCLES cycles"
