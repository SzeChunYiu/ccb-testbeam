#!/bin/bash
# Keeper — keeps the ccb-testbeam codex fleet running non-stop, safe, and tidy.
#
# Architecture (2026-06-09 standard): each pane is a run_pane.sh controller that drives ONE
# interactive codex (bwrap-jailed) and injects the goal as a clean /goal blob, one fresh codex
# per ticket -> cycles. Workers tb1..tbN claim+study+done+PR; the planner tbp keeps the queue
# deep with new directions. This keeper is the always-on supervisor of THOSE controllers:
#   (1) SAFETY: data immutable+intact and canonical repo intact, else hard-stop the fleet.
#   (2) ensure every controller (workers + planner) is alive; relaunch any that died.
#   (3) reap ORPHAN jails (bwrap/codex whose tmux pane is gone) -> never overload the machine.
#   (4) reap stale LOCAL ticket claims (crashed mid-study).
#   (5) auto-merge conflict-free PRs and mark their ticket done.
#   (6) log a status line from the LOCAL queue.
# Runs FOREVER (systemd --user service tb-fleet). Usage: keeper.sh [forever|N] [PERIOD_S]
set -uo pipefail
export PATH="/home/billy/.local/bin:/home/billy/bin:/home/billy/.nvm/versions/node/v24.12.0/bin:/usr/local/bin:/usr/bin:/bin"

REPO=/home/billy/Desktop/test_beam
GH=SzeChunYiu/ccb-testbeam
DATA=/home/billy/ccb-data/extracted
LOG="$HOME/.tb-keeper.log"
TN=/home/billy/tn/bin/tn
PROJECT=testbeam
TMUXROOT=/tmp/tmux-1000
N_WORKERS="${TB_WORKERS:-4}"
STALE_MIN="${TB_STALE_MIN:-45}"
PERIOD="${2:-120}"
MODE="${1:-forever}"
D0=$(ls "$DATA/sorted-a/" 2>/dev/null | wc -l)

log(){ echo "[$(date '+%F %T' 2>/dev/null||echo ?)] keeper: $*" | tee -a "$LOG"; }

controller_alive(){ pgrep -f "run_pane.sh $1\b" >/dev/null 2>&1; }   # $1 = N or "planner"
start_controller(){ nohup bash "$REPO/fleet/run_pane.sh" "$1" >/dev/null 2>&1 & }

reap_orphans(){   # kill any bwrap jail whose owning tmux pane is gone (prevents pile-up/overload)
  local pid args clone base sess killed=0
  for pid in $(pgrep -f -- '--bind /home/billy/.tb-workers/' 2>/dev/null); do
    args="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null)"
    clone="$(printf '%s' "$args" | grep -oE '/home/billy/\.tb-workers/[^ ]+' | head -1)"
    [ -n "$clone" ] || continue
    base="$(basename "$clone")"
    case "$base" in
      testbeam-laptop-*) sess="tb${base##*-}" ;;
      tb-planner)        sess="tbp" ;;
      *)                 continue ;;
    esac
    if ! tmux -S "$TMUXROOT/$sess" has-session -t "$sess" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null && killed=$((killed+1))
    fi
  done
  [ "$killed" -gt 0 ] && log "reaped $killed orphan jail proc(s)"
  return 0
}

cycle(){
  local d merged pr shared tid dead n stat orphans
  # (1) SAFETY
  d=$(ls "$DATA/sorted-a/" 2>/dev/null | wc -l)
  if [ "$d" != "$D0" ] || [ ! -d "$REPO/docs" ]; then
    log "!!! SAFETY BREACH data=$d/$D0 repo=$([ -d "$REPO/docs" ] && echo OK || echo GONE) — STOPPING FLEET"
    for n in $(seq 1 "$N_WORKERS") ; do pkill -9 -f "run_pane.sh $n\b" 2>/dev/null; tmux -S "$TMUXROOT/tb$n" kill-server 2>/dev/null; done
    pkill -9 -f "run_pane.sh planner" 2>/dev/null; tmux -S "$TMUXROOT/tbp" kill-server 2>/dev/null
    exit 2
  fi
  # (2) ensure controllers alive
  dead=""
  for n in $(seq 1 "$N_WORKERS"); do controller_alive "$n" || { dead="$dead tb$n"; start_controller "$n"; }; done
  controller_alive planner || { dead="$dead tbp"; start_controller planner; }
  # (3) reap orphan jails
  reap_orphans
  # (4) reap stale local claims
  "$TN" ticket reaper "$PROJECT" --stale-min "$STALE_MIN" >/dev/null 2>&1
  # (5) auto-merge conflict-free PRs + mark ticket done
  merged=0
  for pr in $(gh pr list --repo "$GH" --state open --json number -q '.[].number' 2>/dev/null); do
    shared=$(gh pr view "$pr" --repo "$GH" --json files -q '.files[].path' 2>/dev/null \
              | grep -vE '^(reports/|scripts/[sp][0-9]|configs/[sp][0-9]|studies/STUDIES\.md|reports/SUMMARY\.md|README\.md)' | head -1)
    if [ -z "$shared" ]; then
      gh pr ready "$pr" --repo "$GH" >/dev/null 2>&1
      if gh pr merge "$pr" --repo "$GH" --squash --delete-branch >/dev/null 2>&1; then
        merged=$((merged+1))
        tid=$(gh pr view "$pr" --repo "$GH" --json files -q '.files[].path' 2>/dev/null \
               | sed -n 's#^reports/\([0-9][0-9.]*\.[0-9a-f]\+\)__.*#\1#p' | head -1)
        [ -n "$tid" ] && "$TN" ticket done "$PROJECT" "$tid" >/dev/null 2>&1
      fi
    fi
  done
  # (6) status
  stat=$("$TN" ticket list "$PROJECT" 2>/dev/null)
  log "data=$d/$D0 repo=OK $stat merged_now=$merged relaunched=[${dead:- none}]"
}

log "start mode=$MODE period=${PERIOD}s workers=$N_WORKERS stale=${STALE_MIN}m"
if [ "$MODE" = forever ]; then
  while :; do cycle; sleep "$PERIOD"; done
else
  for c in $(seq 1 "$MODE"); do cycle; [ "$c" -lt "$MODE" ] && sleep "$PERIOD"; done
fi
