# Fleet standard — how to run the autonomous codex fleet on `billy` (THE canonical way)

**Read this before touching the fleet.** It is the hard-won, verified-working recipe for running
many codex panes autonomously on this machine. Every detail here was found by debugging a real
failure; do not "simplify" it without re-deriving why each piece exists. Verified 2026-06-09,
codex `0.129.0-alpha.15`, kernel 5.15, gpt-5.5 (ChatGPT-auth).

## TL;DR of the architecture

```
systemd --user service  tb-fleet
        └── fleet/keeper.sh forever         (always-on supervisor; no codex itself)
              ├── ensures 4 worker controllers + 1 planner controller are alive
              ├── reaps orphan jails, reaps stale ticket claims
              ├── auto-merges conflict-free PRs and marks their ticket done
              └── SAFETY: hard-stops the fleet if the data or repo ever change
        each controller = fleet/run_pane.sh <N|planner>   (one per pane)
              └── loops:  fresh interactive codex in tmux  ->  inject /goal (clean blob)
                          ->  pursue one ticket  ->  Goal achieved  ->  restart for the next
        each codex runs inside  ~/.tb-bwrap-codex.sh   (bubblewrap jail)
```

- **Workers** `tb1..tb4`: claim one ticket → reproduce + traditional + ML → `tn-ticket done` → PR.
- **Planner** `tbp`: Principal-Investigator role; reviews findings + queue and appends NEW study
  tickets so the fleet never runs dry and pulse understanding keeps deepening.
- **Queue**: local `tn-ticket` backend at `~/.config/tn/tickets/testbeam` (NOT GitHub).
- **Watch a pane**: `tmux -S /tmp/tmux-1000/tb1 attach -t tb1` (planner: `tbp`). Detach: `Ctrl-b d`.
- **Control**: `systemctl --user {status,restart,stop} tb-fleet`. Logs: `~/.tb-keeper.log`,
  `~/.tb-worker-<N>.log`, `~/.tb-planner.log`.

## The five things that were broken and how they're fixed (DO NOT regress these)

1. **codex's internal sandbox is broken on this kernel.** `codex --sandbox workspace-write` grants
   write ONLY to the cwd — not `.git`, not `--add-dir` roots (it lists them as writable but a
   `touch` returns EROFS). So a sandboxed worker cannot commit, PR, or claim a ticket.
   **Fix:** run codex with its sandbox bypassed (`--dangerously-bypass-approvals-and-sandbox`)
   inside an EXTERNAL **bubblewrap** jail — `~/.tb-bwrap-codex.sh`. The jail makes rw = the
   worker's clone (incl `.git`) + the tn-ticket queue + caches + `~/.codex` + `$CODEX_HOME` +
   `$XDG_RUNTIME_DIR` + tmpfs `/dev/shm`,`/tmp`; ro = everything else (canonical repo, the
   IMMUTABLE data, other clones). Proven: git commit + ticket claim work; data/repo writes EROFS.
   The bwrap jail also needs `--bind ~/.codex` (codex's app server writes there even with a custom
   CODEX_HOME) and a writable `$XDG_RUNTIME_DIR`+`/dev/shm` (else "failed to start app server").

2. **`/goal` got mangled to `/model` and path slashes were eaten.** The codex-supervisor injects a
   prompt by sending `/` alone, waiting, then the body — into the TUI slash-menu. On this build
   that mis-resolves `/goal` → `/model` and eats any other `/` (e.g. `fleet/X.md` → `fleetX.md`).
   **Fix (the STANDARD delivery):**
   - Use INTERACTIVE codex (NOT `codex exec` — exec returns a bogus "You've hit your usage limit"
     even when the account is fine).
   - Inject the WHOLE `/goal …` line as ONE literal keystroke blob (`tmux send-keys -l -- "$GOAL"`),
     then double-Enter. Never decouple the slash.
   - Keep the body **slash-free** — only the leading `/goal` may contain a slash. Describe paths in
     words ("a reports subfolder named by the ticket id"), never `fleet/…`.
   - Inject ONLY after the composer is ready (`Tip:` shown), and first dismiss the folder-trust
     modal ("1. Yes, continue") with Enter.
   `/goal` is a real, working codex command ("Goal active … Goal achieved") — it is what makes a
   pane pursue and finish the objective. This recipe lives in `fleet/run_pane.sh`.

3. **"You've hit your usage limit" is usually a LIE.** It appears from `codex exec` and from
   mangled input even when the account has full quota (confirmed: a manual `codex` /goal runs fine
   the same second). NEVER diagnose a fleet stall as a rate limit. It is almost always a
   delivery/approach problem. Use interactive codex + clean `/goal`.

4. **Orphan subprocesses overload the machine.** Killing a pane left codex's `node` / vendor /
   `systemd-inhibit` children orphaned (bwrap without a PID namespace doesn't reap them).
   **Fix:** the jail uses `--unshare-pid --die-with-parent`, so the whole tree dies with the pane;
   `run_pane.sh` also `pkill`s any straggler `--bind <clone>` on restart, and the keeper reaps any
   jail whose tmux session is gone. Always tear down fully before relaunching.
   (Note: `ps | grep --bind <clone>` shows 2 bwrap procs per pane — outer + namespace-init — and
   the path appears twice per line; that is ONE healthy session, not duplicates.)

5. **The tn-ticket shim resolved its lib dir wrong.** `~/.local/bin/tn-ticket` → `~/tn/bin/tn`
   didn't dereference the symlink, so `TN_LIB` pointed at `~/.local/lib` (no store script).
   **Fix:** `~/tn/bin/tn` now `readlink -f`s `$BASH_SOURCE` before computing `TN_LIB`. The keeper
   uses the real binary `/home/billy/tn/bin/tn ticket … testbeam` (the old `~/bin/tn-ticket` is the
   GitHub backend and is NOT our queue).

## Operating it

```bash
# start / restart everything (the keeper brings up all panes):
systemctl --user restart tb-fleet
# scale workers:  edit TB_WORKERS in ~/.config/systemd/user/tb-fleet.service, then restart
# stop everything:
systemctl --user stop tb-fleet ; pkill -f run_pane.sh ; pkill -f -- '--bind /home/billy/.tb-workers/'
# queue:
/home/billy/tn/bin/tn ticket list testbeam
/home/billy/tn/bin/tn ticket add  testbeam "<title>" <<<"<body>"
```

## Data safety (never compromise — see LESSONS.md)
The 6 GB data lives OUTSIDE the repo at `/home/billy/ccb-data` (immutable, `chattr +i`), exposed
read-only into each clone as `./data`. The keeper hard-stops the whole fleet if the data file
count changes or the canonical repo disappears. A worker can only ever write inside its own
disposable clone.
