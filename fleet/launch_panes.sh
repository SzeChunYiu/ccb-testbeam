#!/bin/bash
# launch_panes.sh [N] — start N autonomous worker panes + 1 planner pane, the PROVEN way.
# Each pane = a run_pane.sh controller (interactive codex + clean /goal blob injection, cycling).
#   workers : tb1..tbN   (claim + study + done + PR, cycling)
#   planner : tbp        (Principal Investigator: keeps the queue deep with new study directions)
# Watch:  tmux -S /tmp/tmux-1000/tb<N> attach -t tb<N>   (planner: tbp)
set -uo pipefail
N="${1:-4}"
REPO=/home/billy/Desktop/test_beam
start_one(){ # $1 = arg (N or planner), $2 = match-pattern
  pkill -9 -f "run_pane.sh $1\b" 2>/dev/null
  nohup bash "$REPO/fleet/run_pane.sh" "$1" >/dev/null 2>&1 &
}
for n in $(seq 1 "$N"); do
  start_one "$n"
  echo "[tb$n] worker controller started (watch: tmux -S /tmp/tmux-1000/tb$n attach -t tb$n)"
  sleep 1
done
start_one planner
echo "[tbp] planner controller started (watch: tmux -S /tmp/tmux-1000/tbp attach -t tbp)"
echo "launched $N workers + 1 planner."
