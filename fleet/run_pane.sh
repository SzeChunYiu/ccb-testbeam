#!/bin/bash
# run_pane.sh N — drive ONE ccb-testbeam worker pane the PROVEN-WORKING way.
#
# ┌─ THE STANDARD (verified 2026-06-09 on billy, codex 0.129-alpha.15, gpt-5.5) ──────────────┐
# │ Run INTERACTIVE codex (not `codex exec` — exec returns a bogus "usage limit") inside a    │
# │ tmux pane, and deliver the goal by injecting the WHOLE "/goal …" line as ONE literal       │
# │ keystroke blob, only after the composer is READY ("Tip:" shown).                           │
# │   * Do NOT decouple the slash (send "/" then body) — that mis-resolves /goal -> /model.     │
# │   * Keep the body SLASH-FREE (the TUI slash-menu eats any other "/"; describe paths in      │
# │     words, e.g. "a reports subfolder named by the ticket id").                              │
# │   * /goal is a real, working codex command ("Goal active … Goal achieved"); it is what      │
# │     makes the pane pursue and finish the objective.                                         │
# │ One FRESH codex per ticket: claim -> study -> done -> PR -> "Goal achieved" -> restart for   │
# │ the next ticket. This cycles non-stop and is visible in tmux (attach: tmux -S <sock> a -t). │
# └────────────────────────────────────────────────────────────────────────────────────────────┘
set -uo pipefail
export PATH="/home/billy/.local/bin:/home/billy/bin:/home/billy/.nvm/versions/node/v24.12.0/bin:/usr/local/bin:/usr/bin:/bin"

# Arg is a worker index N (-> pane tbN, label testbeam-laptop-N) OR the literal "planner".
arg="${1:?usage: run_pane.sh <N|planner>}"
GH=https://github.com/SzeChunYiu/ccb-testbeam.git
DATA=/home/billy/ccb-data/extracted
WRAP="$HOME/.tb-bwrap-codex.sh"
GOAL_TIMEOUT="${TB_GOAL_TIMEOUT:-2700}"   # max 45 min per round before we restart the pane
POST_IDLE="${TB_POST_IDLE:-4}"            # sleep between rounds (overridden for the planner)
export CODEX_HOME="${CODEX_HOME:-/home/billy/.codex}"   # the user's default config (gpt-5.5)

if [ "$arg" = planner ]; then
  role=planner; label=planner; clone="$HOME/.tb-workers/tb-planner"; SESS="tbp"; SOCK="/tmp/tmux-1000/tbp"
  LOG="$HOME/.tb-planner.log"; POST_IDLE="${TB_PLANNER_IDLE:-1200}"   # plan every ~20 min
  # Slash-free planner /goal. The PI keeps the pipeline deep so the fleet never runs dry and our
  # understanding of the scintillator PULSE reaches the most atomic level.
  # SHORT planner prompt. NOTE the --project testbeam on the list command (bare "testbeam" reads the
  # wrong default queue and makes the throttle always fire).
  GOAL="/goal You are the ccb-testbeam Principal Investigator. Run \"tn-ticket list testbeam --project testbeam\". If open is under 18, append 3 NEW non-duplicate ACADEMIC-GRADE study tickets via tn-ticket append --project testbeam, each naming a traditional method AND several ML/NN methods to compare (ridge, gradient-boosted trees, MLP, 1D-CNN, transformer where apt) with bootstrap CIs, deepening pulse understanding (shape, timing, pile-up, saturation, pedestal, energy, PID). Trim reports SUMMARY.md to under 200 lines (scoreboard rows only; delete any running pass-log). Keep markdown short. Commit, push. Stop."
else
  role=worker; n="$arg"; label="testbeam-laptop-$n"; clone="$HOME/.tb-workers/$label"
  SESS="tb$n"; SOCK="/tmp/tmux-1000/tb$n"; LOG="$HOME/.tb-worker-$n.log"
  # Slash-free /goal (only the leading /goal carries a slash). Self-contained; no long-doc reading.
  # SHORT prompt (a long /goal fails with a bogus "usage limit"). The REPORT itself must be detailed
  # and academic-grade -- that lives in the per-study file, not in this prompt.
  GOAL="/goal You are $label. Claim ONE ticket: run \"tn-ticket claim $label --project testbeam\" once (queue empty means stop; never claim twice). Reproduce its number from raw ROOT in the data folder, then benchmark a strong traditional method against several ML/NN methods (ridge, gradient-boosted trees, MLP, 1D-CNN, and a new architecture when sensible), split by run with bootstrap CIs; name the winner in result.json. Write a DETAILED academic-grade REPORT.md (methods, equations, tables with CIs, systematics, caveats). Run tn-ticket done, open a PR, append at most 1 novel ticket. Stop."
fi

log(){ echo "[$(date '+%F %T' 2>/dev/null||echo ?)] $label: $*" >> "$LOG"; }
cap(){ tmux -S "$SOCK" capture-pane -t "$SESS" -p 2>/dev/null; }
alive(){ tmux -S "$SOCK" has-session -t "$SESS" 2>/dev/null; }

setup_clone(){
  [ -d "$clone/.git" ] || { rm -rf "$clone" 2>/dev/null; git clone -q "$GH" "$clone" || return 1; }
  ln -sfn "$DATA" "$clone/data"
}

