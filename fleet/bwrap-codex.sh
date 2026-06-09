#!/bin/bash
# ~/.tb-bwrap-codex.sh — external bubblewrap sandbox for ccb-testbeam fleet workers.
#
# WHY THIS EXISTS
#   codex 0.129-alpha's INTERNAL Landlock sandbox is broken on this machine's kernel (5.15,
#   Landlock ABI v1): with `--sandbox workspace-write` it grants write access ONLY to the
#   workspace cwd, and NOT to `.git` (carved out read-only) nor to ANY `--add-dir` writable
#   root (advertised in its header but silently unenforced — `touch` into a whitelisted root
#   returns EROFS). Net effect: a sandboxed worker cannot commit, branch, open a PR, or claim a
#   tn-ticket. That is why the fleet stalled (2026-06-09 diagnosis).
#
# THE FIX (keeps codex 0.129 pinned — do NOT upgrade)
#   Run codex with its broken internal sandbox bypassed (`--dangerously-bypass-approvals-and-
#   sandbox`, which codex docs explicitly intend "for environments that are externally
#   sandboxed") and confine it with bubblewrap instead, which DOES enforce the boundaries:
#     rw : this worker's clone (incl. .git), the tn-ticket queue, caches, gh config, CODEX_HOME
#     ro : EVERYTHING else — the canonical repo, the immutable data store, all other clones
#   Proven 2026-06-09: inside this jail, `git commit` + `tn ticket claim` SUCCEED, while writes
#   to the canonical repo / data / other clones return "Read-only file system". So a worker can
#   only ever damage its own disposable clone — the same safety guarantee the original (broken)
#   sandbox aimed for, now actually delivered. This is SAFE despite the scary bypass flag.
#
# The codex-supervisor invokes this script as CODEX_SUPERVISOR_CMD, with cwd = the worker clone.
set -uo pipefail

CLONE="$PWD"
CODEX_BIN="/home/billy/.nvm/versions/node/v24.12.0/bin/codex"
DATA=/home/billy/ccb-data

RW=( --bind "$CLONE" "$CLONE"
     --bind /home/billy/.config/tn /home/billy/.config/tn
     --bind /home/billy/.cache    /home/billy/.cache )
# codex's embedded app server writes to the DEFAULT ~/.codex (socket/lock/log) even when
# CODEX_HOME points elsewhere — without it: "failed to initialize in-process app-server client".
[ -d /home/billy/.codex ] && RW+=( --bind /home/billy/.codex /home/billy/.codex )
[ -d /home/billy/.config/gh ] && RW+=( --bind /home/billy/.config/gh /home/billy/.config/gh )
[ -n "${CODEX_HOME:-}" ] && [ -d "$CODEX_HOME" ] && RW+=( --bind "$CODEX_HOME" "$CODEX_HOME" )
# codex's embedded app server needs a writable XDG_RUNTIME_DIR (unix socket) and /dev/shm;
# without these it dies with "failed to start embedded app server".
[ -n "${XDG_RUNTIME_DIR:-}" ] && [ -d "$XDG_RUNTIME_DIR" ] && RW+=( --bind "$XDG_RUNTIME_DIR" "$XDG_RUNTIME_DIR" )

exec bwrap \
  --ro-bind / / \
  --dev /dev --proc /proc --tmpfs /tmp --tmpfs /dev/shm \
  "${RW[@]}" \
  --ro-bind "$DATA" "$DATA" \
  --unshare-pid \
  --die-with-parent \
  "$CODEX_BIN" --dangerously-bypass-approvals-and-sandbox "$@"
