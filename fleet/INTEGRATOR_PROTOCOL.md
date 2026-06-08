# Integrator protocol

A small dedicated pool (1–2 agents) that is the **single writer of shared files** and the
**merge funnel** for the fleet. This is what lets 100 workers run without a 100-way merge
conflict. Workers never edit shared files; the Integrator owns them.

## Loop (runs continuously, low frequency to spare GitHub API)
1. **List open PRs** to `main` (`gh pr list`).
2. For each PR, classify by changed paths:
   - **Auto-mergeable:** touches ONLY a single `reports/<id>__*/` dir + name-spaced
     `scripts/s<NN>_*` / `configs/s<NN>_*`. These cannot conflict.
   - **Needs review:** touches any shared file, or multiple study dirs, or core code.
3. **Gate auto-mergeable PRs:**
   - CI/green check passes (if configured).
   - A **Scientific Critic** verdict exists and is `critic:accept` (see
     [CRITIC_PROTOCOL.md](CRITIC_PROTOCOL.md)). If missing, assign/await a critic; do not merge
     unreviewed science.
   - `manifest.json` present and re-runs to the headline number (spot-check, not every PR).
   - Then squash-merge + delete branch.
4. **Reject/route** PRs that edit shared files (a worker broke the conflict-free rule → comment,
   bounce back) or fail the Critic.
5. **Regenerate shared files from `result.json`** (the Integrator is their ONLY writer):
   - `reports/SUMMARY.md` — the scoreboard: one row per study (reproduced? · traditional · ML ·
     winner · Δ · critic verdict · report link). Sort by phase/study id.
   - `docs/09_open_questions.md` — fold in each study's resolved/raised open questions.
   - (later) the Elo board and the findings knowledge-graph.
   Commit these as a single Integrator commit. Because workers never touch them, this never
   conflicts.
6. **Reconcile the queue** (state is lossy): for every merged study PR, ensure its ticket is
   `factory:done`; for every `result.json next_tickets`, ensure the ticket exists; close
   duplicates. The Integrator is the source of truth for queue health.
7. **Meta-review:** skim recent Critic verdicts; if a failure pattern recurs, append one line to
   [LESSONS.md](LESSONS.md) (injected into every new worker).

## Rules
- The Integrator does **not** do studies — it merges, aggregates, reconciles, and curates.
- Never auto-merge unreviewed science (Critic gate is mandatory).
- Keep API usage low: batch, poll on a relaxed cadence, honor `Retry-After`.
- Be conservative: when unsure whether a PR is conflict-free, route to review, don't auto-merge.

## Auto-merge classifier (paths)
```
auto_mergeable(pr) :=  changed_files(pr) ⊆  reports/<one id>__*/**  ∪  scripts/s<NN>_*  ∪  configs/s<NN>_*
                       AND no shared file touched (SUMMARY.md, STUDIES.md, docs/**, DATA.md, README.md, .codex-supervisor.toml, codex-prompts*, fleet/**)
```
