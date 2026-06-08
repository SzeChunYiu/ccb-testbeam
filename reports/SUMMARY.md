# Rolling summary / scoreboard

Maintained by the orchestrator/Integrator. One row per study as results land.

| Study | Status | Reproduced? | Traditional | ML | ML beats baseline? | Report/PR |
|---|---|---|---|---|---|---|
| S00 | ✅ done | ✅ 640,737 exact | per-stave counts | run-split sanity | — (foundation) | reports/S00_… (PR #1) |
| S01b | ✅ merged | ✅ raw-ROOT re-deriv | selection rule | run-split check | — | reports/…s01b… (PR #2) |

_Fleet: 5 sandboxed laptop workers, deep queue (~35 tickets: S03–S16 + P01–P11). Keeper auto-merges
conflict-free PRs, reaps stale claims, guards data/repo. LUNARC down for a few days → laptop only._
