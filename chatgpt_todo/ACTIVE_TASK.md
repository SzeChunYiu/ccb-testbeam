# Active Task

- **Task ID:** AUD-MC-002
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T030239Z
- **Initial remote main SHA:** `a4b996ccbdfeea120e6deaead863f19d468d1091`
- **Scope:** audit issue #880 event-weight failure handling, bias direction/denominator semantics, and retained result provenance.
- **Repository evidence:** producer blob `bc1220fdfe1010989fd8ab273f8c1b1fcf708b2c`; result blob `37d69e2c697a7ce7c9e1eff9aeff48539551d922`; merged PR #897; open issue #880.
- **Confirmed defects:** nonfinite weights become `1.0`; four weighted helpers can fall back to unweighted estimators; signed fields use weighted-minus-unweighted while prose describes legacy bias; ROOT hash, producer commit, generation command, and policy/version are absent.
- **Independent calculation:** first-B weighted change relative to unweighted is `-68.022432%`, whereas legacy overstatement relative to weighted is `+212.719216%`; deuteron legacy-minus-weighted is `+40.585087 pp` and `+244.399660%` relative to weighted.
- **Validation:** focused py_compile passed; pytest returned `6 passed in 0.04s`; JSON and SVG parsed; changed Python lines are at most 99 characters.
- **Scientific boundary:** exact ROOT bytes were unavailable; no production rerun, uncertainty propagation, event-weight-definition proof, or data/MC closure is claimed.
- **Status:** PARTIAL — audit gate and visual evidence validated; retained study remains FLAWED pending strict content-addressed rerun.
