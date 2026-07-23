# Active Task

- **Task ID:** AUD-AMP-005
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T01:05:04Z
- **Base main SHA:** `947df912016b97d7d21160c1f4e8f2b075c4cbda`
- **Scope:** require the pedestal data needed to execute a hash-bound `ABSOLUTE` amplitude convention while avoiding false rejection of hash-bound `NET` tables.
- **Finding:** v2.8.0 accepted any hash-bound convention without checking whether an `ABSOLUTE` table had one unique, complete pedestal column. Its aggregate gate followed heuristic baseline state and could also reject `NET` evidence because an optional pedestal diagnostic was incomplete.
- **Change:** v2.9.0 makes physics acceptance convention-specific: `ABSOLUTE` requires a unique complete pedestal, while `NET` requires no subtraction. Every non-acceptable physics state is counted by `n_nonaccepted_physics_conventions` and fails the CLI.
- **Validation:** `python -m py_compile` passed and focused pytest returned `3 passed in 0.04s` on exact local reconstructions.
- **Boundary:** no real pulse table or A-002 input was available; convention assignments and quarantined A-002 outputs remain unresolved.
- **Status:** PARTIAL — code and synthetic regression validated; real-table audit remains blocked on exact data and reviewed evidence.
