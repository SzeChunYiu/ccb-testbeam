# Active Task

- **Task ID:** AUD-AMP-003
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-22T23:07:00Z
- **Base main SHA:** `c6b86c9a5253887b709c235766687a69ee322bc2`
- **Scope:** prevent unusable pedestal values from anchoring legacy `amplitude_adc` convention decisions.
- **Finding:** v2.6.0 treated the mere presence of one pedestal-level column as acceptable evidence, even when that column was empty, malformed, or nonfinite for finite-amplitude rows.
- **Change:** v2.7.0 requires a finite pedestal value for every finite amplitude used in classification; incomplete coverage is recorded, subtraction correctness is withheld, and the command exits nonzero.
- **Validation:** `python -m py_compile` passed and focused pytest returned `3 passed in 0.08s` on exact temporary copies.
- **Boundary:** no real pulse table or A-002 input was available; convention assignments and quarantined A-002 outputs remain unresolved.
- **Status:** PARTIAL — code and synthetic regression validated; real-table audit remains blocked on data access.
