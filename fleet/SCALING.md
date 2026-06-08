# Scaling to many agents (target: ~100 concurrent)

At 5 agents the bottleneck is compute. At 100 it is **coordination**: git contention, merge
conflicts, and GitHub API rate limits. This document is the architecture that makes 100
concurrent workers actually work, and the honest limits.

## The five bottlenecks and their fixes

### 1. Work isolation — never share a checkout
100 agents in one working tree clobber each other's branch on every `git switch`. **Each agent
works in its own git worktree** rooted on node-local fast storage:
```
<node-worktrees-root>/<worker-label>/   # e.g. ~/.tb-worktrees/lunarc-a-07/
```
Worktrees share one `.git` (cheap) but have independent working dirs and HEADs. The supervisor
auto-prunes stale worktrees. **Data is NOT in the worktree** (it's gitignored) — every worker
reads it by **absolute path** (`/.../test_beam/data/` on laptop, the LUNARC mirror on cluster),
never relative.

### 2. Conflict-free outputs — one writer per file
The killer at scale is 100 PRs all editing `SUMMARY.md` / `STUDIES.md` / `docs/`. Rule:
- A worker writes **only** files it owns: its own `reports/<ticket-id>__<slug>/` directory and
  **new, name-spaced** `scripts/sNN_*.py` / `configs/sNN_*.yaml`. Prefix every new file with the
  study id so two studies never create the same path.
- A worker **never edits a shared file** (`SUMMARY.md`, `STUDIES.md`, `docs/*`, `DATA.md`).
  Instead it emits a machine-readable **`reports/<id>/result.json`** (schema below). The
  **Integrator** (one role) regenerates the shared files from all `result.json`s. This turns a
  100-way merge conflict into 100 independent directories.

### 3. The merge funnel — Integrator + auto-merge
100 workers cannot each merge to `main`. A small **Integrator** pool (1–2 agents,
[INTEGRATOR_PROTOCOL.md](INTEGRATOR_PROTOCOL.md)):
- Auto-merges any PR that is **green + touches only its own `reports/<id>/` + name-spaced
  scripts** (these can never conflict). 
- Routes PRs that touch shared files or fail the Critic to a human/critic queue.
- Regenerates `SUMMARY.md` (the scoreboard) and the `docs/09` open-questions list from the
  `result.json` files — the single writer of those files.

### 4. Queue at scale — GitHub API is the hard limit
`tn-ticket` is GitHub-issues-backed. **GitHub REST allows ~5,000 requests/hour per user.** A
claim+work+done+PR cycle is ~10–30 API calls. At 100 agents that is thousands of calls/hour —
you *will* throttle. Mitigations, in order:
- **Coarse-grained tickets.** One substantial study per session (10–30 min of compute), not
  micro-claims. Compute-bound agents make few API calls per hour. This is the biggest lever.
- **Jittered polling / backoff.** Workers stagger `tn-ticket` calls; honor `Retry-After`.
- **Two GitHub identities.** `SzeChunYiu` + `Babbloo-studio` ≈ 2× the budget; assign half the
  fleet to each token. (Beyond ~2× you need a non-GitHub queue.)
- **Reliability:** workers MUST verify `claim`/`done` actually succeeded and retry; the
  orchestrator periodically **reconciles** queue drift (the S00 worker did the science but its
  `done`/`append` did not stick — at scale, assume self-reported state is lossy and reconcile).
- **Beyond ~100 / multi-node:** move the queue to a local dispatcher (one process holds the
  backlog, hands out work over a socket, syncs to GitHub at low frequency). Designed, not built.

### 5. Compute topology — multi-node
| Tier | Hardware | Panes | Notes |
|---|---|---|---|
| Laptop `billy` | 16 cores / 31 GB / A3000 6 GB | **4–5** | light `[L]` studies; ~600 MB+1 thread per pane |
| LUNARC node ×1 | 48 CPU | **~30–40** | `NODE_MAX_PANES=40`; RLIMIT_NPROC ~4096; 1 BLAS thread/pane |
| **100 agents** | laptop + **~3 LUNARC nodes** | 100 | book nodes via SLURM; mirror data to project storage |

Codex **account rate limits** also bind: the supervisor respawns panes on usage-limit; spread
across accounts. GPU studies (S08/S09) need GPU nodes, not the 48-CPU CPU nodes.

## result.json schema (every study emits this)
```json
{
  "study": "S04", "ticket": 2369, "worker": "lunarc-a-07",
  "title": "Same-particle timing resolution",
  "reproduced": true, "repro_tolerance": "<1%",
  "traditional": {"metric": "sigma_B6_ns", "value": 0.71, "ci": [0.68, 0.74]},
  "ml":          {"metric": "sigma_B6_ns", "value": 0.69, "ci": [0.66, 0.72]},
  "ml_beats_baseline": false,
  "falsification": {"preregistered_metric": "sigma_B6_ns", "p_value": 0.21, "n_tries": 3},
  "input_sha256": "….", "git_commit": "….",
  "critic": "pending",
  "next_tickets": ["S04b: full-RMS + chi2/ndf", "S05: stave-error independence"]
}
```

## Rollout plan (validate coordination at each step)
1. **5 (laptop now):** confirm worktree isolation + conflict-free outputs + auto-merge work with
   real concurrency. Fix what breaks here — it is cheap.
2. **~25 (1 LUNARC node):** confirm GitHub API headroom holds; tune ticket granularity & jitter.
3. **~100 (laptop + ~3 nodes, both GH accounts):** add the Integrator pool and reconciler.

Do not jump to 100 before step 1 surfaces the coordination bugs. Scale is earned, not assumed.