reset_clone(){  # start every ticket on a CLEAN, CURRENT main: drop old work branches + untracked,
                # pull the latest merged studies so workers never redo completed work.
  ( cd "$clone" 2>/dev/null || exit 0
    git checkout -q main 2>/dev/null
    git fetch -q origin main 2>/dev/null && git reset -q --hard origin/main 2>/dev/null
    git for-each-ref --format='%(refname:short)' refs/heads/ 2>/dev/null \
      | grep -vx main | xargs -r -n1 git branch -qD 2>/dev/null
    git clean -fdq -e data 2>/dev/null )
  ln -sfn "$DATA" "$clone/data"
}

kill_codex(){   # tear down this pane's codex + jail FULLY (no orphan subprocesses -> no overload)
  tmux -S "$SOCK" kill-session -t "$SESS" 2>/dev/null
  sleep 1
  # belt-and-suspenders: --unshare-pid already reaps the jail tree when bwrap dies, but kill any
  # straggler bwrap/codex bound to THIS clone just in case (match the unique --bind <clone> arg).
  pkill -9 -f -- "--bind $clone " 2>/dev/null
  sleep 0.3
}

start_codex(){
  kill_codex
  tmux -S "$SOCK" new-session -d -s "$SESS" -x 220 -y 50
  tmux -S "$SOCK" send-keys -t "$SESS" -l "cd $clone && CODEX_HOME=$CODEX_HOME bash $WRAP" 2>/dev/null
  tmux -S "$SOCK" send-keys -t "$SESS" Enter
}

wait_ready(){   # codex composer truly idle-ready
  local i c
  for ((i=1;i<=50;i++)); do
    alive || return 1
    c="$(cap)"
    # codex shows a folder-trust modal on a fresh clone ("1. Yes, continue / Press enter"); accept it.
    if printf '%s' "$c" | grep -qiE 'trust the contents|Do you trust'; then
      tmux -S "$SOCK" send-keys -t "$SESS" Enter 2>/dev/null; sleep 3; continue
    fi
    printf '%s' "$c" | grep -qiE 'Booting|Loading|Starting MCP' && { sleep 2; continue; }
    printf '%s' "$c" | grep -qiE 'Tip:|/model to change' && { sleep 1; return 0; }
    sleep 2
  done
  return 1
}

inject_goal(){  # the PROVEN sequence: clear composer, send whole /goal as ONE blob, double-Enter
  tmux -S "$SOCK" send-keys -t "$SESS" Escape 2>/dev/null; sleep 0.3
  local k; for ((k=1;k<=50;k++)); do tmux -S "$SOCK" send-keys -t "$SESS" BSpace 2>/dev/null; done; sleep 0.4
  tmux -S "$SOCK" send-keys -t "$SESS" -l -- "$GOAL" 2>/dev/null; sleep 1.2
  tmux -S "$SOCK" send-keys -t "$SESS" Enter; sleep 1.5
  tmux -S "$SOCK" send-keys -t "$SESS" Enter
  # confirm it actually engaged (Goal active / Pursuing / Working), retry once if not
  local i c
  for ((i=1;i<=10;i++)); do
    c="$(cap)"
    printf '%s' "$c" | grep -qiE 'Goal active|Pursuing goal|Working \(' && return 0
    printf '%s' "$c" | grep -qiE 'Unrecognized command|/model goal' && return 1
    sleep 1
  done
  return 1
}

wait_goal(){    # 0=achieved, 3=codex died, 1=timeout  (queue-empty is detected via the REAL queue
                # in the main loop — never by grepping pane text, which contains the prompt's own
                # "if it says queue empty" and would false-trigger.)
  local start now c; start=$(date +%s 2>/dev/null||echo 0)
  while :; do
    alive || return 3
    c="$(cap)"
    printf '%s' "$c" | grep -qiE 'Goal achieved|Goal completed' && return 0
    now=$(date +%s 2>/dev/null||echo 0); [ $((now-start)) -ge "$GOAL_TIMEOUT" ] && return 1
    sleep 10
  done
}

queue_open(){ /home/billy/tn/bin/tn ticket list testbeam 2>/dev/null | grep -oE 'open=[0-9]+' | cut -d= -f2; }

setup_clone || { log "clone failed"; exit 1; }
trap 'kill_codex; log "controller exiting; codex torn down"; exit 0' TERM INT
log "controller start (clone=$clone, sock=$SOCK)"
while :; do
  reset_clone        # clean, current main before each ticket
  start_codex
  if ! wait_ready; then log "codex not ready; restart in 10s"; sleep 10; continue; fi
  if ! inject_goal; then log "goal injection failed; restart"; sleep 5; continue; fi
  log "goal injected; pursuing"
  wait_goal; rc=$?
  case "$rc" in
    0) log "Goal achieved" ;;
    3) log "codex died; restart" ;;
    1) log "ticket timed out (${GOAL_TIMEOUT}s); restart" ;;
  esac
  # If the queue is genuinely empty, idle a while instead of busy-restarting.
  if [ "$role" = worker ] && [ "$(queue_open)" = "0" ]; then log "queue truly empty; idle 120s"; kill_codex; sleep 120; fi
  kill_codex                  # ensure no orphan subprocesses between rounds
  sleep "$POST_IDLE"          # workers: brief; planner: ~20 min between planning rounds
done
